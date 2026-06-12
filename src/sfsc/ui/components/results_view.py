"""Área de resultados — banner de diagnóstico, avisos críticos e tabs.

Auditoria F3.4 (componentização) e M-05 (avisos críticos no topo, antes das tabs).
A identidade visual é a da versão monolítica anterior.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from sfsc.assessment import assess_result
from sfsc.engineering import CalculationResultState
from sfsc.enums import CheckStatus
from sfsc.i18n import Lang, t
from sfsc.models import ReportContext
from sfsc.ui.support_visual import support_preview_html

_STATUS_KEY = {
    CheckStatus.OK: "status.ok",
    CheckStatus.MARGINAL: "status.marginal",
    CheckStatus.FAIL: "status.fail",
    CheckStatus.NOT_CHECKED: "status.not_checked",
    CheckStatus.INFORMATIVE: "status.informative",
}

_ENGINEERING_STATE_KEY = {
    CalculationResultState.VERIFIED: "engineering.state.verified",
    CalculationResultState.SIMPLIFIED: "engineering.state.simplified",
    CalculationResultState.NOT_VERIFIED: "engineering.state.notVerified",
    CalculationResultState.NOT_APPLICABLE: "engineering.state.notApplicable",
    CalculationResultState.REQUIRES_ENGINEER_REVIEW: "engineering.state.requiresEngineerReview",
    CalculationResultState.FAILED: "engineering.state.failed",
}


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def _member_status_label(status: str, lang: Lang) -> str:
    status_key = {
        "PASS": "status.ok",
        "MARGINAL": "status.marginal",
        "FAIL": "status.fail",
    }.get(status)
    return t(status_key, lang) if status_key else status


def _member_axis_label(axis: object, lang: Lang) -> str:
    if axis in ("y", "z"):
        return str(axis)
    return t("report.label.none", lang)


def _connection_status_label(status: str, lang: Lang) -> str:
    return {
        "verified": t("engineering.state.verified", lang),
        "failed": t("engineering.state.failed", lang),
        "not_verified": t("engineering.state.notVerified", lang),
        "requires_engineer_review": t("engineering.state.requiresEngineerReview", lang),
    }.get(status, status)


def _connection_check_rows(
    res,
    *,
    check_types: set[str] | None = None,
    lang: Lang = Lang.PT,
) -> list[dict[str, object]]:
    rows = []
    for row in getattr(res, "connection_check_rows", []):
        row_type = str(row.get("type", ""))
        if check_types is not None and row_type not in check_types:
            continue
        rows.append(
            {
                t("report.column.support", lang): str(row.get("support_id", "")),
                t("report.column.type", lang): row_type,
                t("report.column.status", lang): _connection_status_label(
                    str(row.get("status", "")),
                    lang,
                ),
                t("report.column.eta", lang): row.get("utilization_ratio"),
                t("report.column.combination", lang): str(
                    row.get("governing_combination", "")
                ),
                t("report.column.reactionFx", lang): row.get("reaction_fx_kN"),
                t("report.column.reactionFz", lang): row.get("reaction_fz_kN"),
                t("report.column.reactionMy", lang): row.get("reaction_my_kNm"),
                t("report.column.missingInputs", lang): "; ".join(
                    str(item) for item in row.get("missing_inputs", [])
                ),
                t("report.column.warnings", lang): "; ".join(
                    str(item) for item in row.get("warnings", [])
                ),
            }
        )
    return rows


def render(ctx: ReportContext, base_ctx: ReportContext, lang: Lang = Lang.PT) -> None:
    """Renderiza banner + avisos críticos + breakdown modular + tabs."""
    res = ctx.fan_support_result
    assert res is not None
    base_res = base_ctx.fan_support_result
    assessment = assess_result(res)

    _render_banner(res, assessment, lang)
    _render_critical_warnings(ctx)
    _render_serviceability_warning(ctx, res, lang)
    _render_module_breakdown(res)
    _render_engineering_state_summary(ctx)
    _render_import_review(ctx)
    _render_support_visual(ctx, res)
    _render_tabs(ctx, res, base_res)


def _render_module_breakdown(res, lang: Lang = Lang.PT) -> None:
    """Tabela clara de utilização POR módulo (tarefa 1.1) — sem misturar perfil
    com base plate."""
    if not res.module_breakdown:
        return
    st.subheader(t("report.section.moduleSummary", lang))
    rows = [
        {
            t("report.column.module", lang): t(c.label_key, lang),
            t("report.column.status", lang): t(
                _STATUS_KEY.get(c.status, "status.informative"), lang
            ),
            t("report.column.eta", lang): "N/A" if c.eta is None else f"{c.eta:.3f}",
            t("report.column.governing", lang): "★" if c.governing else "",
        }
        for c in res.module_breakdown
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_engineering_state_summary(ctx: ReportContext, lang: Lang = Lang.PT) -> None:
    report_state = ctx.engineering_report_state
    if report_state is None or not report_state.states:
        return
    st.subheader(t("engineering.summary.title", lang))
    rows = [
        {
            t("engineering.column.item", lang): t(item.label_key, lang),
            t("report.column.status", lang): t(_ENGINEERING_STATE_KEY[item.state], lang),
        }
        for item in report_state.states
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_import_review(ctx: ReportContext, lang: Lang = Lang.PT) -> None:
    import_review = ctx.import_review
    if import_review is None:
        return
    st.subheader(t("report.section.importReview", lang))
    col_1, col_2, col_3 = st.columns(3)
    col_1.metric(t("report.column.importedElements", lang), import_review.imported_elements_count)
    col_2.metric(t("report.column.acceptedMembers", lang), import_review.accepted_members_count)
    col_3.metric(t("report.column.rejectedElements", lang), import_review.rejected_elements_count)
    st.caption(
        f"{t('report.column.source', lang)}: {import_review.source.source_type} | "
        f"{t('report.column.fileName', lang)}: {import_review.source.file_name or '—'} | "
        f"{t('report.column.confirmed', lang)}: "
        f"{t('common.yes', lang) if import_review.confirmed else t('common.no', lang)}"
    )
    member_rows = [
        {
            t("report.column.element", lang): item.id,
            t("report.column.type", lang): item.classification,
            t("report.column.status", lang): (
                t("engineering.state.verified", lang)
                if item.accepted
                else t("engineering.state.notVerified", lang)
            ),
            t("report.column.member", lang): (
                f"{item.start_node_id or '—'} -> {item.end_node_id or '—'}"
            ),
            t("report.column.warnings", lang): "; ".join(item.warnings),
        }
        for item in import_review.members
    ]
    if member_rows:
        st.dataframe(pd.DataFrame(member_rows), hide_index=True, width="stretch")
    if import_review.warnings:
        warning_rows = [
            {
                t("report.column.warningCode", lang): item.code,
                t("report.column.warningSeverity", lang): item.severity,
                t("report.column.element", lang): item.element_id or "—",
                t("report.column.warnings", lang): item.message,
            }
            for item in import_review.warnings
        ]
        st.dataframe(pd.DataFrame(warning_rows), hide_index=True, width="stretch")


def _render_banner(res, assessment, lang: Lang = Lang.PT) -> None:
    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    col_s1.metric("Diagnóstico", assessment.headline)
    col_s2.metric("Estado técnico", res.status.value)
    col_s3.metric("Utilização gov.", _fmt_pct(assessment.utilization_percent))
    col_s4.metric("Conservadorismo", _fmt_pct(assessment.conservatism_percent))
    col_s5.metric("Uso do limite", _fmt_pct(assessment.limit_percent))

    msg = f"{assessment.summary} Verificação governante: {assessment.governing_item}."
    # REQUIRES_SPECIALIST nunca aparece como sucesso (auditoria C-03).
    if assessment.is_failure:
        st.error(msg)
    elif assessment.is_specialist:
        st.error(
            f"⚠️ **REQUER ESPECIALISTA** — {msg} "
            "Este resultado não pode ser usado sem revisão por engenheiro "
            "estrutural qualificado."
        )
    elif assessment.is_borderline:
        st.warning(msg)
    else:
        st.success(msg)

    # Phase 07: always show simplified model and unverified check warnings
    _is_global_frame = res.solver_engine == "global_frame" and not res.solver_failed
    if not _is_global_frame:
        st.warning(t("sidebar.results.simplifiedModel", lang))
    if not res.connection_check_rows:
        st.warning(t("sidebar.results.connectionNotVerified", lang))


def _render_critical_warnings(ctx: ReportContext) -> None:
    """Avisos CRITICAL no topo, antes das tabs (auditoria M-05)."""
    criticals = [w for w in ctx.warnings if w.severity == "CRITICAL"]
    for w in criticals:
        st.error(f"**[{w.code}]** {w.message}")


def _render_serviceability_warning(ctx: ReportContext, res, lang: Lang = Lang.PT) -> None:
    """Phase 07: show serviceability not_verified warning when deflection unavailable."""
    inp = ctx.fan_support_input
    if inp is None:
        return
    include_sls = inp.calculation_options.include_serviceability
    displacement_available = bool(res.solver_displacements)
    if include_sls and not displacement_available:
        st.warning(t("sidebar.results.serviceabilityNotVerified", lang))


def _render_support_visual(ctx: ReportContext, res, lang: Lang = Lang.PT) -> None:
    inp = ctx.fan_support_input
    if inp is None:
        return
    st.subheader("Vista do suporte")  # structural visual — not a calculation label
    components.html(support_preview_html(inp, res), height=640)


def _render_tabs(ctx: ReportContext, res, base_res, lang: Lang = Lang.PT) -> None:
    labels = ["Secção"]
    if res.platform:
        labels.append("Plataforma")
    # "Mesa / Chapa" is connection/fixation terminology, not tramex (ADR 001)
    labels.extend(["Mesa / Chapa", "Ancoragens", "Ligações", "Combinações", "Avisos", "Citações"])
    tabs = iter(st.tabs(labels))
    with next(tabs):
        _tab_section(ctx, res, base_res)
    if res.platform:
        with next(tabs):
            _tab_platform(res)
    with next(tabs):
        _tab_base_plate(res)
    with next(tabs):
        _tab_anchor(res)
    with next(tabs):
        _tab_connection(res)
    with next(tabs):
        _tab_combinations(res)
    with next(tabs):
        _tab_warnings(ctx)
    with next(tabs):
        _tab_citations(ctx)


def _tab_section(ctx, res, base_res) -> None:
    lang = Lang.PT
    if base_res and base_res.section_options:
        st.subheader("Perfis aprovados")
        option_rows = [
            {
                "Perfil": opt.section.designation,
                "Família": opt.section.family.value,
                "Peso [kg/m]": round(opt.section.weight_kgm, 1),
                "η máx.": opt.utilization_ratio,
                "Governa": opt.governing_check,
                "Estado": opt.status.value,
                "Ativo": "Sim"
                if res.recommended_section
                and opt.section.designation == res.recommended_section.designation
                else "",
            }
            for opt in base_res.section_options
        ]
        st.dataframe(pd.DataFrame(option_rows), hide_index=True, width="stretch")

    if res.recommended_section:
        sec = res.recommended_section
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"Perfil: **{sec.designation}**")
            grade = ctx.fan_support_input.steel_grade.value if ctx.fan_support_input else "—"
            st.markdown(f"Família: `{sec.family.value}` | Aço: `{grade}`")
            st.dataframe(
                {
                    "Propriedade": [
                        "h [mm]",
                        "b [mm]",
                        "tw [mm]",
                        "tf [mm]",
                        "A [cm²]",
                        "I_y [cm⁴]",
                        "W_el,y [cm³]",
                        "Peso [kg/m]",
                    ],
                    "Valor": [
                        f"{sec.h_mm:g}",
                        f"{sec.b_mm:g}",
                        f"{sec.tw_mm:g}",
                        f"{sec.tf_mm:g}",
                        f"{sec.A_cm2:g}",
                        f"{sec.I_y_cm4:g}",
                        f"{sec.W_el_y_cm3:g}",
                        f"{sec.weight_kgm:g}",
                    ],
                },
                hide_index=True,
            )
        with c2:
            if res.section_verification:
                sv = res.section_verification
                st.subheader(f"Utilização máxima: η = {sv.utilization_ratio:.3f}")
                st.caption(f"Governa: `{sv.governing_check}` | {sv.code_clause}")
                st.dataframe(
                    {
                        "Check": list(sv.utilization_by_check.keys()),
                        "η": [round(v, 4) for v in sv.utilization_by_check.values()],
                    },
                    hide_index=True,
                )

        if res.member_check_rows:
            st.subheader(t("report.section.memberChecks", lang))
            member_rows = [
                {
                    t("report.column.member", lang): str(row.get("member_id", "")),
                    t("report.column.type", lang): str(row.get("member_kind", "")),
                    t("report.column.status", lang): _member_status_label(
                        str(row.get("status", "")),
                        lang,
                    ),
                    t("report.column.eta", lang): row.get("utilization_ratio"),
                    t("report.column.governingCheck", lang): str(
                        row.get("governing_check", "")
                    ),
                    t("report.column.combination", lang): str(
                        row.get("governing_combination", "")
                    ),
                    t("report.column.axis", lang): _member_axis_label(
                        row.get("governing_axis"),
                        lang,
                    ),
                    t("report.column.axialForce", lang): row.get("axial_force_kN"),
                    t("report.column.shearForce", lang): row.get("shear_force_kN"),
                    t("report.column.bendingMoment", lang): row.get("bending_moment_kNm"),
                    t("report.column.warnings", lang): "; ".join(
                        str(item) for item in row.get("warnings", [])
                    ),
                }
                for row in res.member_check_rows
            ]
            st.dataframe(pd.DataFrame(member_rows), hide_index=True, width="stretch")

        # Memória de fórmulas (valores intermédios) — Fase 3.
        sv = res.section_verification
        if sv and sv.calculation_details:
            with st.expander("Memória de fórmulas (valores intermédios)"):
                d = sv.calculation_details
                st.dataframe(
                    {"Grandeza": list(d.keys()), "Valor": list(d.values())},
                    hide_index=True,
                )


def _tab_base_plate(res) -> None:
    lang = Lang.PT
    rows = _connection_check_rows(res, check_types={"base_plate", "base_plate_transfer"}, lang=lang)
    if rows:
        st.subheader(t("report.section.connectionChecks", lang))
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if not res.base_plate:
        st.info("Mesa não activada neste cálculo.")
        return
    bp = res.base_plate
    st.subheader(f"Chapa {bp.length_mm:.0f} × {bp.width_mm:.0f} × {bp.thickness_mm:.0f} mm")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Tensão de contacto", f"{bp.bearing_stress_mpa:.2f} MPa")
        st.metric("η bearing", f"{bp.utilization_bearing:.3f}")
        st.metric("η bending", f"{bp.utilization_bending:.3f}")
    with c2:
        st.metric("Parafusos ventilador → chapa", f"M{bp.bolt_diameter_mm:.0f} × {bp.n_bolts_fan}")
        st.metric("η bolt (fan)", f"{bp.bolt_utilization_fan:.3f}")
        st.metric("Soldadura garganta", f"{bp.weld_throat_mm:.1f} mm  η={bp.weld_utilization:.3f}")
    st.subheader("Furação e bordo livre")
    st.dataframe(
        {
            "Item": [
                "Furo ancoragem [mm]",
                "Espaçamento X [mm]",
                "Espaçamento Y [mm]",
                "Mín. espaçamento [mm]",
                "Bordo X [mm]",
                "Bordo Y [mm]",
                "Mín. bordo [mm]",
                "Geometria OK",
            ],
            "Valor": [
                f"{bp.hole_diameter_mm:.1f}",
                f"{bp.anchor_spacing_x_mm:.0f}",
                f"{bp.anchor_spacing_y_mm:.0f}",
                f"{bp.min_spacing_mm:.1f}",
                f"{bp.edge_distance_x_mm:.0f}",
                f"{bp.edge_distance_y_mm:.0f}",
                f"{bp.min_edge_distance_mm:.1f}",
                "Sim" if bp.spacing_ok and bp.edge_distance_ok else "Não",
            ],
        },
        hide_index=True,
    )
    st.subheader("Betão / arrancamento")
    st.dataframe(
        {
            "Verificação": ["Cone de betão", "Pull-out", "Pry-out"],
            "Capacidade [kN]": [
                bp.concrete_cone_capacity_kN,
                bp.pullout_capacity_kN,
                bp.pryout_capacity_kN,
            ],
            "η": [
                bp.utilization_concrete_cone,
                bp.utilization_pullout,
                bp.utilization_pryout,
            ],
        },
        hide_index=True,
    )


def _tab_platform(res) -> None:
    platform = res.platform
    if not platform:
        return
    st.subheader(f"Plataforma {platform.length_mm:.0f} × {platform.width_mm:.0f} mm")
    c1, c2, c3 = st.columns(3)
    c1.metric("Nº vigas", str(platform.n_beams))
    c2.metric("Carga por viga", f"{platform.load_per_beam_kN:.2f} kN")
    c3.metric("Momento por viga", f"{platform.moment_per_beam_kNm:.2f} kNm")
    st.dataframe(
        pd.DataFrame(
            [
                {"Item": "Área [m²]", "Valor": platform.area_m2},
                {"Item": "Peso tramex [kg]", "Valor": round(platform.surface_weight_kg, 1)},
                {"Item": "Peso aço [kg]", "Valor": round(platform.steel_weight_kg, 1)},
                {"Item": "Aço/Tramex [kN/m²]", "Valor": round(platform.surface_weight_kn_m2, 3)},
                {
                    "Item": "Axial por viga [kN]",
                    "Valor": round(platform.axial_per_beam_kN, 3),
                },
                {
                    "Item": "Com diagonais",
                    "Valor": "Sim" if platform.braced else "Não",
                },
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    if platform.diagonal:
        diag = platform.diagonal
        st.subheader("Diagonais / mãos-francesas")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Item": "Nº diagonais", "Valor": diag.n_diagonals},
                    {"Item": "Ângulo [°]", "Valor": round(diag.angle_deg, 2)},
                    {"Item": "Comprimento [mm]", "Valor": round(diag.length_mm, 1)},
                    {"Item": "Axial [kN]", "Valor": round(diag.axial_force_kN, 3)},
                    {
                        "Item": "η compressão",
                        "Valor": round(diag.utilization_compression, 4),
                    },
                    {
                        "Item": "η encurvadura",
                        "Valor": round(diag.utilization_buckling, 4),
                    },
                    {"Item": "η global", "Valor": round(diag.utilization_ratio, 4)},
                    {"Item": "Estado", "Valor": diag.status.value},
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(diag.code_clause)


def _tab_anchor(res) -> None:
    lang = Lang.PT
    rows = _connection_check_rows(res, check_types={"anchor_group"}, lang=lang)
    if rows:
        st.subheader(t("report.section.connectionChecks", lang))
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if not res.anchor:
        return
    anc = res.anchor
    is_rod = anc.anchor_type == "rod"
    st.caption(
        "Verificação: varões roscados de suspensão (sem betão)"
        if is_rod
        else "Verificação: ancoragens embebidas em betão"
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Nº varões" if is_rod else "Nº ancoragens", str(anc.n_anchors))
    c2.metric("Diâmetro", f"Ø{anc.anchor_diameter_mm:.0f} mm")
    if is_rod:
        c3.metric("η interacção", f"{anc.utilization_combined:.3f}")
    else:
        c3.metric("Profundidade hef", f"{anc.embedment_depth_mm:.0f} mm")
    c1.metric("N_Rd total", f"{anc.tensile_capacity_kN:.1f} kN")
    c2.metric("V_Rd total", f"{anc.shear_capacity_kN:.1f} kN")
    if not is_rod:
        c3.metric("η interacção", f"{anc.utilization_combined:.3f}")
    st.caption(f"Cláusula: {anc.code_clause}")


def _tab_connection(res) -> None:
    lang = Lang.PT
    rows = _connection_check_rows(res, check_types={"steel_fixation"}, lang=lang)
    if rows:
        st.subheader(t("report.section.connectionChecks", lang))
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if not res.metal_connection:
        return
    mc = res.metal_connection
    c1, c2, c3 = st.columns(3)
    c1.metric("Tipo", mc.connection_type)
    c2.metric("Parafusos", f"M{mc.bolt_diameter_mm:.0f} × {mc.n_bolts}")
    c3.metric("η global", f"{mc.utilization_ratio:.3f}")
    st.dataframe(
        {
            "Item": [
                "Chapa ligação [mm]",
                "Furo [mm]",
                "Espaçamento fornecido [mm]",
                "Espaçamento mínimo [mm]",
                "Bordo fornecido [mm]",
                "Bordo mínimo [mm]",
                "Capacidade corte parafusos [kN]",
                "Capacidade tração parafusos [kN]",
                "η corte parafusos",
                "η tração parafusos",
                "Solda a [mm]",
                "Comprimento solda [mm]",
                "η solda",
                "Stiffener",
                "Cantoneira",
                "Diagonal",
            ],
            "Valor": [
                f"{mc.plate_thickness_mm:.1f}",
                f"{mc.bolt_hole_diameter_mm:.1f}",
                f"{mc.provided_spacing_mm:.1f}",
                f"{mc.min_spacing_mm:.1f}",
                f"{mc.provided_edge_distance_mm:.1f}",
                f"{mc.min_edge_distance_mm:.1f}",
                f"{mc.bolt_shear_capacity_kN:.2f}",
                f"{mc.bolt_tension_capacity_kN:.2f}",
                f"{mc.utilization_bolt_shear:.3f}",
                f"{mc.utilization_bolt_tension:.3f}",
                f"{mc.weld_throat_mm:.1f}",
                f"{mc.weld_length_mm:.0f}",
                f"{mc.weld_utilization:.3f}",
                f"{mc.stiffener_thickness_mm:.1f} mm" if mc.stiffener_required else "Não",
                mc.cleat_angle or "n/a",
                mc.diagonal_member or "n/a",
            ],
        },
        hide_index=True,
    )
    st.caption(f"Cláusula: {mc.code_clause}")


def _tab_combinations(res) -> None:
    def _rows(combos):
        return [
            {
                "Combinação": c.name,
                "V_z (kN)": round(c.V_z_kN, 3),
                "V_y (kN)": round(c.V_y_kN, 3),
                "M_y (kNm)": round(c.M_y_kNm, 3),
                "M_z (kNm)": round(c.M_z_kNm, 3),
                "N (kN)": round(c.N_kN, 3),
                "Gov.": "★" if c.governing else "",
                "Descrição": c.description,
            }
            for c in combos
        ]

    if res.all_combinations:
        st.subheader("Combinações de acções (totais)")
        st.dataframe(pd.DataFrame(_rows(res.all_combinations)), hide_index=True, width="stretch")
    if res.member_forces:
        st.subheader("Esforços de cálculo no elemento")
        st.dataframe(pd.DataFrame(_rows(res.member_forces)), hide_index=True, width="stretch")
        st.caption(
            "As acções totais e os esforços no elemento são níveis diferentes — "
            "não comparar directamente entre tabelas."
        )


def _tab_warnings(ctx) -> None:
    for w in ctx.warnings:
        if w.severity == "CRITICAL":
            st.error(f"**[{w.code}]** {w.message}")
        elif w.severity == "WARNING":
            st.warning(f"**[{w.code}]** {w.message}")
        else:
            st.info(f"**[{w.code}]** {w.message}")
    if ctx.assumptions_declared:
        st.subheader("Pressupostos declarados")
        for a in ctx.assumptions_declared:
            st.caption(f"• {a}")
    if ctx.limitations:
        st.subheader("Limitações")
        for lim in ctx.limitations:
            st.caption(f"• {lim}")


def _tab_citations(ctx) -> None:
    cit_rows = [
        {
            "Norma": c.standard_id,
            "Edição": c.edition,
            "Cláusula": c.clause,
            "Descrição": c.description,
        }
        for c in ctx.citations
    ]
    if cit_rows:
        st.dataframe(pd.DataFrame(cit_rows), hide_index=True, width="stretch")
