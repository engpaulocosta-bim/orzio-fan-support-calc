"""Barra de exportação — PDF/Excel/CSV com gate de engenheiro responsável.

Auditoria F3.5: o memorial só pode ser exportado depois de identificado o
engenheiro responsável (consta na capa e no bloco de assinaturas do PDF).
"""

from __future__ import annotations

import datetime

import streamlit as st

from sfsc.models import ReportContext
from sfsc.reports.exports import generate_csv, generate_excel
from sfsc.reports.memorial_pdf import generate_pdf


def render(ctx: ReportContext, support_tag: str) -> None:
    """Renderiza os três botões de download, bloqueados sem engenheiro responsável."""
    st.divider()
    st.subheader("Exportar memorial")

    prepared_by = (ctx.prepared_by or "").strip()
    if not prepared_by or prepared_by.upper().startswith("SFSC"):
        st.warning(
            "Indique o **Engenheiro responsável** na barra lateral (secção 1) "
            "antes de exportar — o nome consta na capa e nas assinaturas do memorial."
        )
        return

    today = datetime.date.today()
    col_pdf, col_xlsx, col_csv = st.columns(3)
    with col_pdf:
        st.download_button(
            "📄 Download PDF",
            data=generate_pdf(ctx),
            file_name=f"sfsc_{support_tag}_{today}.pdf",
            mime="application/pdf",
            width="stretch",
        )
    with col_xlsx:
        st.download_button(
            "📊 Download Excel",
            data=generate_excel(ctx),
            file_name=f"sfsc_{support_tag}_{today}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with col_csv:
        st.download_button(
            "📋 Download CSV",
            data=generate_csv(ctx),
            file_name=f"sfsc_{support_tag}_{today}.csv",
            mime="text/csv",
            width="stretch",
        )
