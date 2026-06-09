"""Final result checking and classification."""
from __future__ import annotations

import math

from ..enums import CheckerStatus, ClassificationLevel
from ..models import FanSupportInput, FanSupportResult


def run_checker(inp: FanSupportInput, result: FanSupportResult) -> CheckerStatus:
    """Consolidate utilization ratios and return the global status."""
    statuses: list[CheckerStatus] = []
    ratios: list[float] = []

    if result.section_verification:
        statuses.append(result.section_verification.status)
        ratios.append(result.section_verification.utilization_ratio)
        ratios.extend(result.section_verification.utilization_by_check.values())
    if result.base_plate:
        statuses.append(result.base_plate.status)
        ratios.extend([
            result.base_plate.utilization_ratio,
            result.base_plate.utilization_bearing,
            result.base_plate.utilization_bending,
            result.base_plate.bolt_utilization_fan,
            result.base_plate.bolt_utilization_structure,
            result.base_plate.weld_utilization,
        ])
    if result.anchor:
        statuses.append(result.anchor.status)
        ratios.extend([
            result.anchor.utilization_tension,
            result.anchor.utilization_shear,
            result.anchor.utilization_combined,
            result.anchor.utilization_bearing,
            result.anchor.utilization_tearout,
            result.anchor.utilization_block_shear,
            result.anchor.utilization_prying,
        ])
    if result.metal_connection:
        statuses.append(result.metal_connection.status)
        ratios.extend([
            result.metal_connection.utilization_ratio,
            result.metal_connection.utilization_bolt_shear,
            result.metal_connection.utilization_bolt_tension,
            result.metal_connection.weld_utilization,
        ])
    if result.platform and result.platform.diagonal:
        statuses.append(result.platform.diagonal.status)
        ratios.append(result.platform.diagonal.utilization_ratio)

    if any(not math.isfinite(float(r)) for r in ratios):
        result.warnings.append("Resultado numerico invalido (NaN ou infinito); calculo marcado como FAIL.")
        return CheckerStatus.FAIL

    if not statuses:
        return CheckerStatus.PASS

    priority = [
        CheckerStatus.FAIL,
        CheckerStatus.REQUIRES_SPECIALIST,
        CheckerStatus.DATASET_MISSING,
        CheckerStatus.OUT_OF_SCOPE,
        CheckerStatus.MARGINAL,
        CheckerStatus.WARNING,
        CheckerStatus.PASS,
    ]
    for p in priority:
        if p in statuses:
            return p
    return CheckerStatus.PASS


def classify(inp: FanSupportInput, result: FanSupportResult) -> ClassificationLevel:
    """Return the calculation classification level."""
    total_kg = inp.total_operating_weight_kg

    if total_kg > 500.0:
        return ClassificationLevel.REQUIRES_SPECIALIST

    if result.seismic_factor_g > 0.15:
        return ClassificationLevel.REQUIRES_SPECIALIST

    from ..enums import AntiVibrationType, SupportType
    if (
        result.support_type == SupportType.COMBINED
        and inp.anti_vibration == AntiVibrationType.SPRINGS
    ):
        return ClassificationLevel.REQUIRES_SPECIALIST

    return ClassificationLevel.ENGINEERING_ESTIMATE
