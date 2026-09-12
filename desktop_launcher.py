"""LexiCore Desktop launcher.

Commercial desktop runtime bootstrap. It keeps confidential working data outside
of the packaged application directory and serves LexiCore only on loopback.
Licensing/activation is deliberately a separate deployment gate.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

PRODUCT_DIR = "LexiCore"
DEFAULT_PORT = 53147


def _default_data_dir() -> Path:
    override = os.environ.get("LEXICORE_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return (Path(base) / PRODUCT_DIR).resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / PRODUCT_DIR).resolve()
    return (Path.home() / ".lexicore").resolve()


def configure_runtime_environment() -> Path:
    data_dir = _default_data_dir()
    uploads = data_dir / "uploads"
    backups = data_dir / "backups"
    exports = data_dir / "exports"
    for directory in (data_dir, uploads, backups, exports):
        directory.mkdir(parents=True, exist_ok=True)

    # Absolute paths are intentional: packaged binaries may live in Program Files
    # or PyInstaller's temporary extraction directory and must never store cases there.
    os.environ.setdefault("LEXICORE_DATA_DIR", str(data_dir))
    os.environ.setdefault("LEXICORE_DB_PATH", str(data_dir / "lexicore.db"))
    os.environ.setdefault("LEXICORE_BACKUP_DIR", str(backups))
    os.environ.setdefault("LEXICORE_UPLOAD_DIR", str(uploads))
    os.environ.setdefault("LEXICORE_EXPORT_DIR", str(exports))
    os.environ.setdefault("LEXICORE_HOST", "127.0.0.1")
    os.environ.setdefault("LEXICORE_DEBUG", "0")
    # Commercial desktop builds require activation before any confidential API is usable.
    os.environ.setdefault("LEXICORE_LICENSE_REQUIRED", "1")
    return data_dir


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def _existing_instance(port: int, timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(_health_url(port), timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def choose_port() -> int:
    requested = int(os.environ.get("LEXICORE_DESKTOP_PORT", str(DEFAULT_PORT)))
    if _existing_instance(requested):
        return requested
    if _port_is_free(requested):
        return requested
    # Avoid exposing on LAN and avoid failing startup just because the preferred
    # loopback port is occupied by an unrelated program.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _open_when_ready(port: int) -> None:
    deadline = time.time() + 20
    url = f"http://127.0.0.1:{port}/"
    while time.time() < deadline:
        if _existing_instance(port, timeout=0.4):
            webbrowser.open(url)
            return
        time.sleep(0.2)


def main() -> int:
    data_dir = configure_runtime_environment()
    port = choose_port()
    if _existing_instance(port):
        webbrowser.open(f"http://127.0.0.1:{port}/")
        return 0

    # Import only after writable runtime paths are configured; database.py and
    # app.py resolve their storage paths during module import.
    from app import app
    try:
        from waitress import serve
    except ImportError as exc:
        raise SystemExit(
            "Waitress belum terpasang. Install requirements-desktop.txt sebelum menjalankan desktop runtime."
        ) from exc

    print(f"LexiCore Desktop data: {data_dir}")
    print(f"LexiCore Desktop: http://127.0.0.1:{port}")
    threading.Thread(target=_open_when_ready, args=(port,), daemon=True).start()
    serve(app, host="127.0.0.1", port=port, threads=6, clear_untrusted_proxy_headers=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
