"""Internacionalização (PT/EN/ES) baseada em chaves — tarefa 1.6.

Uso::

    from sfsc.i18n import t, Lang
    t("support.types.platform_frame_braced.label", Lang.PT)

As traduções vivem em ``pt.json``, ``en.json`` e ``es.json`` (mesma árvore
de chaves). Texto nunca deve ser hardcoded nas camadas de UI/relatório.
"""

from __future__ import annotations

import functools
import json
from enum import Enum
from pathlib import Path

_DIR = Path(__file__).parent


class Lang(str, Enum):
    PT = "pt"
    EN = "en"
    ES = "es"


DEFAULT_LANG = Lang.PT


@functools.lru_cache(maxsize=4)
def _catalog(lang: str) -> dict[str, str]:
    path = _DIR / f"{lang}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, lang: Lang | str = DEFAULT_LANG, /, **params: object) -> str:
    """Traduz ``key`` para ``lang``; faz fallback PT → chave; interpola ``params``."""
    lang_val = lang.value if isinstance(lang, Lang) else str(lang)
    text = _catalog(lang_val).get(key)
    if text is None and lang_val != DEFAULT_LANG.value:
        text = _catalog(DEFAULT_LANG.value).get(key)
    if text is None:
        return key
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError):
            return text
    return text


def available_keys(lang: Lang | str = DEFAULT_LANG) -> set[str]:
    lang_val = lang.value if isinstance(lang, Lang) else str(lang)
    return set(_catalog(lang_val).keys())


def missing_keys() -> dict[str, set[str]]:
    """Chaves presentes em PT mas ausentes em EN/ES (apoio aos testes i18n)."""
    base = available_keys(Lang.PT)
    return {
        "en": base - available_keys(Lang.EN),
        "es": base - available_keys(Lang.ES),
    }
