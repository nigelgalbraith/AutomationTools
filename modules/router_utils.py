
# ---------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
from functools import partial
import json
import os
import shutil
import tarfile
import tempfile


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

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
    settings = edit.get("field_encryption") or {}
    name = settings.get("algorithm")
    if name is None:
        return None
    handler = functions.get(name)
    if not callable(handler):
        raise ValueError(f"Unsupported router algorithm: {name}")
    return partial(handler, **{key: value for key, value in settings.items()
                               if key not in ("algorithm", "fields")})


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


# ---------------------------------------------------------------------
# ROUTER SPECIFICATIONS AND OPERATION RESOLUTION
# ---------------------------------------------------------------------

def extract_router_settings(value):
    """Remove null values recursively from router specifications."""
    if isinstance(value, dict):
        return {key: extract_router_settings(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [extract_router_settings(item) for item in value if item is not None]
    return value


def resolve_router_operations(router_settings, registry, operation):
    """Select registered callables in registry execution order."""
    router = router_settings["router_specs"]
    codec = router.get("codec") or {}
    edit = router.get("edit") or {}
    if operation in ("edit", "view"):
        selected = {edit.get("configuration_format")}
    elif operation == "checksum":
        selected = {codec.get("checksum")}
    elif operation in ("extract", "check"):
        selected = {codec.get("archive")}
    else:
        selected = {
            codec.get("encoding"),
            codec.get("wrapper"),
            codec.get("archive"),
            (codec.get("key_derivation") or codec.get("encryption")) if codec.get("encryption") else None,
            (codec.get("signature") or {}).get("algorithm"),
            (edit.get("field_encryption") or {}).get("algorithm"),
        }
    selected.discard(None)
    return {name: function for name, function in registry.items() if name in selected}


# ---------------------------------------------------------------------
# OPERATION BUILDERS
# ---------------------------------------------------------------------

def build_encode_operations(router_settings, encode_operations, encode_validate_operations):
    """Return selected encode validators and algorithms in execution order."""
    codec = router_settings['router_specs'].get('codec') or {}
    if codec.get('key_derivation') and not codec.get('encryption'):
        raise ValueError('key_derivation requires encryption')
    roles = {name: codec.get(name) for name in ('archive', 'encryption', 'encoding', 'wrapper')}
    roles['encryption'] = (codec.get('key_derivation') or codec.get('encryption')) if codec.get('encryption') else None
    signature = (codec.get('signature') or {}).get('algorithm')
    required = (set(roles.values()) | {signature}) - {None}
    for name in required:
        _handler(encode_operations, name)
    names = [name for name in encode_operations if name in required]
    order = codec.get('encode_order')
    if order:
        active = {role for role, name in roles.items() if name is not None}
        if len(order) != len(set(order)) or not active.issubset(order) or not set(order).issubset(roles):
            raise ValueError('Invalid encode_order')
        names = [roles[role] for role in order if roles[role] is not None]
        if signature:
            names.insert(names.index(roles['archive']) if roles['archive'] in names else 0, signature)
        names = list(dict.fromkeys(names))
    return [function for name, function in encode_validate_operations.items() if name in required] + [encode_operations[name] for name in names]


def build_decode_operations(router_settings, decode_operations, decode_validate_operations):
    """Return selected decode validators and algorithms in execution order."""
    codec = router_settings['router_specs'].get('codec') or {}
    if codec.get('key_derivation') and not codec.get('encryption'):
        raise ValueError('key_derivation requires encryption')
    roles = {name: codec.get(name) for name in ('wrapper', 'encoding', 'encryption', 'archive')}
    roles['encryption'] = (codec.get('key_derivation') or codec.get('encryption')) if codec.get('encryption') else None
    signature = (codec.get('signature') or {}).get('algorithm')
    required = (set(roles.values()) | {signature}) - {None}
    for name in required:
        _handler(decode_operations, name)
    names = [name for name in decode_operations if name in required]
    order = codec.get('decode_order')
    if order:
        active = {role for role, name in roles.items() if name is not None}
        if len(order) != len(set(order)) or not active.issubset(order) or not set(order).issubset(roles):
            raise ValueError('Invalid decode_order')
        names = [roles[role] for role in order if roles[role] is not None]
        if signature:
            names.insert(names.index(roles['archive']) + 1 if roles['archive'] in names else len(names), signature)
        names = list(dict.fromkeys(names))
    return [function for name, function in decode_validate_operations.items() if name in required] + [decode_operations[name] for name in names]


def build_edit_operations(router_settings, edit_operations, edit_validate_operations):
    """Return the selected format validators followed by its editor."""
    method = (router_settings['router_specs'].get('edit') or {}).get('configuration_format')
    if method is None:
        return []
    editor = _handler(edit_operations, method)
    return [function for name, function in edit_validate_operations.items() if name == method] + [editor]


def build_view_operations(router_settings, view_operations, view_validate_operations):
    """Return the selected format validators followed by its reader."""
    method = (router_settings['router_specs'].get('edit') or {}).get('configuration_format')
    if method is None:
        return []
    viewer = _handler(view_operations, method)
    return [function for name, function in view_validate_operations.items() if name == method] + [viewer]


# ---------------------------------------------------------------------
# OPERATION EXECUTION AND DISPLAY
# ---------------------------------------------------------------------

def run_router_operations(data, operations, context):
    """Execute supplied operations in order, retaining data after validators."""
    for operation in operations:
        value = operation(data, context=context)
        if value is not None:
            if isinstance(data, bytes) and (not isinstance(value, bytes) or not value):
                raise ValueError(f'Invalid router payload from {operation.__name__}')
            data = value
    return data


def display_router_operations(operations, label):
    """Display a callable list through the existing router console formatter."""
    from modules.display_utils import print_router_dictionary
    return print_router_dictionary({str(index): function for index, function in enumerate(operations, 1)}, label)


# ---------------------------------------------------------------------
# ROUTER INPUT AND CREDENTIAL LOADING
# ---------------------------------------------------------------------

def read_router_input(path):
    """Read backup bytes together with their source path, including empty files."""
    source = Path(path).expanduser()
    return {"path": source, "data": source.read_bytes()}


def prepare_codec_context(codec, hardware, firmware, password_path, device_key_path, checksum_functions, edit=None):
    """Load credentials and construct metadata for selected codec operations."""
    password_required = bool(codec.get("password_required"))
    device_key_required = bool(codec.get("device_key_required"))
    if password_required and not password_path:
        raise ValueError("Required router password path is not configured")
    if device_key_required and not device_key_path:
        raise ValueError("Required router device key path is not configured")
    password = read_router_credential(password_path if password_required else None, codec)
    device_key = None
    if device_key_required:
        path = Path(device_key_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Required router device key is missing: {path}")
        device_key = path.read_bytes()
    return {
        "codec": codec,
        "hardware": hardware,
        "firmware": firmware,
        "password": password,
        "device_key": device_key,
        "checksum_functions": checksum_functions,
        "edit": edit or {},
        "header": b"",
        "check_inputs": True,
    }


# ---------------------------------------------------------------------
# ROUTER VALIDATION
# ---------------------------------------------------------------------

def validate_router_field_mappings(model_specs: dict) -> bool:
    """Validate logical field mappings and their protected-field references."""
    edit = model_specs["router_specs"].get("edit") or {}
    names = [field["name"] for field in model_specs["config_fields"]]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate logical configuration field names")
    field_paths = [field["path"] for field in model_specs["config_fields"] if field["path"] is not None]
    if len(field_paths) != len(set(field_paths)):
        raise ValueError("Duplicate configuration field mappings")
    if field_paths and not edit.get("configuration_format"):
        raise ValueError("Configuration field mappings require an edit section")
    if edit.get("configuration_format"):
        safe_relative(edit["configuration_file"])
    protected = edit.get("field_encryption") or {}
    if protected.get("algorithm") is not None and (not isinstance(protected.get("fields"), list) or not protected["fields"]):
        raise ValueError("Field encryption requires a nonempty declared fields list")
    mapped = {field["name"] for field in model_specs["config_fields"] if field["path"] is not None}
    if any(name not in mapped for name in protected.get("fields") or []):
        raise ValueError("Encrypted field has no configuration mapping")
    return True


def validate_router_details(details_path: str, config_fields: list) -> bool:
    """Validate the replacement settings file against declared editable fields."""
    details = load_router_details(details_path)
    mapped = {field["name"] for field in config_fields if field["path"] is not None}
    for key in details:
        if key not in mapped:
            raise ValueError(f"Unknown router setting: {key}")
    return True


def validate_router_output_paths(paths: dict) -> bool:
    """Reject unsafe or overlapping automation output locations."""
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
    return True


def validate_router_inputs(paths: dict, model_specs: dict) -> bool:
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
    return True


def validate_decoded_configuration(data: bytes, model_specs: dict, check_functions: dict, checksum_functions: dict) -> bool:
    """Validate decoded payload bytes and the selected archive format before saving."""
    if not isinstance(data, bytes) or not data:
        raise ValueError("No decoded router configuration available to save")
    router = model_specs["router_specs"]
    method = router["codec"].get("archive")
    if method is not None:
        context = {"codec": router["codec"], "edit": router.get("edit"), "checksum_functions": checksum_functions}
        _handler(check_functions, method)(data, context=context)
    return True



# ---------------------------------------------------------------------
# DECODING AND CONFIGURATION EXTRACTION
# ---------------------------------------------------------------------

def parse_router_wrapper(data: bytes, codec: dict, hardware: str | None, firmware: str | None, decode_functions: dict, checksum_functions: dict) -> dict:
    """Validate a registered wrapper and retain its declared metadata."""
    context = {"codec": codec, "hardware": hardware, "firmware": firmware,
               "checksum_functions": checksum_functions, "header": b""}
    method = codec.get("wrapper")
    payload = data if method is None else _handler(decode_functions, method)(data, context=context)
    return dict(context, data=data, encoded=payload, encrypted=payload)


def extract_router_config(archive_path: str, output_dir: str, model_specs: dict, decode_functions: dict, checksum_functions: dict, strict=False) -> str | bool:
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
        if strict:
            raise
        print(f"Failed to extract router configuration: {exc}")
        return False


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


# ---------------------------------------------------------------------
# CONFIGURATION VIEWING
# ---------------------------------------------------------------------

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


def display_configuration_values(values, context, config_fields):
    """Display selected fields using the existing layout."""
    if not isinstance(values, dict):
        raise ValueError('Configuration values must be a mapping')
    rows = [(field['name'], values[field['name']]) for field in config_fields if field['path'] is not None]
    width = max([len('Field'), *(len(label) for label, _ in rows)])
    print(f"\nConfiguration: {context['source'].name} ({context['relative']})")
    print(f"{'Field':<{width}} | Value")
    print(f"{'-' * width}-+------------------------------")
    for label, value in rows:
        print(f'{label:<{width}} | {value}')
    return True


# ---------------------------------------------------------------------
# CONFIGURATION EDITING
# ---------------------------------------------------------------------

def read_configuration_source(config_dir, edit):
    """Read a safe configuration file and retain its exact source bytes."""
    if not edit or not edit.get("configuration_file"):
        raise ValueError('Configuration format is not established')
    source = Path(config_dir).expanduser()
    validate_directory(source)
    if not source.is_dir():
        raise NotADirectoryError(f'Configuration directory not found: {source}')
    relative = safe_relative(edit['configuration_file'])
    path = source / relative
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f'Configuration file not found or unsafe: {path}')
    original = path.read_bytes()
    return {
        'source': source,
        'relative': relative,
        'original_bytes': original,
        'original': original.decode('utf-8'),
    }


def prepare_configuration_context(source, edit, config_fields, decode_functions, encode_functions=None, view_operations=None, edit_operations=None, destination=None):
    """Bind format and field handlers to a loaded configuration source."""
    if not view_operations or (edit_operations is not None and not edit_operations) or (destination is not None and not edit_operations):
        raise ValueError('Configuration format is not established')
    target = Path(destination).expanduser() if destination is not None else None
    if target is not None:
        if any(item.is_symlink() for item in (target, *target.parents)):
            raise ValueError(f'Unsafe edited configuration symlink: {target}')
        directory = source['source'].resolve()
        if directory == target.resolve() or directory in target.resolve().parents or target.resolve() in directory.parents:
            raise ValueError('Edited directory must be outside the decoded directory')
    return {
        **source,
        'destination': target,
        'specs': _field_specs(edit, config_fields),
        'decrypt_handler': field_handler(edit, decode_functions),
        'encrypt_handler': field_handler(edit, encode_functions) if encode_functions is not None else None,
        'viewer': view_operations[-1],
        'editor': edit_operations[-1] if edit_operations else None,
    }


def prepare_router_changes(values, details, context):
    """Validate requested fields and display the existing edit summary."""
    if not isinstance(values, dict) or not isinstance(details, dict):
        raise ValueError('Router configuration values and details must be mappings')
    for label in details:
        if label not in values:
            raise ValueError(f'Unknown router setting: {label}')
    changes = {label: str(value) for label, value in details.items() if str(value) != values[label]}
    print(f"\nEditing configuration: {context['source'].name}")
    for label, current in values.items():
        print(f'{label}: {current}')
    if changes:
        print('\nChanges:')
        for label, replacement in changes.items():
            print(f'{label}: {values[label]} -> {replacement}')
    else:
        print('No changes made.')
    context['changes'] = changes
    return context


def validate_configuration_changes(original: str, edited: str, specs: dict,
                                   viewer, editor, decrypt_handler=None, encrypt_handler=None) -> bool:
    """Permit only declared replacements using the selected format's own editor."""
    if not isinstance(original, str) or not isinstance(edited, str):
        raise ValueError('Original and edited configuration must be text')
    before = viewer(original, specs, decrypt_handler)
    after = viewer(edited, specs, decrypt_handler)
    if before.keys() != after.keys():
        raise ValueError("Edited configuration fields do not match the original")
    changes = {name: value for name, value in after.items() if value != before[name]}
    if editor(original, specs, changes, encrypt_handler) != edited:
        raise ValueError("Edited configuration differs outside declared editable values")
    return True


# ---------------------------------------------------------------------
# ENCODING AND VERIFICATION
# ---------------------------------------------------------------------

def validate_encode_paths(edited_dir, original_cfg, output_path):
    """Reject unsafe encoding inputs and overlapping output locations."""
    directory, original, output = (Path(value).expanduser() for value in (edited_dir, original_cfg, output_path))
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError(f'Unsafe updated backup symlink: {output}')
    if output.resolve() == original.resolve() or (output.exists() and original.exists() and output.samefile(original)):
        raise ValueError('Output destination must not overwrite the original backup')
    if output.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Output destination must not overwrite the edited configuration directory')
    if not directory.is_dir():
        raise NotADirectoryError(f'Edited configuration directory not found: {directory}')
    validate_directory(directory)
    return {'directory': directory, 'original': original, 'output': output}


def load_encode_credentials(codec, password_path, device_key_path):
    """Load the supplied encoding credentials, retaining optional-credential behaviour."""
    return {
        'password': read_router_credential(password_path, codec),
        'device_key': Path(device_key_path).expanduser().read_bytes() if device_key_path else None,
    }


def compare_configuration_files(directory, files, edit):
    """Compare the edited directory with the original and protect uneditable files."""
    if files is None:
        raise ValueError('Selected decoder does not declare editable configuration files')
    actual = {str(path.relative_to(directory)) for path in directory.rglob('*') if path.is_file()}
    if actual != set(files):
        raise ValueError('Edited files do not match the original configuration')
    configured = str(safe_relative(edit['configuration_file']))
    if configured not in files:
        raise ValueError('Configured file missing from original backup')
    changes = []
    configuration = None
    for name, original_data in files.items():
        edited_data = (directory / safe_relative(name)).read_bytes()
        if name == configured:
            configuration = edited_data
        elif original_data != edited_data:
            raise ValueError(f'Original mismatch in uneditable file: {name}')
        if original_data != edited_data:
            changes.append(name)
    return {
        'changes': changes,
        'original': files[configured].decode('utf-8'),
        'edited': configuration.decode('utf-8'),
        'data': configuration,
    }


def prepare_encode_payload(original_archive, original_context, comparison, credentials, signing, directory):
    """Construct encoding metadata and payload from validated configuration inputs."""
    data = comparison['data'] if original_context.get('configuration_payload') else original_archive
    return {
        **original_context,
        **credentials,
        'signing': signing,
        'edited_dir': str(directory),
        'changes': comparison['changes'],
        'data': data,
        'expected': data,
        'configuration_payload': bool(original_context.get('configuration_payload')),
    }


def verify_encoded_backup(actual, expected):
    """Require byte-identical round-trip recovery before saving."""
    if actual != expected:
        raise ValueError('Generated backup failed decryption verification')
    return True


# ---------------------------------------------------------------------
# FILE AND DIRECTORY SAVING
# ---------------------------------------------------------------------

def save_router_config(decoded_config: bytes, decoded_config_path: str, model_specs: dict, strict=False) -> bool:
    """Save the decoded router configuration in its declared format."""
    if not isinstance(decoded_config, bytes) or not decoded_config:
        if strict:
            raise ValueError("No decoded router configuration available to save")
        print("No decoded router configuration available to save.")
        return False
    try:
        path = Path(decoded_config_path).expanduser()
        extension = model_specs["router_specs"]["codec"]["decoded_extension"]
        if not path.name.endswith(extension):
            raise ValueError(f"Decoded configuration path must end with {extension}")
        if path.is_symlink():
            raise ValueError(f"Unsafe decoded archive symlink: {path}")
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
        if strict:
            raise
        print(f"Failed to save decoded router configuration: {exc}")
        return False


def save_configuration_directory(source: Path, destination: Path, relative: Path, original_bytes: bytes, edited: str, edit: dict, config_fields: list, details: dict, decrypt_handler=None, encrypt_handler=None, viewer=None, editor=None) -> bool:
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
    return True


def save_encoded_backup(output: Path, rebuilt: bytes) -> bool:
    """Write verified backup bytes and atomically publish the output."""
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, prefix=f".{output.name}.", delete=False) as target:
            temp_path = Path(target.name)
            os.chmod(temp_path, 0o600)
            target.write(rebuilt)
        if temp_path.read_bytes() != rebuilt:
            raise ValueError("Generated output failed write verification")
        os.replace(temp_path, output)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return True


# ---------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------

def report_edited_backup(context):
    """Report the atomically saved edited directory."""
    print(f"Saved edited router configuration: {context['destination']}")
    return str(context['destination'])


def report_encoded_backup(output, context):
    """Report the modified files and verified encoded output."""
    print('Modified files: ' + (', '.join(context['changes']) or 'none; original configuration retained'))
    print(f'Updated router backup: {output}; local round-trip verified.')
    return str(output)
