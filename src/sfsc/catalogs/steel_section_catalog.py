"""Catálogo de secções metálicas — HEA, HEB, IPE, UPN, RHS."""
from __future__ import annotations
import functools
from typing import Optional
from ..config import get_section_catalog
from ..enums import SectionFamily
from ..models import SteelSection
from ..exceptions import SectionNotFoundError


@functools.lru_cache(maxsize=16)
def _load_family(family: SectionFamily) -> list[SteelSection]:
    raw = get_section_catalog(family.value)
    sections = []
    for r in raw:
        r.setdefault("W_pl_z_cm3", r.get("W_pl_y_cm3", 0.0))
        r.setdefault("catalog_status", classify_section_for_fan_support(family, r))
        sections.append(SteelSection(family=family, **r))
    return sorted(sections, key=lambda s: s.weight_kgm)


def get_section(family: SectionFamily, designation: str) -> SteelSection:
    wanted = _normalise_designation(designation)
    for s in _load_family(family):
        if _normalise_designation(s.designation) == wanted:
            return s
    raise SectionNotFoundError(family.value, designation)


def _normalise_designation(designation: str) -> str:
    return designation.upper().replace(" ", "").replace("-", "")


def list_sections(family: SectionFamily) -> list[SteelSection]:
    return list(_load_family(family))


def list_selectable_sections(family: SectionFamily, include_hidden: bool = False) -> list[SteelSection]:
    """Return sections suitable for the default fan-support selector.

    The YAML catalog is preserved intact; this filter only prevents clearly
    disproportionate profiles from being proposed first for supports up to
    roughly 2 t. Hidden profiles remain available through explicit verify mode.
    """
    sections = _load_family(family)
    if include_hidden:
        return list(sections)
    return [s for s in sections if s.catalog_status != "hidden"]


def classify_section_for_fan_support(family: SectionFamily, row: dict) -> str:
    """Classify catalog rows without changing or inventing geometric properties."""
    weight = float(row.get("weight_kgm", 0.0) or 0.0)
    h_mm = float(row.get("h_mm", 0.0) or 0.0)

    if family == SectionFamily.HEB:
        if h_mm <= 160 and weight <= 45.0:
            return "acceptable"
        if h_mm <= 200 and weight <= 65.0:
            return "heavy"
        return "hidden"
    if family == SectionFamily.HEA:
        if h_mm <= 200 and weight <= 45.0:
            return "acceptable"
        if h_mm <= 240 and weight <= 65.0:
            return "heavy"
        return "hidden"
    if family == SectionFamily.IPE:
        if h_mm <= 220 and weight <= 30.0:
            return "recommended"
        if h_mm <= 300 and weight <= 45.0:
            return "acceptable"
        return "hidden"
    if family == SectionFamily.UPN:
        if h_mm <= 220 and weight <= 32.0:
            return "recommended"
        if h_mm <= 300 and weight <= 48.0:
            return "acceptable"
        return "hidden"
    if family == SectionFamily.RHS:
        if weight <= 30.0 and h_mm <= 200:
            return "recommended"
        if weight <= 50.0 and h_mm <= 250:
            return "acceptable"
        return "hidden"
    return "acceptable"


def section_catalog_rank(section: SteelSection) -> tuple[int, float, str, str]:
    status_rank = {
        "recommended": 0,
        "acceptable": 1,
        "heavy": 2,
        "hidden": 3,
    }.get(section.catalog_status, 1)
    return (status_rank, section.weight_kgm, section.family.value, section.designation)


def is_overdimensioned_choice(
    chosen: SteelSection,
    options: list[SteelSection],
    weight_ratio: float = 1.60,
) -> bool:
    """Return True if a chosen passing profile is much heavier than the lightest option."""
    if chosen.catalog_status in ("heavy", "hidden"):
        return True
    weights = [s.weight_kgm for s in options if s.weight_kgm > 0]
    if not weights or chosen.weight_kgm <= 0:
        return False
    return chosen.weight_kgm > min(weights) * weight_ratio


def find_minimum_section(
    family: SectionFamily,
    required_W_el_y_cm3: float,
    required_A_cm2: float = 0.0,
) -> Optional[SteelSection]:
    for s in _load_family(family):
        if s.W_el_y_cm3 >= required_W_el_y_cm3 and s.A_cm2 >= required_A_cm2:
            return s
    return None


def get_available_families() -> list[SectionFamily]:
    available = []
    for fam in [SectionFamily.HEA, SectionFamily.HEB, SectionFamily.IPE,
                SectionFamily.UPN, SectionFamily.RHS]:
        try:
            secs = _load_family(fam)
            if secs:
                available.append(fam)
        except Exception:
            pass
    return available
