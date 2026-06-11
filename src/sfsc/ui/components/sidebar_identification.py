"""Sidebar §1 — identificação do projecto e engenheiro responsável."""

from __future__ import annotations

from typing import Any

import streamlit as st


def render() -> dict[str, Any]:
    """Renderiza a secção de identificação e devolve os valores."""
    st.subheader("1. Identificação")
    project_name = st.text_input("Nome do projecto", value="Projecto Demo")
    support_tag = st.text_input("Tag do suporte", value="FSU-001")
    engineer = st.text_input(
        "Engenheiro responsável",
        value="",
        help="Obrigatório para exportar o memorial — consta na capa e nas assinaturas.",
    )
    design_notes = st.text_area("Notas", height=60)
    return {
        "project_name": project_name,
        "support_tag": support_tag,
        "engineer": engineer,
        "design_notes": design_notes,
    }
