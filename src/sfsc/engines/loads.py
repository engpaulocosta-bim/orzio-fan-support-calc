"""Load engine for simplified EC/NBR/NCh action combinations."""

from __future__ import annotations

import logging

from ..enums import CantileverSubtype, LoadCaseName, StructuralCode, SupportType
from ..models import FanSupportInput, LoadCombination
from ..units import kg_to_kn, mm_to_m
from .load_surfaces import build_load_path_summary

logger = logging.getLogger("sfsc.loads")

_GAMMA: dict[str, dict[str, float]] = {
    "EC": {"gamma_G": 1.35, "gamma_Q": 1.50, "psi_0": 1.0},
    "BR": {"gamma_G": 1.40, "gamma_Q": 1.40, "psi_0": 1.0},
    "CL": {"gamma_G": 1.40, "gamma_Q": 1.60, "psi_0": 1.0},
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
    support_steel_weight_kg: float | None = None,
) -> tuple[float, list[LoadCombination]]:
    """Calculate total vertical load and simplified action combinations."""
    equipment_kN = kg_to_kn(inp.total_operating_weight_kg)

    if inp.support_type == SupportType.PLATFORM_FRAME_BRACED:
        if support_steel_weight_kg is None:
            steel_length_m = mm_to_m(inp.platform_length_eff_mm) * max(2, inp.platform_n_beams)
            if inp.cantilever_subtype in (None, CantileverSubtype.BRACKETED):
                steel_length_m += mm_to_m(
                    (inp.platform_length_eff_mm**2 + inp.installation_height_mm**2) ** 0.5
                ) * max(2, inp.platform_n_beams)
            support_steel_weight_kg = 22.0 * steel_length_m
        support_kN = kg_to_kn(support_steel_weight_kg)
    else:
        support_kN = 0.15 * equipment_kN

    load_path = build_load_path_summary(inp)
    surface_totals = load_path.vertical_totals_by_case

    permanent_kN = support_kN + surface_totals.get(LoadCaseName.G.value, 0.0)
    equipment_case_kN = equipment_kN + surface_totals.get(LoadCaseName.EQ.value, 0.0)
    manual_kN = surface_totals.get(LoadCaseName.MANUAL.value, 0.0)
    dynamic_kN = equipment_kN * (inp.dynamic_factor - 1.0)
    variable_kN = dynamic_kN + surface_totals.get(LoadCaseName.Q.value, 0.0)

    total_vertical_kN = permanent_kN + equipment_case_kN + variable_kN + manual_kN
    horizontal_seismic_kN = (permanent_kN + equipment_case_kN + manual_kN) * seismic_factor_g
    horizontal_total_kN = horizontal_seismic_kN + load_path.horizontal_total_kN

    group = _CODE_TO_GROUP.get(structural_code, "EC")
    gamma_g = _GAMMA[group]["gamma_G"]
    gamma_q = _GAMMA[group]["gamma_Q"]

    uls_vertical_kN = gamma_g * (permanent_kN + equipment_case_kN) + gamma_q * (
        variable_kN + manual_kN
    )
    combo_uls = LoadCombination(
        name="ULS_fundamental",
        V_z_kN=uls_vertical_kN,
        N_kN=0.0,
        load_factors_used={
            "gamma_G": gamma_g,
            "gamma_Q": gamma_q,
            "G_kN": round(permanent_kN, 3),
            "EQ_kN": round(equipment_case_kN, 3),
            "Q_kN": round(variable_kN, 3),
            "MANUAL_kN": round(manual_kN, 3),
            "G_equipment_kN": round(equipment_kN, 3),
            "G_support_kN": round(support_kN, 3),
            "G_surface_kN": round(surface_totals.get(LoadCaseName.G.value, 0.0), 3),
            "EQ_surface_kN": round(surface_totals.get(LoadCaseName.EQ.value, 0.0), 3),
            "Q_surface_kN": round(surface_totals.get(LoadCaseName.Q.value, 0.0), 3),
            "Q_dynamic_kN": round(dynamic_kN, 3),
            "manual_horizontal_kN": round(load_path.horizontal_total_kN, 3),
            "G_steel_kg": round(support_steel_weight_kg, 3)
            if inp.support_type == SupportType.PLATFORM_FRAME_BRACED
            and support_steel_weight_kg is not None
            else 0.0,
        },
        description=f"{gamma_g}x(G+EQ) + {gamma_q}x(Q+MANUAL) = {uls_vertical_kN:.2f} kN",
    )

    combo_seismic = LoadCombination(
        name="ULS_seismic",
        V_z_kN=permanent_kN + equipment_case_kN + manual_kN,
        V_y_kN=horizontal_total_kN,
        N_kN=0.0,
        load_factors_used={
            "gamma_G": 1.0,
            "ag_g": seismic_factor_g,
            "G_kN": round(permanent_kN, 3),
            "EQ_kN": round(equipment_case_kN, 3),
            "MANUAL_kN": round(manual_kN, 3),
            "manual_horizontal_kN": round(load_path.horizontal_total_kN, 3),
            "E_d_kN": round(horizontal_total_kN, 3),
        },
        description=(
            f"1.0x(G+EQ+MANUAL) + E_d = "
            f"{permanent_kN + equipment_case_kN + manual_kN:.2f} kN vertical + "
            f"{horizontal_total_kN:.2f} kN horizontal"
        ),
    )

    combo_sls = LoadCombination(
        name="SLS_characteristic",
        V_z_kN=total_vertical_kN,
        load_factors_used={
            "gamma_G": 1.0,
            "gamma_Q": 1.0,
            "G_kN": round(permanent_kN, 3),
            "EQ_kN": round(equipment_case_kN, 3),
            "Q_kN": round(variable_kN, 3),
            "MANUAL_kN": round(manual_kN, 3),
        },
        description=f"1.0x(G+EQ+Q+MANUAL) = {total_vertical_kN:.2f} kN",
    )

    combinations = [combo_uls, combo_seismic, combo_sls]
    logger.debug(
        "Loads: G=%.2f kN, EQ=%.2f kN, Q=%.2f kN, MANUAL=%.2f kN, H=%.2f kN, ULS=%.2f kN",
        permanent_kN,
        equipment_case_kN,
        variable_kN,
        manual_kN,
        horizontal_total_kN,
        uls_vertical_kN,
    )
    return total_vertical_kN, combinations
