"""Section orientation helpers for local-axis property selection."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import SectionOrientation
from .models import SteelSection

_ORIENTATION_TOLERANCE_DEG = 1e-6


class UnsupportedSectionOrientationError(ValueError):
    """Raised when the current phase cannot map an orientation to local axes."""


def resolve_section_orientation_deg(
    orientation: SectionOrientation,
    rotation_deg: float | None = None,
) -> float:
    """Return the local-axis rotation currently supported by Phase 01.

    Phase 01 supports only the explicit 0 deg and 90 deg cases.
    """

    if orientation == SectionOrientation.STRONG_AXIS_VERTICAL:
        return 0.0
    if orientation == SectionOrientation.WEAK_AXIS_VERTICAL:
        return 90.0
    if rotation_deg is None:
        raise UnsupportedSectionOrientationError("custom_rotation requires section_rotation_deg.")
    normalized = rotation_deg % 180.0
    if abs(normalized) <= _ORIENTATION_TOLERANCE_DEG:
        return 0.0
    if abs(normalized - 90.0) <= _ORIENTATION_TOLERANCE_DEG:
        return 90.0
    raise UnsupportedSectionOrientationError(
        "Phase 01 supports only section rotations of 0 deg or 90 deg."
    )


def orientation_swaps_local_axes(orientation_deg: float) -> bool:
    normalized = orientation_deg % 180.0
    return abs(normalized - 90.0) <= _ORIENTATION_TOLERANCE_DEG


@dataclass(frozen=True)
class LocalSectionAxisProperties:
    orientation_deg: float
    swapped_axes: bool
    local_iy_mm4: float
    local_iz_mm4: float
    local_iy_radius_mm: float
    local_iz_radius_mm: float
    local_wy_el_mm3: float
    local_wz_el_mm3: float
    local_wy_pl_mm3: float
    local_wz_pl_mm3: float


def get_local_section_axis_properties(
    section: SteelSection,
    orientation_deg: float,
) -> LocalSectionAxisProperties:
    swapped = orientation_swaps_local_axes(orientation_deg)
    if swapped:
        return LocalSectionAxisProperties(
            orientation_deg=90.0,
            swapped_axes=True,
            local_iy_mm4=section.I_z_mm4,
            local_iz_mm4=section.I_y_mm4,
            local_iy_radius_mm=section.i_z_mm,
            local_iz_radius_mm=section.i_y_mm,
            local_wy_el_mm3=section.W_el_z_mm3,
            local_wz_el_mm3=section.W_el_y_mm3,
            local_wy_pl_mm3=section.W_pl_z_mm3,
            local_wz_pl_mm3=section.W_pl_y_mm3,
        )
    return LocalSectionAxisProperties(
        orientation_deg=0.0,
        swapped_axes=False,
        local_iy_mm4=section.I_y_mm4,
        local_iz_mm4=section.I_z_mm4,
        local_iy_radius_mm=section.i_y_mm,
        local_iz_radius_mm=section.i_z_mm,
        local_wy_el_mm3=section.W_el_y_mm3,
        local_wz_el_mm3=section.W_el_z_mm3,
        local_wy_pl_mm3=section.W_pl_y_mm3,
        local_wz_pl_mm3=section.W_pl_z_mm3,
    )


def select_local_iy_mm4(section: SteelSection, orientation_deg: float) -> float:
    return get_local_section_axis_properties(section, orientation_deg).local_iy_mm4


def select_local_iz_mm4(section: SteelSection, orientation_deg: float) -> float:
    return get_local_section_axis_properties(section, orientation_deg).local_iz_mm4


def select_local_wy_mm3(section: SteelSection, orientation_deg: float) -> float:
    return get_local_section_axis_properties(section, orientation_deg).local_wy_el_mm3


def select_local_wz_mm3(section: SteelSection, orientation_deg: float) -> float:
    return get_local_section_axis_properties(section, orientation_deg).local_wz_el_mm3
