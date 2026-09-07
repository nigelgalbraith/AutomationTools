from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree
from typing import Any, Dict, List, Optional, Union, Callable
from urllib.parse import parse_qs, unquote, urlparse
import requests
from bs4 import BeautifulSoup
from modules.system_utils import load_skip_list
from modules.json_utils import save_named_json


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


def search_web(domain: str, terms: List[str], max_results: int) -> List[Dict[str, str]]:
  """Search Bing's RSS results, limited to max_results URLs per term."""
  host = (urlparse(domain if "://" in domain else f"https://{domain}").hostname or "").lower().rstrip(".")
  if not host or not terms or any(not isinstance(term, str) or not term.strip() for term in terms):
    raise ValueError("Search requires a domain and nonempty search terms.")
  if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results < 1:
    raise ValueError("max_results must be a positive integer.")
  results: List[Dict[str, str]] = []
  for term in dict.fromkeys(term.strip() for term in terms):
    query = f'site:{host} "{term.replace(chr(34), " ")}"'
    print(f"[INFO] Web search (Bing RSS): {query}")
    try:
      response = requests.get("https://www.bing.com/search", params={"q": query, "format": "rss", "count": max_results}, timeout=25)
      response.raise_for_status()
      root = ElementTree.fromstring(response.content)
      if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Search provider returned an unexpected response instead of RSS results.")
      seen = set()
      for item in root.findall("./channel/item"):
        url = (item.findtext("link") or "").strip()
        parsed = urlparse(url)
        target = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in ("http", "https") or not (target == host or target.endswith(f".{host}")):
          continue
        url = parsed._replace(fragment="").geturl()
        if url in seen:
          continue
        seen.add(url)
        results.append({"term": term, "url": url})
        if len(seen) >= max_results:
          break
      print(f"[INFO] Search performed for '{term}': {len(seen)} candidate URLs found.")
    except Exception as e:
      print(f"[ERROR] Web search failed for '{term}': {e!r}")
      raise
  return results


def print_search_results(results: List[Dict[str, str]]) -> bool:
  """Display candidate URLs without invoking either crawler."""
  for index, result in enumerate(results, start=1):
    print(f"{index}. {result['term']} -> {result['url']}")
  print(f"[INFO] Search candidates: {len(results)}")
  return bool(results)


def page_contains_term(
  html: str,
  term: str,
) -> bool:
  """Return True when page text contains the configured term."""
  soup = BeautifulSoup(html, "html.parser")
  text = soup.get_text(" ", strip=True)
  return term.casefold() in text.casefold()


def run_photon(
  url: str,
  photon_python: str,
  photon_script: str,
  depth: int,
) -> List[str]:
  """Run Photon and return URLs discovered by the crawl."""
  python_path = Path(os.path.expanduser(photon_python))
  script_path = Path(os.path.expanduser(photon_script))
  if not python_path.exists():
    raise FileNotFoundError(f"Photon Python not found: {python_path}")
  if not script_path.exists():
    raise FileNotFoundError(f"Photon script not found: {script_path}")
  with tempfile.TemporaryDirectory(prefix="photon_") as output_dir:
    command = [
      str(python_path),
      str(script_path),
      "-u",
      url,
      "-l",
      str(depth),
      "-o",
      output_dir,
    ]
    result = subprocess.run(
      command,
      capture_output=True,
      text=True,
      check=False,
    )
    if result.returncode != 0:
      raise RuntimeError(result.stderr.strip() or f"Photon returned {result.returncode}")
    internal_file = Path(output_dir) / "internal.txt"
    if not internal_file.exists():
      raise RuntimeError("Photon produced no internal.txt URL dataset.")
    return list(dict.fromkeys(
      line.strip() for line in internal_file.read_text(encoding="utf-8").splitlines()
      if line.strip().startswith(("http://", "https://"))
    ))


def crawl_with_photon(
  candidates: List[Dict[str, str]],
  terms: List[str],
  photon_python: str,
  photon_script: str,
  depth: int = 2,
  checkpoint_fn: Optional[Callable[[List[Dict[str, str]]], None]] = None,
) -> Dict[str, Any]:
  """Run Photon from search candidates and check discovered pages for terms."""
  results: List[Dict[str, str]] = []
  result_seen = set()
  fallback = {}
  checked = set()
  seeds = dict.fromkeys(candidate["url"] for candidate in candidates if candidate.get("url"))
  if not seeds:
    print("[INFO] Photon skipped: no search candidates.")
  for seed_url in seeds:
    print(f"[INFO] Executing Photon for candidate: {seed_url}")
    try:
      discovered = run_photon(seed_url, photon_python, photon_script, depth)
    except Exception as e:
      print(f"[ERROR] Photon failed: {seed_url} -> {e!r}")
      fallback[seed_url] = {"url": seed_url}
      continue
    print(f"[INFO] Photon executed: {len(discovered)} internal URLs discovered.")
    for page_url in dict.fromkeys([seed_url] + discovered):
      if page_url in checked:
        continue
      checked.add(page_url)
      try:
        html = fetch_text(page_url)
      except Exception as e:
        print(f"[WARN] Photon page check failed: {page_url} -> {e!r}")
        fallback[page_url] = {"url": page_url}
        continue
      for term in dict.fromkeys(terms):
        key = (term.casefold(), page_url)
        if key not in result_seen and page_contains_term(html, term):
          result_seen.add(key)
          results.append({"term": term, "url": page_url, "source": "photon"})
          print(f"[OK] Found '{term}': {page_url}")
          if checkpoint_fn is not None:
            try:
              checkpoint_fn(results)
            except Exception as e:
              print(f"[ERROR] Checkpoint failed -> {e!r}")
  print(f"[SUMMARY] Photon matches: {len(results)}; Selenium fallback URLs: {len(fallback)}")
  return {"results": results, "fallback_urls": list(fallback.values())}


def merge_crawl_results(
  photon_results: List[Dict[str, str]],
  selenium_results: List[Dict[str, str]],
) -> List[Dict[str, str]]:
  """Merge crawler results using term and URL as the unique key."""
  merged: List[Dict[str, str]] = []
  seen = set()
  for result in list(photon_results or []) + list(selenium_results or []):
    term = result.get("term", "")
    url = result.get("url", "")
    if not term or not url:
      continue
    key = (term.casefold(), url)
    if key in seen:
      continue
    seen.add(key)
    merged.append(result)
  return merged


def print_crawl_results(
  results: List[Dict[str, str]],
) -> bool:
  """Print crawler matches to the terminal."""
  print()
  print("WEB CRAWLER RESULTS")
  print("-------------------")
  if not results:
    print("No matches found; no result file will be written.")
    return False
  for index, result in enumerate(results, start=1):
    print(f"{index}. {result['term']} -> {result['url']} ({result['source']})")
  print()
  print(f"Total results: {len(results)}")
  return True


def build_crawl_results(
  domain: str,
  results: List[Dict[str, str]],
) -> Dict[str, Any]:
  """Build crawler result data for JSON output."""
  return {
    "domain": domain,
    "total_results": len(results),
    "results": results,
  }


def make_checkpoint(source: str, domain: str, output_name: str, results_dir: str, ctx: Dict[str, Any]):
  """Initialize and publish one crawler's live results independently of final output."""
  if output_name.lower().endswith(".json"):
    output_name = output_name[:-5]
  output_name = f"{output_name}-{source.capitalize()}"
  saved_results = None
  def checkpoint(results):
    nonlocal saved_results
    unique = merge_crawl_results(results, [])
    if source == "photon":
      ctx.setdefault("photon_crawl", {})["results"] = list(unique)
    else:
      ctx["selenium_results"] = list(unique)
    if unique == saved_results:
      return
    path = save_named_json(
      build_crawl_results(domain, unique),
      results_dir,
      output_name,
    )
    if path:
      saved_results = unique
      print(f"[INFO] {source.capitalize()} results saved: {len(unique)}")
    else:
      print(f"[ERROR] {source.capitalize()} live results were not saved; crawling will continue.")
  try:
    checkpoint([])
  except Exception as e:
    print(f"[ERROR] {source.capitalize()} live results initialization failed -> {e!r}")
  return checkpoint
