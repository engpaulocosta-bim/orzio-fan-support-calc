"""Catálogo de graus de aço estrutural."""
from __future__ import annotations
from dataclasses import dataclass
from ..enums import SteelGrade, StructuralCode
from ..config import get_steel_grades_config
from ..exceptions import SteelGradeNotFoundError


@dataclass(frozen=True)
class SteelGradeSpec:
    key: str
    norm: str
    fy_mpa: float          # t ≤ 40 mm
    fu_mpa: float
    fy_thick_mpa: float    # t > 40 mm
    E_mpa: float = 210_000.0
    G_mpa: float = 81_000.0
    gamma_M0: float = 1.00
    gamma_M1: float = 1.00
    gamma_M2: float = 1.25


def get_grade_spec(grade: SteelGrade) -> SteelGradeSpec:
    raw = get_steel_grades_config().get("grades", {})
    g = raw.get(grade.value)
    if not g:
        raise SteelGradeNotFoundError(grade.value)
    return SteelGradeSpec(
        key=grade.value,
        norm=g["norm"],
        fy_mpa=g["fy_mpa"],
        fu_mpa=g["fu_mpa"],
        fy_thick_mpa=g.get("fy_thick_mpa", g["fy_mpa"]),
        E_mpa=g.get("E_mpa", 210_000.0),
        G_mpa=g.get("G_mpa", 81_000.0),
        gamma_M0=g.get("gamma_M0", 1.00),
        gamma_M1=g.get("gamma_M1", 1.00),
        gamma_M2=g.get("gamma_M2", 1.25),
    )


def design_strength(grade: SteelGrade, thickness_mm: float = 20.0) -> float:
    """Retorna fy/gamma_M0 [MPa]."""
    spec = get_grade_spec(grade)
    fy = spec.fy_mpa if thickness_mm <= 40.0 else spec.fy_thick_mpa
    return fy / spec.gamma_M0
