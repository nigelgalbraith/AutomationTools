from __future__ import annotations

import os
import hashlib
import base64
import hmac
import subprocess
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------
# FILE CONSTANTS
# ---------------------------------------------------------------------

OPENSSL_HEADER = b"Salted__"


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def derive_router_passphrase(password: str, model_specs: dict) -> str:
    """Hash the factory password independently of OpenSSL key derivation."""
    if not isinstance(password, str) or (model_specs["password_required"] and not password):
        raise ValueError("Factory Wi-Fi password is required")
    algorithm = model_specs["password_hash"]
    if algorithm == "none":
        hashed = password
    else:
        hashed = hashlib.new(algorithm, password.encode("utf-8")).hexdigest()
    passphrase = model_specs["password_base"] + hashed
    if any(c in passphrase for c in "\r\n\x00"):
        raise ValueError("Passphrase contains unsupported control characters")
    return passphrase


def interpret_password_credentials(data: bytes) -> str:
    """Interpret only explicitly selected text-password credentials."""
    try:
        password = data.decode("utf-8").strip()
    except UnicodeError:
        raise ValueError("Password file must contain UTF-8 text") from None
    if not password or any(c in password for c in "\r\n\x00"):
        raise ValueError("Password file is empty or contains invalid control characters")
    return password

# ---------------------------------------------------------------------
# PRE STEPS
# ---------------------------------------------------------------------

def prepare_legacy_key(data: bytes, password: str, specs: dict, decrypt: bool) -> tuple[list, bytes]:
    """Prepare OpenSSL password derivation arguments and private stdin data."""
    if decrypt and specs["salted"] and (not data.startswith(OPENSSL_HEADER) or len(data) < 32):
        raise ValueError("Missing or corrupt OpenSSL salted header")
    passphrase = derive_router_passphrase(password, specs)
    return (["-salt" if specs["salted"] else "-nosalt", "-md", specs["key_derivation_digest"],
             "-pass", "stdin"], passphrase.encode("utf-8") + b"\n")


def load_device_key_credentials(password_path: str | None, model_specs: dict, password_prompt: str = "") -> str | bool:
    """Do not read a configured password file as a binary device key."""
    raise ValueError("THENC device key unavailable: credential loading is not established; an export password is not a device key")


def load_target_device_key_credentials(template_credentials, model_specs: dict, password_prompt: str):
    """Reject destination key selection until authenticated THENC support exists."""
    raise ValueError("THENC destination device key unavailable: an export password is not a device key; signature signing is not established")

# ---------------------------------------------------------------------
# ENCRYPTION OPERATIONS
# ---------------------------------------------------------------------

def crypt_aes_256_cbc(data: bytes, password: str, model_specs: dict, decrypt: bool, wrapper=None, device_key=None) -> bytes:
    """Run the established AES cipher with explicit OpenSSL legacy derivation."""
    options, credential = prepare_legacy_key(data, password, model_specs, decrypt)
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "payload"
        source.write_bytes(data)
        command = ["openssl", "enc", "-aes-256-cbc", "-d" if decrypt else "-e",
                   "-in", str(source), *options]
        result = subprocess.run(command, input=credential,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ValueError("OpenSSL failed: incorrect factory password, corrupt payload or unavailable cipher/digest")
    return result.stdout


def crypt_technicolor_thenc(data: bytes, password: str, model_specs: dict, decrypt: bool, wrapper=None, device_key=None) -> bytes:
    """Reject THENC operations until device-key handling and authentication exist."""
    if not decrypt:
        raise ValueError("THENC device key handling and signature signing are not established; encryption unavailable")
    if device_key is None:
        raise ValueError("THENC device key unavailable: credential loading is not established; an export password is not a device key")
    raise ValueError("THENC device key derivation and signature verification are not established; decryption unavailable")



# ---------------------------------------------------------------------
# CHECKSUMS AND SIGNATURES
# ---------------------------------------------------------------------

def calculate_payload_checksum(data: bytes, algorithm: str) -> bytes:
    """Calculate the lowercase ASCII hexadecimal checksum used by backup wrappers."""
    return hashlib.new(algorithm, data).hexdigest().encode("ascii")


def crypt_aes_256_cbc_fixed_key(data: bytes, password: str, model_specs: dict, decrypt: bool, wrapper=None, device_key=None) -> bytes:
    """Encrypt/decrypt aligned AES blocks using fixed key/IV values from the specification."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    if not data or len(data) % 16:
        raise ValueError("AES-256-CBC input must contain complete 16-byte blocks")
    settings = model_specs["encryption_settings"]
    key = bytes.fromhex(settings["key_hex"])
    iv = bytes.fromhex(settings["iv_hex"])
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    operation = cipher.decryptor() if decrypt else cipher.encryptor()
    return operation.update(data) + operation.finalize()


def verify_rsa_md5_signature(signed: bytes, signature: bytes, specs: dict) -> None:
    """Verify the entire configured RSA/MD5 PKCS#1 v1.5 signature block."""
    length = specs["backup_format"]["signature_length"]
    parameters = specs["signature"]
    modulus = int(parameters["modulus_hex"], 16)
    if length != (modulus.bit_length() + 7) // 8:
        raise ValueError("backup_format.signature_length: does not match RSA modulus size")
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


def decrypt_aes_128_cbc_field(value: str, settings: dict) -> str:
    """Decrypt a Base64-encoded, zero-padded AES-128-CBC field without logging its value."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    key = bytes.fromhex(settings["key_hex"])
    iv = bytes.fromhex(settings["iv_hex"])

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




def encrypt_aes_128_cbc_field(value: str, settings: dict) -> str:
    """Encrypt UTF-8 with zero padding and Base64, checking the field round trip."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("Field plaintext must be a string without null characters")
    key = bytes.fromhex(settings["key_hex"])
    iv = bytes.fromhex(settings["iv_hex"])

    try:
        data = value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Field plaintext is not valid UTF-8") from None
    # Zero padding adds only the bytes needed, with one block for an empty value.
    data += b"\x00" * ((-len(data) % 16) if data else 16)
    operation = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encoded = base64.b64encode(operation.update(data) + operation.finalize()).decode("ascii")
    if not hmac.compare_digest(decrypt_aes_128_cbc_field(encoded, settings).encode("utf-8"), value.encode("utf-8")):
        raise ValueError("Encrypted field failed decryption verification")
    return encoded


def sign_rsa_md5_configuration(signed: bytes, specs: dict) -> bytes:
    """Sign a PKCS#1 v1.5 MD5 block using JSON parameters, then verify it."""
    parameters = specs["signature"]
    length = specs["backup_format"]["signature_length"]
    modulus = int(parameters["modulus_hex"], 16)
    private_hex = parameters["private_exponent_hex"]
    # A public-key-only specification can decode, but cannot sign new data.
    if private_hex is None:
        raise ValueError("RSA/MD5 signing requires signature.private_exponent_hex")
    private = int(private_hex, 16)
    if not 1 < private < modulus:
        raise ValueError("signature.private_exponent_hex: must be between 1 and the modulus")
    if length != (modulus.bit_length() + 7) // 8:
        raise ValueError("backup_format.signature_length: does not match RSA modulus size")
    digest_info = bytes.fromhex("3020300c06082a864886f70d020505000410") + hashlib.md5(signed).digest()
    padding_length = length - len(digest_info) - 3
    block = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    signature = pow(int.from_bytes(block, "big"), private, modulus).to_bytes(length, "big")
    try:
        verify_rsa_md5_signature(signed, signature, specs)
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Generated RSA/MD5 signature failed verification; check signing parameters") from None
    return signature

# ---------------------------------------------------------------------
# ENCODING AND WRAPPERS
# ---------------------------------------------------------------------

def encode_base64_payload(data: bytes, specs: dict) -> bytes:
    """Produce Base64 with the configured wrapping and trailing newline."""
    encoded = base64.b64encode(data)
    width = specs["backup_format"]["payload_line_length"]
    return b"".join(encoded[i:i + width] + b"\n" for i in range(0, len(encoded), width))


def decode_base64_payload(data: bytes, specs: dict) -> bytes:
    """Decode the transport separately from encryption and wrapper handling."""
    return base64.b64decode(data.replace(b"\n", b""), validate=True)


def encode_router_payload(data: bytes, specs: dict) -> bytes:
    """Encode using the configured transport format."""
    if specs["encoding"] == "base64":
        return encode_base64_payload(data, specs)
    return data


def decode_router_payload(data: bytes, specs: dict) -> bytes:
    """Decode using the configured transport format."""
    if specs["encoding"] == "base64":
        return decode_base64_payload(data, specs)
    return data


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
    expected = calculate_payload_checksum(encoded, checksum["algorithm"])
    if special[prefix_length:] != expected:
        raise ValueError("Backup encrypted payload checksum mismatch")
    encrypted = decode_router_payload(encoded, model_specs)
    if encode_router_payload(encrypted, model_specs) != encoded:
        raise ValueError("Invalid encoded payload line layout")
    return {"header": b"".join(lines[:count]), "encoded": encoded,
            "encrypted": encrypted, "checksum": expected}


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
    special = prefix + calculate_payload_checksum(encoded, checksum["algorithm"]) + b"\n"
    result = header + b"".join(lines[:position]) + special + b"".join(lines[position:]) + wrapper_trailer(fmt)
    parse_line_wrapper(result, specs)
    return result


def parse_encrypted_configuration(data: bytes, model_specs: dict) -> dict:
    """Check the block boundaries of a whole-file encrypted configuration."""
    if not data or len(data) % 16:
        raise ValueError("Invalid encrypted configuration block length")
    return {"header": b"", "encoded": data, "encrypted": data, "checksum": b""}
