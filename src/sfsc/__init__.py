"""SFSC — Steel Fan Support Calc."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("sfsc")
except PackageNotFoundError:
    # Build congelado (PyInstaller) ou execução sem instalação — manter em
    # sincronia com pyproject.toml.
    __version__ = "1.0.0"
