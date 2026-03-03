from __future__ import annotations

import os
import re
from typing import Dict, List
from modules.json_utils import build_basename


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------


def render_prompt_template(template_text: str, values: Dict[str, str]) -> str:
  """Render a text template by replacing {{key}} placeholders"""
  out = template_text
  for key, val in (values or {}).items():
    out = out.replace(f"{{{{{key}}}}}", "" if val is None else str(val))
  return out


# ---------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------

def write_prompts_from_items(
  template_path: str,
  prompts_out_dir: str,
  items: List[Dict[str, str]],
  injection_keys: List[str],
  basename_keys: List[str],
  output_suffix: str = ".prompt.txt",
) -> int:
  """Write rendered prompt text files for each extracted item."""
  if not items:
    print("[INFO] No items provided. Nothing to render.")
    return 0
  with open(template_path, "r", encoding="utf-8", newline="") as f:
    template_text = f.read()
  os.makedirs(prompts_out_dir, exist_ok=True)
  print(f"[INFO] Rendering {len(items)} prompt(s) from template: {template_path}")
  saved = 0
  for idx, item in enumerate(items, start=1):
    try:
      values = {}
      for key in (injection_keys or []):
        values[key] = item.get(key, "")
      rendered = render_prompt_template(template_text, values)
      base = build_basename(idx, item, basename_keys)
      path = os.path.join(prompts_out_dir, f"{base}{output_suffix}")
      with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(rendered)
      print(f"[{idx}/{len(items)}] Saved: {path}")
      saved += 1
    except Exception as e:
      print(f"[ERROR] Failed writing prompt #{idx} -> {e!r}")
  print(f"[SUMMARY] Prompts written: {saved}/{len(items)}")
  return saved
