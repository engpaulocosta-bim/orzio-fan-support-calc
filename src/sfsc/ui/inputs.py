"""Sidebar input form for the SFSC Streamlit UI.

``render_sidebar`` draws every input widget and returns whether the user
clicked *Calcular* plus a zero-argument builder that constructs the
``FanSupportInput``. Construction is deferred into the callable so the caller
keeps the single try/except around model validation (out-of-scope inputs must
surface as a controlled message, not a traceback).
"""
from __future__ import annotations

from typing import Callable

import streamlit as st

from sfsc.catalogs.seismic_catalog import list_zones
from sfsc.enums import (
    AnchorageSubstrate, AntiVibrationType, CantileverSubtype, Country,
    ExposureClass, FanConnectionType, FanType, OperationMode, SectionFamily,
    SteelGrade, SupportType,
)
from sfsc.models import FanSupportInput, FanUnit

_COUNTRY_LABELS = {
    "PT": "Portugal", "ES": "Espanha", "IE": "Irlanda",
    "EU": "Europa (genérico)", "UK": "Reino Unido",
    "FR": "França", "BR": "Brasil", "CL": "Chile",
}
_SUBSTRATE_LABELS = {
    "concrete": "Betão",
    "steel_structure": "Estrutura metálica",
}
# Friendly menu labels mapped to the internal SupportType. Only the two real
# concepts are offered: suspended (hanger) and fixed to an existing beam
# (cantilever, one or two sides). The other engines stay in the code base.
_SUPPORT_CHOICES = {
    "Pendurado (tirantes)": SupportType.HANGER,
    "Engastado (1 lado)": SupportType.CANTILEVER_1,
    "Engastado (2 lados)": SupportType.CANTILEVER_2,
    "Plataforma / Mesa (grelha)": SupportType.PLATFORM,
}


def render_sidebar() -> tuple[bool, Callable[[], FanSupportInput]]:
    """Draw the sidebar and return ``(calc_clicked, build_input)``."""
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

        fan_unit_inputs = []
        for i in range(int(n_units)):
            with st.expander(f"Unidade {i+1}", expanded=(i == 0)):
                fan_type = st.selectbox(f"Tipo [{i+1}]", [e.value for e in FanType], key=f"ft{i}")
                weight_kg = st.number_input(f"Peso vazio [kg] [{i+1}]", min_value=1.0, value=120.0, step=5.0, key=f"wv{i}")
                op_weight = st.number_input(f"Peso operação [kg] [{i+1}]", min_value=1.0, value=130.0, step=5.0, key=f"wo{i}")
                fl_len = st.number_input(f"Comprimento base [mm] [{i+1}]", min_value=100.0, value=800.0, step=50.0, key=f"fl{i}")
                fl_wid = st.number_input(f"Largura base [mm] [{i+1}]", min_value=100.0, value=600.0, step=50.0, key=f"fw{i}")
                cg_h = st.number_input(f"Altura CG [mm] [{i+1}]", min_value=0.0, value=300.0, step=10.0, key=f"cg{i}")
                fan_unit_inputs.append({
                    "tag": f"V{i+1}",
                    "fan_type": fan_type,
                    "weight_kg": weight_kg,
                    "operating_weight_kg": op_weight,
                    "footprint_length_mm": fl_len,
                    "footprint_width_mm": fl_wid,
                    "centre_of_gravity_height_mm": cg_h,
                })

        # ── Tipo de suporte ──
        # Apenas os dois conceitos reais: pendurado (tirantes) e engastado em
        # viga preexistente (1 ou 2 lados). Mapeiam para os SupportType internos
        # sem alterar os motores de cálculo.
        st.subheader("3. Tipo de Suporte")
        support_choice = st.selectbox(
            "Tipo",
            list(_SUPPORT_CHOICES.keys()),
        )
        support_type = _SUPPORT_CHOICES[support_choice]

        cantilever_subtype = None
        if support_type in (SupportType.CANTILEVER_1, SupportType.CANTILEVER_2,
                            SupportType.PLATFORM):
            csub = st.radio(
                "Mão-francesa (contraventamento)",
                ["bracketed", "pure"],
                format_func=lambda x: "Com mão-francesa" if x == "bracketed" else "Sem mão-francesa",
                horizontal=True,
                help="A plataforma é calculada com e sem mão-francesa. Com mão-francesa, "
                     "as diagonais a 45° escoram a ponta e são verificadas à parte.",
            )
            cantilever_subtype = CantileverSubtype(csub)

        # Parâmetros da grelha da plataforma.
        platform_n_beams = 2
        platform_width_mm = None
        platform_length_mm = None
        platform_grating_kg_m2 = 30.0
        if support_type == SupportType.PLATFORM:
            st.caption("Grelha da mesa (mín. 2 vigas — as duas bordas)")
            platform_n_beams = int(st.number_input(
                "Nº de vigas paralelas", min_value=2, max_value=12, value=2, step=1,
                help="A carga vertical reparte-se igualmente por estas vigas.",
            ))
            col_pw, col_pl = st.columns(2)
            with col_pw:
                _pw = st.number_input(
                    "Largura plataforma [mm] (0 = auto)", min_value=0.0, value=0.0, step=50.0,
                    help="0 = derivar do footprint dos ventiladores.",
                )
                platform_width_mm = _pw or None
            with col_pl:
                _pl = st.number_input(
                    "Comprimento plataforma [mm] (0 = vão)", min_value=0.0, value=0.0, step=50.0,
                    help="0 = usar o vão L.",
                )
                platform_length_mm = _pl or None
            platform_grating_kg_m2 = st.number_input(
                "Peso do tramex/grating [kg/m²]", min_value=0.0, value=30.0, step=1.0,
                help="Tramex/chapa estriada 3 mm ≈ 30 kg/m². Entra como peso próprio.",
            )

        operation_mode = OperationMode.DIMENSION
        received_section_tag = None
        received_section_family = None

        # ── País e Sismo ──
        st.subheader("4. País / Norma / Sismo")
        country_val = st.selectbox("País", [e.value for e in Country],
                                   format_func=lambda x: _COUNTRY_LABELS.get(x, x))
        country = Country(country_val)

        zones_dict = list_zones(country)
        zone_options = list(zones_dict.keys())
        zone_descs = [f"{k} — {v.get('description','')}" for k, v in zones_dict.items()]
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
        preferred_raw = st.multiselect(
            "Famílias preferidas",
            fam_options,
            default=["RHS", "IPE", "UPN", "HEA", "HEB"],
        )
        preferred_families = [SectionFamily(f) for f in preferred_raw] if preferred_raw else [SectionFamily.RHS]

        # ── Geometria ──
        st.subheader("6. Geometria")
        span_mm = st.number_input("Vão / comprimento L [mm]", min_value=100.0, value=1200.0, step=50.0)
        h_inst_mm = st.number_input("Altura de instalação h [mm]", min_value=50.0, value=500.0, step=50.0)
        ecc_mm = st.number_input("Excentricidade CG [mm]", min_value=0.0, value=0.0, step=10.0)
        dyn_fac = st.number_input("Factor dinâmico", min_value=1.0, max_value=3.0, value=1.5, step=0.1,
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
        bp_thick_mm = None
        if include_bp:
            conn_val = st.selectbox("Tipo de fixação ventilador", [e.value for e in FanConnectionType])
            fan_conn_type = FanConnectionType(conn_val)
            bp_thick_mm = st.number_input("Espessura chapa [mm] (0 = auto)", min_value=0.0, value=0.0, step=5.0)
            if bp_thick_mm == 0.0:
                bp_thick_mm = None

        exposure_val = st.selectbox("Classe de exposição", [e.value for e in ExposureClass])
        exposure = ExposureClass(exposure_val)
        anchorage_substrate_val = st.selectbox(
            "Material de fixação",
            [e.value for e in AnchorageSubstrate],
            format_func=lambda x: _SUBSTRATE_LABELS.get(x, x),
        )
        anchorage_substrate = AnchorageSubstrate(anchorage_substrate_val)
        if anchorage_substrate == AnchorageSubstrate.CONCRETE:
            concrete_grade = st.selectbox("Betão (ancoragens)", ["C20/25", "C25/30", "C30/37", "C35/45", "C40/50"], index=1)
            receiver_steel_grade = SteelGrade.S235
            receiver_plate_thickness_mm = 10.0
            receiver_edge_distance_mm = 50.0
            receiver_spacing_mm = 80.0
            receiver_bolt_grade = "8.8"
        else:
            concrete_grade = "C25/30"
            st.caption("Dados do elemento metálico receptor")
            receiver_steel_grade = SteelGrade(st.selectbox(
                "Aço do receptor",
                [e.value for e in SteelGrade],
                index=[e.value for e in SteelGrade].index("S235"),
            ))
            receiver_plate_thickness_mm = st.number_input(
                "Espessura receptor [mm]", min_value=3.0, value=10.0, step=1.0,
            )
            receiver_edge_distance_mm = st.number_input(
                "Bordo livre receptor [mm]", min_value=10.0, value=50.0, step=5.0,
            )
            receiver_spacing_mm = st.number_input(
                "Espaçamento receptor [mm]", min_value=20.0, value=80.0, step=5.0,
            )
            receiver_bolt_grade = st.selectbox("Classe parafusos receptor", ["8.8", "10.9", "5.8", "A4-70"], index=0)
            st.info("Ligação a estrutura metálica: o cálculo usa parafusos aço-aço e não aplica verificações de cone/pull-out de betão.")

        # ── Botão Calcular ──
        st.divider()
        calc_btn = st.button("▶ Calcular", type="primary", width="stretch")

    def build_input() -> FanSupportInput:
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
        return FanSupportInput(
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
            platform_n_beams=platform_n_beams,
            platform_width_mm=platform_width_mm,
            platform_length_mm=platform_length_mm,
            platform_grating_kg_m2=platform_grating_kg_m2,
            anti_vibration=anti_vib,
            anti_vibration_static_deflection_mm=av_defl_mm,
            include_base_plate=include_bp,
            fan_connection_type=fan_conn_type,
            base_plate_thickness_mm=bp_thick_mm,
            received_section_tag=received_section_tag,
            received_section_family=received_section_family,
            exposure_class=exposure,
            anchorage_substrate=anchorage_substrate,
            receiver_steel_grade=receiver_steel_grade,
            receiver_plate_thickness_mm=receiver_plate_thickness_mm,
            receiver_edge_distance_mm=receiver_edge_distance_mm,
            receiver_spacing_mm=receiver_spacing_mm,
            receiver_bolt_grade=receiver_bolt_grade,
            concrete_grade=concrete_grade,
        )

    return bool(calc_btn), build_input
