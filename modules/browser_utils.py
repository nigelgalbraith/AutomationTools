from __future__ import annotations

import os
import socket
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import quote


def open_html_with_json(
  viewer_path: str,
  json_path: Optional[str],
  host: str,
  port: int,
) -> bool:
  """Serve an HTML viewer and JSON file locally and open it in the browser."""
  if not json_path:
    return False
  viewer = Path(os.path.expanduser(viewer_path)).resolve()
  json_file = Path(os.path.expanduser(json_path)).resolve()
  if not viewer.exists():
    print(f"[ERROR] HTML viewer not found: {viewer}")
    return False
  if not json_file.exists():
    print(f"[ERROR] JSON file not found: {json_file}")
    return False
  server_root = viewer.parent.parent
  try:
    json_relative = json_file.relative_to(server_root)
  except ValueError:
    print(f"[ERROR] JSON file is outside server directory: {json_file}")
    return False
  server_running = False
  try:
    with socket.create_connection((host, port), timeout=0.25):
      server_running = True
  except OSError:
    pass
  if not server_running:
    subprocess.Popen(
      [
        "python3",
        "-m",
        "http.server",
        str(port),
        "--bind",
        host,
        "--directory",
        str(server_root),
      ],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      start_new_session=True,
    )
    time.sleep(0.25)
  json_value = quote(json_relative.as_posix())
  viewer_url = f"http://{host}:{port}/{viewer.relative_to(server_root).as_posix()}?result={json_value}"
  print(f"[INFO] Opening: {viewer_url}")
  return bool(webbrowser.open(viewer_url))