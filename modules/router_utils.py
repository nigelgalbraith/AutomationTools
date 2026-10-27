# ---------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------

from __future__ import annotations

from functools import partial
from pathlib import Path
import json
import os
import shutil
import subprocess
import tarfile
import tempfile

import jsonschema

from modules.json_utils import load_json
from modules.router_config_utils import (
    normalize_key_value_fields,
    parse_key_value_fields,
    parse_xml_field_selector,
    validate_key_value_field_changes,
    xml_field_values,
    view_key_value_values,
    edit_key_value_values,
    update_xml_fields,
    validate_xml_field_changes,
)
from modules.router_encryption_utils import (
    decrypt_aes_128_cbc_field, encrypt_aes_128_cbc_field,
    crypt_aes_256_cbc, crypt_aes_256_cbc_fixed_key, crypt_technicolor_thenc,
    interpret_password_credentials,
    calculate_payload_checksum, verify_rsa_md5_signature, sign_rsa_md5_configuration,
)
from modules.router_format_utils import (
    validate_xml_declaration,
    validate_directory,
    safe_relative,
    rebuild_tar_archive,
    extract_tar_archive,
    replace_router_directory,
    read_tar_files,
    split_line_wrapper, prepare_line_wrapper,
    parse_technicolor_wrapper, parse_encrypted_configuration,
    rebuild_technicolor_wrapper,
    encode_base64_payload, decode_base64_payload,
    unpack_signed_configuration, pack_signed_configuration, decode_xml_configuration,
)


# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------

DECODED_EXTENSION = ".tar.gz"

ROUTER_FUNCTIONS = {
    "base64": {"decode": decode_base64_payload, "encode": encode_base64_payload},
    "aes-256-cbc": {"decode": crypt_aes_256_cbc, "encode": crypt_aes_256_cbc},
    "fixed-key": {"decode": crypt_aes_256_cbc_fixed_key, "encode": crypt_aes_256_cbc_fixed_key},
    "device-key": {"decode": crypt_technicolor_thenc, "encode": crypt_technicolor_thenc},
    "line-wrapper": {"decode": split_line_wrapper, "encode": prepare_line_wrapper},
    "technicolor-thenc": {"decode": parse_technicolor_wrapper, "encode": rebuild_technicolor_wrapper},
    "encrypted-configuration": {"decode": parse_encrypted_configuration, "encode": parse_encrypted_configuration},
    "tar.gz": {"decode": read_tar_files, "encode": rebuild_tar_archive},
    "signed-zlib": {"decode": unpack_signed_configuration, "encode": pack_signed_configuration},
    "rsa-md5": {"decode": verify_rsa_md5_signature, "encode": sign_rsa_md5_configuration},
    "md5": {"checksum": calculate_payload_checksum},
    "sha256": {"checksum": calculate_payload_checksum},
    "sha512": {"checksum": calculate_payload_checksum},
    "key-value": {"decode": view_key_value_values, "edit": edit_key_value_values},
    "xml": {"decode": xml_field_values, "edit": update_xml_fields},
    "aes-128-cbc-zero-padded-base64": {"decode": decrypt_aes_128_cbc_field, "encode": encrypt_aes_128_cbc_field},
}


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------


def field_handler(specs: dict, action: str):
    settings = (specs["router_specs"].get("edit") or {}).get("field_encryption")
    if not settings or settings.get("algorithm") is None:
        return None
    return partial(ROUTER_FUNCTIONS[settings["algorithm"]][action],
                   key_hex=settings["key_hex"], iv_hex=settings["iv_hex"])


def parse_line_wrapper(data: bytes, backup_format: dict) -> dict:
    """Verify the wrapper checksum before decoding and validating its Base64 payload."""
    wrapper = ROUTER_FUNCTIONS["line-wrapper"]["decode"](data, backup_format)
    encoded = wrapper["encoded"]
    expected = ROUTER_FUNCTIONS[backup_format["checksum"]]["checksum"](encoded, backup_format["checksum"])
    if wrapper["checksum"] != expected:
        raise ValueError("Backup encrypted payload checksum mismatch")
    encrypted = decode_base64_payload(encoded)
    if encode_base64_payload(encrypted, backup_format) != encoded:
        raise ValueError("Invalid encoded payload line layout")
    return {"header": wrapper["header"], "encoded": encoded,
            "encrypted": encrypted, "checksum": expected}


def rebuild_line_wrapper(encoded: bytes, header: bytes, backup_format: dict) -> bytes:
    """Build and verify a wrapper with its checksum and fresh random prefix."""
    before, after = ROUTER_FUNCTIONS["line-wrapper"]["encode"](encoded, header, backup_format)
    checksum = ROUTER_FUNCTIONS[backup_format["checksum"]]["checksum"](encoded, backup_format["checksum"])
    result = before + checksum + after
    parse_line_wrapper(result, backup_format)
    return result


def parse_router_wrapper(data: bytes, settings: dict) -> dict:
    method = settings.get("wrapper")
    if method == "line-wrapper":
        return parse_line_wrapper(data, settings)
    if method == "technicolor-thenc":
        return ROUTER_FUNCTIONS[method]["decode"](data, settings, settings["hardware"], settings["firmware"])
    if method == "encrypted-configuration":
        return ROUTER_FUNCTIONS[method]["decode"](data)
    if method is None:
        return {"header": b"", "encrypted": data}
    raise ValueError(f"Unsupported router wrapper: {method}")


def rebuild_router_wrapper(encoded: bytes, header: bytes, settings: dict) -> bytes:
    method = settings.get("wrapper")
    if method == "line-wrapper":
        return rebuild_line_wrapper(encoded, header, settings)
    if method == "technicolor-thenc":
        return ROUTER_FUNCTIONS[method]["encode"](encoded, header, settings, settings["hardware"], settings["firmware"])
    if method == "encrypted-configuration":
        ROUTER_FUNCTIONS[method]["encode"](encoded)
    elif method is not None:
        raise ValueError(f"Unsupported router wrapper: {method}")
    return encoded


def decode_signed_configuration(data: bytes, backup_format: dict, signature: dict) -> bytes:
    """Verify the decompressed RSA block before interpreting authenticated XML bytes."""
    signed, signature_bytes = ROUTER_FUNCTIONS["signed-zlib"]["decode"](data, backup_format)
    ROUTER_FUNCTIONS["rsa-md5"]["decode"](signed, signature_bytes, backup_format, signature)
    return decode_xml_configuration(signed, backup_format)


def encode_signed_configuration(xml: bytes, backup_format: dict, signature: dict) -> bytes:
    """Sign XML, compress and pad it, then verify the exact recovered bytes."""
    validate_xml_declaration(xml, backup_format)
    if b"\x00" in xml:
        raise ValueError("XML configuration contains an embedded null byte")
    signed = xml + b"\x00"
    signature_bytes = ROUTER_FUNCTIONS["rsa-md5"]["encode"](signed, backup_format, signature)
    padded = ROUTER_FUNCTIONS["signed-zlib"]["encode"](signed, signature_bytes)
    if decode_signed_configuration(padded, backup_format, signature) != xml:
        raise ValueError("Rebuilt signed configuration failed verification")
    return padded


def crypt_router_payload(data: bytes, password: str, settings: dict, action: str, device_key_path: str | None = None) -> bytes:
    """Pass the selected cipher its explicit parameters and credential type."""
    if not settings.get("encryption"):
        return data
    derivation = settings.get("key_derivation")
    decrypt = action == "decode"
    if derivation == "openssl-legacy":
        return ROUTER_FUNCTIONS[settings["encryption"]][action](data, password, decrypt,
            salted=settings["salted"], password_required=settings["password_required"],
            password_base=settings["password_base"], password_hash=settings["password_hash"],
            key_derivation_digest=settings["key_derivation_digest"])
    if derivation == "fixed-key":
        return ROUTER_FUNCTIONS[derivation][action](data, password, decrypt,
            encryption_settings=settings["encryption_settings"])
    if derivation == "device-key":
        if not device_key_path:
            raise ValueError("THENC device key unavailable: device_key_path is required; an export password is not a device key")
        key = Path(device_key_path).expanduser().read_bytes()
        if not key:
            raise ValueError("THENC device key file is empty")
        return ROUTER_FUNCTIONS[derivation][action](data, password, decrypt, device_key=key)
    raise ValueError(f"Unsupported key_derivation: {derivation}")


def _validate_router_codec(router: dict, codec: dict, edit: dict) -> None:
    """Validate selected implementations, codec requirements and operation ordering."""
    derivation = codec.get("key_derivation")
    cipher = "aes-256-cbc" if derivation == "openssl-legacy" else derivation
    selected = [(codec.get("encoding"), ("decode", "encode")),
                (cipher, ("decode", "encode")),
                (codec.get("wrapper"), ("decode", "encode")),
                (codec.get("archive"), ("decode", "encode")),
                (codec.get("checksum"), ("checksum",)),
                ((codec.get("signature") or {}).get("algorithm"), ("decode", "encode")),
                (edit.get("configuration_format"), ("decode", "edit")),
                ((edit.get("field_encryption") or {}).get("algorithm"), ("decode", "encode"))]
    for method, actions in selected:
        if method is not None:
            for action in actions:
                if not callable(ROUTER_FUNCTIONS.get(method, {}).get(action)):
                    raise ValueError(f"Unsupported {action} method: {method}")
    required = []
    if codec.get("encryption"):
        required.append("key_derivation")
    elif derivation:
        raise ValueError("key_derivation requires encryption")
    if derivation == "openssl-legacy":
        required += ["password_base", "password_hash", "salted", "password_required", "key_derivation_digest"]
        if codec.get("wrapper") != "line-wrapper":
            raise ValueError("OpenSSL legacy backups require a line-wrapper")
    elif derivation == "fixed-key":
        required.append("encryption_settings")
        if any((codec.get("encryption_settings") or {}).get(name) is None for name in ("key_hex", "iv_hex")):
            raise ValueError("Fixed-key encryption requires encryption_settings.key_hex and encryption_settings.iv_hex")
        if codec.get("wrapper") != "encrypted-configuration":
            raise ValueError("Fixed-key backups require encrypted-configuration")
    elif derivation == "device-key":
        if codec.get("wrapper") != "technicolor-thenc":
            raise ValueError("Device-key backups require technicolor-thenc")
    wrapper = codec.get("wrapper")
    if codec.get("encoding") == "base64":
        required.append("payload_line_length")
    if wrapper == "line-wrapper":
        required += ["header_lines", "preserve_header", "payload_line_length", "newline", "checksum",
                     "checksum_after_payload_lines", "checksum_prefix_bytes", "trailer_character", "trailer_repeat"]
        if codec.get("encoding") != "base64" or edit.get("configuration_format") != "key-value":
            raise ValueError("Line wrappers require Base64 and key-value configuration")
        if (codec.get("header_lines") or 0) > 0 and not codec.get("preserve_header"):
            raise ValueError("A nonempty wrapper header must be preserved")
    elif wrapper == "technicolor-thenc":
        required += ["header_lines", "iv_length", "signature_length", "preamble", "backup_version", "header_terminator"]
        if codec.get("header_lines") != 9 or codec.get("iv_length") != 16:
            raise ValueError("THENC requires nine header lines and a 16-byte IV")
        if not router.get("hardware") or not router.get("firmware"):
            raise ValueError("THENC requires hardware and firmware identifiers")
        if edit or codec.get("archive"):
            raise ValueError("THENC configuration editing and archives are not established")
    elif wrapper == "encrypted-configuration":
        if derivation != "fixed-key" or edit.get("configuration_format") != "xml":
            raise ValueError("Encrypted configurations require fixed-key AES and XML configuration")
    if wrapper in ("technicolor-thenc", "encrypted-configuration") and codec.get("encoding"):
        raise ValueError("Binary wrappers do not use transport encoding")
    if codec.get("archive") == "signed-zlib":
        required += ["signature", "signature_length", "preamble"]
        if any((codec.get("signature") or {}).get(name) is None for name in ("algorithm", "modulus_hex", "exponent")):
            raise ValueError("Signed zlib requires signature.algorithm, signature.modulus_hex and signature.exponent")
        if edit.get("configuration_format") != "xml" or wrapper != "encrypted-configuration":
            raise ValueError("Signed zlib requires XML and encrypted-configuration")
        if not (codec.get("preamble") or "").startswith("<?xml"):
            raise ValueError("Signed configurations require an XML preamble")
    if edit.get("configuration_format") == "key-value" and codec.get("archive") != "tar.gz":
        raise ValueError("Key-value configuration requires a tar.gz archive")
    if edit.get("configuration_format") == "xml" and codec.get("archive") != "signed-zlib":
        raise ValueError("XML configuration requires a signed-zlib archive")
    for name in required:
        if codec.get(name) is None:
            raise ValueError(f"Required codec parameter {name} is missing or null")
    for action, default in (("decode", ("wrapper", "encoding", "encryption", "archive")),
                            ("encode", ("archive", "encryption", "encoding", "wrapper"))):
        order = codec.get(f"{action}_order") or default
        for step in default:
            if codec.get(step) and step not in order:
                raise ValueError(f"{action}_order is missing the active {step} operation")


def _validate_router_fields(router: dict, config_fields: list, codec: dict, edit: dict) -> None:
    """Validate logical mappings, protected fields and encoding-only settings."""
    names = [field["name"] for field in config_fields]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate logical configuration field names")
    mapped = set()
    for field in config_fields:
        if field["path"] is None:
            continue
        mapped.add(field["name"])
        if edit.get("configuration_format") == "xml":
            parse_xml_field_selector(field["path"], field["name"])
        elif edit.get("configuration_format") == "key-value":
            if not field["path"].strip() or any(char in field["path"] for char in "=\r\n\x00"):
                raise ValueError(f"Invalid configuration key: {field['name']}")
        else:
            raise ValueError("Configuration field mappings require an edit section")
    fields = edit.get("field_encryption") or {}
    if edit.get("configuration_format") and edit.get("configuration_file") is None:
        raise ValueError("Configuration editing requires configuration_file")
    if fields.get("algorithm") and any(fields.get(name) is None for name in ("key_hex", "iv_hex", "fields")):
        raise ValueError("Field encryption requires key_hex, iv_hex and fields")
    if fields.get("algorithm") and edit.get("configuration_format") != "xml":
        raise ValueError("Protected fields require XML configuration")
    for name in fields.get("fields") or []:
        if name not in mapped:
            raise ValueError(f"Encrypted field has no configuration mapping: {name}")
    if router.get("encode") and codec.get("archive") != "signed-zlib":
        raise ValueError("Private signing settings require a signed-zlib archive")


def _validate_router_inputs(paths: dict, model_specs: dict) -> None:
    """Check required input files and the selected password or device-key credentials."""
    for key in ("model_specs_path", "model_specs_readme_path", "template_config_path",
                "router_details_path"):
        if not Path(paths[key]).expanduser().is_file():
            raise FileNotFoundError(f"Required router input not found: {paths[key]}")
    if model_specs["router_specs"]["codec"].get("key_derivation") == "device-key":
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
            read_router_credential(paths.get(key), model_specs["router_specs"]["codec"])


def validate_router_settings(specs: dict) -> None:
    """Check required method settings, compatible formats and logical field mappings."""
    router = specs["router_specs"]
    codec = router["codec"]
    edit = router.get("edit") or {}
    _validate_router_codec(router, codec, edit)
    _validate_router_fields(router, specs["config_fields"], codec, edit)


def validate_tar_gzip_config(decoded: bytes, model_specs: dict) -> None:
    """Validate TAR/GZIP contents and the declared key-value configuration."""
    files = ROUTER_FUNCTIONS["tar.gz"]["decode"](decoded)
    configured = str(Path(model_specs["router_specs"]["edit"]["configuration_file"]))
    if configured not in files:
        raise ValueError("Configured file missing from archive")
    parse_key_value_fields(files[configured].decode("utf-8"), model_specs)


def validate_edited_fields(original_archive: bytes, directory: Path, specs: dict) -> None:
    """Match every original byte except values explicitly declared editable."""
    config_path = Path(specs["router_specs"]["edit"]["configuration_file"])
    found = False
    files = read_tar_files(original_archive)
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


def validate_edited_xml(original: bytes, directory: Path, specs: dict, decrypt_handler=None, encrypt_handler=None) -> tuple[bytes, list[str]]:
    """Permit only configured XML field edits relative to the authenticated original."""
    if not directory.is_dir():
        raise NotADirectoryError(f"Edited configuration directory not found: {directory}")
    validate_directory(directory)
    relative = Path(specs["router_specs"]["edit"]["configuration_file"])
    actual = {path.relative_to(directory) for path in directory.rglob("*") if path.is_file()}
    if actual != {relative}:
        raise ValueError("Edited files do not match the original single-file configuration")
    edited = (directory / relative).read_bytes()
    validate_xml_declaration(edited, specs["router_specs"]["codec"])
    before = xml_field_values(original.decode("utf-8"), specs, decrypt_handler)
    after = xml_field_values(edited.decode("utf-8"), specs, decrypt_handler)
    changes = {label: value for label, value in after.items() if value != before[label]}
    validate_xml_field_changes(original.decode("utf-8"), edited.decode("utf-8"), specs, changes, decrypt_handler, encrypt_handler)
    return edited, [str(relative)] if edited != original else []


def extract_xml_configuration(archive_path: Path, output: Path, model_specs: dict) -> None:
    """Stage the preserved XML bytes as a single configuration file and replace the destination."""
    decoded = archive_path.read_bytes()
    validate_xml_declaration(decoded, model_specs["router_specs"]["codec"])
    relative = Path(model_specs["router_specs"]["edit"]["configuration_file"])
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=f".{output.name}.") as directory:
        prepared = Path(directory) / "configuration"
        target = prepared / relative
        target.parent.mkdir(parents=True, mode=0o700)
        target.write_bytes(decoded)
        target.chmod(0o600)
        replace_router_directory(prepared, output)


def _save_configuration_directory(
    source: Path,
    destination: Path,
    relative: Path,
    original_bytes: bytes,
    edited: str,
    model_specs: dict,
    details: dict,
) -> None:
    """Stage and verify a non-interactive edited copy before replacing its destination."""
    configuration_format = (model_specs["router_specs"].get("edit") or {}).get("configuration_format")
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
        if configuration_format == "xml":
            validate_xml_field_changes(original, target.read_bytes().decode("utf-8"), model_specs, details, field_handler(model_specs, "decode"), field_handler(model_specs, "encode"))
        if source_file.read_bytes() != original_bytes:
            raise ValueError("Original decoded configuration changed during editing")
        validate_directory(staged)
        replace_router_directory(staged, destination)
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def _save_encoded_backup(
    output: Path,
    rebuilt: bytes,
    rebuilt_archive: bytes,
    single_file: bool,
    model_specs: dict,
    target_password_path: str,
    device_key_path: str | None,
) -> None:
    """Verify the temporary backup and atomically publish the single automation output."""
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


# ---------------------------------------------------------------------
# ROUTER CREDENTIALS
# ---------------------------------------------------------------------


def read_router_credential(password_path: str, specs: dict) -> str | bytes:
    """Read the selected credential type without treating passwords as device keys."""
    if specs.get("key_derivation") in (None, "fixed-key"):
        return ""
    if specs.get("key_derivation") == "openssl-legacy":
        if not specs.get("password_required", False):
            return ""
        if not password_path:
            raise ValueError("Router password file is required by the selected specification")
        return interpret_password_credentials(Path(password_path).expanduser().read_bytes())
    elif specs.get("key_derivation") == "device-key":
        raise ValueError("THENC credential loading is not established; an export password is not a device key")
    raise ValueError(f'Unsupported key_derivation: {specs.get("key_derivation")}')


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


def validate_router_configuration(paths: dict, model_specs: dict) -> bool:
    """Validate configured inputs and distinct output locations for full automation."""
    if (model_specs["router_specs"].get("edit") or {}).get("configuration_format") is not None and (model_specs["router_specs"].get("edit") or {}).get("configuration_format") not in ROUTER_FUNCTIONS:
        raise ValueError("Configuration editing is unsupported for this format")
    if model_specs["router_specs"]["codec"].get("archive") == "signed-zlib" and (model_specs["router_specs"].get("encode") or {}).get("private_exponent_hex") is None:
        raise ValueError("Signed backup encoding requires signature.private_exponent_hex; Decode and View remain available")
    _validate_router_inputs(paths, model_specs)
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
    parse_router_wrapper(Path(paths["template_config_path"]).expanduser().read_bytes(), {**model_specs["router_specs"]["codec"], "hardware": model_specs["router_specs"].get("hardware"), "firmware": model_specs["router_specs"].get("firmware")})
    print("Router configuration validated.")
    return True


# ---------------------------------------------------------------------
# ROUTER DECODING
# ---------------------------------------------------------------------


def decode_router_config(config_path: str | bytes, model_specs: dict, password_path: str | None = None, device_key_path: str | None = None, *, password: str | None = None) -> bytes:
    """Decode bytes or an application backup path in the specified order."""
    settings = {**model_specs["router_specs"]["codec"],
                "hardware": model_specs["router_specs"].get("hardware"),
                "firmware": model_specs["router_specs"].get("firmware")}
    data = config_path if isinstance(config_path, bytes) else Path(config_path).expanduser().read_bytes()
    if password is None:
        password = "" if not settings.get("encryption") or settings.get("key_derivation") == "device-key" else read_router_credential(password_path, settings)
    if password is False:
        return False
    for operation in (settings.get("decode_order") or ("wrapper", "encoding", "encryption", "archive")):
        if operation == "wrapper":
            wrapper = parse_router_wrapper(data, settings)
            data = wrapper["encoded" if settings.get("wrapper") == "line-wrapper" else "encrypted"]
        elif operation == "encoding" and settings.get("encoding"):
            data = ROUTER_FUNCTIONS[settings["encoding"]]["decode"](data)
        elif operation == "encryption":
            data = crypt_router_payload(data, password, settings, "decode", device_key_path)
        elif operation == "archive":
            if settings.get("archive") == "tar.gz":
                validate_tar_gzip_config(data, model_specs)
            elif settings.get("archive") == "signed-zlib":
                data = decode_signed_configuration(data, settings, settings["signature"])
    return data


# ---------------------------------------------------------------------
# CONFIGURATION SAVING
# ---------------------------------------------------------------------


def save_router_config(decoded_config: bytes, decoded_config_path: str, model_specs: dict) -> bool:
    """Save the decoded router configuration in its declared format."""
    if not isinstance(decoded_config, bytes) or not decoded_config:
        print("No decoded router configuration available to save.")
        return False
    try:
        path = Path(decoded_config_path).expanduser()
        extension = ".xml" if (model_specs["router_specs"].get("edit") or {}).get("configuration_format") == "xml" else DECODED_EXTENSION
        if not path.name.endswith(extension):
            raise ValueError(f"Decoded configuration path must end with {extension}")
        if path.is_symlink():
            raise ValueError(f"Unsafe decoded archive symlink: {path}")
        if (model_specs["router_specs"].get("edit") or {}).get("configuration_format") == "xml":
            validate_xml_declaration(decoded_config, model_specs["router_specs"]["codec"])
        else:
            read_tar_files(decoded_config)
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


# ---------------------------------------------------------------------
# CONFIGURATION EXTRACTION
# ---------------------------------------------------------------------


def extract_router_config(archive_path: str, output_dir: str, model_specs: dict) -> str | bool:
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
        if (model_specs["router_specs"].get("edit") or {}).get("configuration_format") == "xml":
            extract_xml_configuration(archive_path, output, model_specs)
        else:
            extract_tar_archive(archive_path, output)
        print(f"Extracted router configuration: {output}")
        return str(output)
    except (OSError, ValueError, TypeError, tarfile.TarError) as exc:
        print(f"Failed to extract router configuration: {exc}")
        return False


# ---------------------------------------------------------------------
# CONFIGURATION VIEWING
# ---------------------------------------------------------------------


def view_router_config_fields(config_dir: str, model_specs: dict) -> bool:
    """Display selected router configuration fields."""
    try:
        viewer = ROUTER_FUNCTIONS.get((model_specs["router_specs"].get("edit") or {}).get("configuration_format"), {}).get("decode")
        if viewer is None:
            raise ValueError(f'Unsupported configuration_format for viewing: {(model_specs["router_specs"].get("edit") or {}).get("configuration_format")}')
        config_fields = model_specs["config_fields"]
        directory = Path(config_dir).expanduser()
        validate_directory(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Configuration directory not found: {directory}")
        config_file = model_specs["router_specs"]["edit"]["configuration_file"]
        relative = Path(config_file)
        path = directory / relative
        if not path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        contents = path.read_bytes().decode("utf-8")
        values = viewer(contents, model_specs, field_handler(model_specs, "decode"))
        rows = []
        for field in config_fields:
            label, key = field["name"], field["path"]
            if key is not None:
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


# ---------------------------------------------------------------------
# CONFIGURATION EDITING
# ---------------------------------------------------------------------


def edit_router_config_fields(config_dir: str, edited_dir: str, model_specs: dict, router_details_path: str) -> str | bool:
    """Copy and edit selected router configuration fields."""
    try:
        configuration_format = (model_specs["router_specs"].get("edit") or {}).get("configuration_format")
        editor = ROUTER_FUNCTIONS.get(configuration_format, {}).get("edit")
        viewer = ROUTER_FUNCTIONS.get(configuration_format, {}).get("decode")
        if editor is None or viewer is None:
            raise ValueError(f"Unsupported configuration_format for editing: {configuration_format}")
        decrypt_handler = field_handler(model_specs, "decode")
        encrypt_handler = field_handler(model_specs, "encode")
        source = Path(config_dir).expanduser()
        validate_directory(source)
        destination = Path(edited_dir).expanduser()
        if not source.is_dir():
            raise NotADirectoryError(f"Decoded configuration directory not found: {source}")
        if any(path.is_symlink() for path in (destination, *destination.parents)):
            raise ValueError(f"Unsafe edited configuration symlink: {destination}")
        if source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents or destination.resolve() in source.resolve().parents:
            raise ValueError("Edited directory must be outside the decoded directory")
        relative = safe_relative(model_specs["router_specs"]["edit"]["configuration_file"])
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
        _save_configuration_directory(source, destination, relative, original_bytes, edited, model_specs, details)
        print(f"Saved edited router configuration: {destination}")
        return str(destination)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(f"Failed to edit router configuration: {exc}")
        return False


# ---------------------------------------------------------------------
# ROUTER ENCODING
# ---------------------------------------------------------------------


def encode_router_config_bytes(data: bytes, specs: dict, password: str = "", header: bytes = b"", device_key_path: str | None = None) -> bytes:
    """Encode prepared configuration bytes in the independent encode order."""
    settings = {**specs["router_specs"]["codec"],
                "hardware": specs["router_specs"].get("hardware"),
                "firmware": specs["router_specs"].get("firmware")}
    for operation in (settings.get("encode_order") or ("archive", "encryption", "encoding", "wrapper")):
        if operation == "archive" and settings.get("archive") == "signed-zlib":
            signature = {**settings["signature"], **(specs["router_specs"].get("encode") or {})}
            signature.setdefault("private_exponent_hex", None)
            data = encode_signed_configuration(data, settings, signature)
        elif operation == "encryption":
            data = crypt_router_payload(data, password, settings, "encode", device_key_path)
        elif operation == "encoding" and settings.get("encoding"):
            data = ROUTER_FUNCTIONS[settings["encoding"]]["encode"](data, settings)
        elif operation == "wrapper":
            data = rebuild_router_wrapper(data, header, settings)
    return data


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
        single_file = model_specs["router_specs"]["codec"].get("archive") == "signed-zlib"
        directory = Path(edited_dir).expanduser()
        original = Path(original_cfg).expanduser()
        output = Path(output_path).expanduser()
        if any(path.is_symlink() for path in (output, *output.parents)):
            raise ValueError(f"Unsafe updated backup symlink: {output}")
        if output.resolve() == original.resolve() or (output.exists() and original.exists() and output.samefile(original)):
            raise ValueError("Output destination must not overwrite the original backup")
        if output.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Output destination must not overwrite the edited configuration directory")
        codec = model_specs["router_specs"]["codec"]
        wrapper = parse_router_wrapper(original.read_bytes(), {
            **codec, "hardware": model_specs["router_specs"].get("hardware"),
            "firmware": model_specs["router_specs"].get("firmware")})
        original_archive = decode_router_config(str(original), model_specs, template_password_path, template_device_key_path)
        if single_file:
            rebuilt_archive, changes = validate_edited_xml(original_archive, directory, model_specs,
                field_handler(model_specs, "decode"), field_handler(model_specs, "encode"))
        else:
            rebuilt_archive, changes = rebuild_tar_archive(original_archive, str(directory))
            validate_edited_fields(original_archive, directory, model_specs)
        target_password = "" if codec.get("key_derivation") == "device-key" else read_router_credential(target_password_path, codec)
        rebuilt = encode_router_config_bytes(rebuilt_archive, model_specs, target_password, wrapper["header"], device_key_path)
        decrypted = decode_router_config(rebuilt, model_specs, device_key_path=device_key_path, password=target_password)
        if decrypted != rebuilt_archive:
            raise ValueError("Generated backup failed decryption verification")
        if not single_file:
            read_tar_files(decrypted)
        _save_encoded_backup(output, rebuilt, rebuilt_archive, single_file,
                             model_specs, target_password_path, device_key_path)
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
