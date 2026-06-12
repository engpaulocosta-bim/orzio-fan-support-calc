"""Phase 02 helpers for load surfaces, manual loads, and traceable distribution."""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import (
    LoadCaseName,
    LoadDirection,
    LoadDistributionMethod,
    ManualLoadType,
    SupportType,
)
from ..models import FanSupportInput, ManualLoad
from ..units import kg_to_kn, mm_to_m


@dataclass(frozen=True)
class LoadPathSummary:
    surface_components: list[dict[str, object]]
    distributed_line_loads: list[dict[str, object]]
    manual_loads_applied: list[dict[str, object]]
    vertical_totals_by_case: dict[str, float]
    horizontal_total_kN: float
    warnings: list[str]
    requires_engineer_review: bool


def _as_float(value: object) -> float:
    assert isinstance(value, int | float)
    return float(value)


def member_labels_for_input(inp: FanSupportInput) -> list[str]:
    if inp.support_type == SupportType.PLATFORM_FRAME_BRACED:
        return [f"beam_{index}" for index in range(1, max(2, inp.platform_n_beams) + 1)]
    return ["primary_member"]


def _manual_targets(inp: FanSupportInput, manual_load: ManualLoad) -> list[str]:
    labels = member_labels_for_input(inp)
    if manual_load.target_member_id:
        return [manual_load.target_member_id]
    return labels


def build_load_path_summary(inp: FanSupportInput) -> LoadPathSummary:
    area_m2 = inp.platform_area_m2
    width_m = mm_to_m(inp.platform_width_eff_mm)
    length_m = mm_to_m(inp.platform_length_eff_mm)
    beam_labels = member_labels_for_input(inp)
    targets_for_surface = inp.walking_surface.target_member_ids or beam_labels

    warnings: list[str] = []
    requires_engineer_review = False

    if inp.walking_surface.distribution_method == LoadDistributionMethod.MANUAL:
        if not inp.walking_surface.target_member_ids:
            requires_engineer_review = True
            warnings.append(
                "Manual surface distribution without explicit target members requires engineer review."
            )

    surface_components: list[dict[str, object]] = []

    def _add_surface_component(source: str, load_case: LoadCaseName, area_load_kn_m2: float) -> None:
        if area_load_kn_m2 <= 0.0:
            return
        surface_components.append(
            {
                "source": source,
                "load_case": load_case.value,
                "area_load_kn_m2": round(area_load_kn_m2, 6),
                "area_m2": round(area_m2, 6),
                "total_load_kN": round(area_load_kn_m2 * area_m2, 6),
                "direction": LoadDirection.GLOBAL_Z.value,
                "distribution_method": inp.walking_surface.distribution_method.value,
            }
        )

    _add_surface_component("surface_self_weight", LoadCaseName.G, inp.walking_surface.self_weight_kn_m2)
    _add_surface_component("surface_imposed", LoadCaseName.Q, inp.walking_surface.imposed_load_kn_m2)
    _add_surface_component(
        "surface_maintenance",
        LoadCaseName.Q,
        inp.walking_surface.maintenance_load_kn_m2,
    )
    if inp.walking_surface.equipment_load_distributed and area_m2 > 0:
        _add_surface_component(
            "equipment_distributed",
            LoadCaseName.EQ,
            kg_to_kn(inp.total_operating_weight_kg) / area_m2,
        )

    vertical_totals_by_case = {case.value: 0.0 for case in LoadCaseName}
    horizontal_total_kN = 0.0
    distributed_line_loads: list[dict[str, object]] = []

    if width_m > 0 and length_m > 0 and surface_components:
        tributary_width_m = width_m / max(1, len(targets_for_surface))
        for component in surface_components:
            area_load_kn_m2 = _as_float(component["area_load_kn_m2"])
            total_component_kN = _as_float(component["total_load_kN"])
            vertical_totals_by_case[str(component["load_case"])] += total_component_kN
            for target in targets_for_surface:
                line_load_kN_m = area_load_kn_m2 * tributary_width_m
                distributed_line_loads.append(
                    {
                        "source": component["source"],
                        "load_case": component["load_case"],
                        "target_member": target,
                        "tributary_width_m": round(tributary_width_m, 6),
                        "line_load_kN_m": round(line_load_kN_m, 6),
                        "loaded_length_m": round(length_m, 6),
                        "total_load_kN": round(line_load_kN_m * length_m, 6),
                        "distribution_method": component["distribution_method"],
                    }
                )

    manual_loads_applied: list[dict[str, object]] = []
    for index, manual_load in enumerate(inp.manual_loads, start=1):
        name = manual_load.name or f"manual_{index}"
        target_members = _manual_targets(inp, manual_load)
        if manual_load.target_member_id is None and len(target_members) > 1:
            requires_engineer_review = True
            warnings.append(
                f"Manual load '{name}' without explicit target member requires engineer review."
            )

        if manual_load.load_type == ManualLoadType.POINT:
            total_load_kN = manual_load.value
        elif manual_load.load_type == ManualLoadType.LINE:
            assert manual_load.loaded_length_m is not None
            total_load_kN = manual_load.value * manual_load.loaded_length_m
        else:
            assert manual_load.loaded_area_m2 is not None
            total_load_kN = manual_load.value * manual_load.loaded_area_m2

        is_horizontal = manual_load.direction not in (
            LoadDirection.GLOBAL_Z,
            LoadDirection.LOCAL_Z,
        )
        if is_horizontal:
            horizontal_total_kN += total_load_kN
        else:
            vertical_totals_by_case[manual_load.load_case.value] += total_load_kN

        if manual_load.load_type == ManualLoadType.AREA and not is_horizontal and area_m2 > 0:
            surface_components.append(
                {
                    "source": name,
                    "load_case": manual_load.load_case.value,
                    "area_load_kn_m2": round(manual_load.value, 6),
                    "area_m2": round(manual_load.loaded_area_m2 or 0.0, 6),
                    "total_load_kN": round(total_load_kN, 6),
                    "direction": manual_load.direction.value,
                    "distribution_method": inp.walking_surface.distribution_method.value,
                }
            )
            tributary_width_m = width_m / max(1, len(targets_for_surface)) if targets_for_surface else 0.0
            for target in targets_for_surface:
                line_load_kN_m = manual_load.value * tributary_width_m
                distributed_line_loads.append(
                    {
                        "source": name,
                        "load_case": manual_load.load_case.value,
                        "target_member": target,
                        "tributary_width_m": round(tributary_width_m, 6),
                        "line_load_kN_m": round(line_load_kN_m, 6),
                        "loaded_length_m": round(length_m, 6),
                        "total_load_kN": round(line_load_kN_m * length_m, 6),
                        "distribution_method": inp.walking_surface.distribution_method.value,
                    }
                )

        for target in target_members:
            manual_loads_applied.append(
                {
                    "name": name,
                    "load_type": manual_load.load_type.value,
                    "load_case": manual_load.load_case.value,
                    "direction": manual_load.direction.value,
                    "target_member": target,
                    "value": round(manual_load.value, 6),
                    "unit": manual_load.unit,
                    "equivalent_total_kN": round(total_load_kN, 6),
                    "loaded_length_m": manual_load.loaded_length_m,
                    "loaded_area_m2": manual_load.loaded_area_m2,
                }
            )

    if distributed_line_loads:
        warnings.append(
            "Surface load distribution uses a simplified one-way / tributary-width method."
        )

    return LoadPathSummary(
        surface_components=surface_components,
        distributed_line_loads=distributed_line_loads,
        manual_loads_applied=manual_loads_applied,
        vertical_totals_by_case={k: round(v, 6) for k, v in vertical_totals_by_case.items()},
        horizontal_total_kN=round(horizontal_total_kN, 6),
        warnings=warnings,
        requires_engineer_review=requires_engineer_review,
    )
