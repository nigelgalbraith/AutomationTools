from __future__ import annotations

import os
from glob import glob
from typing import Dict, Optional
import requests


# ---------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------


def send_prompt_text_to_ollama_and_save(
  prompt_path: str,
  letters_out_dir: str,
  base_url: str,
  model: str,
  temperature: float,
  output_suffix: str = ".coverletter.txt",
  overwrite: bool = False,
  timeout_s: int = 600,
) -> Optional[str]:
  """Generate one letter from one prompt text file and save to disk"""
  print(f"\n[INFO] Processing prompt: {prompt_path}")
  try:
    with open(prompt_path, "r", encoding="utf-8") as f:
      prompt_text = f.read()
    print(f"[DEBUG] Prompt length: {len(prompt_text)} characters")
  except Exception as e:
    print(f"[ERROR] Failed to load prompt text: {prompt_path} -> {e!r}")
    return None
  try:
    b = (base_url or "").rstrip("/")
    generate_url = b + "/api/generate"
    print(f"[DEBUG] Sending to: {generate_url}")
    print(f"[DEBUG] Model: {model}")
    print(f"[DEBUG] Temperature: {temperature}")
    payload: Dict[str, object] = {
      "model": model,
      "prompt": prompt_text,
      "stream": False,
      "options": {"temperature": temperature},
    }
    resp = requests.post(generate_url, json=payload, timeout=timeout_s)
    print(f"[DEBUG] HTTP status: {resp.status_code}")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
      print(f"[ERROR] Unexpected Ollama response type for: {prompt_path}")
      return None
    text_out = (data.get("response") or "").strip()
    if not text_out:
      print(f"[ERROR] Empty response from Ollama for: {prompt_path}")
      return None
    print(f"[DEBUG] Response length: {len(text_out)} characters")
  except requests.HTTPError as e:
    body = ""
    try:
      body = e.response.text if e.response is not None else ""
    except Exception:
      body = ""
    print(f"[ERROR] Ollama HTTP error for {prompt_path}")
    print(f"        Status: {e.response.status_code if e.response else 'unknown'}")
    print(f"        Body: {body}")
    return None
  except Exception as e:
    print(f"[ERROR] Ollama request failed for {prompt_path} -> {e!r}")
    return None
  try:
    os.makedirs(letters_out_dir, exist_ok=True)
    base = os.path.basename(prompt_path)
    if base.endswith(".prompt.txt"):
      base = base[: -len(".prompt.txt")]
    else:
      base = os.path.splitext(base)[0]
    out_path = os.path.join(letters_out_dir, f"{base}{output_suffix}")
    if (not overwrite) and os.path.exists(out_path):
      print(f"[INFO] Letter exists, skipping: {out_path}")
      return out_path
    with open(out_path, "w", encoding="utf-8") as f:
      f.write(text_out)
    print(f"[OK] Letter saved: {out_path}")
    return out_path
  except Exception as e:
    print(f"[ERROR] Failed to save letter for {prompt_path} -> {e!r}")
    return None


def generate_text_from_prompts_dir(
  prompts_out_dir: str,
  letters_out_dir: str,
  base_url: str,
  model: str,
  temperature: float,
  prompt_glob: str = "*.prompt.txt",
  overwrite: bool = False,
) -> Dict[str, int]:
  """Generate letters for prompt files in prompts_out_dir"""
  summary = {"processed": 0, "saved": 0, "skipped": 0, "failed": 0}
  print(f"\n[INFO] Looking for prompts in: {prompts_out_dir}")
  if not os.path.isdir(prompts_out_dir):
    print(f"[WARN] prompts_out_dir does not exist: {prompts_out_dir}")
    return summary
  prompt_paths = sorted(glob(os.path.join(prompts_out_dir, prompt_glob)))
  print(f"[INFO] Found {len(prompt_paths)} prompt file(s)")
  for idx, prompt_path in enumerate(prompt_paths, start=1):
    print(f"\n[{idx}/{len(prompt_paths)}] Generating letter...")
    summary["processed"] += 1
    base = os.path.basename(prompt_path)
    if base.endswith(".prompt.txt"):
      base = base[: -len(".prompt.txt")]
    else:
      base = os.path.splitext(base)[0]
    expected = os.path.join(letters_out_dir, f"{base}.coverletter.txt")
    existed = os.path.exists(expected)
    out_path = send_prompt_text_to_ollama_and_save(
      prompt_path=prompt_path,
      letters_out_dir=letters_out_dir,
      base_url=base_url,
      model=model,
      temperature=temperature,
      overwrite=overwrite,
    )
    if out_path is None:
      summary["failed"] += 1
      continue
    if existed and not overwrite:
      summary["skipped"] += 1
    else:
      summary["saved"] += 1
  print("\n[SUMMARY]")
  print(f"  Processed: {summary['processed']}")
  print(f"  Saved:     {summary['saved']}")
  print(f"  Skipped:   {summary['skipped']}")
  print(f"  Failed:    {summary['failed']}")
  return summary
