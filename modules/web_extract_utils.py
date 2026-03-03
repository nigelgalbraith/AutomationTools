from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------


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
) -> Union[Dict[str, str], List[Dict[str, str]]]:
  """Extract fields from one URL/path, or from a list of URL/path sources"""
  if isinstance(source, list):
    items: List[Dict[str, str]] = []
    for s in source:
      try:
        items.append(_extract_one_source(s, rules, show_source=True))
      except Exception as e:
        print(f"[ERROR] Extraction failed: {s} -> {e!r}")
    return items
  return _extract_one_source(source, rules, show_source=True)


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



