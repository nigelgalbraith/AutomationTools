"""Backup transport encoding, wrapper processing and archive operations."""

from __future__ import annotations

import base64
import copy
import io
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import zlib
from modules.router_config_utils import (safe_relative, validate_directory, parse_key_value_fields, normalize_key_value_fields, decode_xml_configuration, validate_xml_declaration)
from modules.router_encryption_utils import calculate_payload_checksum, verify_rsa_md5_signature, sign_rsa_md5_configuration



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


# ---------------------------------------------------------------------
# ARCHIVE OPERATIONS
# ---------------------------------------------------------------------

def validate_archive(archive: tarfile.TarFile) -> list:
    """Validate all entries before any extraction or edited-file reads."""
    members = archive.getmembers()
    seen = {}
    if not members:
        raise ValueError("Empty archive")
    for member in members:
        path = safe_relative(member.name)
        if not (member.isfile() or member.isdir()) or path in seen or (path == Path('.') and not member.isdir()):
            raise ValueError(f"Unsafe or duplicate archive member: {member.name}")
        seen[path] = member
    for path in seen:
        if any(parent in seen and not seen[parent].isdir() for parent in path.parents):
            raise ValueError(f"Conflicting archive paths: {path}")
    return members


def read_tar_files(data: bytes, specs: dict) -> dict:
    """Read validated TAR members without extracting paths."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        return {str(Path(member.name)): archive.extractfile(member).read()
                for member in validate_archive(archive) if member.isfile()}


def replace_router_directory(staged: Path, destination: Path) -> None:
    """Install a prepared directory, restoring the old one if installation fails."""
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError(f"Unsafe destination symlink: {destination}")
    if not destination.exists():
        os.replace(staged, destination)
        return
    if not destination.is_dir():
        raise NotADirectoryError(f"Expected output directory: {destination}")
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=f".{destination.name}.backup.") as backup_dir:
        backup = Path(backup_dir) / "original"
        os.replace(destination, backup)
        try:
            os.replace(staged, destination)
        except BaseException:
            os.replace(backup, destination)
            raise


def extract_tar_archive(archive_path: Path, output: Path, model_specs: dict) -> None:
    """Extract validated TAR files using staged directory replacement."""
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = validate_archive(archive)
        if not members:
            raise ValueError("Decoded archive is empty")
        for member in members:
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsafe archive member: {member.name}")
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        staged = Path(tempfile.mkdtemp(dir=output.parent, prefix=f".{output.name}."))
        try:
            for member in members:
                destination = staged / member.name
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError(f"Cannot extract: {member.name}")
                    with stream, destination.open("xb") as target:
                        shutil.copyfileobj(stream, target)
                    destination.chmod(0o600)
            replace_router_directory(staged, output)
        finally:
            if staged.exists():
                shutil.rmtree(staged)


def rebuild_tar_archive(original_archive: bytes, edited_dir: str, model_specs: dict) -> tuple[bytes, list[str]]:
    """Rebuild the original tar.gz archive using edited files."""
    directory = Path(edited_dir).expanduser()
    if not directory.is_dir():
        raise NotADirectoryError(f"Edited configuration directory not found: {directory}")
    validate_directory(directory)
    changes = []
    with tarfile.open(fileobj=io.BytesIO(original_archive), mode="r:gz") as source:
        members = validate_archive(source)
        expected = {str(Path(m.name)) for m in members if m.isfile()}
        actual = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
        if actual != expected:
            raise ValueError("Edited files do not match the original archive")
        contents = []
        for member in members:
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsafe archive member: {member.name}")
            if not member.isfile():
                contents.append(None)
                continue
            stream = source.extractfile(member)
            if stream is None:
                raise ValueError(f"Unreadable archive member: {member.name}")
            with stream:
                original_content = stream.read()
            edited_file = directory / relative
            if not edited_file.is_file() or edited_file.is_symlink():
                raise ValueError(f"Missing or unsafe edited file: {edited_file}")
            edited_content = edited_file.read_bytes()
            if edited_content != original_content:
                changes.append(member.name)
            contents.append(edited_content)
        if not changes:
            return original_archive, changes
        buffer = io.BytesIO()
        archive_format = tarfile.PAX_FORMAT if any(member.pax_headers for member in members) else tarfile.GNU_FORMAT
        with tarfile.open(fileobj=buffer, mode="w:gz", format=archive_format) as target:
            for member, content in zip(members, contents):
                entry = copy.deepcopy(member)
                entry.pax_headers.pop("size", None)
                if entry.isfile():
                    entry.size = len(content)
                    target.addfile(entry, io.BytesIO(content))
                else:
                    target.addfile(entry)
    return buffer.getvalue(), changes


def validate_tar_gzip_config(decoded: bytes, model_specs: dict) -> None:
    """Validate TAR/GZIP contents and the declared key-value configuration."""
    files = read_tar_files(decoded, model_specs)
    configured = str(safe_relative(model_specs["config_fields"]["file"]))
    if configured not in files:
        raise ValueError("Configured file missing from archive")
    parse_key_value_fields(files[configured].decode("utf-8"), model_specs)


def validate_edited_fields(original_archive: bytes, directory: Path, specs: dict) -> None:
    """Match every original byte except values explicitly declared editable."""
    config_path = safe_relative(specs["config_fields"]["file"])
    found = False
    files = read_tar_files(original_archive, specs)
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


def parse_encrypted_configuration(data: bytes, model_specs: dict) -> dict:
    """Check the block boundaries of a whole-file encrypted configuration."""
    if not data or len(data) % 16:
        raise ValueError("Invalid encrypted configuration block length")
    return {"header": b"", "encoded": data, "encrypted": data, "checksum": b""}


def decode_signed_configuration(data: bytes, specs: dict) -> bytes:
    """Decompress a signed single-file configuration and verify the complete RSA block."""
    try:
        decompressor = zlib.decompressobj()
        # Bound authenticated output before allocating an arbitrarily large decompressed stream.
        decoded = decompressor.decompress(data, 64 * 1024 * 1024 + 1)
    except zlib.error:
        raise ValueError("Invalid zlib configuration: incorrect key/IV or corrupt backup") from None
    if len(decoded) > 64 * 1024 * 1024 or not decompressor.eof:
        raise ValueError("Truncated or oversized zlib configuration")
    trailing = decompressor.unused_data
    if len(trailing) > 16 or any(trailing):
        raise ValueError("Invalid trailing AES zero padding")
    length = specs["backup_format"]["signature_length"]
    if len(decoded) <= length:
        raise ValueError("Missing signed configuration or RSA signature")
    signed, signature = decoded[:-length], decoded[-length:]
    verify_rsa_md5_signature(signed, signature, specs)
    return decode_xml_configuration(signed, specs)


def extract_xml_configuration(archive_path: Path, output: Path, model_specs: dict) -> None:
    """Stage the preserved XML bytes as a single configuration file and replace the destination."""
    decoded = archive_path.read_bytes()
    validate_xml_declaration(decoded, model_specs)
    relative = safe_relative(model_specs["config_fields"]["file"])
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=f".{output.name}.") as directory:
        prepared = Path(directory) / "configuration"
        target = prepared / relative
        target.parent.mkdir(parents=True, mode=0o700)
        target.write_bytes(decoded)
        target.chmod(0o600)
        replace_router_directory(prepared, output)


def encode_signed_configuration(xml: bytes, specs: dict) -> bytes:
    """Build signed zlib data with AES zero padding, preserving every XML byte."""
    validate_xml_declaration(xml, specs)
    if b"\x00" in xml:
        raise ValueError("XML configuration contains an embedded null byte")
    signed = xml + b"\x00"
    signature = sign_rsa_md5_configuration(signed, specs)
    compressed = zlib.compress(signed + signature, 9)
    padded = compressed + b"\x00" * (16 - len(compressed) % 16)
    if decode_signed_configuration(padded, specs) != xml:
        raise ValueError("Rebuilt signed configuration failed verification")
    return padded
