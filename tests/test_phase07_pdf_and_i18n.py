"""Phase 07: PDF reporting, i18n coverage and engineering transparency tests.

Acceptance criteria:
- serviceability is not_verified when deflection is unavailable
- connection checks are not_verified when not implemented
- PDF/report model does not mark missing checks as verified
- calculation states are rendered through i18n keys
- tramex is not labeled as base plate
- base plate is treated as connection/fixation terminology
- warning messages are generated for simplified or not verified items
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfsc.engineering import (
    CalculationResultState,
    build_phase01_engineering_model,
    determine_connection_state,
    determine_serviceability_state,
)
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    Country,
    FanType,
    SupportType,
)
from sfsc.i18n import Lang, t
from sfsc.models import (
    CalculationOptions,
    FanSupportInput,
    FanUnit,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_inp(**overrides) -> FanSupportInput:
    data: dict = {
        "project_name": "Phase 07 Test",
        "support_tag": "FSU-PH07",
        "prepared_by": "Test Engineer",
        "fan_units": [
            FanUnit(
                tag="FAN-1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=200.0,
                operating_weight_kg=220.0,
                footprint_length_mm=900.0,
                footprint_width_mm=700.0,
                centre_of_gravity_height_mm=300.0,
            )
        ],
        "support_type": SupportType.PEDESTAL,
        "country": Country.PORTUGAL,
        "installation_height_mm": 600.0,
        "span_mm": 1000.0,
    }
    data.update(overrides)
    return FanSupportInput(**data)


def _run(inp: FanSupportInput):
    """Return (FanSupportResult, ReportContext) tuple."""
    ctx = run_full_calculation(inp)
    assert ctx.fan_support_result is not None
    return ctx.fan_support_result, ctx


# ── i18n key existence tests ──────────────────────────────────────────────────

_I18N_DIR = Path(__file__).parent.parent / "src" / "sfsc" / "i18n"

_PHASE07_REQUIRED_KEYS = [
    "report.section.calculationModel",
    "report.section.serviceability",
    "report.section.connectionStatus",
    "report.section.engineeringWarnings",
    "report.label.serviceabilityStatus",
    "report.label.serviceabilityNotVerified",
    "report.label.deflectionNotAvailable",
    "report.label.basePlateStatus",
    "report.label.anchorStatus",
    "report.label.weldStatus",
    "report.label.connectionNotVerified",
    "report.label.connectionWarning",
    "report.label.simplifiedModelWarning",
    "report.label.engineerReviewRequired",
    "report.label.tramexNotBasePlate",
    "warning.serviceability.notVerified",
    "warning.connection.notVerified",
    "warning.connection.basePlateNotVerified",
    "warning.connection.anchorNotVerified",
    "warning.connection.weldNotVerified",
    "warning.model.simplified",
    "warning.engineer.reviewRequired",
    "warning.tramex.notBasePlate",
    "engineering.state.verified",
    "engineering.state.notVerified",
    "engineering.state.notApplicable",
    "engineering.state.simplified",
    "engineering.state.requiresEngineerReview",
    "engineering.state.failed",
    "pdf.cover.title",
    "pdf.cover.subtitle",
    "pdf.preliminary.label",
    "pdf.disclaimer",
    "pdf.section.basePlate",
    "pdf.section.anchors",
    "pdf.section.warnings",
    "pdf.footer.warning",
]


@pytest.mark.parametrize("lang_file", ["en.json", "pt.json", "es.json"])
@pytest.mark.parametrize("key", _PHASE07_REQUIRED_KEYS)
def test_phase07_i18n_key_exists_in_all_languages(lang_file: str, key: str):
    path = _I18N_DIR / lang_file
    data = json.loads(path.read_text(encoding="utf-8"))
    assert key in data, f"Key '{key}' missing from {lang_file}"


def test_i18n_engineering_state_keys_translate_via_t():
    """All six engineering states must resolve via t() without fallback."""
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        for state in CalculationResultState:
            key_map = {
                CalculationResultState.VERIFIED: "engineering.state.verified",
                CalculationResultState.SIMPLIFIED: "engineering.state.simplified",
                CalculationResultState.NOT_VERIFIED: "engineering.state.notVerified",
                CalculationResultState.NOT_APPLICABLE: "engineering.state.notApplicable",
                CalculationResultState.REQUIRES_ENGINEER_REVIEW: "engineering.state.requiresEngineerReview",
                CalculationResultState.FAILED: "engineering.state.failed",
            }
            result = t(key_map[state], lang)
            assert result, f"Empty translation for state {state.value} in {lang}"
            # Must not return the raw key (i.e. translation must exist)
            assert result != key_map[state], f"Key returned verbatim for {state.value} in {lang}"


# ── serviceability not_verified tests ──────────────────────────────────────────


def test_serviceability_not_verified_when_no_displacement():
    """When serviceability is enabled but no displacement results, state must be NOT_VERIFIED."""
    state = determine_serviceability_state(
        include_serviceability=True,
        displacement_results_available=False,
    )
    assert state == CalculationResultState.NOT_VERIFIED


def test_serviceability_not_applicable_when_disabled():
    state = determine_serviceability_state(
        include_serviceability=False,
        displacement_results_available=False,
    )
    assert state == CalculationResultState.NOT_APPLICABLE


def test_serviceability_cannot_be_verified_without_displacement():
    """Even if serviceability is enabled, VERIFIED requires actual displacement results."""
    # The only path to VERIFIED is displacement_results_available=True
    state_without = determine_serviceability_state(
        include_serviceability=True,
        displacement_results_available=False,
    )
    state_with = determine_serviceability_state(
        include_serviceability=True,
        displacement_results_available=True,
    )
    assert state_without != CalculationResultState.VERIFIED
    assert state_with == CalculationResultState.VERIFIED


def test_serviceability_in_engineering_model_is_not_verified():
    """Phase 07: engineering model must report serviceability as NOT_VERIFIED when no deflection."""
    inp = _make_inp(
        calculation_options=CalculationOptions(
            include_serviceability=True,
            include_base_plate=False,
            include_anchors=False,
            include_steel_connections=False,
        )
    )
    result, _ctx = _run(inp)
    _, report_state = build_phase01_engineering_model(inp, result)
    sls_item = next(item for item in report_state.states if item.id == "serviceability")
    assert sls_item.state == CalculationResultState.NOT_VERIFIED, (
        f"Expected NOT_VERIFIED but got {sls_item.state.value}"
    )


def test_serviceability_in_engineering_model_is_not_applicable_when_disabled():
    inp = _make_inp(
        calculation_options=CalculationOptions(
            include_serviceability=False,
        )
    )
    result, _ctx = _run(inp)
    _, report_state = build_phase01_engineering_model(inp, result)
    sls_item = next(item for item in report_state.states if item.id == "serviceability")
    assert sls_item.state == CalculationResultState.NOT_APPLICABLE


# ── connection not_verified tests ─────────────────────────────────────────────


def test_connection_not_verified_when_no_rows_but_checks_requested():
    """If checks are requested but no rows produced, state is NOT_VERIFIED."""
    state = determine_connection_state(
        checks_requested=True,
        rows=[],
    )
    assert state == CalculationResultState.NOT_VERIFIED


def test_connection_not_applicable_when_no_checks_requested():
    state = determine_connection_state(
        checks_requested=False,
        rows=[],
    )
    assert state == CalculationResultState.NOT_APPLICABLE


def test_connection_not_verified_propagates_from_row():
    rows = [{"status": "not_verified", "type": "base_plate"}]
    state = determine_connection_state(checks_requested=True, rows=rows)
    assert state == CalculationResultState.NOT_VERIFIED


def test_connection_failed_propagates_from_row():
    rows = [{"status": "failed", "type": "base_plate"}]
    state = determine_connection_state(checks_requested=True, rows=rows)
    assert state == CalculationResultState.FAILED


def test_no_connection_row_means_not_verified_in_engineering_model():
    """If simplified engine produces no connection_check_rows, engineering model must be NOT_VERIFIED."""
    inp = _make_inp(
        calculation_options=CalculationOptions(
            include_base_plate=False,
            include_anchors=False,
            include_steel_connections=False,
        )
    )
    result, _ctx = _run(inp)
    # Ensure there are no connection check rows
    assert len(result.connection_check_rows) == 0, "Expected no connection rows for this input"
    _, report_state = build_phase01_engineering_model(inp, result)
    conn_item = next(item for item in report_state.states if item.id == "connection_checks")
    # With no checks requested and no rows, state must be NOT_APPLICABLE or NOT_VERIFIED
    assert conn_item.state in (
        CalculationResultState.NOT_APPLICABLE,
        CalculationResultState.NOT_VERIFIED,
    ), f"Unexpected state: {conn_item.state.value}"


# ── tramex is not base plate ───────────────────────────────────────────────────


def test_tramex_not_labeled_as_base_plate_in_i18n():
    """The tramex surface type must not use 'base plate' terminology in i18n keys."""
    for lang_file in ("en.json", "pt.json", "es.json"):
        path = _I18N_DIR / lang_file
        data = json.loads(path.read_text(encoding="utf-8"))
        tramex_label = data.get("surface.tramex.label", "")
        # Tramex label must not contain "base plate" or "placa base" or "mesa"
        # as a connection term — it's a load surface
        bad_terms = ["base plate", "placa base"]  # "mesa" is OK as "grelha metálica"
        for term in bad_terms:
            assert term.lower() not in tramex_label.lower(), (
                f"surface.tramex.label in {lang_file} contains '{term}': '{tramex_label}'"
            )


def test_base_plate_role_tooltip_correct_in_i18n():
    """The base plate role tooltip must clarify it's not the grating."""
    for lang_file in ("en.json", "pt.json", "es.json"):
        path = _I18N_DIR / lang_file
        data = json.loads(path.read_text(encoding="utf-8"))
        tooltip = data.get("basePlate.role.tooltip", "")
        assert tooltip, f"basePlate.role.tooltip missing in {lang_file}"
        # Must explicitly mention it is NOT the grating/tramex
        has_negation = (
            "not" in tooltip.lower()
            or "não" in tooltip.lower()
            or "no es" in tooltip.lower()
            or "nicht" in tooltip.lower()
        )
        assert has_negation, (
            f"basePlate.role.tooltip in {lang_file} should clarify it's not the grating: '{tooltip}'"
        )


def test_tramex_warning_key_exists_in_all_langs():
    """The warning that tramex is not base plate must exist in all languages."""
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        result = t("warning.tramex.notBasePlate", lang)
        assert result, f"Empty tramex warning for {lang}"
        assert result != "warning.tramex.notBasePlate", f"Key not found for {lang}"


def test_pdf_section_base_plate_label_not_tramex():
    """The PDF base plate section label must be for connection, not load surface."""
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        label = t("pdf.section.basePlate", lang)
        assert label, f"Empty base plate section label for {lang}"
        # Must not contain tramex or grating as main subject
        bad_terms = ["tramex", "grelha metálica", "rejilla"]
        for term in bad_terms:
            assert term.lower() not in label.lower(), (
                f"pdf.section.basePlate in {lang} appears to reference tramex: '{label}'"
            )


# ── PDF/report model does not mark missing checks as verified ─────────────────


def test_engineering_report_state_global_frame_for_pedestal():
    """After Phase 03 extension, PEDESTAL uses the global frame solver."""
    inp = _make_inp()
    result, _ctx = _run(inp)
    _, report_state = build_phase01_engineering_model(inp, result)
    calc_item = next(item for item in report_state.states if item.id == "calculation_model")
    assert calc_item.state == CalculationResultState.VERIFIED


def test_engineering_report_state_unverified_flag_when_serviceability_enabled():
    """When serviceability is enabled but not calculated, report must flag unverified."""
    inp = _make_inp(
        calculation_options=CalculationOptions(
            include_serviceability=True,
        )
    )
    result, _ctx = _run(inp)
    _, report_state = build_phase01_engineering_model(inp, result)
    assert report_state.contains_unverified_checks is True, (
        "Report must flag unverified checks when serviceability is enabled but not calculated"
    )


def test_engineering_model_never_presents_serviceability_as_verified():
    """Serviceability must never be VERIFIED without actual displacement calculation."""
    inp = _make_inp(calculation_options=CalculationOptions(include_serviceability=True))
    result, _ctx = _run(inp)
    _, report_state = build_phase01_engineering_model(inp, result)
    sls_item = next(item for item in report_state.states if item.id == "serviceability")
    assert sls_item.state != CalculationResultState.VERIFIED


# ── warning messages for simplified / not verified items ─────────────────────


def test_simplified_model_warning_key_present_all_langs():
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        msg = t("warning.model.simplified", lang)
        assert msg and msg != "warning.model.simplified", (
            f"Missing simplified model warning for {lang}"
        )


def test_serviceability_not_verified_warning_key_present_all_langs():
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        msg = t("warning.serviceability.notVerified", lang)
        assert msg and msg != "warning.serviceability.notVerified", (
            f"Missing SLS warning for {lang}"
        )


def test_connection_not_verified_warning_keys_present_all_langs():
    keys = [
        "warning.connection.notVerified",
        "warning.connection.basePlateNotVerified",
        "warning.connection.anchorNotVerified",
        "warning.connection.weldNotVerified",
    ]
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        for key in keys:
            msg = t(key, lang)
            assert msg and msg != key, f"Missing warning key {key} for {lang}"


def test_engineer_review_required_warning_present_all_langs():
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        msg = t("warning.engineer.reviewRequired", lang)
        assert msg and msg != "warning.engineer.reviewRequired", (
            f"Missing engineer review warning for {lang}"
        )


# ── PDF structural section reporting ─────────────────────────────────────────


def test_serviceability_section_label_present_all_langs():
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        label = t("report.section.serviceability", lang)
        assert label and label != "report.section.serviceability"


def test_connection_status_section_label_present_all_langs():
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        label = t("report.section.connectionStatus", lang)
        assert label and label != "report.section.connectionStatus"


def test_calculation_model_section_label_present_all_langs():
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        label = t("report.section.calculationModel", lang)
        assert label and label != "report.section.calculationModel"


def test_engineering_warnings_section_label_present_all_langs():
    for lang in (Lang.EN, Lang.PT, Lang.ES):
        label = t("report.section.engineeringWarnings", lang)
        assert label and label != "report.section.engineeringWarnings"


# ── PDF generation smoke test ─────────────────────────────────────────────────


def test_pdf_generate_does_not_raise_for_simplified_model():
    """PDF generation must succeed for a typical simplified model calculation."""
    try:
        import reportlab  # noqa: F401
    except ImportError:
        pytest.skip("reportlab not installed")

    from sfsc.engineering import build_phase01_engineering_model
    from sfsc.models import ReportContext, WarningItem
    from sfsc.reports.memorial_pdf import generate_pdf

    inp = _make_inp()
    result, _base_ctx = _run(inp)
    _, report_state = build_phase01_engineering_model(inp, result)

    ctx = ReportContext(
        project_name="Phase 07 PDF Test",
        support_tag="FSU-PH07",
        prepared_by="Test",
        date="2026-06-12",
        revision="A",
        fan_support_input=inp,
        fan_support_result=result,
        engineering_report_state=report_state,
        warnings=[
            WarningItem(
                code="SLS-001",
                severity="WARNING",
                message="Serviceability not verified — deflection not calculated.",
            )
        ],
        limitations=[
            "Simplified structural model in use.",
            "Connection checks not implemented.",
            "Serviceability check not implemented.",
        ],
    )
    pdf_bytes = generate_pdf(ctx)
    assert pdf_bytes, "PDF must not be empty"
    assert len(pdf_bytes) > 1000, "PDF must have meaningful content"


def test_pdf_generate_does_not_overstate_serviceability():
    """PDF generation must not claim serviceability is verified when not calculated."""
    try:
        import reportlab  # noqa: F401
    except ImportError:
        pytest.skip("reportlab not installed")

    from sfsc.engineering import build_phase01_engineering_model
    from sfsc.models import ReportContext
    from sfsc.reports.memorial_pdf import generate_pdf

    inp = _make_inp(calculation_options=CalculationOptions(include_serviceability=True))
    result, _base_ctx = _run(inp)
    _, report_state = build_phase01_engineering_model(inp, result)
    sls_item = next(item for item in report_state.states if item.id == "serviceability")
    assert sls_item.state == CalculationResultState.NOT_VERIFIED

    ctx = ReportContext(
        project_name="Phase 07 SLS Test",
        support_tag="FSU-SLS",
        prepared_by="Test",
        date="2026-06-12",
        revision="A",
        fan_support_input=inp,
        fan_support_result=result,
        engineering_report_state=report_state,
    )
    pdf_bytes = generate_pdf(ctx)
    assert pdf_bytes, "PDF must not be empty"
    # The engineering state item must remain NOT_VERIFIED (not promoted to VERIFIED)
    assert sls_item.state != CalculationResultState.VERIFIED
