"""Testes do tipo de suporte PLATFORM (plataforma / mesa de grelha).

Caso de referência real: 4 ventiladores France Air de 83 kg sobre uma mesa de
grelha (3 vigas + tramex 3 mm) engastada num bordo e escorada por mãos-francesas.
"""
import pytest

from sfsc.enums import (
    CantileverSubtype, Country, SectionFamily, SteelGrade, StructuralCode,
    SupportType,
)
from sfsc.engines.loads import calculate_loads
from sfsc.engines.selector import run_full_calculation
from sfsc.engines.support_types.platform import compute_platform_breakdown
from sfsc.models import FanSupportInput, FanUnit


def _france_air_units(n=4, kg=83.0):
    return [
        FanUnit(
            tag=f"V{i+1}",
            weight_kg=kg,
            operating_weight_kg=kg,
            footprint_length_mm=760.0,
            footprint_width_mm=760.0,
            centre_of_gravity_height_mm=300.0,
        )
        for i in range(n)
    ]


def _platform_inp(subtype=CantileverSubtype.BRACKETED, n_beams=3):
    return FanSupportInput(
        project_name="Caso real France Air",
        support_tag="FSU-REAL",
        fan_units=_france_air_units(),
        support_type=SupportType.PLATFORM,
        cantilever_subtype=subtype,
        country=Country.EU_GENERIC,
        steel_grade=SteelGrade.S235,
        preferred_section_families=[SectionFamily.IPE, SectionFamily.UPN, SectionFamily.HEA],
        installation_height_mm=1000.0,
        span_mm=2000.0,
        platform_n_beams=n_beams,
        platform_width_mm=2425.0,
        platform_length_mm=2000.0,
        platform_grating_kg_m2=30.0,
    )


def test_self_weight_counts_tramex_and_steel():
    """O peso próprio da plataforma inclui tramex (por área) + aço, não o chute de 15%."""
    inp = _platform_inp()
    G_kN, _ = calculate_loads(inp, StructuralCode.EC3_EN1993, 0.10)
    # Equipamento: 4×83 kg ≈ 3.26 kN. Tramex (2.0×2.425 m × 30 kg/m² ≈ 145 kg) ≈ 1.4 kN.
    # G total tem de ser claramente acima do equipamento sozinho.
    G_equipment = 4 * 83 * 9.80665 / 1000.0
    assert G_kN > G_equipment * 1.3  # tramex + aço somam bem mais que 15%


def test_load_shared_across_beams():
    """Mais vigas → menos momento por viga (a carga reparte-se)."""
    bd2 = compute_platform_breakdown(
        _platform_inp(n_beams=2),
        calculate_loads(_platform_inp(n_beams=2), StructuralCode.EC3_EN1993, 0.10)[1],
    )
    bd4 = compute_platform_breakdown(
        _platform_inp(n_beams=4),
        calculate_loads(_platform_inp(n_beams=4), StructuralCode.EC3_EN1993, 0.10)[1],
    )
    assert bd4.load_per_beam_kN < bd2.load_per_beam_kN
    assert bd4.moment_per_beam_kNm < bd2.moment_per_beam_kNm


def test_min_two_beams_enforced():
    bd = compute_platform_breakdown(
        _platform_inp(n_beams=2),
        calculate_loads(_platform_inp(n_beams=2), StructuralCode.EC3_EN1993, 0.10)[1],
    )
    assert bd.n_beams == 2


def test_bracketed_has_diagonal_pure_does_not():
    braced = run_full_calculation(_platform_inp(CantileverSubtype.BRACKETED)).fan_support_result
    pure = run_full_calculation(_platform_inp(CantileverSubtype.PURE)).fan_support_result

    assert braced.platform is not None and braced.platform.diagonal is not None
    assert braced.platform.diagonal.axial_force_kN > 0
    assert braced.platform.braced is True

    assert pure.platform is not None and pure.platform.diagonal is None
    assert pure.platform.braced is False
    # Sem diagonal não há compressão induzida nas vigas.
    assert pure.platform.axial_per_beam_kN == 0.0


def test_real_case_is_conservative_with_three_ipe():
    """O caso real (3 vigas, carga leve) deve passar com folga — está sobredimensionado."""
    res = run_full_calculation(_platform_inp(n_beams=3)).fan_support_result
    assert res.recommended_section is not None
    # Um IPE leve já chega; a utilização governante é baixa.
    assert res.section_verification.utilization_ratio < 0.5
    assert res.status.value == "PASS"
    # A diagonal também verifica.
    assert res.platform.diagonal.status.value == "PASS"


def test_platform_breakdown_consistency():
    inp = _platform_inp()
    _, combos = calculate_loads(inp, StructuralCode.EC3_EN1993, 0.10)
    bd = compute_platform_breakdown(inp, combos)
    # A diagonal a θ = atan(1000/2000) ≈ 26.6°.
    assert 25.0 < bd.diagonal_angle_deg < 28.0
    # Comprimento da diagonal = hypot(2000, 1000) ≈ 2236 mm.
    assert 2200 < bd.diagonal_length_mm < 2270
