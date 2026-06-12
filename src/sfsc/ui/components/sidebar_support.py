"""Sidebar §3 — tipo de suporte e modo de cálculo (dimensionar/verificar)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from sfsc.catalogs.steel_section_catalog import get_available_families, list_sections
from sfsc.enums import CantileverSubtype, OperationMode, SupportType


def render() -> dict[str, Any]:
    """Renderiza tipo de suporte + modo; devolve os valores (incl. VERIFY)."""
    st.subheader("3. Tipo de Suporte")
    support_type_val = st.selectbox(
        "Tipo",
        [e.value for e in SupportType],
        format_func=lambda x: x.replace("_", " ").title(),
    )
    support_type = SupportType(support_type_val)

    cantilever_subtype = None
    if support_type in (SupportType.CANTILEVER_1, SupportType.PLATFORM_FRAME_BRACED):
        label = (
            "Subtipo consola" if support_type == SupportType.CANTILEVER_1 else "Subtipo plataforma"
        )
        csub = st.radio(label, ["pure", "bracketed"], horizontal=True)
        cantilever_subtype = CantileverSubtype(csub)

    # ── Modo de cálculo (auditoria M-03: VERIFY exposto na UI) ────────────────
    mode_label = st.radio(
        "Modo de cálculo",
        ["Dimensionar", "Verificar perfil existente"],
        horizontal=True,
        help=(
            "Dimensionar: o SFSC escolhe o perfil mais leve que verifica. "
            "Verificar: o utilizador indica um perfil recebido e o SFSC verifica-o."
        ),
    )
    operation_mode = OperationMode.DIMENSION
    received_section_family = None
    received_section_tag = None
    if mode_label == "Verificar perfil existente":
        operation_mode = OperationMode.VERIFY
        families = get_available_families()
        fam_val = st.selectbox("Família do perfil a verificar", [f.value for f in families])
        received_section_family = next(f for f in families if f.value == fam_val)
        designations = [s.designation for s in list_sections(received_section_family)]
        received_section_tag = st.selectbox("Perfil a verificar", designations)

    return {
        "support_type": support_type,
        "cantilever_subtype": cantilever_subtype,
        "operation_mode": operation_mode,
        "received_section_family": received_section_family,
        "received_section_tag": received_section_tag,
    }
