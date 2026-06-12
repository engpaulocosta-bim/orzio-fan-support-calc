"""Sidebar Phase 06 - assisted BIM/IFC import review."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st
from pydantic import ValidationError as PydanticValidationError

from sfsc.engines.ifc_import import build_import_review
from sfsc.i18n import Lang, t
from sfsc.models import ImportedModelPayload

_EXAMPLE_PAYLOAD = """{
  "source": {
    "source_type": "ifc_extracted",
    "file_name": "support_frame.ifc",
    "source_application": "Revit",
    "source_model_name": "Fan support"
  },
  "elements": [
    {
      "id": "B1",
      "classification": "beam",
      "is_structural": true,
      "start": {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
      "end": {"x_m": 2.0, "y_m": 0.0, "z_m": 0.0},
      "section_name": "HEB200",
      "material_name": "S355",
      "orientation_deg": 0.0,
      "start_support_condition": "fixed"
    }
  ]
}"""


def render(lang: Lang = Lang.PT) -> dict[str, Any]:
    st.subheader(t("sidebar.import.heading", lang))
    enabled = st.checkbox(t("sidebar.import.enable", lang), value=False)
    imported_model = None
    imported_model_confirmed = False
    imported_model_confirmation_notes = ""
    imported_model_error = None

    if enabled:
        raw_payload = st.text_area(
            t("sidebar.import.payload", lang),
            value=_EXAMPLE_PAYLOAD,
            height=240,
            help=t("sidebar.import.payloadHelp", lang),
        )
        imported_model_confirmation_notes = st.text_area(
            t("sidebar.import.notes", lang),
            height=70,
        )
        if raw_payload.strip():
            try:
                payload = ImportedModelPayload.model_validate(json.loads(raw_payload))
                review = build_import_review(
                    payload,
                    confirmed=False,
                    confirmed_by=None,
                    confirmation_notes=imported_model_confirmation_notes,
                )
                imported_model = payload.model_dump(mode="python")
                imported_model_confirmed = st.checkbox(
                    t("sidebar.import.confirm", lang),
                    value=False,
                    help=t("sidebar.import.confirmHelp", lang),
                )
                col_1, col_2, col_3 = st.columns(3)
                col_1.metric(
                    t("report.column.importedElements", lang),
                    review.imported_elements_count,
                )
                col_2.metric(
                    t("report.column.acceptedMembers", lang),
                    review.accepted_members_count,
                )
                col_3.metric(
                    t("report.column.rejectedElements", lang),
                    review.rejected_elements_count,
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
                        t("report.column.warnings", lang): "; ".join(item.warnings),
                    }
                    for item in review.members
                ]
                if member_rows:
                    st.dataframe(pd.DataFrame(member_rows), hide_index=True, width="stretch")
                if review.warnings:
                    warning_rows = [
                        {
                            t("report.column.warningCode", lang): item.code,
                            t("report.column.warningSeverity", lang): item.severity,
                            t("report.column.element", lang): item.element_id or "—",
                            t("report.column.warnings", lang): item.message,
                        }
                        for item in review.warnings
                    ]
                    st.dataframe(pd.DataFrame(warning_rows), hide_index=True, width="stretch")
            except (json.JSONDecodeError, PydanticValidationError) as exc:
                imported_model_error = str(exc)
                st.error(t("sidebar.import.invalid", lang))
        else:
            st.info(t("sidebar.import.empty", lang))

    return {
        "imported_model": imported_model,
        "imported_model_confirmed": imported_model_confirmed,
        "imported_model_confirmation_notes": imported_model_confirmation_notes,
        "imported_model_error": imported_model_error,
    }
