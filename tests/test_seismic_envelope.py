"""Envelope sísmico e separação acções/esforços — auditoria C-01/C-02.

Caso de referência (cálculo manual no docstring de cada teste):

    1 ventilador, 320 kg em operação, pedestal, h = 800 mm, L = 1200 mm,
    CG = 300 mm, footprint 1000×800 mm.

    G_eq  = 320 × 9.80665 / 1000           = 3.13813 kN
    G_tot = 1.15 × G_eq                     = 3.60885 kN   (suporte = 15%)
    Q     = G_eq × (1.5 − 1.0)              = 1.56906 kN   (factor dinâmico 1.5)

    Chile (NCh): ULS = 1.4×G_tot + 1.6×Q    = 5.05239 + 2.51050 = 7.56289 kN
    Chile zona 3: ag/g = 0.40 → E_h = 0.40 × 3.60885 = 1.44354 kN

    Esforços no patim, combinação sísmica (V_z = 1.0×G_tot, V_y = E_h):
      q        = (3.60885/2) / 1.2          = 1.50369 kN/m
      M_patim  = q × 1.2² / 8               = 0.27066 kNm
      M_sismo  = 1.44354 × 0.8 / 2          = 0.57742 kNm
      M_y      = 0.27066 + 0.57742          = 0.84808 kNm
"""
import pytest
from sfsc.enums import SupportType, Country, FanType
from sfsc.models import FanSupportInput, FanUnit
from sfsc.engines.selector import run_full_calculation


def _pedestal(country: Country, zone: str) -> FanSupportInput:
    return FanSupportInput(
        project_name="Seis", support_tag="FSU-S",
        fan_units=[FanUnit(fan_type=FanType.CENTRIFUGAL, weight_kg=300.0,
                           operating_weight_kg=320.0,
                           footprint_length_mm=1000.0, footprint_width_mm=800.0,
                           centre_of_gravity_height_mm=300.0)],
        support_type=SupportType.PEDESTAL,
        country=country, seismic_zone=zone,
        installation_height_mm=800.0, span_mm=1200.0,
    )


def test_design_load_is_total_uls():
    """design_load_kN = ULS total (acções): 1.4×3.60885 + 1.6×1.56906 = 7.563 kN."""
    res = run_full_calculation(_pedestal(Country.CHILE, "3")).fan_support_result
    assert res.design_load_kN == pytest.approx(7.563, abs=0.01)


def test_seismic_member_moment_hand_calc():
    """M_y sísmico no patim = 0.27066 + 0.57742 = 0.848 kNm (ver docstring do módulo)."""
    res = run_full_calculation(_pedestal(Country.CHILE, "3")).fan_support_result
    seis = next(c for c in res.member_forces if c.name == "ULS_seismic")
    assert seis.member_level is True
    assert seis.M_y_kNm == pytest.approx(0.848, abs=0.005)


def test_seismic_combination_governs_in_chile():
    """Chile z3 (ag/g=0.40): M sísmico (0.848) > M fundamental (0.57) → sísmica governa."""
    res = run_full_calculation(_pedestal(Country.CHILE, "3")).fan_support_result
    assert res.governing_load_combination.name == "ULS_seismic"
    gov_actions = [c for c in res.all_combinations if c.governing]
    assert [c.name for c in gov_actions] == ["ULS_seismic"]


def test_chile_vs_ireland_different_design():
    """O mesmo input em Chile z3 e Irlanda tem de produzir dimensionamento diferente
    (auditoria C-01: antes o sismo nunca chegava ao dimensionamento)."""
    res_cl = run_full_calculation(_pedestal(Country.CHILE, "3")).fan_support_result
    res_ie = run_full_calculation(_pedestal(Country.IRELAND, "IE")).fan_support_result
    assert res_ie.governing_load_combination.name == "ULS_fundamental"
    eta_cl = res_cl.section_verification.utilization_ratio
    eta_ie = res_ie.section_verification.utilization_ratio
    assert eta_cl != eta_ie
    assert eta_cl > eta_ie


def test_action_and_member_tables_are_separate_levels():
    """all_combinations = acções totais; member_forces = esforços no elemento.
    Na tabela de acções, ULS fundamental ≥ SLS (coerência C-02)."""
    res = run_full_calculation(_pedestal(Country.CHILE, "3")).fan_support_result
    assert all(not c.member_level for c in res.all_combinations)
    assert all(c.member_level for c in res.member_forces)
    uls = next(c for c in res.all_combinations if c.name == "ULS_fundamental")
    sls = next(c for c in res.all_combinations if c.name == "SLS_characteristic")
    assert uls.V_z_kN >= sls.V_z_kN


def test_base_plate_uses_total_action_envelope():
    """A mesa é dimensionada para a carga ULS TOTAL (7.56289 kN), não para o
    esforço por patim (P/4 = 1.89 kN).

    Parafusos ventilador→chapa, M16 8.8, 4 un.:
      As     = 0.78π × 8²                = 156.83 mm²
      F_v,Rd = 0.6×800×156.83/1.25       = 60.22 kN
      η      = (7.56289/4) / 60.22       = 0.0314   (com P/4 seria 0.0079)
    """
    from sfsc.enums import FanConnectionType
    inp = _pedestal(Country.CHILE, "3").model_copy(update={
        "include_base_plate": True,
        "fan_connection_type": FanConnectionType.DIRECT_FLANGE,
    })
    res = run_full_calculation(inp).fan_support_result
    bp = res.base_plate
    assert bp.bolt_utilization_fan == pytest.approx(0.0314, abs=0.0005)


def test_eccentricity_increases_member_moment():
    """Hanger PT, 130 kg, L=1.2 m:
    V_uls = 1.35×1.46609 + 1.5×0.63743 = 2.93537 kN
    e=0:      M = V×L/4 = 0.88061 kNm
    e=100mm:  M = V×L/4 + V×0.1 = 1.17415 kNm
    """
    def hanger(ecc):
        return FanSupportInput(
            project_name="Ecc", support_tag="FSU-E",
            fan_units=[FanUnit(fan_type=FanType.CENTRIFUGAL, weight_kg=120.0,
                               operating_weight_kg=130.0,
                               footprint_length_mm=800.0, footprint_width_mm=600.0)],
            support_type=SupportType.HANGER,
            country=Country.PORTUGAL, seismic_zone="1.3",
            installation_height_mm=500.0, span_mm=1200.0,
            eccentricity_mm=ecc,
        )
    res0 = run_full_calculation(hanger(0.0)).fan_support_result
    res1 = run_full_calculation(hanger(100.0)).fan_support_result
    m0 = next(c for c in res0.member_forces if c.name == "ULS_fundamental").M_y_kNm
    m1 = next(c for c in res1.member_forces if c.name == "ULS_fundamental").M_y_kNm
    assert m0 == pytest.approx(0.88061, abs=0.002)
    assert m1 == pytest.approx(1.17415, abs=0.002)
