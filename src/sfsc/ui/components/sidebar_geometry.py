"""Sidebar §6–7 — geometria e opções (anti-vibração, mesa, exposição, betão)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from sfsc.enums import AntiVibrationType, ExposureClass, FanConnectionType, SupportType


def render(support_type: SupportType) -> dict[str, Any]:
    """Renderiza geometria + opções; devolve os valores."""
    st.subheader("6. Geometria")
    span_mm = st.number_input("Vão / comprimento L [mm]", min_value=100.0, value=1200.0, step=50.0)
    h_inst_mm = st.number_input(
        "Altura de instalação h [mm]", min_value=50.0, value=500.0, step=50.0
    )
    ecc_mm = st.number_input("Excentricidade CG [mm]", min_value=0.0, value=0.0, step=10.0)
    dyn_fac = st.number_input(
        "Factor dinâmico",
        min_value=1.0,
        max_value=3.0,
        value=1.5,
        step=0.1,
        help="Default 1.5 (VDI 3840). Editável.",
    )

    hanger_rod_mm = None
    if support_type == SupportType.HANGER:
        hanger_rod_mm = st.number_input(
            "Comprimento dos varões [mm]", min_value=100.0, value=h_inst_mm, step=50.0
        )

    st.subheader("7. Opções")
    anti_vib_val = st.selectbox("Anti-vibração", [e.value for e in AntiVibrationType])
    anti_vib = AntiVibrationType(anti_vib_val)
    av_defl_mm = None
    if anti_vib == AntiVibrationType.SPRINGS:
        av_defl_mm = st.number_input("Deflexão estática molas [mm]", min_value=1.0, value=25.0)

    include_bp = st.checkbox("Incluir mesa / base plate", value=False)
    fan_conn_type = None
    bp_thick_mm = None
    if include_bp:
        conn_val = st.selectbox(
            "Tipo de fixação ventilador (informativo)",
            [e.value for e in FanConnectionType],
            help="Registado no memorial — não altera o modelo de cálculo da chapa.",
        )
        fan_conn_type = FanConnectionType(conn_val)
        bp_thick_mm = st.number_input(
            "Espessura chapa [mm] (0 = auto)",
            min_value=0.0,
            value=0.0,
            step=5.0,
            help=(
                "0 = dimensionar automaticamente; valor > 0 = a chapa fornecida "
                "é verificada (não redimensionada)."
            ),
        )
        if bp_thick_mm == 0.0:
            bp_thick_mm = None

    exposure_val = st.selectbox("Classe de exposição", [e.value for e in ExposureClass])
    exposure = ExposureClass(exposure_val)
    concrete_grade = st.selectbox(
        "Betão (ancoragens)", ["C20/25", "C25/30", "C30/37", "C35/45", "C40/50"], index=1
    )

    return {
        "span_mm": span_mm,
        "h_inst_mm": h_inst_mm,
        "ecc_mm": ecc_mm,
        "dyn_fac": dyn_fac,
        "hanger_rod_mm": hanger_rod_mm,
        "anti_vib": anti_vib,
        "av_defl_mm": av_defl_mm,
        "include_bp": include_bp,
        "fan_conn_type": fan_conn_type,
        "bp_thick_mm": bp_thick_mm,
        "exposure": exposure,
        "concrete_grade": concrete_grade,
    }
