#!/usr/bin/env python3
"""
system_utils.py
"""

import os
import subprocess
from typing import List


# ----------------------------------------------------------------------------
# SMALL HELPERS / STATUS
# ----------------------------------------------------------------------------


def check_account(expected_user="standard"):
  """Return True if script is run by the expected user type ("standard" vs "root")"""
  is_root = os.geteuid() == 0
  expected_user = expected_user.lower()
  if expected_user == "standard" and is_root:
    print("Please run this script as a standard (non-root) user.")
    return False
  elif expected_user == "root" and not is_root:
    print("Please run this script as root.")
    return False
  return True


# ---------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------

def run_cmd(
  cmd: List[str],
  *,
  check: bool = True,
  timeout: int | float | None = None
) -> subprocess.CompletedProcess | None:
  """Run a system command, print output, and return CompletedProcess (or None on failure)."""
  print(f"[CMD] {' '.join(cmd)}")
  try:
    result = subprocess.run(
      cmd,
      capture_output=True,
      text=True,
      check=False,
      timeout=timeout,
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if stdout:
      print(stdout)
    if stderr:
      print(stderr)
    if check and result.returncode != 0:
      print(f"[ERROR] Command exited with code {result.returncode}")
      return None
    return result
  except subprocess.TimeoutExpired as e:
    print(f"[ERROR] Command timed out: {' '.join(cmd)}")
    return None
  except Exception as e:
    print(f"[ERROR] Unexpected failure: {e}")
    return None
