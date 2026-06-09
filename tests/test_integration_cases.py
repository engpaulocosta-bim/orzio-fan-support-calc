"""Casos de integração E2E — input → run_full_calculation → ReportContext."""
import pytest
from sfsc.enums import (
    SupportType, Country, SteelGrade, SectionFamily, FanType,
    CantileverSubtype, FanConnectionType, AntiVibrationType,
    CheckerStatus, AnchorageSubstrate,
)
from sfsc.models import FanSupportInput, FanUnit
from sfsc.engines.selector import run_full_calculation, context_for_section_choice


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
    assert res.section_options
    assert all(opt.utilization_ratio <= 1.0 for opt in res.section_options)


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
    res = ctx.fan_support_result
    assert res.base_plate is not None
    assert res.base_plate.hole_diameter_mm > res.base_plate.bolt_diameter_mm
    assert res.base_plate.anchor_spacing_x_mm >= res.base_plate.min_spacing_mm
    assert res.base_plate.edge_distance_x_mm >= res.base_plate.min_edge_distance_mm
    assert res.base_plate.concrete_cone_capacity_kN > 0
    assert res.base_plate.pullout_capacity_kN > 0
    assert res.base_plate.pryout_capacity_kN > 0
    assert res.metal_connection is not None
    assert res.metal_connection.connection_type
    assert res.metal_connection.n_bolts >= 4
    assert res.metal_connection.weld_length_mm > 0
    assert res.metal_connection.utilization_ratio >= 0


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
    assert ctx.fan_support_result.metal_connection is not None
    assert ctx.fan_support_result.metal_connection.diagonal_member


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


def test_section_choice_rebuilds_report_context():
    inp = _make_inp(support_tag="CASE-11")
    ctx = run_full_calculation(inp)
    options = ctx.fan_support_result.section_options
    assert len(options) >= 2

    chosen = options[-1].section.designation
    chosen_ctx = context_for_section_choice(ctx, chosen)

    assert chosen_ctx.fan_support_input is inp
    assert chosen_ctx.fan_support_result.recommended_section.designation == chosen
    assert chosen_ctx.fan_support_result.section_options == options


def test_bracketed_cantilever_reports_diagonal_and_stiffener():
    inp = _make_inp(
        support_tag="CASE-12",
        support_type=SupportType.CANTILEVER_1,
        cantilever_subtype=CantileverSubtype.BRACKETED,
        installation_height_mm=600.0,
        span_mm=900.0,
    )
    ctx = run_full_calculation(inp)
    conn = ctx.fan_support_result.metal_connection
    assert conn is not None
    assert conn.diagonal_member
    assert conn.plate_thickness_mm >= 8.0
    assert conn.provided_spacing_mm >= conn.min_spacing_mm
    assert conn.provided_edge_distance_mm >= conn.min_edge_distance_mm


def test_steel_structure_anchorage_uses_bolted_connection_not_concrete_checks():
    inp = _make_inp(
        support_tag="CASE-13",
        support_type=SupportType.PEDESTAL,
        include_base_plate=True,
        fan_connection_type=FanConnectionType.FRAME_PLATFORM,
        anchorage_substrate=AnchorageSubstrate.STEEL_STRUCTURE,
    )
    ctx = run_full_calculation(inp)
    res = ctx.fan_support_result

    assert res.base_plate.anchorage_substrate == AnchorageSubstrate.STEEL_STRUCTURE
    assert res.base_plate.concrete_cone_capacity_kN == 0.0
    assert res.base_plate.utilization_concrete_cone == 0.0
    assert res.anchor.anchorage_substrate == AnchorageSubstrate.STEEL_STRUCTURE
    assert res.anchor.embedment_depth_mm == 0.0
    assert "estrutura metálica" in res.anchor.connector_label
    assert res.anchor.receiver_steel_grade == SteelGrade.S235
    assert res.anchor.receiver_plate_thickness_mm == 10.0
    assert res.anchor.utilization_bearing >= 0.0
    assert res.anchor.utilization_block_shear >= 0.0
    assert res.anchor.utilization_prying >= 0.0
    assert res.anchor.status in (CheckerStatus.PASS, CheckerStatus.MARGINAL, CheckerStatus.FAIL)


def test_weak_steel_receiver_returns_fail_instead_of_error():
    inp = _make_inp(
        support_tag="CASE-14",
        support_type=SupportType.PEDESTAL,
        include_base_plate=True,
        fan_connection_type=FanConnectionType.FRAME_PLATFORM,
        anchorage_substrate=AnchorageSubstrate.STEEL_STRUCTURE,
        receiver_plate_thickness_mm=3.0,
        receiver_edge_distance_mm=10.0,
        receiver_spacing_mm=20.0,
    )
    ctx = run_full_calculation(inp)
    res = ctx.fan_support_result

    assert res.anchor.status == CheckerStatus.FAIL
    assert res.status == CheckerStatus.FAIL
    assert res.anchor.utilization_tearout > 1.0 or res.anchor.utilization_block_shear > 1.0
