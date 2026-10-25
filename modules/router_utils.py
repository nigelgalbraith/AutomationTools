from __future__ import annotations
import base64
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from modules.router_encryption_utils import (
    SUPPORTED_HASHES,
    crypt_aes_256_cbc,
    crypt_technicolor_thenc,
    validate_legacy_key_specs,
    interpret_password_credentials,
    validate_device_key_specs,
    load_device_key_credentials,
)

# ---------------------------------------------------------------------
# FILE CONSTANTS
# ---------------------------------------------------------------------

DECODED_EXTENSION = ".tar.gz"
MODEL_SPECS_EXTENSION = ".json"
CONFIG_FIELDS_KEY = "config_fields"
CONFIG_FIELDS_FILE_KEY = "file"

ENCRYPTION_HANDLERS = {
    ("aes-256-cbc", "openssl-legacy"): crypt_aes_256_cbc,
    ("aes-256-cbc", "device-key"): crypt_technicolor_thenc,
}

ROUTER_SPEC_SCHEMA = {
    "model": str, "firmware": str, "hardware": str,
    "encryption": str, "encoding": str, "salted": bool,
    "password_base": str, "password_hash": str, "key_derivation": str,
    "config_fields": {"file": str, "wifi_2g_ssid": str, "wifi_2g_password": str,
                      "wifi_5g_ssid": str, "wifi_5g_password": str},
    "password_required": bool, "key_derivation_digest": str,
    "backup_format": {
        "type": str, "header_lines": int, "preserve_header": bool,
        "payload_line_length": int, "newline": str,
        "checksum": {"algorithm": str, "scope": str, "encoding": str,
                     "after_payload_lines": int,
                     "prefix": {"encoding": str, "random_bytes": int}},
        "trailer": {"character": str, "repeat": int},
        "iv_length": int, "signature_length": int, "preamble": str,
        "backup_version": str, "header_terminator": str,
    },
    "archive": {"format": str, "compression": str},
    "configuration_format": str,
}


# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

def validate_model_specs(specs: dict) -> None:
    """Validate the complete schema and the selected mechanism settings."""
    validate_spec_schema(specs)
    for key in ("model", "firmware", "hardware", "encryption", "encoding", "key_derivation"):
        value = specs[key]
        require_setting(value, key, isinstance(value, str) and bool(value.strip()) and not any(c in value for c in "\r\n\x00"))
    mechanism = (specs["encryption"], specs["key_derivation"])
    if mechanism not in ENCRYPTION_HANDLERS:
        raise ValueError(f"Unsupported encryption mechanism: {mechanism}")
    if specs["key_derivation"] == "openssl-legacy":
        validate_legacy_key_specs(specs)
    elif specs["key_derivation"] == "device-key":
        validate_device_key_specs(specs)
    if specs["encoding"] == "base64":
        validate_base64_specs(specs)
    elif specs["encoding"] != "binary":
        raise ValueError(f'Unsupported encoding: {specs["encoding"]}')
    fmt = specs["backup_format"]
    if fmt["type"] not in ("line-wrapper", "technicolor-thenc"):
        raise ValueError(f'Unsupported backup_format.type: {fmt["type"]}')
    value = fmt["header_lines"]
    require_setting(value, "backup_format.header_lines", isinstance(value, int) and value >= 0)
    require_setting(fmt["preserve_header"], "backup_format.preserve_header", not value or fmt["preserve_header"])
    if fmt["type"] == "line-wrapper":
        validate_line_wrapper_specs(specs)
    else:
        # Binary wrappers use JSON-defined boundaries rather than line checksums.
        require_setting(specs["encoding"], "encoding", specs["encoding"] == "binary")
        require_null_settings(fmt, ("payload_line_length", "newline"), "backup_format")
        require_null_settings(fmt["checksum"], ("algorithm", "scope", "encoding", "after_payload_lines"), "backup_format.checksum")
        require_null_settings(fmt["checksum"]["prefix"], ("encoding", "random_bytes"), "backup_format.checksum.prefix")
        require_null_settings(fmt["trailer"], ("character", "repeat"), "backup_format.trailer")
        for key in ("iv_length", "signature_length"):
            value = fmt[key]
            require_setting(value, f"backup_format.{key}", isinstance(value, int) and value > 0)
        for key in ("preamble", "backup_version"):
            value = fmt[key]
            require_setting(value, f"backup_format.{key}", isinstance(value, str) and bool(value.strip()) and all(32 <= ord(c) <= 126 for c in value))
        value = fmt["header_terminator"]
        require_setting(value, "backup_format.header_terminator", isinstance(value, str) and bool(value) and all(c in "\r\n" or 32 <= ord(c) <= 126 for c in value))
    if specs["archive"]["format"] is None:
        require_null_settings(specs["archive"], ("compression",), "archive")
    else:
        validate_tar_specs(specs)
    if specs["configuration_format"] is None:
        require_null_settings(specs["config_fields"], tuple(specs["config_fields"]), "config_fields")
        if specs["archive"]["format"] is not None:
            raise ValueError("archive.format must be null when configuration_format is unknown")
    elif specs["configuration_format"] == "key-value":
        validate_key_value_specs(specs)
        require_setting(specs["archive"]["format"], "archive.format", True)
    else:
        raise ValueError(f'Unsupported configuration_format: {specs["configuration_format"]}')


def validate_line_wrapper_specs(specs: dict) -> None:
    """Validate the established line layout and its applicable fields."""
    fmt = specs["backup_format"]
    require_setting(specs["encoding"], "encoding", specs["encoding"] == "base64")
    require_null_settings(fmt, ("iv_length", "signature_length", "preamble", "backup_version",
                               "header_terminator"), "backup_format")
    for key in ("payload_line_length", "newline"):
        require_setting(fmt[key], f"backup_format.{key}", True)
    require_setting(fmt["newline"], "backup_format.newline", fmt["newline"] == "\n")
    require_setting(fmt["payload_line_length"], "backup_format.payload_line_length", fmt["payload_line_length"] > 0 and fmt["payload_line_length"] % 4 == 0)
    checksum = fmt["checksum"]
    for key, allowed in (("algorithm", SUPPORTED_HASHES), ("scope", ("encoded-payload-with-newlines",)), ("encoding", ("hex-lower",))):
        require_setting(checksum[key], f"backup_format.checksum.{key}", checksum[key] in allowed)
    value = checksum["after_payload_lines"]
    require_setting(value, "backup_format.checksum.after_payload_lines", isinstance(value, int) and value >= 0)
    prefix = checksum["prefix"]
    require_setting(prefix["encoding"], "backup_format.checksum.prefix.encoding", prefix["encoding"] == "base64")
    value = prefix["random_bytes"]
    require_setting(value, "backup_format.checksum.prefix.random_bytes", isinstance(value, int) and value >= 0)
    trailer = fmt["trailer"]
    value = trailer["character"]
    require_setting(value, "backup_format.trailer.character", isinstance(value, str) and len(value) == 1 and value.isascii() and value not in "\r\n")
    value = trailer["repeat"]
    require_setting(value, "backup_format.trailer.repeat", isinstance(value, int) and value > 0)


def validate_archive(archive: tarfile.TarFile) -> list:
    """Validate all entries before any extraction or edited-file reads."""
    members = archive.getmembers()
    seen = {}
    if not members:
        raise ValueError("Empty archive")
    for member in members:
        path = safe_relative(member.name)
        if not (member.isfile() or member.isdir()) or path in seen or (path == Path('.') and not member.isdir()):
            raise ValueError(f"Unsafe or duplicate archive member: {member.name}")
        seen[path] = member
    for path in seen:
        if any(parent in seen and not seen[parent].isdir() for parent in path.parents):
            raise ValueError(f"Conflicting archive paths: {path}")
    return members


def validate_directory(directory: Path) -> None:
    """Reject symlinks and special files, including symlink ancestors."""
    if any(path.is_symlink() for path in (directory, *directory.parents)):
        raise ValueError("Unsafe directory symlink")
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"Unsafe configuration entry: {path}")


def validate_base64_specs(specs: dict) -> None:
    """Require the line width used by the existing Base64 encoder."""
    width = specs["backup_format"]["payload_line_length"]
    require_setting(width, "backup_format.payload_line_length", isinstance(width, int) and width > 0 and width % 4 == 0)


def validate_tar_specs(specs: dict) -> None:
    """Require the implemented TAR/GZIP compression."""
    if specs["archive"]["format"] != "tar":
        raise ValueError(f'Unsupported archive.format: {specs["archive"]["format"]}')
    require_setting(specs["archive"]["compression"], "archive.compression", specs["archive"]["compression"] == "gzip")


def validate_key_value_specs(specs: dict) -> None:
    """Validate populated mappings while allowing unused fields to be null."""
    fields = specs["config_fields"]
    value = fields["file"]
    require_setting(value, "config_fields.file", isinstance(value, str) and bool(value.strip()))
    try:
        safe_relative(value)
    except ValueError:
        raise ValueError("Invalid JSON key: config_fields.file; unsafe relative path") from None
    require_setting(value, "config_fields.file", not any(c in value for c in "\r\n\x00"))
    seen = set()
    for label, key in fields.items():
        if label == "file" or key is None:
            continue
        require_setting(key, f"config_fields.{label}", bool(key.strip()) and not any(c in key for c in "=\r\n\x00"))
        if key in seen:
            raise ValueError(f"Duplicate configuration mapping: config_fields.{label}")
        seen.add(key)


def validate_settings(settings: dict, allowed: tuple, category: str) -> None:
    """Reject undeclared keys, retaining the existing validation helper API."""
    for key in settings:
        if key not in allowed:
            path = f"{category}.{key}" if category else key
            raise ValueError(f"Unexpected JSON key: {path}")


def validate_spec_schema(settings: dict, schema: dict = ROUTER_SPEC_SCHEMA, prefix: str = "") -> None:
    """Check complete keys and nullable types independently of mechanisms."""
    if type(settings) is not dict:
        raise ValueError(f"Invalid JSON object: {prefix or 'model specifications'}")
    for key in schema:
        path = f"{prefix}.{key}" if prefix else key
        if key not in settings:
            raise ValueError(f"Missing JSON key: {path}")
    validate_settings(settings, tuple(schema), prefix)
    for key, kind in schema.items():
        path = f"{prefix}.{key}" if prefix else key
        value = settings[key]
        if isinstance(kind, dict):
            validate_spec_schema(value, kind, path)
        elif value is not None and type(value) is not kind:
            raise ValueError(f"Invalid JSON key: {path}; expected {kind.__name__} or null")


def require_setting(value, path: str, condition: bool) -> None:
    """Report the exact key whose mechanism-specific value is invalid."""
    if value is None or not condition:
        raise ValueError(f"Missing or invalid JSON key: {path}")


def require_null_settings(settings: dict, keys: tuple, prefix: str = "") -> None:
    """Reject settings which the selected mechanism cannot use."""
    for key in keys:
        if settings[key] is not None:
            path = f"{prefix}.{key}" if prefix else key
            raise ValueError(f"Non-applicable JSON key must be null: {path}")


def validate_tar_gzip_config(decoded: bytes, model_specs: dict) -> None:
    """Validate TAR/GZIP contents and the declared key-value configuration."""
    files = read_tar_files(decoded, model_specs)
    configured = str(safe_relative(model_specs["config_fields"]["file"]))
    if configured not in files:
        raise ValueError("Configured file missing from archive")
    parse_key_value_fields(files[configured].decode("utf-8"), model_specs)

# ---------------------------------------------------------------------
# ENCODING AND WRAPPERS
# ---------------------------------------------------------------------

def encode_base64_payload(data: bytes, specs: dict) -> bytes:
    """Produce Base64 with the configured wrapping and trailing newline."""
    if specs["encoding"] != "base64":
        raise ValueError("Unsupported encoding")
    encoded = base64.b64encode(data)
    width = specs["backup_format"]["payload_line_length"]
    return b"".join(encoded[i:i + width] + b"\n" for i in range(0, len(encoded), width))


def decode_base64_payload(data: bytes, specs: dict) -> bytes:
    """Decode the transport separately from encryption and wrapper handling."""
    if specs["encoding"] != "base64":
        raise ValueError("Unsupported encoding")
    return base64.b64decode(data.replace(b"\n", b""), validate=True)


def wrapper_trailer(fmt: dict) -> bytes:
    """Construct the configured final line."""
    return (fmt["trailer"]["character"] * fmt["trailer"]["repeat"] + fmt["newline"]).encode("ascii")


def parse_line_wrapper(data: bytes, model_specs: dict) -> dict:
    """Validate the exact wrapper and checksum before decoding the payload."""
    fmt = model_specs["backup_format"]
    checksum = fmt["checksum"]
    lines = data.splitlines(keepends=True)
    count = fmt["header_lines"]
    position = count + checksum["after_payload_lines"]
    if len(lines) <= position + 1 or lines[-1] != wrapper_trailer(fmt):
        raise ValueError("Invalid backup wrapper or trailer")
    if any(not line.endswith(b"\n") or b"\r" in line for line in lines):
        raise ValueError("Invalid wrapper newline")
    special = lines[position][:-1]
    prefix_size = checksum["prefix"]["random_bytes"]
    prefix_length = 4 * ((prefix_size + 2) // 3)
    prefix = special[:prefix_length]
    if len(base64.b64decode(prefix, validate=True)) != prefix_size:
        raise ValueError("Invalid checksum random prefix")
    encoded = b"".join(lines[count:position] + lines[position + 1:-1])
    expected = hashlib.new(checksum["algorithm"], encoded).hexdigest().encode("ascii")
    if special[prefix_length:] != expected:
        raise ValueError("Backup encrypted payload checksum mismatch")
    encrypted = decode_router_payload(encoded, model_specs)
    if encode_router_payload(encrypted, model_specs) != encoded:
        raise ValueError("Invalid encoded payload line layout")
    return {"header": b"".join(lines[:count]), "encoded": encoded,
            "encrypted": encrypted, "checksum": expected}


def rebuild_line_wrapper(encoded: bytes, header: bytes, specs: dict) -> bytes:
    """Insert a fresh checksum and random prefix into the configured layout."""
    fmt = specs["backup_format"]
    checksum = fmt["checksum"]
    lines = encoded.splitlines(keepends=True)
    position = checksum["after_payload_lines"]
    if len(lines) < position:
        raise ValueError("Payload too short for configured checksum location")
    if len(header.splitlines(keepends=True)) != fmt["header_lines"]:
        raise ValueError("Original header does not match configured layout")
    prefix = base64.b64encode(os.urandom(checksum["prefix"]["random_bytes"]))
    special = prefix + hashlib.new(checksum["algorithm"], encoded).hexdigest().encode("ascii") + b"\n"
    result = header + b"".join(lines[:position]) + special + b"".join(lines[position:]) + wrapper_trailer(fmt)
    parse_router_wrapper(result, specs)
    return result


def parse_technicolor_wrapper(data: bytes, model_specs: dict) -> dict:
    """Split THENC header, IV, ciphertext and signature; do not authenticate."""
    fmt = model_specs["backup_format"]
    header, separator, payload = data.partition(fmt["header_terminator"].encode("ascii"))
    lines = header.split(b"\n")
    names = ("PREAMBLE", "BACKUPVERSION", "BOARDMNEMONIC", "PRODUCTNAME",
             "SERIALNUMBER", "MAC", "BUILDVERSION", "CIPHERKEY", "SIGNATUREKEY")
    if not separator or len(lines) != fmt["header_lines"] or len(lines) != len(names):
        raise ValueError("Invalid or truncated THENC header")
    values = {}
    for name, line in zip(names, lines):
        key, equal, value = line.partition(b"=")
        if key != name.encode("ascii") or not equal or not value or any(c < 32 or c > 126 for c in value):
            raise ValueError(f"Invalid THENC header field: {name}")
        values[name] = value.decode("ascii")
    expected = {"PREAMBLE": fmt["preamble"], "BACKUPVERSION": fmt["backup_version"],
                "BOARDMNEMONIC": model_specs["hardware"]}
    if any(values[k] != v for k, v in expected.items()):
        raise ValueError("THENC header does not match configured values")
    if not (values["BUILDVERSION"] == model_specs["firmware"] or
            values["BUILDVERSION"].startswith(model_specs["firmware"] + "-")):
        raise ValueError("THENC firmware does not match configured value")
    iv_length, signature_length = fmt["iv_length"], fmt["signature_length"]
    size = len(payload) - iv_length - signature_length
    if size <= 0 or size % 16:
        raise ValueError("Invalid or truncated THENC IV, ciphertext or signature boundaries")
    return {"header": header + separator, "encoded": payload, "encrypted": payload[iv_length:-signature_length],
            "checksum": b"", "iv": payload[:iv_length], "signature": payload[-signature_length:],
            "cipher_key_id": values["CIPHERKEY"], "signature_key_id": values["SIGNATUREKEY"]}


def rebuild_technicolor_wrapper(encoded: bytes, header: bytes, specs: dict) -> bytes:
    """Never generate an unauthenticated device-key backup."""
    raise ValueError("THENC rebuilding unavailable: device key and signature signing are not established")

# ---------------------------------------------------------------------
# ARCHIVE OPERATIONS
# ---------------------------------------------------------------------

def safe_relative(name: str) -> Path:
    """Reject absolute paths and traversal."""
    path = Path(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe relative path: {name}")
    return path


def read_tar_files(data: bytes, specs: dict) -> dict:
    """Read validated TAR members without extracting paths."""
    with tarfile.open(fileobj=io.BytesIO(data), mode=tar_gzip_mode(specs, "r")) as archive:
        return {str(Path(member.name)): archive.extractfile(member).read()
                for member in validate_archive(archive) if member.isfile()}


def tar_gzip_mode(specs: dict, operation: str) -> str:
    """Select supported archive and compression mechanisms."""
    if specs["archive"].get("format") != "tar" or specs["archive"].get("compression") != "gzip":
        raise ValueError("Unsupported archive format or compression")
    return operation + ":gz"


def replace_router_directory(staged: Path, destination: Path) -> None:
    """Install a prepared directory, restoring the old one if installation fails."""
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError(f"Unsafe destination symlink: {destination}")
    if not destination.exists():
        os.replace(staged, destination)
        return
    if not destination.is_dir():
        raise NotADirectoryError(f"Expected output directory: {destination}")
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=f".{destination.name}.backup.") as backup_dir:
        backup = Path(backup_dir) / "original"
        os.replace(destination, backup)
        try:
            os.replace(staged, destination)
        except BaseException:
            os.replace(backup, destination)
            raise


def extract_tar_archive(archive_path: Path, output: Path, model_specs: dict) -> None:
    """Extract validated TAR files using staged directory replacement."""
    with tarfile.open(archive_path, mode=tar_gzip_mode(model_specs, "r")) as archive:
        members = validate_archive(archive)
        if not members:
            raise ValueError("Decoded archive is empty")
        for member in members:
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsafe archive member: {member.name}")
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        staged = Path(tempfile.mkdtemp(dir=output.parent, prefix=f".{output.name}."))
        try:
            for member in members:
                destination = staged / member.name
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError(f"Cannot extract: {member.name}")
                    with stream, destination.open("xb") as target:
                        shutil.copyfileobj(stream, target)
                    destination.chmod(0o600)
            replace_router_directory(staged, output)
        finally:
            if staged.exists():
                shutil.rmtree(staged)


def rebuild_tar_archive(original_archive: bytes, edited_dir: str, model_specs: dict) -> tuple[bytes, list[str]]:
    """Rebuild the original tar.gz archive using edited files."""
    directory = Path(edited_dir).expanduser()
    if not directory.is_dir():
        raise NotADirectoryError(f"Edited configuration directory not found: {directory}")
    validate_directory(directory)
    changes = []
    with tarfile.open(fileobj=io.BytesIO(original_archive), mode=tar_gzip_mode(model_specs, "r")) as source:
        members = validate_archive(source)
        expected = {str(Path(m.name)) for m in members if m.isfile()}
        actual = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
        if actual != expected:
            raise ValueError("Edited files do not match the original archive")
        contents = []
        for member in members:
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsafe archive member: {member.name}")
            if not member.isfile():
                contents.append(None)
                continue
            stream = source.extractfile(member)
            if stream is None:
                raise ValueError(f"Unreadable archive member: {member.name}")
            with stream:
                original_content = stream.read()
            edited_file = directory / relative
            if not edited_file.is_file() or edited_file.is_symlink():
                raise ValueError(f"Missing or unsafe edited file: {edited_file}")
            edited_content = edited_file.read_bytes()
            if edited_content != original_content:
                changes.append(member.name)
            contents.append(edited_content)
        if not changes:
            return original_archive, changes
        buffer = io.BytesIO()
        archive_format = tarfile.PAX_FORMAT if any(member.pax_headers for member in members) else tarfile.GNU_FORMAT
        with tarfile.open(fileobj=buffer, mode=tar_gzip_mode(model_specs, "w"), format=archive_format) as target:
            for member, content in zip(members, contents):
                entry = copy.deepcopy(member)
                entry.pax_headers.pop("size", None)
                if entry.isfile():
                    entry.size = len(content)
                    target.addfile(entry, io.BytesIO(content))
                else:
                    target.addfile(entry)
    return buffer.getvalue(), changes

# ---------------------------------------------------------------------
# CONFIGURATION FIELDS
# ---------------------------------------------------------------------

def parse_key_value_fields(contents: str, specs: dict) -> tuple[list, dict]:
    """Parse key-value lines and require unique configured keys."""
    if specs["configuration_format"] != "key-value":
        raise ValueError(f'Unsupported configuration_format: {specs["configuration_format"]}')
    lines = contents.splitlines(keepends=True)
    indices = {}
    for index, line in enumerate(lines):
        if "=" in line and not line.lstrip().startswith(("#", ";")):
            key = line.split("=", 1)[0].strip()
            if key in indices:
                raise ValueError(f"Duplicate configuration key: {key}")
            indices[key] = index
    fields = {}
    for label, key in specs["config_fields"].items():
        if label == "file" or key is None:
            continue
        if key not in indices:
            raise ValueError(f"Missing configuration field: {label} ({key})")
        fields[label] = (key, indices[key])
    return lines, fields


def validate_edited_fields(original_archive: bytes, directory: Path, specs: dict) -> None:
    """Match every original byte except values explicitly declared editable."""
    config_path = safe_relative(specs["config_fields"]["file"])
    found = False
    files = read_tar_files(original_archive, specs)
    for name, original in files.items():
        edited = (directory / safe_relative(name)).read_bytes()
        if Path(name) != config_path:
            if original != edited:
                raise ValueError(f"Original mismatch in uneditable file: {name}")
            continue
        found = True
        if normalize_key_value_fields(original.decode("utf-8"), specs) != normalize_key_value_fields(edited.decode("utf-8"), specs):
            raise ValueError("Edited configuration differs outside declared editable values")
    if not found:
        raise ValueError("Configured file missing from original archive")


def key_value_values(lines: list, fields: dict) -> dict:
    """Read displayed values from key-value lines."""
    return {key: lines[index].split("=", 1)[1].rstrip("\r\n") for key, index in fields.values()}


def update_key_value_fields(lines: list, fields: dict, details: dict) -> list:
    """Replace declared values while preserving whitespace and line endings."""
    for label, value in details.items():
        if label not in fields:
            raise ValueError(f"Unknown router setting: {label}")
        index = fields[label][1]
        line = lines[index]
        prefix, current = line.split("=", 1)
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        current = current[:-len(newline)] if newline else current
        leading = current[:len(current) - len(current.lstrip())]
        trailing = current[len(current.rstrip()):] if current.strip() else ""
        lines[index] = f"{prefix}={leading}{value}{trailing}{newline}"
    return lines


def normalize_key_value_fields(contents: str, specs: dict) -> list:
    """Mask editable values for comparison while retaining all other text."""
    lines, fields = parse_key_value_fields(contents, specs)
    for _, index in fields.values():
        line = lines[index]
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        lines[index] = line.split("=", 1)[0] + "=" + newline
    return lines

# ---------------------------------------------------------------------
# DISPATCHER FUNCTIONS
# ---------------------------------------------------------------------

def read_router_credential(password_path: str, specs: dict) -> str | bytes:
    """Read the selected credential type without treating passwords as device keys."""
    if specs["key_derivation"] == "openssl-legacy":
        if not specs["password_required"]:
            return ""
        if not password_path:
            raise ValueError("Router password file is required by the selected specification")
        return interpret_password_credentials(Path(password_path).expanduser().read_bytes())
    elif specs["key_derivation"] == "device-key":
        return load_device_key_credentials(password_path, specs)
    raise ValueError(f'Unsupported key_derivation: {specs["key_derivation"]}')


def decrypt_router_payload(data: bytes, password: str, model_specs: dict, wrapper: dict | None = None, device_key: bytes | None = None, device_key_path: str | None = None) -> bytes:
    """Decrypt using the encryption method defined in the router specification."""
    validate_model_specs(model_specs)
    mechanism = (model_specs["encryption"], model_specs["key_derivation"])
    if mechanism not in ENCRYPTION_HANDLERS:
        raise ValueError(f"Unsupported encryption mechanism: {mechanism}")
    if model_specs["key_derivation"] == "device-key" and device_key is None:
        if not device_key_path:
            raise ValueError("THENC device key unavailable: device_key_path is required; an export password is not a device key")
        device_key = Path(device_key_path).expanduser().read_bytes()
        if not device_key:
            raise ValueError("THENC device key file is empty")
    return ENCRYPTION_HANDLERS[mechanism](data, password, model_specs, True, wrapper=wrapper, device_key=device_key)


def encrypt_router_payload(data: bytes, password: str, model_specs: dict, device_key_path: str | None = None) -> bytes:
    """Encrypt using the encryption method defined in the router specification."""
    validate_model_specs(model_specs)
    mechanism = (model_specs["encryption"], model_specs["key_derivation"])
    if mechanism not in ENCRYPTION_HANDLERS:
        raise ValueError(f"Unsupported encryption mechanism: {mechanism}")
    if model_specs["key_derivation"] == "device-key":
        if not device_key_path:
            raise ValueError("THENC device key unavailable: device_key_path is required; an export password is not a device key")
        device_key = Path(device_key_path).expanduser().read_bytes()
        if not device_key:
            raise ValueError("THENC device key file is empty")
        return ENCRYPTION_HANDLERS[mechanism](data, password, model_specs, False, device_key=device_key)
    return ENCRYPTION_HANDLERS[mechanism](data, password, model_specs, False)


def encode_router_payload(data: bytes, specs: dict) -> bytes:
    """Encode using the configured transport format."""
    if specs["encoding"] == "base64":
        return encode_base64_payload(data, specs)
    if specs["encoding"] == "binary":
        return data
    raise ValueError(f'Unsupported encoding: {specs["encoding"]}')


def decode_router_payload(data: bytes, specs: dict) -> bytes:
    """Decode using the configured transport format."""
    if specs["encoding"] == "base64":
        return decode_base64_payload(data, specs)
    if specs["encoding"] == "binary":
        return data
    raise ValueError(f'Unsupported encoding: {specs["encoding"]}')


def parse_router_wrapper(data: bytes, model_specs: dict) -> dict:
    """Validate specifications and parse the configured backup wrapper."""
    validate_model_specs(model_specs)
    if model_specs["backup_format"]["type"] == "line-wrapper":
        return parse_line_wrapper(data, model_specs)
    elif model_specs["backup_format"]["type"] == "technicolor-thenc":
        return parse_technicolor_wrapper(data, model_specs)
    raise ValueError(f'Unsupported backup_format.type: {model_specs["backup_format"]["type"]}')


def rebuild_router_wrapper(encoded: bytes, header: bytes, specs: dict) -> bytes:
    """Validate specifications and rebuild the configured backup wrapper."""
    validate_model_specs(specs)
    if specs["backup_format"]["type"] == "line-wrapper":
        return rebuild_line_wrapper(encoded, header, specs)
    elif specs["backup_format"]["type"] == "technicolor-thenc":
        return rebuild_technicolor_wrapper(encoded, header, specs)
    raise ValueError(f'Unsupported backup_format.type: {specs["backup_format"]["type"]}')

# ---------------------------------------------------------------------
# ROUTER WORKFLOWS
# ---------------------------------------------------------------------

def load_router_model_specs(specs_path: str) -> dict | bool:
    """Load and validate router model specifications from a JSON file."""
    try:
        path = Path(specs_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Router model specifications not found: {path}")
        if path.suffix.lower() != MODEL_SPECS_EXTENSION:
            raise ValueError(f"Router model specifications must be a {MODEL_SPECS_EXTENSION} file")
        with path.open("r", encoding="utf-8") as file:
            specs = json.load(file)
        validate_model_specs(specs)
        print(f"Loaded router model specifications: {specs['model']}")
        return specs
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Failed to load router model specifications: {exc}")
        return False


def decode_router_config(
    config_path: str,
    model_specs: dict,
    password_path: str,
    device_key_path: str | None = None
) -> bytes | bool:
    """Decode and validate an original backup using only declared mechanisms."""
    wrapper = parse_router_wrapper(
        Path(config_path).expanduser().read_bytes(),
        model_specs
    )
    password = "" if model_specs["key_derivation"] == "device-key" else read_router_credential(password_path, model_specs)
    decoded = decrypt_router_payload(
        wrapper["encrypted"],
        password,
        model_specs,
        wrapper=wrapper,
        device_key_path=device_key_path
    )
    validate_tar_gzip_config(decoded, model_specs)
    return decoded


def save_router_config(decoded_config: bytes, decoded_config_path: str, model_specs: dict) -> bool:
    """Validate and atomically save the declared archive format."""
    if not isinstance(decoded_config, bytes) or not decoded_config:
        print("No decoded router configuration available to save.")
        return False
    try:
        path = Path(decoded_config_path).expanduser()
        extension = DECODED_EXTENSION
        if not path.name.endswith(extension):
            raise ValueError(f"Decoded configuration path must end with {extension}")
        if path.is_symlink():
            raise ValueError(f"Unsafe decoded archive symlink: {path}")
        read_tar_files(decoded_config, model_specs)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            os.chmod(temp_path, 0o600)
            temp_file.write(decoded_config)
        try:
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)
        print(f"Saved decoded router configuration: {path}")
        return True
    except (OSError, ValueError, TypeError, tarfile.TarError, EOFError) as exc:
        print(f"Failed to save decoded router configuration: {exc}")
        return False


def extract_router_config(archive_path: str, output_dir: str, model_specs: dict) -> str | bool:
    """Safely extract the decoded router configuration."""
    try:
        archive_path = Path(archive_path).expanduser()
        output = Path(output_dir).expanduser()
        if not archive_path.is_file():
            raise FileNotFoundError(f"Decoded archive not found: {archive_path}")
        if output.is_symlink():
            raise ValueError(f"Unsafe extraction directory symlink: {output}")
        if output.resolve() in archive_path.resolve().parents:
            raise ValueError("Extraction directory must not contain the decoded archive")
        extract_tar_archive(archive_path, output, model_specs)
        print(f"Extracted router configuration: {output}")
        return str(output)
    except (OSError, ValueError, TypeError, tarfile.TarError) as exc:
        print(f"Failed to extract router configuration: {exc}")
        return False


def view_router_config_fields(config_dir: str, model_specs: dict) -> bool:
    """Display selected router configuration fields."""
    try:
        config_fields = model_specs["config_fields"]
        directory = Path(config_dir).expanduser()
        validate_directory(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Configuration directory not found: {directory}")
        config_file = config_fields[CONFIG_FIELDS_FILE_KEY]
        relative = Path(config_file)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid configuration file path")
        path = directory / relative
        if not path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        contents = path.read_bytes().decode("utf-8")
        lines, fields = parse_key_value_fields(contents, model_specs)
        values = key_value_values(lines, fields)
        rows = []
        for label, key in config_fields.items():
            if label != CONFIG_FIELDS_FILE_KEY and key is not None:
                rows.append((label, values[key]))
        width = max([len("Field"), *(len(label) for label, _ in rows)])
        print(f"\nConfiguration: {directory.name} ({config_file})")
        print(f"{'Field':<{width}} | Value")
        print(f"{'-' * width}-+------------------------------")
        for label, value in rows:
            print(f"{label:<{width}} | {value}")
        return True
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Failed to view router configuration fields: {exc}")
        return False


def edit_router_config_fields(config_dir: str, edited_dir: str, model_specs: dict, router_details_path: str) -> str | bool:
    """Copy and edit selected router configuration fields."""
    try:
        config_fields = model_specs["config_fields"]
        source = Path(config_dir).expanduser()
        validate_directory(source)
        destination = Path(edited_dir).expanduser()
        if not source.is_dir():
            raise NotADirectoryError(f"Decoded configuration directory not found: {source}")
        if destination.is_symlink():
            raise ValueError(f"Unsafe edited configuration symlink: {destination}")
        if source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents or destination.resolve() in source.resolve().parents:
            raise ValueError("Edited directory must be outside the decoded directory")
        relative = Path(config_fields[CONFIG_FIELDS_FILE_KEY])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid configuration file path")
        source_file = source / relative
        if not source_file.is_file() or source_file.is_symlink():
            raise FileNotFoundError(f"Configuration file not found or unsafe: {source_file}")
        original = source_file.read_bytes().decode("utf-8")
        lines, fields = parse_key_value_fields(original, model_specs)
        details = load_router_details(router_details_path)
        lines = update_key_value_fields(lines, fields, details)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        staged = Path(tempfile.mkdtemp(dir=destination.parent, prefix=f".{destination.name}."))
        try:
            shutil.copytree(source, staged, dirs_exist_ok=True)
            target = staged / relative
            if target.is_symlink():
                raise ValueError(f"Unsafe configuration file: {target}")
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=target.parent, prefix=".config.", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.writelines(lines)
            try:
                os.chmod(temp_path, 0o600)
                os.replace(temp_path, target)
            finally:
                temp_path.unlink(missing_ok=True)
            replace_router_directory(staged, destination)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
        print(f"Saved edited router configuration: {destination}")
        return str(destination)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(f"Failed to edit router configuration: {exc}")
        return False


def encode_router_config(
    edited_dir: str,
    original_cfg: str,
    output_path: str,
    model_specs: dict,
    template_password_path: str,
    target_password_path: str,
    template_device_key_path: str | None = None,
    device_key_path: str | None = None
) -> str | bool:
    """Rebuild, encrypt and verify an edited backup without changing its source."""
    try:
        validate_model_specs(model_specs)
        directory = Path(edited_dir).expanduser()
        original = Path(original_cfg).expanduser()
        output = Path(output_path).expanduser()
        if output.is_symlink():
            raise ValueError(f"Unsafe updated backup symlink: {output}")
        wrapper = parse_router_wrapper(
            original.read_bytes(),
            model_specs
        )
        # Read the template password separately from the target password
        template_password = "" if model_specs["key_derivation"] == "device-key" else read_router_credential(template_password_path, model_specs)
        original_archive = decrypt_router_payload(
            wrapper["encrypted"],
            template_password,
            model_specs,
            wrapper=wrapper,
            device_key_path=template_device_key_path
        )
        rebuilt_archive, changes = rebuild_tar_archive(
            original_archive,
            str(directory),
            model_specs
        )
        validate_edited_fields(
            original_archive,
            directory,
            model_specs
        )
        # Encrypt for target router using its factory password
        target_password = "" if model_specs["key_derivation"] == "device-key" else read_router_credential(target_password_path, model_specs)
        encrypted = encrypt_router_payload(
            rebuilt_archive,
            target_password,
            model_specs,
            device_key_path=device_key_path
        )
        rebuilt = rebuild_router_wrapper(
            encode_router_payload(encrypted, model_specs),
            wrapper["header"],
            model_specs
        )
        # Verify using target router password
        verified = parse_router_wrapper(rebuilt, model_specs)
        decrypted = decrypt_router_payload(
            verified["encrypted"],
            target_password,
            model_specs,
            wrapper=verified,
            device_key_path=device_key_path
        )
        if decrypted != rebuilt_archive:
            raise ValueError(
                "Generated backup failed decryption verification"
            )
        read_tar_files(decrypted, model_specs)
        output.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700
        )
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, prefix=f".{output.name}.", delete=False) as target:
            temp_path = Path(target.name)
            os.chmod(temp_path, 0o600)
            target.write(rebuilt)
        try:
            os.replace(temp_path, output)
        finally:
            temp_path.unlink(missing_ok=True)
        print(
            "Modified files: " +
            (", ".join(changes) or "none; original compressed archive retained")
        )
        print(
            f"Updated router backup: {output}; "
            "checksum and local round-trip verified."
        )
        return str(output)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        tarfile.TarError,
        EOFError,
        subprocess.SubprocessError
    ) as exc:
        print(f"Failed to encode router configuration: {exc}")
        return False

# ---------------------------------------------------------------------
# APPLICATION-SPECIFIC OPERATIONS
# ---------------------------------------------------------------------

def load_router_details(details_path: str) -> dict:
    """Load ordinary key-value settings, rejecting multiline values."""
    with Path(details_path).expanduser().open(encoding="utf-8") as source:
        details = json.load(source)
    if not isinstance(details, dict):
        raise ValueError("Router details must be a JSON object")
    for key, value in details.items():
        if not key or type(value) not in (str, int, float, bool):
            raise ValueError("Router details require named scalar settings")
        if any(c in str(value) for c in "\r\n\x00"):
            raise ValueError("Router detail contains invalid control characters")
    return details


def view_router_details(details_path: str) -> bool:
    """Display all router details, including credentials."""
    print(json.dumps(load_router_details(details_path), indent=4))
    return True


def view_readme(data: dict | None, readme_path: str) -> bool:
    """Display the supplied data and README documentation."""
    readme = Path(readme_path).expanduser().read_text(encoding="utf-8")
    if data is not None:
        print(json.dumps(data, indent=4))
    print(readme)
    return True


def validate_router_configuration(paths: dict, model_specs: dict) -> bool:
    """Validate configured inputs and distinct output locations."""
    validate_model_specs(model_specs)
    for key in ("model_specs_path", "model_specs_readme_path", "template_config_path",
                "router_details_path"):
        if not Path(paths[key]).expanduser().is_file():
            raise FileNotFoundError(f"Required router input not found: {paths[key]}")
    if model_specs["key_derivation"] == "device-key":
        for key in ("template_device_key_path", "target_device_key_path"):
            if not paths.get(key):
                raise ValueError(f"THENC device key unavailable: {key} is required")
            path = Path(paths[key]).expanduser()
            if not path.is_file():
                raise FileNotFoundError(f"Device key file not found for {key}: {path}")
            if not path.stat().st_size:
                raise ValueError(f"Device key file is empty for {key}: {path}")
    else:
        for key in ("template_router_password_path", "target_router_password_path"):
            read_router_credential(paths.get(key), model_specs)
    details = load_router_details(paths["router_details_path"])
    for key in details:
        if key == "file" or key not in model_specs["config_fields"] or model_specs["config_fields"][key] is None:
            raise ValueError(f"Unknown router setting: {key}")
    outputs = [Path(paths[key]).expanduser() for key in (
        "decoded_config_archive_path", "decoded_config_path", "edited_config_path", "encoded_config_path")]
    for index, output in enumerate(outputs):
        if output.is_symlink():
            raise ValueError(f"Unsafe router output symlink: {output}")
        output = output.resolve()
        for other in outputs[index + 1:]:
            other = other.resolve()
            if output == other or output in other.parents or other in output.parents:
                raise ValueError("Router outputs must be distinct and must not contain each other")
    parse_router_wrapper(Path(paths["template_config_path"]).expanduser().read_bytes(), model_specs)
    print("Router configuration validated.")
    return True
