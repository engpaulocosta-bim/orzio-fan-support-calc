import importlib.util
import os
import socket
from pathlib import Path
from types import SimpleNamespace


def _load_launcher_module():
    launcher_path = Path(__file__).parent.parent / "build_desktop" / "launcher.py"
    spec = importlib.util.spec_from_file_location("sfsc_desktop_launcher", launcher_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_desktop_launcher_enables_webview_downloads():
    launcher = _load_launcher_module()
    fake_webview = SimpleNamespace(settings={"ALLOW_DOWNLOADS": False})

    launcher._enable_webview_downloads(fake_webview)

    assert fake_webview.settings["ALLOW_DOWNLOADS"] is True


def test_desktop_launcher_uses_next_free_port_when_default_is_busy():
    launcher = _load_launcher_module()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        occupied_port = sock.getsockname()[1]

        assert launcher._find_free_port(start=occupied_port, attempts=2) == occupied_port + 1


def test_desktop_launcher_server_command_dev_mode(monkeypatch):
    launcher = _load_launcher_module()
    monkeypatch.setattr(launcher.sys, "frozen", False, raising=False)
    monkeypatch.setattr(launcher.sys, "executable", r"C:\Python\python.exe")

    command = launcher._server_command(8510)

    assert command[0] == r"C:\Python\python.exe"
    assert command[1].endswith(os.path.join("build_desktop", "launcher.py"))
    assert command[-2:] == ["--sfsc-server", "8510"]


def test_desktop_launcher_server_command_frozen(monkeypatch):
    launcher = _load_launcher_module()
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setattr(launcher.sys, "executable", r"C:\Apps\SFSC.exe")

    assert launcher._server_command(8511) == [r"C:\Apps\SFSC.exe", "--sfsc-server", "8511"]


def test_desktop_launcher_rotates_debug_log(tmp_path):
    launcher = _load_launcher_module()
    log_path = tmp_path / "sfsc_portable_debug.log"
    log_path.write_text("x" * (launcher.LOG_MAX_BYTES + 1), encoding="utf-8")

    launcher._rotate_log(log_path)

    assert not log_path.exists()
    assert log_path.with_suffix(".log.1").exists()


def test_desktop_launcher_shutdown_terminates_then_kills_if_needed():
    launcher = _load_launcher_module()

    class FakeServer:
        def __init__(self):
            self.terminated = False
            self.killed = False
            self.waits = 0

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout):
            self.waits += 1
            if self.waits == 1:
                raise launcher.subprocess.TimeoutExpired("SFSC.exe", timeout)
            return 0

    server = FakeServer()
    launcher._shutdown_server(server, timeout=0.01)

    assert server.terminated is True
    assert server.killed is True


def test_pyinstaller_spec_has_no_author_machine_path():
    spec_text = (Path(__file__).parent.parent / "build_desktop" / "sfsc.spec").read_text(
        encoding="utf-8"
    )

    assert "C:/Users/Paulo Costa" not in spec_text
    assert "version_file=str(VERSION_FILE)" in spec_text


def test_make_version_file_generates_windows_version_resource(tmp_path):
    module_path = Path(__file__).parent.parent / "build_desktop" / "make_version_file.py"
    spec = importlib.util.spec_from_file_location("sfsc_make_version_file", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nversion = "2.3.4"\n', encoding="utf-8")

    output = module.write_version_file(repo)

    text = output.read_text(encoding="utf-8")
    assert "filevers=(2, 3, 4, 0)" in text
    assert "StringStruct('ProductVersion', '2.3.4')" in text


def test_publish_release_detects_default_branch_instead_of_master_default():
    script_text = (
        Path(__file__).parent.parent / "build_desktop" / "publish_release.ps1"
    ).read_text(encoding="utf-8")

    assert '[string] $TargetCommitish = "master"' not in script_text
    assert "function Get-DefaultBranch" in script_text
    assert "Required asset is empty" in script_text
