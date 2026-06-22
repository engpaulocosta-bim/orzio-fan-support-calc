"""Sidebar §6–7 — geometria e opções (anti-vibração, mesa, exposição, betão)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from sfsc.enums import AntiVibrationType, ExposureClass, FanConnectionType, SupportType
from sfsc.i18n import Lang, t


def render(support_type: SupportType, lang: Lang = Lang.PT) -> dict[str, Any]:
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

    platform_n_beams = 2
    platform_n_crossbeams = 0
    platform_width_mm = None
    platform_length_mm = None
    if support_type == SupportType.PLATFORM_FRAME_BRACED:
        st.caption("Parâmetros específicos da plataforma metálica.")
        platform_n_beams = int(
            st.number_input(
                t("sidebar.geometry.platformLongitudinalBeams", lang),
                min_value=2,
                value=3,
                step=1,
            )
        )
        platform_n_crossbeams = int(
            st.number_input(
                t("sidebar.geometry.platformCrossbeams", lang),
                min_value=0,
                value=3,
                step=1,
                help=t("sidebar.geometry.platformCrossbeamsHelp", lang),
            )
        )
        platform_width_mm = st.number_input(
            "Largura da plataforma [mm]",
            min_value=200.0,
            value=2400.0,
            step=50.0,
        )
        platform_length_mm = st.number_input(
            "Comprimento da plataforma [mm]",
            min_value=200.0,
            value=span_mm,
            step=50.0,
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
    base_plate_input = None
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
        st.caption(t("sidebar.connection.basePlateInputs", lang))
        bp_length_mm = st.number_input(
            t("sidebar.connection.basePlateLength", lang),
            min_value=0.0,
            value=0.0,
            step=25.0,
        )
        bp_width_mm = st.number_input(
            t("sidebar.connection.basePlateWidth", lang),
            min_value=0.0,
            value=0.0,
            step=25.0,
        )
        bp_thickness_explicit_mm = st.number_input(
            t("sidebar.connection.basePlateThickness", lang),
            min_value=0.0,
            value=float(bp_thick_mm or 0.0),
            step=1.0,
        )
        bp_weld_mm = st.number_input(
            t("sidebar.connection.basePlateWeld", lang),
            min_value=0.0,
            value=0.0,
            step=1.0,
        )
        bp_bolt_diameter_mm = st.number_input(
            t("sidebar.connection.basePlateBoltDiameter", lang),
            min_value=0.0,
            value=0.0,
            step=2.0,
        )
        bp_bolt_count = int(
            st.number_input(
                t("sidebar.connection.basePlateBoltCount", lang),
                min_value=0,
                value=0,
                step=1,
            )
        )
        base_plate_input = {
            "length_mm": bp_length_mm or None,
            "width_mm": bp_width_mm or None,
            "thickness_mm": bp_thickness_explicit_mm or None,
            "weld_throat_mm": bp_weld_mm or None,
            "bolt_diameter_mm": bp_bolt_diameter_mm or None,
            "n_bolts": bp_bolt_count or None,
        }
        bp_thick_mm = bp_thickness_explicit_mm or None

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
        "platform_n_beams": platform_n_beams,
        "platform_n_crossbeams": platform_n_crossbeams,
        "platform_width_mm": platform_width_mm,
        "platform_length_mm": platform_length_mm,
        "anti_vib": anti_vib,
        "av_defl_mm": av_defl_mm,
        "include_bp": include_bp,
        "fan_conn_type": fan_conn_type,
        "bp_thick_mm": bp_thick_mm,
        "base_plate_input": base_plate_input,
        "exposure": exposure,
        "concrete_grade": concrete_grade,
    }
