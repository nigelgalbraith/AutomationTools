from __future__ import annotations

import os
from glob import glob
from typing import Dict, List, Optional
import requests
from modules.system_utils import expand_path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def prepare_prompts_directory(prompts_out_dir: str) -> Optional[str]:
    """Expand and validate the prompts directory."""
    prompts_out_dir = expand_path(prompts_out_dir)
    print(f"\n[INFO] Looking for prompts in: {prompts_out_dir}")
    if not os.path.isdir(prompts_out_dir):
        print(f"[WARN] prompts_out_dir does not exist: {prompts_out_dir}")
        return None
    return prompts_out_dir


def discover_prompt_files(
    prompts_out_dir: str,
    prompt_glob: str = "*.prompt.txt",
) -> List[str]:
    """Find prompt files in the supplied directory."""
    prompt_paths = sorted(glob(os.path.join(prompts_out_dir, prompt_glob)))
    print(f"[INFO] Found {len(prompt_paths)} prompt file(s)")
    return prompt_paths


# ---------------------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------------------

def display_generation_summary(
    summary: Dict[str, int],
) -> Dict[str, int]:
    """Display and return the generation summary."""
    print("\n[SUMMARY]")
    print(f"  Processed: {summary['processed']}")
    print(f"  Saved:     {summary['saved']}")
    print(f"  Skipped:   {summary['skipped']}")
    print(f"  Failed:    {summary['failed']}")
    return summary

# ---------------------------------------------------------------------
# STATUS
# ---------------------------------------------------------------------


def check_ollama_status(base_url: str, timeout: float = 5.0) -> bool:
    """Check whether the Ollama API is reachable and print its status."""
    url = f"{base_url.rstrip('/')}/api/tags"
    print(f"\n[INFO] Checking Ollama API: {url}")
    try:
        with urlopen(url, timeout=timeout) as response:
            if response.status == 200:
                print("[OK] Ollama is running and responding.")
                return True
            print(f"[WARN] Ollama returned HTTP {response.status}.")
            return False
    except HTTPError as e:
        print(f"[ERROR] Ollama returned HTTP {e.code}: {e.reason}")
    except URLError as e:
        print(f"[WARN] Cannot connect to Ollama: {e.reason}")
    except TimeoutError:
        print(f"[WARN] Ollama did not respond within {timeout} seconds.")
    except (OSError, ValueError) as e:
        print(f"[ERROR] Ollama status check failed: {e}")
    print("[WARN] Ollama is not available.")
    return False


# ---------------------------------------------------------------------
# TEXT GENERATION
# ---------------------------------------------------------------------

def load_prompt_text(prompt_path: str) -> Optional[str]:
    """Read a prompt text file."""
    prompt_path = expand_path(prompt_path)
    print(f"\n[INFO] Processing prompt: {prompt_path}")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        print(f"[DEBUG] Prompt length: {len(prompt_text)} characters")
        return prompt_text
    except Exception as e:
        print(f"[ERROR] Failed to load prompt text: {prompt_path} -> {e!r}")
        return None


def generate_ollama_response(
    prompt_path: str,
    prompt_text: str,
    base_url: str,
    model: str,
    temperature: float,
    timeout_s: int = 600,
) -> Optional[str]:
    """Send a prompt to Ollama and return the generated text."""
    try:
        generate_url = (base_url or "").rstrip("/") + "/api/generate"
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
        return text_out
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


def save_generated_text(
    prompt_path: str,
    text_out_dir: str,
    text_out: str,
    output_suffix: str = ".generated.txt",
    overwrite: bool = False,
) -> Optional[str]:
    """Save generated text to its corresponding output file."""
    try:
        text_out_dir = expand_path(text_out_dir)
        os.makedirs(text_out_dir, exist_ok=True)
        base = os.path.basename(prompt_path)
        if base.endswith(".prompt.txt"):
            base = base[: -len(".prompt.txt")]
        else:
            base = os.path.splitext(base)[0]
        out_path = os.path.join(text_out_dir, f"{base}{output_suffix}")
        if not overwrite and os.path.exists(out_path):
            print(f"[INFO] Text exists, skipping: {out_path}")
            return out_path
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text_out)
        print(f"[OK] Text saved: {out_path}")
        return out_path
    except Exception as e:
        print(f"[ERROR] Failed to save text for {prompt_path} -> {e!r}")
        return None
    

# ---------------------------------------------------------------------
# BATCH OPERATIONS
# ---------------------------------------------------------------------

def generate_text_from_prompt_files(
    prompt_paths: List[str],
    text_out_dir: str,
    base_url: str,
    model: str,
    temperature: float,
    overwrite: bool = False,
) -> Dict[str, int]:
    """Generate text for the supplied prompt files."""
    text_out_dir = expand_path(text_out_dir)
    summary = {"processed": 0, "saved": 0, "skipped": 0, "failed": 0}
    for idx, prompt_path in enumerate(prompt_paths, start=1):
        print(f"\n[{idx}/{len(prompt_paths)}] Processing...")
        summary["processed"] += 1
        base = os.path.basename(prompt_path)
        if base.endswith(".prompt.txt"):
            base = base[: -len(".prompt.txt")]
        else:
            base = os.path.splitext(base)[0]
        expected = os.path.join(text_out_dir, f"{base}.generated.txt")
        if os.path.exists(expected) and not overwrite:
            print(f"[SKIP] Already exists: {expected}")
            summary["skipped"] += 1
            continue
        prompt_text = load_prompt_text(prompt_path)
        if prompt_text is None:
            summary["failed"] += 1
            continue
        generated_text = generate_ollama_response(
            prompt_path,
            prompt_text,
            base_url,
            model,
            temperature,
        )
        if generated_text is None:
            summary["failed"] += 1
            continue
        out_path = save_generated_text(
            prompt_path,
            text_out_dir,
            generated_text,
            overwrite=overwrite,
        )
        if out_path is None:
            summary["failed"] += 1
        else:
            summary["saved"] += 1
    return summary


