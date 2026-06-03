"""
Launcher SFSC — abre o Streamlit no browser e mantém o processo vivo.
Este ficheiro é o entry-point compilado pelo PyInstaller.
"""
from __future__ import annotations
import os
import sys
import time
import socket
import threading
import subprocess
import webbrowser
from pathlib import Path

# ── Detectar se está dentro de um bundle PyInstaller ──────────────────────────
if getattr(sys, "frozen", False):
    # executável compilado: _MEIPASS contém os ficheiros extraídos
    BUNDLE_DIR = Path(sys._MEIPASS)
    APP_ROOT   = Path(sys.executable).parent
else:
    BUNDLE_DIR = Path(__file__).parent.parent
    APP_ROOT   = BUNDLE_DIR

PORT = 8502
APP_PY = BUNDLE_DIR / "app.py"


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _port_free(port):
            return True
        time.sleep(0.5)
    return False


def _open_browser(port: int):
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")


def main():
    # Se a porta já está ocupada, só abre o browser
    if not _port_free(PORT):
        webbrowser.open(f"http://localhost:{PORT}")
        return

    # Construir o comando Streamlit
    streamlit_exe = Path(sys.executable).parent / "Scripts" / "streamlit.exe"
    if not streamlit_exe.exists():
        streamlit_exe = Path(sys.executable).parent / "streamlit.exe"
    if not streamlit_exe.exists():
        # Dentro do bundle, o streamlit foi incluído como módulo
        cmd = [sys.executable, "-m", "streamlit", "run", str(APP_PY),
               "--server.port", str(PORT),
               "--server.headless", "true",
               "--browser.gatherUsageStats", "false"]
    else:
        cmd = [str(streamlit_exe), "run", str(APP_PY),
               "--server.port", str(PORT),
               "--server.headless", "true",
               "--browser.gatherUsageStats", "false"]

    # Lançar Streamlit em subprocesso
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BUNDLE_DIR / "src") + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(BUNDLE_DIR),
    )

    # Abrir o browser depois do servidor arrancar
    threading.Thread(target=_open_browser, args=(PORT,), daemon=True).start()

    if not _wait_for_server(PORT):
        print(f"Servidor não arrancou na porta {PORT}.")
        proc.terminate()
        return

    # Manter o processo vivo até o utilizador fechar a janela (se console)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()
