"""Budget quantity take-off for SFSC results."""

from __future__ import annotations

import math
from typing import Any, cast

from ..enums import CantileverSubtype, SupportType
from ..models import FanSupportInput, FanSupportResult, QuantityEstimate
from ..units import mm_to_m

STEEL_DENSITY_KG_M3 = 7850.0


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def _plate_mass_kg(length_mm: float, width_mm: float, thickness_mm: float) -> float:
    volume_m3 = mm_to_m(length_mm) * mm_to_m(width_mm) * mm_to_m(thickness_mm)
    return volume_m3 * STEEL_DENSITY_KG_M3


def _primary_member_length_m(inp: FanSupportInput) -> tuple[float, list[dict[str, Any]]]:
    span_m = mm_to_m(inp.span_mm)
    height_m = mm_to_m(inp.installation_height_mm)
    items: list[dict[str, Any]] = []

    if inp.support_type == SupportType.HANGER:
        items.append({"item": "hanger_beam", "quantity": 1, "length_m": _round(span_m)})
    elif inp.support_type == SupportType.CANTILEVER_1:
        items.append({"item": "cantilever_arm", "quantity": 1, "length_m": _round(span_m)})
        if inp.cantilever_subtype == CantileverSubtype.BRACKETED:
            diagonal_m = math.hypot(span_m, height_m)
            items.append({"item": "diagonal_brace", "quantity": 1, "length_m": _round(diagonal_m)})
    elif inp.support_type == SupportType.CANTILEVER_2:
        items.append(
            {"item": "two_symmetric_arms_total", "quantity": 2, "length_m": _round(span_m / 2.0)}
        )
    elif inp.support_type == SupportType.CANTILEVER_3:
        items.append({"item": "top_beam", "quantity": 1, "length_m": _round(span_m)})
        items.append({"item": "columns", "quantity": 2, "length_m": _round(height_m)})
    elif inp.support_type in (SupportType.PEDESTAL, SupportType.COMBINED):
        items.append({"item": "longitudinal_skids", "quantity": 2, "length_m": _round(span_m)})
        if inp.support_type == SupportType.COMBINED:
            rod_length_m = mm_to_m(inp.hanger_rod_length_mm or inp.installation_height_mm)
            items.append(
                {"item": "combined_hanger_rods", "quantity": 4, "length_m": _round(rod_length_m)}
            )

    total = 0.0
    for item in items:
        total += cast(float, item["quantity"]) * cast(float, item["length_m"])
    return total, items


def calculate_quantities(inp: FanSupportInput, result: FanSupportResult) -> QuantityEstimate:
    """Return preliminary quantities for pricing and integration.

    The estimate intentionally uses the selected section and high-level geometry
    only. It should be treated as an early budgeting quantity, not a fabrication
    cut list.
    """
    line_items: list[dict[str, Any]] = []
    section = result.recommended_section

    member_length_m, member_items = _primary_member_length_m(inp)
    structural_mass_kg = 0.0
    if section is not None:
        structural_mass_kg = member_length_m * section.weight_kgm
        for item in member_items:
            mass_kg = (
                cast(float, item["quantity"]) * cast(float, item["length_m"]) * section.weight_kgm
            )
            line_items.append(
                {
                    **item,
                    "section": section.designation,
                    "weight_kgm": _round(section.weight_kgm),
                    "mass_kg": _round(mass_kg, 2),
                }
            )

    plate_mass_kg = 0.0
    if result.base_plate is not None:
        bp = result.base_plate
        plate_mass_kg = _plate_mass_kg(bp.length_mm, bp.width_mm, bp.thickness_mm)
        line_items.append(
            {
                "item": "base_plate",
                "quantity": 1,
                "length_mm": _round(bp.length_mm, 1),
                "width_mm": _round(bp.width_mm, 1),
                "thickness_mm": _round(bp.thickness_mm, 1),
                "mass_kg": _round(plate_mass_kg, 2),
            }
        )

    anchor_count = 0
    anchor_diameter_mm = 0.0
    anchor_depth_or_length_mm = 0.0
    anchor_type = ""
    if result.anchor is not None:
        anchor = result.anchor
        anchor_count = anchor.n_anchors
        anchor_diameter_mm = anchor.anchor_diameter_mm
        anchor_type = anchor.anchor_type
        if anchor.anchor_type == "rod":
            anchor_depth_or_length_mm = inp.hanger_rod_length_mm or inp.installation_height_mm
        else:
            anchor_depth_or_length_mm = anchor.embedment_depth_mm
        line_items.append(
            {
                "item": "anchors_or_rods",
                "quantity": anchor_count,
                "type": anchor_type,
                "diameter_mm": _round(anchor_diameter_mm, 1),
                "embedment_or_length_mm": _round(anchor_depth_or_length_mm, 1),
            }
        )

    weld_length_mm = 0.0
    weld_throat_values: list[float] = []
    if result.base_plate is not None and section is not None:
        weld_length_mm += 2.0 * (section.h_mm + section.b_mm)
        if result.base_plate.weld_throat_mm:
            weld_throat_values.append(result.base_plate.weld_throat_mm)
    if result.metal_connection is not None:
        weld_length_mm += result.metal_connection.weld_length_mm
        if result.metal_connection.weld_throat_mm:
            weld_throat_values.append(result.metal_connection.weld_throat_mm)
    weld_throat_mm = max(weld_throat_values, default=0.0)
    if weld_length_mm > 0:
        line_items.append(
            {
                "item": "welds",
                "length_mm": _round(weld_length_mm, 1),
                "throat_mm": _round(weld_throat_mm, 1),
            }
        )

    return QuantityEstimate(
        structural_steel_length_m=_round(member_length_m),
        structural_steel_mass_kg=_round(structural_mass_kg, 2),
        plate_mass_kg=_round(plate_mass_kg, 2),
        total_steel_mass_kg=_round(structural_mass_kg + plate_mass_kg, 2),
        anchor_count=anchor_count,
        anchor_diameter_mm=_round(anchor_diameter_mm, 1),
        anchor_embedment_or_length_mm=_round(anchor_depth_or_length_mm, 1),
        anchor_type=anchor_type,
        weld_length_mm=_round(weld_length_mm, 1),
        weld_throat_mm=_round(weld_throat_mm, 1),
        line_items=line_items,
    )
