"""Testes do motor de cargas."""
from sfsc.engines.loads import calculate_loads
from sfsc.enums import StructuralCode


def test_loads_basic(base_inp):
    G_kN, combos = calculate_loads(base_inp, StructuralCode.EC3_EN1993, 0.15)
    assert G_kN > 0
    assert len(combos) == 3


def test_uls_fundamental_greater_than_sls(base_inp):
    _, combos = calculate_loads(base_inp, StructuralCode.EC3_EN1993, 0.10)
    uls = next(c for c in combos if c.name == "ULS_fundamental")
    sls = next(c for c in combos if c.name == "SLS_characteristic")
    assert uls.V_z_kN >= sls.V_z_kN


def test_seismic_combo_has_horizontal(base_inp):
    _, combos = calculate_loads(base_inp, StructuralCode.EC3_EN1993, 0.20)
    seis = next(c for c in combos if c.name == "ULS_seismic")
    assert abs(seis.V_y_kN) > 0.01


def test_nbr_coeff(base_inp):
    from sfsc.enums import Country
    inp = base_inp.model_copy(update={"country": Country.BRAZIL})
    _, combos = calculate_loads(inp, StructuralCode.NBR_8800, 0.10)
    uls = next(c for c in combos if c.name == "ULS_fundamental")
    # NBR: 1.40*G + 1.40*Q — coeficiente maior que EC
    ec_combos = calculate_loads(base_inp, StructuralCode.EC3_EN1993, 0.10)[1]
    uls_ec = next(c for c in ec_combos if c.name == "ULS_fundamental")
    assert uls.V_z_kN >= uls_ec.V_z_kN * 0.95  # razoavelmente próximo ou maior
