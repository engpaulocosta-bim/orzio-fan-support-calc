"""Interface Streamlit — SFSC Steel Fan Support Calc."""

from __future__ import annotations

import datetime
import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import streamlit as st
from pydantic import ValidationError as PydanticValidationError

from sfsc.assessment import assess_result
from sfsc.catalogs.seismic_catalog import list_zones
from sfsc.engines.selector import context_for_section_choice, run_full_calculation
from sfsc.enums import (
    AntiVibrationType,
    CantileverSubtype,
    Country,
    ExposureClass,
    FanConnectionType,
    FanType,
    OperationMode,
    SectionFamily,
    SteelGrade,
    SupportType,
)
from sfsc.exceptions import SFSCBaseError
from sfsc.models import FanSupportInput, FanUnit
from sfsc.policy import (
    WEIGHT_BLOCK_KG,
    WEIGHT_MIN_RECOMMENDED_KG,
    WEIGHT_PRODUCT_MAX_KG,
    WeightBand,
    weight_band,
)
from sfsc.reports.exports import generate_csv, generate_excel
from sfsc.reports.memorial_pdf import generate_pdf

logger = logging.getLogger("sfsc.ui")


def main() -> None:
    """Render the SFSC Streamlit UI. Called on every Streamlit rerun."""
    # ── Tema ──────────────────────────────────────────────────────────────────────
    st.set_page_config(
        page_title="SFSC — Steel Fan Support Calc",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
    <style>
        .main-title {font-size:2rem; font-weight:800; color:#1447E6; margin-bottom:0}
        .sub-title  {font-size:1rem; color:#64748B; margin-top:0}
        .status-pass    {background:#DCFCE7; color:#166534; padding:6px 12px; border-radius:6px; font-weight:600}
        .status-fail    {background:#FEE2E2; color:#991B1B; padding:6px 12px; border-radius:6px; font-weight:600}
        .status-marginal{background:#FEF9C3; color:#713F12; padding:6px 12px; border-radius:6px; font-weight:600}
        .status-specialist{background:#FEE2E2; color:#7C3AED; padding:6px 12px; border-radius:6px; font-weight:600}
        .eta-ok   {color:#16A34A; font-weight:600}
        .eta-warn {color:#CA8A04; font-weight:600}
        .eta-fail {color:#DC2626; font-weight:600}
        div[data-testid="stMetricValue"] {font-size:1.3rem}
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<p class="main-title">SFSC — Steel Fan Support Calc</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-title">Dimensionamento de suportes metálicos para ventiladores industriais (35–600 kg)</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ════════════════════════════════════════════════════════════════════════════════
    # SIDEBAR — entradas
    # ════════════════════════════════════════════════════════════════════════════════
    with st.sidebar:
        st.header("Configuração")

        # ── Identificação ──
        st.subheader("1. Identificação")
        project_name = st.text_input("Nome do projecto", value="Projecto Demo")
        support_tag = st.text_input("Tag do suporte", value="FSU-001")
        design_notes = st.text_area("Notas", height=60)

        # ── Ventilador ──
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

        # ── Política de peso (sfsc.policy) ──
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

        # ── Tipo de suporte ──
        st.subheader("3. Tipo de Suporte")
        support_type_val = st.selectbox(
            "Tipo",
            [e.value for e in SupportType],
            format_func=lambda x: x.replace("_", " ").title(),
        )
        support_type = SupportType(support_type_val)

        cantilever_subtype = None
        if support_type == SupportType.CANTILEVER_1:
            csub = st.radio("Subtipo consola", ["pure", "bracketed"], horizontal=True)
            cantilever_subtype = CantileverSubtype(csub)

        operation_mode = OperationMode.DIMENSION
        received_section_tag = None
        received_section_family = None

        # ── País e Sismo ──
        st.subheader("4. País / Norma / Sismo")
        country_val = st.selectbox(
            "País",
            [e.value for e in Country],
            format_func=lambda x: {
                "PT": "Portugal",
                "ES": "Espanha",
                "IE": "Irlanda",
                "EU": "Europa (genérico)",
                "UK": "Reino Unido",
                "FR": "França",
                "BR": "Brasil",
                "CL": "Chile",
            }.get(x, x),
        )
        country = Country(country_val)

        zones_dict = list_zones(country)
        zone_options = list(zones_dict.keys())
        zone_descs = [f"{k} — {v.get('description', '')}" for k, v in zones_dict.items()]
        if zone_options:
            seismic_zone_sel = st.selectbox(
                "Zona sísmica (None = default conservativo)", ["Automático (default)"] + zone_descs
            )
            if seismic_zone_sel == "Automático (default)":
                seismic_zone = None
            else:
                seismic_zone = zone_options[zone_descs.index(seismic_zone_sel)]
        else:
            seismic_zone = None

        # ── Material ──
        st.subheader("5. Material e Perfis")
        steel_grade_val = st.selectbox("Grau do aço", [e.value for e in SteelGrade])
        steel_grade = SteelGrade(steel_grade_val)

        fam_options = [e.value for e in SectionFamily if e not in (SectionFamily.CUSTOM,)]
        preferred_raw = st.multiselect("Famílias preferidas", fam_options, default=["HEB", "IPE"])
        preferred_families = (
            [SectionFamily(f) for f in preferred_raw] if preferred_raw else [SectionFamily.HEB]
        )

        # ── Geometria ──
        st.subheader("6. Geometria")
        span_mm = st.number_input(
            "Vão / comprimento L [mm]", min_value=100.0, value=1200.0, step=50.0
        )
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

        # ── Opções ──
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
                help="0 = dimensionar automaticamente; valor > 0 = a chapa fornecida é verificada (não redimensionada).",
            )
            if bp_thick_mm == 0.0:
                bp_thick_mm = None

        exposure_val = st.selectbox("Classe de exposição", [e.value for e in ExposureClass])
        exposure = ExposureClass(exposure_val)
        concrete_grade = st.selectbox(
            "Betão (ancoragens)", ["C20/25", "C25/30", "C30/37", "C35/45", "C40/50"], index=1
        )

        # ── Botão Calcular ──
        st.divider()
        calc_btn = st.button("▶ Calcular", type="primary", width="stretch")

    # ════════════════════════════════════════════════════════════════════════════════
    # ÁREA PRINCIPAL — resultados
    # ════════════════════════════════════════════════════════════════════════════════

    # O cálculo só corre quando o utilizador clica em Calcular, mas o resultado é
    # guardado em session_state. Assim, os reruns disparados pelos botões de
    # download (que tornam calc_btn=False) não apagam os resultados nem voltam ao
    # ecrã inicial.
    if calc_btn:
        try:
            fan_units = [
                FanUnit(
                    tag=unit["tag"],
                    fan_type=FanType(unit["fan_type"]),
                    weight_kg=unit["weight_kg"],
                    operating_weight_kg=unit["operating_weight_kg"],
                    footprint_length_mm=unit["footprint_length_mm"],
                    footprint_width_mm=unit["footprint_width_mm"],
                    centre_of_gravity_height_mm=unit["centre_of_gravity_height_mm"],
                )
                for unit in fan_unit_inputs
            ]

            inp = FanSupportInput(
                project_name=project_name,
                support_tag=support_tag,
                design_notes=design_notes,
                fan_units=fan_units,
                support_type=support_type,
                cantilever_subtype=cantilever_subtype,
                operation_mode=operation_mode,
                country=country,
                seismic_zone=seismic_zone,
                steel_grade=steel_grade,
                preferred_section_families=preferred_families,
                dynamic_factor=dyn_fac,
                installation_height_mm=h_inst_mm,
                span_mm=span_mm,
                eccentricity_mm=ecc_mm,
                hanger_rod_length_mm=hanger_rod_mm,
                anti_vibration=anti_vib,
                anti_vibration_static_deflection_mm=av_defl_mm,
                include_base_plate=include_bp,
                fan_connection_type=fan_conn_type,
                base_plate_thickness_mm=bp_thick_mm,
                received_section_tag=received_section_tag,
                received_section_family=received_section_family,
                exposure_class=exposure,
                concrete_grade=concrete_grade,
                confirm_extended_range=confirm_extended,
            )

            with st.spinner("A calcular…"):
                st.session_state["sfsc_ctx"] = run_full_calculation(inp)
                st.session_state["sfsc_tag"] = support_tag
                result = st.session_state["sfsc_ctx"].fan_support_result
                if result and result.recommended_section:
                    st.session_state["sfsc_selected_section"] = (
                        result.recommended_section.designation
                    )
            st.session_state.pop("sfsc_error", None)
        except (SFSCBaseError, PydanticValidationError) as e:
            # Erro de domínio/validação: mensagem orientada ao utilizador, sem traceback.
            st.session_state["sfsc_ctx"] = None
            st.session_state["sfsc_error"] = e
        except Exception as e:
            logger.exception("Erro interno no cálculo SFSC")
            st.session_state["sfsc_ctx"] = None
            st.session_state["sfsc_error"] = e

    if st.session_state.get("sfsc_error") is not None:
        err = st.session_state["sfsc_error"]
        if isinstance(err, SFSCBaseError):
            st.error(f"**[{err.code}]** {err.message}")
        elif isinstance(err, PydanticValidationError):
            msgs = "\n".join(
                f"- `{'.'.join(str(p) for p in e['loc'])}`: {e['msg']}" for e in err.errors()
            )
            st.error(f"**Input inválido:**\n{msgs}")
        else:
            st.error(
                "**Erro interno do SFSC.** O cálculo não foi concluído. "
                "Reveja os inputs; se o problema persistir, reporte ao suporte "
                "indicando os parâmetros usados."
            )
        if os.environ.get("SFSC_DEBUG") == "1":
            st.exception(err)

    ctx = st.session_state.get("sfsc_ctx")
    if ctx is not None:
        try:
            support_tag = st.session_state.get("sfsc_tag", support_tag)
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
                default = (
                    saved
                    if saved in options
                    else (
                        base_res.recommended_section.designation
                        if base_res.recommended_section
                        and base_res.recommended_section.designation in options
                        else options[0]
                    )
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

            def _fmt_pct(value: float | None) -> str:
                return "n/a" if value is None else f"{value:.1f}%"

            # ── Status banner ──────────────────────────────────────────────────────
            col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
            col_s1.metric("Diagnóstico", assessment.headline)
            col_s2.metric("Estado técnico", res.status.value)
            col_s3.metric("Utilização gov.", _fmt_pct(assessment.utilization_percent))
            col_s4.metric("Conservadorismo", _fmt_pct(assessment.conservatism_percent))
            col_s5.metric("Uso do limite", _fmt_pct(assessment.limit_percent))

            assessment_message = (
                f"{assessment.summary} Verificação governante: {assessment.governing_item}."
            )
            # REQUIRES_SPECIALIST nunca aparece como sucesso (auditoria C-03).
            if assessment.is_failure:
                st.error(assessment_message)
            elif assessment.is_specialist:
                st.error(
                    f"⚠️ **REQUER ESPECIALISTA** — {assessment_message} "
                    "Este resultado não pode ser usado sem revisão por engenheiro "
                    "estrutural qualificado."
                )
            elif assessment.is_borderline:
                st.warning(assessment_message)
            else:
                st.success(assessment_message)

            tabs = st.tabs(
                ["Secção", "Mesa", "Ancoragens", "Ligações", "Combinações", "Avisos", "Citações"]
            )

            # ── Tab 1: Secção ──────────────────────────────────────────────────────
            with tabs[0]:
                if base_res and base_res.section_options:
                    import pandas as pd

                    st.subheader("Perfis aprovados")
                    option_rows = []
                    for opt in base_res.section_options:
                        option_rows.append(
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
                        )
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
                            st.dataframe(
                                {
                                    "Propriedade": [
                                        "Família",
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
                                        sec_opt.family.value,
                                        f"{sec_opt.h_mm:g}",
                                        f"{sec_opt.b_mm:g}",
                                        f"{sec_opt.tw_mm:g}",
                                        f"{sec_opt.tf_mm:g}",
                                        f"{sec_opt.A_cm2:g}",
                                        f"{sec_opt.I_y_cm4:g}",
                                        f"{sec_opt.W_el_y_cm3:g}",
                                        f"{sec_opt.weight_kgm:g}",
                                    ],
                                },
                                hide_index=True,
                            )
                            st.dataframe(
                                {
                                    "Check": list(opt.utilization_by_check.keys()),
                                    "η": [round(v, 4) for v in opt.utilization_by_check.values()],
                                },
                                hide_index=True,
                            )

                if res.recommended_section:
                    sec = res.recommended_section
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader(f"Perfil: **{sec.designation}**")
                        _grade = (
                            ctx.fan_support_input.steel_grade.value
                            if ctx.fan_support_input
                            else steel_grade.value
                        )
                        st.markdown(f"Família: `{sec.family.value}` | Aço: `{_grade}`")
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
                            eta_data = {
                                "Check": list(sv.utilization_by_check.keys()),
                                "η": [round(v, 4) for v in sv.utilization_by_check.values()],
                            }
                            st.dataframe(eta_data, hide_index=True)

            # ── Tab 2: Mesa ────────────────────────────────────────────────────────
            with tabs[1]:
                if res.base_plate:
                    bp = res.base_plate
                    st.subheader(
                        f"Chapa {bp.length_mm:.0f} × {bp.width_mm:.0f} × {bp.thickness_mm:.0f} mm"
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        st.metric("Tensão de contacto", f"{bp.bearing_stress_mpa:.2f} MPa")
                        st.metric("η bearing", f"{bp.utilization_bearing:.3f}")
                        st.metric("η bending", f"{bp.utilization_bending:.3f}")
                    with c2:
                        st.metric(
                            "Parafusos ventilador → chapa",
                            f"M{bp.bolt_diameter_mm:.0f} × {bp.n_bolts_fan}",
                        )
                        st.metric("η bolt (fan)", f"{bp.bolt_utilization_fan:.3f}")
                        st.metric(
                            "Soldadura garganta",
                            f"{bp.weld_throat_mm:.1f} mm  η={bp.weld_utilization:.3f}",
                        )
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
                else:
                    st.info("Mesa não activada neste cálculo.")

            # ── Tab 3: Ancoragens / varões ─────────────────────────────────────────
            with tabs[2]:
                if res.anchor:
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
                    if not is_rod:
                        c3.metric("Profundidade hef", f"{anc.embedment_depth_mm:.0f} mm")
                    else:
                        c3.metric("η interacção", f"{anc.utilization_combined:.3f}")
                    c1.metric("N_Rd total", f"{anc.tensile_capacity_kN:.1f} kN")
                    c2.metric("V_Rd total", f"{anc.shear_capacity_kN:.1f} kN")
                    if not is_rod:
                        c3.metric("η interacção", f"{anc.utilization_combined:.3f}")
                    st.caption(f"Cláusula: {anc.code_clause}")

            # ── Tab 4: Ligações ────────────────────────────────────────────────────
            with tabs[3]:
                if res.metal_connection:
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
                                f"{mc.stiffener_thickness_mm:.1f} mm"
                                if mc.stiffener_required
                                else "Não",
                                mc.cleat_angle or "n/a",
                                mc.diagonal_member or "n/a",
                            ],
                        },
                        hide_index=True,
                    )
                    st.caption(f"Cláusula: {mc.code_clause}")

            # ── Tab 5: Combinações ─────────────────────────────────────────────────
            with tabs[4]:
                import pandas as pd

                def _combo_rows(combos):
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
                    st.dataframe(
                        pd.DataFrame(_combo_rows(res.all_combinations)),
                        hide_index=True,
                        width="stretch",
                    )
                if res.member_forces:
                    st.subheader("Esforços de cálculo no elemento")
                    st.dataframe(
                        pd.DataFrame(_combo_rows(res.member_forces)),
                        hide_index=True,
                        width="stretch",
                    )
                    st.caption(
                        "As acções totais e os esforços no elemento são níveis "
                        "diferentes — não comparar directamente entre tabelas."
                    )

            # ── Tab 6: Avisos ──────────────────────────────────────────────────────
            with tabs[5]:
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

            # ── Tab 7: Citações ────────────────────────────────────────────────────
            with tabs[6]:
                import pandas as pd

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

            # ── Exportar ───────────────────────────────────────────────────────────
            st.divider()
            st.subheader("Exportar memorial")
            col_e1, col_e2, col_e3 = st.columns(3)

            with col_e1:
                pdf_bytes = generate_pdf(ctx)
                st.download_button(
                    "📄 Download PDF",
                    data=pdf_bytes,
                    file_name=f"sfsc_{support_tag}_{datetime.date.today()}.pdf",
                    mime="application/pdf",
                    width="stretch",
                )
            with col_e2:
                xlsx_bytes = generate_excel(ctx)
                st.download_button(
                    "📊 Download Excel",
                    data=xlsx_bytes,
                    file_name=f"sfsc_{support_tag}_{datetime.date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
            with col_e3:
                csv_str = generate_csv(ctx)
                st.download_button(
                    "📋 Download CSV",
                    data=csv_str,
                    file_name=f"sfsc_{support_tag}_{datetime.date.today()}.csv",
                    mime="text/csv",
                    width="stretch",
                )

        except Exception as e:
            logger.exception("Erro ao apresentar resultados SFSC")
            st.error(
                "**Erro ao apresentar resultados.** Recalcule; se o problema "
                "persistir, reporte ao suporte."
            )
            if os.environ.get("SFSC_DEBUG") == "1":
                st.exception(e)

    elif st.session_state.get("sfsc_error") is None:
        # Estado inicial — guia de uso
        st.info(
            "Configure os parâmetros na barra lateral e clique **▶ Calcular**.\n\n"
            "**Tipos de suporte disponíveis:**\n"
            "- **Hanger**: pendurado em viga (varões roscados)\n"
            "- **Cantilever 1**: consola simples (mão-francesa — pura ou com diagonal)\n"
            "- **Cantilever 2**: consolas simétricas dos dois lados\n"
            "- **Cantilever 3**: U invertido (pórtico simples)\n"
            "- **Pedestal**: mesa com 2 patins longitudinais\n"
            "- **Combined**: mesa + pendurais anti-vibração\n\n"
            "**Países suportados:** Portugal, Espanha, Irlanda, UK, França, Brasil, Chile (+ EU genérico)\n\n"
            "**Output:** perfil metálico dimensionado (HEA/HEB/IPE/UPN/RHS) + mesa + ancoragens + "
            "memorial PDF + Excel"
        )


if __name__ == "__main__":
    main()
