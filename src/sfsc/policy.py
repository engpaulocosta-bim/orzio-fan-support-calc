"""Política única de escopo de peso do SFSC (auditoria C-07, §D).

Todas as regras de faixa de peso vivem aqui — validators, checker, UI,
reports e README devem usar estas constantes/funções e nunca redefinir
limites próprios.

Faixas (peso total em operação, soma das unidades):

    < 35 kg          BELOW_MIN  — permitido com warning; classificação PRELIMINARY
    35 – 500 kg      NORMAL     — faixa validada do produto; ENGINEERING_ESTIMATE
    500 – 600 kg     SPECIALIST — permitido; classificação REQUIRES_SPECIALIST
    600 – 1000 kg    EXTENDED   — fora da faixa do produto; só com confirmação
                                  explícita do utilizador; REQUIRES_SPECIALIST
    > 1000 kg        BLOCKED    — OutOfScopeError
"""
from __future__ import annotations

from enum import Enum

WEIGHT_MIN_RECOMMENDED_KG: float = 35.0
WEIGHT_SPECIALIST_KG: float = 500.0
WEIGHT_PRODUCT_MAX_KG: float = 600.0
WEIGHT_BLOCK_KG: float = 1000.0


class WeightBand(str, Enum):
    BELOW_MIN  = "BELOW_MIN"
    NORMAL     = "NORMAL"
    SPECIALIST = "SPECIALIST"
    EXTENDED   = "EXTENDED"
    BLOCKED    = "BLOCKED"


def weight_band(total_kg: float) -> WeightBand:
    """Classifica o peso total em operação numa faixa da política."""
    if total_kg > WEIGHT_BLOCK_KG:
        return WeightBand.BLOCKED
    if total_kg > WEIGHT_PRODUCT_MAX_KG:
        return WeightBand.EXTENDED
    if total_kg > WEIGHT_SPECIALIST_KG:
        return WeightBand.SPECIALIST
    if total_kg < WEIGHT_MIN_RECOMMENDED_KG:
        return WeightBand.BELOW_MIN
    return WeightBand.NORMAL


def weight_warning(total_kg: float) -> str | None:
    """Mensagem de aviso associada à faixa, ou None se faixa normal."""
    band = weight_band(total_kg)
    if band == WeightBand.BELOW_MIN:
        return (
            f"Peso total ({total_kg:.1f} kg) abaixo da faixa validada "
            f"({WEIGHT_MIN_RECOMMENDED_KG:.0f} kg). Resultado tratado como "
            "PRELIMINARY — verificar adequação de fixações leves."
        )
    if band == WeightBand.SPECIALIST:
        return (
            f"Peso total ({total_kg:.1f} kg) acima de "
            f"{WEIGHT_SPECIALIST_KG:.0f} kg — o cálculo requer revisão por "
            "engenheiro estrutural qualificado (REQUIRES_SPECIALIST)."
        )
    if band == WeightBand.EXTENDED:
        return (
            f"Peso total ({total_kg:.1f} kg) fora da faixa do produto "
            f"({WEIGHT_PRODUCT_MAX_KG:.0f} kg). Utilização confirmada pelo "
            "utilizador — resultado obrigatoriamente sujeito a revisão por "
            "engenheiro estrutural qualificado."
        )
    return None
