# ---------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
import base64
import hashlib
import hmac
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from modules.router_format_utils import validate_xml_declaration

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------

OPENSSL_HEADER = b"Salted__"


# ---------------------------------------------------------------------
# LEGACY AES-256-CBC
# ---------------------------------------------------------------------

def validate_legacy_aes_settings(data=None, *, context) -> None:
    """Validate legacy derivation settings and, when requested, credentials."""
    codec = context["codec"]
    salted, password_required = codec.get("salted"), codec.get("password_required")
    password_base, password_hash = codec.get("password_base"), codec.get("password_hash")
    key_derivation_digest = codec.get("key_derivation_digest")
    if any(value is None for value in (salted, password_required, password_base, password_hash, key_derivation_digest)):
        raise ValueError("Legacy AES requires salt, password and derivation settings")
    if not isinstance(salted, bool) or not isinstance(password_required, bool):
        raise ValueError("Salt and password requirements must be boolean")
    if password_hash != "none":
        hashlib.new(password_hash)
    hashlib.new(key_derivation_digest)
    if context.get("check_inputs"):
        password = context.get("password", "")
        if not isinstance(password, str) or (password_required and not password):
            raise ValueError("Factory Wi-Fi password is required")
        hashed = password if password_hash == "none" else hashlib.new(password_hash, password.encode("utf-8")).hexdigest()
        if any(c in password_base + hashed for c in "\r\n\x00"):
            raise ValueError("Passphrase contains unsupported control characters")


def encrypt_aes_256_cbc(data: bytes, *, context: dict) -> bytes:
    """Encrypt AES with explicit OpenSSL legacy derivation."""
    validate_legacy_aes_settings(context=context)
    codec = context["codec"]
    password = context.get("password", "")
    salted, password_required = codec["salted"], codec["password_required"]
    password_base, password_hash = codec["password_base"], codec["password_hash"]
    key_derivation_digest = codec["key_derivation_digest"]
    if not isinstance(password, str) or (password_required and not password):
        raise ValueError("Factory Wi-Fi password is required")
    hashed = password if password_hash == "none" else hashlib.new(password_hash, password.encode("utf-8")).hexdigest()
    passphrase = password_base + hashed
    if any(c in passphrase for c in "\r\n\x00"):
        raise ValueError("Passphrase contains unsupported control characters")
    options = ["-salt" if salted else "-nosalt", "-md", key_derivation_digest, "-pass", "stdin"]
    credential = passphrase.encode("utf-8") + b"\n"
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "payload"
        source.write_bytes(data)
        command = ["openssl", "enc", "-aes-256-cbc", "-e",
                   "-in", str(source), *options]
        result = subprocess.run(command, input=credential,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ValueError("OpenSSL failed: incorrect factory password, corrupt payload or unavailable cipher/digest")
    return result.stdout


def decrypt_aes_256_cbc(data: bytes, *, context: dict) -> bytes:
    """Decrypt AES with explicit OpenSSL legacy derivation."""
    validate_legacy_aes_settings(context=context)
    codec = context["codec"]
    password = context.get("password", "")
    salted, password_required = codec["salted"], codec["password_required"]
    password_base, password_hash = codec["password_base"], codec["password_hash"]
    key_derivation_digest = codec["key_derivation_digest"]
    if salted and (not data.startswith(OPENSSL_HEADER) or len(data) < 32):
        raise ValueError("Missing or corrupt OpenSSL salted header")
    if not isinstance(password, str) or (password_required and not password):
        raise ValueError("Factory Wi-Fi password is required")
    hashed = password if password_hash == "none" else hashlib.new(password_hash, password.encode("utf-8")).hexdigest()
    passphrase = password_base + hashed
    if any(c in passphrase for c in "\r\n\x00"):
        raise ValueError("Passphrase contains unsupported control characters")
    options = ["-salt" if salted else "-nosalt", "-md", key_derivation_digest, "-pass", "stdin"]
    credential = passphrase.encode("utf-8") + b"\n"
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "payload"
        source.write_bytes(data)
        command = ["openssl", "enc", "-aes-256-cbc", "-d",
                   "-in", str(source), *options]
        result = subprocess.run(command, input=credential,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ValueError("OpenSSL failed: incorrect factory password, corrupt payload or unavailable cipher/digest")
    return result.stdout


# ---------------------------------------------------------------------
# FIXED-KEY AES-256-CBC
# ---------------------------------------------------------------------

def validate_fixed_key_settings(data=None, *, context) -> None:
    """Validate the fixed AES key and IV without encrypting payloads."""
    settings = context["codec"].get("encryption_settings")
    if not isinstance(settings, dict) or any(settings.get(name) is None for name in ("key_hex", "iv_hex")):
        raise ValueError("Fixed-key encryption requires key_hex and iv_hex")
    if len(bytes.fromhex(settings["key_hex"])) != 32 or len(bytes.fromhex(settings["iv_hex"])) != 16:
        raise ValueError("AES-256-CBC requires a 32-byte key and 16-byte IV")


def encrypt_aes_256_cbc_fixed_key(data: bytes, *, context: dict) -> bytes:
    """Encrypt aligned AES blocks using the configured fixed key and IV."""
    validate_fixed_key_settings(context=context)
    settings = context["codec"]["encryption_settings"]
    key, iv = bytes.fromhex(settings["key_hex"]), bytes.fromhex(settings["iv_hex"])
    if not data or len(data) % 16:
        raise ValueError("AES-256-CBC input must contain complete 16-byte blocks")
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    operation = cipher.encryptor()
    return operation.update(data) + operation.finalize()


def decrypt_aes_256_cbc_fixed_key(data: bytes, *, context: dict) -> bytes:
    """Decrypt aligned AES blocks using the configured fixed key and IV."""
    validate_fixed_key_settings(context=context)
    settings = context["codec"]["encryption_settings"]
    key, iv = bytes.fromhex(settings["key_hex"]), bytes.fromhex(settings["iv_hex"])
    if not data or len(data) % 16:
        raise ValueError("AES-256-CBC input must contain complete 16-byte blocks")
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    operation = cipher.decryptor()
    return operation.update(data) + operation.finalize()


# ---------------------------------------------------------------------
# TECHNICOLOR ENCRYPTION
# ---------------------------------------------------------------------

def validate_device_key_settings(data=None, *, context) -> None:
    """Require device credentials during input validation."""
    if context.get("check_inputs") and not context.get("device_key"):
        raise ValueError("THENC device key unavailable or empty")


def encrypt_technicolor_thenc(data: bytes, *, context: dict) -> bytes:
    """Reject THENC encryption until key handling and signing exist."""
    device_key = context.get("device_key")
    if not device_key:
        raise ValueError("THENC device key unavailable or empty; an export password is not a device key")
    raise ValueError("THENC device key handling and signature signing are not established; encryption unavailable")


def decrypt_technicolor_thenc(data: bytes, *, context: dict) -> bytes:
    """Reject THENC decryption until key derivation and verification exist."""
    device_key = context.get("device_key")
    if not device_key:
        raise ValueError("THENC device key unavailable or empty; an export password is not a device key")
    if device_key is None:
        raise ValueError("THENC device key unavailable: credential loading is not established; an export password is not a device key")
    raise ValueError("THENC device key derivation and signature verification are not established; decryption unavailable")


# ---------------------------------------------------------------------
# RSA-MD5 SIGNATURES
# ---------------------------------------------------------------------

def _rsa_md5_parameters(backup_format: dict, parameters: dict) -> tuple[int, int]:
    """Validate the RSA public key and signature block size before using them."""
    if not isinstance(parameters, dict) or any(parameters.get(name) is None for name in ("modulus_hex", "exponent")):
        raise ValueError("RSA/MD5 requires modulus_hex and exponent")
    length = backup_format.get("signature_length")
    modulus = int(parameters["modulus_hex"], 16)
    exponent = parameters["exponent"]
    if not isinstance(length, int) or not 64 <= length <= 1024 or length != (modulus.bit_length() + 7) // 8 or modulus % 2 != 1:
        raise ValueError("Signature length does not match a supported RSA modulus")
    if not isinstance(exponent, int) or not 3 <= exponent <= 4294967295 or exponent % 2 != 1:
        raise ValueError("Invalid RSA public exponent")
    return length, modulus


def validate_rsa_md5_settings(data=None, *, context) -> None:
    """Validate the public RSA parameters without verifying a payload."""
    _rsa_md5_parameters(context["codec"], context["codec"]["signature"])


def validate_rsa_md5_signing_settings(data=None, *, context) -> None:
    """Validate public parameters and require a private key for encoding inputs."""
    codec = context["codec"]
    parameters = {**codec["signature"], **(context.get("signing") or {})}
    length, modulus = _rsa_md5_parameters(codec, parameters)
    if not context.get("check_inputs"):
        return
    private_hex = parameters.get("private_exponent_hex")
    if private_hex is None:
        raise ValueError("RSA/MD5 signing requires signature.private_exponent_hex")
    if not 1 < int(private_hex, 16) < modulus:
        raise ValueError("signature.private_exponent_hex: must be between 1 and the modulus")


def verify_rsa_md5_signature(signed: bytes, *, context: dict) -> bytes:
    """Verify the entire configured RSA/MD5 PKCS#1 v1.5 signature block."""
    backup_format = context["codec"]
    parameters, signature = backup_format["signature"], context["signature"]
    length, modulus = _rsa_md5_parameters(backup_format, parameters)
    value = int.from_bytes(signature, "big")
    if not 0 < value < modulus:
        raise ValueError("RSA/MD5 signature verification failed")
    recovered = pow(value, parameters["exponent"], modulus).to_bytes(length, "big")
    # Full PKCS#1 v1.5 block: DER MD5 DigestInfo followed by the binary MD5 digest.
    digest_info = bytes.fromhex("3020300c06082a864886f70d020505000410") + hashlib.md5(signed).digest()
    padding_length = length - len(digest_info) - 3
    expected = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    if padding_length < 8 or not hmac.compare_digest(recovered, expected):
        raise ValueError("RSA/MD5 signature verification failed")
    return signed


def encode_rsa_md5_configuration(xml: bytes, *, context: dict) -> bytes:
    """Sign a PKCS#1 v1.5 MD5 block and retain the verified signature metadata."""
    validate_xml_declaration(xml, context["codec"])
    if b"\x00" in xml:
        raise ValueError("XML configuration contains an embedded null byte")
    signed = xml + b"\x00"
    backup_format = context["codec"]
    parameters = {**backup_format["signature"], **(context.get("signing") or {})}
    validate_rsa_md5_signing_settings(context=dict(context, check_inputs=True))
    length, modulus = _rsa_md5_parameters(backup_format, parameters)
    private = int(parameters["private_exponent_hex"], 16)
    digest_info = bytes.fromhex("3020300c06082a864886f70d020505000410") + hashlib.md5(signed).digest()
    padding_length = length - len(digest_info) - 3
    block = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    signature = pow(int.from_bytes(block, "big"), private, modulus).to_bytes(length, "big")
    try:
        verify_rsa_md5_signature(signed, context={"codec": {**backup_format, "signature": parameters}, "signature": signature})
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Generated RSA/MD5 signature failed verification; check signing parameters") from None
    context["signature"] = signature
    return signed


def decode_rsa_md5_configuration(signed: bytes, *, context: dict) -> bytes:
    """Remove the signed null terminator and preserve authenticated XML bytes unchanged."""
    specs = context["codec"]
    verify_rsa_md5_signature(signed, context=context)
    if not signed.endswith(b"\x00"):
        raise ValueError("Signed configuration is missing its trailing null byte")
    xml = signed[:-1]
    if not xml.startswith(specs["preamble"].encode("ascii")) or b"\x00" in xml:
        raise ValueError("Invalid XML configuration declaration or embedded null byte")
    try:
        ET.fromstring(xml)
    except ET.ParseError as exc:
        print(f"[WARN] Signature verified, but authenticated configuration is not well-formed XML: {exc}. Original bytes are preserved.")
    context["configuration_payload"] = True
    if context.get("edit"):
        context["files"] = {context["edit"]["configuration_file"]: xml}
    return xml


# ---------------------------------------------------------------------
# AES-128-CBC FIELD ENCRYPTION
# ---------------------------------------------------------------------

def validate_field_encryption_settings(*, key_hex: str, iv_hex: str) -> None:
    """Validate field AES key material without encrypting or decrypting values."""
    if not isinstance(key_hex, str) or not isinstance(iv_hex, str):
        raise ValueError("Field encryption requires key_hex and iv_hex")
    key = bytes.fromhex(key_hex)
    iv = bytes.fromhex(iv_hex)
    if len(key) != 16 or len(iv) != 16:
        raise ValueError("AES-128-CBC fields require a 16-byte key and IV")


def encrypt_aes_128_cbc_field(value: str, *, key_hex: str, iv_hex: str) -> str:
    """Encrypt UTF-8 with zero padding and Base64, checking the field round trip."""
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("Field plaintext must be a string without null characters")
    validate_field_encryption_settings(key_hex=key_hex, iv_hex=iv_hex)
    key, iv = bytes.fromhex(key_hex), bytes.fromhex(iv_hex)
    try:
        data = value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Field plaintext is not valid UTF-8") from None
    # Zero padding adds only the bytes needed, with one block for an empty value.
    data += b"\x00" * ((-len(data) % 16) if data else 16)
    operation = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encoded = base64.b64encode(operation.update(data) + operation.finalize()).decode("ascii")
    if not hmac.compare_digest(decrypt_aes_128_cbc_field(encoded, key_hex=key_hex, iv_hex=iv_hex).encode("utf-8"), value.encode("utf-8")):
        raise ValueError("Encrypted field failed decryption verification")
    return encoded


def decrypt_aes_128_cbc_field(value: str, *, key_hex: str, iv_hex: str) -> str:
    """Decrypt a Base64-encoded, zero-padded AES-128-CBC field without logging its value."""
    validate_field_encryption_settings(key_hex=key_hex, iv_hex=iv_hex)
    key, iv = bytes.fromhex(key_hex), bytes.fromhex(iv_hex)
    if not isinstance(value, str):
        raise ValueError("Field ciphertext must be a Base64 string")
    try:
        ciphertext = base64.b64decode(value, validate=True)
    except ValueError:
        raise ValueError("Invalid Base64 field ciphertext") from None
    if not ciphertext or len(ciphertext) % 16:
        raise ValueError("Field ciphertext must contain complete 16-byte AES blocks")
    operation = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plaintext = (operation.update(ciphertext) + operation.finalize()).rstrip(b"\x00")
    if b"\x00" in plaintext:
        raise ValueError("Invalid zero padding in decrypted field")
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Decrypted field is not valid UTF-8") from None


# ---------------------------------------------------------------------
# CHECKSUMS
# ---------------------------------------------------------------------

def calculate_payload_checksum(data: bytes, algorithm: str) -> bytes:
    """Calculate the lowercase ASCII hexadecimal checksum used by backup wrappers."""
    return hashlib.new(algorithm, data).hexdigest().encode("ascii")
