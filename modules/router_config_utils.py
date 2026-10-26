"""Configuration parsing, transformations and path checks using supplied field callbacks."""

from __future__ import annotations

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
