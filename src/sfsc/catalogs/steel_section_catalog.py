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
        sections.append(SteelSection(family=family, **r))
    return sorted(sections, key=lambda s: s.weight_kgm)


def get_section(family: SectionFamily, designation: str) -> SteelSection:
    for s in _load_family(family):
        if s.designation == designation:
            return s
    raise SectionNotFoundError(family.value, designation)


def list_sections(family: SectionFamily) -> list[SteelSection]:
    return list(_load_family(family))


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
