"""Testes da Fase 4 — verificação do perfil receptor (elemento hospedeiro).

Coberturas:
  1. Motor directo: `run_receiving_member_check` com esforços conhecidos → η analítico.
  2. Validação de forma fechada: corte puro → η = V_Ed / Vpl,Rd.
  3. Validação de forma fechada: flexão pura → η = M_Ed / Mpl,Rd.
  4. Torção: braço explícito → T_Ed = V·e; η_torção = T_Ed / Tt,pl,Rd.
  5. Torção: braço estimado (50 mm por defeito) + aviso.
  6. Falha η > 1.0: estado FAIL no breakdown.
  7. Integração selector: secção fornecida → `receiving_member_checked = True`.
  8. Integração selector: sem secção → NOT_CHECKED, aviso W-STEELFIX-RECEIVER.
  9. Integração selector: módulo desativado → breakdown NOT_CHECKED com chave disabled.
  10. `resolve_receiving_member_section`: HEB200, IPE300, secção inexistente.
  11. Modo não aço-aço: CONCRETE → breakdown NOT_CHECKED com chave notSteelFixation.
  12. Tipo de suporte não steel_fix: módulo NOT_CHECKED.
"""

from __future__ import annotations

import math

import pytest

from sfsc.catalogs.steel_section_catalog import get_section
from sfsc.engines.receiving_member import (
    resolve_receiving_member_section,
    run_receiving_member_check,
)
from sfsc.enums import (
    CheckStatus,
    ModuleId,
    SectionFamily,
    SteelGrade,
    SupportFixationMedium,
    SupportType,
)
from sfsc.models import (
    CalculationOptions,
    FanSupportInput,
    FanUnit,
    LoadCombination,
    SteelFixationInput,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _zero_combo(**overrides: float) -> LoadCombination:
    """Combinação de esforços com todos os valores zero, excepto os fornecidos."""
    return LoadCombination(
        name="ULS_fundamental",
        description="test",
        N_kN=overrides.get("N_kN", 0.0),
        V_y_kN=overrides.get("V_y_kN", 0.0),
        V_z_kN=overrides.get("V_z_kN", 0.0),
        M_y_kNm=overrides.get("M_y_kNm", 0.0),
        M_z_kNm=overrides.get("M_z_kNm", 0.0),
        T_kNm=overrides.get("T_kNm", 0.0),
    )


def _heb200() -> object:
    return get_section(SectionFamily.HEB, "HEB200")


def _steel_fix_input(
    section_id: str | None = "HEB200", material: str | None = None
) -> SteelFixationInput:
    return SteelFixationInput(
        receiving_member_section_id=section_id,
        receiving_member_material=material,
    )


def _platform_input(**kw: object) -> FanSupportInput:
    """Input mínimo de plataforma para integração com selector."""
    base: dict[str, object] = dict(
        support_type=SupportType.PLATFORM_FRAME_BRACED,
        support_tag="TEST-RECV",
        project_name="Fase4",
        platform_width_eff_mm=1500.0,
        platform_length_eff_mm=2000.0,
        platform_n_beams=2,
        platform_n_crossbeams=2,
        installation_height_mm=3000.0,
        span_mm=2000.0,
        support_fixation_medium=SupportFixationMedium.STEEL_STRUCTURE,
        steel_fixation=_steel_fix_input(),
        fan_units=[
            FanUnit(
                weight_kg=83.0,
                operating_weight_kg=90.0,
                footprint_length_mm=600.0,
                footprint_width_mm=600.0,
            )
        ],
        calculation_options=CalculationOptions(
            include_receiving_member=True,
        ),
    )
    base.update(kw)
    return FanSupportInput(**base)


# ── 1. Motor directo: corte puro ─────────────────────────────────────────────


def test_shear_only_closed_form() -> None:
    """η_corte = V_Ed / Vpl,Rd = V_Ed / (fy·Av / (√3·γM0))."""
    section = _heb200()
    fy = 355.0  # S355

    # Av ≈ h·tw
    Av_mm2 = section.h_mm * section.tw_mm
    Vpl_Rd = fy * Av_mm2 / (math.sqrt(3.0) * 1.0 * 1000.0)  # kN
    V_Ed = 0.3 * Vpl_Rd  # 30% da capacidade

    combo = _zero_combo(V_z_kN=V_Ed)
    result = run_receiving_member_check(
        section=section,
        steel_grade=SteelGrade.S355,
        combination=combo,
        torsion_lever_mm=1.0,  # braço mínimo para anular torção
    )

    assert result.solved
    assert not result.failed
    assert result.eta_shear == pytest.approx(V_Ed / Vpl_Rd, rel=0.02)
    assert result.eta_overall == pytest.approx(V_Ed / Vpl_Rd, rel=0.02)
    assert result.governing_check == "shear_z"


# ── 2. Flexão pura ────────────────────────────────────────────────────────────


def test_bending_y_only_closed_form() -> None:
    """η_flexão_y = M_Ed / Mpl_y,Rd = M_Ed / (fy·Wpl_y / γM0)."""
    section = _heb200()
    fy = 275.0  # S275

    Wpl_y_mm3 = section.W_pl_y_cm3 * 1000.0
    Mpl_y_Rd = fy * Wpl_y_mm3 / (1.0 * 1e6)  # kNm
    M_Ed = 0.6 * Mpl_y_Rd

    combo = _zero_combo(M_y_kNm=M_Ed)
    result = run_receiving_member_check(
        section=section,
        steel_grade=SteelGrade.S275,
        combination=combo,
        torsion_lever_mm=1.0,
    )

    assert result.solved
    assert result.eta_bending_y == pytest.approx(M_Ed / Mpl_y_Rd, rel=0.02)
    assert result.governing_check in ("bending_y", "interaction_nm")


# ── 3. Torção com braço explícito ─────────────────────────────────────────────


def test_torsion_explicit_lever() -> None:
    """T_Ed = V_Ed × e; η_torção = T_Ed / Tt,pl,Rd."""
    section = _heb200()
    fy = 355.0
    V_Ed = 20.0  # kN
    e_mm = 100.0  # braço explícito

    # Capacidade de torção de St. Venant
    tf = section.tf_mm
    tw = section.tw_mm
    b = section.b_mm
    h = section.h_mm
    hw = h - 2.0 * tf
    Wt_mm3 = 2.0 * b * tf**2 + hw * tw**2
    tau_rd = fy / (math.sqrt(3.0) * 1.0)
    Tt_pl_Rd = tau_rd * Wt_mm3 / 1e6  # kNm
    T_Ed = V_Ed * e_mm / 1000.0  # kNm
    eta_t_expected = T_Ed / Tt_pl_Rd

    combo = _zero_combo(V_z_kN=V_Ed)
    result = run_receiving_member_check(
        section=section,
        steel_grade=SteelGrade.S355,
        combination=combo,
        torsion_lever_mm=e_mm,
    )

    assert result.eta_torsion == pytest.approx(eta_t_expected, rel=0.02)
    assert result.intermediate["torsion_lever_mm"] == pytest.approx(e_mm, rel=1e-9)


# ── 4. Torção com braço estimado → aviso ─────────────────────────────────────


def test_torsion_estimated_lever_warning() -> None:
    """Sem braço fornecido → usa 50 mm e emite aviso."""
    section = _heb200()
    combo = _zero_combo(V_z_kN=10.0)
    result = run_receiving_member_check(
        section=section,
        steel_grade=SteelGrade.S355,
        combination=combo,
    )
    assert result.intermediate["torsion_lever_mm"] == pytest.approx(50.0)
    assert any("W-RECV-TORSION-LEVER" in w for w in result.warnings)


# ── 5. η > 1.0 → aviso de falha ──────────────────────────────────────────────


def test_overloaded_section_warning() -> None:
    """Quando η > 1.0 deve emitir aviso W-RECV-FAIL."""
    section = get_section(SectionFamily.IPE, "IPE160")  # secção mais fraca
    fy = 355.0
    Av_mm2 = section.h_mm * section.tw_mm
    Vpl_Rd = fy * Av_mm2 / (math.sqrt(3.0) * 1000.0)
    V_Ed = 2.0 * Vpl_Rd  # 200% → falha

    combo = _zero_combo(V_z_kN=V_Ed)
    result = run_receiving_member_check(
        section=section,
        steel_grade=SteelGrade.S355,
        combination=combo,
        torsion_lever_mm=1.0,
    )
    assert result.eta_overall > 1.0
    assert any("W-RECV-FAIL" in w for w in result.warnings)


# ── 6. resolve_receiving_member_section ───────────────────────────────────────


def test_resolve_heb200() -> None:
    s = resolve_receiving_member_section("HEB200")
    assert s is not None
    assert "200" in s.designation.upper()


def test_resolve_ipe300() -> None:
    s = resolve_receiving_member_section("IPE300")
    assert s is not None
    assert "300" in s.designation.upper()


def test_resolve_unknown_returns_none() -> None:
    s = resolve_receiving_member_section("XYZXYZ999")
    assert s is None


# ── 7. Integração selector: secção fornecida ─────────────────────────────────


def test_integration_section_provided_checked() -> None:
    """Com secção no catálogo: receiving_member_checked = True e módulo OK/FAIL."""
    from sfsc.engines.selector import run_full_calculation

    inp = _platform_input()
    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result
    assert result is not None

    rm_checks = [c for c in result.module_breakdown if c.id == ModuleId.RECEIVING_MEMBER]
    assert len(rm_checks) == 1
    rm = rm_checks[0]
    assert rm.status in (CheckStatus.OK, CheckStatus.MARGINAL, CheckStatus.FAIL)
    # A fixação deve indicar que o receptor foi verificado.
    assert result.steel_fixation is not None
    assert result.steel_fixation.receiving_member_checked is True


# ── 8. Integração selector: secção não fornecida ─────────────────────────────


def test_integration_no_section_not_checked() -> None:
    """Sem secção: NOT_CHECKED e aviso W-STEELFIX-RECEIVER."""
    from sfsc.engines.selector import run_full_calculation

    inp = _platform_input(
        steel_fixation=_steel_fix_input(section_id=None),
    )
    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result
    assert result is not None

    rm_checks = [c for c in result.module_breakdown if c.id == ModuleId.RECEIVING_MEMBER]
    assert len(rm_checks) == 1
    assert rm_checks[0].status == CheckStatus.NOT_CHECKED

    codes = [w.code for w in ctx.warnings]
    assert "W-STEELFIX-RECEIVER" in codes


# ── 9. Integração selector: módulo desativado ─────────────────────────────────


def test_integration_module_disabled() -> None:
    """Módulo desativado → NOT_CHECKED com chave 'disabled'."""
    from sfsc.engines.selector import run_full_calculation

    inp = _platform_input(
        calculation_options=CalculationOptions(include_receiving_member=False),
    )
    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result
    assert result is not None

    rm_checks = [c for c in result.module_breakdown if c.id == ModuleId.RECEIVING_MEMBER]
    assert len(rm_checks) == 1
    assert rm_checks[0].status == CheckStatus.NOT_CHECKED
    keys = [m.key for m in rm_checks[0].messages]
    assert any("disabled" in k for k in keys)


# ── 10. Fixação não em aço → notSteelFixation ─────────────────────────────────


def test_integration_concrete_fixation_not_applicable() -> None:
    """Fixação em betão → módulo NOT_CHECKED com chave notSteelFixation."""
    from sfsc.engines.selector import run_full_calculation

    inp = _platform_input(
        support_fixation_medium=SupportFixationMedium.CONCRETE,
        steel_fixation=None,
        calculation_options=CalculationOptions(include_receiving_member=True),
    )
    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result
    assert result is not None

    rm_checks = [c for c in result.module_breakdown if c.id == ModuleId.RECEIVING_MEMBER]
    assert len(rm_checks) == 1
    assert rm_checks[0].status == CheckStatus.NOT_CHECKED
    keys = [m.key for m in rm_checks[0].messages]
    assert any("notSteelFixation" in k for k in keys)


# ── 11. Interacção N+M ───────────────────────────────────────────────────────


def test_interaction_nm_dominates() -> None:
    """Axial + flexão combinados: η_nm = N/Npl + M/Mpl deve ser governante."""
    section = get_section(SectionFamily.IPE, "IPE160")
    fy = 355.0

    A_mm2 = section.A_cm2 * 100.0
    Npl_Rd = fy * A_mm2 / 1000.0
    Wpl_y_mm3 = section.W_pl_y_cm3 * 1000.0
    Mpl_y_Rd = fy * Wpl_y_mm3 / 1e6

    # 60% Npl + 60% Mpl → η_nm = 1.2 > 1.0
    N_Ed = 0.6 * Npl_Rd
    M_Ed = 0.6 * Mpl_y_Rd

    combo = _zero_combo(N_kN=N_Ed, M_y_kNm=M_Ed)
    result = run_receiving_member_check(
        section=section,
        steel_grade=SteelGrade.S355,
        combination=combo,
        torsion_lever_mm=1.0,
    )
    assert result.eta_interaction_nm == pytest.approx(0.6 + 0.6, rel=0.02)
    assert result.governing_check == "interaction_nm"
    assert result.eta_overall > 1.0
