from __future__ import annotations

import pytest

from sfsc.catalogs.steel_section_catalog import get_section
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    Country,
    FanType,
    ModuleId,
    OperationMode,
    SectionFamily,
    ServiceabilityLimit,
    SupportType,
)
from sfsc.models import CalculationOptions, FanSupportInput, FanUnit
from sfsc.section_orientation import get_local_section_axis_properties


def _hanger_input(**updates) -> FanSupportInput:
    data = {
        "project_name": "Phase 09",
        "support_tag": "FSU-PH09",
        "prepared_by": "Eng. Phase 09",
        "fan_units": [
            FanUnit(
                tag="FAN-1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=280.0,
                operating_weight_kg=300.0,
                footprint_length_mm=1000.0,
                footprint_width_mm=800.0,
                centre_of_gravity_height_mm=350.0,
            )
        ],
        "support_type": SupportType.HANGER,
        "operation_mode": OperationMode.VERIFY,
        "received_section_family": SectionFamily.HEB,
        "received_section_tag": "HEB200",
        "country": Country.PORTUGAL,
        "seismic_zone": "1.2",
        "installation_height_mm": 1200.0,
        "span_mm": 2000.0,
        "dynamic_factor": 1.0,
        "calculation_options": CalculationOptions(include_serviceability=True),
    }
    data.update(updates)
    return FanSupportInput(**data)


def test_serviceability_matches_closed_form_for_hanger_sls_deflection():
    ctx = run_full_calculation(_hanger_input())
    result = ctx.fan_support_result
    assert result is not None
    assert result.recommended_section is not None

    sls_combo = next(
        combo for combo in result.all_combinations if combo.name == "SLS_characteristic"
    )
    sls_check = next(
        check for check in result.module_breakdown if check.id == ModuleId.SERVICEABILITY
    )

    section = get_section(SectionFamily.HEB, "HEB200")
    oriented = get_local_section_axis_properties(section, 0.0)
    elastic_modulus_kN_m2 = 210_000.0 * 1_000.0
    inertia_m4 = oriented.local_iy_mm4 * 1e-12
    span_m = 2.0
    expected_deflection_m = (
        abs(sls_combo.V_z_kN) * span_m**3 / (48.0 * elastic_modulus_kN_m2 * inertia_m4)
    )
    expected_limit_m = span_m / 250.0
    expected_eta = expected_deflection_m / expected_limit_m

    assert result.recommended_section.designation == "HEB200"
    assert sls_check.status.value == "ok"
    assert sls_check.clause_refs == ["EN 1990 A1.4"]
    assert sls_check.inputs["limit_label"] == "L/250"
    assert sls_check.intermediate_values["max_vertical_deflection_m"] == pytest.approx(
        expected_deflection_m,
        rel=1e-4,
    )
    assert sls_check.intermediate_values["allowable_deflection_m"] == pytest.approx(
        expected_limit_m,
        rel=1e-8,
    )
    assert sls_check.eta == pytest.approx(round(expected_eta, 4), abs=1e-12)
    assert sls_check.intermediate_values["eta_els"] == pytest.approx(expected_eta, rel=1e-4)
    assert ctx.engineering_report_state.state_for("serviceability").state.value == "verified"


def test_serviceability_accepts_custom_deflection_limit():
    ctx = run_full_calculation(
        _hanger_input(
            calculation_options=CalculationOptions(
                include_serviceability=True,
                serviceability_limit=ServiceabilityLimit.CUSTOM,
                serviceability_custom_limit_divisor=300.0,
            )
        )
    )
    result = ctx.fan_support_result
    assert result is not None

    sls_check = next(
        check for check in result.module_breakdown if check.id == ModuleId.SERVICEABILITY
    )
    assert sls_check.inputs["limit_label"] == "L/300"
    assert sls_check.intermediate_values["allowable_deflection_m"] == pytest.approx(2.0 / 300.0)
