#!/usr/bin/env python3
"""
package_utils.py

Package management helpers for APT/dpkg plus small checks for installed packages/binaries.
"""

import subprocess
from typing import List, Union
from shutil import which


# ---------------------------------------------------------------------
# HELPERS / STATUS
# ---------------------------------------------------------------------


def check_package(pkg: str) -> bool:
  """Return True if `pkg` is installed (via dpkg-query), otherwise False"""
  try:
    output = subprocess.check_output(
      ["dpkg-query", "-W", "-f=${Status}", pkg],
      stderr=subprocess.DEVNULL
    )
    return b"install ok installed" in output
  except subprocess.CalledProcessError:
    return False

# ---------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------


def ensure_dependencies_installed(dependencies):
  """Ensure required executables are installed via APT and return True if all succeed"""
  success = True
  for dep in dependencies:
    if which(dep) is None:
      try:
        subprocess.run(["sudo", "apt", "update", "-y"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y", dep], check=True)
      except subprocess.CalledProcessError:
        success = False
  return success


# ---------------------------------------------------------------------
# APT INSTALL / UNINSTALL
# ---------------------------------------------------------------------


def install_packages(packages: Union[str, List[str]]) -> bool:
  """Install one or more APT packages and return True on success"""
  if not packages:
    return False
  if isinstance(packages, str):
    packages = [packages]
  try:
    subprocess.run(["sudo", "apt", "update", "-y"], check=True)
    subprocess.run(["sudo", "apt", "install", "-y"] + packages, check=True)
    return True
  except subprocess.CalledProcessError:
    return False
