from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from modules.system_utils import load_skip_list


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------
def should_skip_extracted_item(item_data: Dict[str, str], extract_rules: Dict[str, Any]) -> bool:
  """Return True if any extracted field value matches its configured skip list."""
  for field_name, rule in extract_rules.items():
    skip_list_file = rule.get("skip_list_file", "")
    if not skip_list_file:
      continue
    field_value = str(item_data.get(field_name, "")).strip()
    if not field_value:
      continue
    skip_values = {value.strip().lower() for value in load_skip_list(skip_list_file)}
    if field_value.lower() in skip_values:
      print(f"[INFO] Skipping item because '{field_name}' matched skip list: {field_value}")
      return True
  return False


def fetch_text(url: str, timeout_s: int = 15, headers: Optional[Dict[str, str]] = None) -> str:
  """Fetch text content from a URL"""
  hdrs = headers or {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) WebExtract/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  }
  resp = requests.get(url, headers=hdrs, timeout=timeout_s)
  resp.raise_for_status()
  return resp.text


def parse_fields_from_html(html: str, rules: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
  """Extract named text fields from HTML using CSS selector or regex rules"""
  soup = BeautifulSoup(html, "html.parser")
  out: Dict[str, str] = {}
  for field, rule in (rules or {}).items():
    rule = rule or {}
    pattern = rule.get("regex")
    if pattern:
      m = re.search(pattern, html)
      out[field] = m.group(1).strip() if m else ""
      continue
    selector = rule.get("css", "")
    attr = rule.get("attr")
    sep = rule.get("sep", "\n")
    if not selector:
      out[field] = ""
      continue
    node = soup.select_one(selector)
    if not node:
      out[field] = ""
      continue
    if attr:
      val = node.get(attr)
      out[field] = str(val).strip() if val is not None else ""
    else:
      out[field] = node.get_text(separator=sep, strip=True)
  return out


def _extract_one_source(source: str, rules: Dict[str, Dict[str, Any]], show_source: bool = False) -> Dict[str, str]:
  source = (source or "").strip()
  parsed = urlparse(source)
  if parsed.scheme in ("http", "https"):
    html = fetch_text(source)
  elif parsed.scheme == "file":
    with open(parsed.path, "r", encoding="utf-8", errors="replace") as f:
      html = f.read()
  elif os.path.exists(source):
    with open(source, "r", encoding="utf-8", errors="replace") as f:
      html = f.read()
  else:
    raise ValueError(f"Unsupported source: {source}")
  data = parse_fields_from_html(html, rules)
  if show_source:
    data["html_source"] = source
  return data


def extract_fields_from_url(
  source: Union[str, List[str]], rules: Dict[str, Dict[str, Any]], show_source: bool = True
) -> Union[Optional[Dict[str, str]], List[Dict[str, str]]]:
  """Extract fields from one URL/path, or from a list of URL/path sources."""
  if isinstance(source, list):
    items: List[Dict[str, str]] = []
    for s in source:
      try:
        item = _extract_one_source(s, rules, show_source=show_source)
        if should_skip_extracted_item(item, rules):
          print(f"[INFO] Skipped extracted item: {s}")
          continue
        items.append(item)
      except Exception as e:
        print(f"[ERROR] Extraction failed: {s} -> {e!r}")
    return items
  item = _extract_one_source(source, rules, show_source=show_source)
  if should_skip_extracted_item(item, rules):
    print(f"[INFO] Skipped extracted item: {source}")
    return {}
  return item


# ---------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------

def list_html_files(html_dir: str) -> List[str]:
  """Return absolute paths for .html/.htm files in html_dir, sorted"""
  if not html_dir:
    return []
  if not os.path.isdir(html_dir):
    print(f"[WARN] html_dir does not exist: {html_dir}")
    return []
  files: List[str] = []
  for name in os.listdir(html_dir):
    low = name.lower()
    if low.endswith(".html") or low.endswith(".htm"):
      files.append(os.path.abspath(os.path.join(html_dir, name)))
  files.sort()
  print(f"[OK] Found {len(files)} HTML files in: {html_dir}")
  return files



