"""Sidebar §8 — superfície, meio de fixação e módulos de cálculo opcionais.

Tarefas 1.3, 1.5, 2.2–2.4: o utilizador escolhe a superfície de apoio (tramex
≠ base plate), o meio de fixação (betão vs estrutura metálica) e quais módulos
entram no cálculo. As regras de coerência (betão↔ancoragens, aço↔ligações)
são aplicadas aqui e reforçadas no motor.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from sfsc.enums import (
    BoltClass,
    CalculationMode,
    SteelConnectionType,
    SupportFixationMedium,
    WalkingSurfaceType,
)
from sfsc.i18n import Lang, t

_SURFACE_KEYS = {
    WalkingSurfaceType.NONE: "surface.none.label",
    WalkingSurfaceType.STEEL_GRATING_TRAMEX: "surface.tramex.label",
    WalkingSurfaceType.CHECKER_PLATE: "surface.checkerPlate.label",
    WalkingSurfaceType.SOLID_PLATE: "surface.solidPlate.label",
    WalkingSurfaceType.OTHER: "surface.other.label",
}
_FIXATION_KEYS = {
    SupportFixationMedium.CONCRETE: "fixation.concrete.label",
    SupportFixationMedium.STEEL_STRUCTURE: "fixation.steelStructure.label",
    SupportFixationMedium.MASONRY: "fixation.masonry.label",
    SupportFixationMedium.MIXED: "fixation.mixed.label",
    SupportFixationMedium.UNKNOWN: "fixation.unknown.label",
}


def render(lang: Lang = Lang.PT) -> dict[str, Any]:
    """Renderiza superfície, fixação, modo e toggles de módulos."""
    st.subheader("8. Superfície e fixação")

    # ── Superfície de apoio (tramex ≠ base plate) ────────────────────────────
    surf_type = st.selectbox(
        "Superfície de apoio (walking surface)",
        list(WalkingSurfaceType),
        format_func=lambda s: t(_SURFACE_KEYS[s], lang),
        help=t("warning.surface.notBasePlate", lang),
    )
    surf_weight = 0.0
    surf_distributed = False
    if surf_type != WalkingSurfaceType.NONE:
        surf_weight = st.number_input(
            "Peso próprio da superfície [kN/m²]", min_value=0.0, value=0.45, step=0.05
        )
        surf_distributed = st.checkbox(
            "Carga do equipamento distribuída na superfície", value=False
        )

    # ── Meio de fixação ──────────────────────────────────────────────────────
    fix_medium = st.selectbox(
        "Meio de fixação do suporte",
        list(SupportFixationMedium),
        format_func=lambda f: t(_FIXATION_KEYS[f], lang),
    )
    is_steel = fix_medium == SupportFixationMedium.STEEL_STRUCTURE

    steel_fix = None
    if is_steel:
        st.caption(t("warning.steel.receivingMemberNotChecked", lang))
        conn_val = st.selectbox("Tipo de ligação aço-aço", [c.value for c in SteelConnectionType])
        bolt_d = st.number_input("Diâmetro parafuso [mm]", min_value=8.0, value=16.0, step=2.0)
        n_bolts = st.number_input("Número de parafusos", min_value=1, value=4, step=1)
        bolt_cls = st.selectbox("Classe parafuso", [c.value for c in BoltClass], index=2)
        plate_t = st.number_input(
            "Espessura chapa ligação [mm]", min_value=4.0, value=10.0, step=1.0
        )
        steel_fix = {
            "connection_type": conn_val,
            "bolt_diameter_mm": bolt_d,
            "number_of_bolts": int(n_bolts),
            "bolt_class": bolt_cls,
            "plate_thickness_mm": plate_t,
        }

    # ── Modo de cálculo ──────────────────────────────────────────────────────
    st.subheader("9. Modo e módulos")
    mode_val = st.selectbox(
        "Modo de cálculo",
        [m.value for m in CalculationMode],
        index=2,
        help=t("benchmark.note", lang),
    )
    mode = CalculationMode(mode_val)
    if mode == CalculationMode.ROBOT_BENCHMARK:
        st.warning(t("benchmark.note", lang))

    # ── Toggles de módulos ───────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        inc_dyn = st.checkbox(t("calculation.modules.dynamicFactor", lang), value=True)
        inc_biax = st.checkbox(t("calculation.modules.biaxialBending", lang), value=True)
        inc_ltb = st.checkbox(t("calculation.modules.lateralTorsionalBuckling", lang), value=True)
        inc_bp = st.checkbox(t("calculation.modules.basePlate", lang), value=False)
    with c2:
        inc_anchors = st.checkbox(
            t("calculation.modules.anchors", lang),
            value=not is_steel,
            disabled=is_steel,
            help=t("warning.anchors.steelMediumDisablesConcrete", lang) if is_steel else None,
        )
        inc_conn = st.checkbox(t("calculation.modules.steelConnections", lang), value=True)
        inc_seis = st.checkbox(t("calculation.modules.seismicEquivalentStatic", lang), value=True)
        inc_serv = st.checkbox(t("calculation.modules.serviceability", lang), value=False)

    return {
        "walking_surface": {
            "surface_type": surf_type.value,
            "self_weight_kn_m2": surf_weight,
            "equipment_load_distributed": surf_distributed,
        },
        "support_fixation_medium": fix_medium,
        "steel_fixation": steel_fix,
        "calculation_mode": mode,
        "calculation_options": {
            "include_dynamic_factor": inc_dyn,
            "include_biaxial_bending": inc_biax,
            "include_lateral_torsional_buckling": inc_ltb,
            "include_base_plate": inc_bp,
            "include_anchors": inc_anchors,
            "include_steel_connections": inc_conn,
            "include_seismic_equivalent_static": inc_seis,
            "include_serviceability": inc_serv,
        },
    }
