from sfsc.assessment import assess_result
from sfsc.enums import (
    CheckerStatus,
    SeismicCode,
    StructuralCode,
    SupportType,
)
from sfsc.models import AnchorResult, FanSupportResult, ReportContext
from sfsc.reports.exports import generate_csv


def _result(status: CheckerStatus, eta: float) -> FanSupportResult:
    return FanSupportResult(
        support_tag="FSU-T",
        support_type=SupportType.HANGER,
        structural_code=StructuralCode.EC3_EN1993,
        seismic_code=SeismicCode.EC8,
        seismic_factor_g=0.08,
        total_weight_kN=1.0,
        design_load_kN=1.5,
        anchor=AnchorResult(
            n_anchors=4,
            anchor_diameter_mm=12,
            embedment_depth_mm=90,
            tensile_capacity_kN=20,
            shear_capacity_kN=12,
            utilization_tension=eta * 0.50,
            utilization_shear=eta * 0.75,
            utilization_combined=eta,
            status=status,
        ),
        status=status,
    )


def test_assessment_reports_conservative_margin():
    assessment = assess_result(_result(CheckerStatus.PASS, 0.72))

    assert assessment.headline == "PASSA - CONSERVADOR"
    assert assessment.is_conservative
    assert assessment.conservatism_percent == 28.0
    assert assessment.limit_percent == 72.0


def test_assessment_reports_borderline_result():
    assessment = assess_result(_result(CheckerStatus.MARGINAL, 0.96))

    assert assessment.headline == "PASSA, MAS ESTÁ NO LIMITE"
    assert assessment.is_borderline
    assert assessment.conservatism_percent == 4.0


def test_assessment_reports_failure_result():
    assessment = assess_result(_result(CheckerStatus.FAIL, 1.08))

    assert assessment.headline == "NÃO PASSA"
    assert assessment.is_failure
    assert round(assessment.exceedance_percent, 1) == 8.0


def test_csv_exports_assessment_fields():
    result = _result(CheckerStatus.PASS, 0.72)
    csv_text = generate_csv(ReportContext(
        project_name="Project",
        support_tag="FSU-T",
        fan_support_result=result,
    ))

    assert "diagnosis,governing_item,governing_utilization_pct" in csv_text
    assert "PASSA - CONSERVADOR" in csv_text
    assert "Ancoragens" in csv_text
