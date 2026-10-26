from __future__ import annotations
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
SUPPORTED_HASHES = ("md5", "sha256", "sha512")


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
    elif algorithm in SUPPORTED_HASHES:
        hashed = hashlib.new(algorithm, password.encode("utf-8")).hexdigest()
    else:
        raise ValueError(f"Unsupported password_hash: {algorithm}")
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
# VALIDATION
# ---------------------------------------------------------------------

def validate_legacy_key_specs(specs: dict) -> None:
    """Validate text-password derivation without treating passwords as keys."""
    required = {"salted": bool, "password_required": bool, "password_base": str,
                "password_hash": str, "key_derivation_digest": str}
    for key, kind in required.items():
        if type(specs.get(key)) is not kind:
            raise ValueError(f"Missing or invalid legacy key setting: {key}")
    if specs["key_derivation_digest"] not in SUPPORTED_HASHES:
        raise ValueError("Unsupported key_derivation_digest")
    if specs["password_hash"] not in (*SUPPORTED_HASHES, "none"):
        raise ValueError("Unsupported password_hash")
    if any(c in specs["password_base"] for c in "\r\n\x00"):
        raise ValueError("Invalid password_base")


def validate_device_key_specs(specs: dict) -> None:
    """Reject legacy password settings for the unverified device-key mechanism."""
    for key in ("password_base", "password_hash", "key_derivation_digest"):
        if specs[key] is not None:
            raise ValueError(f"Non-applicable JSON key must be null: {key}")
    for key in ("salted", "password_required"):
        if specs[key] is not False:
            raise ValueError(f"Missing or invalid JSON key: {key}; device-key requires false")

# ---------------------------------------------------------------------
# PRE STEPS
# ---------------------------------------------------------------------

def prepare_legacy_key(data: bytes, password: str, specs: dict, decrypt: bool) -> tuple[list, bytes]:
    """Prepare OpenSSL password derivation arguments and private stdin data."""
    if (specs["encryption"], specs["key_derivation"]) != ("aes-256-cbc", "openssl-legacy"):
        raise ValueError("Unsupported encryption mechanism for OpenSSL legacy AES-256-CBC")
    validate_legacy_key_specs(specs)
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
    try:
        settings = model_specs["encryption_settings"]
        key = bytes.fromhex(settings["key_hex"])
        iv = bytes.fromhex(settings["iv_hex"])
    except (ValueError, KeyError, TypeError):
        raise ValueError("Invalid encryption_settings: expected hexadecimal key_hex and iv_hex") from None
    if len(key) != 32 or len(iv) != 16:
        raise ValueError("AES-256-CBC credentials require a 32-byte key and 16-byte IV")
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    operation = cipher.decryptor() if decrypt else cipher.encryptor()
    return operation.update(data) + operation.finalize()


def verify_rsa_md5_signature(signed: bytes, signature: bytes, specs: dict) -> None:
    """Verify the entire configured RSA/MD5 PKCS#1 v1.5 signature block."""
    length = specs["backup_format"]["signature_length"]
    parameters = specs["signature"]
    modulus = int(parameters["modulus_hex"], 16)
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
    try:
        key = bytes.fromhex(settings["key_hex"])
        iv = bytes.fromhex(settings["iv_hex"])
    except (ValueError, KeyError, TypeError):
        raise ValueError("Invalid field_encryption key_hex or iv_hex") from None
    if len(key) != 16 or len(iv) != 16:
        raise ValueError("AES-128-CBC field encryption requires a 16-byte key and 16-byte IV")
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
    try:
        key = bytes.fromhex(settings["key_hex"])
        iv = bytes.fromhex(settings["iv_hex"])
    except (ValueError, KeyError, TypeError):
        raise ValueError("Invalid field_encryption key_hex or iv_hex") from None
    if len(key) != 16 or len(iv) != 16:
        raise ValueError("AES-128-CBC field encryption requires a 16-byte key and 16-byte IV")
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
    try:
        parameters = specs["signature"]
        length = specs["backup_format"]["signature_length"]
        modulus = int(parameters["modulus_hex"], 16)
        private_hex = parameters["private_exponent_hex"]
        if not isinstance(private_hex, str) or not private_hex or any(c not in "0123456789abcdefABCDEF" for c in private_hex):
            raise ValueError
        private = int(private_hex, 16)
        if parameters["algorithm"] != "rsa-md5" or type(length) is not int or length != (modulus.bit_length() + 7) // 8 or not 1 < private < modulus:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid or missing RSA/MD5 signing parameters: signature.private_exponent_hex, modulus or signature length") from None
    digest_info = bytes.fromhex("3020300c06082a864886f70d020505000410") + hashlib.md5(signed).digest()
    padding_length = length - len(digest_info) - 3
    if padding_length < 8:
        raise ValueError("RSA modulus is too short for PKCS#1 v1.5 MD5 signing")
    block = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    signature = pow(int.from_bytes(block, "big"), private, modulus).to_bytes(length, "big")
    try:
        verify_rsa_md5_signature(signed, signature, specs)
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("Generated RSA/MD5 signature failed verification; check signing parameters") from None
    return signature
