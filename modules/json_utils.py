#!/usr/bin/env python3
"""
json_utils.py

Helpers for loading JSON config and validating config/job structures.
"""

import os
import re
import json
import tempfile

from pathlib import Path
from typing import Union, Dict, Any, List, Tuple, Optional


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def load_json(path: str) -> Dict[str, Any]:
  """Load a JSON file into a dict"""
  if not os.path.exists(path):
    raise FileNotFoundError(f"JSON file not found: {path}")
  with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
  if not isinstance(data, dict):
    raise TypeError(f"JSON root must be an object: {path}")
  return data


def save_json_file(path: str, data: Dict[str, Any]) -> None:
  """Atomically save a dict, preserving the previous file if writing fails."""
  parent = os.path.dirname(path)
  if parent:
    os.makedirs(parent, exist_ok=True)
  temporary_path = None
  try:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=parent or ".", prefix=".json-", suffix=".tmp", delete=False) as f:
      temporary_path = f.name
      json.dump(data, f, indent=2, ensure_ascii=False)
      f.flush()
      os.fsync(f.fileno())
    os.replace(temporary_path, path)
  finally:
    if temporary_path and os.path.exists(temporary_path):
      os.unlink(temporary_path)


def slugify(text: str) -> str:
  """Convert text into a safe filename slug"""
  s = (text or "").strip().lower()
  s = re.sub(r"[^a-z0-9]+", "_", s)
  s = re.sub(r"_+", "_", s).strip("_")
  return s or "item"


def build_basename(item: Dict[str, str], basename_keys: List[str]) -> str:
  """Build output basename from configured keys."""
  return "_".join(
    slugify(item.get(key, f"unknown_{key}"))
    for key in (basename_keys or [])
  )

def resolve_value(data: dict, primary_key: str, secondary_key: str, default_key: str = "default", check_file: bool = True) -> str | bool:
  """Resolve a nested dictionary value with fallback to `default_key`"""
  value = None
  if primary_key in data and secondary_key in data[primary_key]:
    value = data[primary_key][secondary_key]
  elif default_key in data and secondary_key in data[default_key]:
    value = data[default_key][secondary_key]
  if value is None:
    return False
  if check_file and isinstance(value, str) and not os.path.isfile(value):
    return False
  return value

# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------


def validate_required_fields(jobs: Dict[str, Dict[str, Any]], required_fields: Dict[str, Union[type, Tuple[type, ...]]]) -> Dict[str, bool]:
  """Check that each job dict contains required fields of the expected type(s)"""
  results: Dict[str, bool] = {field: True for field in required_fields}
  for job_name, meta in jobs.items():
    if not isinstance(meta, dict):
      for field in required_fields:
        results[field] = False
      continue
    for field, expected_type in required_fields.items():
      types = expected_type if isinstance(expected_type, tuple) else (expected_type,)
      if field not in meta or not isinstance(meta[field], types):
        results[field] = False
  return results


def validate_secondary_subkey(jobs_block: Dict[str, Dict[str, Any]], subkey: str, rules: Dict[str, Any]) -> Dict[str, bool]:
  """Validate required fields for dict items stored under a list-valued subkey for each job"""
  allow_empty = bool(rules.get("allow_empty", False))
  required = rules.get("required_job_fields", {}) or {}
  results: Dict[str, bool] = {fname: True for fname in required}
  for job_name, meta in jobs_block.items():
    if not isinstance(meta, dict):
      for fname in required:
        results[fname] = False
      continue
    items = meta.get(subkey, [])
    if not isinstance(items, list):
      for fname in required:
        results[fname] = False
      continue
    if not items and not allow_empty:
      for fname in required:
        results[fname] = False
      continue
    for itm in items:
      if not isinstance(itm, dict):
        for fname in required:
          results[fname] = False
        continue
      for field, expected_type in required.items():
        types_tuple = expected_type if isinstance(expected_type, tuple) else (expected_type,)
        if field not in itm or not isinstance(itm[field], types_tuple):
          results[field] = False
  return results

# ---------------------------------------------------------------------
# LOADERS AND SAVERS
# ---------------------------------------------------------------------


def load_items_from_dir(items_dir: str) -> List[Dict[str, str]]:
  """Load extracted item JSON files from items_dir (excludes *.profile.json)"""
  items: List[Dict[str, str]] = []
  if not os.path.isdir(items_dir):
    return items
  for name in sorted(os.listdir(items_dir)):
    if not name.endswith(".json"):
      continue
    path = os.path.join(items_dir, name)
    try:
      with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, dict):
        items.append({k: ("" if v is None else str(v)) for k, v in data.items()})
    except Exception as e:
      print(f"[ERROR] Failed to load item JSON: {path} -> {e!r}")
  return items


def save_items_json_dir(
  items: List[Dict[str, str]],
  out_dir: str,
  basename_keys: List[str],
) -> bool:
  """Save one JSON file per item into out_dir using configured basename keys."""
  if not items:
    print("[INFO] No items to save.")
    return False
  os.makedirs(out_dir, exist_ok=True)
  print(f"[INFO] Saving {len(items)} JSON file(s) to: {out_dir}")
  saved = 0
  for idx, item in enumerate(items, start=1):
    try:
      base = build_basename(item, basename_keys)
      path = os.path.join(out_dir, f"{base}.json")
      save_json_file(path, item)
      print(f"[{idx}/{len(items)}] Saved: {path}")
      saved += 1
    except Exception as e:
      print(f"[ERROR] Failed saving item #{idx} -> {e!r}")
  print(f"[SUMMARY] JSON files written: {saved}/{len(items)}")
  return saved == len(items)


def save_named_json(
  data: Dict[str, Any],
  out_dir: str,
  output_name: str,
) -> Optional[str]:
  """Save data as a named JSON file in the configured output directory."""
  if not output_name:
    print("[ERROR] No output name provided.")
    return None
  os.makedirs(out_dir, exist_ok=True)
  safe_name = os.path.basename(output_name)
  if not safe_name.lower().endswith(".json"):
    safe_name = f"{safe_name}.json"
  path = os.path.join(out_dir, safe_name)
  try:
    save_json_file(path, data)
    print(f"[INFO] Saved JSON: {path}")
    return path
  except Exception as e:
    print(f"[ERROR] Failed saving JSON -> {e!r}")
    return None

def select_json_file(
  json_dir: str,
) -> Optional[str]:
  """Select a JSON file from a directory."""
  if not os.path.isdir(json_dir):
    print(f"[INFO] JSON directory does not exist: {json_dir}")
    return None
  files = sorted(
    name for name in os.listdir(json_dir)
    if name.lower().endswith(".json")
  )
  if not files:
    print(f"[INFO] No JSON files found in: {json_dir}")
    return None
  print()
  print("JSON files")
  print("----------")
  for index, filename in enumerate(files, start=1):
    print(f"{index}. {filename}")
  print("0. Cancel")
  while True:
    choice = input("Select JSON file: ").strip()
    if choice == "0":
      return None
    try:
      index = int(choice) - 1
    except ValueError:
      print("Invalid selection.")
      continue
    if 0 <= index < len(files):
      return os.path.abspath(os.path.join(json_dir, files[index]))
    print("Invalid selection.")