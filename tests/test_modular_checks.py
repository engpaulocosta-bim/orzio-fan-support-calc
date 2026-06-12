"""Testes da refatoração modular (tarefa — secção 8).

Cobre: diagnóstico global por módulo, contradição da base plate, fixação
betão vs estrutura metálica, módulos opcionais, benchmark Robot, novo tipo
de suporte e separação tramex/base plate.
"""

import pytest

from sfsc.checks import AggregateResult, CheckResult, aggregate_results, classify_eta
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    BasePlateRole,
    CalculationMode,
    CantileverSubtype,
    CheckStatus,
    Country,
    FanConnectionType,
    FanType,
    ModuleId,
    SupportFixationMedium,
    SupportType,
    WalkingSurfaceType,
)
from sfsc.models import (
    CalculationOptions,
    FanSupportInput,
    FanUnit,
    SteelFixationInput,
    WalkingSurface,
)


def _mk(**kw):
    d = dict(
        project_name="Mod",
        support_tag="FSU-M",
        prepared_by="Eng",
        fan_units=[
            FanUnit(
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=280.0,
                operating_weight_kg=300.0,
                footprint_length_mm=1000.0,
                footprint_width_mm=800.0,
                centre_of_gravity_height_mm=350.0,
            )
        ],
        support_type=SupportType.PEDESTAL,
        country=Country.PORTUGAL,
        seismic_zone="1.2",
        installation_height_mm=700.0,
        span_mm=1100.0,
    )
    d.update(kw)
    return FanSupportInput(**d)


def _module(res, module_id: ModuleId) -> CheckResult:
    return next(c for c in res.module_breakdown if c.id == module_id)


# ── 8.1 Diagnóstico global ──────────────────────────────────────────────────


def test_aggregator_marginal_base_plate_makes_global_marginal():
    checks = [
        CheckResult(id=ModuleId.STEEL_SECTION, label_key="x", eta=0.534, status=CheckStatus.OK),
        CheckResult(id=ModuleId.BASE_PLATE, label_key="x", eta=0.933, status=CheckStatus.MARGINAL),
        CheckResult(id=ModuleId.CONCRETE_ANCHORS, label_key="x", eta=0.583, status=CheckStatus.OK),
    ]
    agg = aggregate_results(checks)
    assert agg.global_status == CheckStatus.MARGINAL
    assert agg.governing_module == ModuleId.BASE_PLATE
    assert agg.governing_eta == pytest.approx(0.933)


def test_aggregator_not_checked_cannot_govern():
    checks = [
        CheckResult(id=ModuleId.STEEL_SECTION, label_key="x", eta=0.4, status=CheckStatus.OK),
        CheckResult(
            id=ModuleId.BASE_PLATE, label_key="x", eta=None, status=CheckStatus.NOT_CHECKED
        ),
    ]
    agg = aggregate_results(checks)
    assert agg.governing_module == ModuleId.STEEL_SECTION
    assert not _find(agg, ModuleId.BASE_PLATE).governing


def test_aggregator_any_fail_is_global_fail():
    checks = [
        CheckResult(id=ModuleId.STEEL_SECTION, label_key="x", eta=0.4, status=CheckStatus.OK),
        CheckResult(id=ModuleId.CONCRETE_ANCHORS, label_key="x", eta=1.2, status=CheckStatus.FAIL),
    ]
    assert aggregate_results(checks).global_status == CheckStatus.FAIL


def test_classify_eta_thresholds():
    assert classify_eta(0.84) == CheckStatus.OK
    assert classify_eta(0.85) == CheckStatus.MARGINAL
    assert classify_eta(1.0) == CheckStatus.MARGINAL
    assert classify_eta(1.01) == CheckStatus.FAIL
    assert classify_eta(None) == CheckStatus.NOT_CHECKED


def test_disabled_base_plate_not_governing_in_pipeline():
    opts = CalculationOptions(include_base_plate=False)
    res = run_full_calculation(_mk(calculation_options=opts)).fan_support_result
    bp = _module(res, ModuleId.BASE_PLATE)
    assert bp.status == CheckStatus.NOT_CHECKED
    assert not bp.governing


# ── 8.2 Base plate contraditória ────────────────────────────────────────────


def test_base_plate_below_constructive_is_coherent():
    """t_user < mínimo construtivo mas η ≤ 1: MARGINAL com mensagem coerente,
    NUNCA 'passa' + 'não verifica' em simultâneo (tarefa 1.2)."""
    res = run_full_calculation(
        _mk(
            include_base_plate=True,
            fan_connection_type=FanConnectionType.DIRECT_FLANGE,
            base_plate_thickness_mm=5.0,
        )
    ).fan_support_result
    bp = res.base_plate
    assert bp.utilization_bending <= 1.0
    assert bp.status.value == "MARGINAL"
    # Não pode existir a mensagem contraditória antiga.
    assert not any("não verifica" in w for w in bp.warnings)
    assert any("mínimo construtivo" in w for w in bp.warnings)


def test_base_plate_adequate_thickness_passes():
    res = run_full_calculation(
        _mk(
            include_base_plate=True,
            fan_connection_type=FanConnectionType.DIRECT_FLANGE,
            base_plate_thickness_mm=20.0,
        )
    ).fan_support_result
    assert res.base_plate.status.value in ("PASS", "MARGINAL")
    assert not any("mínimo construtivo" in w for w in res.base_plate.warnings)


# ── 8.3 Fixação betão vs estrutura metálica ─────────────────────────────────


def test_concrete_fixation_has_anchors():
    res = run_full_calculation(
        _mk(support_fixation_medium=SupportFixationMedium.CONCRETE)
    ).fan_support_result
    assert res.anchor is not None
    assert res.steel_fixation is None
    assert _module(res, ModuleId.CONCRETE_ANCHORS).status != CheckStatus.NOT_CHECKED


def test_steel_fixation_disables_concrete_anchors():
    res = run_full_calculation(
        _mk(
            support_fixation_medium=SupportFixationMedium.STEEL_STRUCTURE,
            steel_fixation=SteelFixationInput(bolt_diameter_mm=16.0, number_of_bolts=4),
        )
    ).fan_support_result
    assert res.anchor is None  # sem cone de betão
    assert res.steel_fixation is not None
    assert _module(res, ModuleId.CONCRETE_ANCHORS).status == CheckStatus.NOT_CHECKED
    assert _module(res, ModuleId.STEEL_CONNECTIONS).eta is not None


def test_steel_fixation_warns_receiving_member_not_checked():
    ctx = run_full_calculation(_mk(support_fixation_medium=SupportFixationMedium.STEEL_STRUCTURE))
    assert any(w.code == "W-STEELFIX-RECEIVER" for w in ctx.warnings)
    assert ctx.fan_support_result.steel_fixation.receiving_member_checked is False


# ── 8.5 Benchmark Robot ─────────────────────────────────────────────────────


def test_robot_benchmark_excludes_modules():
    res = run_full_calculation(
        _mk(
            calculation_mode=CalculationMode.ROBOT_BENCHMARK,
            include_base_plate=True,
            fan_connection_type=FanConnectionType.DIRECT_FLANGE,
        )
    ).fan_support_result
    assert res.base_plate is None
    assert res.anchor is None
    assert res.metal_connection is None
    # Sem sísmica: a fundamental governa (não a combinação sísmica).
    assert res.governing_load_combination.name == "ULS_fundamental"


def test_full_design_includes_modules_per_options():
    res = run_full_calculation(
        _mk(
            calculation_mode=CalculationMode.FULL_PRELIMINARY_DESIGN,
            include_base_plate=True,
            fan_connection_type=FanConnectionType.DIRECT_FLANGE,
        )
    ).fan_support_result
    assert res.base_plate is not None
    assert res.anchor is not None
    assert res.metal_connection is not None


def test_options_fingerprint_in_provenance_changes_with_options():
    ctx_a = run_full_calculation(
        _mk(calculation_options=CalculationOptions(include_base_plate=True))
    )
    ctx_b = run_full_calculation(
        _mk(calculation_options=CalculationOptions(include_base_plate=False))
    )
    fa = ctx_a.dataset_provenance["options_fingerprint"]
    fb = ctx_b.dataset_provenance["options_fingerprint"]
    assert fa != fb


def test_dynamic_factor_toggle_changes_loads():
    res_on = run_full_calculation(
        _mk(calculation_options=CalculationOptions(include_dynamic_factor=True))
    ).fan_support_result
    res_off = run_full_calculation(
        _mk(calculation_options=CalculationOptions(include_dynamic_factor=False))
    ).fan_support_result
    assert res_off.design_load_kN < res_on.design_load_kN


def test_ltb_toggle_changes_section_checks():
    on = run_full_calculation(
        _mk(
            support_type=SupportType.CANTILEVER_1,
            cantilever_subtype=CantileverSubtype.PURE,
            span_mm=800.0,
            calculation_options=CalculationOptions(include_lateral_torsional_buckling=True),
        )
    ).fan_support_result
    off = run_full_calculation(
        _mk(
            support_type=SupportType.CANTILEVER_1,
            cantilever_subtype=CantileverSubtype.PURE,
            span_mm=800.0,
            calculation_options=CalculationOptions(include_lateral_torsional_buckling=False),
        )
    ).fan_support_result
    assert "ltb" in on.section_verification.utilization_by_check
    assert "ltb" not in off.section_verification.utilization_by_check


# ── Novo tipo de suporte + tramex ───────────────────────────────────────────


def test_platform_frame_braced_runs():
    res = run_full_calculation(
        _mk(
            support_type=SupportType.PLATFORM_FRAME_BRACED,
            walking_surface=WalkingSurface(
                surface_type=WalkingSurfaceType.STEEL_GRATING_TRAMEX, self_weight_kn_m2=0.45
            ),
        )
    ).fan_support_result
    assert res.recommended_section is not None
    surf = _module(res, ModuleId.LOAD_DISTRIBUTION_SURFACE)
    assert surf.status == CheckStatus.INFORMATIVE


def test_tramex_does_not_activate_base_plate():
    """Tramex é superfície de distribuição, não base plate (tarefa 1.4/secção 10)."""
    res = run_full_calculation(
        _mk(
            support_type=SupportType.PLATFORM_FRAME_BRACED,
            walking_surface=WalkingSurface(surface_type=WalkingSurfaceType.STEEL_GRATING_TRAMEX),
            base_plate_role=BasePlateRole.NONE,
        )
    ).fan_support_result
    assert res.base_plate is None
    assert _module(res, ModuleId.BASE_PLATE).status == CheckStatus.NOT_CHECKED


def _find(agg: AggregateResult, module_id: ModuleId) -> CheckResult:
    return next(c for c in agg.checks if c.id == module_id)


# ── UI: novos elementos expostos ────────────────────────────────────────────


def test_ui_exposes_platform_type_and_module_toggles():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()
    assert not app.exception
    tipo = [s for s in app.selectbox if s.label == "Tipo"]
    assert tipo
    assert any("platform" in str(o).lower() for o in tipo[0].options)
    toggles = [c.label for c in app.checkbox]
    assert any("dinâmico" in tlabel.lower() or "Fator" in tlabel for tlabel in toggles)


def test_ui_module_breakdown_table_after_calc():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()
    eng = [f for f in app.text_input if "Engenheiro" in f.label]
    if eng:
        eng[0].set_value("Eng Teste")
    calc = [b for b in app.button if "Calcular" in b.label][0]
    calc.click()
    app.run()
    assert not app.exception
    assert len(app.metric) > 0
    # A tabela de módulos é um dataframe adicional.
    assert len(app.dataframe) >= 1


def test_pdf_contains_module_summary():
    import base64
    import re
    import zlib

    from sfsc.reports.memorial_pdf import generate_pdf

    def _pdf_text(pdf_bytes):
        text = b""
        for m in re.finditer(rb"(?<!end)stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL):
            data = m.group(1).strip()
            try:
                text += zlib.decompress(base64.a85decode(data, adobe=True))
            except Exception:
                pass
        return text

    ctx = run_full_calculation(
        _mk(include_base_plate=True, fan_connection_type=FanConnectionType.DIRECT_FLANGE)
    )
    pdf = _pdf_text(generate_pdf(ctx))
    assert b"final por m" in pdf.lower() or b"Verifica" in pdf  # "Verificação final por módulo"
