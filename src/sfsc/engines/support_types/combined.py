"""COMBINED — mesa (pedestal) + pendurais anti-vibração."""
from __future__ import annotations
from ...models import FanSupportInput, LoadCombination
from ...enums import StructuralCode, AntiVibrationType
from ...units import mm_to_m
from .pedestal import calc_pedestal


def calc_combined(
    inp: FanSupportInput,
    total_weight_kN: float,
    combinations: list[LoadCombination],
    code: StructuralCode,
) -> tuple[LoadCombination, float, float]:
    """
    Mesa + pendurais anti-vibração.
    A mesa (pedestal) suporta a carga vertical.
    Pendurais (tirantes) estabilizam horizontalmente — absorvem carga sísmica.

    Distribuição:
        Mesa:      70% da carga (carga vertical + parte do sismo)
        Pendurais: 30% da carga vertical + toda a carga horizontal (tirantes)
    """
    # Base: calcular como pedestal
    combo_pedestal, Lcr_y, Lcr_z = calc_pedestal(
        inp, total_weight_kN, combinations, code
    )

    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    P_kN = governing.V_z_kN
    H_kN = abs(governing.V_y_kN)

    # Pendurais absorvem 100% da carga horizontal
    # Mesa reduz momento por ter travamento dos pendurais
    factor_mesa = 0.70
    M_reduced   = combo_pedestal.M_y_kNm * factor_mesa

    # Força nos pendurais (tirantes diagonais ou verticais)
    n_hangers  = 4  # 4 tirantes (um em cada canto)
    F_hanger_kN = (P_kN * 0.30 + H_kN) / n_hangers

    updated = LoadCombination(
        name=governing.name,
        N_kN=combo_pedestal.N_kN,
        V_z_kN=combo_pedestal.V_z_kN * factor_mesa,
        V_y_kN=H_kN,
        M_y_kNm=M_reduced,
        governing=True,
        load_factors_used={
            **governing.load_factors_used,
            "factor_mesa": factor_mesa,
            "F_hanger_kN": round(F_hanger_kN, 3),
            "n_hangers": n_hangers,
        },
        description=(
            f"Combined (mesa+pendurais) — {int(factor_mesa*100)}% carga na mesa "
            f"F_pendural={F_hanger_kN:.2f} kN/tirante"
        ),
    )

    # Aviso sobre anti-vibração
    if inp.anti_vibration == AntiVibrationType.SPRINGS:
        defl = inp.anti_vibration_static_deflection_mm or 25.0
        updated.description += (
            f" | Molas: δ_estático={defl:.1f} mm "
            f"(dim. dinâmica fora do âmbito — A-VIB-001)"
        )

    return updated, Lcr_y, Lcr_z
