from __future__ import annotations
import hashlib
import subprocess
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------
# FILE CONSTANTS
# ---------------------------------------------------------------------

OPENSSL_HEADER = b"Salted__"
SUPPORTED_HASHES = ("md5", "sha256", "sha512")


# ---------------------------------------------------------------------
# PASSWORD DERIVATION AND ENCRYPTION
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


def interpret_password_credentials(data: bytes) -> str:
    """Interpret only explicitly selected text-password credentials."""
    try:
        password = data.decode("utf-8").strip()
    except UnicodeError:
        raise ValueError("Password file must contain UTF-8 text") from None
    if not password or any(c in password for c in "\r\n\x00"):
        raise ValueError("Password file is empty or contains invalid control characters")
    return password


def validate_device_key_specs(specs: dict) -> None:
    """Reject legacy password settings for the unverified device-key mechanism."""
    for key in ("password_base", "password_hash", "key_derivation_digest"):
        if specs[key] is not None:
            raise ValueError(f"Non-applicable JSON key must be null: {key}")
    for key in ("salted", "password_required"):
        if specs[key] is not False:
            raise ValueError(f"Missing or invalid JSON key: {key}; device-key requires false")


def load_device_key_credentials(password_path: str | None, model_specs: dict, password_prompt: str = "") -> str | bool:
    """Do not read a configured password file as a binary device key."""
    raise ValueError("THENC device key unavailable: credential loading is not established; an export password is not a device key")


def load_target_device_key_credentials(template_credentials, model_specs: dict, password_prompt: str):
    """Reject destination key selection until authenticated THENC support exists."""
    raise ValueError("THENC destination device key unavailable: an export password is not a device key; signature signing is not established")


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
