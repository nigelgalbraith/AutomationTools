#!/usr/bin/env python3
"""
display_utils.py

Console formatting, table printing, and interactive prompts for CLI utilities.
"""

from io import StringIO
from contextlib import redirect_stdout
from typing import Dict, Any, Optional
from pathlib import Path
import os
import getpass
import json

# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------

MAX_COL_WIDTH = 60

# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------


def dict_to_lines(d: dict) -> list[str]:
  """Convert a dict into a readable list of lines (keys with nested values indented)"""
  lines: list[str] = []
  for k, v in d.items():
    lines.append(str(k))
    if isinstance(v, dict):
      for sk, sv in v.items():
        lines.append(f"  {sk}: {sv}")
    elif isinstance(v, list):
      lines.extend(f"  - {x}" for x in v)
    else:
      lines.append(f"  {v}")
  return lines


def format_value_lines(val):
  """Return a list of display lines for a value (supports dicts and lists for multi-line cells)"""
  if isinstance(val, dict):
    return dict_to_lines(val)
  if isinstance(val, list):
    out = []
    for v in val:
      if isinstance(v, dict):
        out.extend(dict_to_lines(v))
      else:
        out.append(str(v))
    return out
  return [str(val)]


def value_display_len(v):
  """Return the maximum display line length needed to render a value (including dict/list values)"""
  if isinstance(v, dict):
    return max((len(line) for line in dict_to_lines(v)), default=0)
  if isinstance(v, list):
    max_len = 0
    for x in v:
      if isinstance(x, dict):
        max_len = max(max_len, *(len(l) for l in dict_to_lines(x)))
      else:
        max_len = max(max_len, len(str(x)))
    return max_len
  return len(str(v))


def compute_col_widths(items, field_names, pad=2):
  """Compute padded column widths for dict-table output, capped at MAX_COL_WIDTH"""
  widths = []
  for field in field_names:
    max_len = max(
      value_display_len(item.get(field, "")) for item in items
    ) if items else 0
    width = max(len(field), max_len) + pad
    widths.append(min(width, MAX_COL_WIDTH))
  return widths


def truncate_to_width(s, width):
  """Return `s` truncated to `width` characters using an ellipsis when needed"""
  s = str(s)
  if len(s) > width:
    return s[: max(0, width - 3)] + "..."
  return s


def build_header(label, field_names, col_widths):
  """Print a section header and aligned column headings for a dict-table"""
  print(f"\n{label.upper()}:")
  print(
    "  " + "  ".join(f"{name:<{col_widths[i]}}" for i, name in enumerate(field_names))
  )
  print("  " + "  ".join("-" * w for w in col_widths))


def wrap_in_box(val: Any, title: str | None = None, indent: int = 2, pad: int = 1) -> str:
  """Return a string with `val` wrapped in an ASCII box"""
  lines = format_value_lines(val)
  if title:
    lines.insert(0, f"[ {title} ]")
  content_width = max((len(line) for line in lines), default=0)
  inner_lines = [(" " * pad) + line.ljust(content_width) + (" " * pad) for line in lines]
  inner_width = len(inner_lines[0]) if inner_lines else (pad * 2)
  border = "+" + "-" * inner_width + "+"
  prefix = " " * indent
  out = [prefix + border] + [f"{prefix}|{l}| " for l in inner_lines] + [prefix + border]
  return "\n".join(out)


# ---------------------------------------------------------------------
# DISPLAY / PRINTING
# ---------------------------------------------------------------------


def print_dict_table(items, field_names, label):
  """Print a table for a list of dicts using multi-line cells where needed"""
  if not items:
    print(f"\n{label.upper()}: (None)")
    return
  col_widths = compute_col_widths(items, field_names)
  build_header(label, field_names, col_widths)
  for item in items:
    blocks = []
    for i, field in enumerate(field_names):
      raw_lines = format_value_lines(item.get(field, ""))
      cell_lines = [
        f"{truncate_to_width(line, col_widths[i]):<{col_widths[i]}}"
        for line in raw_lines
      ]
      blocks.append(cell_lines)
    max_lines = max(len(b) for b in blocks)
    for j in range(max_lines):
      row_parts = [
        blocks[i][j] if j < len(blocks[i]) else " " * col_widths[i]
        for i in range(len(field_names))
      ]
      print("  " + "  ".join(row_parts))
  print()
  return True


def format_status_summary(
  status_dict: Dict[str, Any],
  label: str = "Item",
  count_keys: Optional[list] = None,
  labels: Optional[Dict[Any, str]] = None
) -> str:
  """
  Return a formatted status table + counts summary for a dict of {item: status}.

  Example:
    print(format_status_summary({"curl": True, "wget": False}, label="Package"))
  """
  labels = labels or {True: "INSTALLED", False: "NOT INSTALLED"}
  non_spacer_items = [(k, v) for k, v in status_dict.items() if str(k).strip() != ""]
  max_item_len = max([len(label)] + [len(str(item)) for item, _ in non_spacer_items], default=len(label))
  col_width = max_item_len + 4
  lines: list[str] = []
  title = f"{label} Status Summary"
  lines.append(f"\n{title}\n" + "-" * len(title))
  lines.append(f"{label:<{col_width}}Status")
  lines.append(f"{'-' * len(label):<{col_width}}------")
  for item, status in status_dict.items():
    if str(item).strip() == "":
      lines.append("")
      continue
    display_status = labels.get(status, str(status))
    lines.append(f"{item:<{col_width}}{display_status}")
  counts: Dict[str, int] = {}
  for _, status in non_spacer_items:
    display_status = labels.get(status, str(status))
    counts[display_status] = counts.get(display_status, 0) + 1
  lines.append("\nSummary:\n--------")
  display_keys = count_keys if count_keys else sorted(counts.keys())
  for key in display_keys:
    lines.append(f"{key:<13}: {counts.get(key, 0)}")
  lines.append(f"Total        : {sum(counts.values())}")
  return "\n".join(lines)


def display_example(example: Any) -> None:
  """Print the EXAMPLE section exactly as stored in the config doc JSON"""
  print("\nEXAMPLE")
  print("-------")
  if example is None:
    print("[WARN] No EXAMPLE section found.")
    return
  print(json.dumps(example, indent=2, ensure_ascii=False))


def display_description(description: dict[str, Any]) -> None:
  """Print DESCRIPTION as a collapsed dot-path hierarchy"""
  print("\nDESCRIPTION")
  print("-----------")
  if not isinstance(description, dict):
    print("[ERROR] DESCRIPTION is not a dict.")
    return
  DESC_KEY = "__DESC__"
  tree: dict[str, Any] = {}
  for key, text in description.items():
    if not isinstance(key, str):
      continue
    parts = key.split(".")
    node = tree
    for part in parts:
      node = node.setdefault(part, {})
    node[DESC_KEY] = str(text)
  stack: list[tuple[dict[str, Any], list[str], int, int, bool]] = [
    (tree, sorted(tree.keys()), 0, 0, False)
  ]
  while stack:
    node, keys, idx, depth, printed_desc = stack[-1]
    if not printed_desc and DESC_KEY in node:
      stack[-1] = (node, keys, idx, depth, True)
      print(f"{'  ' * (depth + 1)}{node[DESC_KEY]}")
      continue
    if idx >= len(keys):
      stack.pop()
      continue
    k = keys[idx]
    stack[-1] = (node, keys, idx + 1, depth, printed_desc)
    if k == DESC_KEY:
      continue
    indent = "  " * depth
    arrow = "↳ " if depth > 0 else ""
    print(f"{indent}{arrow}{k}")
    child = node.get(k)
    if isinstance(child, dict):
      stack.append((child, sorted(child.keys()), 0, depth + 1, False))
# ---------------------------------------------------------------------
# INTERACTIVE INPUT
# ---------------------------------------------------------------------


def confirm(
  prompt: str = "Proceed? [y/n]: ",
  *,
  valid_yes: tuple[str, ...] = ("y", "yes"),
  valid_no: tuple[str, ...] = ("n", "no"),
) -> bool:
  """
  Prompt repeatedly for a yes/no answer and return True/False for valid input.

  Example:
    if confirm("Install packages? [y/n]: "):
      ...
  """
  yes = tuple(s.lower() for s in valid_yes)
  no = tuple(s.lower() for s in valid_no)
  while True:
    resp = input(prompt).strip().lower()
    if resp in yes:
      return True
    if resp in no:
      return False
    print(
      f"Invalid input. Please enter one of: {', '.join(valid_yes + valid_no)}."
    )


def select_from_list(title: str, options: list[str]) -> str | None:
  """Render a numbered menu and return the selected option (or None on invalid input)"""
  if not options:
    return None
  print(f"\n{title}:")
  for i, opt in enumerate(options, start=1):
    print(f"{i}) {opt}")
  try:
    idx = int(input(f"Enter your selection (1-{len(options)}): ").strip())
  except ValueError:
    return None
  return options[idx - 1] if 1 <= idx <= len(options) else None


def pick_constants_interactively(choices: dict[str, tuple[str, Optional[int]]]) -> str:
  """Prompt the user to select a constants module, filtering choices by allowed UID rules"""
  current_uid = os.geteuid()
  current_user = getpass.getuser()
  allowed = {
    label: mod
    for label, (mod, uid) in choices.items()
    if (
      uid is None
      or uid == current_uid
      or (isinstance(uid, int) and uid >= 1000 and current_uid >= 1000)
    )
  }
  disallowed = {
    label: (mod, uid)
    for label, (mod, uid) in choices.items()
    if uid is not None and uid != current_uid
  }
  if disallowed:
    disallowed_lines = [
      f"[{'root only' if uid == 0 else f'uid {uid}+ only'}] {label}"
      for label, (_, uid) in disallowed.items()
    ]
    print(
      wrap_in_box(
        disallowed_lines,
        title="Programs not available for this user",
        indent=2,
      )
    )
  if not allowed:
    raise SystemExit(
      f"[FATAL] No utilities available for user '{current_user}' (uid {current_uid})"
    )
  options = list(allowed.keys()) + ["Exit"]
  print("\nChoose a utility")
  for i, opt in enumerate(options, 1):
    print(f"{i}) {opt}")
  choice = input(f"Enter your selection (1-{len(options)}): ").strip()
  if not choice.isdigit() or not (1 <= int(choice) <= len(options)):
    raise SystemExit("Invalid selection.")
  selection = options[int(choice) - 1]
  if selection == "Exit":
    raise SystemExit("Exited by user.")
  return allowed[selection]
# ---------------------------------------------------------------------
# CONFIG DOC HELPERS
# ---------------------------------------------------------------------


def display_config_doc(doc_path: str) -> bool:
  """Load a config help JSON doc and print its EXAMPLE and DESCRIPTION sections"""
  path = Path(doc_path)
  if not path.is_file():
    print(f"[ERROR] Config doc not found: {path}")
    return False
  try:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
  except Exception as e:
    print(f"[ERROR] Failed to read config doc '{path}': {e!r}")
    return False
  print()
  print(f"Config Help: {path.name}")
  print("-" * (13 + len(path.name)))
  if "EXAMPLE" in data:
    display_example(data["EXAMPLE"])
  else:
    print("\nEXAMPLE")
    print("-------")
    print("[WARN] No EXAMPLE section found.")
  if "DESCRIPTION" in data:
    display_description(data["DESCRIPTION"])
  else:
    print("\nDESCRIPTION")
    print("-----------")
    print("[WARN] No DESCRIPTION section found.")
  print()
  return True


def format_config_help(doc_path: str) -> list[str]:
  """Return formatted output lines for a config help JSON doc"""
  path = Path(doc_path)
  if not path.is_file():
    return [f"[WARN] No config help found at: {doc_path}"]
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except Exception as e:
    return [f"[WARN] Failed to read config help '{doc_path}': {e!r}"]
  lines: list[str] = []
  lines.append(f"Config Help: {path.name}")
  lines.append("-" * (13 + len(path.name)))
  buf = StringIO()
  with redirect_stdout(buf):
    display_example(data.get("EXAMPLE"))
    display_description(data.get("DESCRIPTION"))
  captured = buf.getvalue().splitlines()
  while captured and captured[0].strip() == "":
    captured.pop(0)
  lines.extend(captured)
  return lines
