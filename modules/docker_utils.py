from __future__ import annotations

import subprocess
import time
import requests

# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

import subprocess


def is_ollama_running(compose_dir: str) -> bool:
  """Return True if the Ollama container is already running."""
  try:
    result = subprocess.run(
      ["docker", "compose", "ps", "--status", "running"],
      cwd=compose_dir,
      capture_output=True,
      text=True,
      check=True,
    )
    return "ollama" in result.stdout.lower()
  except Exception:
    return False
  

def wait_for_ollama_ready(timeout: int = 15) -> bool:
  """Wait until Ollama API responds or timeout expires."""
  for _ in range(timeout):
    try:
      r = requests.get("http://localhost:11434/api/tags", timeout=2)
      if r.status_code == 200:
        return True
    except Exception:
      pass
    time.sleep(1)
  return False

# ---------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------

def start_ollama_compose(compose_dir: str) -> bool:
  """Start Ollama services with docker compose in the given directory."""
  if not compose_dir:
    print("[ERROR] compose_dir is required.")
    return False
  if is_ollama_running(compose_dir):
    print("[INFO] Ollama already running.")
  else:
    try:
      print(f"[INFO] Starting docker compose in: {compose_dir}")
      subprocess.run(
        ["docker", "compose", "up", "-d"],
        cwd=compose_dir,
        check=True,
      )
      print("[OK] Docker compose started.")
    except Exception as e:
      print(f"[ERROR] Failed to start docker compose: {e!r}")
      return False
  print("[INFO] Waiting for Ollama to become ready...")
  if wait_for_ollama_ready():
    print("[OK] Ollama is ready.")
    return True
  print("[ERROR] Ollama did not become ready in time.")
  return False


def stop_ollama_compose(compose_dir: str) -> bool:
  """Stop Ollama services with docker compose in the given directory"""
  if not compose_dir:
    print("[ERROR] compose_dir is required.")
    return False
  try:
    print(f"[INFO] Stopping docker compose in: {compose_dir}")
    subprocess.run(["docker", "compose", "down"], cwd=compose_dir, check=True)
    print("[OK] Docker compose stopped.")
    return True
  except Exception as e:
    print(f"[ERROR] Failed to stop docker compose: {e!r}")
    return False
