"""Motor de cargas — combinações de acções EC1/EC8/NBR/NCh."""
from __future__ import annotations
import logging
from ..models import FanSupportInput, LoadCombination
from ..enums import Country, StructuralCode, SupportType
from ..units import kg_to_kn, G_GRAVITY

logger = logging.getLogger("sfsc.loads")

# Coeficientes de combinação por código
_GAMMA: dict[str, dict[str, float]] = {
    "EC": {"gamma_G": 1.35, "gamma_Q": 1.50, "psi_0": 1.0},
    "BR": {"gamma_G": 1.40, "gamma_Q": 1.40, "psi_0": 1.0},  # NBR 6118 / NBR 8800
    "CL": {"gamma_G": 1.40, "gamma_Q": 1.60, "psi_0": 1.0},  # NCh2369
}

_CODE_TO_GROUP: dict[StructuralCode, str] = {
    StructuralCode.EC3_EN1993: "EC",
    StructuralCode.EC3_UK_NA:  "EC",
    StructuralCode.EC3_NF_NA:  "EC",
    StructuralCode.NBR_8800:   "BR",
    StructuralCode.NCH_427:    "CL",
}


def _platform_self_weight_kN(
    inp: FanSupportInput,
    steel_self_weight_kg: float | None,
) -> tuple[float, dict[str, float]]:
    """Peso próprio real de uma plataforma de grelha: tramex + estrutura de aço.

    O tramex é peso por área (kg/m² × área). O aço é o peso real dos perfis
    quando já conhecido (``steel_self_weight_kg``); na primeira passagem, antes
    de a secção estar escolhida, estima-se por um kg/m típico de viga leve.
    """
    G_grating_kN = kg_to_kn(inp.grating_weight_kg)

    if steel_self_weight_kg is not None:
        steel_kg = steel_self_weight_kg
    else:
        # Estimativa pré-selecção: ~22 kg/m por viga (ordem de IPE200) × N × comprimento.
        from ..units import mm_to_m
        steel_kg = 22.0 * inp.platform_n_beams * mm_to_m(inp.platform_length_eff_mm)
    G_steel_kN = kg_to_kn(steel_kg)

    breakdown = {
        "G_grating_kN": round(G_grating_kN, 3),
        "G_steel_kN": round(G_steel_kN, 3),
        "grating_kg": round(inp.grating_weight_kg, 1),
        "steel_kg": round(steel_kg, 1),
    }
    return G_grating_kN + G_steel_kN, breakdown


def calculate_loads(
    inp: FanSupportInput,
    structural_code: StructuralCode,
    seismic_factor_g: float,
    steel_self_weight_kg: float | None = None,
) -> tuple[float, list[LoadCombination]]:
    """
    Calcula peso total e combinações de acções.

    Args:
        steel_self_weight_kg — peso real da estrutura de aço, quando já conhecido
            (PLATFORM, 2ª passagem). None = estimar.

    Returns:
        total_weight_kN  — carga permanente G (peso ventilador + suporte)
        combinations     — lista de LoadCombination ordenada por M_y governante
    """
    # ── Carga permanente G ────────────────────────────────────────────────────
    G_equipment_kN = kg_to_kn(inp.total_operating_weight_kg)

    self_weight_breakdown: dict[str, float] = {}
    if inp.support_type == SupportType.PLATFORM:
        # Peso próprio real: tramex por área + aço dos perfis (sem o chute de 15%).
        G_support_kN, self_weight_breakdown = _platform_self_weight_kN(
            inp, steel_self_weight_kg,
        )
    else:
        # Peso estimado do suporte: 15% do equipamento (conservativo)
        G_support_kN = 0.15 * G_equipment_kN
    G_total_kN   = G_equipment_kN + G_support_kN

    # ── Carga variável Q (arranque dinâmico) ──────────────────────────────────
    Q_dynamic_kN = G_equipment_kN * (inp.dynamic_factor - 1.0)

    # ── Carga sísmica E_d ─────────────────────────────────────────────────────
    E_d_horizontal_kN = G_total_kN * seismic_factor_g  # F_h = ag/g × G

    # ── Coeficientes ──────────────────────────────────────────────────────────
    group = _CODE_TO_GROUP.get(structural_code, "EC")
    gG = _GAMMA[group]["gamma_G"]
    gQ = _GAMMA[group]["gamma_Q"]

    # ── Combinação 1: ULS fundamental (domina normalmente) ────────────────────
    G_d  = gG * G_total_kN
    Q_d  = gQ * Q_dynamic_kN
    V_uls = G_d + Q_d

    combo_uls = LoadCombination(
        name="ULS_fundamental",
        V_z_kN=V_uls,
        N_kN=0.0,
        load_factors_used={"gamma_G": gG, "gamma_Q": gQ,
                           "G_kN": G_total_kN,
                           "G_equipment_kN": round(G_equipment_kN, 3),
                           "G_support_kN": round(G_support_kN, 3),
                           "Q_kN": Q_dynamic_kN,
                           **self_weight_breakdown},
        description=f"{gG}×G + {gQ}×Q  =  {V_uls:.2f} kN",
    )

    # ── Combinação 2: ULS sísmica ─────────────────────────────────────────────
    V_seismic   = 1.0 * G_total_kN
    H_seismic   = 1.0 * E_d_horizontal_kN

    combo_seis = LoadCombination(
        name="ULS_seismic",
        V_z_kN=V_seismic,
        V_y_kN=H_seismic,
        N_kN=0.0,
        load_factors_used={"gamma_G": 1.0, "ag_g": seismic_factor_g,
                           "G_kN": G_total_kN,
                           "E_d_kN": E_d_horizontal_kN},
        description=f"1.0×G + E_d  =  {V_seismic:.2f} kN vertical + {H_seismic:.2f} kN horizontal",
    )

    # ── Combinação 3: SLS característica ─────────────────────────────────────
    combo_sls = LoadCombination(
        name="SLS_characteristic",
        V_z_kN=G_total_kN + Q_dynamic_kN,
        load_factors_used={"gamma_G": 1.0, "gamma_Q": 1.0,
                           "G_kN": G_total_kN,
                           "Q_kN": Q_dynamic_kN},
        description=f"1.0×G + 1.0×Q  =  {G_total_kN + Q_dynamic_kN:.2f} kN",
    )

    combinations = [combo_uls, combo_seis, combo_sls]
    logger.debug(
        "Loads: G=%.2f kN, Q=%.2f kN, E_d=%.2f kN, ULS=%.2f kN",
        G_total_kN, Q_dynamic_kN, E_d_horizontal_kN, V_uls,
    )
    return G_total_kN, combinations
