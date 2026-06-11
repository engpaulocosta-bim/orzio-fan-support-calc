"""Sidebar §2 — unidades de ventilador e política de peso."""

from __future__ import annotations

from typing import Any

import streamlit as st

from sfsc.enums import FanType
from sfsc.policy import (
    WEIGHT_BLOCK_KG,
    WEIGHT_MIN_RECOMMENDED_KG,
    WEIGHT_PRODUCT_MAX_KG,
    WeightBand,
    weight_band,
)


def render() -> tuple[list[dict[str, Any]], bool]:
    """Renderiza as unidades de ventilador; devolve (unidades, confirmação 600–1000 kg)."""
    st.subheader("2. Ventilador")
    n_units = st.number_input("Número de unidades", min_value=1, max_value=10, value=1)

    fan_unit_inputs: list[dict[str, Any]] = []
    for i in range(int(n_units)):
        with st.expander(f"Unidade {i + 1}", expanded=(i == 0)):
            fan_type = st.selectbox(f"Tipo [{i + 1}]", [e.value for e in FanType], key=f"ft{i}")
            weight_kg = st.number_input(
                f"Peso vazio [kg] (informativo) [{i + 1}]",
                min_value=1.0,
                value=120.0,
                step=5.0,
                key=f"wv{i}",
                help="Apenas registado no memorial — o cálculo usa o peso em operação.",
            )
            op_weight = st.number_input(
                f"Peso operação [kg] [{i + 1}]",
                min_value=1.0,
                value=130.0,
                step=5.0,
                key=f"wo{i}",
            )
            fl_len = st.number_input(
                f"Comprimento base [mm] [{i + 1}]",
                min_value=100.0,
                value=800.0,
                step=50.0,
                key=f"fl{i}",
            )
            fl_wid = st.number_input(
                f"Largura base [mm] [{i + 1}]",
                min_value=100.0,
                value=600.0,
                step=50.0,
                key=f"fw{i}",
            )
            cg_h = st.number_input(
                f"Altura CG [mm] [{i + 1}]", min_value=0.0, value=300.0, step=10.0, key=f"cg{i}"
            )
            fan_unit_inputs.append(
                {
                    "tag": f"V{i + 1}",
                    "fan_type": fan_type,
                    "weight_kg": weight_kg,
                    "operating_weight_kg": op_weight,
                    "footprint_length_mm": fl_len,
                    "footprint_width_mm": fl_wid,
                    "centre_of_gravity_height_mm": cg_h,
                }
            )

    confirm_extended = _render_weight_policy(fan_unit_inputs)
    return fan_unit_inputs, confirm_extended


def _render_weight_policy(fan_unit_inputs: list[dict[str, Any]]) -> bool:
    """Feedback da política de peso (sfsc.policy) + confirmação da faixa EXTENDED."""
    total_op_weight = sum(u["operating_weight_kg"] for u in fan_unit_inputs)
    band = weight_band(total_op_weight)
    confirm_extended = False
    if band == WeightBand.BLOCKED:
        st.error(
            f"Peso total {total_op_weight:.0f} kg acima do limite de "
            f"{WEIGHT_BLOCK_KG:.0f} kg — fora do âmbito do SFSC."
        )
    elif band == WeightBand.EXTENDED:
        st.warning(
            f"Peso total {total_op_weight:.0f} kg fora da faixa do produto "
            f"(35–{WEIGHT_PRODUCT_MAX_KG:.0f} kg)."
        )
        confirm_extended = st.checkbox(
            f"Confirmo a utilização fora da faixa do produto "
            f"({WEIGHT_PRODUCT_MAX_KG:.0f}–{WEIGHT_BLOCK_KG:.0f} kg) — "
            "o resultado exige revisão por engenheiro estrutural qualificado.",
            value=False,
        )
    elif band == WeightBand.SPECIALIST:
        st.warning(
            f"Peso total {total_op_weight:.0f} kg > 500 kg — o resultado será "
            "classificado REQUIRES_SPECIALIST."
        )
    elif band == WeightBand.BELOW_MIN:
        st.info(
            f"Peso total {total_op_weight:.0f} kg abaixo da faixa validada "
            f"({WEIGHT_MIN_RECOMMENDED_KG:.0f} kg) — resultado PRELIMINARY."
        )
    return confirm_extended
