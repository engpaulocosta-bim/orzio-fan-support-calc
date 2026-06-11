"""Configuração global — carregamento de YAMLs com cache."""

from __future__ import annotations

import functools
import sys
from pathlib import Path

import yaml

_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent.parent))


@functools.lru_cache(maxsize=32)
def _load_yaml(name: str) -> dict:
    path = _ROOT / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_seismic_zones() -> dict:
    return _load_yaml("seismic_zones.yaml")


def get_steel_grades_config() -> dict:
    return _load_yaml("steel_grades.yaml")


def get_standards_registry() -> dict:
    data = _load_yaml("standards_registry.yaml")
    return {s["id"]: s for s in data.get("standards", [])}


def get_assumptions() -> dict:
    return _load_yaml("assumptions.yaml")


def get_section_catalog(family: str) -> list[dict]:
    """Carrega catálogo YAML de uma família de perfis (hea, heb, ipe, ...)."""
    data = _load_yaml(f"data/catalogs/{family.lower()}_sections.yaml")
    return data.get("sections", [])
