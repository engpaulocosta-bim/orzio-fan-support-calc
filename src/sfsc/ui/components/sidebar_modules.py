"""Sidebar section for load surface, fixation, and optional calculation modules."""

from __future__ import annotations

from typing import Any

import streamlit as st

from sfsc.enums import (
    BoltClass,
    CalculationMode,
    LoadCaseName,
    LoadDirection,
    LoadDistributionMethod,
    ManualLoadType,
    SteelConnectionType,
    SupportFixationMedium,
    SupportType,
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
_DISTRIBUTION_KEYS = {
    LoadDistributionMethod.ONE_WAY: "loadDistribution.oneWay",
    LoadDistributionMethod.TWO_WAY: "loadDistribution.twoWay",
    LoadDistributionMethod.TRIBUTARY_WIDTH: "loadDistribution.tributaryWidth",
    LoadDistributionMethod.MANUAL: "loadDistribution.manual",
}
_MANUAL_TYPE_KEYS = {
    ManualLoadType.POINT: "manualLoadType.point",
    ManualLoadType.LINE: "manualLoadType.line",
    ManualLoadType.AREA: "manualLoadType.area",
}
_LOAD_CASE_KEYS = {
    LoadCaseName.G: "loadCase.G",
    LoadCaseName.Q: "loadCase.Q",
    LoadCaseName.EQ: "loadCase.EQ",
    LoadCaseName.MANUAL: "loadCase.MANUAL",
}
_DIRECTION_KEYS = {
    LoadDirection.GLOBAL_X: "loadDirection.globalX",
    LoadDirection.GLOBAL_Y: "loadDirection.globalY",
    LoadDirection.GLOBAL_Z: "loadDirection.globalZ",
    LoadDirection.LOCAL_Y: "loadDirection.localY",
    LoadDirection.LOCAL_Z: "loadDirection.localZ",
}


def _member_target_options(
    support_type: SupportType,
    platform_n_beams: int,
    platform_n_crossbeams: int,
) -> list[str]:
    if support_type == SupportType.PLATFORM_FRAME_BRACED:
        labels = [f"beam_{index}" for index in range(1, max(2, platform_n_beams) + 1)]
        labels.extend(f"crossbeam_{index}" for index in range(1, max(0, platform_n_crossbeams) + 1))
        return labels
    return ["primary_member"]


def render(
    support_type: SupportType,
    platform_n_beams: int,
    platform_n_crossbeams: int,
    lang: Lang = Lang.PT,
) -> dict[str, Any]:
    """Render load surface, fixation, mode, and optional-module controls."""
    st.subheader("8. Superfície e fixação")

    member_targets = _member_target_options(
        support_type,
        platform_n_beams,
        platform_n_crossbeams,
    )

    surf_type = st.selectbox(
        t("sidebar.surface.type", lang),
        list(WalkingSurfaceType),
        format_func=lambda s: t(_SURFACE_KEYS[s], lang),
        help=t("warning.surface.notBasePlate", lang),
    )
    surf_weight = 0.0
    imposed_load = 0.0
    maintenance_load = 0.0
    surf_distributed = False
    distribution_method = (
        LoadDistributionMethod.TWO_WAY
        if support_type == SupportType.PLATFORM_FRAME_BRACED
        and platform_n_beams >= 2
        and platform_n_crossbeams >= 2
        else LoadDistributionMethod.ONE_WAY
    )
    surface_targets: list[str] = []

    if surf_type != WalkingSurfaceType.NONE:
        surf_weight = st.number_input(
            t("sidebar.surface.selfWeight", lang),
            min_value=0.0,
            value=0.45,
            step=0.05,
        )
        imposed_load = st.number_input(
            t("sidebar.surface.imposedLoad", lang),
            min_value=0.0,
            value=0.0,
            step=0.10,
        )
        maintenance_load = st.number_input(
            t("sidebar.surface.maintenanceLoad", lang),
            min_value=0.0,
            value=0.0,
            step=0.10,
        )
        surf_distributed = st.checkbox(
            t("sidebar.surface.equipmentDistributed", lang),
            value=False,
        )
        distribution_method = st.selectbox(
            t("sidebar.surface.distributionMethod", lang),
            list(LoadDistributionMethod),
            format_func=lambda item: t(_DISTRIBUTION_KEYS[item], lang),
            help=t("warning.surface.simplifiedDistribution", lang),
        )
        if distribution_method == LoadDistributionMethod.MANUAL:
            surface_targets = st.multiselect(
                t("sidebar.surface.targetMembers", lang),
                member_targets,
                default=[],
            )
        st.caption(t("warning.surface.simplifiedDistribution", lang))

    st.subheader(t("sidebar.surface.manualLoadsHeading", lang))
    manual_load_count = int(
        st.number_input(
            t("sidebar.surface.manualLoadCount", lang),
            min_value=0,
            max_value=3,
            value=0,
            step=1,
        )
    )
    manual_loads: list[dict[str, object]] = []
    for index in range(manual_load_count):
        st.caption(f"{t('sidebar.manualLoad.item', lang)} {index + 1}")
        name = st.text_input(
            t("sidebar.manualLoad.name", lang),
            value=f"manual_{index + 1}",
            key=f"manual_load_name_{index}",
        )
        load_type = st.selectbox(
            t("sidebar.manualLoad.type", lang),
            list(ManualLoadType),
            format_func=lambda item: t(_MANUAL_TYPE_KEYS[item], lang),
            key=f"manual_load_type_{index}",
        )
        load_case = st.selectbox(
            t("sidebar.manualLoad.case", lang),
            list(LoadCaseName),
            format_func=lambda item: t(_LOAD_CASE_KEYS[item], lang),
            key=f"manual_load_case_{index}",
        )
        direction = st.selectbox(
            t("sidebar.manualLoad.direction", lang),
            list(LoadDirection),
            format_func=lambda item: t(_DIRECTION_KEYS[item], lang),
            key=f"manual_load_direction_{index}",
        )
        value = st.number_input(
            t("sidebar.manualLoad.value", lang),
            min_value=0.0,
            value=0.0,
            step=0.10,
            key=f"manual_load_value_{index}",
        )
        target = st.selectbox(
            t("sidebar.manualLoad.target", lang),
            [t("common.none", lang)] + member_targets,
            key=f"manual_load_target_{index}",
        )
        manual_item: dict[str, object] = {
            "name": name,
            "load_type": load_type.value,
            "load_case": load_case.value,
            "direction": direction.value,
            "value": value,
            "target_member_id": None if target == t("common.none", lang) else target,
        }
        if load_type == ManualLoadType.LINE:
            manual_item["loaded_length_m"] = st.number_input(
                t("sidebar.manualLoad.length", lang),
                min_value=0.01,
                value=1.00,
                step=0.10,
                key=f"manual_load_length_{index}",
            )
        if load_type == ManualLoadType.AREA:
            manual_item["loaded_area_m2"] = st.number_input(
                t("sidebar.manualLoad.area", lang),
                min_value=0.01,
                value=1.00,
                step=0.10,
                key=f"manual_load_area_{index}",
            )
        manual_loads.append(manual_item)

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
            "Espessura chapa ligação [mm]",
            min_value=4.0,
            value=10.0,
            step=1.0,
        )
        steel_fix = {
            "connection_type": conn_val,
            "bolt_diameter_mm": bolt_d,
            "number_of_bolts": int(n_bolts),
            "bolt_class": bolt_cls,
            "plate_thickness_mm": plate_t,
        }

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

    anchor_layout = None
    if fix_medium == SupportFixationMedium.CONCRETE and (inc_bp or inc_anchors):
        st.caption(t("sidebar.connection.anchorInputs", lang))
        anchor_count = int(
            st.number_input(
                t("sidebar.connection.anchorCount", lang),
                min_value=0,
                value=0,
                step=1,
            )
        )
        anchor_diameter_mm = st.number_input(
            t("sidebar.connection.anchorDiameter", lang),
            min_value=0.0,
            value=0.0,
            step=2.0,
        )
        anchor_spacing_x_mm = st.number_input(
            t("sidebar.connection.anchorSpacingX", lang),
            min_value=0.0,
            value=0.0,
            step=10.0,
        )
        anchor_spacing_y_mm = st.number_input(
            t("sidebar.connection.anchorSpacingY", lang),
            min_value=0.0,
            value=0.0,
            step=10.0,
        )
        anchor_edge_x_mm = st.number_input(
            t("sidebar.connection.anchorEdgeX", lang),
            min_value=0.0,
            value=0.0,
            step=10.0,
        )
        anchor_edge_y_mm = st.number_input(
            t("sidebar.connection.anchorEdgeY", lang),
            min_value=0.0,
            value=0.0,
            step=10.0,
        )
        anchor_layout = {
            "n_anchors": anchor_count or None,
            "anchor_diameter_mm": anchor_diameter_mm or None,
            "spacing_x_mm": anchor_spacing_x_mm or None,
            "spacing_y_mm": anchor_spacing_y_mm or None,
            "edge_distance_x_mm": anchor_edge_x_mm or None,
            "edge_distance_y_mm": anchor_edge_y_mm or None,
        }

    return {
        "walking_surface": {
            "surface_type": surf_type.value,
            "self_weight_kn_m2": surf_weight,
            "equipment_load_distributed": surf_distributed,
            "imposed_load_kn_m2": imposed_load,
            "maintenance_load_kn_m2": maintenance_load,
            "distribution_method": distribution_method.value,
            "target_member_ids": surface_targets,
        },
        "manual_loads": manual_loads,
        "support_fixation_medium": fix_medium,
        "steel_fixation": steel_fix,
        "anchor_layout": anchor_layout,
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
