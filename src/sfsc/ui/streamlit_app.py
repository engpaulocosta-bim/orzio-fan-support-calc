"""Interface Streamlit — SFSC Steel Fan Support Calc.

Orquestrador fino: a sidebar e a área de resultados vivem em
``sfsc.ui.components`` (auditoria Fase 3 — F3.4). Este módulo recolhe os
inputs dos componentes, constrói o ``FanSupportInput``, corre o cálculo e
delega a apresentação.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import streamlit as st
from pydantic import ValidationError as PydanticValidationError

from sfsc.engines.selector import context_for_section_choice, run_full_calculation
from sfsc.exceptions import SFSCBaseError, ValidationError
from sfsc.models import (
    AnchorLayoutInput,
    BasePlateInput,
    CalculationOptions,
    FanSupportInput,
    FanUnit,
    ImportedModelPayload,
    ManualLoad,
    SteelFixationInput,
    WalkingSurface,
)
from sfsc.ui.components import (
    export_bar,
    results_view,
    sidebar_context,
    sidebar_fan,
    sidebar_geometry,
    sidebar_identification,
    sidebar_import,
    sidebar_modules,
    sidebar_support,
)

logger = logging.getLogger("sfsc.ui")

_CSS = """
<style>
    .main-title {font-size:2rem; font-weight:800; color:#1447E6; margin-bottom:0}
    .sub-title  {font-size:1rem; color:#64748B; margin-top:0}
    div[data-testid="stMetricValue"] {font-size:1.3rem}
</style>
"""

_INTRO = (
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


def _collect_inputs() -> FanSupportInput:
    """Recolhe os componentes da sidebar e constrói o FanSupportInput."""
    ident = sidebar_identification.render()
    fan_units_raw, confirm_extended = sidebar_fan.render()
    support = sidebar_support.render()
    context = sidebar_context.render()
    imported = sidebar_import.render()
    geom = sidebar_geometry.render(support["support_type"])
    modules = sidebar_modules.render(
        support["support_type"],
        geom["platform_n_beams"],
        geom["platform_n_crossbeams"],
    )

    if imported["imported_model_error"]:
        raise ValidationError(imported["imported_model_error"], "imported_model")

    fan_units = [
        FanUnit(
            tag=u["tag"],
            fan_type=u["fan_type"],
            weight_kg=u["weight_kg"],
            operating_weight_kg=u["operating_weight_kg"],
            footprint_length_mm=u["footprint_length_mm"],
            footprint_width_mm=u["footprint_width_mm"],
            centre_of_gravity_height_mm=u["centre_of_gravity_height_mm"],
        )
        for u in fan_units_raw
    ]

    return FanSupportInput(
        project_name=ident["project_name"],
        support_tag=ident["support_tag"],
        design_notes=ident["design_notes"],
        prepared_by=ident["engineer"] or "SFSC",
        fan_units=fan_units,
        support_type=support["support_type"],
        cantilever_subtype=support["cantilever_subtype"],
        operation_mode=support["operation_mode"],
        received_section_family=support["received_section_family"],
        received_section_tag=support["received_section_tag"],
        country=context["country"],
        seismic_zone=context["seismic_zone"],
        steel_grade=context["steel_grade"],
        preferred_section_families=context["preferred_families"],
        dynamic_factor=geom["dyn_fac"],
        installation_height_mm=geom["h_inst_mm"],
        span_mm=geom["span_mm"],
        eccentricity_mm=geom["ecc_mm"],
        hanger_rod_length_mm=geom["hanger_rod_mm"],
        platform_n_beams=geom["platform_n_beams"],
        platform_n_crossbeams=geom["platform_n_crossbeams"],
        platform_width_mm=geom["platform_width_mm"],
        platform_length_mm=geom["platform_length_mm"],
        anti_vibration=geom["anti_vib"],
        anti_vibration_static_deflection_mm=geom["av_defl_mm"],
        include_base_plate=geom["include_bp"],
        fan_connection_type=geom["fan_conn_type"],
        base_plate_thickness_mm=geom["bp_thick_mm"],
        exposure_class=geom["exposure"],
        concrete_grade=geom["concrete_grade"],
        confirm_extended_range=confirm_extended,
        calculation_mode=modules["calculation_mode"],
        calculation_options=CalculationOptions(**modules["calculation_options"]),
        walking_surface=WalkingSurface(**modules["walking_surface"]),
        manual_loads=[ManualLoad(**item) for item in modules["manual_loads"]],
        support_fixation_medium=modules["support_fixation_medium"],
        steel_fixation=(
            SteelFixationInput(**modules["steel_fixation"]) if modules["steel_fixation"] else None
        ),
        base_plate_input=(
            BasePlateInput(**geom["base_plate_input"]) if geom["base_plate_input"] else None
        ),
        anchor_layout=(
            AnchorLayoutInput(**modules["anchor_layout"]) if modules["anchor_layout"] else None
        ),
        imported_model=(
            ImportedModelPayload(**imported["imported_model"])
            if imported["imported_model"]
            else None
        ),
        imported_model_confirmed=imported["imported_model_confirmed"],
        imported_model_confirmation_notes=imported["imported_model_confirmation_notes"],
    )


def _show_error(err: Exception) -> None:
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


def main() -> None:
    """Render the SFSC Streamlit UI. Called on every Streamlit rerun."""
    st.set_page_config(
        page_title="SFSC — Steel Fan Support Calc",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<p class="main-title">SFSC — Steel Fan Support Calc</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-title">Dimensionamento de suportes metálicos para ventiladores '
        "industriais (35–600 kg)</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    with st.sidebar:
        st.header("Configuração")
        inp_or_error = _safe_collect()
        calc_btn = st.button("▶ Calcular", type="primary", width="stretch")

    if calc_btn:
        if isinstance(inp_or_error, Exception):
            st.session_state["sfsc_ctx"] = None
            st.session_state["sfsc_error"] = inp_or_error
        else:
            try:
                with st.spinner("A calcular…"):
                    new_ctx = run_full_calculation(inp_or_error)
                st.session_state["sfsc_ctx"] = new_ctx
                st.session_state["sfsc_tag"] = inp_or_error.support_tag
                res = new_ctx.fan_support_result
                if res and res.recommended_section:
                    st.session_state["sfsc_selected_section"] = res.recommended_section.designation
                st.session_state.pop("sfsc_error", None)
            except (SFSCBaseError, PydanticValidationError) as e:
                st.session_state["sfsc_ctx"] = None
                st.session_state["sfsc_error"] = e
            except Exception as e:  # noqa: BLE001 — bug interno → mensagem genérica
                logger.exception("Erro interno no cálculo SFSC")
                st.session_state["sfsc_ctx"] = None
                st.session_state["sfsc_error"] = e

    if st.session_state.get("sfsc_error") is not None:
        _show_error(st.session_state["sfsc_error"])

    stored_ctx = st.session_state.get("sfsc_ctx")
    if stored_ctx is not None:
        _render_results(stored_ctx)
    elif st.session_state.get("sfsc_error") is None:
        st.info(_INTRO)


def _safe_collect():
    """Recolhe inputs; devolve o FanSupportInput ou a excepção de validação."""
    try:
        return _collect_inputs()
    except (SFSCBaseError, PydanticValidationError) as e:
        return e


def _render_results(base_ctx) -> None:
    try:
        support_tag = st.session_state.get("sfsc_tag", "FSU")
        active_ctx = base_ctx
        base_res = base_ctx.fan_support_result

        # Selector de perfil aprovado — recalcula o contexto activo.
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
            active_ctx = context_for_section_choice(base_ctx, selected_section)

        results_view.render(active_ctx, base_ctx)
        export_bar.render(active_ctx, support_tag)
    except Exception as e:  # noqa: BLE001
        logger.exception("Erro ao apresentar resultados SFSC")
        st.error(
            "**Erro ao apresentar resultados.** Recalcule; se o problema "
            "persistir, reporte ao suporte."
        )
        if os.environ.get("SFSC_DEBUG") == "1":
            st.exception(e)


if __name__ == "__main__":
    main()
