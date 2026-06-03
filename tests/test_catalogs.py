"""Testes dos catálogos de perfis, aços e sísmico."""
import pytest
from sfsc.enums import SectionFamily, SteelGrade, Country
from sfsc.catalogs.steel_section_catalog import get_section, list_sections, find_minimum_section
from sfsc.catalogs.steel_grade_catalog import get_grade_spec, design_strength
from sfsc.catalogs.seismic_catalog import get_seismic_factor, list_zones


def test_heb_catalog_loads():
    sections = list_sections(SectionFamily.HEB)
    assert len(sections) > 10


def test_get_heb200():
    sec = get_section(SectionFamily.HEB, "HEB200")
    assert sec.h_mm == 200
    assert sec.b_mm == 200
    assert sec.A_cm2 == pytest.approx(78.1, rel=0.01)
    assert sec.W_el_y_cm3 == pytest.approx(569.6, rel=0.01)


def test_get_ipe_catalog():
    sections = list_sections(SectionFamily.IPE)
    assert len(sections) >= 15


def test_find_minimum_ipe():
    sec = find_minimum_section(SectionFamily.IPE, required_W_el_y_cm3=100.0)
    assert sec is not None
    assert sec.W_el_y_cm3 >= 100.0


def test_section_properties():
    sec = get_section(SectionFamily.HEB, "HEB200")
    # I_y_mm4 deve ser >> I_y_cm4
    assert sec.I_y_mm4 == pytest.approx(sec.I_y_cm4 * 1e4, rel=0.001)
    # W_el_y_mm3
    assert sec.W_el_y_mm3 == pytest.approx(sec.W_el_y_cm3 * 1e3, rel=0.001)


def test_steel_grade_s355():
    spec = get_grade_spec(SteelGrade.S355)
    assert spec.fy_mpa == 355
    assert spec.fu_mpa == 510
    assert spec.E_mpa == 210_000


def test_design_strength():
    fs = design_strength(SteelGrade.S355, thickness_mm=20.0)
    assert fs == pytest.approx(355.0, rel=0.001)


def test_design_strength_thick():
    fs = design_strength(SteelGrade.S355, thickness_mm=50.0)
    assert fs == pytest.approx(335.0, rel=0.001)


def test_seismic_portugal():
    ag, zone = get_seismic_factor(Country.PORTUGAL, "1.3")
    assert ag == pytest.approx(0.15, rel=0.001)
    assert zone == "1.3"


def test_seismic_brazil():
    ag, zone = get_seismic_factor(Country.BRAZIL, "II")
    assert ag == pytest.approx(0.10, rel=0.001)


def test_seismic_chile_default():
    ag, zone = get_seismic_factor(Country.CHILE, None)
    assert ag > 0.0


def test_seismic_uk():
    ag, zone = get_seismic_factor(Country.UK, "UK")
    assert ag == pytest.approx(0.05, rel=0.001)


def test_list_zones_portugal():
    zones = list_zones(Country.PORTUGAL)
    assert "1.1" in zones
    assert "1.6" in zones
