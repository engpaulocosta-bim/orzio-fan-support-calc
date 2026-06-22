import pytest

from sfsc.engineering import CalculationResultState
from sfsc.engines.load_surfaces import build_load_path_summary
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    Country,
    FanType,
    LoadCaseName,
    LoadDirection,
    LoadDistributionMethod,
    ManualLoadType,
    SupportType,
    WalkingSurfaceType,
)
from sfsc.models import FanSupportInput, FanUnit, ManualLoad, WalkingSurface
from sfsc.reports.export_json import export_report_dict


def _platform_input(**updates) -> FanSupportInput:
    data = {
        "project_name": "Phase 02",
        "support_tag": "FSU-PH02",
        "prepared_by": "Eng. Phase 02",
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
        "support_type": SupportType.PLATFORM_FRAME_BRACED,
        "country": Country.PORTUGAL,
        "seismic_zone": "1.2",
        "installation_height_mm": 900.0,
        "span_mm": 2000.0,
        "platform_n_beams": 2,
        "platform_width_mm": 2000.0,
        "platform_length_mm": 2000.0,
        "walking_surface": WalkingSurface(
            surface_type=WalkingSurfaceType.STEEL_GRATING_TRAMEX,
            self_weight_kn_m2=0.50,
            imposed_load_kn_m2=1.00,
            distribution_method=LoadDistributionMethod.ONE_WAY,
        ),
    }
    data.update(updates)
    return FanSupportInput(**data)


def test_area_load_distribution_creates_traceable_line_loads():
    summary = build_load_path_summary(_platform_input())

    assert len(summary.surface_components) == 2
    assert summary.vertical_totals_by_case["G"] == pytest.approx(2.0)
    assert summary.vertical_totals_by_case["Q"] == pytest.approx(4.0)

    self_weight_lines = [
        item for item in summary.distributed_line_loads if item["source"] == "surface_self_weight"
    ]
    imposed_lines = [
        item for item in summary.distributed_line_loads if item["source"] == "surface_imposed"
    ]

    assert len(self_weight_lines) == 2
    assert len(imposed_lines) == 2
    assert self_weight_lines[0]["line_load_kN_m"] == pytest.approx(0.5)
    assert self_weight_lines[0]["total_load_kN"] == pytest.approx(1.0)
    assert imposed_lines[0]["line_load_kN_m"] == pytest.approx(1.0)
    assert imposed_lines[0]["target_member"] == "beam_1"


def test_manual_load_without_target_requires_engineer_review():
    inp = _platform_input(
        manual_loads=[
            ManualLoad(
                name="walkway_patch",
                load_type=ManualLoadType.POINT,
                load_case=LoadCaseName.MANUAL,
                direction=LoadDirection.GLOBAL_Z,
                value=2.5,
            )
        ]
    )

    summary = build_load_path_summary(inp)
    ctx = run_full_calculation(inp)

    assert summary.requires_engineer_review is True
    assert ctx.engineering_report_state.state_for("load_surfaces").state == (
        CalculationResultState.REQUIRES_ENGINEER_REVIEW
    )


def test_manual_area_load_is_exported_and_distributed():
    inp = _platform_input(
        manual_loads=[
            ManualLoad(
                name="piping",
                load_type=ManualLoadType.AREA,
                load_case=LoadCaseName.MANUAL,
                direction=LoadDirection.GLOBAL_Z,
                value=1.5,
                loaded_area_m2=2.0,
                target_member_id="beam_1",
            )
        ]
    )
    ctx = run_full_calculation(inp)
    payload = export_report_dict(ctx, calc_id="00000000-0000-4000-8000-000000000004")

    platform = ctx.fan_support_result.platform
    assert platform is not None
    assert any(item["source"] == "piping" for item in platform.load_surface_components)
    assert any(item["name"] == "piping" for item in platform.manual_loads_applied)
    assert any(item["source"] == "piping" for item in platform.distributed_line_loads)
    assert payload["engineering_model"]["manual_loads"]
    assert payload["engineering_model"]["load_surfaces"]


def test_platform_result_exposes_simplified_load_trace_without_base_plate_confusion():
    ctx = run_full_calculation(_platform_input())
    res = ctx.fan_support_result

    assert res.platform is not None
    assert res.base_plate is None
    assert res.platform.load_distribution_method == LoadDistributionMethod.ONE_WAY.value
    assert res.platform.load_surface_components
    assert any(
        "grating" in note.lower() or "tramex" in note.lower()
        for note in ctx.engineering_report_state.state_for("load_surfaces").notes
    )
