"""Casos de integração E2E — input → run_full_calculation → ReportContext."""
import pytest
from sfsc.enums import (
    SupportType, Country, SteelGrade, SectionFamily, FanType,
    CantileverSubtype, FanConnectionType, AntiVibrationType,
    CheckerStatus,
)
from sfsc.models import FanSupportInput, FanUnit
from sfsc.engines.selector import run_full_calculation


def _make_inp(**kwargs):
    defaults = dict(
        project_name="IntegTest",
        support_tag="FSU-IT",
        fan_units=[FanUnit(fan_type=FanType.CENTRIFUGAL, weight_kg=120.0,
                           operating_weight_kg=130.0, footprint_length_mm=800.0,
                           footprint_width_mm=600.0)],
        support_type=SupportType.HANGER,
        country=Country.PORTUGAL,
        seismic_zone="1.3",
        steel_grade=SteelGrade.S355,
        preferred_section_families=[SectionFamily.HEB, SectionFamily.IPE],
        installation_height_mm=500.0,
        span_mm=1200.0,
    )
    defaults.update(kwargs)
    return FanSupportInput(**defaults)


# ── Caso 1: Hanger PT S355 ────────────────────────────────────────────────────
def test_case1_hanger_pt():
    inp = _make_inp(support_tag="CASE-1")
    ctx = run_full_calculation(inp)
    assert ctx.fan_support_result is not None
    res = ctx.fan_support_result
    assert res.recommended_section is not None
    assert res.section_verification is not None
    assert res.anchor is not None
    assert res.status in (CheckerStatus.PASS, CheckerStatus.MARGINAL)


# ── Caso 2: Cantilever 1 (puro) ES S275 ──────────────────────────────────────
def test_case2_cantilever1_pure_es():
    inp = _make_inp(
        support_tag="CASE-2",
        support_type=SupportType.CANTILEVER_1,
        cantilever_subtype=CantileverSubtype.PURE,
        country=Country.SPAIN,
        seismic_zone="B",
        steel_grade=SteelGrade.S275,
        span_mm=800.0,
    )
    ctx = run_full_calculation(inp)
    assert ctx.fan_support_result.recommended_section is not None


# ── Caso 3: Cantilever 1 (bracketed) PT S355 ─────────────────────────────────
def test_case3_cantilever1_bracketed():
    inp = _make_inp(
        support_tag="CASE-3",
        support_type=SupportType.CANTILEVER_1,
        cantilever_subtype=CantileverSubtype.BRACKETED,
        installation_height_mm=600.0,
        span_mm=700.0,
    )
    ctx = run_full_calculation(inp)
    assert ctx.fan_support_result is not None


# ── Caso 4: Pedestal Brasil NBR ───────────────────────────────────────────────
def test_case4_pedestal_brazil():
    inp = _make_inp(
        support_tag="CASE-4",
        support_type=SupportType.PEDESTAL,
        country=Country.BRAZIL,
        seismic_zone="II",
        steel_grade=SteelGrade.A36,
        span_mm=1000.0,
        fan_units=[FanUnit(fan_type=FanType.CENTRIFUGAL, weight_kg=280.0,
                           operating_weight_kg=300.0, footprint_length_mm=1000.0,
                           footprint_width_mm=800.0)],
    )
    ctx = run_full_calculation(inp)
    res = ctx.fan_support_result
    assert res is not None
    # Brasil → NBR_8800
    from sfsc.enums import StructuralCode
    assert res.structural_code == StructuralCode.NBR_8800


# ── Caso 5: Pedestal com mesa (base plate) ────────────────────────────────────
def test_case5_pedestal_with_base_plate():
    inp = _make_inp(
        support_tag="CASE-5",
        support_type=SupportType.PEDESTAL,
        include_base_plate=True,
        fan_connection_type=FanConnectionType.DIRECT_FLANGE,
        span_mm=1000.0,
    )
    ctx = run_full_calculation(inp)
    assert ctx.fan_support_result.base_plate is not None


# ── Caso 6: Combined Chile NCh ────────────────────────────────────────────────
def test_case6_combined_chile():
    inp = _make_inp(
        support_tag="CASE-6",
        support_type=SupportType.COMBINED,
        country=Country.CHILE,
        seismic_zone="2",
        span_mm=1500.0,
        fan_units=[FanUnit(fan_type=FanType.AXIAL, weight_kg=200.0,
                           operating_weight_kg=210.0, footprint_length_mm=900.0,
                           footprint_width_mm=700.0)],
    )
    ctx = run_full_calculation(inp)
    assert ctx.fan_support_result is not None


# ── Caso 7: Ventilador pesado (>500 kg) → REQUIRES_SPECIALIST ─────────────────
def test_case7_heavy_fan_requires_specialist():
    inp = _make_inp(
        support_tag="CASE-7",
        support_type=SupportType.CANTILEVER_3,
        span_mm=2000.0,
        installation_height_mm=1000.0,
        fan_units=[FanUnit(fan_type=FanType.CENTRIFUGAL, weight_kg=520.0,
                           operating_weight_kg=540.0, footprint_length_mm=1500.0,
                           footprint_width_mm=1200.0)],
    )
    ctx = run_full_calculation(inp)
    from sfsc.enums import ClassificationLevel
    assert ctx.fan_support_result.classification_level == ClassificationLevel.REQUIRES_SPECIALIST


# ── Caso 8: ReportContext tem citações e pressupostos ─────────────────────────
def test_case8_report_context_populated():
    inp = _make_inp(support_tag="CASE-8")
    ctx = run_full_calculation(inp)
    assert len(ctx.citations) >= 3
    assert len(ctx.assumptions_declared) >= 3
    assert len(ctx.limitations) >= 1
    assert ctx.date != ""


# ── Caso 9: Cantilever 2 (2 lados) UK ─────────────────────────────────────────
def test_case9_cantilever2_uk():
    inp = _make_inp(
        support_tag="CASE-9",
        support_type=SupportType.CANTILEVER_2,
        country=Country.UK,
        seismic_zone="UK",
    )
    ctx = run_full_calculation(inp)
    from sfsc.enums import StructuralCode
    assert ctx.fan_support_result.structural_code == StructuralCode.EC3_UK_NA


# ── Caso 10: Molas → aviso A-VIB-001 ─────────────────────────────────────────
def test_case10_springs_warning():
    inp = _make_inp(
        support_tag="CASE-10",
        support_type=SupportType.COMBINED,
        anti_vibration=AntiVibrationType.SPRINGS,
        anti_vibration_static_deflection_mm=25.0,
    )
    ctx = run_full_calculation(inp)
    codes = [w.code for w in ctx.warnings]
    assert "W-VIB-001" in codes
