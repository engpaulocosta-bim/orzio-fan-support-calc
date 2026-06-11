"""Verificação final e classificação do resultado."""
from __future__ import annotations

from ..enums import CheckerStatus, ClassificationLevel
from ..models import FanSupportInput, FanSupportResult
from ..policy import WeightBand, weight_band

_PRIORITY = [
    CheckerStatus.FAIL,
    CheckerStatus.REQUIRES_SPECIALIST,
    CheckerStatus.DATASET_MISSING,
    CheckerStatus.OUT_OF_SCOPE,
    CheckerStatus.MARGINAL,
    CheckerStatus.WARNING,
    CheckerStatus.PASS,
]


def run_checker(
    inp: FanSupportInput,
    result: FanSupportResult,
    extra_statuses: list[CheckerStatus] | None = None,
) -> CheckerStatus:
    """Consolida todos os ratios de utilização e retorna status global.

    extra_statuses permite ao orquestrador injectar estados recuperados de
    excepções (DATASET_MISSING, OUT_OF_SCOPE — auditoria H-08).
    """
    statuses: list[CheckerStatus] = list(extra_statuses or [])

    if result.section_verification:
        statuses.append(result.section_verification.status)
    if result.base_plate:
        statuses.append(result.base_plate.status)
    if result.anchor:
        statuses.append(result.anchor.status)
    if result.metal_connection:
        statuses.append(result.metal_connection.status)

    if not statuses:
        return CheckerStatus.PASS

    for p in _PRIORITY:
        if p in statuses:
            return p
    return CheckerStatus.PASS


def classify(inp: FanSupportInput, result: FanSupportResult) -> ClassificationLevel:
    """Determina o nível de classificação do cálculo (política sfsc.policy)."""
    band = weight_band(inp.total_operating_weight_kg)

    # Acima da faixa de produto ou >500 kg → especialista
    if band in (WeightBand.SPECIALIST, WeightBand.EXTENDED, WeightBand.BLOCKED):
        return ClassificationLevel.REQUIRES_SPECIALIST

    # Combinação sísmica relevante (ag > 0.15g)
    if result.seismic_factor_g > 0.15:
        return ClassificationLevel.REQUIRES_SPECIALIST

    # COMBINED com molas → vibração fora do âmbito
    from ..enums import AntiVibrationType, SupportType
    if (result.support_type == SupportType.COMBINED and
            inp.anti_vibration == AntiVibrationType.SPRINGS):
        return ClassificationLevel.REQUIRES_SPECIALIST

    # Abaixo do mínimo validado → resultado preliminar
    if band == WeightBand.BELOW_MIN:
        return ClassificationLevel.PRELIMINARY

    return ClassificationLevel.ENGINEERING_ESTIMATE
