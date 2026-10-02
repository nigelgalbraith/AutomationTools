from __future__ import annotations

import subprocess
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlsplit
from modules.system_utils import expand_path


# ---------------------------------------------------------------------
# BROWSER VIEWER
# ---------------------------------------------------------------------

def open_html_with_json(
    viewer_path: str,
    json_path: Optional[str],
    host: str,
    port: int,
) -> bool:
    """Serve an HTML viewer and JSON file locally and open it in the browser."""
    if not isinstance(json_path, (str, Path)) or not json_path:
        return False
    viewer = Path(expand_path(viewer_path)).resolve()
    json_file = Path(expand_path(json_path)).resolve()
    if not viewer.is_file():
        print(f"[ERROR] HTML viewer not found: {viewer}")
        return False
    if not json_file.is_file():
        print(f"[ERROR] JSON file not found: {json_file}")
        return False
    server_root = viewer.parent.parent
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "modules.browser_utils",
            str(server_root),
            str(json_file),
            host,
            str(port),
        ],
        cwd=str(Path(__file__).resolve().parent.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    with server.stdout:
        server_port = server.stdout.readline().strip()
    if not server_port.isdigit():
        print("[ERROR] Could not start viewer server.")
        return False
    port = int(server_port)
    json_value = quote("__crawler_result__.json")
    viewer_url = f"http://{host}:{port}/{viewer.relative_to(server_root).as_posix()}?result={json_value}"
    print(f"[INFO] Opening: {viewer_url}")
    return bool(webbrowser.open(viewer_url))


if __name__ == "__main__":
    server_root, json_path, host, port = sys.argv[1:]

    class ViewerHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=server_root, **kwargs)

        def translate_path(self, path):
            if urlsplit(path).path == "/__crawler_result__.json":
                return json_path
            return super().translate_path(path)

    try:
        server = ThreadingHTTPServer((host, int(port)), ViewerHandler)
    except OSError:
        server = ThreadingHTTPServer((host, 0), ViewerHandler)
    print(server.server_port, flush=True)
    with server:
        server.serve_forever()
