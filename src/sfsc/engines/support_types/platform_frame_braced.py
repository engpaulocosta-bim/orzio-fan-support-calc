"""PLATFORM_FRAME_BRACED - plataforma metálica com N vigas paralelas."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ...enums import CantileverSubtype, StructuralCode
from ...models import FanSupportInput, LoadCombination
from ...units import mm_to_m


@dataclass(frozen=True)
class PlatformBreakdown:
    """Esforços derivados do modelo de plataforma."""

    n_beams: int
    braced: bool
    load_per_beam_kN: float
    moment_per_beam_kNm: float
    axial_per_beam_kN: float
    diagonal_force_kN: float
    diagonal_angle_deg: float
    diagonal_length_mm: float
    Lcr_y_mm: float
    Lcr_z_mm: float


def _is_braced(inp: FanSupportInput) -> bool:
    return inp.cantilever_subtype is None or inp.cantilever_subtype == CantileverSubtype.BRACKETED


def _breakdown_for_combo(inp: FanSupportInput, combo: LoadCombination) -> PlatformBreakdown:
    length_mm = inp.platform_length_eff_mm
    length_m = mm_to_m(length_mm)
    height_mm = inp.installation_height_mm
    height_m = mm_to_m(height_mm)
    n_beams = max(2, inp.platform_n_beams)
    braced = _is_braced(inp)

    total_vertical_kN = abs(combo.V_z_kN)
    total_horizontal_kN = abs(combo.V_y_kN)
    load_per_beam_kN = total_vertical_kN / n_beams
    q_kN_m = load_per_beam_kN / length_m if length_m > 0 else 0.0
    moment_per_beam_kNm = q_kN_m * length_m**2 / 8.0
    moment_per_beam_kNm += (total_horizontal_kN * height_m) / n_beams if height_m > 0 else 0.0

    if braced:
        theta = math.atan2(height_m, length_m) if length_m > 0 else math.pi / 4.0
        reaction_tip_kN = 3.0 * q_kN_m * length_m / 8.0 if length_m > 0 else 0.0
        diagonal_force_kN = (
            reaction_tip_kN / math.sin(theta) if math.sin(theta) > 1e-6 else reaction_tip_kN
        )
        axial_per_beam_kN = reaction_tip_kN / math.tan(theta) if math.tan(theta) > 1e-6 else 0.0
        diagonal_length_mm = math.hypot(length_mm, height_mm)
        Lcr_y_mm = length_mm
        Lcr_z_mm = length_mm
    else:
        theta = 0.0
        diagonal_force_kN = 0.0
        axial_per_beam_kN = 0.0
        diagonal_length_mm = 0.0
        Lcr_y_mm = length_mm
        Lcr_z_mm = 0.5 * length_mm

    return PlatformBreakdown(
        n_beams=n_beams,
        braced=braced,
        load_per_beam_kN=round(load_per_beam_kN, 4),
        moment_per_beam_kNm=round(moment_per_beam_kNm, 4),
        axial_per_beam_kN=round(axial_per_beam_kN, 4),
        diagonal_force_kN=round(diagonal_force_kN, 4),
        diagonal_angle_deg=round(math.degrees(theta), 2),
        diagonal_length_mm=round(diagonal_length_mm, 1),
        Lcr_y_mm=Lcr_y_mm,
        Lcr_z_mm=Lcr_z_mm,
    )


def compute_platform_breakdown(
    inp: FanSupportInput, combinations: list[LoadCombination]
) -> PlatformBreakdown:
    """Return the governing platform breakdown among the supplied combinations."""
    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    return _breakdown_for_combo(inp, governing)


def _member_forces(inp: FanSupportInput, combo: LoadCombination) -> LoadCombination:
    breakdown = _breakdown_for_combo(inp, combo)
    length_m = mm_to_m(inp.platform_length_eff_mm)
    weak_axis_moment_kNm = abs(combo.V_y_kN) * length_m / (8.0 * breakdown.n_beams)

    desc = (
        f"Plataforma {breakdown.n_beams} vigas - "
        f"{'com mão-francesa' if breakdown.braced else 'sem mão-francesa'} - "
        f"P/viga={breakdown.load_per_beam_kN:.2f} kN "
        f"M/viga={breakdown.moment_per_beam_kNm:.2f} kNm"
    )
    if breakdown.braced:
        desc += (
            f" | diagonal θ={breakdown.diagonal_angle_deg:.1f}° "
            f"F_diag={breakdown.diagonal_force_kN:.2f} kN "
            f"N_viga={breakdown.axial_per_beam_kN:.2f} kN"
        )

    return LoadCombination(
        name=combo.name,
        N_kN=breakdown.axial_per_beam_kN,
        V_z_kN=breakdown.load_per_beam_kN / 2.0,
        V_y_kN=combo.V_y_kN / breakdown.n_beams,
        M_y_kNm=breakdown.moment_per_beam_kNm,
        M_z_kNm=weak_axis_moment_kNm,
        T_kNm=combo.T_kNm / breakdown.n_beams,
        member_level=True,
        load_factors_used={
            **combo.load_factors_used,
            "n_beams": breakdown.n_beams,
            "load_per_beam_kN": breakdown.load_per_beam_kN,
            "diagonal_force_kN": breakdown.diagonal_force_kN,
        },
        description=desc,
    )


def calc_platform_frame_braced(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[list[LoadCombination], float, float]:
    """Transform action combinations into member-level forces for one platform beam."""
    del total_weight_kN, code
    member_combos = [_member_forces(inp, combo) for combo in combinations]
    governing = compute_platform_breakdown(inp, combinations)
    return member_combos, governing.Lcr_y_mm, governing.Lcr_z_mm
