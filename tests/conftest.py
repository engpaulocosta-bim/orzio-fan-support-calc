"""Fixtures partilhadas para os testes SFSC."""
import base64
import re
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sfsc.enums import Country, FanType, SectionFamily, SteelGrade, SupportType
from sfsc.models import FanSupportInput, FanUnit


def pdf_text(pdf_bytes: bytes) -> bytes:
    """Extrai texto dos content streams do PDF (ASCII85 + Flate do ReportLab)."""
    text = b""
    for m in re.finditer(rb"(?<!end)stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL):
        data = m.group(1).strip()
        try:
            text += zlib.decompress(base64.a85decode(data, adobe=True))
        except Exception:
            try:
                text += zlib.decompress(data)
            except Exception:
                pass
    return text


@pytest.fixture
def fan_unit_small():
    return FanUnit(
        fan_type=FanType.CENTRIFUGAL,
        weight_kg=80.0,
        operating_weight_kg=90.0,
        footprint_length_mm=600.0,
        footprint_width_mm=500.0,
        centre_of_gravity_height_mm=250.0,
    )


@pytest.fixture
def fan_unit_medium():
    return FanUnit(
        fan_type=FanType.CENTRIFUGAL,
        weight_kg=200.0,
        operating_weight_kg=220.0,
        footprint_length_mm=900.0,
        footprint_width_mm=700.0,
        centre_of_gravity_height_mm=400.0,
    )


@pytest.fixture
def fan_unit_heavy():
    return FanUnit(
        fan_type=FanType.AXIAL,
        weight_kg=480.0,
        operating_weight_kg=500.0,
        footprint_length_mm=1200.0,
        footprint_width_mm=1000.0,
        centre_of_gravity_height_mm=600.0,
    )


@pytest.fixture
def base_inp(fan_unit_small):
    return FanSupportInput(
        project_name="Test Project",
        support_tag="FSU-TEST",
        fan_units=[fan_unit_small],
        support_type=SupportType.HANGER,
        country=Country.PORTUGAL,
        seismic_zone="1.3",
        steel_grade=SteelGrade.S355,
        preferred_section_families=[SectionFamily.HEB, SectionFamily.IPE],
        dynamic_factor=1.5,
        installation_height_mm=500.0,
        span_mm=1200.0,
    )
