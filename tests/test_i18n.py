"""i18n PT/EN/ES — tarefa 1.6 / secção 8.4.

Garante paridade de chaves entre locales e cobertura dos tipos de suporte e
módulos de cálculo nos três idiomas.
"""

from sfsc.enums import ModuleId, SupportType
from sfsc.i18n import Lang, available_keys, missing_keys, t

_SUPPORT_LABEL_KEYS = {
    SupportType.HANGER: "support.types.hanger_threaded_rods.label",
    SupportType.CANTILEVER_1: "support.types.cantilever_bracket.label",
    SupportType.CANTILEVER_2: "support.types.double_cantilever.label",
    SupportType.CANTILEVER_3: "support.types.inverted_u_frame.label",
    SupportType.PEDESTAL: "support.types.pedestal_skid_frame.label",
    SupportType.COMBINED: "support.types.combined_table_hanger.label",
    SupportType.PLATFORM_FRAME_BRACED: "support.types.platform_frame_braced.label",
}

_MODULE_LABEL_KEYS = {
    ModuleId.STEEL_SECTION: "calculation.modules.steelSection",
    ModuleId.LATERAL_TORSIONAL_BUCKLING: "calculation.modules.lateralTorsionalBuckling",
    ModuleId.BASE_PLATE: "calculation.modules.basePlate",
    ModuleId.CONCRETE_ANCHORS: "calculation.modules.anchors",
    ModuleId.STEEL_CONNECTIONS: "calculation.modules.steelConnections",
    ModuleId.SEISMIC_EQUIVALENT_STATIC: "calculation.modules.seismicEquivalentStatic",
    ModuleId.SERVICEABILITY: "calculation.modules.serviceability",
    ModuleId.LOAD_DISTRIBUTION_SURFACE: "calculation.modules.loadDistributionSurface",
}


def test_locales_have_identical_key_sets():
    miss = missing_keys()
    assert miss["en"] == set(), f"EN em falta: {miss['en']}"
    assert miss["es"] == set(), f"ES em falta: {miss['es']}"


def test_all_support_types_translated_in_three_langs():
    for support, key in _SUPPORT_LABEL_KEYS.items():
        for lang in (Lang.PT, Lang.EN, Lang.ES):
            value = t(key, lang)
            assert value and value != key, f"{support.value} sem tradução {lang.value}"


def test_all_modules_translated_in_three_langs():
    for module, key in _MODULE_LABEL_KEYS.items():
        for lang in (Lang.PT, Lang.EN, Lang.ES):
            value = t(key, lang)
            assert value and value != key, f"{module.value} sem tradução {lang.value}"


def test_platform_type_description_distinct_per_lang():
    pt = t("support.types.platform_frame_braced.description", Lang.PT)
    en = t("support.types.platform_frame_braced.description", Lang.EN)
    es = t("support.types.platform_frame_braced.description", Lang.ES)
    assert pt != en != es
    assert "tramex" in pt.lower() or "grelha" in pt.lower()


def test_param_interpolation_and_fallback():
    msg = t("warning.module.disabled", Lang.EN, module="Base plate")
    assert "Base plate" in msg
    # chave inexistente devolve a própria chave
    assert t("nonexistent.key", Lang.PT) == "nonexistent.key"


def test_default_lang_is_pt():
    assert t("status.ok") == t("status.ok", Lang.PT)
    assert "pt" in {lang.value for lang in Lang}
    assert len(available_keys(Lang.PT)) >= 40
