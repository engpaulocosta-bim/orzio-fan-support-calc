"""Engineering interpretation helpers for calculation results."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import CheckerStatus, ClassificationLevel
from .models import FanSupportResult


@dataclass(frozen=True)
class ResultAssessment:
    status: CheckerStatus
    classification: ClassificationLevel
    headline: str
    summary: str
    governing_item: str
    governing_utilization: float | None
    utilization_percent: float | None
    conservatism_percent: float | None
    limit_percent: float | None
    exceedance_percent: float | None
    is_conservative: bool
    is_borderline: bool
    is_failure: bool
    is_specialist: bool


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}%"


def _round_pct(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def get_governing_utilization(result: FanSupportResult) -> tuple[str, float | None]:
    checks: list[tuple[str, float]] = []

    if result.section_verification:
        label = "Secção metálica"
        if result.section_verification.governing_check:
            label = f"{label} ({result.section_verification.governing_check})"
        checks.append((label, result.section_verification.utilization_ratio))

    if result.base_plate:
        checks.append(("Mesa / base plate", result.base_plate.utilization_ratio))

    if result.anchor:
        anchor_eta = max(
            result.anchor.utilization_tension,
            result.anchor.utilization_shear,
            result.anchor.utilization_combined,
        )
        anchor_label = "Varões de suspensão" if result.anchor.anchor_type == "rod" else "Ancoragens"
        checks.append((anchor_label, anchor_eta))

    if result.metal_connection:
        checks.append(("Ligações metálicas", result.metal_connection.utilization_ratio))

    if not checks:
        return "Sem verificacoes dimensionantes", None

    return max(checks, key=lambda item: item[1])


def assess_result(result: FanSupportResult) -> ResultAssessment:
    """Interpretação do resultado.

    REQUIRES_SPECIALIST tem precedência sobre qualquer leitura "verde"
    (auditoria C-03): um cálculo classificado como REQUIRES_SPECIALIST nunca
    produz a headline "PASSA - CONSERVADOR", mesmo com status PASS.
    """
    item, eta = get_governing_utilization(result)
    utilization_percent = _round_pct(eta * 100.0 if eta is not None else None)
    conservatism_percent = _round_pct(max(0.0, (1.0 - eta) * 100.0) if eta is not None else None)
    exceedance_percent = _round_pct(max(0.0, (eta - 1.0) * 100.0) if eta is not None else None)
    limit_percent = utilization_percent

    classification = result.classification_level
    is_specialist = (
        classification == ClassificationLevel.REQUIRES_SPECIALIST
        or result.status == CheckerStatus.REQUIRES_SPECIALIST
    )
    is_failure = result.status == CheckerStatus.FAIL or (eta is not None and eta > 1.0)
    is_borderline = result.status == CheckerStatus.MARGINAL or (
        eta is not None and 0.90 < eta <= 1.0
    )
    is_conservative = (
        result.status == CheckerStatus.PASS
        and not is_specialist
        and eta is not None
        and eta <= 0.90
    )

    if is_failure:
        headline = "NÃO PASSA"
        summary = (
            "O cálculo não passa: a verificação governante excede o limite "
            f"normativo em {_pct(exceedance_percent)}."
        )
        if is_specialist:
            summary += (
                " Adicionalmente, o caso está classificado como REQUIRES_SPECIALIST — "
                "qualquer solução requer engenheiro estrutural qualificado."
            )
    elif is_specialist:
        headline = "REQUER ESPECIALISTA"
        summary = (
            "Este cálculo NÃO pode ser usado sem revisão por engenheiro "
            "estrutural qualificado (classificação REQUIRES_SPECIALIST). "
            f"As verificações numéricas usam {_pct(limit_percent)} da capacidade, "
            "mas o caso está fora das condições em que o modelo simplificado é "
            "suficiente por si só."
        )
    elif is_borderline:
        headline = "PASSA, MAS ESTÁ NO LIMITE"
        summary = (
            "O cálculo passa, mas está no limite: a verificação governante "
            f"usa {_pct(limit_percent)} da capacidade, com apenas "
            f"{_pct(conservatism_percent)} de folga informativa."
        )
    elif result.status == CheckerStatus.PASS:
        headline = "PASSA - CONSERVADOR"
        summary = (
            "O cálculo passa com margem conservadora: a verificação governante "
            f"usa {_pct(limit_percent)} da capacidade, deixando "
            f"{_pct(conservatism_percent)} de folga informativa até ao limite."
        )
    else:
        headline = result.status.value
        summary = (
            "O resultado requer leitura técnica adicional antes de ser tratado "
            f"como aprovado. Estado técnico: {result.status.value}."
        )

    if classification == ClassificationLevel.PRELIMINARY and not is_failure:
        summary += (
            " Classificação PRELIMINARY: caso abaixo da faixa validada do produto — "
            "resultado meramente indicativo."
        )

    return ResultAssessment(
        status=result.status,
        classification=classification,
        headline=headline,
        summary=summary,
        governing_item=item,
        governing_utilization=eta,
        utilization_percent=utilization_percent,
        conservatism_percent=conservatism_percent,
        limit_percent=limit_percent,
        exceedance_percent=exceedance_percent,
        is_conservative=is_conservative,
        is_borderline=is_borderline,
        is_failure=is_failure,
        is_specialist=is_specialist,
    )
