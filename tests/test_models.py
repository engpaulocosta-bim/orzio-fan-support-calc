"""Testes de validação dos modelos Pydantic."""

import pytest
from pydantic import ValidationError

from sfsc.enums import FanType, OperationMode, SupportType
from sfsc.models import FanSupportInput, FanUnit


def test_fan_unit_weight():
    u = FanUnit(
        fan_type=FanType.CENTRIFUGAL,
        weight_kg=100.0,
        operating_weight_kg=110.0,
        footprint_length_mm=800.0,
        footprint_width_mm=600.0,
    )
    assert u.operating_weight_kg == 110.0


def test_fan_unit_invalid_weight():
    with pytest.raises(ValidationError):
        FanUnit(
            fan_type=FanType.CENTRIFUGAL,
            weight_kg=-10.0,
            operating_weight_kg=110.0,
            footprint_length_mm=800.0,
            footprint_width_mm=600.0,
        )


def test_fan_unit_operating_below_empty_rejected():
    """operating_weight_kg < weight_kg deve falhar (auditoria H-09)."""
    with pytest.raises(ValidationError):
        FanUnit(
            fan_type=FanType.CENTRIFUGAL,
            weight_kg=120.0,
            operating_weight_kg=100.0,
            footprint_length_mm=800.0,
            footprint_width_mm=600.0,
        )


def test_total_weight_property(base_inp):
    assert base_inp.total_operating_weight_kg == 90.0
    assert abs(base_inp.total_weight_kn - 90.0 * 9.80665 / 1000) < 0.01


def test_verify_mode_requires_section(fan_unit_small):
    with pytest.raises(ValidationError):
        FanSupportInput(
            project_name="Test",
            support_tag="T1",
            fan_units=[fan_unit_small],
            support_type=SupportType.HANGER,
            operation_mode=OperationMode.VERIFY,
            # sem received_section_tag → deve falhar
            installation_height_mm=500.0,
            span_mm=1200.0,
        )


def test_base_plate_requires_connection_type(fan_unit_small):
    with pytest.raises(ValidationError):
        FanSupportInput(
            project_name="Test",
            support_tag="T2",
            fan_units=[fan_unit_small],
            support_type=SupportType.PEDESTAL,
            include_base_plate=True,
            # fan_connection_type=None → deve falhar
            installation_height_mm=500.0,
            span_mm=1200.0,
        )
