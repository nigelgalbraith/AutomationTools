
# ---------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
from functools import partial
import json
import os
import shutil
import subprocess
import tarfile
import tempfile


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------


def validate_configuration_changes(original: str, edited: str, specs: dict,
                                   viewer, editor, decrypt_handler=None, encrypt_handler=None) -> dict:
    """Permit only declared replacements using the selected format's own editor."""
    before = viewer(original, specs, decrypt_handler)
    after = viewer(edited, specs, decrypt_handler)
    if before.keys() != after.keys():
        raise ValueError("Edited configuration fields do not match the original")
    changes = {name: value for name, value in after.items() if value != before[name]}
    if editor(original, specs, changes, encrypt_handler) != edited:
        raise ValueError("Edited configuration differs outside declared editable values")
    return changes


def safe_relative(name: str) -> Path:
    """Reject absolute paths and traversal."""
    path = Path(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe relative path: {name}")
    return path


def validate_directory(directory: Path) -> None:
    """Reject symlinks and special files, including symlink ancestors."""
    if any(path.is_symlink() for path in (directory, *directory.parents)):
        raise ValueError("Unsafe directory symlink")
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"Unsafe configuration entry: {path}")


def replace_router_directory(staged: Path, destination: Path) -> None:
    """Install a prepared directory, restoring the old one if installation fails."""
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError(f"Unsafe destination symlink: {destination}")
    if not destination.exists():
        os.replace(staged, destination)
        return
    if not destination.is_dir():
        raise NotADirectoryError(f"Expected output directory: {destination}")
    backup_dir = Path(tempfile.mkdtemp(dir=destination.parent, prefix=f".{destination.name}.backup."))
    backup = backup_dir / "original"
    installed = False
    try:
        os.replace(destination, backup)
        try:
            os.replace(staged, destination)
            installed = True
        except BaseException:
            os.replace(backup, destination)
            raise
    finally:
        if installed or not backup.exists():
            shutil.rmtree(backup_dir)
        else:
            print(f"Original configuration retained at: {backup}")


def lookup_values(mapping: dict, keys) -> dict:
    """Return the values associated with the supplied dictionary keys."""
    return {key: mapping[key] for key in keys}


def _handler(functions: dict, name: str | None):
    """Resolve a configured algorithm; skip null values, reject unknown ones."""
    if name is None:
        return None
    handler = functions.get(name)
    if not callable(handler):
        raise ValueError(f"Unsupported router algorithm: {name}")
    return handler


def _field_specs(edit: dict, config_fields: list) -> dict:
    """Supply the existing field utilities with their required configuration shape."""
    return {"router_specs": {"edit": edit}, "config_fields": config_fields}


def field_handler(edit: dict, functions: dict):
    """Bind the configured field cipher to its key and IV."""
    settings = (edit.get("field_encryption") or {})
    handler = _handler(functions, settings.get("algorithm"))
    if handler is None:
        return None
    return partial(handler, **{key: value for key, value in settings.items()
                               if key not in ("algorithm", "fields")})


def _validate_router_codec(router: dict, codec: dict, edit: dict, registry: dict, *, context=None) -> None:
    """Validate selected implementations through their existing invocation contract."""
    context = {} if context is None else dict(context)
    context.update(codec=codec, edit=edit, hardware=router.get("hardware"),
                   firmware=router.get("firmware"), signing=router.get("encode"),
                   checksum_functions=registry["checksum"])
    methods = {codec.get("encoding"), codec.get("wrapper"), codec.get("archive"),
               (codec.get("key_derivation") or codec.get("encryption")) if codec.get("encryption") else None,
               (codec.get("signature") or {}).get("algorithm")} - {None}
    if codec.get("key_derivation") and not codec.get("encryption"):
        raise ValueError("key_derivation requires encryption")
    for action in ("decode", "encode"):
        for method in methods:
            _handler(registry[action]["functions"], method)
        for method in registry[action]["functions"]:
            if method in methods:
                validator = registry[action]["validate"].get(method)
                if validator is not None:
                    validator(context=context)
    _handler(registry["checksum"], codec.get("checksum"))
    specs = _field_specs(edit, context.get("config_fields", []))
    for action in ("view", "edit"):
        method = edit.get("configuration_format")
        if _handler(registry[action]["functions"], method) is not None:
            validator = registry[action]["validate"].get(method)
            if validator is not None:
                validator(specs)
    settings = edit.get("field_encryption") or {}
    for action in ("decode", "encode"):
        method = settings.get("algorithm")
        if _handler(registry[action]["functions"], method) is not None:
            validator = _handler(registry[action]["validate"], method)
            validator(**{key: value for key, value in settings.items()
                         if key not in ("algorithm", "fields")})


def _validate_router_fields(router: dict, config_fields: list, codec: dict, edit: dict) -> None:
    """Validate logical mappings and protected-field references, independent of format."""
    names = [field["name"] for field in config_fields]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate logical configuration field names")
    paths = [field["path"] for field in config_fields if field["path"] is not None]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate configuration field mappings")
    if paths and not edit.get("configuration_format"):
        raise ValueError("Configuration field mappings require an edit section")
    if edit.get("configuration_format"):
        safe_relative(edit["configuration_file"])
    protected = edit.get("field_encryption") or {}
    if protected.get("algorithm") is not None and (not isinstance(protected.get("fields"), list) or not protected["fields"]):
        raise ValueError("Field encryption requires a nonempty declared fields list")
    mapped = {field["name"] for field in config_fields if field["path"] is not None}
    if any(name not in mapped for name in protected.get("fields") or []):
        raise ValueError("Encrypted field has no configuration mapping")


def _validate_router_inputs(paths: dict, model_specs: dict) -> None:
    """Check declared inputs and any supplied credential files."""
    for key in ("model_specs_path", "model_specs_readme_path", "template_config_path", "router_details_path"):
        if not Path(paths[key]).expanduser().is_file():
            raise FileNotFoundError(f"Required router input not found: {paths[key]}")
    codec = model_specs["router_specs"]["codec"]
    for key in ("template_device_key_path", "target_device_key_path"):
        if codec.get("device_key_required") and not paths.get(key):
            raise ValueError(f"Required device key path missing: {key}")
        if paths.get(key):
            path = Path(paths[key]).expanduser()
            if not path.is_file() or not path.stat().st_size:
                raise ValueError(f"Device key file missing or empty for {key}: {path}")
    for key in ("template_router_password_path", "target_router_password_path"):
        read_router_credential(paths.get(key), model_specs["router_specs"]["codec"])


def _save_configuration_directory(source: Path, destination: Path, relative: Path, original_bytes: bytes, edited: str, edit: dict, config_fields: list, details: dict, decrypt_handler=None, encrypt_handler=None, *, viewer, editor) -> None:
    """Stage, verify and atomically replace an edited configuration directory."""
    specs = _field_specs(edit, config_fields)
    original = original_bytes.decode("utf-8")
    source_file = source / relative
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staged = Path(tempfile.mkdtemp(dir=destination.parent, prefix=f".{destination.name}."))
    try:
        shutil.copytree(source, staged, dirs_exist_ok=True)
        target = staged / relative
        if target.is_symlink():
            raise ValueError(f"Unsafe configuration file: {target}")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=target.parent, prefix=".config.", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(edited)
        try:
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, target)

        finally:
            temp_path.unlink(missing_ok=True)
        validate_configuration_changes(original, target.read_bytes().decode("utf-8"), specs, viewer, editor, decrypt_handler, encrypt_handler)
        if source_file.read_bytes() != original_bytes:
            raise ValueError("Original decoded configuration changed during editing")
        validate_directory(staged)
        replace_router_directory(staged, destination)
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def read_router_credential(password_path: str, specs: dict) -> str | bytes:
    """Read an optional text credential; device keys use their separate input."""
    if not password_path:
        if specs.get("password_required"):
            raise ValueError("Router password file is required by the selected specification")
        return ""
    try:
        password = Path(password_path).expanduser().read_bytes().decode("utf-8").strip()
    except UnicodeError:
        raise ValueError("Password file must contain UTF-8 text") from None
    if not password or any(char in password for char in "\r\n\x00"):
        raise ValueError("Password file is empty or contains invalid control characters")
    return password


def extract_configuration_file(data: bytes, output: Path, configuration_file: str | None = None, *, context=None) -> None:
    """Stage one decoded configuration file, preserving its bytes and permissions."""
    if context is not None:
        configuration_file = context["edit"]["configuration_file"]
    relative = safe_relative(configuration_file)
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=f".{output.name}.") as directory:
        prepared = Path(directory) / "configuration"
        target = prepared / relative
        target.parent.mkdir(parents=True, mode=0o700)
        target.write_bytes(data)
        target.chmod(0o600)
        replace_router_directory(prepared, output)


def parse_router_wrapper(data: bytes, codec: dict, hardware: str | None, firmware: str | None, decode_functions: dict, checksum_functions: dict) -> dict:
    """Validate a registered wrapper and retain its declared metadata."""
    context = {"codec": codec, "hardware": hardware, "firmware": firmware,
               "checksum_functions": checksum_functions, "header": b""}
    method = codec.get("wrapper")
    payload = data if method is None else _handler(decode_functions, method)(data, context=context)
    return dict(context, encoded=payload, encrypted=payload)


def validate_router_settings(specs: dict, registry: dict) -> None:
    """Validate configured algorithms, formats and logical field mappings."""
    router = specs["router_specs"]
    codec = router["codec"]
    edit = router.get("edit") or {}
    _validate_router_codec(router, codec, edit, registry, context={"config_fields": specs["config_fields"]})
    _validate_router_fields(router, specs["config_fields"], codec, edit)


def _save_encoded_backup(output: Path, rebuilt: bytes, rebuilt_archive: bytes, single_file: bool, codec: dict, hardware: str | None, firmware: str | None, target_password_path: str | None, device_key_path: str | None, decode_functions: dict, decode_validators: dict, checksum_functions: dict) -> None:
    """Verify a temporary backup and atomically publish the output."""
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, prefix=f".{output.name}.", delete=False) as target:
            temp_path = Path(target.name)
            os.chmod(temp_path, 0o600)
            target.write(rebuilt)
        if temp_path.read_bytes() != rebuilt:
            raise ValueError("Generated output failed write verification")
        recovered = decode_router_config(
            str(temp_path), codec, hardware, firmware, target_password_path,
            device_key_path, decode_functions, decode_validators, checksum_functions)
        if recovered != rebuilt_archive:
            raise ValueError("Generated backup failed independent decode verification")
        os.replace(temp_path, output)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------
# ROUTER DETAILS AND HELP
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


# ---------------------------------------------------------------------
# ROUTER VALIDATION
# ---------------------------------------------------------------------


def validate_router_configuration(paths: dict, model_specs: dict, registry: dict) -> bool:
    """Validate configured inputs and distinct output locations for full automation."""
    router = model_specs["router_specs"]
    codec = router["codec"]
    edit = router.get("edit") or {}
    if edit.get("configuration_format") is not None and edit["configuration_format"] not in registry["edit"]["functions"]:
        raise ValueError("Configuration editing is unsupported for this format")
    _validate_router_inputs(paths, model_specs)
    _validate_router_codec(router, codec, edit, registry, context={
        "check_inputs": True, "config_fields": model_specs["config_fields"],
        "password": read_router_credential(paths.get("target_router_password_path"), codec),
        "device_key": Path(paths["target_device_key_path"]).expanduser().read_bytes() if paths.get("target_device_key_path") else None,
    })
    details = load_router_details(paths["router_details_path"])
    mapped = {field["name"] for field in model_specs["config_fields"] if field["path"] is not None}
    for key in details:
        if key not in mapped:
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
    parse_router_wrapper(Path(paths["template_config_path"]).expanduser().read_bytes(),
        codec, router.get("hardware"), router.get("firmware"), registry["decode"]["functions"], registry["checksum"])
    print("Router configuration validated.")
    return True


# ---------------------------------------------------------------------
# ROUTER DECODING
# ---------------------------------------------------------------------


def decode_router_config(config_path: str | bytes, codec: dict, hardware: str | None, firmware: str | None, password_path: str | None, device_key_path: str | None, decode_functions: dict, decode_validators: dict, checksum_functions: dict, *, password: str | None = None, context: dict | None = None) -> bytes:
    """Execute selected byte transformations in registry insertion order."""
    data = config_path if isinstance(config_path, bytes) else Path(config_path).expanduser().read_bytes()
    context = {} if context is None else context
    for key in ("files", "configuration_payload", "signature"):
        context.pop(key, None)
    context.update(codec=codec, hardware=hardware, firmware=firmware,
                   checksum_functions=checksum_functions,
                   password=read_router_credential(password_path, codec) if password is None else password,
                   device_key=Path(device_key_path).expanduser().read_bytes() if device_key_path else None)
    selected = {codec.get("encoding"), codec.get("wrapper"), codec.get("archive"),
                (codec.get("key_derivation") or codec.get("encryption")) if codec.get("encryption") else None,
                (codec.get("signature") or {}).get("algorithm")} - {None}
    for method in selected:
        _handler(decode_functions, method)
    for name, validator in decode_validators.items():
        if name in selected:
            validator(context={**context, "check_inputs": True})
    for name, function in decode_functions.items():
        if name in selected:
            data = function(data, context=context)
            if not isinstance(data, bytes) or not data:
                raise ValueError(f"Invalid decoded payload from {name}")
    return data


# ---------------------------------------------------------------------
# CONFIGURATION SAVING
# ---------------------------------------------------------------------


def save_router_config(decoded_config: bytes, decoded_config_path: str, model_specs: dict, decode_functions: dict, checksum_functions: dict) -> bool:
    """Save the decoded router configuration in its declared format."""
    if not isinstance(decoded_config, bytes) or not decoded_config:
        print("No decoded router configuration available to save.")
        return False
    try:
        path = Path(decoded_config_path).expanduser()
        extension = model_specs["router_specs"]["codec"]["decoded_extension"]
        if not path.name.endswith(extension):
            raise ValueError(f"Decoded configuration path must end with {extension}")
        if path.is_symlink():
            raise ValueError(f"Unsafe decoded archive symlink: {path}")
        router = model_specs["router_specs"]
        context = {"codec": router["codec"], "edit": router.get("edit"),
                   "checksum_functions": checksum_functions}
        method = router["codec"].get("archive")
        if method is not None:
            _handler(decode_functions, method)(decoded_config, context=context)
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
    except (OSError, ValueError, TypeError, KeyError, tarfile.TarError, EOFError) as exc:
        print(f"Failed to save decoded router configuration: {exc}")
        return False


# ---------------------------------------------------------------------
# CONFIGURATION EXTRACTION
# ---------------------------------------------------------------------


def extract_router_config(archive_path: str, output_dir: str, model_specs: dict, decode_functions: dict, checksum_functions: dict) -> str | bool:
    """Safely extract the decoded router configuration."""
    try:
        archive_path = Path(archive_path).expanduser()
        output = Path(output_dir).expanduser()
        if not archive_path.is_file():

            raise FileNotFoundError(f"Decoded archive not found: {archive_path}")
        if any(path.is_symlink() for path in (output, *output.parents)):
            raise ValueError(f"Unsafe extraction directory symlink: {output}")
        if output.exists():
            if not output.is_dir():
                raise ValueError(f"Extraction destination is not a directory: {output}")
        if output.resolve() in archive_path.resolve().parents:
            raise ValueError("Extraction directory must not contain the decoded archive")
        router = model_specs["router_specs"]
        context = {"codec": router["codec"], "edit": router.get("edit"),
                   "checksum_functions": checksum_functions}
        method = router["codec"].get("archive")
        if method is None:
            raise ValueError("Configuration extraction is not declared for this router")
        _handler(decode_functions, method)(archive_path.read_bytes(), output, context=context)
        if not output.is_dir():
            raise ValueError("Selected extractor did not create configuration files")
        validate_directory(output)
        if not (output / safe_relative(context["edit"]["configuration_file"])).is_file():
            raise ValueError("Configured file missing from extracted configuration")
        print(f"Extracted router configuration: {output}")
        return str(output)
    except (OSError, ValueError, TypeError, KeyError, tarfile.TarError) as exc:
        print(f"Failed to extract router configuration: {exc}")
        return False


# ---------------------------------------------------------------------
# CONFIGURATION VIEWING
# ---------------------------------------------------------------------


def view_router_config_fields(config_dir: str, edit: dict, config_fields: list, view_functions: dict, decode_functions: dict) -> bool:
    """Display selected router configuration fields using the supplied viewer."""
    try:
        configuration_format = edit.get("configuration_format")
        viewer = _handler(view_functions, configuration_format)
        if viewer is None:
            raise ValueError(f"Unsupported configuration_format for viewing: {configuration_format}")
        directory = Path(config_dir).expanduser()
        validate_directory(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Configuration directory not found: {directory}")
        config_file = edit["configuration_file"]
        path = directory / safe_relative(config_file)
        if not path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        values = viewer(path.read_bytes().decode("utf-8"), _field_specs(edit, config_fields), field_handler(edit, decode_functions))
        rows = [(field["name"], values[field["name"]]) for field in config_fields if field["path"] is not None]
        width = max([len("Field"), *(len(label) for label, _ in rows)])
        print(f"\nConfiguration: {directory.name} ({config_file})")
        print(f"{'Field':<{width}} | Value")
        print(f"{'-' * width}-+------------------------------")
        for label, value in rows:
            print(f"{label:<{width}} | {value}")
        return True
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(f"Failed to view router configuration fields: {exc}")
        return False


# ---------------------------------------------------------------------
# CONFIGURATION EDITING
# ---------------------------------------------------------------------


def edit_router_config_fields(config_dir: str, edited_dir: str, edit: dict, config_fields: list, router_details_path: str, edit_functions: dict, view_functions: dict, decode_functions: dict, encode_functions: dict) -> str | bool:
    """Copy and edit declared fields using the supplied format handlers."""
    try:
        configuration_format = edit.get("configuration_format")
        editor = _handler(edit_functions, configuration_format)
        viewer = _handler(view_functions, configuration_format)
        if editor is None or viewer is None:
            raise ValueError(f"Unsupported configuration_format for editing: {configuration_format}")
        decrypt_handler = field_handler(edit, decode_functions)
        encrypt_handler = field_handler(edit, encode_functions)
        specs = _field_specs(edit, config_fields)
        source = Path(config_dir).expanduser()
        validate_directory(source)
        destination = Path(edited_dir).expanduser()
        if not source.is_dir():
            raise NotADirectoryError(f"Decoded configuration directory not found: {source}")
        if any(path.is_symlink() for path in (destination, *destination.parents)):
            raise ValueError(f"Unsafe edited configuration symlink: {destination}")
        if source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents or destination.resolve() in source.resolve().parents:
            raise ValueError("Edited directory must be outside the decoded directory")
        relative = safe_relative(edit["configuration_file"])
        source_file = source / relative
        if not source_file.is_file() or source_file.is_symlink():
            raise FileNotFoundError(f"Configuration file not found or unsafe: {source_file}")
        original_bytes = source_file.read_bytes()
        original = original_bytes.decode("utf-8")
        values = viewer(original, specs, decrypt_handler)
        details = load_router_details(router_details_path)
        for label in details:
            if label not in values:
                raise ValueError(f"Unknown router setting: {label}")
        details = {label: str(value) for label, value in details.items() if str(value) != values[label]}
        print(f"\nEditing configuration: {source.name}")
        for label, current in values.items():
            print(f"{label}: {current}")
        if details:
            print("\nChanges:")
            for label, replacement in details.items():
                print(f"{label}: {values[label]} -> {replacement}")
        else:
            print("No changes made.")
        edited = editor(original, specs, details, encrypt_handler)
        validate_configuration_changes(original, edited, specs, viewer, editor, decrypt_handler, encrypt_handler)
        _save_configuration_directory(source, destination, relative, original_bytes, edited, edit, config_fields, details, decrypt_handler, encrypt_handler, viewer=viewer, editor=editor)
        print(f"Saved edited router configuration: {destination}")
        return str(destination)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(f"Failed to edit router configuration: {exc}")
        return False


# ---------------------------------------------------------------------
# ROUTER ENCODING
# ---------------------------------------------------------------------


def encode_router_config(
    edited_dir: str,
    original_cfg: str,
    output_path: str,
    codec: dict,
    hardware: str | None,
    firmware: str | None,
    signing: dict | None,
    edit: dict,
    config_fields: list,
    template_password_path: str | None,
    target_password_path: str | None,
    template_device_key_path: str | None,
    device_key_path: str | None,
    encode_functions: dict,
    encode_validators: dict,
    decode_functions: dict,
    decode_validators: dict,
    checksum_functions: dict,
    view_functions: dict,
    edit_functions: dict,
) -> str | bool:
    """Rebuild, encrypt and round-trip verify an edited router backup."""
    try:
        directory = Path(edited_dir).expanduser()
        original = Path(original_cfg).expanduser()
        output = Path(output_path).expanduser()
        if any(path.is_symlink() for path in (output, *output.parents)):
            raise ValueError(f"Unsafe updated backup symlink: {output}")
        if output.resolve() == original.resolve() or (output.exists() and original.exists() and output.samefile(original)):
            raise ValueError("Output destination must not overwrite the original backup")
        if output.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Output destination must not overwrite the edited configuration directory")
        if not directory.is_dir():
            raise NotADirectoryError(f"Edited configuration directory not found: {directory}")
        context = {"edit": edit, "header": b""}
        original_archive = decode_router_config(
            original.read_bytes(), codec, hardware, firmware,
            template_password_path, template_device_key_path,
            decode_functions, decode_validators, checksum_functions, context=context)
        target_password = read_router_credential(target_password_path, codec)
        context.update(password=target_password, signing=signing,
                       device_key=Path(device_key_path).expanduser().read_bytes() if device_key_path else None,
                       edited_dir=str(directory), changes=[], expected=original_archive)
        validate_directory(directory)
        files = context.get("files")
        if files is None:
            raise ValueError("Selected decoder does not declare editable configuration files")
        actual = {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file()}
        if actual != set(files):
            raise ValueError("Edited files do not match the original configuration")
        configured = str(safe_relative(edit["configuration_file"]))
        if configured not in files:
            raise ValueError("Configured file missing from original backup")
        specs = _field_specs(edit, config_fields)
        viewer = _handler(view_functions, edit["configuration_format"])
        editor = _handler(edit_functions, edit["configuration_format"])
        for name, original_data in files.items():
            edited_data = (directory / safe_relative(name)).read_bytes()
            if name == configured:
                validate_configuration_changes(original_data.decode("utf-8"), edited_data.decode("utf-8"),
                    specs, viewer, editor, field_handler(edit, decode_functions), field_handler(edit, encode_functions))
            elif original_data != edited_data:
                raise ValueError(f"Original mismatch in uneditable file: {name}")
            if original_data != edited_data:
                context["changes"].append(name)
        # A decoder explicitly declares whether its payload is the configuration
        # file itself; archive rebuild operations instead update expected bytes.
        data = (directory / safe_relative(configured)).read_bytes() if context.get("configuration_payload") else original_archive
        context["expected"] = data
        selected = {codec.get("encoding"), codec.get("wrapper"), codec.get("archive"),
                    (codec.get("key_derivation") or codec.get("encryption")) if codec.get("encryption") else None,
                    (codec.get("signature") or {}).get("algorithm")} - {None}
        for method in selected:
            _handler(encode_functions, method)
        for name, validator in encode_validators.items():
            if name in selected:
                validator(context={**context, "check_inputs": True})
        for name, function in encode_functions.items():
            if name in selected:
                data = function(data, context=context)
                if not isinstance(data, bytes) or not data:
                    raise ValueError(f"Invalid encoded payload from {name}")
        rebuilt, rebuilt_archive, changes = data, context["expected"], context["changes"]
        decrypted = decode_router_config(
            rebuilt, codec, hardware, firmware, None, device_key_path,
            decode_functions, decode_validators, checksum_functions, password=target_password
        )
        if decrypted != rebuilt_archive:
            raise ValueError("Generated backup failed decryption verification")
        _save_encoded_backup(
            output, rebuilt, rebuilt_archive, bool(context.get("configuration_payload")),
            codec, hardware, firmware, target_password_path,
            device_key_path, decode_functions, decode_validators, checksum_functions
        )
        print(
            "Modified files: " +
            (", ".join(changes) or "none; original configuration retained")
        )
        print(f"Updated router backup: {output}; local round-trip verified.")
        return str(output)
    except (
        OSError, ValueError, KeyError, TypeError, UnicodeError,
        tarfile.TarError, EOFError, subprocess.SubprocessError
    ) as exc:
        print(f"Failed to encode router configuration: {exc}")
        return False
