"""Portable backup wrappers, transport, archives and signed compression."""


# ---------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
import base64
import copy
import io
import os
import shutil
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zlib



# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def wrapper_trailer(fmt: dict) -> bytes:
    """Construct the configured final line."""
    return (fmt["trailer_character"] * fmt["trailer_repeat"] + fmt["newline"]).encode("ascii")


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


# ---------------------------------------------------------------------
# WORKFLOW
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


def encode_base64_payload(data: bytes, backup_format: dict) -> bytes:
    """Produce Base64 with the configured wrapping and trailing newline."""
    encoded = base64.b64encode(data)
    width = backup_format["payload_line_length"]
    return b"".join(encoded[i:i + width] + b"\n" for i in range(0, len(encoded), width))


def decode_base64_payload(data: bytes) -> bytes:
    """Decode the transport separately from encryption and wrapper handling."""
    return base64.b64decode(data.replace(b"\n", b""), validate=True)


def split_line_wrapper(data: bytes, backup_format: dict) -> dict:
    """Validate wrapper layout and return the stored checksum without authenticating it."""
    fmt = backup_format
    lines = data.splitlines(keepends=True)
    count = fmt["header_lines"]
    position = count + fmt["checksum_after_payload_lines"]
    if len(lines) <= position + 1 or lines[-1] != wrapper_trailer(fmt):
        raise ValueError("Invalid backup wrapper or trailer")
    if any(not line.endswith(b"\n") or b"\r" in line for line in lines):
        raise ValueError("Invalid wrapper newline")
    special = lines[position][:-1]
    prefix_size = fmt["checksum_prefix_bytes"]
    prefix_length = 4 * ((prefix_size + 2) // 3)
    prefix = special[:prefix_length]
    if len(base64.b64decode(prefix, validate=True)) != prefix_size:
        raise ValueError("Invalid checksum random prefix")
    encoded = b"".join(lines[count:position] + lines[position + 1:-1])
    return {"header": b"".join(lines[:count]), "encoded": encoded,
            "checksum": special[prefix_length:]}


def prepare_line_wrapper(encoded: bytes, header: bytes, backup_format: dict) -> tuple[bytes, bytes]:
    """Prepare wrapper bytes before and after the checksum, including its random prefix."""
    fmt = backup_format
    lines = encoded.splitlines(keepends=True)
    position = fmt["checksum_after_payload_lines"]
    if len(lines) < position:
        raise ValueError("Payload too short for configured checksum location")
    if len(header.splitlines(keepends=True)) != fmt["header_lines"]:
        raise ValueError("Original header does not match configured layout")
    prefix = base64.b64encode(os.urandom(fmt["checksum_prefix_bytes"]))
    return (header + b"".join(lines[:position]) + prefix,
            b"\n" + b"".join(lines[position:]) + wrapper_trailer(fmt))


def parse_technicolor_wrapper(data: bytes, backup_format: dict, hardware: str, firmware: str) -> dict:
    """Split THENC header, IV, ciphertext and signature; do not authenticate."""
    fmt = backup_format
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
                "BOARDMNEMONIC": hardware}
    if any(values[k] != v for k, v in expected.items()):
        raise ValueError("THENC header does not match configured values")
    if not (values["BUILDVERSION"] == firmware or
            values["BUILDVERSION"].startswith(firmware + "-")):
        raise ValueError("THENC firmware does not match configured value")
    iv_length, signature_length = fmt["iv_length"], fmt["signature_length"]
    size = len(payload) - iv_length - signature_length
    if size <= 0 or size % 16:
        raise ValueError("Invalid or truncated THENC IV, ciphertext or signature boundaries")
    return {"header": header + separator, "encoded": payload, "encrypted": payload[iv_length:-signature_length],
            "checksum": b"", "iv": payload[:iv_length], "signature": payload[-signature_length:],
            "cipher_key_id": values["CIPHERKEY"], "signature_key_id": values["SIGNATUREKEY"]}


def rebuild_technicolor_wrapper(encoded: bytes, header: bytes, backup_format: dict, hardware: str, firmware: str) -> bytes:
    """Never generate an unauthenticated device-key backup."""
    raise ValueError("THENC rebuilding unavailable: device key and signature signing are not established")


def parse_encrypted_configuration(data: bytes) -> dict:
    """Check the block boundaries of a whole-file encrypted configuration."""
    if not data or len(data) % 16:
        raise ValueError("Invalid encrypted configuration block length")
    return {"header": b"", "encoded": data, "encrypted": data, "checksum": b""}


def decode_xml_configuration(signed: bytes, specs: dict) -> bytes:
    """Remove the signed null terminator and preserve authenticated XML bytes unchanged."""
    if not signed.endswith(b"\x00"):
        raise ValueError("Signed configuration is missing its trailing null byte")
    xml = signed[:-1]
    if not xml.startswith(specs["preamble"].encode("ascii")) or b"\x00" in xml:
        raise ValueError("Invalid XML configuration declaration or embedded null byte")
    try:
        ET.fromstring(xml)
    except ET.ParseError as exc:
        print(f"[WARN] Signature verified, but authenticated configuration is not well-formed XML: {exc}. Original bytes are preserved.")
    return xml


def validate_xml_declaration(data: bytes, specs: dict) -> None:
    """Require the declaration configured for a saved XML configuration."""
    if not data.startswith(specs["preamble"].encode("ascii")):
        raise ValueError("Missing XML declaration")


def unpack_signed_configuration(data: bytes, backup_format: dict) -> tuple[bytes, bytes]:
    """Decompress padded configuration bytes and split the unverified signature."""
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
    length = backup_format["signature_length"]
    if len(decoded) <= length:
        raise ValueError("Missing signed configuration or RSA signature")
    signed, signature = decoded[:-length], decoded[-length:]
    return signed, signature


def pack_signed_configuration(signed: bytes, signature: bytes) -> bytes:
    """Compress signed bytes and their signature with the established AES zero padding."""
    compressed = zlib.compress(signed + signature, 9)
    return compressed + b"\x00" * (16 - len(compressed) % 16)


def read_tar_files(data: bytes) -> dict:
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


def extract_tar_archive(archive_path: Path, output: Path) -> None:
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


def rebuild_tar_archive(original_archive: bytes, edited_dir: str) -> tuple[bytes, list[str]]:
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
