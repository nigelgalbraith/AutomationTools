#!/usr/bin/env python3
"""
system_utils.py
"""

import os
import subprocess
from typing import List, Set, Optional


# ---------------------------------------------------------------------
# SYSTEM STATUS HELPERS
# ---------------------------------------------------------------------

def expand_path(path):
    """Expand ~ in filesystem paths."""
    return os.path.expanduser(path)


def load_skip_list(skip_list_file: Optional[str]) -> Set[str]:
    """Load skip list values from file."""
    if not skip_list_file:
        return set()
    skip_list_file = expand_path(skip_list_file)
    if not os.path.exists(skip_list_file):
        return set()
    with open(skip_list_file, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


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
# COMMAND EXECUTION
# ---------------------------------------------------------------------

def run_cmd(
    cmd: List[str],
    *,
    check: bool = True,
    timeout: int | float | None = None,
    stream: bool = False,
    show_cmd: bool = True,
) -> subprocess.CompletedProcess | None:
    """Run a command; stream=True inherits terminal output instead of capturing it.

    show_cmd=False hides only the command line, not output or errors.
    Return CompletedProcess (stdout/stderr are None when streaming), or None on failure.
    """
    if show_cmd:
        print(f"[CMD] {' '.join(cmd)}", flush=True)
    try:
        result = subprocess.run(
            cmd,
            capture_output=not stream,
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
