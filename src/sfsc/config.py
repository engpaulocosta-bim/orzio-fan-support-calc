"""Configuração global — carregamento de YAMLs com cache e proveniência."""

from __future__ import annotations

import datetime
import functools
import hashlib
import sys
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent.parent))

# Datasets que alimentam o cálculo — base da rastreabilidade (auditoria H-07).
_DATASET_FILES = [
    "assumptions.yaml",
    "seismic_zones.yaml",
    "standards_registry.yaml",
    "steel_grades.yaml",
    "data/catalogs/hea_sections.yaml",
    "data/catalogs/heb_sections.yaml",
    "data/catalogs/ipe_sections.yaml",
    "data/catalogs/rhs_sections.yaml",
    "data/catalogs/upn_sections.yaml",
]


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


@functools.lru_cache(maxsize=1)
def get_dataset_provenance() -> dict[str, Any]:
    """Proveniência dos datasets: SHA-256 e data de modificação de cada YAML.

    Incluída em todos os outputs (PDF/Excel/CSV) para que um relatório seja
    rastreável aos dados exactos com que foi calculado (auditoria H-07).
    """
    from . import __version__

    datasets: dict[str, dict[str, str]] = {}
    for rel in _DATASET_FILES:
        path = _ROOT / rel
        if not path.exists():
            datasets[rel] = {"sha256": "MISSING", "modified": "—"}
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        modified = datetime.datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        datasets[rel] = {"sha256": digest, "modified": modified}

    combined = hashlib.sha256("".join(d["sha256"] for d in datasets.values()).encode()).hexdigest()
    return {
        "software_version": __version__,
        "datasets": datasets,
        "datasets_combined_sha256": combined,
    }
