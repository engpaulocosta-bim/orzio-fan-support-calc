"""COMBINED — mesa (pedestal) + pendurais anti-vibração."""
from __future__ import annotations

from ...enums import AntiVibrationType, StructuralCode
from ...models import FanSupportInput, LoadCombination
from .pedestal import _member_forces as _pedestal_member_forces
from .pedestal import calc_pedestal

# Distribuição assumida (modelo simplificado):
#   Mesa:      70% da carga vertical (+ momento reduzido pelo travamento)
#   Pendurais: 30% da carga vertical + toda a carga horizontal (tirantes)
_FACTOR_MESA = 0.70
_N_HANGERS = 4


def _member_forces(inp: FanSupportInput, c: LoadCombination) -> LoadCombination:
    """Esforços na mesa para UMA combinação de acções (base: pedestal × 70%)."""
    base = _pedestal_member_forces(inp, c)
    P_kN = c.V_z_kN
    H_kN = abs(c.V_y_kN)
    F_hanger_kN = (P_kN * (1.0 - _FACTOR_MESA) + H_kN) / _N_HANGERS

    combo = LoadCombination(
        name=c.name,
        N_kN=base.N_kN,
        V_z_kN=base.V_z_kN * _FACTOR_MESA,
        V_y_kN=H_kN,
        M_y_kNm=base.M_y_kNm * _FACTOR_MESA,
        member_level=True,
        load_factors_used={
            **c.load_factors_used,
            "factor_mesa": _FACTOR_MESA,
            "F_hanger_kN": round(F_hanger_kN, 3),
            "n_hangers": _N_HANGERS,
        },
        description=(
            f"Combined (mesa+pendurais) — {int(_FACTOR_MESA*100)}% carga na mesa "
            f"F_pendural={F_hanger_kN:.2f} kN/tirante"
        ),
    )

    if inp.anti_vibration == AntiVibrationType.SPRINGS:
        defl = inp.anti_vibration_static_deflection_mm or 25.0
        combo.description += (
            f" | Molas: δ_estático={defl:.1f} mm "
            f"(dim. dinâmica fora do âmbito — A-VIB-001)"
        )
    return combo


def calc_combined(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[list[LoadCombination], float, float]:
    """
    Transforma TODAS as combinações de acções em esforços na mesa
    (auditoria C-01/C-02 — a combinação sísmica também é verificada).

    Comprimentos de encurvadura herdados do modelo pedestal.
    """
    _, Lcr_y, Lcr_z = calc_pedestal(inp, total_weight_kN, combinations, code)
    member_combos = [_member_forces(inp, c) for c in combinations]
    return member_combos, Lcr_y, Lcr_z
