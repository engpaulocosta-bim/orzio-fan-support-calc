"""Results area for the SFSC Streamlit UI.

``render_results`` takes a computed context (held in session_state so download
reruns don't wipe it) and draws the diagnosis banner, the per-topic tabs and the
export buttons.
"""
from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from sfsc.assessment import assess_result
from sfsc.enums import AnchorageSubstrate
from sfsc.engines.selector import context_for_section_choice
from sfsc.reports.exports import generate_csv, generate_excel
from sfsc.reports.memorial_pdf import generate_pdf
from sfsc.ui.support_visual import support_preview_html


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def render_results(ctx, fallback_support_tag: str, fallback_steel_grade) -> None:
    """Render the full results area for a computed context."""
    support_tag = st.session_state.get("sfsc_tag", fallback_support_tag)
    base_ctx = ctx
    base_res = base_ctx.fan_support_result

    if base_res and base_res.section_options:
        labels = {
            opt.section.designation: (
                f"{opt.section.designation} | {opt.section.family.value} | "
                f"η={opt.utilization_ratio:.3f} | {opt.section.weight_kgm:.1f} kg/m | "
                f"{opt.status.value}"
            )
            for opt in base_res.section_options
        }
        options = list(labels.keys())
        saved = st.session_state.get("sfsc_selected_section")
        default = saved if saved in options else (
            base_res.recommended_section.designation
            if base_res.recommended_section and base_res.recommended_section.designation in options
            else options[0]
        )
        selected_section = st.selectbox(
            "Perfil ativo para resultados e documentos",
            options,
            index=options.index(default),
            format_func=lambda value: labels[value],
        )
        st.session_state["sfsc_selected_section"] = selected_section
        ctx = context_for_section_choice(base_ctx, selected_section)

    res = ctx.fan_support_result
    assert res is not None
    assessment = assess_result(res)

    # ── Status banner ───────────────────────────────────────────────────────────
    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    col_s1.metric("Diagnóstico", assessment.headline)
    col_s2.metric("Estado técnico", res.status.value)
    col_s3.metric("Utilização gov.", _fmt_pct(assessment.utilization_percent))
    col_s4.metric("Conservadorismo", _fmt_pct(assessment.conservatism_percent))
    col_s5.metric("Uso do limite", _fmt_pct(assessment.limit_percent))

    assessment_message = f"{assessment.summary} Verificação governante: {assessment.governing_item}."
    if assessment.is_failure:
        st.error(assessment_message)
    elif assessment.is_borderline:
        st.warning(assessment_message)
    else:
        st.success(assessment_message)

    tab_labels = ["Modelo", "Secção"]
    if res.platform:
        tab_labels.append("Plataforma")
    tab_labels += ["Mesa", "Ancoragens", "Ligações", "Combinações", "Avisos", "Citações"]
    tabs = dict(zip(tab_labels, st.tabs(tab_labels)))

    with tabs["Modelo"]:
        _render_model_tab(ctx, res)
    with tabs["Secção"]:
        _render_section_tab(ctx, res, base_res, fallback_steel_grade)
    if "Plataforma" in tabs:
        with tabs["Plataforma"]:
            _render_platform_tab(res)
    with tabs["Mesa"]:
        _render_base_plate_tab(res)
    with tabs["Ancoragens"]:
        _render_anchor_tab(res)
    with tabs["Ligações"]:
        _render_connection_tab(res)
    with tabs["Combinações"]:
        _render_combinations_tab(res)
    with tabs["Avisos"]:
        _render_warnings_tab(ctx)
    with tabs["Citações"]:
        _render_citations_tab(ctx)

    _render_exports(ctx, support_tag)


# ── Tabs ─────────────────────────────────────────────────────────────────────────

def _render_model_tab(ctx, res) -> None:
    if ctx.fan_support_input:
        # Renderiza num iframe isolado: o sanitizador do st.markdown corrompe
        # SVG complexo e despeja a marcação como texto. st.iframe aceita HTML
        # inline e substitui o (depreciado) components.html.
        st.iframe(
            support_preview_html(ctx.fan_support_input, res),
            height=620,
        )


def _render_section_tab(ctx, res, base_res, fallback_steel_grade) -> None:
    if base_res and base_res.section_options:
        st.subheader("Perfis aprovados")
        option_rows = []
        for opt in base_res.section_options:
            option_rows.append({
                "Perfil": opt.section.designation,
                "Família": opt.section.family.value,
                "Categoria": opt.section.catalog_status,
                "Peso [kg/m]": round(opt.section.weight_kgm, 1),
                "η máx.": opt.utilization_ratio,
                "Governa": opt.governing_check,
                "Estado": opt.status.value,
                "Ativo": "Sim" if res.recommended_section and opt.section.designation == res.recommended_section.designation else "",
            })
        st.dataframe(pd.DataFrame(option_rows), hide_index=True, width="stretch")

        for opt in base_res.section_options:
            expanded = bool(
                res.recommended_section
                and opt.section.designation == res.recommended_section.designation
            )
            with st.expander(
                f"{opt.section.designation} - η={opt.utilization_ratio:.3f} - {opt.status.value}",
                expanded=expanded,
            ):
                sec_opt = opt.section
                st.dataframe({
                    "Propriedade": ["Família", "Categoria", "h [mm]", "b [mm]", "tw [mm]", "tf [mm]", "A [cm²]", "I_y [cm⁴]", "W_el,y [cm³]", "Peso [kg/m]"],
                    "Valor": [
                        sec_opt.family.value,
                        sec_opt.catalog_status,
                        f"{sec_opt.h_mm:g}",
                        f"{sec_opt.b_mm:g}",
                        f"{sec_opt.tw_mm:g}",
                        f"{sec_opt.tf_mm:g}",
                        f"{sec_opt.A_cm2:g}",
                        f"{sec_opt.I_y_cm4:g}",
                        f"{sec_opt.W_el_y_cm3:g}",
                        f"{sec_opt.weight_kgm:g}",
                    ],
                }, hide_index=True)
                st.dataframe({
                    "Check": list(opt.utilization_by_check.keys()),
                    "η": [round(v, 4) for v in opt.utilization_by_check.values()],
                }, hide_index=True)

    if res.recommended_section:
        sec = res.recommended_section
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"Perfil: **{sec.designation}**")
            _grade = ctx.fan_support_input.steel_grade.value if ctx.fan_support_input else fallback_steel_grade.value
            st.markdown(f"Família: `{sec.family.value}` | Categoria: `{sec.catalog_status}` | Aço: `{_grade}`")
            if sec.catalog_status in ("heavy", "hidden"):
                st.warning("Perfil aprovado, porém possivelmente sobredimensionado para esta carga.")
            st.dataframe({
                "Propriedade": ["h [mm]", "b [mm]", "tw [mm]", "tf [mm]", "A [cm²]", "I_y [cm⁴]", "W_el,y [cm³]", "Peso [kg/m]"],
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
            }, hide_index=True)
        with c2:
            if res.section_verification:
                sv = res.section_verification
                st.subheader(f"Utilização máxima: η = {sv.utilization_ratio:.3f}")
                st.caption(f"Governa: `{sv.governing_check}` | {sv.code_clause}")
                eta_data = {"Check": list(sv.utilization_by_check.keys()),
                            "η": [round(v, 4) for v in sv.utilization_by_check.values()]}
                st.dataframe(eta_data, hide_index=True)


def _render_platform_tab(res) -> None:
    p = res.platform
    if not p:
        return
    st.subheader(f"Plataforma de grelha — {p.n_beams} vigas paralelas")
    st.caption(
        ("Com mão-francesa (diagonais escoram a ponta)" if p.braced
         else "Sem mão-francesa (mesa biapoiada)")
        + f" • {p.length_mm:.0f} × {p.width_mm:.0f} mm • área {p.area_m2:.2f} m²"
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Carga por viga", f"{p.load_per_beam_kN:.2f} kN")
    c2.metric("Momento por viga", f"{p.moment_per_beam_kNm:.2f} kNm")
    c3.metric("Axial por viga", f"{p.axial_per_beam_kN:.2f} kN")

    st.subheader("Peso próprio do suporte")
    st.dataframe({
        "Parcela": ["Tramex / grating", "Estrutura de aço (vigas + diagonais)", "Total suporte"],
        "Peso [kg]": [
            f"{p.grating_weight_kg:.1f}  ({p.grating_kg_m2:.0f} kg/m²)",
            f"{p.steel_weight_kg:.1f}",
            f"{p.grating_weight_kg + p.steel_weight_kg:.1f}",
        ],
    }, hide_index=True)

    if p.diagonal:
        d = p.diagonal
        st.subheader(f"Mão-francesa (diagonais) — {d.n_diagonals} × @ {d.angle_deg:.1f}°")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Comprimento", f"{d.length_mm:.0f} mm")
        cc2.metric("Compressão por diagonal", f"{d.axial_force_kN:.2f} kN")
        cc3.metric("η diagonal", f"{d.utilization_ratio:.3f}")
        st.dataframe({
            "Verificação": ["Secção", "η compressão (6.2.4)", "η encurvadura (6.3.1)", "Estado"],
            "Valor": [
                d.section.designation if d.section else "n/a",
                f"{d.utilization_compression:.3f}",
                f"{d.utilization_buckling:.3f}",
                d.status.value,
            ],
        }, hide_index=True)
        st.caption(f"Cláusula: {d.code_clause}")
    else:
        st.info("Sem mão-francesa: a mesa apoia-se nas duas extremidades. "
                "Selecione 'Com mão-francesa' para escorar a ponta com diagonais.")


def _render_base_plate_tab(res) -> None:
    if not res.base_plate:
        st.info("Mesa não activada neste cálculo.")
        return
    bp = res.base_plate
    st.subheader(f"Chapa {bp.length_mm:.0f} × {bp.width_mm:.0f} × {bp.thickness_mm:.0f} mm")
    st.caption(
        "Material de fixação: "
        + ("Betão" if bp.anchorage_substrate == AnchorageSubstrate.CONCRETE else "Estrutura metálica")
    )
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
    st.dataframe({
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
    }, hide_index=True)
    if bp.anchorage_substrate == AnchorageSubstrate.CONCRETE:
        st.subheader("Betão / arrancamento")
        st.dataframe({
            "Verificação": ["Cone de betão", "Pull-out", "Pry-out"],
            "Capacidade [kN]": [
                bp.concrete_cone_capacity_kN,
                bp.pullout_capacity_kN,
                bp.pryout_capacity_kN,
            ],
            "Eta": [
                bp.utilization_concrete_cone,
                bp.utilization_pullout,
                bp.utilization_pryout,
            ],
        }, hide_index=True)
    else:
        st.info("Fixação em estrutura metálica: verificações de betão não se aplicam.")


def _render_anchor_tab(res) -> None:
    if not res.anchor:
        return
    anc = res.anchor
    c1, c2, c3 = st.columns(3)
    c1.metric("Conectores", f"{anc.connector_label}: {anc.n_anchors}")
    c2.metric("Diametro", f"M{anc.anchor_diameter_mm:.0f}")
    if anc.anchorage_substrate == AnchorageSubstrate.CONCRETE:
        c3.metric("Profundidade hef", f"{anc.embedment_depth_mm:.0f} mm")
    else:
        c3.metric("Embutimento", "n/a")
    c1.metric("N_Rd total", f"{anc.tensile_capacity_kN:.1f} kN")
    c2.metric("V_Rd total", f"{anc.shear_capacity_kN:.1f} kN")
    c3.metric("η interacção", f"{anc.utilization_combined:.3f}")
    if anc.anchorage_substrate == AnchorageSubstrate.STEEL_STRUCTURE:
        st.dataframe({
            "Verificação": [
                "Aço receptor",
                "Espessura receptor [mm]",
                "Bordo livre [mm]",
                "Espaçamento [mm]",
                "η parafuso tração/corte",
                "η esmagamento receptor",
                "η bordo/espaçamento",
                "η bloco de corte",
                "η prying",
            ],
            "Valor": [
                anc.receiver_steel_grade.value if anc.receiver_steel_grade else "n/a",
                f"{anc.receiver_plate_thickness_mm:.1f}",
                f"{anc.receiver_edge_distance_mm:.1f}",
                f"{anc.receiver_spacing_mm:.1f}",
                f"{anc.utilization_combined:.3f}",
                f"{anc.utilization_bearing:.3f}",
                f"{anc.utilization_tearout:.3f}",
                f"{anc.utilization_block_shear:.3f}",
                f"{anc.utilization_prying:.3f}",
            ],
        }, hide_index=True)
    st.caption(f"Cláusula: {anc.code_clause}")


def _render_connection_tab(res) -> None:
    if not res.metal_connection:
        return
    mc = res.metal_connection
    c1, c2, c3 = st.columns(3)
    c1.metric("Tipo", mc.connection_type)
    c2.metric("Parafusos", f"M{mc.bolt_diameter_mm:.0f} × {mc.n_bolts}")
    c3.metric("η global", f"{mc.utilization_ratio:.3f}")
    st.dataframe({
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
    }, hide_index=True)
    st.caption(f"Cláusula: {mc.code_clause}")


def _render_combinations_tab(res) -> None:
    if not res.all_combinations:
        return
    rows = []
    for c in res.all_combinations:
        rows.append({
            "Combinação": c.name,
            "V_z (kN)": round(c.V_z_kN, 3),
            "V_y (kN)": round(c.V_y_kN, 3),
            "M_y (kNm)": round(c.M_y_kNm, 3),
            "N (kN)": round(c.N_kN, 3),
            "Gov.": "★" if c.governing else "",
            "Descrição": c.description,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_warnings_tab(ctx) -> None:
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


def _render_citations_tab(ctx) -> None:
    cit_rows = [{"Norma": c.standard_id, "Edição": c.edition,
                 "Cláusula": c.clause, "Descrição": c.description}
                for c in ctx.citations]
    if cit_rows:
        st.dataframe(pd.DataFrame(cit_rows), hide_index=True, width="stretch")


def _render_exports(ctx, support_tag: str) -> None:
    st.divider()
    st.subheader("Exportar memorial")
    col_e1, col_e2, col_e3 = st.columns(3)
    today = datetime.date.today()

    with col_e1:
        st.download_button(
            "📄 Download PDF",
            data=generate_pdf(ctx),
            file_name=f"sfsc_{support_tag}_{today}.pdf",
            mime="application/pdf",
            width="stretch",
        )
    with col_e2:
        st.download_button(
            "📊 Download Excel",
            data=generate_excel(ctx),
            file_name=f"sfsc_{support_tag}_{today}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with col_e3:
        st.download_button(
            "📋 Download CSV",
            data=generate_csv(ctx),
            file_name=f"sfsc_{support_tag}_{today}.csv",
            mime="text/csv",
            width="stretch",
        )
