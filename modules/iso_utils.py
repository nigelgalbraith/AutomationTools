
#!/usr/bin/env python3
"""
iso_utils.py

Validate Ubuntu Desktop ISOs and embed autoinstall YAML.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from modules.system_utils import expand_path, run_cmd


# ---------------------------------------------------------------------
# PATH VALIDATION
# ---------------------------------------------------------------------

def _validate_input_path(value: str, name: str) -> Path:
    """Expand and validate one readable input file."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty path.")
    path = Path(expand_path(value)).resolve()
    if not path.exists():
        raise FileNotFoundError(f"{name} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{name} is not a regular file: {path}")
    if not os.access(path, os.R_OK):
        raise PermissionError(f"{name} is not readable: {path}")
    return path


def _validate_output_path(output_iso: str, inputs: tuple[Path, ...]) -> None:
    """Require a new output in a writable directory."""
    if not isinstance(output_iso, str) or not output_iso.strip():
        raise ValueError("output_iso must be a non-empty path.")
    output = Path(os.path.abspath(expand_path(output_iso)))
    if output.resolve() in inputs:
        raise ValueError("Output must differ from the input files.")
    if os.path.lexists(output):
        raise FileExistsError(f"Output already exists: {output}")
    if not output.parent.is_dir() or not os.access(output.parent, os.W_OK | os.X_OK):
        raise ValueError(f"Output directory must exist and be writable: {output.parent}")


def validate_iso_paths(source_iso: str, autoinstall_path: str, output_iso: str) -> bool:
    """Validate source ISO, YAML and output paths."""
    source = _validate_input_path(source_iso, "source_iso")
    autoinstall = _validate_input_path(autoinstall_path, "autoinstall_path")
    _validate_output_path(output_iso, (source, autoinstall))
    return True


# ---------------------------------------------------------------------
# UBUNTU VALIDATION
# ---------------------------------------------------------------------

def validate_ubuntu_yaml(autoinstall_path: str) -> bool:
    """Validate autoinstall YAML and require interactive storage."""
    import yaml

    path = _validate_input_path(autoinstall_path, "autoinstall_path")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise ValueError(f"Invalid YAML syntax: {path}") from None
    if not isinstance(data, dict):
        raise ValueError("Autoinstall YAML must contain a mapping.")
    if "autoinstall" in data:
        if set(data) != {"autoinstall"}:
            raise ValueError("Installation-media YAML must have only the autoinstall top-level key.")
        data = data["autoinstall"]
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Autoinstall configuration must specify version: 1.")
    if data.get("interactive-sections") != ["storage"]:
        raise ValueError("Autoinstall configuration must specify interactive-sections: [storage].")
    print(f"[OK] Autoinstall YAML validated: {path}")
    return True


def validate_ubuntu_iso(source_iso: str) -> bool:
    """Verify Ubuntu Desktop installation media metadata."""
    import yaml

    source = _validate_input_path(source_iso, "source_iso")
    with tempfile.TemporaryDirectory(prefix=".ubuntu-iso-check-") as directory:
        info = Path(directory) / "info"
        sources = Path(directory) / "install-sources.yaml"
        result = run_cmd([
            "xorriso", "-abort_on", "FAILURE", "-return_with", "SORRY", "32",
            "-indev", str(source),
            "-osirrox", "on",
            "-extract", "/.disk/info", str(info),
            "-extract", "/casper/install-sources.yaml", str(sources),
            "-end",
        ], show_cmd=False)
        if result is None or result.returncode != 0 or not info.is_file() or not sources.is_file():
            raise ValueError("Unable to read Ubuntu Desktop ISO metadata.")
        if not info.read_text(encoding="utf-8").startswith("Ubuntu "):
            raise ValueError("Only Ubuntu Desktop installation media is supported.")
        data = yaml.safe_load(sources.read_text(encoding="utf-8"))
        entries = data.get("sources", []) if isinstance(data, dict) else data
        if not isinstance(entries, list) or not any(
            isinstance(entry, dict) and entry.get("id") in ("ubuntu-desktop", "ubuntu-desktop-minimal")
            and entry.get("variant") == "desktop" for entry in entries
        ):
            raise ValueError("ISO does not contain a supported Ubuntu Desktop installation source.")
    print(f"[OK] Ubuntu ISO validated: {source}")
    return True


def validate_ubuntu_iso_plan(source_iso: str, autoinstall_path: str, output_iso: str) -> bool:
    """Validate the configured ISO creation before confirmation."""
    errors = []
    for validate, args in (
        (validate_iso_paths, (source_iso, autoinstall_path, output_iso)),
        (validate_ubuntu_yaml, (autoinstall_path,)),
        (validate_ubuntu_iso, (source_iso,)),
    ):
        try:
            validate(*args)
        except Exception as e:
            errors.append(str(e))
    if errors:
        raise ValueError("ISO validation failed:\n" + "\n".join(errors))
    return True


# ---------------------------------------------------------------------
# GENERATED ISO VERIFICATION
# ---------------------------------------------------------------------

def _read_boot_metadata(iso_path: Path) -> list[tuple[str, tuple[str, ...]]]:
    """Read stable boot attributes, excluding relocated sectors and generated GUIDs."""
    result = run_cmd([
        "xorriso", "-abort_on", "FAILURE", "-return_with", "SORRY", "32",
        "-indev", str(iso_path),
        "-report_el_torito", "plain", "-report_system_area", "plain", "-end",
    ], show_cmd=False)
    if result is None or result.returncode != 0:
        raise RuntimeError(f"Unable to inspect ISO boot metadata: {iso_path}")
    lines = (result.stdout or "").splitlines()
    efi_partitions = set()
    for line in lines:
        key, _, value = line.partition(":")
        fields = value.split()
        if key.strip() == "GPT type GUID" and len(fields) == 2 and fields[1].lower() == "28732ac11ff8d211ba4b00a0c93ec93b":
            efi_partitions.add(fields[0])
    metadata = []
    for line in lines:
        key, separator, value = line.partition(":")
        key = key.strip()
        fields = tuple(value.split())
        if key == "El Torito boot img":
            if len(fields) != 8:
                raise RuntimeError("Unrecognized El Torito boot image report.")
            metadata.append((key, fields[:-1]))
        elif key == "MBR partition":
            metadata.append((key, fields[:3]))
        elif key in ("GPT type GUID", "GPT partition flags") and fields and fields[0] in efi_partitions:
            metadata.append((key, fields[1:]))
        elif separator and key in (
            "El Torito cat path", "El Torito img opts", "System area summary",
            "Partition offset",
        ):
            metadata.append((key, fields))
    if not any(key == "El Torito boot img" and fields[2] == "y" for key, fields in metadata):
        raise RuntimeError(f"ISO has no recognized bootable El Torito images: {iso_path}")
    return metadata


def _verify_generated_iso(source: Path, generated: Path, autoinstall: Path) -> None:
    """Verify embedded YAML and boot metadata before publishing."""
    if not generated.is_file() or generated.stat().st_size == 0:
        raise RuntimeError("xorriso did not produce a non-empty ISO.")
    print("[INFO] Verifying embedded YAML and ISO boot metadata.")
    with tempfile.TemporaryDirectory(prefix=".iso-verify-", dir=generated.parent) as directory:
        embedded = Path(directory) / "autoinstall.yaml"
        result = run_cmd([
            "xorriso", "-abort_on", "FAILURE", "-return_with", "SORRY", "32",
            "-indev", str(generated), "-osirrox", "on",
            "-extract", "/autoinstall.yaml", str(embedded), "-end",
        ], show_cmd=False)
        if result is None or result.returncode != 0 or not embedded.is_file():
            raise RuntimeError("Unable to verify /autoinstall.yaml in the generated ISO.")
        if embedded.read_bytes() != autoinstall.read_bytes():
            raise RuntimeError("Embedded autoinstall.yaml differs from the selected YAML.")
    if _read_boot_metadata(source) != _read_boot_metadata(generated):
        raise RuntimeError("Generated ISO boot metadata differs from the source ISO.")


# ---------------------------------------------------------------------
# UBUNTU ISO CREATION
# ---------------------------------------------------------------------

def add_ubuntu_autoinstall(source_iso: str, autoinstall_path: str, output_iso: str) -> bool:
    """Embed autoinstall YAML, preserve boot equipment and publish safely."""
    validate_ubuntu_iso_plan(source_iso, autoinstall_path, output_iso)
    source = Path(expand_path(source_iso)).resolve()
    autoinstall = Path(expand_path(autoinstall_path)).resolve()
    output = Path(os.path.abspath(expand_path(output_iso)))
    with tempfile.TemporaryDirectory(prefix=".iso-editor-", dir=output.parent) as temporary_dir:
        temporary_iso = Path(temporary_dir) / "output.iso"
        result = run_cmd([
            "xorriso",
            "-abort_on", "FAILURE",
            "-return_with", "SORRY", "32",
            "-report_about", "UPDATE",
            "-indev", str(source),
            "-outdev", str(temporary_iso),
            "-map", str(autoinstall), "/autoinstall.yaml",
            "-boot_image", "any", "replay",
            "-commit",
            "-end",
        ], stream=True, show_cmd=False)
        if result is None or result.returncode != 0:
            raise RuntimeError("xorriso failed to create the output ISO.")
        _verify_generated_iso(source, temporary_iso, autoinstall)
        os.link(temporary_iso, output)
    print(f"[INFO] Saved ISO: {output}")
    return True
