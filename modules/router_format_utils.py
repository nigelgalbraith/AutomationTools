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
        path = Path(member.name)
        if not member.name or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe archive path: {member.name}")
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


def encode_base64_payload(data: bytes, *, context: dict) -> bytes:
    """Produce Base64 with the configured wrapping and trailing newline."""
    backup_format = context["codec"]
    validate_base64_settings(context=context)
    width = backup_format["payload_line_length"]
    encoded = base64.b64encode(data)
    return b"".join(encoded[i:i + width] + b"\n" for i in range(0, len(encoded), width))


def decode_base64_payload(data: bytes, *, context: dict) -> bytes:
    """Decode the transport separately from encryption and wrapper handling."""
    return base64.b64decode(data.replace(b"\n", b""), validate=True)


def validate_line_wrapper_settings(fmt=None, checksum_functions=None, *, context=None) -> None:
    """Validate this wrapper's line layout, preserved header and checksum."""
    if context is not None:
        fmt, checksum_functions = context["codec"], context["checksum_functions"]
    required = ("header_lines", "preserve_header", "payload_line_length", "newline", "checksum",
                "checksum_after_payload_lines", "checksum_prefix_bytes", "trailer_character", "trailer_repeat")
    for name in required:
        if fmt.get(name) is None:
            raise ValueError(f"Required line-wrapper setting missing: {name}")
    for name in ("header_lines", "checksum_after_payload_lines", "checksum_prefix_bytes", "trailer_repeat"):
        if not isinstance(fmt[name], int) or fmt[name] < 0:
            raise ValueError(f"Invalid line-wrapper setting: {name}")
    if not isinstance(fmt["payload_line_length"], int) or fmt["payload_line_length"] <= 0:
        raise ValueError("Invalid line-wrapper payload width")
    if fmt["newline"] != "\n":
        raise ValueError("Line-wrapper requires LF newlines")
    if fmt["header_lines"] and not fmt["preserve_header"]:
        raise ValueError("A nonempty wrapper header must be preserved")
    if checksum_functions is not None and not callable(checksum_functions.get(fmt["checksum"])):
        raise ValueError(f"Unsupported wrapper checksum: {fmt['checksum']}")


def split_line_wrapper(data: bytes, *, context: dict) -> bytes:
    """Verify wrapper layout and checksum; retain its header and return encoded bytes."""
    backup_format = context["codec"]
    fmt = backup_format
    validate_line_wrapper_settings(fmt, context["checksum_functions"])
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
    wrapper = {"header": b"".join(lines[:count]), "encoded": encoded,
               "checksum": special[prefix_length:]}
    method = fmt["checksum"]
    expected = context["checksum_functions"][method](encoded, method)
    if wrapper["checksum"] != expected:
        raise ValueError("Backup encrypted payload checksum mismatch")
    if encode_base64_payload(decode_base64_payload(encoded, context=context), context=context) != encoded:
        raise ValueError("Invalid encoded payload line layout")
    context["header"] = wrapper["header"]
    return encoded


def prepare_line_wrapper(encoded: bytes, *, context: dict) -> bytes:
    """Rebuild and verify the wrapper with its checksum and a fresh random prefix."""
    header, backup_format = context.get("header", b""), context["codec"]
    fmt = backup_format
    validate_line_wrapper_settings(fmt, context["checksum_functions"])
    lines = encoded.splitlines(keepends=True)
    position = fmt["checksum_after_payload_lines"]
    if len(lines) < position:
        raise ValueError("Payload too short for configured checksum location")
    if len(header.splitlines(keepends=True)) != fmt["header_lines"]:
        raise ValueError("Original header does not match configured layout")
    prefix = base64.b64encode(os.urandom(fmt["checksum_prefix_bytes"]))
    before = header + b"".join(lines[:position]) + prefix
    after = b"\n" + b"".join(lines[position:]) + wrapper_trailer(fmt)
    method = fmt["checksum"]
    checksum = context["checksum_functions"][method](encoded, method)
    result = before + checksum + after
    if split_line_wrapper(result, context=context) != encoded:
        raise ValueError("Rebuilt wrapper failed verification")
    return result


def parse_technicolor_wrapper(data: bytes, *, context: dict) -> bytes:
    """Split THENC header, IV, ciphertext and signature; do not authenticate."""
    backup_format = context["codec"]
    hardware, firmware = context["hardware"], context["firmware"]
    fmt = backup_format
    validate_technicolor_settings(context=context)
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
    wrapper = {"header": header + separator, "encoded": payload, "encrypted": payload[iv_length:-signature_length],
            "checksum": b"", "iv": payload[:iv_length], "signature": payload[-signature_length:],
            "cipher_key_id": values["CIPHERKEY"], "signature_key_id": values["SIGNATUREKEY"]}

    context.update(wrapper)
    return wrapper["encrypted"]


def rebuild_technicolor_wrapper(encoded: bytes, *, context: dict) -> bytes:
    """Never generate an unauthenticated device-key backup."""
    raise ValueError("THENC rebuilding unavailable: device key and signature signing are not established")


def parse_encrypted_configuration(data: bytes, *, context: dict) -> bytes:
    """Check the block boundaries of a whole-file encrypted configuration."""
    if not data or len(data) % 16:
        raise ValueError("Invalid encrypted configuration block length")
    context["header"] = b""
    return data


def decode_xml_configuration(signed: bytes, *, context: dict, verifier=None) -> bytes:
    """Remove the signed null terminator and preserve authenticated XML bytes unchanged."""
    specs = context["codec"]
    if verifier is None:
        raise ValueError("Signed XML requires a registered signature verifier")
    verifier(signed, context=context)
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


def encode_signed_xml_configuration(xml: bytes, *, context: dict, signer) -> bytes:
    """Validate XML, frame its signed bytes, and retain the generated signature."""
    validate_xml_declaration(xml, context["codec"])
    if b"\x00" in xml:
        raise ValueError("XML configuration contains an embedded null byte")
    return signer(xml + b"\x00", context=context)


def validate_xml_declaration(data: bytes, specs=None, *, context=None) -> None:
    """Require the declaration configured for a saved XML configuration."""
    if context is not None:
        specs = context["codec"]
    if not data.startswith(specs["preamble"].encode("ascii")):
        raise ValueError("Missing XML declaration")


def validate_signed_configuration_settings(fmt=None, *, context=None) -> None:
    """Require signature selection and the signed XML payload layout."""
    if context is not None:
        fmt = context["codec"]
    if not (fmt.get("signature") or {}).get("algorithm"):
        raise ValueError("Signed configuration requires a signature verification algorithm")
    if not isinstance(fmt.get("signature_length"), int) or fmt["signature_length"] <= 0:
        raise ValueError("Signed configuration requires a positive signature_length")
    if not (fmt.get("preamble") or "").startswith("<?xml"):
        raise ValueError("Signed configuration requires an XML preamble")


def unpack_signed_configuration(data: bytes, *, context: dict) -> bytes:
    """Decompress padded configuration bytes and split the unverified signature."""
    backup_format = context["codec"]
    validate_signed_configuration_settings(backup_format)
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
    context["signature"] = signature
    return signed


def pack_signed_configuration(signed: bytes, *, context: dict) -> bytes:
    """Compress signed bytes and their signature with the established AES zero padding."""
    validate_signed_configuration_settings(context["codec"])
    signature = context["signature"]
    compressed = zlib.compress(signed + signature, 9)
    return compressed + b"\x00" * (16 - len(compressed) % 16)


def read_tar_files(data: bytes, *, context: dict) -> bytes:
    """Read validated TAR members without extracting paths."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        files = {str(Path(member.name)): archive.extractfile(member).read()
                 for member in validate_archive(archive) if member.isfile()}
    context["files"] = files
    return data


def validate_tar_configuration(data: bytes, *, context=None) -> None:
    """Check decoded TAR member safety without extracting or rewriting data."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        validate_archive(archive)


def extract_tar_archive(archive_path: Path | bytes, output: Path, *, context=None) -> None:
    """Extract validated TAR members with a self-contained atomic install."""
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError(f"Unsafe extraction directory symlink: {output}")
    if output.exists() and not output.is_dir():
        raise NotADirectoryError(f"Expected extraction directory: {output}")
    source = {"fileobj": io.BytesIO(archive_path)} if isinstance(archive_path, bytes) else {"name": archive_path}
    with tarfile.open(mode="r:gz", **source) as archive:
        members = validate_archive(archive)
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        work = Path(tempfile.mkdtemp(dir=output.parent, prefix=f".{output.name}."))
        staged, backup = work / "contents", work / "original"
        staged.mkdir(mode=0o700)
        installed = False
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
            if output.exists():
                os.replace(output, backup)
            try:
                os.replace(staged, output)
                installed = True
            except BaseException:
                if backup.exists():
                    os.replace(backup, output)
                raise
        finally:
            if installed or not backup.exists():
                shutil.rmtree(work)
            else:
                print(f"Original extraction retained at: {backup}")


def rebuild_tar_archive(original_archive: bytes, *, context: dict) -> bytes:
    """Rebuild the original tar.gz archive using edited files."""
    edited_dir = context["edited_dir"]
    directory = Path(edited_dir).expanduser()
    if not directory.is_dir():
        raise NotADirectoryError(f"Edited configuration directory not found: {directory}")
    if any(path.is_symlink() for path in (directory, *directory.parents)):
        raise ValueError("Unsafe archive source directory symlink")
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"Unsafe archive source entry: {path}")
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
            context["expected"] = original_archive
            context["changes"] = changes
            return original_archive
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
    rebuilt = buffer.getvalue()
    context["expected"] = rebuilt
    context["changes"] = changes
    return rebuilt


def validate_base64_settings(*, context) -> None:
    """Validate the transport line width without encoding a payload."""
    backup_format = context["codec"]
    width = backup_format.get("payload_line_length")
    if not isinstance(width, int) or width <= 0:
        raise ValueError("Base64 payload_line_length must be a positive integer")


def validate_technicolor_settings(*, context) -> None:
    """Validate THENC identifiers and layout without processing a payload."""
    fmt = context["codec"]
    hardware, firmware = context["hardware"], context["firmware"]
    for name in ("header_lines", "iv_length", "signature_length", "preamble", "backup_version", "header_terminator"):
        if fmt.get(name) is None:
            raise ValueError(f"Required THENC setting missing: {name}")
    if fmt["header_lines"] != 9 or fmt["iv_length"] != 16 or fmt["signature_length"] <= 0:
        raise ValueError("Invalid THENC header, IV or signature layout")
    if not hardware or not firmware:
        raise ValueError("THENC requires hardware and firmware identifiers")
