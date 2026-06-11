"""Sidebar §4–5 — país/norma/sismo e material/perfis."""

from __future__ import annotations

from typing import Any

import streamlit as st

from sfsc.catalogs.seismic_catalog import list_zones
from sfsc.enums import Country, SectionFamily, SteelGrade

_COUNTRY_NAMES = {
    "PT": "Portugal",
    "ES": "Espanha",
    "IE": "Irlanda",
    "EU": "Europa (genérico)",
    "UK": "Reino Unido",
    "FR": "França",
    "BR": "Brasil",
    "CL": "Chile",
}


def render() -> dict[str, Any]:
    """Renderiza país/sismo/material; devolve os valores."""
    st.subheader("4. País / Norma / Sismo")
    country_val = st.selectbox(
        "País",
        [e.value for e in Country],
        format_func=lambda x: _COUNTRY_NAMES.get(x, x),
    )
    country = Country(country_val)

    zones_dict = list_zones(country)
    zone_options = list(zones_dict.keys())
    zone_descs = [f"{k} — {v.get('description', '')}" for k, v in zones_dict.items()]
    seismic_zone = None
    if zone_options:
        seismic_zone_sel = st.selectbox(
            "Zona sísmica (None = default conservativo)", ["Automático (default)"] + zone_descs
        )
        if seismic_zone_sel != "Automático (default)":
            seismic_zone = zone_options[zone_descs.index(seismic_zone_sel)]

    st.subheader("5. Material e Perfis")
    steel_grade_val = st.selectbox("Grau do aço", [e.value for e in SteelGrade])
    steel_grade = SteelGrade(steel_grade_val)

    fam_options = [e.value for e in SectionFamily if e not in (SectionFamily.CUSTOM,)]
    preferred_raw = st.multiselect("Famílias preferidas", fam_options, default=["HEB", "IPE"])
    preferred_families = (
        [SectionFamily(f) for f in preferred_raw] if preferred_raw else [SectionFamily.HEB]
    )

    return {
        "country": country,
        "seismic_zone": seismic_zone,
        "steel_grade": steel_grade,
        "preferred_families": preferred_families,
    }
