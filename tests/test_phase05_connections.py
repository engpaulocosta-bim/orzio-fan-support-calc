from sfsc.engineering import CalculationResultState
from sfsc.engines.selector import run_full_calculation
from sfsc.enums import (
    BoltClass,
    CantileverSubtype,
    Country,
    FanConnectionType,
    FanType,
    SteelConnectionType,
    SteelGrade,
    SupportFixationMedium,
    SupportType,
)
from sfsc.models import (
    AnchorLayoutInput,
    BasePlateInput,
    CalculationOptions,
    FanSupportInput,
    FanUnit,
    SteelFixationInput,
)


def _cantilever_input(**updates) -> FanSupportInput:
    data = {
        "project_name": "Phase 05",
        "support_tag": "FSU-PH05",
        "prepared_by": "Eng. Phase 05",
        "fan_units": [
            FanUnit(
                tag="FAN-1",
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=180.0,
                operating_weight_kg=180.0,
                footprint_length_mm=1000.0,
                footprint_width_mm=800.0,
                centre_of_gravity_height_mm=350.0,
            )
        ],
        "support_type": SupportType.CANTILEVER_1,
        "cantilever_subtype": CantileverSubtype.PURE,
        "country": Country.SPAIN,
        "seismic_zone": "B",
        "steel_grade": SteelGrade.S275,
        "installation_height_mm": 500.0,
        "span_mm": 800.0,
        "eccentricity_mm": 0.0,
        "include_base_plate": True,
        "fan_connection_type": FanConnectionType.DIRECT_FLANGE,
        "calculation_options": CalculationOptions(include_base_plate=True, include_anchors=True),
    }
    data.update(updates)
    return FanSupportInput(**data)


def test_phase05_concrete_connection_missing_inputs_stays_not_verified():
    ctx = run_full_calculation(_cantilever_input())

    assert ctx.engineering_report_state.state_for("connection_checks").state == (
        CalculationResultState.NOT_VERIFIED
    )
    types = {row["type"] for row in ctx.fan_support_result.connection_check_rows}
    assert {"base_plate", "base_plate_transfer", "anchor_group"} <= types
    assert any(row["missing_inputs"] for row in ctx.fan_support_result.connection_check_rows)


def test_phase05_concrete_connection_uses_solver_reactions_when_inputs_exist():
    ctx = run_full_calculation(
        _cantilever_input(
            base_plate_input=BasePlateInput(
                length_mm=1200.0,
                width_mm=900.0,
                thickness_mm=15.0,
                weld_throat_mm=4.0,
            ),
            anchor_layout=AnchorLayoutInput(
                n_anchors=4,
                anchor_diameter_mm=16.0,
                spacing_x_mm=300.0,
                spacing_y_mm=600.0,
                edge_distance_x_mm=150.0,
                edge_distance_y_mm=150.0,
            ),
        )
    )

    assert ctx.engineering_report_state.state_for("connection_checks").state == (
        CalculationResultState.VERIFIED
    )
    base_plate = next(
        row for row in ctx.fan_support_result.connection_check_rows if row["type"] == "base_plate"
    )
    assert base_plate["governing_combination"] == "ULS_fundamental"
    assert base_plate["reaction_fz_kN"] > 0.0
    assert base_plate["reaction_my_kNm"] > 0.0
    assert all(
        check.status == CalculationResultState.VERIFIED
        for check in ctx.engineering_model.connection_checks
    )


def test_phase05_steel_fixation_can_be_verified_from_solver_reactions():
    ctx = run_full_calculation(
        _cantilever_input(
            include_base_plate=False,
            fan_connection_type=None,
            support_fixation_medium=SupportFixationMedium.STEEL_STRUCTURE,
            steel_fixation=SteelFixationInput(
                connection_type=SteelConnectionType.BOLTED,
                bolt_diameter_mm=16.0,
                number_of_bolts=4,
                bolt_class=BoltClass.C8_8,
                plate_thickness_mm=10.0,
            ),
            calculation_options=CalculationOptions(include_steel_connections=True),
        )
    )

    assert ctx.engineering_report_state.state_for("connection_checks").state == (
        CalculationResultState.VERIFIED
    )
    assert ctx.fan_support_result.connection_check_rows[0]["type"] == "steel_fixation"
    assert ctx.fan_support_result.connection_check_rows[0]["reaction_fz_kN"] > 0.0
