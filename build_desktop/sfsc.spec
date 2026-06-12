# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for SFSC portable desktop builds.

Build:
    pyinstaller build_desktop/sfsc.spec --noconfirm

Output:
    dist/SFSC.exe
"""
from pathlib import Path
import importlib.util
import sys
import sysconfig

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


ROOT = Path(SPECPATH).parent
BUILD_DIR = ROOT / "build_desktop"
SRC_DIR = ROOT / "src"
DATA_DIR = ROOT / "data"
ICON_PATH = ROOT / "build_desktop" / "sfsc.ico"
VERSION_FILE = ROOT / "build_desktop" / "version_info.txt"

sys.path.insert(0, str(BUILD_DIR))
from make_version_file import write_version_file


def package_dir(package_name):
    spec = importlib.util.find_spec(package_name)
    if spec is None or not spec.submodule_search_locations:
        purelib = sysconfig.get_paths().get("purelib", "<unknown>")
        raise SystemExit(
            f"Required package '{package_name}' was not found. "
            f"Install build dependencies first, e.g. pip install -r requirements-build.txt. "
            f"Resolved purelib: {purelib}"
        )
    return Path(next(iter(spec.submodule_search_locations))).resolve()


STREAMLIT_DIR = package_dir("streamlit")
write_version_file(ROOT, VERSION_FILE)

datas = [
    (str(SRC_DIR / "sfsc"), "sfsc"),
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "seismic_zones.yaml"), "."),
    (str(ROOT / "steel_grades.yaml"), "."),
    (str(ROOT / "standards_registry.yaml"), "."),
    (str(ROOT / "assumptions.yaml"), "."),
    (str(DATA_DIR / "catalogs"), "data/catalogs"),
    (str(STREAMLIT_DIR), "streamlit"),
]

altair_spec = importlib.util.find_spec("altair")
if altair_spec is not None and altair_spec.submodule_search_locations:
    datas.append((str(Path(next(iter(altair_spec.submodule_search_locations))).resolve()), "altair"))

datas += collect_data_files("webview")
datas += copy_metadata("streamlit")

hiddenimports = [
    "sfsc",
    "sfsc.enums",
    "sfsc.models",
    "sfsc.units",
    "sfsc.assessment",
    "sfsc.config",
    "sfsc.validators",
    "sfsc.exceptions",
    "sfsc.checks",
    "sfsc.policy",
    "sfsc.engineering",
    "sfsc.section_orientation",
    "sfsc.api",
    "sfsc.i18n",
    "sfsc.catalogs",
    "sfsc.catalogs.steel_section_catalog",
    "sfsc.catalogs.steel_grade_catalog",
    "sfsc.catalogs.seismic_catalog",
    "sfsc.engines",
    "sfsc.engines.loads",
    "sfsc.engines.load_surfaces",
    "sfsc.engines.section_verifier",
    "sfsc.engines.base_plate",
    "sfsc.engines.anchor",
    "sfsc.engines.checker",
    "sfsc.engines.metal_connections",
    "sfsc.engines.steel_fixation",
    "sfsc.engines.connection_verifier",
    "sfsc.engines.global_frame",
    "sfsc.engines.quantities",
    "sfsc.engines.ifc_import",
    "sfsc.engines.selector",
    "sfsc.engines.support_types",
    "sfsc.engines.support_types.hanger",
    "sfsc.engines.support_types.cantilever_1",
    "sfsc.engines.support_types.cantilever_2",
    "sfsc.engines.support_types.cantilever_3",
    "sfsc.engines.support_types.pedestal",
    "sfsc.engines.support_types.combined",
    "sfsc.engines.support_types.platform_frame_braced",
    "sfsc.reports",
    "sfsc.reports.memorial_pdf",
    "sfsc.reports.exports",
    "sfsc.reports.export_json",
    "sfsc.ui",
    "sfsc.ui.streamlit_app",
    "sfsc.ui.support_visual",
    "sfsc.ui.components",
    "sfsc.ui.components.results_view",
    "sfsc.ui.components.sidebar_geometry",
    "sfsc.ui.components.sidebar_modules",
    "sfsc.ui.components.sidebar_support",
    "sfsc.ui.components.sidebar_fan",
    "sfsc.ui.components.sidebar_identification",
    "sfsc.ui.components.sidebar_context",
    "sfsc.ui.components.sidebar_import",
    "sfsc.ui.components.export_bar",
    "streamlit",
    "streamlit.web",
    "streamlit.web.bootstrap",
    "streamlit.runtime",
    "streamlit.runtime.scriptrunner",
    "streamlit.components.v1",
    "pydantic",
    "pydantic.v1",
    "yaml",
    "reportlab",
    "reportlab.lib",
    "reportlab.platypus",
    "openpyxl",
    "pandas",
    "numpy",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "altair",
    "click",
    "tornado",
    "importlib.metadata",
    "importlib.resources",
    "webview",
    "pythonnet",
    "clr_loader",
    "cffi",
]
hiddenimports += collect_submodules("webview")
hiddenimports += collect_submodules("clr_loader")

a = Analysis(
    [str(ROOT / "build_desktop" / "launcher.py")],
    pathex=[str(SRC_DIR), str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide6",
        "matplotlib",
        "scipy",
        "IPython",
        "jupyter",
        "pytest",
        "setuptools",
        "pip",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SFSC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
    version_file=str(VERSION_FILE),
)
