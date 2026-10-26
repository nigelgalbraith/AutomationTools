"""Configuration parsing, transformations and path checks using supplied field callbacks."""

from __future__ import annotations

import copy
import io
import os
import shutil
import tarfile
import tempfile

from pathlib import Path
from html import unescape, escape
import re
import xml.etree.ElementTree as ET




# ---------------------------------------------------------------------
# VALIDATION
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


# ---------------------------------------------------------------------
# CONFIGURATION FIELDS
# ---------------------------------------------------------------------

def parse_key_value_fields(contents: str, specs: dict) -> tuple[list, dict]:
    """Parse key-value lines and require unique configured keys."""
    lines = contents.splitlines(keepends=True)
    indices = {}
    for index, line in enumerate(lines):
        if "=" in line and not line.lstrip().startswith(("#", ";")):
            key = line.split("=", 1)[0].strip()
            if key in indices:
                raise ValueError(f"Duplicate configuration key: {key}")
            indices[key] = index
    fields = {}
    for label, key in specs["config_fields"].items():
        if label == "file" or key is None:
            continue
        if key not in indices:
            raise ValueError(f"Missing configuration field: {label} ({key})")
        if any(mapped_key == key for mapped_key, _ in fields.values()):
            raise ValueError("config_fields: duplicate configuration mapping")
        fields[label] = (key, indices[key])
    return lines, fields


def key_value_values(lines: list, fields: dict) -> dict:
    """Read displayed values from key-value lines."""
    return {key: lines[index].split("=", 1)[1].rstrip("\r\n") for key, index in fields.values()}


def update_key_value_fields(lines: list, fields: dict, details: dict) -> list:
    """Replace declared values while preserving whitespace and line endings."""
    for label, value in details.items():
        if label not in fields:
            raise ValueError(f"Unknown router setting: {label}")
        index = fields[label][1]
        line = lines[index]
        prefix, current = line.split("=", 1)
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        current = current[:-len(newline)] if newline else current
        leading = current[:len(current) - len(current.lstrip())]
        trailing = current[len(current.rstrip()):] if current.strip() else ""
        lines[index] = f"{prefix}={leading}{value}{trailing}{newline}"
    return lines


def normalize_key_value_fields(contents: str, specs: dict) -> list:
    """Mask editable values for comparison while retaining all other text."""
    lines, fields = parse_key_value_fields(contents, specs)
    for _, index in fields.values():
        line = lines[index]
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        lines[index] = line.split("=", 1)[0] + "=" + newline
    return lines


def view_key_value_values(contents: str, specs: dict, decrypt_handler=None) -> dict:
    """Read configured key-value fields using their display labels."""
    lines, fields = parse_key_value_fields(contents, specs)
    values = key_value_values(lines, fields)
    return {label: values[key] for label, (key, _) in fields.items()}


def decode_xml_configuration(signed: bytes, specs: dict) -> bytes:
    """Remove the signed null terminator and preserve authenticated XML bytes unchanged."""
    if not signed.endswith(b"\x00"):
        raise ValueError("Signed configuration is missing its trailing null byte")
    xml = signed[:-1]
    if not xml.startswith(specs["backup_format"]["preamble"].encode("ascii")) or b"\x00" in xml:
        raise ValueError("Invalid XML configuration declaration or embedded null byte")
    try:
        ET.fromstring(xml)
    except ET.ParseError as exc:
        print(f"[WARN] Signature verified, but authenticated configuration is not well-formed XML: {exc}. Original bytes are preserved.")
    return xml


def parse_xml_field_selector(selector: str, label: str) -> tuple[str, dict[str, str], str]:
    """Parse schema-checked selectors and reject ambiguous duplicate filters."""
    # CHECK has already enforced the declarative selector grammar.
    path = f"config_fields.{label}"
    parts = selector.split("|")
    filters = {}
    for condition in parts[1:-1]:
        name, separator, value = condition.partition("=")
        if name in filters:
            raise ValueError(f"Invalid XML field selector condition: {path}: {condition!r}")
        filters[name] = value
    return parts[0], filters, parts[-1]


def prepare_xml_selectors(specs: dict) -> dict:
    """Prepare derived selectors after CHECK, before planning or backup processing.

    The parser also rejects duplicate filter names, which a syntax pattern alone
    cannot compare. No derived data is installed until all selectors parse.
    """
    selectors = {}
    if specs["configuration_format"] == "xml":
        for label, selector in specs["config_fields"].items():
            if label != "file" and selector is not None:
                selectors[label] = parse_xml_field_selector(selector, label)
    specs["_xml_selectors"] = selectors
    return selectors


def _xml_tag_matches(contents: str, element: str, start: int = 0):
    """Find only the requested tags, skipping comments/CDATA and respecting quoted >."""
    pattern = (
        r"<!--.*?-->|<!\[CDATA\[.*?\]\]>|"
        rf"<(?P<closing>/?){re.escape(element)}(?=[\s/>])(?P<attributes>(?:[^<>\"']|\"[^\"]*\"|'[^']*')*)>"
    )
    for match in re.finditer(pattern, contents[start:], flags=re.DOTALL):
        if match.group("attributes") is not None:
            yield match


def _xml_attributes(text: str, label: str) -> dict:
    """Read quoted XML attributes and reject duplicates without parsing the document."""
    attrs = {}
    for item in re.finditer(r"(?<!\S)([A-Za-z_][\w.:-]*)\s*=\s*([\"'])(.*?)\2", text, flags=re.DOTALL):
        name, _, value = item.groups()
        if name in attrs:
            raise ValueError(f"Duplicate XML attribute for {label}: {name}")
        attrs[name] = re.sub(r"&(?:amp|lt|gt|apos|quot|#[0-9]+|#x[0-9A-Fa-f]+);", lambda entity: unescape(entity.group()), value)
    return attrs


def xml_field_values(contents: str, specs: dict, decrypt_handler=None) -> dict:
    """Read selected XML attributes, decrypting only registered protected fields."""
    values = {label: selected[2] for label, selected in xml_field_selections(contents, specs).items()}
    settings = specs.get("field_encryption", {})
    algorithm = settings.get("algorithm")
    if algorithm is not None:
        if decrypt_handler is None:
            raise ValueError("A selected field decryption handler is required")
        for label in settings["fields"]:
            if label not in values:
                raise ValueError(f"Encrypted configuration field is unavailable: {label}")
            values[label] = decrypt_handler(values[label], settings)
    return values


def validate_xml_declaration(data: bytes, specs: dict) -> None:
    """Require the declaration configured for a saved XML configuration."""
    if not data.startswith(specs["backup_format"]["preamble"].encode("ascii")):
        raise ValueError("Missing XML declaration")


def xml_field_selections(contents: str, specs: dict) -> dict:
    """Locate unique configured attribute value spans and their decoded stored values."""
    selections = {}
    for label, selector in specs["config_fields"].items():
        if label == "file" or selector is None:
            continue
        element, filters, target = specs["_xml_selectors"][label]
        parents = []
        for match in _xml_tag_matches(contents, element):
            if match.group("closing"):
                continue
            attrs = _xml_attributes(match.group("attributes"), label)
            if all(attrs.get(name) == value for name, value in filters.items()):
                parents.append((match, attrs))
        if len(parents) != 1:
            raise ValueError(f"Expected one XML field for {label}, found {len(parents)}")
        parent, attrs = parents[0]
        selected = parent
        offset = 0
        if "@" in target:
            child, attribute = target.split("@")
            if parent.group().rstrip().endswith("/>"):
                raise ValueError(f"Expected one XML child attribute for {label}, found 0")
            # Bound the child search to this parent's matching end tag, including nesting.
            depth = 1
            end = None
            for boundary in _xml_tag_matches(contents, element, parent.end()):
                if boundary.group("closing"):
                    depth -= 1
                elif not boundary.group().rstrip().endswith("/>"):
                    depth += 1
                if depth == 0:
                    end = parent.end() + boundary.start()
                    break
            if end is None:
                raise ValueError(f"Missing closing XML element for {label}: {element}")
            children = [match for match in _xml_tag_matches(contents[parent.end():end], child) if not match.group("closing")]
            if len(children) != 1:
                raise ValueError(f"Expected one XML child attribute for {label}, found {len(children)}")
            selected = children[0]
            offset = parent.end()
            attrs = _xml_attributes(selected.group("attributes"), label)
        else:
            attribute = target
        if attribute not in attrs:
            raise ValueError(f"Missing XML attribute for {label}: {attribute}")
        value_match = re.search(r"(?<!\S)" + re.escape(attribute) + r"\s*=\s*([\"'])(.*?)\1", selected.group("attributes"), flags=re.DOTALL)
        start, end = value_match.span(2)
        base = offset + selected.start("attributes")
        selections[label] = (base + start, base + end, attrs[attribute])
    return selections


def edit_key_value_values(contents: str, specs: dict, changes: dict, encrypt_handler=None) -> str:
    """Apply the existing key-value edits through the format editor dispatcher."""
    lines, fields = parse_key_value_fields(contents, specs)
    return "".join(update_key_value_fields(lines, fields, changes))


def update_xml_fields(contents: str, specs: dict, changes: dict, encrypt_handler=None) -> str:
    """Replace only uniquely selected attribute value spans, preserving surrounding text."""
    selections = xml_field_selections(contents, specs)
    spans = sorted((start, end) for start, end, _ in selections.values())
    if any(left[1] >= right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError("Overlapping XML field mappings cannot be edited")
    settings = specs.get("field_encryption", {})
    encrypted_fields = settings.get("fields") or []
    replacements = []
    for label, value in changes.items():
        if label not in selections:
            raise ValueError(f"Unknown router setting: {label}")
        if not isinstance(value, str) or any(not (ord(c) in (9, 10, 13) or 32 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF) for c in value):
            raise ValueError(f"Invalid XML attribute value for {label}")
        if label in encrypted_fields:
            if encrypt_handler is None:
                raise ValueError("A selected field encryption handler is required")
            value = encrypt_handler(value, settings)
        encoded = escape(value, quote=True).replace("\r", "&#13;").replace("\n", "&#10;").replace("\t", "&#9;")
        start, end, _ = selections[label]
        replacements.append((start, end, encoded))
    for start, end, encoded in sorted(replacements, reverse=True):
        contents = contents[:start] + encoded + contents[end:]
    return contents


def validate_xml_field_changes(original: str, edited: str, specs: dict, changes: dict, decrypt_handler=None, encrypt_handler=None) -> None:
    """Verify selected plaintext replacements and exact preservation of all other text."""
    if edited != update_xml_fields(original, specs, changes, encrypt_handler):
        raise ValueError("Edited XML differs outside the requested configured field replacements")
    expected = xml_field_values(original, specs, decrypt_handler)
    expected.update(changes)
    actual = xml_field_values(edited, specs, decrypt_handler)
    if actual != expected:
        raise ValueError("Edited XML field verification failed")


def validate_edited_xml(original: bytes, directory: Path, specs: dict, decrypt_handler=None, encrypt_handler=None) -> tuple[bytes, list[str]]:
    """Permit only configured XML field edits relative to the authenticated original."""
    if not directory.is_dir():
        raise NotADirectoryError(f"Edited configuration directory not found: {directory}")
    validate_directory(directory)
    relative = safe_relative(specs["config_fields"]["file"])
    actual = {path.relative_to(directory) for path in directory.rglob("*") if path.is_file()}
    if actual != {relative}:
        raise ValueError("Edited files do not match the original single-file configuration")
    edited = (directory / relative).read_bytes()
    validate_xml_declaration(edited, specs)
    before = xml_field_values(original.decode("utf-8"), specs, decrypt_handler)
    after = xml_field_values(edited.decode("utf-8"), specs, decrypt_handler)
    changes = {label: value for label, value in after.items() if value != before[label]}
    validate_xml_field_changes(original.decode("utf-8"), edited.decode("utf-8"), specs, changes, decrypt_handler, encrypt_handler)
    return edited, [str(relative)] if edited != original else []

# ---------------------------------------------------------------------
# ARCHIVE AND FILESYSTEM OPERATIONS
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
