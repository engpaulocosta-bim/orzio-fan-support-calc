import importlib.util
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
