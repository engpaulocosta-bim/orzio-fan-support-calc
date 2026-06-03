"""Interface Streamlit — SFSC Steel Fan Support Calc."""
from __future__ import annotations
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import streamlit as st
from sfsc.enums import (
    SupportType, CantileverSubtype, Country, SteelGrade, SectionFamily,
    ExposureClass, AntiVibrationType, OperationMode, FanConnectionType, FanType,
)
from sfsc.models import FanSupportInput, FanUnit
from sfsc.catalogs.seismic_catalog import list_zones
from sfsc.engines.selector import run_full_calculation
from sfsc.reports.memorial_pdf import generate_pdf
from sfsc.reports.exports import generate_excel, generate_csv

# ── Tema ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SFSC — Steel Fan Support Calc",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
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
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">SFSC — Steel Fan Support Calc</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Dimensionamento de suportes metálicos para ventiladores industriais (35–600 kg)</p>', unsafe_allow_html=True)
st.divider()

# ════════════════════════════════════════════════════════════════════════════════
# SIDEBAR — entradas
# ════════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("Configuração")

    # ── Identificação ──
    st.subheader("1. Identificação")
    project_name = st.text_input("Nome do projecto", value="Projecto Demo")
    support_tag  = st.text_input("Tag do suporte", value="FSU-001")
    design_notes = st.text_area("Notas", height=60)

    # ── Ventilador ──
    st.subheader("2. Ventilador")
    n_units = st.number_input("Número de unidades", min_value=1, max_value=10, value=1)

    fan_units = []
    for i in range(n_units):
        with st.expander(f"Unidade {i+1}", expanded=(i==0)):
            fan_type   = st.selectbox(f"Tipo [{i+1}]", [e.value for e in FanType], key=f"ft{i}")
            weight_kg  = st.number_input(f"Peso vazio [kg] [{i+1}]", min_value=1.0, value=120.0, step=5.0, key=f"wv{i}")
            op_weight  = st.number_input(f"Peso operação [kg] [{i+1}]", min_value=1.0, value=130.0, step=5.0, key=f"wo{i}")
            fl_len     = st.number_input(f"Comprimento base [mm] [{i+1}]", min_value=100.0, value=800.0, step=50.0, key=f"fl{i}")
            fl_wid     = st.number_input(f"Largura base [mm] [{i+1}]", min_value=100.0, value=600.0, step=50.0, key=f"fw{i}")
            cg_h       = st.number_input(f"Altura CG [mm] [{i+1}]", min_value=0.0, value=300.0, step=10.0, key=f"cg{i}")
            fan_units.append(FanUnit(
                tag=f"V{i+1}",
                fan_type=FanType(fan_type),
                weight_kg=weight_kg,
                operating_weight_kg=op_weight,
                footprint_length_mm=fl_len,
                footprint_width_mm=fl_wid,
                centre_of_gravity_height_mm=cg_h,
            ))

    # ── Tipo de suporte ──
    st.subheader("3. Tipo de Suporte")
    support_type_val = st.selectbox("Tipo", [e.value for e in SupportType],
                                    format_func=lambda x: x.replace("_", " ").title())
    support_type = SupportType(support_type_val)

    cantilever_subtype = None
    if support_type == SupportType.CANTILEVER_1:
        csub = st.radio("Subtipo consola", ["pure", "bracketed"], horizontal=True)
        cantilever_subtype = CantileverSubtype(csub)

    operation_mode_val = st.radio("Modo", ["dimension", "verify"], horizontal=True,
                                   format_func=lambda x: "Dimensionar" if x=="dimension" else "Verificar")
    operation_mode = OperationMode(operation_mode_val)

    received_section_tag    = None
    received_section_family = None
    if operation_mode == OperationMode.VERIFY:
        fam_val = st.selectbox("Família do perfil", [e.value for e in SectionFamily if e != SectionFamily.CUSTOM])
        received_section_family = SectionFamily(fam_val)
        received_section_tag = st.text_input("Designação (ex: HEB200)", value="HEB200")

    # ── País e Sismo ──
    st.subheader("4. País / Norma / Sismo")
    country_val = st.selectbox("País", [e.value for e in Country],
                                format_func=lambda x: {
                                    "PT":"Portugal","ES":"Espanha","IE":"Irlanda",
                                    "EU":"Europa (genérico)","UK":"Reino Unido",
                                    "FR":"França","BR":"Brasil","CL":"Chile",
                                }.get(x, x))
    country = Country(country_val)

    zones_dict = list_zones(country)
    zone_options = list(zones_dict.keys())
    zone_descs   = [f"{k} — {v.get('description','')}" for k, v in zones_dict.items()]
    seismic_zone_idx = 0
    if zone_options:
        seismic_zone_sel = st.selectbox("Zona sísmica (None = default conservativo)",
                                        ["Automático (default)"] + zone_descs)
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
    preferred_families = [SectionFamily(f) for f in preferred_raw] if preferred_raw else [SectionFamily.HEB]

    # ── Geometria ──
    st.subheader("6. Geometria")
    span_mm   = st.number_input("Vão / comprimento L [mm]", min_value=100.0, value=1200.0, step=50.0)
    h_inst_mm = st.number_input("Altura de instalação h [mm]", min_value=50.0, value=500.0, step=50.0)
    ecc_mm    = st.number_input("Excentricidade CG [mm]", min_value=0.0, value=0.0, step=10.0)
    dyn_fac   = st.number_input("Factor dinâmico", min_value=1.0, max_value=3.0, value=1.5, step=0.1,
                                 help="Default 1.5 (VDI 3840). Editável.")

    hanger_rod_mm = None
    if support_type == SupportType.HANGER:
        hanger_rod_mm = st.number_input("Comprimento dos varões [mm]", min_value=100.0, value=h_inst_mm, step=50.0)

    # ── Opções ──
    st.subheader("7. Opções")
    anti_vib_val = st.selectbox("Anti-vibração", [e.value for e in AntiVibrationType])
    anti_vib = AntiVibrationType(anti_vib_val)
    av_defl_mm = None
    if anti_vib == AntiVibrationType.SPRINGS:
        av_defl_mm = st.number_input("Deflexão estática molas [mm]", min_value=1.0, value=25.0)

    include_bp = st.checkbox("Incluir mesa / base plate", value=False)
    fan_conn_type = None
    bp_thick_mm   = None
    if include_bp:
        conn_val = st.selectbox("Tipo de fixação ventilador", [e.value for e in FanConnectionType])
        fan_conn_type = FanConnectionType(conn_val)
        bp_thick_mm = st.number_input("Espessura chapa [mm] (0 = auto)", min_value=0.0, value=0.0, step=5.0)
        if bp_thick_mm == 0.0:
            bp_thick_mm = None

    exposure_val = st.selectbox("Classe de exposição", [e.value for e in ExposureClass])
    exposure = ExposureClass(exposure_val)
    concrete_grade = st.selectbox("Betão (ancoragens)", ["C20/25","C25/30","C30/37","C35/45","C40/50"], index=1)

    # ── Botão Calcular ──
    st.divider()
    calc_btn = st.button("▶ Calcular", type="primary", use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════════
# ÁREA PRINCIPAL — resultados
# ════════════════════════════════════════════════════════════════════════════════

if calc_btn:
    try:
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
        )

        with st.spinner("A calcular…"):
            ctx = run_full_calculation(inp)

        res = ctx.fan_support_result
        assert res is not None

        # ── Status banner ──────────────────────────────────────────────────────
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Estado", res.status.value)
        col_s2.metric("Classificação", res.classification_level.value)
        col_s3.metric("Carga de projecto", f"{res.design_load_kN:.2f} kN")
        col_s4.metric("Factor sísmico ag/g", f"{res.seismic_factor_g:.3f}")

        tabs = st.tabs(["Secção", "Mesa", "Ancoragens", "Combinações", "Avisos", "Citações"])

        # ── Tab 1: Secção ──────────────────────────────────────────────────────
        with tabs[0]:
            if res.recommended_section:
                sec = res.recommended_section
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader(f"Perfil: **{sec.designation}**")
                    st.markdown(f"Família: `{sec.family.value}` | Aço: `{inp.steel_grade.value}`")
                    st.dataframe({
                        "Propriedade": ["h [mm]","b [mm]","tw [mm]","tf [mm]","A [cm²]","I_y [cm⁴]","W_el,y [cm³]","Peso [kg/m]"],
                        "Valor": [sec.h_mm, sec.b_mm, sec.tw_mm, sec.tf_mm, sec.A_cm2, sec.I_y_cm4, sec.W_el_y_cm3, sec.weight_kgm],
                    }, hide_index=True)
                with c2:
                    if res.section_verification:
                        sv = res.section_verification
                        st.subheader(f"Utilização máxima: η = {sv.utilization_ratio:.3f}")
                        st.caption(f"Governa: `{sv.governing_check}` | {sv.code_clause}")
                        eta_data = {"Check": list(sv.utilization_by_check.keys()),
                                    "η": [round(v,4) for v in sv.utilization_by_check.values()]}
                        st.dataframe(eta_data, hide_index=True)

        # ── Tab 2: Mesa ────────────────────────────────────────────────────────
        with tabs[1]:
            if res.base_plate:
                bp = res.base_plate
                st.subheader(f"Chapa {bp.length_mm:.0f} × {bp.width_mm:.0f} × {bp.thickness_mm:.0f} mm")
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Tensão de contacto", f"{bp.bearing_stress_mpa:.2f} MPa")
                    st.metric("η bearing", f"{bp.utilization_bearing:.3f}")
                    st.metric("η bending", f"{bp.utilization_bending:.3f}")
                with c2:
                    st.metric(f"Parafusos ventilador → chapa", f"M{bp.bolt_diameter_mm:.0f} × {bp.n_bolts_fan}")
                    st.metric("η bolt (fan)", f"{bp.bolt_utilization_fan:.3f}")
                    st.metric("Soldadura garganta", f"{bp.weld_throat_mm:.1f} mm  η={bp.weld_utilization:.3f}")
            else:
                st.info("Mesa não activada neste cálculo.")

        # ── Tab 3: Ancoragens ──────────────────────────────────────────────────
        with tabs[2]:
            if res.anchor:
                anc = res.anchor
                c1, c2, c3 = st.columns(3)
                c1.metric("Nº ancoragens", str(anc.n_anchors))
                c2.metric("Diâmetro", f"Ø{anc.anchor_diameter_mm:.0f} mm")
                c3.metric("Profundidade hef", f"{anc.embedment_depth_mm:.0f} mm")
                c1.metric("N_Rd total", f"{anc.tensile_capacity_kN:.1f} kN")
                c2.metric("V_Rd total", f"{anc.shear_capacity_kN:.1f} kN")
                c3.metric("η interacção", f"{anc.utilization_combined:.3f}")
                st.caption(f"Cláusula: {anc.code_clause}")

        # ── Tab 4: Combinações ─────────────────────────────────────────────────
        with tabs[3]:
            if res.all_combinations:
                import pandas as pd
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
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        # ── Tab 5: Avisos ──────────────────────────────────────────────────────
        with tabs[4]:
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

        # ── Tab 6: Citações ────────────────────────────────────────────────────
        with tabs[5]:
            import pandas as pd
            cit_rows = [{"Norma": c.standard_id, "Edição": c.edition,
                          "Cláusula": c.clause, "Descrição": c.description}
                         for c in ctx.citations]
            if cit_rows:
                st.dataframe(pd.DataFrame(cit_rows), hide_index=True, use_container_width=True)

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
                use_container_width=True,
            )
        with col_e2:
            xlsx_bytes = generate_excel(ctx)
            st.download_button(
                "📊 Download Excel",
                data=xlsx_bytes,
                file_name=f"sfsc_{support_tag}_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_e3:
            csv_str = generate_csv(ctx)
            st.download_button(
                "📋 Download CSV",
                data=csv_str,
                file_name=f"sfsc_{support_tag}_{datetime.date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    except Exception as e:
        st.error(f"**Erro:** {e}")
        st.exception(e)

else:
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
