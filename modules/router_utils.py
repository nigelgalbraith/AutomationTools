from __future__ import annotations
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from modules.router_encryption_utils import (
    SUPPORTED_HASHES,
    decrypt_aes_128_cbc_field,
    encrypt_aes_128_cbc_field,
    crypt_aes_256_cbc_fixed_key,
    crypt_aes_256_cbc,
    crypt_technicolor_thenc,
    validate_legacy_key_specs,
    interpret_password_credentials,
    validate_device_key_specs,
    load_device_key_credentials,
)
from modules.router_config_utils import (
    safe_relative,
    validate_xml_declaration,
    parse_xml_field_selector,
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
    "encryption_settings": {"key_hex": str, "iv_hex": str},
    "signature": {"algorithm": str, "modulus_hex": str, "exponent": int, "private_exponent_hex": str},
    "field_encryption": {"algorithm": str, "key_hex": str, "iv_hex": str, "fields": list},
}


# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

def validate_model_specs(specs: dict) -> None:
    """Validate the complete schema and the selected mechanism settings."""
    validate_spec_schema(specs)
    field_settings = specs["field_encryption"]
    algorithm = field_settings["algorithm"]
    if algorithm is None:
        require_null_settings(field_settings, tuple(field_settings), "field_encryption")
    else:
        require_setting(algorithm, "field_encryption.algorithm", algorithm in FIELD_DECRYPT_HANDLERS and algorithm in FIELD_ENCRYPT_HANDLERS)
        require_setting(specs["configuration_format"], "configuration_format", specs["configuration_format"] == "xml")
        for key in ("key_hex", "iv_hex"):
            value = field_settings[key]
            require_setting(value, f"field_encryption.{key}", isinstance(value, str) and len(value) == 32 and all(c in "0123456789abcdefABCDEF" for c in value))
        fields = field_settings["fields"]
        require_setting(fields, "field_encryption.fields", isinstance(fields, list) and bool(fields) and all(isinstance(label, str) and label != "file" and specs["config_fields"].get(label) is not None for label in fields))
        require_setting(fields, "field_encryption.fields", len(set(fields)) == len(fields))
    for key in ("model", "firmware", "hardware", "encryption", "encoding", "key_derivation"):
        value = specs[key]
        require_setting(value, key, isinstance(value, str) and bool(value.strip()) and not any(c in value for c in "\r\n\x00"))
    mechanism = (specs["encryption"], specs["key_derivation"])
    if mechanism not in ENCRYPTION_HANDLERS:
        raise ValueError(f"Unsupported encryption mechanism: {mechanism}")
    if specs["key_derivation"] != "fixed-key":
        require_null_settings(specs["encryption_settings"], ("key_hex", "iv_hex"), "encryption_settings")
        require_null_settings(specs["signature"], ("algorithm", "modulus_hex", "exponent", "private_exponent_hex"), "signature")
    if specs["key_derivation"] == "openssl-legacy":
        validate_legacy_key_specs(specs)
    elif specs["key_derivation"] == "device-key":
        validate_device_key_specs(specs)
    elif specs["key_derivation"] == "fixed-key":
        for key, size in (("key_hex", 64), ("iv_hex", 32)):
            value = specs["encryption_settings"][key]
            require_setting(value, f"encryption_settings.{key}", isinstance(value, str) and len(value) == size and all(c in "0123456789abcdefABCDEF" for c in value))
        require_null_settings(specs, ("password_base", "password_hash", "key_derivation_digest"))
        for key in ("salted", "password_required"):
            require_setting(specs[key], key, specs[key] is False)
        signature = specs["signature"]
        require_setting(signature["algorithm"], "signature.algorithm", signature["algorithm"] == "rsa-md5")
        modulus = signature["modulus_hex"]
        require_setting(modulus, "signature.modulus_hex", isinstance(modulus, str) and 128 <= len(modulus) <= 2048 and all(c in "0123456789abcdefABCDEF" for c in modulus))
        value = signature["exponent"]
        require_setting(value, "signature.exponent", isinstance(value, int) and 3 <= value <= 0xffffffff and value % 2 == 1)
        require_setting(modulus, "signature.modulus_hex", int(modulus, 16) % 2 == 1 and int(modulus, 16).bit_length() >= 512)
        private = signature["private_exponent_hex"]
        if private is not None:
            require_setting(private, "signature.private_exponent_hex", bool(private) and all(c in "0123456789abcdefABCDEF" for c in private) and 1 < int(private, 16) < int(modulus, 16))
    if specs["encoding"] == "base64":
        validate_base64_specs(specs)
    elif specs["encoding"] != "binary":
        raise ValueError(f'Unsupported encoding: {specs["encoding"]}')
    fmt = specs["backup_format"]
    if fmt["type"] not in ("line-wrapper", "technicolor-thenc", "encrypted-configuration"):
        raise ValueError(f'Unsupported backup_format.type: {fmt["type"]}')
    value = fmt["header_lines"]
    require_setting(value, "backup_format.header_lines", isinstance(value, int) and value >= 0)
    require_setting(fmt["preserve_header"], "backup_format.preserve_header", not value or fmt["preserve_header"])
    if fmt["type"] == "line-wrapper":
        validate_line_wrapper_specs(specs)
    elif fmt["type"] == "encrypted-configuration":
        require_setting(specs["configuration_format"], "configuration_format", specs["configuration_format"] == "xml")
        require_setting(specs["encoding"], "encoding", specs["encoding"] == "binary")
        require_setting(specs["key_derivation"], "key_derivation", specs["key_derivation"] == "fixed-key")
        require_setting(fmt["header_lines"], "backup_format.header_lines", fmt["header_lines"] == 0)
        require_setting(fmt["preserve_header"], "backup_format.preserve_header", fmt["preserve_header"] is False)
        require_setting(fmt["iv_length"], "backup_format.iv_length", fmt["iv_length"] == 16)
        require_setting(fmt["signature_length"], "backup_format.signature_length", fmt["signature_length"] == (int(specs["signature"]["modulus_hex"], 16).bit_length() + 7) // 8)
        require_setting(fmt["preamble"], "backup_format.preamble", isinstance(fmt["preamble"], str) and fmt["preamble"].startswith("<?xml") and fmt["preamble"].isascii())
        require_null_settings(fmt, ("payload_line_length", "newline", "backup_version", "header_terminator"), "backup_format")
        require_null_settings(fmt["checksum"], ("algorithm", "scope", "encoding", "after_payload_lines"), "backup_format.checksum")
        require_null_settings(fmt["checksum"]["prefix"], ("encoding", "random_bytes"), "backup_format.checksum.prefix")
        require_null_settings(fmt["trailer"], ("character", "repeat"), "backup_format.trailer")
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
    elif specs["archive"]["format"] == "single-file":
        require_setting(specs["archive"]["compression"], "archive.compression", specs["archive"]["compression"] == "zlib")
    else:
        validate_tar_specs(specs)
    if specs["configuration_format"] is None:
        require_null_settings(specs["config_fields"], tuple(specs["config_fields"]), "config_fields")
        if specs["archive"]["format"] is not None:
            raise ValueError("archive.format must be null when configuration_format is unknown")
    elif specs["configuration_format"] == "key-value":
        validate_key_value_specs(specs)
        require_setting(specs["archive"]["format"], "archive.format", True)
    elif specs["configuration_format"] == "xml":
        require_setting(specs["archive"]["format"], "archive.format", specs["archive"]["format"] == "single-file")
        require_setting(fmt["type"], "backup_format.type", fmt["type"] == "encrypted-configuration")
        path = specs["config_fields"]["file"]
        require_setting(path, "config_fields.file", isinstance(path, str) and bool(path.strip()))
        safe_relative(path)
        for label, selector in specs["config_fields"].items():
            if label != "file" and selector is not None:
                parse_xml_field_selector(selector, label)
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


def parse_router_wrapper(data: bytes, model_specs: dict) -> dict:
    """Validate specifications and parse the configured backup wrapper."""
    validate_model_specs(model_specs)
    if model_specs["backup_format"]["type"] == "line-wrapper":
        return parse_line_wrapper(data, model_specs)
    elif model_specs["backup_format"]["type"] == "technicolor-thenc":
        return parse_technicolor_wrapper(data, model_specs)
    elif model_specs["backup_format"]["type"] == "encrypted-configuration":
        return parse_encrypted_configuration(data, model_specs)
    raise ValueError(f'Unsupported backup_format.type: {model_specs["backup_format"]["type"]}')


def rebuild_router_wrapper(encoded: bytes, header: bytes, specs: dict) -> bytes:
    """Validate specifications and rebuild the configured backup wrapper."""
    validate_model_specs(specs)
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
        relative = Path(config_fields[CONFIG_FIELDS_FILE_KEY])
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
        validate_model_specs(model_specs)
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
    validate_model_specs(model_specs)
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
