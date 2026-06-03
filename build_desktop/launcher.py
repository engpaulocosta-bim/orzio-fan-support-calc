"""
Portable desktop launcher for SFSC.

The executable starts Streamlit as an internal backend and shows it in a
native desktop window via pywebview. No browser tab is opened.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path


PORT = 8502
APP_TITLE = "SFSC - Steel Fan Support Calc"


if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    APP_ROOT = Path(sys.executable).parent
else:
    BUNDLE_DIR = Path(__file__).parent.parent
    APP_ROOT = BUNDLE_DIR

APP_PY = BUNDLE_DIR / "app.py"


def _debug(message: str) -> None:
    if os.environ.get("SFSC_DEBUG") != "1":
        return
    log_path = Path(os.environ.get("TEMP", str(APP_ROOT))) / "sfsc_portable_debug.log"
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _find_free_port(start: int = PORT, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free local port found for SFSC.")


def _wait_for_server(port: int, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_is_open(port):
            return True
        time.sleep(0.5)
    return False


def _configure_environment() -> None:
    os.environ["PYTHONPATH"] = (
        str(BUNDLE_DIR / "src")
        + os.pathsep
        + os.environ.get("PYTHONPATH", "")
    )
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_SERVER_ADDRESS", "127.0.0.1")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    os.chdir(BUNDLE_DIR)


def _run_streamlit_server(port: int) -> None:
    _configure_environment()
    _debug(f"server start argv={sys.argv!r} bundle={BUNDLE_DIR} app={APP_PY} exists={APP_PY.exists()}")

    from streamlit.web import bootstrap

    flag_options = {
        "server_port": port,
        "server_address": "127.0.0.1",
        "server_headless": True,
        "server_fileWatcherType": "none",
        "browser_gatherUsageStats": False,
        "global_developmentMode": False,
    }
    bootstrap.load_config_options(flag_options)
    bootstrap.run(
        str(APP_PY),
        False,
        [],
        flag_options,
    )


def _server_command(port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable)), "--sfsc-server", str(port)]
    return [sys.executable, str(Path(__file__).resolve()), "--sfsc-server", str(port)]


def _enable_webview_downloads(webview_module) -> None:
    # pywebview disables downloads by default. Streamlit download_button relies
    # on the embedded WebView accepting the browser download request.
    webview_module.settings["ALLOW_DOWNLOADS"] = True


def main() -> None:
    _debug(f"main start argv={sys.argv!r} frozen={getattr(sys, 'frozen', False)} exe={sys.executable}")
    _configure_environment()

    if "--sfsc-server" in sys.argv:
        index = sys.argv.index("--sfsc-server")
        port = int(sys.argv[index + 1])
        _run_streamlit_server(port)
        return

    port = _find_free_port()
    server = subprocess.Popen(
        _server_command(port),
        cwd=str(BUNDLE_DIR),
        stdout=subprocess.DEVNULL if os.environ.get("SFSC_DEBUG") != "1" else open(Path(os.environ.get("TEMP", str(APP_ROOT))) / "sfsc_server_stdout.log", "a", encoding="utf-8"),
        stderr=subprocess.DEVNULL if os.environ.get("SFSC_DEBUG") != "1" else open(Path(os.environ.get("TEMP", str(APP_ROOT))) / "sfsc_server_stderr.log", "a", encoding="utf-8"),
    )

    if not _wait_for_server(port):
        server.terminate()
        raise RuntimeError("SFSC backend did not start.")

    import webview

    _enable_webview_downloads(webview)

    window = webview.create_window(
        APP_TITLE,
        f"http://127.0.0.1:{port}",
        width=1280,
        height=850,
        min_size=(1024, 700),
        confirm_close=False,
    )

    try:
        webview.start(private_mode=False)
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _debug(traceback.format_exc())
        raise
