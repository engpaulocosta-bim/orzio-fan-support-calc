# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para SFSC — Steel Fan Support Calc.

Gera um executável Windows single-folder (onedir) com:
  - Streamlit embutido
  - Todos os módulos sfsc
  - YAMLs de dados
  - Ícone personalizado

Build:
    cd c:\Repositorios\orzio-fan-support-calc
    pyinstaller build_desktop/sfsc.spec --noconfirm
"""
import sys
import os
from pathlib import Path
import site

ROOT         = Path(SPECPATH).parent          # raiz do repositório
SRC_DIR      = ROOT / "src"
DATA_DIR     = ROOT / "data"
ICON_PATH    = ROOT / "build_desktop" / "sfsc.ico"
SITE_PKGS    = Path(site.getsitepackages()[0]) / "Lib" / "site-packages"
# Sobrepor com o Python 3.11 onde Streamlit está instalado
_py311_pkgs = Path("C:/Users/Paulo Costa/AppData/Local/Programs/Python/Python311/Lib/site-packages")
if _py311_pkgs.exists():
    SITE_PKGS = _py311_pkgs

# ── Dados a incluir no bundle ─────────────────────────────────────────────────
datas = [
    # Código fonte sfsc
    (str(SRC_DIR / "sfsc"), "sfsc"),
    # app.py entry-point
    (str(ROOT / "app.py"), "."),
    # YAMLs de configuração (raiz do repo)
    (str(ROOT / "seismic_zones.yaml"),     "."),
    (str(ROOT / "steel_grades.yaml"),      "."),
    (str(ROOT / "standards_registry.yaml"),"."),
    (str(ROOT / "assumptions.yaml"),       "."),
    # Catálogos de perfis
    (str(DATA_DIR / "catalogs"), "data/catalogs"),
    # Streamlit static assets
    (str(SITE_PKGS / "streamlit"), "streamlit"),
    # Altair (dependência do Streamlit)
    (str(SITE_PKGS / "altair"), "altair") if (SITE_PKGS / "altair").exists() else ("", ""),
]
# Remover entradas vazias
datas = [(s, d) for s, d in datas if s]

# ── Hidden imports ─────────────────────────────────────────────────────────────
hiddenimports = [
    # sfsc
    "sfsc", "sfsc.enums", "sfsc.models", "sfsc.units", "sfsc.config",
    "sfsc.validators", "sfsc.exceptions",
    "sfsc.catalogs", "sfsc.catalogs.steel_section_catalog",
    "sfsc.catalogs.steel_grade_catalog", "sfsc.catalogs.seismic_catalog",
    "sfsc.engines", "sfsc.engines.loads", "sfsc.engines.section_verifier",
    "sfsc.engines.base_plate", "sfsc.engines.anchor",
    "sfsc.engines.checker", "sfsc.engines.selector",
    "sfsc.engines.support_types",
    "sfsc.engines.support_types.hanger",
    "sfsc.engines.support_types.cantilever_1",
    "sfsc.engines.support_types.cantilever_2",
    "sfsc.engines.support_types.cantilever_3",
    "sfsc.engines.support_types.pedestal",
    "sfsc.engines.support_types.combined",
    "sfsc.reports", "sfsc.reports.memorial_pdf", "sfsc.reports.exports",
    "sfsc.ui", "sfsc.ui.streamlit_app",
    # Streamlit internals
    "streamlit", "streamlit.web", "streamlit.web.cli",
    "streamlit.runtime", "streamlit.runtime.scriptrunner",
    "streamlit.components.v1",
    # Dependências
    "pydantic", "pydantic.v1",
    "yaml", "reportlab", "reportlab.lib", "reportlab.platypus",
    "openpyxl", "pandas", "numpy",
    "PIL", "PIL.Image", "PIL.ImageDraw",
    "altair", "click", "tornado",
    "importlib.metadata", "importlib.resources",
]

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
        "tkinter", "PyQt5", "PyQt6", "PySide6",
        "matplotlib", "scipy", "IPython", "jupyter",
        "pytest", "setuptools", "pip",
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
    [],
    exclude_binaries=True,
    name="SFSC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # sem janela de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SFSC",
)
