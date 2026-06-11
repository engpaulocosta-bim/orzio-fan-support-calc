"""Modelos de ancoragem por tipo de suporte — auditoria C-05/C-06."""
import pytest

from sfsc.engines.selector import run_full_calculation
from sfsc.enums import Country, FanType, SupportType
from sfsc.models import FanSupportInput, FanUnit


def _inp(**kwargs):
    defaults = dict(
        project_name="Anc", support_tag="FSU-A",
        fan_units=[FanUnit(fan_type=FanType.CENTRIFUGAL, weight_kg=120.0,
                           operating_weight_kg=130.0,
                           footprint_length_mm=800.0, footprint_width_mm=600.0,
                           centre_of_gravity_height_mm=300.0)],
        support_type=SupportType.HANGER,
        country=Country.PORTUGAL, seismic_zone="1.3",
        installation_height_mm=500.0, span_mm=1200.0,
    )
    defaults.update(kwargs)
    return FanSupportInput(**defaults)


def test_hanger_uses_rod_model_without_concrete():
    """HANGER → verificação de varão roscado: sem hef/betão (auditoria C-05)."""
    res = run_full_calculation(_inp()).fan_support_result
    anc = res.anchor
    assert anc.anchor_type == "rod"
    assert anc.embedment_depth_mm == 0.0
    assert "varões" in anc.code_clause or "varoes" in anc.code_clause.lower()
    assert "1992-4" not in anc.code_clause


def test_hanger_slender_rods_warned():
    """Varão Ø12, L=2000 mm: i = d/4 = 3 mm → λ = 2000/3 = 667 > 200 → aviso."""
    res = run_full_calculation(_inp(hanger_rod_length_mm=2000.0)).fan_support_result
    assert any("esbelt" in w.lower() for w in res.anchor.warnings)


def test_floor_anchor_uplift_from_overturning():
    """Pedestal Chile z3, 320 kg, h=800, CG=300, footprint 1000 (auditoria C-06):

    G_tot = 1.15 × 320×9.80665/1000 = 3.60885 kN
    E_h   = 0.40 × G_tot            = 1.44354 kN
    h_cg  = 800 + 300 = 1100 mm; M_ot = 1.44354 × 1.1 = 1.58789 kNm
    braço = 0.8 × 1.0 m = 0.8 m; n = 4, lado traccionado n_t = 2
    T_anc = max(0, 1.58789/(0.8×2) − 3.60885/4) = 0.99243 − 0.90221 = 0.09022 kN
    Ø12 8.8: As = 0.78π×36 = 88.22 mm²; F_t,Rd = 0.9×800×88.22/1.25/1000 = 50.81 kN
    η_N = 0.09022 / 50.81 = 0.00178
    """
    inp = _inp(
        support_type=SupportType.PEDESTAL,
        country=Country.CHILE, seismic_zone="3",
        installation_height_mm=800.0, span_mm=1200.0,
        fan_units=[FanUnit(fan_type=FanType.CENTRIFUGAL, weight_kg=300.0,
                           operating_weight_kg=320.0,
                           footprint_length_mm=1000.0, footprint_width_mm=800.0,
                           centre_of_gravity_height_mm=300.0)],
    )
    anc = run_full_calculation(inp).fan_support_result.anchor
    assert anc.anchor_type == "concrete"
    assert anc.utilization_tension > 0.0
    assert anc.utilization_tension == pytest.approx(0.0018, abs=0.0003)


def test_floor_anchor_no_seismic_no_tension():
    """Irlanda (ag/g=0.03): derrube não vence o peso próprio → tracção nula + nota."""
    inp = _inp(support_type=SupportType.PEDESTAL,
               country=Country.IRELAND, seismic_zone="IE")
    anc = run_full_calculation(inp).fan_support_result.anchor
    assert anc.anchor_type == "concrete"
    assert anc.utilization_tension == 0.0
    assert any("derrube" in w.lower() or "peso próprio" in w.lower() for w in anc.warnings)


def test_wall_cantilever_tension_from_moment():
    """CANTILEVER_1 (parede): tracção das ancoragens vem do momento de
    encastramento — tem de ser > 0 mesmo sem sismo."""
    inp = _inp(support_type=SupportType.CANTILEVER_1, span_mm=800.0)
    from sfsc.enums import CantileverSubtype
    inp = inp.model_copy(update={"cantilever_subtype": CantileverSubtype.PURE})
    anc = run_full_calculation(inp).fan_support_result.anchor
    assert anc.anchor_type == "concrete"
    assert anc.utilization_tension > 0.0
