"""Robustez: ramos de falha do anchor, validators defensivos e YAML inválido.

Cobre as prioridades F2.4 da auditoria (ramo FAIL de anchor.py, validators a
ramos completos, dados de catálogo malformados → erro explícito).
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

import sfsc.config as config
from sfsc.catalogs import seismic_catalog, steel_section_catalog
from sfsc.engines.anchor import calculate_anchor
from sfsc.enums import (
    AntiVibrationType,
    CantileverSubtype,
    CheckerStatus,
    Country,
    FanType,
    SectionFamily,
    StructuralCode,
    SupportType,
)
from sfsc.exceptions import MissingInputError, SeismicDataMissingError, ValidationError
from sfsc.models import FanSupportInput, FanUnit, LoadCombination
from sfsc.validators import validate_fan_support_input


def _inp(**kwargs):
    defaults = dict(
        project_name="Rob",
        support_tag="FSU-R",
        fan_units=[
            FanUnit(
                fan_type=FanType.CENTRIFUGAL,
                weight_kg=120.0,
                operating_weight_kg=130.0,
                footprint_length_mm=800.0,
                footprint_width_mm=600.0,
            )
        ],
        support_type=SupportType.HANGER,
        country=Country.PORTUGAL,
        seismic_zone="1.3",
        installation_height_mm=500.0,
        span_mm=1200.0,
    )
    defaults.update(kwargs)
    return FanSupportInput(**defaults)


# ── Anchor: ramo de falha ──────────────────────────────────────────────────────


def test_anchor_fail_branch_when_demand_exceeds_max():
    """Demanda absurda (3000 kN) excede Ø30×8 (F_t,Rd = 0.9×800×551.5/1.25
    ≈ 317.7 kN/varão → 2541 kN no grupo) → FAIL + aviso CRÍTICO.

    Teste unitário directo a calculate_anchor — a política de peso bloquearia
    este caso a montante, mas o ramo de falha tem de estar protegido.
    """
    inp = _inp()
    combos = [LoadCombination(name="ULS_fundamental", V_z_kN=3000.0)]
    res = calculate_anchor(inp, combos, StructuralCode.EC3_EN1993)
    assert res.status == CheckerStatus.FAIL
    assert res.anchor_diameter_mm == 30.0
    assert res.n_anchors == 8
    assert any("CRÍTICO" in w for w in res.warnings)


# ── Validators: ramos defensivos ───────────────────────────────────────────────


def test_validator_empty_fan_units():
    fake = SimpleNamespace(fan_units=[])
    with pytest.raises(MissingInputError):
        validate_fan_support_input(fake)


def test_validator_zero_total_weight():
    fake = SimpleNamespace(fan_units=[SimpleNamespace(operating_weight_kg=0.0)])
    with pytest.raises(ValidationError):
        validate_fan_support_input(fake)


def test_validator_cantilever1_requires_subtype():
    inp = _inp(support_type=SupportType.CANTILEVER_1, cantilever_subtype=None)
    with pytest.raises(MissingInputError):
        validate_fan_support_input(inp)


def test_validator_springs_require_deflection():
    inp = _inp(anti_vibration=AntiVibrationType.SPRINGS, anti_vibration_static_deflection_mm=None)
    with pytest.raises(MissingInputError):
        validate_fan_support_input(inp)


def test_validator_valid_input_passes():
    validate_fan_support_input(
        _inp(
            support_type=SupportType.CANTILEVER_1,
            cantilever_subtype=CantileverSubtype.PURE,
            anti_vibration=AntiVibrationType.SPRINGS,
            anti_vibration_static_deflection_mm=25.0,
        )
    )


# ── Catálogos YAML malformados → erro explícito ────────────────────────────────


@pytest.fixture
def _clear_catalog_caches():
    steel_section_catalog._load_family.cache_clear()
    config._load_yaml.cache_clear()
    yield
    steel_section_catalog._load_family.cache_clear()
    config._load_yaml.cache_clear()


def test_section_catalog_missing_field_raises(monkeypatch, _clear_catalog_caches):
    """Entrada de perfil sem propriedades obrigatórias (W_pl_y, A) → erro de
    validação Pydantic explícito, não um perfil silenciosamente errado."""
    bad_rows = [{"designation": "BAD100", "h_mm": 100, "b_mm": 100}]
    monkeypatch.setattr(
        "sfsc.catalogs.steel_section_catalog.get_section_catalog",
        lambda family: bad_rows,
    )
    with pytest.raises(PydanticValidationError):
        steel_section_catalog.list_sections(SectionFamily.HEB)


def test_seismic_zone_missing_ag_g_raises(monkeypatch):
    """Zona sem ag_g (ou inválido) → SeismicDataMissingError, não KeyError."""
    bad = {"countries": {"PT": {"default_zone": "X", "zones": {"X": {"description": "sem ag_g"}}}}}
    monkeypatch.setattr("sfsc.catalogs.seismic_catalog.get_seismic_zones", lambda: bad)
    with pytest.raises(SeismicDataMissingError):
        seismic_catalog.get_seismic_factor(Country.PORTUGAL, "X")


def test_seismic_zone_negative_ag_g_raises(monkeypatch):
    bad = {"countries": {"PT": {"default_zone": "X", "zones": {"X": {"ag_g": -0.1}}}}}
    monkeypatch.setattr("sfsc.catalogs.seismic_catalog.get_seismic_zones", lambda: bad)
    with pytest.raises(SeismicDataMissingError):
        seismic_catalog.get_seismic_factor(Country.PORTUGAL, "X")


def test_missing_yaml_returns_empty_catalog(_clear_catalog_caches):
    """Família sem ficheiro de catálogo → lista vazia documentada (não excepção).

    Comportamento actual: famílias L/C estão no enum sem catálogo. A Fase 3
    (provenance) deverá promover isto a DATASET_MISSING explícito.
    """
    assert steel_section_catalog.list_sections(SectionFamily.L) == []
