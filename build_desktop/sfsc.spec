# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for SFSC portable desktop builds.

Build:
    pyinstaller build_desktop/sfsc.spec --noconfirm

Output:
    dist/SFSC.exe
"""
from pathlib import Path
import site

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


ROOT = Path(SPECPATH).parent
SRC_DIR = ROOT / "src"
DATA_DIR = ROOT / "data"
ICON_PATH = ROOT / "build_desktop" / "sfsc.ico"

SITE_PKGS = Path(site.getsitepackages()[0])
PY311_PKGS = Path("C:/Users/Paulo Costa/AppData/Local/Programs/Python/Python311/Lib/site-packages")
if PY311_PKGS.exists():
    SITE_PKGS = PY311_PKGS

datas = [
    (str(SRC_DIR / "sfsc"), "sfsc"),
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "seismic_zones.yaml"), "."),
    (str(ROOT / "steel_grades.yaml"), "."),
    (str(ROOT / "standards_registry.yaml"), "."),
    (str(ROOT / "assumptions.yaml"), "."),
    (str(DATA_DIR / "catalogs"), "data/catalogs"),
    (str(SITE_PKGS / "streamlit"), "streamlit"),
]

if (SITE_PKGS / "altair").exists():
    datas.append((str(SITE_PKGS / "altair"), "altair"))

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
    "sfsc.catalogs",
    "sfsc.catalogs.steel_section_catalog",
    "sfsc.catalogs.steel_grade_catalog",
    "sfsc.catalogs.seismic_catalog",
    "sfsc.engines",
    "sfsc.engines.loads",
    "sfsc.engines.section_verifier",
    "sfsc.engines.base_plate",
    "sfsc.engines.anchor",
    "sfsc.engines.checker",
    "sfsc.engines.selector",
    "sfsc.engines.support_types",
    "sfsc.engines.support_types.hanger",
    "sfsc.engines.support_types.cantilever_1",
    "sfsc.engines.support_types.cantilever_2",
    "sfsc.engines.support_types.cantilever_3",
    "sfsc.engines.support_types.pedestal",
    "sfsc.engines.support_types.combined",
    "sfsc.reports",
    "sfsc.reports.memorial_pdf",
    "sfsc.reports.exports",
    "sfsc.ui",
    "sfsc.ui.streamlit_app",
    "sfsc.ui.inputs",
    "sfsc.ui.results",
    "sfsc.ui.support_visual",
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
    version_file=None,
)
