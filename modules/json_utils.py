#!/usr/bin/env python3
"""
json_utils.py

Helpers for loading JSON config and validating config/job structures.
"""

import os
import re
import json
from pathlib import Path
from typing import Union,Dict, Any, List, Tuple


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
  """Save a dict to a JSON file"""
  parent = os.path.dirname(path)
  if parent:
    os.makedirs(parent, exist_ok=True)
  with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)


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
