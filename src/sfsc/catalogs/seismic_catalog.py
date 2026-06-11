"""Catálogo de factores sísmicos por país/zona."""
from __future__ import annotations

from ..config import get_seismic_zones
from ..enums import Country, SeismicCode
from ..exceptions import SeismicDataMissingError

_SEISMIC_CODE_MAP: dict[Country, SeismicCode] = {
    Country.PORTUGAL:   SeismicCode.EC8,
    Country.SPAIN:      SeismicCode.EC8,
    Country.IRELAND:    SeismicCode.EC8,
    Country.EU_GENERIC: SeismicCode.EC8,
    Country.UK:         SeismicCode.EC8_UK,
    Country.FRANCE:     SeismicCode.EC8,
    Country.BRAZIL:     SeismicCode.NBR_15421,
    Country.CHILE:      SeismicCode.NCH_433,
}


def get_seismic_code(country: Country) -> SeismicCode:
    return _SEISMIC_CODE_MAP.get(country, SeismicCode.EC8)


def get_seismic_factor(country: Country, zone: str | None = None) -> tuple[float, str]:
    """
    Retorna (ag_g, zone_used).
    Se zone=None, usa zona default do país (conservativa).
    """
    data = get_seismic_zones().get("countries", {})
    country_data = data.get(country.value)
    if not country_data:
        raise SeismicDataMissingError(country.value)

    target_zone = zone or country_data.get("default_zone")
    zones = country_data.get("zones", {})

    if target_zone not in zones:
        target_zone = country_data.get("default_zone")

    zone_data = zones.get(target_zone)
    if not zone_data:
        raise SeismicDataMissingError(country.value, str(target_zone))

    ag_g = zone_data.get("ag_g")
    if not isinstance(ag_g, (int, float)) or ag_g < 0:
        raise SeismicDataMissingError(
            country.value, f"zona '{target_zone}' com ag_g inválido: {ag_g!r}")

    return float(ag_g), str(target_zone)


def list_zones(country: Country) -> dict[str, dict]:
    data = get_seismic_zones().get("countries", {})
    country_data = data.get(country.value, {})
    return country_data.get("zones", {})
