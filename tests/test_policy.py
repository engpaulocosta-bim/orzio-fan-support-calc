"""Fronteiras da política de peso (sfsc.policy) — auditoria C-07.

Faixas: <35 BELOW_MIN | 35–500 NORMAL | 500–600 SPECIALIST |
600–1000 EXTENDED (confirmação) | >1000 BLOCKED.
"""

import pytest

from sfsc.engines.selector import run_full_calculation
from sfsc.enums import ClassificationLevel, Country, FanType, SupportType
from sfsc.exceptions import OutOfScopeError
from sfsc.models import FanSupportInput, FanUnit
from sfsc.policy import WeightBand, weight_band, weight_warning
from sfsc.validators import validate_fan_support_input


def _inp(op_weight_kg: float, confirm: bool = False, country=Country.IRELAND):
    return FanSupportInput(
        project_name="Policy",
        support_tag="FSU-P",
        fan_units=[
            FanUnit(
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=min(op_weight_kg, op_weight_kg * 0.9) or 0.1,
                operating_weight_kg=op_weight_kg,
                footprint_length_mm=800.0,
                footprint_width_mm=600.0,
            )
        ],
        support_type=SupportType.HANGER,
        country=country,
        installation_height_mm=500.0,
        span_mm=1200.0,
        confirm_extended_range=confirm,
    )


@pytest.mark.parametrize(
    "kg,band",
    [
        (34.9, WeightBand.BELOW_MIN),
        (35.0, WeightBand.NORMAL),
        (500.0, WeightBand.NORMAL),
        (500.1, WeightBand.SPECIALIST),
        (600.0, WeightBand.SPECIALIST),
        (600.1, WeightBand.EXTENDED),
        (1000.0, WeightBand.EXTENDED),
        (1000.1, WeightBand.BLOCKED),
    ],
)
def test_weight_band_boundaries(kg, band):
    assert weight_band(kg) == band


def test_below_min_allowed_with_warning():
    validate_fan_support_input(_inp(34.9))  # não levanta
    assert weight_warning(34.9) is not None


def test_normal_range_no_warning():
    validate_fan_support_input(_inp(300.0))
    assert weight_warning(300.0) is None


def test_specialist_band_allowed():
    validate_fan_support_input(_inp(600.0))  # não levanta (≤600)


def test_extended_requires_confirmation():
    with pytest.raises(OutOfScopeError):
        validate_fan_support_input(_inp(600.1, confirm=False))
    validate_fan_support_input(_inp(600.1, confirm=True))  # com confirmação passa
    validate_fan_support_input(_inp(1000.0, confirm=True))


def test_blocked_even_with_confirmation():
    with pytest.raises(OutOfScopeError):
        validate_fan_support_input(_inp(1000.1, confirm=True))


def test_classification_below_min_is_preliminary():
    # Irlanda (ag/g=0.03) para não disparar REQUIRES_SPECIALIST por sismo
    ctx = run_full_calculation(_inp(30.0))
    assert ctx.fan_support_result.classification_level == ClassificationLevel.PRELIMINARY


def test_classification_540kg_requires_specialist():
    ctx = run_full_calculation(_inp(540.0))
    assert ctx.fan_support_result.classification_level == ClassificationLevel.REQUIRES_SPECIALIST


def test_classification_extended_requires_specialist():
    ctx = run_full_calculation(_inp(700.0, confirm=True))
    assert ctx.fan_support_result.classification_level == ClassificationLevel.REQUIRES_SPECIALIST
