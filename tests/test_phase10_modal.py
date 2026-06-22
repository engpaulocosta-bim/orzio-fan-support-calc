"""Fase 3 — testes de análise modal e verificação de ressonância.

Validação de forma fechada:
  Viga biapoiada, vão L, massa central M:
    f1 = (1/2π) · √(48·E·I / (M·L³))

  A grelha reduz-se a este caso quando se usa 1 viga longitudinal
  com 2 nós de extremidade e 1 nó central, onde se aplica a massa
  do ventilador. A rigidez equivalente do vão é k = 48·E·I/L³.
"""

from __future__ import annotations

import math

import pytest

from sfsc.catalogs.steel_section_catalog import get_section
from sfsc.engines.global_frame import _section_torsion_constant_m4  # type: ignore[attr-defined]
from sfsc.engines.grillage import (
    GrillageMember,
    GrillageNode,
    GrillageSupport,
    build_grillage_stiffness,
)
from sfsc.engines.modal_analysis import RESONANCE_BAND_HIGH, RESONANCE_BAND_LOW, run_modal_analysis
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    Country,
    FanType,
    ModuleId,
    OperationMode,
    SectionFamily,
    SupportType,
)
from sfsc.models import CalculationOptions, FanSupportInput, FanUnit

# ── Helpers ──────────────────────────────────────────────────────────────────

_E_KN_M2 = 210_000.0 * 1_000.0  # kN/m²
_G_KN_M2 = 81_000.0 * 1_000.0  # kN/m²


def _simply_supported_beam_3nodes(
    span_m: float,
    section_tag: str = "HEB200",
) -> tuple[list[GrillageNode], list[GrillageMember], list[GrillageSupport], str, float]:
    """Return a 3-node simply-supported beam (A-C-B) as a grillage.

    Nó C (centro) é livre — permite massa vertical e verificação modal.
    """

    section = get_section(SectionFamily.HEB, section_tag)
    inertia_m4 = section.I_y_cm4 * 1e-8
    torsion_m4 = _section_torsion_constant_m4(section)

    nodes = [
        GrillageNode(id="A", x_m=0.0, y_m=0.0),
        GrillageNode(id="C", x_m=span_m / 2.0, y_m=0.0),
        GrillageNode(id="B", x_m=span_m, y_m=0.0),
    ]
    members = [
        GrillageMember(
            id="beam-left",
            node_i="A",
            node_j="C",
            elastic_modulus_kN_m2=_E_KN_M2,
            shear_modulus_kN_m2=_G_KN_M2,
            inertia_m4=inertia_m4,
            torsion_constant_m4=torsion_m4,
        ),
        GrillageMember(
            id="beam-right",
            node_i="C",
            node_j="B",
            elastic_modulus_kN_m2=_E_KN_M2,
            shear_modulus_kN_m2=_G_KN_M2,
            inertia_m4=inertia_m4,
            torsion_constant_m4=torsion_m4,
        ),
    ]
    supports = [
        GrillageSupport(node_id="A", w=True),
        GrillageSupport(node_id="B", w=True),
    ]
    return nodes, members, supports, section_tag, inertia_m4


# ── Testes unitários do motor modal ──────────────────────────────────────────


def test_modal_no_excitation_frequency_returns_not_solved():
    """Se não há frequência de excitação, o motor reporta falha sem crash."""

    nodes, members, supports, _, _ = _simply_supported_beam_3nodes(3.0)
    stiffness_result = build_grillage_stiffness(nodes, members, supports)
    assert stiffness_result is not None
    k_ff, free_dofs = stiffness_result

    result = run_modal_analysis(
        nodes=nodes,
        members=members,
        supports=supports,
        loaded_node_ids=["C"],
        stiffness_ff=k_ff,
        free_dofs=free_dofs,
        steel_density_kg_m3=7850.0,
        section_area_m2=78.08e-4,
        equipment_mass_kg=100.0,
        excitation_frequencies_hz=[],
    )
    assert not result.solved
    assert result.first_frequency_hz is None
    assert result.failure_reason == "modal_no_excitation_frequency"


def test_modal_simply_supported_beam_closed_form():
    """
    Viga biapoiada com massa central M: f1 = (1/2π)·√(48EI/(M·L³)).

    Usa 3 nós (A, C, B) com C no meio. A massa do ventilador vai para o nó C.
    A massa da estrutura é desprezável (densidade muito baixa) para comparar
    com a fórmula fechada que apenas usa a massa concentrada.
    """

    span_m = 4.0
    equipment_mass_kg = 500.0
    section = get_section(SectionFamily.HEB, "HEB200")
    inertia_m4 = section.I_y_cm4 * 1e-8
    torsion_m4 = _section_torsion_constant_m4(section)
    area_m2 = section.A_cm2 * 1e-4

    nodes = [
        GrillageNode(id="A", x_m=0.0, y_m=0.0),
        GrillageNode(id="C", x_m=span_m / 2, y_m=0.0),
        GrillageNode(id="B", x_m=span_m, y_m=0.0),
    ]
    members = [
        GrillageMember(
            id="beam-1-left",
            node_i="A",
            node_j="C",
            elastic_modulus_kN_m2=_E_KN_M2,
            shear_modulus_kN_m2=_G_KN_M2,
            inertia_m4=inertia_m4,
            torsion_constant_m4=torsion_m4,
        ),
        GrillageMember(
            id="beam-1-right",
            node_i="C",
            node_j="B",
            elastic_modulus_kN_m2=_E_KN_M2,
            shear_modulus_kN_m2=_G_KN_M2,
            inertia_m4=inertia_m4,
            torsion_constant_m4=torsion_m4,
        ),
    ]
    supports = [
        GrillageSupport(node_id="A", w=True),
        GrillageSupport(node_id="B", w=True),
    ]

    stiffness_result = build_grillage_stiffness(nodes, members, supports)
    assert stiffness_result is not None
    k_ff, free_dofs = stiffness_result

    excitation_hz = [5.0]  # far from f1 so resonance should NOT be violated
    result = run_modal_analysis(
        nodes=nodes,
        members=members,
        supports=supports,
        loaded_node_ids=["C"],
        stiffness_ff=k_ff,
        free_dofs=free_dofs,
        steel_density_kg_m3=0.001,  # near-zero to isolate equipment mass effect
        section_area_m2=area_m2,
        equipment_mass_kg=equipment_mass_kg,
        excitation_frequencies_hz=excitation_hz,
    )

    assert result.solved, f"Modal solver failed: {result.failure_reason}"
    assert result.first_frequency_hz is not None

    # Closed-form: f1 = (1/2π)·√(48·E·I/(M·L³))
    k_equiv_n_m = 48.0 * _E_KN_M2 * 1_000.0 * inertia_m4 / (span_m**3)
    f1_expected_hz = (1.0 / (2.0 * math.pi)) * math.sqrt(k_equiv_n_m / equipment_mass_kg)

    assert result.first_frequency_hz == pytest.approx(f1_expected_hz, rel=0.05), (
        f"f1={result.first_frequency_hz:.4f} Hz, expected {f1_expected_hz:.4f} Hz "
        f"(closed-form). Relative error: "
        f"{abs(result.first_frequency_hz - f1_expected_hz) / f1_expected_hz:.4%}"
    )


def test_resonance_band_violated_when_f1_inside_prohibited_zone():
    """f1 dentro de [0.7, 1.3]×f_exc deve dar resonance_violated=True."""

    nodes, members, supports, _, inertia_m4 = _simply_supported_beam_3nodes(4.0)
    stiffness_result = build_grillage_stiffness(nodes, members, supports)
    assert stiffness_result is not None
    k_ff, free_dofs = stiffness_result

    section = get_section(SectionFamily.HEB, "HEB200")
    area_m2 = section.A_cm2 * 1e-4

    # First probe to get f1.
    probe = run_modal_analysis(
        nodes=nodes,
        members=members,
        supports=supports,
        loaded_node_ids=["C"],
        stiffness_ff=k_ff,
        free_dofs=free_dofs,
        steel_density_kg_m3=7850.0,
        section_area_m2=area_m2,
        equipment_mass_kg=200.0,
        excitation_frequencies_hz=[99.0],  # far from resonance
    )
    assert probe.solved, f"Probe failed: {probe.failure_reason}"
    f1 = probe.first_frequency_hz
    assert f1 is not None

    # Set excitation exactly equal to f1 → ratio = 1.0, inside [0.7, 1.3] → should FAIL
    result_inside = run_modal_analysis(
        nodes=nodes,
        members=members,
        supports=supports,
        loaded_node_ids=["C"],
        stiffness_ff=k_ff,
        free_dofs=free_dofs,
        steel_density_kg_m3=7850.0,
        section_area_m2=area_m2,
        equipment_mass_kg=200.0,
        excitation_frequencies_hz=[f1],
    )
    assert result_inside.solved
    assert result_inside.resonance_violated, (
        f"Expected resonance violation when f_exc = f1 = {f1:.4f} Hz, "
        f"but got ratios={result_inside.frequency_ratios}"
    )
    assert result_inside.violated_excitation_hz == pytest.approx(f1, rel=1e-6)


def test_resonance_safe_when_f1_outside_prohibited_zone():
    """f1 bem acima de 1.3×f_exc não deve violar a faixa."""

    nodes, members, supports, _, _ = _simply_supported_beam_3nodes(1.0)
    stiffness_result = build_grillage_stiffness(nodes, members, supports)
    assert stiffness_result is not None
    k_ff, free_dofs = stiffness_result

    section = get_section(SectionFamily.HEB, "HEB200")
    area_m2 = section.A_cm2 * 1e-4

    # f_exc very low → f1/f_exc >> 1.3 → safe (over-tuned)
    result = run_modal_analysis(
        nodes=nodes,
        members=members,
        supports=supports,
        loaded_node_ids=["C"],
        stiffness_ff=k_ff,
        free_dofs=free_dofs,
        steel_density_kg_m3=7850.0,
        section_area_m2=area_m2,
        equipment_mass_kg=100.0,
        excitation_frequencies_hz=[0.1],  # 0.1 Hz → very low
    )
    assert result.solved
    assert not result.resonance_violated, (
        f"Did not expect resonance: f1={result.first_frequency_hz}, "
        f"ratios={result.frequency_ratios}"
    )


def test_resonance_band_constants_match_spec():
    """Garantir que os limites [0.7, 1.3] correspondem à decisão de engenharia."""

    assert RESONANCE_BAND_LOW == pytest.approx(0.7)
    assert RESONANCE_BAND_HIGH == pytest.approx(1.3)


# ── Testes de integração fim-a-fim ───────────────────────────────────────────


def _platform_grillage_input(**updates) -> FanSupportInput:
    """Input base com grelha 2.5D e velocidade de ventilador configurada."""

    data: dict[str, object] = {
        "project_name": "Phase 10 Modal",
        "support_tag": "FSU-PH10",
        "prepared_by": "Eng. Test Phase 10",
        "fan_units": [
            FanUnit(
                tag="FAN-1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=200.0,
                operating_weight_kg=250.0,
                footprint_length_mm=800.0,
                footprint_width_mm=600.0,
                centre_of_gravity_height_mm=300.0,
                speed_rpm=1450.0,  # ~24.2 Hz
            )
        ],
        "support_type": SupportType.PLATFORM_FRAME_BRACED,
        "operation_mode": OperationMode.VERIFY,
        "received_section_family": SectionFamily.HEB,
        "received_section_tag": "HEB200",
        "country": Country.PORTUGAL,
        "seismic_zone": "1.2",
        "installation_height_mm": 1200.0,
        "span_mm": 3000.0,
        "platform_n_beams": 2,
        "platform_n_crossbeams": 2,
        "platform_width_mm": 800.0,
        "dynamic_factor": 1.5,
        "calculation_options": CalculationOptions(
            include_modal_frequency=True,
        ),
    }
    data.update(updates)
    return FanSupportInput(**data)


def test_modal_module_appears_in_breakdown_when_enabled():
    """O módulo MODAL_FREQUENCY aparece no breakdown quando include_modal_frequency=True."""

    ctx = run_full_calculation(_platform_grillage_input())
    result = ctx.fan_support_result
    assert result is not None

    modal_check = next(
        (c for c in result.module_breakdown if c.id == ModuleId.MODAL_FREQUENCY),
        None,
    )
    assert modal_check is not None, "MODAL_FREQUENCY não encontrado no module_breakdown"


def test_modal_module_not_checked_when_disabled():
    """O módulo MODAL_FREQUENCY fica NOT_CHECKED quando include_modal_frequency=False."""

    from sfsc.enums import CheckStatus

    inp = _platform_grillage_input(
        calculation_options=CalculationOptions(include_modal_frequency=False)
    )
    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result
    assert result is not None

    modal_check = next(
        (c for c in result.module_breakdown if c.id == ModuleId.MODAL_FREQUENCY),
        None,
    )
    assert modal_check is not None
    assert modal_check.status == CheckStatus.NOT_CHECKED


def test_modal_frequency_derived_from_speed_rpm():
    """A frequência de excitação é derivada de speed_rpm quando não fornecida explicitamente."""

    ctx = run_full_calculation(_platform_grillage_input())
    result = ctx.fan_support_result
    assert result is not None

    modal_check = next(
        (c for c in result.module_breakdown if c.id == ModuleId.MODAL_FREQUENCY),
        None,
    )
    assert modal_check is not None
    # speed_rpm=1450 → f_exc = 1450/60 ≈ 24.17 Hz; should appear in inputs
    excitations = modal_check.inputs.get("excitation_frequencies_hz", [])
    assert isinstance(excitations, list)
    assert len(excitations) == 1
    assert excitations[0] == pytest.approx(1450.0 / 60.0, rel=1e-6)


def test_modal_explicit_excitation_frequency_overrides_rpm():
    """Quando excitation_frequency_hz é fornecido, prevalece sobre speed_rpm."""

    inp = _platform_grillage_input(
        calculation_options=CalculationOptions(
            include_modal_frequency=True,
            excitation_frequency_hz=10.0,
        )
    )
    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result
    assert result is not None

    modal_check = next(
        (c for c in result.module_breakdown if c.id == ModuleId.MODAL_FREQUENCY),
        None,
    )
    assert modal_check is not None
    excitations = modal_check.inputs.get("excitation_frequencies_hz", [])
    assert excitations == [pytest.approx(10.0)]


def test_modal_not_checked_when_no_excitation_source():
    """Sem speed_rpm nem excitation_frequency_hz → NOT_CHECKED com mensagem."""

    from sfsc.enums import CheckStatus

    inp = _platform_grillage_input(
        fan_units=[
            FanUnit(
                tag="FAN-1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=200.0,
                operating_weight_kg=250.0,
                footprint_length_mm=800.0,
                footprint_width_mm=600.0,
                centre_of_gravity_height_mm=300.0,
                speed_rpm=None,  # no rpm
            )
        ],
        calculation_options=CalculationOptions(include_modal_frequency=True),
    )
    ctx = run_full_calculation(inp)
    result = ctx.fan_support_result
    assert result is not None

    modal_check = next(
        (c for c in result.module_breakdown if c.id == ModuleId.MODAL_FREQUENCY),
        None,
    )
    assert modal_check is not None
    assert modal_check.status == CheckStatus.NOT_CHECKED
    assert any("noExcitationFrequency" in m.key for m in modal_check.messages)


def test_existing_412_tests_still_pass():
    """Smoke test: cálculo de suporte hanger básico sem análise modal ainda funciona."""

    inp = FanSupportInput(
        project_name="Phase 10 smoke",
        support_tag="FSU-SMOKE",
        prepared_by="Test",
        fan_units=[
            FanUnit(
                tag="F1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=150.0,
                operating_weight_kg=170.0,
                footprint_length_mm=600.0,
                footprint_width_mm=500.0,
                centre_of_gravity_height_mm=200.0,
            )
        ],
        support_type=SupportType.HANGER,
        operation_mode=OperationMode.VERIFY,
        received_section_family=SectionFamily.HEB,
        received_section_tag="HEB160",
        country=Country.PORTUGAL,
        seismic_zone="1.2",
        installation_height_mm=1000.0,
        span_mm=1500.0,
        dynamic_factor=1.5,
        calculation_options=CalculationOptions(include_modal_frequency=False),
    )
    ctx = run_full_calculation(inp)
    assert ctx.fan_support_result is not None
    assert ctx.fan_support_result.recommended_section is not None
