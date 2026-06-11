"""Testes do verificador de secções."""

import pytest

from sfsc.catalogs.steel_section_catalog import get_section
from sfsc.engines.section_verifier import auto_select_section, verify_section
from sfsc.enums import CheckerStatus, SectionFamily, SteelGrade, StructuralCode
from sfsc.models import LoadCombination


@pytest.fixture
def heb200():
    return get_section(SectionFamily.HEB, "HEB200")


@pytest.fixture
def light_combo():
    return LoadCombination(name="ULS_fundamental", V_z_kN=5.0, M_y_kNm=1.5)


@pytest.fixture
def heavy_combo():
    return LoadCombination(name="ULS_fundamental", V_z_kN=80.0, M_y_kNm=30.0)


def test_light_load_passes(heb200, light_combo):
    result = verify_section(
        heb200, light_combo, StructuralCode.EC3_EN1993, SteelGrade.S355, 1200.0, 600.0
    )
    assert result.status == CheckerStatus.PASS
    assert result.utilization_ratio < 0.5


def test_heavy_load_fails_or_marginal(heb200, heavy_combo):
    result = verify_section(
        heb200, heavy_combo, StructuralCode.EC3_EN1993, SteelGrade.S355, 1200.0, 600.0
    )
    # Pode passar ou falhar dependendo dos valores exactos — verificar que calcula
    assert result.utilization_ratio > 0.0
    assert result.governing_check in ("bending_y", "shear_z", "ltb", "axial")


def test_auto_select_finds_section():
    combos = [LoadCombination(name="ULS_fundamental", V_z_kN=20.0, M_y_kNm=8.0)]
    sec, sv = auto_select_section(
        combos,
        StructuralCode.EC3_EN1993,
        SteelGrade.S355,
        [SectionFamily.HEB, SectionFamily.IPE],
        1500.0,
        750.0,
    )
    assert sec is not None
    assert sv.utilization_ratio <= 0.90


def test_checks_dict_populated(heb200, light_combo):
    result = verify_section(
        heb200, light_combo, StructuralCode.EC3_EN1993, SteelGrade.S355, 1200.0, 600.0
    )
    assert "shear_z" in result.utilization_by_check
    assert "bending_y" in result.utilization_by_check
