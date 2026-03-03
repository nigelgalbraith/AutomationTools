from __future__ import annotations

import os
import re
import time
from random import uniform
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------


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


def _fetch_page_links(driver, url, limit, link_selector, url_must_contain=None):
  """Extract links from a search page using a CSS selector."""
  from selenium.webdriver.common.by import By
  from selenium.webdriver.support.ui import WebDriverWait
  from selenium.webdriver.support import expected_conditions as EC
  driver.get(url)
  try:
    WebDriverWait(driver, 12).until(
      EC.presence_of_element_located((By.CSS_SELECTOR, link_selector))
    )
  except Exception:
    return []
  driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
  time.sleep(2.0)
  elements = driver.find_elements(By.CSS_SELECTOR, link_selector)
  page_links: List[str] = []
  for element in elements:
    href = element.get_attribute("href")
    if not href:
      continue
    clean_url = href.split("?", 1)[0]
    if url_must_contain and url_must_contain not in clean_url:
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
  link_selector: str,
  links_per_search: int = 10,
  headless: bool = False,
  minimized: bool = False,
  delay_between_actions: float = 3.0,
  filename_from_url_regex: Optional[str] = None,
  title_selectors: Optional[List[str]] = None,
  min_delay_between_downloads_s: float = 2.0,
  max_delay_between_downloads_s: float = 4.0,
  min_html_size_bytes: int = 5000,
  url_must_contain: Optional[str] = None,
) -> Dict[str, Any]:
  """Download HTML pages by scraping links from search URLs"""
  results: Dict[str, Any] = {
    "success": False,
    "total_links_found": 0,
    "downloads_attempted": 0,
    "downloads_succeeded": 0,
    "download_dir": download_dir,
    "errors": [],
  }
  if not search_urls:
    print("[INFO] No search URLs provided.")
    return results
  os.makedirs(download_dir, exist_ok=True)
  driver: Optional[webdriver.Chrome] = None
  try:
    print(f"[INFO] Starting Selenium (headless={headless}, minimized={minimized})")
    driver = setup_selenium_driver(headless=headless, minimized=minimized)
    all_links: List[str] = []
    for idx, url in enumerate(search_urls, start=1):
      print(f"[INFO] [{idx}/{len(search_urls)}] Loading search page: {url}")
      links = _fetch_page_links(
        driver=driver,
        url=url,
        limit=links_per_search,
        link_selector=link_selector,
        url_must_contain=url_must_contain,
      )
      print(f"[OK] Found {len(links)} link(s) on search page.")
      all_links.extend(links)
      time.sleep(delay_between_actions)
    unique_links = sorted(set(all_links))
    results["total_links_found"] = len(unique_links)
    print(f"[INFO] Total unique link(s) to download: {len(unique_links)}")
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
