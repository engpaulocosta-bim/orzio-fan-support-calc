"""Helpers for load surfaces, manual loads, and traceable distribution."""

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
        labels = [f"beam_{index}" for index in range(1, max(2, inp.platform_n_beams) + 1)]
        if inp.has_platform_grillage:
            labels.extend(f"crossbeam_{index}" for index in range(1, inp.platform_n_crossbeams + 1))
        return labels
    return ["primary_member"]


def effective_distribution_method(inp: FanSupportInput) -> LoadDistributionMethod:
    """Return the physically available method for the current platform geometry."""

    requested = inp.walking_surface.distribution_method
    if requested != LoadDistributionMethod.TWO_WAY:
        return requested
    width_m = mm_to_m(inp.platform_width_eff_mm)
    length_m = mm_to_m(inp.platform_length_eff_mm)
    aspect_ratio = length_m / width_m if width_m > 0.0 else 0.0
    if inp.has_platform_grillage and 0.5 <= aspect_ratio <= 2.0:
        return LoadDistributionMethod.TWO_WAY
    return LoadDistributionMethod.ONE_WAY


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
    distribution_method = effective_distribution_method(inp)

    warnings: list[str] = []
    requires_engineer_review = False

    if distribution_method == LoadDistributionMethod.MANUAL:
        if not inp.walking_surface.target_member_ids:
            requires_engineer_review = True
            warnings.append(
                "Manual surface distribution without explicit target members requires engineer review."
            )

    surface_components: list[dict[str, object]] = []

    def _add_surface_component(
        source: str,
        load_case: LoadCaseName,
        area_load_kn_m2: float,
        component_area_m2: float = area_m2,
    ) -> dict[str, object] | None:
        if area_load_kn_m2 <= 0.0 or component_area_m2 <= 0.0:
            return None
        component: dict[str, object] = {
            "source": source,
            "load_case": load_case.value,
            "area_load_kn_m2": round(area_load_kn_m2, 6),
            "area_m2": round(component_area_m2, 6),
            "total_load_kN": round(area_load_kn_m2 * component_area_m2, 6),
            "direction": LoadDirection.GLOBAL_Z.value,
            "distribution_method": distribution_method.value,
        }
        surface_components.append(component)
        return component

    _add_surface_component(
        "surface_self_weight",
        LoadCaseName.G,
        inp.walking_surface.self_weight_kn_m2,
    )
    _add_surface_component(
        "surface_imposed",
        LoadCaseName.Q,
        inp.walking_surface.imposed_load_kn_m2,
    )
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

    def _append_member_loads(
        component: dict[str, object],
        targets: list[str],
        loaded_length_m: float,
        share: float,
    ) -> None:
        if not targets or loaded_length_m <= 0.0 or share <= 0.0:
            return
        total_load_kN = _as_float(component["total_load_kN"]) * share
        area_load_kn_m2 = _as_float(component["area_load_kn_m2"])
        load_per_target_kN = total_load_kN / len(targets)
        line_load_kN_m = load_per_target_kN / loaded_length_m
        tributary_width_m = line_load_kN_m / area_load_kn_m2 if area_load_kn_m2 > 0.0 else 0.0
        for target in targets:
            distributed_line_loads.append(
                {
                    "source": component["source"],
                    "load_case": component["load_case"],
                    "target_member": target,
                    "tributary_width_m": round(tributary_width_m, 6),
                    "line_load_kN_m": round(line_load_kN_m, 6),
                    "loaded_length_m": round(loaded_length_m, 6),
                    "total_load_kN": round(load_per_target_kN, 6),
                    "distribution_method": distribution_method.value,
                    "direction_share": round(share, 6),
                }
            )

    def _distribute_area_component(component: dict[str, object]) -> None:
        if distribution_method == LoadDistributionMethod.TWO_WAY:
            longitudinal_targets = [
                target for target in targets_for_surface if target.startswith("beam_")
            ]
            transverse_targets = [
                target for target in targets_for_surface if target.startswith("crossbeam_")
            ]
            length_fourth = length_m**4
            width_fourth = width_m**4
            denominator = length_fourth + width_fourth
            longitudinal_share = width_fourth / denominator if denominator > 0.0 else 0.5
            _append_member_loads(
                component,
                longitudinal_targets,
                length_m,
                longitudinal_share,
            )
            _append_member_loads(
                component,
                transverse_targets,
                width_m,
                1.0 - longitudinal_share,
            )
            return
        _append_member_loads(component, targets_for_surface, length_m, 1.0)

    if width_m > 0 and length_m > 0:
        for component in surface_components:
            vertical_totals_by_case[str(component["load_case"])] += _as_float(
                component["total_load_kN"]
            )
            _distribute_area_component(component)

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

        if manual_load.load_type == ManualLoadType.AREA and not is_horizontal:
            assert manual_load.loaded_area_m2 is not None
            manual_component = _add_surface_component(
                name,
                manual_load.load_case,
                manual_load.value,
                manual_load.loaded_area_m2,
            )
            if manual_component is not None:
                _distribute_area_component(manual_component)

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

    if distributed_line_loads and distribution_method != LoadDistributionMethod.TWO_WAY:
        warnings.append(
            "Surface load distribution uses a simplified one-way / tributary-width method."
        )

    return LoadPathSummary(
        surface_components=surface_components,
        distributed_line_loads=distributed_line_loads,
        manual_loads_applied=manual_loads_applied,
        vertical_totals_by_case={
            key: round(value, 6) for key, value in vertical_totals_by_case.items()
        },
        horizontal_total_kN=round(horizontal_total_kN, 6),
        warnings=warnings,
        requires_engineer_review=requires_engineer_review,
    )
