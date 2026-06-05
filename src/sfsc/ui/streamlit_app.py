"""Interface Streamlit — SFSC Steel Fan Support Calc.

Slim orchestrator: the input form lives in :mod:`sfsc.ui.inputs` and the
results area in :mod:`sfsc.ui.results`. ``main`` wires them together and owns
the session_state lifecycle so download reruns (``calc_btn=False``) don't wipe
the computed results.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import streamlit as st

from sfsc.engines.selector import run_full_calculation
from sfsc.exceptions import SFSCBaseError
from sfsc.ui.inputs import render_sidebar
from sfsc.ui.results import render_results

_THEME_CSS = """
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


def main() -> None:
    """Render the SFSC Streamlit UI. Called on every Streamlit rerun."""
    st.set_page_config(
        page_title="SFSC — Steel Fan Support Calc",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_THEME_CSS, unsafe_allow_html=True)
    st.markdown('<p class="main-title">SFSC — Steel Fan Support Calc</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Dimensionamento de suportes metálicos para ventiladores industriais (35–600 kg)</p>', unsafe_allow_html=True)
    st.divider()

    calc_clicked, build_input = render_sidebar()

    # O cálculo só corre quando o utilizador clica em Calcular, mas o resultado é
    # guardado em session_state. Assim, os reruns disparados pelos botões de
    # download (que tornam calc_clicked=False) não apagam os resultados nem voltam
    # ao ecrã inicial.
    if calc_clicked:
        try:
            inp = build_input()
            with st.spinner("A calcular…"):
                ctx = run_full_calculation(inp)
                st.session_state["sfsc_ctx"] = ctx
                st.session_state["sfsc_tag"] = inp.support_tag
                st.session_state["sfsc_steel_grade"] = inp.steel_grade
                result = ctx.fan_support_result
                if result and result.recommended_section:
                    st.session_state["sfsc_selected_section"] = result.recommended_section.designation
            st.session_state.pop("sfsc_error", None)
        except Exception as e:
            st.session_state["sfsc_ctx"] = None
            st.session_state["sfsc_error"] = e

    if st.session_state.get("sfsc_error") is not None:
        err = st.session_state["sfsc_error"]
        if isinstance(err, SFSCBaseError):
            st.warning(f"**Cálculo não executado:** {err.message}")
            st.caption(f"Código: {err.code}")
        else:
            st.error(f"**Erro inesperado:** {err}")
            st.exception(err)

    ctx = st.session_state.get("sfsc_ctx")
    if ctx is not None:
        try:
            render_results(
                ctx,
                fallback_support_tag=st.session_state.get("sfsc_tag", ""),
                fallback_steel_grade=st.session_state.get("sfsc_steel_grade"),
            )
        except Exception as e:
            st.error(f"**Erro ao apresentar resultados:** {e}")
            st.exception(e)

    elif st.session_state.get("sfsc_error") is None:
        st.info(_INTRO)


if __name__ == "__main__":
    main()
