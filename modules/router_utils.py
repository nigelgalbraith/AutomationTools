from __future__ import annotations
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from modules.json_utils import load_json
from modules.router_encryption_utils import (
    decrypt_aes_128_cbc_field,
    encrypt_aes_128_cbc_field,
    crypt_aes_256_cbc_fixed_key,
    crypt_aes_256_cbc,
    crypt_technicolor_thenc,
    interpret_password_credentials,
    load_device_key_credentials,
)
from modules.router_config_utils import (
    safe_relative,
    validate_xml_declaration,
    xml_field_values,
    view_key_value_values,
    edit_key_value_values,
    update_xml_fields,
    validate_xml_field_changes,
    validate_edited_xml,
    validate_directory,
    parse_key_value_fields,
    key_value_values,
    update_key_value_fields,
)
from modules.router_format_utils import (
    validate_tar_gzip_config,
    parse_encrypted_configuration,
    decode_signed_configuration,
    encode_signed_configuration,
    extract_xml_configuration,
    parse_line_wrapper,
    parse_technicolor_wrapper,
    rebuild_technicolor_wrapper,
    rebuild_line_wrapper,
    read_tar_files,
    replace_router_directory,
    extract_tar_archive,
    rebuild_tar_archive,
    validate_edited_fields,
    encode_router_payload,
)

# ---------------------------------------------------------------------
# FILE CONSTANTS
# ---------------------------------------------------------------------

DECODED_EXTENSION = ".tar.gz"
MODEL_SPECS_EXTENSION = ".json"
CONFIG_FIELDS_KEY = "config_fields"
CONFIG_FIELDS_FILE_KEY = "file"

# ---------------------------------------------------------------------
# DISPATCHER HANDLERS
# ---------------------------------------------------------------------

ENCRYPTION_HANDLERS = {
    ("aes-256-cbc", "openssl-legacy"): crypt_aes_256_cbc,
    ("aes-256-cbc", "device-key"): crypt_technicolor_thenc,
    ("aes-256-cbc", "fixed-key"): crypt_aes_256_cbc_fixed_key,
}

FIELD_ENCRYPT_HANDLERS = {
    "aes-128-cbc-zero-padded-base64": encrypt_aes_128_cbc_field,
}

FIELD_DECRYPT_HANDLERS = {
    "aes-128-cbc-zero-padded-base64": decrypt_aes_128_cbc_field,
}

CONFIG_VIEW_HANDLERS = {
    "key-value": view_key_value_values,
    "xml": xml_field_values,
}

CONFIG_EDIT_HANDLERS = {
    "key-value": edit_key_value_values,
    "xml": update_xml_fields,
}

# ---------------------------------------------------------------------
# DISPATCHER FUNCTIONS
# ---------------------------------------------------------------------

def read_router_credential(password_path: str, specs: dict) -> str | bytes:
    """Read the selected credential type without treating passwords as device keys."""
    if specs["key_derivation"] == "fixed-key":
        return ""
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
    mechanism = (model_specs["encryption"], model_specs["key_derivation"])
    if model_specs["key_derivation"] == "device-key" and device_key is None:
        if not device_key_path:
            raise ValueError("THENC device key unavailable: device_key_path is required; an export password is not a device key")
        device_key = Path(device_key_path).expanduser().read_bytes()
        if not device_key:
            raise ValueError("THENC device key file is empty")
    return ENCRYPTION_HANDLERS[mechanism](data, password, model_specs, True, wrapper=wrapper, device_key=device_key)


def encrypt_router_payload(data: bytes, password: str, model_specs: dict, device_key_path: str | None = None) -> bytes:
    """Encrypt using the encryption method defined in the router specification."""
    mechanism = (model_specs["encryption"], model_specs["key_derivation"])
    if model_specs["key_derivation"] == "device-key":
        if not device_key_path:
            raise ValueError("THENC device key unavailable: device_key_path is required; an export password is not a device key")
        device_key = Path(device_key_path).expanduser().read_bytes()
        if not device_key:
            raise ValueError("THENC device key file is empty")
        return ENCRYPTION_HANDLERS[mechanism](data, password, model_specs, False, device_key=device_key)
    return ENCRYPTION_HANDLERS[mechanism](data, password, model_specs, False)


def parse_router_wrapper(data: bytes, model_specs: dict) -> dict:
    """Parse the configured backup wrapper using loaded specifications."""
    if model_specs["backup_format"]["type"] == "line-wrapper":
        return parse_line_wrapper(data, model_specs)
    elif model_specs["backup_format"]["type"] == "technicolor-thenc":
        return parse_technicolor_wrapper(data, model_specs)
    elif model_specs["backup_format"]["type"] == "encrypted-configuration":
        return parse_encrypted_configuration(data, model_specs)
    raise ValueError(f'Unsupported backup_format.type: {model_specs["backup_format"]["type"]}')


def rebuild_router_wrapper(encoded: bytes, header: bytes, specs: dict) -> bytes:
    """Rebuild the configured backup wrapper using loaded specifications."""
    if specs["backup_format"]["type"] == "line-wrapper":
        return rebuild_line_wrapper(encoded, header, specs)
    elif specs["backup_format"]["type"] == "technicolor-thenc":
        return rebuild_technicolor_wrapper(encoded, header, specs)
    elif specs["backup_format"]["type"] == "encrypted-configuration":
        parse_encrypted_configuration(encoded, specs)
        return encoded
    raise ValueError(f'Unsupported backup_format.type: {specs["backup_format"]["type"]}')

# ---------------------------------------------------------------------
# ROUTER WORKFLOWS
# ---------------------------------------------------------------------

def load_router_model_specs(specs_path: str) -> dict:
    """Load a model dictionary; CHECK and derived-data preparation belong to PRE."""
    path = Path(specs_path).expanduser()
    if path.suffix.lower() != MODEL_SPECS_EXTENSION:
        raise ValueError(f"Router model specifications must be a {MODEL_SPECS_EXTENSION} file")
    specs = load_json(path)
    if not isinstance(specs, dict):
        raise ValueError(f"Router model specifications must be a JSON object: {path}")
    return specs


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
    if model_specs["archive"] == {"format": "single-file", "compression": "zlib"}:
        return decode_signed_configuration(decoded, model_specs)
    validate_tar_gzip_config(decoded, model_specs)
    return decoded


def save_router_config(decoded_config: bytes, decoded_config_path: str, model_specs: dict) -> bool:
    """Validate and atomically save the declared archive format."""
    if not isinstance(decoded_config, bytes) or not decoded_config:
        print("No decoded router configuration available to save.")
        return False
    try:
        path = Path(decoded_config_path).expanduser()
        extension = ".xml" if model_specs["configuration_format"] == "xml" else DECODED_EXTENSION
        if not path.name.endswith(extension):
            raise ValueError(f"Decoded configuration path must end with {extension}")
        if path.is_symlink():
            raise ValueError(f"Unsafe decoded archive symlink: {path}")
        if model_specs["configuration_format"] == "xml":
            validate_xml_declaration(decoded_config, model_specs)
        else:
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
        if model_specs["configuration_format"] == "xml":
            extract_xml_configuration(archive_path, output, model_specs)
        else:
            extract_tar_archive(archive_path, output, model_specs)
        print(f"Extracted router configuration: {output}")
        return str(output)
    except (OSError, ValueError, TypeError, tarfile.TarError) as exc:
        print(f"Failed to extract router configuration: {exc}")
        return False


def view_router_config_fields(config_dir: str, model_specs: dict) -> bool:
    """Display selected router configuration fields."""
    try:
        viewer = CONFIG_VIEW_HANDLERS.get(model_specs["configuration_format"])
        if viewer is None:
            raise ValueError(f'Unsupported configuration_format for viewing: {model_specs["configuration_format"]}')
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
        values = viewer(contents, model_specs, FIELD_DECRYPT_HANDLERS.get(model_specs["field_encryption"]["algorithm"]))
        rows = []
        for label, key in config_fields.items():
            if label != CONFIG_FIELDS_FILE_KEY and key is not None:
                rows.append((label, values[label]))
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
        configuration_format = model_specs["configuration_format"]
        editor = CONFIG_EDIT_HANDLERS.get(configuration_format)
        viewer = CONFIG_VIEW_HANDLERS.get(configuration_format)
        if editor is None or viewer is None:
            raise ValueError(f"Unsupported configuration_format for editing: {configuration_format}")
        algorithm = model_specs["field_encryption"]["algorithm"]
        decrypt_handler = FIELD_DECRYPT_HANDLERS.get(algorithm)
        encrypt_handler = FIELD_ENCRYPT_HANDLERS.get(algorithm)
        config_fields = model_specs["config_fields"]
        source = Path(config_dir).expanduser()
        validate_directory(source)
        destination = Path(edited_dir).expanduser()
        if not source.is_dir():
            raise NotADirectoryError(f"Decoded configuration directory not found: {source}")
        if any(path.is_symlink() for path in (destination, *destination.parents)):
            raise ValueError(f"Unsafe edited configuration symlink: {destination}")
        if source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents or destination.resolve() in source.resolve().parents:
            raise ValueError("Edited directory must be outside the decoded directory")
        relative = safe_relative(config_fields[CONFIG_FIELDS_FILE_KEY])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid configuration file path")
        source_file = source / relative
        if not source_file.is_file() or source_file.is_symlink():
            raise FileNotFoundError(f"Configuration file not found or unsafe: {source_file}")
        original_bytes = source_file.read_bytes()
        original = original_bytes.decode("utf-8")
        values = viewer(original, model_specs, decrypt_handler)
        details = load_router_details(router_details_path)
        for label in details:
            if label not in values:
                raise ValueError(f"Unknown router setting: {label}")
        if configuration_format == "xml":
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
        edited = editor(original, model_specs, details, encrypt_handler)
        if configuration_format == "xml":
            validate_xml_field_changes(original, edited, model_specs, details, decrypt_handler, encrypt_handler)
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
            if configuration_format == "xml":
                validate_xml_field_changes(original, target.read_bytes().decode("utf-8"), model_specs, details, decrypt_handler, encrypt_handler)
            if source_file.read_bytes() != original_bytes:
                raise ValueError("Original decoded configuration changed during editing")
            validate_directory(staged)
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
        single_file = model_specs["archive"] == {"format": "single-file", "compression": "zlib"}
        directory = Path(edited_dir).expanduser()
        original = Path(original_cfg).expanduser()
        output = Path(output_path).expanduser()
        if any(path.is_symlink() for path in (output, *output.parents)):
            raise ValueError(f"Unsafe updated backup symlink: {output}")
        if output.resolve() == original.resolve() or (output.exists() and original.exists() and output.samefile(original)):
            raise ValueError("Output destination must not overwrite the original backup")
        if output.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Output destination must not overwrite the edited configuration directory")
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
        if single_file:
            original_archive = decode_signed_configuration(original_archive, model_specs)
            algorithm = model_specs["field_encryption"]["algorithm"]
            rebuilt_archive, changes = validate_edited_xml(original_archive, directory, model_specs,
                FIELD_DECRYPT_HANDLERS.get(algorithm), FIELD_ENCRYPT_HANDLERS.get(algorithm))
            payload = encode_signed_configuration(rebuilt_archive, model_specs)
        else:
            rebuilt_archive, changes = rebuild_tar_archive(original_archive, str(directory), model_specs)
            validate_edited_fields(original_archive, directory, model_specs)
            payload = rebuilt_archive
        # Encrypt for target router using its factory password
        target_password = "" if model_specs["key_derivation"] == "device-key" else read_router_credential(target_password_path, model_specs)
        encrypted = encrypt_router_payload(
            payload,
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
        if single_file:
            decrypted = decode_signed_configuration(decrypted, model_specs)
        if decrypted != rebuilt_archive:
            raise ValueError("Generated backup failed decryption verification")
        if not single_file:
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
            if temp_path.read_bytes() != rebuilt:
                raise ValueError("Generated output failed write verification")
            if single_file:
                recovered = decode_router_config(str(temp_path), model_specs, target_password_path, device_key_path=device_key_path)
                if recovered != rebuilt_archive:
                    raise ValueError("Generated backup failed independent decode verification")
            os.replace(temp_path, output)
        finally:
            temp_path.unlink(missing_ok=True)
        print(
            "Modified files: " +
            (", ".join(changes) or ("none; original XML retained" if single_file else "none; original compressed archive retained"))
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
        UnicodeError,
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
    """Validate configured inputs and distinct output locations for full automation."""
    if model_specs["configuration_format"] is not None and model_specs["configuration_format"] not in CONFIG_EDIT_HANDLERS:
        raise ValueError("Configuration editing is unsupported for this format")
    if model_specs["archive"]["format"] == "single-file" and model_specs["signature"]["private_exponent_hex"] is None:
        raise ValueError("Signed backup encoding requires signature.private_exponent_hex; Decode and View remain available")
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
