"""Motor de cargas — combinações de acções EC1/EC8/NBR/NCh."""

from __future__ import annotations

import logging

from ..enums import StructuralCode
from ..models import FanSupportInput, LoadCombination
from ..units import kg_to_kn

logger = logging.getLogger("sfsc.loads")

# Coeficientes de combinação por código
_GAMMA: dict[str, dict[str, float]] = {
    "EC": {"gamma_G": 1.35, "gamma_Q": 1.50, "psi_0": 1.0},
    "BR": {"gamma_G": 1.40, "gamma_Q": 1.40, "psi_0": 1.0},  # NBR 6118 / NBR 8800
    "CL": {"gamma_G": 1.40, "gamma_Q": 1.60, "psi_0": 1.0},  # NCh2369
}

_CODE_TO_GROUP: dict[StructuralCode, str] = {
    StructuralCode.EC3_EN1993: "EC",
    StructuralCode.EC3_UK_NA: "EC",
    StructuralCode.EC3_NF_NA: "EC",
    StructuralCode.NBR_8800: "BR",
    StructuralCode.NCH_427: "CL",
}


def calculate_loads(
    inp: FanSupportInput,
    structural_code: StructuralCode,
    seismic_factor_g: float,
) -> tuple[float, list[LoadCombination]]:
    """
    Calcula peso total e combinações de acções.

    Returns:
        total_weight_kN  — carga permanente G (peso ventilador + suporte estimado)
        combinations     — lista de LoadCombination ordenada por M_y governante
    """
    # ── Carga permanente G ────────────────────────────────────────────────────
    G_equipment_kN = kg_to_kn(inp.total_operating_weight_kg)

    # Peso estimado do suporte: 15% do equipamento (conservativo)
    G_support_kN = 0.15 * G_equipment_kN
    G_total_kN = G_equipment_kN + G_support_kN

    # ── Carga variável Q (arranque dinâmico) ──────────────────────────────────
    Q_dynamic_kN = G_equipment_kN * (inp.dynamic_factor - 1.0)

    # ── Carga sísmica E_d ─────────────────────────────────────────────────────
    E_d_horizontal_kN = G_total_kN * seismic_factor_g  # F_h = ag/g × G

    # ── Coeficientes ──────────────────────────────────────────────────────────
    group = _CODE_TO_GROUP.get(structural_code, "EC")
    gG = _GAMMA[group]["gamma_G"]
    gQ = _GAMMA[group]["gamma_Q"]

    # ── Combinação 1: ULS fundamental (domina normalmente) ────────────────────
    G_d = gG * G_total_kN
    Q_d = gQ * Q_dynamic_kN
    V_uls = G_d + Q_d

    combo_uls = LoadCombination(
        name="ULS_fundamental",
        V_z_kN=V_uls,
        N_kN=0.0,
        load_factors_used={
            "gamma_G": gG,
            "gamma_Q": gQ,
            "G_kN": round(G_total_kN, 3),
            "Q_kN": round(Q_dynamic_kN, 3),
        },
        description=f"{gG}×G + {gQ}×Q  =  {V_uls:.2f} kN",
    )

    # ── Combinação 2: ULS sísmica ─────────────────────────────────────────────
    V_seismic = 1.0 * G_total_kN
    H_seismic = 1.0 * E_d_horizontal_kN

    combo_seis = LoadCombination(
        name="ULS_seismic",
        V_z_kN=V_seismic,
        V_y_kN=H_seismic,
        N_kN=0.0,
        load_factors_used={
            "gamma_G": 1.0,
            "ag_g": seismic_factor_g,
            "G_kN": round(G_total_kN, 3),
            "E_d_kN": round(E_d_horizontal_kN, 3),
        },
        description=f"1.0×G + E_d  =  {V_seismic:.2f} kN vertical + {H_seismic:.2f} kN horizontal",
    )

    # ── Combinação 3: SLS característica ─────────────────────────────────────
    combo_sls = LoadCombination(
        name="SLS_characteristic",
        V_z_kN=G_total_kN + Q_dynamic_kN,
        load_factors_used={
            "gamma_G": 1.0,
            "gamma_Q": 1.0,
            "G_kN": round(G_total_kN, 3),
            "Q_kN": round(Q_dynamic_kN, 3),
        },
        description=f"1.0×G + 1.0×Q  =  {G_total_kN + Q_dynamic_kN:.2f} kN",
    )

    combinations = [combo_uls, combo_seis, combo_sls]
    logger.debug(
        "Loads: G=%.2f kN, Q=%.2f kN, E_d=%.2f kN, ULS=%.2f kN",
        G_total_kN,
        Q_dynamic_kN,
        E_d_horizontal_kN,
        V_uls,
    )
    return G_total_kN, combinations
