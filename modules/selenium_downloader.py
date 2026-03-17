from __future__ import annotations

import os
import re
import time
from random import uniform
from typing import Any, Dict, List, Optional, Tuple, Set
from modules.system_utils import load_skip_list

# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------  

def extract_skip_id_from_url(url: str, filename_from_url_regex: Optional[str]) -> str:
  """Extract skip ID from URL using the configured regex."""
  if not filename_from_url_regex:
    return ""
  match = re.search(filename_from_url_regex, url)
  if not match:
    return ""
  return match.group(1).strip()


def append_skip_id(skip_id: str, skip_list_file: Optional[str], skip_ids: Set[str]) -> None:
  """Append a new skip ID to the skip list file and update the in-memory set."""
  if not skip_id or not skip_list_file:
    return
  if skip_id in skip_ids:
    return
  skip_ids.add(skip_id)
  with open(skip_list_file, "a+", encoding="utf-8") as f:
    f.seek(0, os.SEEK_END)
    if f.tell() > 0:
      f.seek(f.tell() - 1)
      if f.read(1) != "\n":
        f.write("\n")
    f.write(skip_id + "\n")


def setup_selenium_driver(headless: bool = False, minimized: bool = False):
  """Create a Chrome/Chromium webdriver with practical defaults."""
  from selenium import webdriver
  from selenium.webdriver.chrome.options import Options
  chrome_options = Options()
  chrome_options.add_argument("--window-size=1920,1080")
  chrome_options.add_argument("--start-maximized")
  chrome_options.add_argument("--no-sandbox")
  chrome_options.add_argument("--disable-dev-shm-usage")
  if headless:
    chrome_options.add_argument("--headless=new")
  driver = webdriver.Chrome(options=chrome_options)
  if minimized and not headless:
    driver.minimize_window()
  return driver


def _filename_base_from_url(url: str, pattern: Optional[str], default: str) -> str:
  """Extract group(1) from URL using regex pattern else return default"""
  if not pattern:
    return default
  m = re.search(pattern, url)
  return m.group(1) if m else default


def _extract_title_slug(driver: Any, selectors: List[str]) -> Optional[str]:
  """Extract a title and convert to a safe filename slug"""
  from selenium.webdriver.common.by import By
  for selector in selectors:
    try:
      element = driver.find_element(By.CSS_SELECTOR, selector)
      text = (element.text or "").strip()
      if not text:
        continue
      slug = re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")
      return slug[:60] if slug else None
    except Exception:
      continue
  return None


def _fetch_page_links(
  driver,
  url,
  limit,
  link_selector,
  url_must_contain=None,
  skip_ids: Optional[Set[str]] = None,
  filename_from_url_regex: Optional[str] = None,
):
  """Extract non-skipped links from a search page using a CSS selector."""
  from selenium.webdriver.common.by import By
  from selenium.webdriver.support.ui import WebDriverWait
  from selenium.webdriver.support import expected_conditions as EC
  driver.get(url)
  time.sleep(3.0)
  print(f"[DEBUG] Page title: {driver.title}")
  print(f"[DEBUG] Current URL: {driver.current_url}")
  try:
    WebDriverWait(driver, 20).until(
      lambda d: len(d.find_elements(By.CSS_SELECTOR, link_selector)) > 0
    )
  except Exception as e:
    print(f"[WARN] No elements found for selector: {link_selector} -> {e!r}")
    print(f"[DEBUG] Page title: {driver.title}")
    print(f"[DEBUG] Page source length: {len(driver.page_source or '')}")
    return []
  driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
  time.sleep(2.0)
  elements = driver.find_elements(By.CSS_SELECTOR, link_selector)
  print(f"[DEBUG] Raw matched elements: {len(elements)}")
  page_links: List[str] = []
  active_skip_ids = skip_ids or set()
  for element in elements:
    href = element.get_attribute("href")
    if not href:
      continue
    clean_url = href.split("?", 1)[0]
    if url_must_contain and url_must_contain not in clean_url:
      continue
    skip_id = extract_skip_id_from_url(clean_url, filename_from_url_regex)
    if skip_id and skip_id in active_skip_ids:
      print(f"[INFO] Skipping URL with skip ID '{skip_id}': {clean_url}")
      continue
    if clean_url not in page_links:
      page_links.append(clean_url)
    if len(page_links) >= limit:
      break
  return page_links


def _download_html_page(
  driver: "Any",
  page_url: str,
  download_dir: str,
  min_html_size_bytes: int = 5000,
  filename_from_url_regex: Optional[str] = None,
  title_selectors: Optional[List[str]] = None,
  index: int = 1,
) -> Tuple[bool, Optional[str], Optional[str]]:
  """Download a page and save HTML and return (ok, filename, error)"""
  try:
    driver.get(page_url)
    time.sleep(uniform(3.5, 5.5))
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.5)
    page_source = driver.page_source or ""
    if len(page_source) < min_html_size_bytes:
      return False, None, f"HTML too small ({len(page_source)} bytes) - likely blocked/partial"
    base = _filename_base_from_url(page_url, filename_from_url_regex, default=f"{index:03d}")
    title_slug = None
    if title_selectors:
      title_slug = _extract_title_slug(driver, title_selectors)
    filename = f"{base}.html" if not title_slug else f"{base}_{title_slug}.html"
    filepath = os.path.join(download_dir, filename)
    with open(filepath, "w", encoding="utf-8", newline="") as f:
      f.write(page_source)
    size = os.path.getsize(filepath)
    if size < min_html_size_bytes:
      return False, None, f"Saved file too small ({size} bytes) - likely blocked/partial"
    return True, filename, None
  except Exception as e:
    return False, None, repr(e)


# ---------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------


def download_html_pages(
  search_urls: List[str],
  download_dir: str,
  follow_links: bool,
  link_selector: str,
  links_per_search: int = 10,
  headless: bool = False,
  minimized: bool = False,
  delay_between_actions: float = 3.0,
  filename_from_url_regex: Optional[str] = None,
  title_selectors: Optional[List[str]] = None,
  skip_list_file: Optional[str] = None,
  min_delay_between_downloads_s: float = 2.0,
  max_delay_between_downloads_s: float = 4.0,
  min_html_size_bytes: int = 5000,
  url_must_contain: Optional[str] = None,
) -> Dict[str, Any]:
  """Download HTML pages by scraping links from search URLs (or downloading URLs directly)."""
  results: Dict[str, Any] = {
    "success": False,
    "total_links_found": 0,
    "downloads_attempted": 0,
    "downloads_succeeded": 0,
    "download_dir": download_dir,
    "errors": [],
  }
  skip_ids = load_skip_list(skip_list_file)
  if not skip_list_file:
    print("[INFO] Skip list disabled.")
  else:
    print(f"[INFO] Loaded {len(skip_ids)} skip IDs.")
  if not search_urls:
    print("[INFO] No search URLs provided.")
    return results
  os.makedirs(download_dir, exist_ok=True)
  driver: Optional[webdriver.Chrome] = None
  try:
    print(f"[INFO] Starting Selenium (headless={headless}, minimized={minimized})")
    driver = setup_selenium_driver(headless=headless, minimized=minimized)
    if follow_links:
      all_links: List[str] = []
      for idx, url in enumerate(search_urls, start=1):
        print(f"[INFO] [{idx}/{len(search_urls)}] Loading search page: {url}")
        links = _fetch_page_links(
          driver=driver,
          url=url,
          limit=links_per_search,
          link_selector=link_selector,
          url_must_contain=url_must_contain,
          skip_ids=skip_ids,
          filename_from_url_regex=filename_from_url_regex,
        )
        print(f"[OK] Found {len(links)} link(s) on search page.")
        all_links.extend(links)
        time.sleep(delay_between_actions)
      unique_links = sorted(set(all_links))
      print(f"[INFO] Total unique scraped link(s): {len(unique_links)}")
    else:
      print("[INFO] follow_links=False -> downloading provided URLs directly.")
      unique_links = sorted(set(u.strip() for u in search_urls if (u or "").strip()))
      print(f"[INFO] Total provided URL(s): {len(unique_links)}")
    filtered_links: List[str] = []
    skipped_count = 0
    for link in unique_links:
      skip_id = extract_skip_id_from_url(link, filename_from_url_regex)
      if skip_id and skip_id in skip_ids:
        skipped_count += 1
        print(f"[INFO] Skipping URL with skip ID '{skip_id}': {link}")
        continue
      filtered_links.append(link)
    unique_links = filtered_links
    results["total_links_found"] = len(unique_links)
    print(f"[INFO] Total link(s) after skip filtering: {len(unique_links)}")
    print(f"[INFO] Total skipped link(s): {skipped_count}")
    for i, page_url in enumerate(unique_links, start=1):
      results["downloads_attempted"] += 1
      print(f"[INFO] [{i}/{len(unique_links)}] Downloading: {page_url}")
      ok, filename, err = _download_html_page(
        driver=driver,
        page_url=page_url,
        download_dir=download_dir,
        min_html_size_bytes=min_html_size_bytes,
        filename_from_url_regex=filename_from_url_regex,
        title_selectors=title_selectors,
        index=i,
      )
      if ok:
        results["downloads_succeeded"] += 1
        print(f"    [OK] Saved: {filename}")
        job_id = extract_skip_id_from_url(page_url, filename_from_url_regex)
        append_skip_id(job_id, skip_list_file, skip_ids)
      else:
        results["errors"].append({"url": page_url, "error": err})
        print(f"    [ERROR] Failed: {err}")
      time.sleep(uniform(min_delay_between_downloads_s, max_delay_between_downloads_s))
    results["success"] = results["downloads_succeeded"] > 0
    print(
      f"[SUMMARY] attempted={results['downloads_attempted']} "
      f"saved={results['downloads_succeeded']} "
      f"failed={results['downloads_attempted'] - results['downloads_succeeded']}"
    )
    return results
  except Exception as e:
    results["errors"].append({"general": repr(e)})
    print(f"[ERROR] download_html_pages crashed -> {e!r}")
    return results
  finally:
    if driver is not None:
      print("[INFO] Closing Selenium driver...")
      try:
        driver.quit()
      except Exception:
        pass
