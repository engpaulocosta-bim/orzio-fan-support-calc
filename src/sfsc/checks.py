"""Estrutura granular de verificações e agregador global (tarefas 1.1, 1.2, secção 3).

Cada módulo de cálculo devolve um ``CheckResult`` com estado próprio. O
agregador separa claramente a utilização de cada módulo da utilização
governante global — corrigindo a confusão que misturava perfil metálico,
base plate, ancoragens e ligações num único número (origem da divergência
face ao Autodesk Robot).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import CheckStatus, ModuleId

# Thresholds configuráveis (secção 3). marginal: 0.85 ≤ η ≤ 1.00.
DEFAULT_MARGINAL_THRESHOLD = 0.85
DEFAULT_FAIL_THRESHOLD = 1.00


class DiagnosticMessage(BaseModel):
    """Mensagem técnica anexa a uma verificação."""

    severity: str = "info"  # info, warning, critical
    key: str  # chave i18n
    params: dict[str, object] = Field(default_factory=dict)


class CheckResult(BaseModel):
    """Resultado de um módulo de verificação (espelha o CheckResult da spec)."""

    id: ModuleId
    label_key: str
    eta: float | None = None
    status: CheckStatus
    governing: bool = False
    clause_refs: list[str] = Field(default_factory=list)
    messages: list[DiagnosticMessage] = Field(default_factory=list)
    inputs: dict[str, object] = Field(default_factory=dict)
    intermediate_values: dict[str, object] = Field(default_factory=dict)


class AggregateResult(BaseModel):
    """Diagnóstico global a partir dos módulos individuais."""

    checks: list[CheckResult] = Field(default_factory=list)
    global_status: CheckStatus = CheckStatus.OK
    governing_eta: float | None = None
    governing_module: ModuleId | None = None
    governing_label_key: str | None = None


def classify_eta(
    eta: float | None,
    *,
    marginal: float = DEFAULT_MARGINAL_THRESHOLD,
    fail: float = DEFAULT_FAIL_THRESHOLD,
) -> CheckStatus:
    """Estado de uma verificação a partir do η (secção 3)."""
    if eta is None:
        return CheckStatus.NOT_CHECKED
    if eta > fail:
        return CheckStatus.FAIL
    if eta >= marginal:
        return CheckStatus.MARGINAL
    return CheckStatus.OK


def aggregate_results(
    checks: list[CheckResult],
    *,
    marginal: float = DEFAULT_MARGINAL_THRESHOLD,
) -> AggregateResult:
    """Agrega os módulos num diagnóstico global (secção 3).

    Regras:
      - módulos NOT_CHECKED/INFORMATIVE são listados mas não governam;
      - qualquer FAIL ⇒ global FAIL;
      - senão, maxEta ≥ marginal ⇒ MARGINAL; caso contrário OK;
      - governingEta = maior η entre módulos que contam (ok/marginal/fail).
    """
    governing_candidates = [
        c
        for c in checks
        if c.status in (CheckStatus.OK, CheckStatus.MARGINAL, CheckStatus.FAIL)
        and c.eta is not None
    ]

    governing = max(governing_candidates, key=lambda c: c.eta or 0.0, default=None)
    governing_eta = governing.eta if governing else None
    governing_module = governing.id if governing else None
    governing_label = governing.label_key if governing else None

    # Marcar o governante (e desmarcar os restantes).
    for c in checks:
        c.governing = governing is not None and c.id == governing.id

    any_marginal = any(c.status == CheckStatus.MARGINAL for c in checks)
    if any(c.status == CheckStatus.FAIL for c in checks):
        global_status = CheckStatus.FAIL
    elif (governing_eta is not None and governing_eta >= marginal) or any_marginal:
        # Um módulo marginal (por utilização OU por regra construtiva) leva o
        # diagnóstico global a MARGINAL — nunca esconde uma ressalva de módulo.
        global_status = CheckStatus.MARGINAL
    else:
        global_status = CheckStatus.OK

    return AggregateResult(
        checks=checks,
        global_status=global_status,
        governing_eta=governing_eta,
        governing_module=governing_module,
        governing_label_key=governing_label,
    )
