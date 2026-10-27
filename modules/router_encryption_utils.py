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

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------

OPENSSL_HEADER = b"Salted__"


# ---------------------------------------------------------------------
# WORKFLOW
# ---------------------------------------------------------------------

def interpret_password_credentials(data: bytes) -> str:
    """Interpret only explicitly selected text-password credentials."""
    try:
        password = data.decode("utf-8").strip()
    except UnicodeError:
        raise ValueError("Password file must contain UTF-8 text") from None
    if not password or any(c in password for c in "\r\n\x00"):
        raise ValueError("Password file is empty or contains invalid control characters")
    return password


def crypt_aes_256_cbc(data: bytes, password: str, decrypt: bool, *, salted: bool, password_required: bool, password_base: str, password_hash: str, key_derivation_digest: str) -> bytes:
    """Run the established AES cipher with explicit OpenSSL legacy derivation."""
    if decrypt and salted and (not data.startswith(OPENSSL_HEADER) or len(data) < 32):
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
        command = ["openssl", "enc", "-aes-256-cbc", "-d" if decrypt else "-e",
                   "-in", str(source), *options]
        result = subprocess.run(command, input=credential,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ValueError("OpenSSL failed: incorrect factory password, corrupt payload or unavailable cipher/digest")
    return result.stdout


def crypt_aes_256_cbc_fixed_key(data: bytes, password: str, decrypt: bool, *, encryption_settings: dict) -> bytes:
    """Encrypt/decrypt aligned AES blocks using fixed key/IV values from the specification."""
    if not data or len(data) % 16:
        raise ValueError("AES-256-CBC input must contain complete 16-byte blocks")
    settings = encryption_settings
    key = bytes.fromhex(settings["key_hex"])
    iv = bytes.fromhex(settings["iv_hex"])
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    operation = cipher.decryptor() if decrypt else cipher.encryptor()
    return operation.update(data) + operation.finalize()


def crypt_technicolor_thenc(data: bytes, password: str, decrypt: bool, device_key=None) -> bytes:
    """Reject THENC operations until device-key handling and authentication exist."""
    if not decrypt:
        raise ValueError("THENC device key handling and signature signing are not established; encryption unavailable")
    if device_key is None:
        raise ValueError("THENC device key unavailable: credential loading is not established; an export password is not a device key")
    raise ValueError("THENC device key derivation and signature verification are not established; decryption unavailable")


def calculate_payload_checksum(data: bytes, algorithm: str) -> bytes:
    """Calculate the lowercase ASCII hexadecimal checksum used by backup wrappers."""
    return hashlib.new(algorithm, data).hexdigest().encode("ascii")


def verify_rsa_md5_signature(signed: bytes, signature: bytes, backup_format: dict, parameters: dict) -> None:
    """Verify the entire configured RSA/MD5 PKCS#1 v1.5 signature block."""
    length = backup_format["signature_length"]
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


def sign_rsa_md5_configuration(signed: bytes, backup_format: dict, parameters: dict) -> bytes:
    """Sign a PKCS#1 v1.5 MD5 block using JSON parameters, then verify it."""
    length = backup_format["signature_length"]
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
        verify_rsa_md5_signature(signed, signature, backup_format, parameters)
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Generated RSA/MD5 signature failed verification; check signing parameters") from None
    return signature


def decrypt_aes_128_cbc_field(value: str, *, key_hex: str, iv_hex: str) -> str:
    """Decrypt a Base64-encoded, zero-padded AES-128-CBC field without logging its value."""
    key = bytes.fromhex(key_hex)
    iv = bytes.fromhex(iv_hex)

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


def encrypt_aes_128_cbc_field(value: str, *, key_hex: str, iv_hex: str) -> str:
    """Encrypt UTF-8 with zero padding and Base64, checking the field round trip."""
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("Field plaintext must be a string without null characters")
    key = bytes.fromhex(key_hex)
    iv = bytes.fromhex(iv_hex)

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
