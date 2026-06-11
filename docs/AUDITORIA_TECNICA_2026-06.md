# Auditoria Técnica Completa — SFSC (Steel Fan Support Calc)

| Campo | Valor |
|---|---|
| Repositório | `engpaulocosta-bim/orzio-fan-support-calc` |
| Commit auditado | `688d43b` (branch base) |
| Data da auditoria | 2026-06-09 |
| Âmbito | Código-fonte completo (~4 900 linhas Python), YAMLs, testes, build desktop, packaging |
| Método | Leitura integral do código, execução da suite de testes (48/48 PASS, 90% cobertura de linhas), execução de casos de verificação manuais |

> **Natureza deste documento**: auditoria e plano. Nenhuma alteração de código foi feita.
> Os achados de cálculo (secção C) foram confirmados por execução real, não apenas por leitura.

---

## A. Resumo executivo

**Estado geral**: o projeto está bem acima da média para um MVP de software de engenharia — arquitetura limpa (UI / modelos / motores / catálogos / reports separados), Pydantic v2 em todo o domínio, 48 testes a passar com 90% de cobertura de linhas, assumptions declaradas com IDs, disclaimers presentes no PDF. A fundação é boa e **não justifica reescrita** — justifica correção dirigida.

**Mas não está pronto para uso real de engenharia, nem mesmo piloto, no estado atual.** A auditoria confirmou por execução dois defeitos de cálculo que produzem resultados errados ou enganosos:

1. **A ação sísmica nunca entra no dimensionamento.** Todos os motores de suporte escolhem a combinação governante por `max(V_z)` — que é sempre a ULS fundamental (1.35G+1.5Q > 1.0G) — e depois leem a força horizontal `V_y` *dessa* combinação, que é 0. Resultado verificado: pedestal no Chile, zona sísmica 3 (ag/g = 0.40), `M_sismo = 0.00 kNm`. O relatório lista a combinação sísmica na tabela, dando a impressão de que foi considerada. **Isto pode induzir um engenheiro a confiar num suporte não verificado ao sismo.**

2. **A tabela de combinações mistura grandezas incomparáveis.** Os motores transformam a combinação governante em esforços por elemento (ex.: pedestal → V por patim = P/4) mas deixam as restantes combinações com valores totais. No caso verificado, a tabela mostra `ULS_fundamental Vz=1.89 kN` ao lado de `SLS Vz=5.18 kN` — a SLS aparece maior que a ULS, e o campo "Carga de cálculo (ULS)" do PDF mostra 1.89 kN quando a carga ULS total é 7.57 kN.

3. **`REQUIRES_SPECIALIST` não pesa no veredicto.** Um ventilador de 540 kg em zona sísmica alta recebe banner **verde "PASSA - CONSERVADOR"** na UI e no PDF, com a exigência de especialista relegada para a tab "Avisos" e para a secção 9 do PDF. O `assess_result()` ignora completamente `classification_level`.

4. **Sete inputs recolhidos na UI nunca são usados em cálculo nenhum** (excentricidade, altura do CG, classe de exposição, comprimento dos varões do hanger, espessura de chapa indicada pelo utilizador, tipo de fixação do ventilador, peso vazio). O utilizador ajusta-os acreditando que afetam o resultado.

**Veredicto**: adequado para **demonstração interna e desenvolvimento**. **Não usar em projeto real** (nem como "estimate" entregável) antes da Fase 1 do plano abaixo. Com as Fases 1–2 executadas e validação independente dos motores, torna-se um candidato sério a piloto interno controlado.

**Principais oportunidades**: a estrutura `ReportContext` + assumptions com IDs + enums de classificação já existentes são exatamente a fundação certa para um produto profissional com rastreabilidade; falta ligá-los de forma coerente (muitos estados — `PRELIMINARY`, `DATASET_MISSING`, `OUT_OF_SCOPE`, `WARNING`, `dataset_provenance` — existem nos modelos mas nunca são produzidos). O caminho para o Orzio SaaS (export JSON do `ReportContext`) é curto.

---

## B. Mapa da arquitetura atual

```
app.py                          ── entrada Streamlit; injeta src/ no sys.path; chama main()
Start SFSC.bat                  ── conveniência Windows (porta 8502)

src/sfsc/
├── enums.py                    ── SupportType, Country, StructuralCode, CheckerStatus, ClassificationLevel…
├── models.py                   ── Pydantic v2: FanUnit, FanSupportInput, SteelSection, LoadCombination,
│                                  *Result, ReportContext, WarningItem, CitationItem, BatchRowResult
├── validators.py               ── validate_fan_support_input() (peso ≤2000 kg, campos condicionais)
├── exceptions.py               ── hierarquia SFSCBaseError (OutOfScope, DatasetMissing, …)
├── units.py                    ── conversões + constantes (g=9.80665, E aço)
├── assessment.py               ── assess_result(): headline PASSA/LIMITE/NÃO PASSA + métricas %
├── config.py                   ── loader YAML com lru_cache; raiz = sys._MEIPASS ou repo root
├── catalogs/
│   ├── steel_section_catalog.py── carrega data/catalogs/*.yaml → SteelSection ordenado por peso
│   ├── steel_grade_catalog.py  ── steel_grades.yaml → SteelGradeSpec (fy, fu, γM)
│   └── seismic_catalog.py      ── seismic_zones.yaml → ag/g por país/zona (fallback silencioso)
├── engines/
│   ├── selector.py             ── run_full_calculation(): valida → código/sismo → cargas → motor de
│   │                              suporte → secção → base plate → ancoragens → ligações → checker →
│   │                              ReportContext; context_for_section_choice() (re-corre em VERIFY)
│   ├── loads.py                ── G (+15% suporte), Q=(φ−1)·G, E_h=ag/g·G; 3 combinações (γ por grupo EC/BR/CL)
│   ├── support_types/*.py      ── 6 motores; cada um devolve (combo transformado, Lcr_y, Lcr_z)
│   ├── section_verifier.py     ── EC3: corte 6.2.6, flexão 6.2.5, LTB 6.3.2, compressão 6.2.4/6.3.1;
│   │                              find_passing_sections / auto_select_section (η ≤ 0.90)
│   ├── base_plate.py           ── bearing, flexão da chapa, parafusos, furação, cone/pull-out/pry-out, solda
│   ├── anchor.py               ── varões 8.8: tração/corte/interação^1.5; hef = 8d
│   ├── metal_connections.py    ── ligação simplificada por tipo de suporte (parafusos, solda, stiffener)
│   └── checker.py              ── run_checker() (prioridade de status) + classify() (>500 kg, ag>0.15, COMBINED+molas)
├── reports/
│   ├── memorial_pdf.py         ── ReportLab; 12 secções + resumo executivo + footer disclaimer
│   └── exports.py              ── Excel (6 folhas) + CSV de 1 linha
└── ui/streamlit_app.py         ── 585 linhas: sidebar de inputs, cálculo em session_state,
                                   seletor de perfil ativo, 7 tabs, 3 botões de export

data/catalogs/*.yaml            ── HEA/HEB/IPE/UPN/RHS (~15-17 perfis cada; sem fonte/versão)
*.yaml (raiz)                   ── assumptions (12 IDs), seismic_zones (8 países), standards (14), steel_grades (6)
tests/ (48 testes)              ── catálogos, loads, secção, modelos, assessment, E2E (12 casos), UI (AppTest), launcher
build_desktop/                  ── launcher.py (subprocess Streamlit + pywebview), sfsc.spec (caminho absoluto local),
                                   publish_release.ps1 (token via git credential fill)
```

**Avaliação da separação**: boa no geral. Problemas estruturais: (1) os motores de suporte **mutam a semântica** de `LoadCombination` (de "combinação total" para "esforço por elemento") sem mudar de tipo — origem do achado C-02; (2) regras normativas (γ, curvas de encurvadura, β_w) estão hardcoded nos motores em vez de derivar de `standards_registry.yaml`; (3) a UI conhece demasiado da orquestração (`context_for_section_choice`); (4) `selector.py` acumula citações/assunções manualmente, com duplicação e perda (dedupe por `standard_id`).

**Base para Orzio SaaS**: razoável — `ReportContext` é serializável (Pydantic), `BatchRowResult` já existe. Falta: IDs estáveis de cálculo/versão, separação UI↔serviço (a função `run_full_calculation(input) → ReportContext` já é a API natural).

---

## C. Achados críticos

Legenda de severidade: **CRITICAL** = pode produzir cálculo/relatório errado ou interpretação perigosa; **HIGH** = risco real de erro ou de responsabilidade; **MEDIUM** = qualidade/robustez; **LOW** = cosmético/manutenção.

### CRITICAL

| ID | Achado | Evidência | Consequência |
|---|---|---|---|
| **C-01** | **Ação sísmica nunca entra no dimensionamento.** Todos os 6 motores fazem `governing = max(combinations, key=abs(V_z))` → sempre `ULS_fundamental`; depois leem `governing.V_y_kN` (=0). A combinação `ULS_seismic` é criada mas nunca verificada. | `support_types/*.py`; verificado em runtime: Chile zona 3 (ag/g=0.40) → `M_sismo=0.00` | Suporte declarado PASS sem qualquer verificação sísmica, com a combinação sísmica impressa no relatório como se considerada. Cálculo errado + relatório enganoso. |
| **C-02** | **Tabela de combinações mistura totais e por-elemento.** O motor transforma só a combinação governante (ex.: pedestal V→P/4); as outras ficam com valores totais. `design_load_kN = governing.V_z` apresenta o esforço por elemento como "Carga de cálculo (ULS)". | Runtime: tabela mostra ULS Vz=1.89 < SLS Vz=5.18 para o mesmo caso; PDF secção 4 | Relatório tecnicamente incoerente; revisor externo desacredita o documento; risco de uso do valor errado a jusante. |
| **C-03** | **`REQUIRES_SPECIALIST` não pesa no veredicto.** `classify()` devolve REQUIRES_SPECIALIST (>500 kg, ag>0.15, COMBINED+molas) mas `assess_result()` ignora `classification_level`; status global continua PASS → banner verde "PASSA - CONSERVADOR" na UI, no resumo executivo do PDF e no Excel. | `assessment.py:65-123`; runtime: status=PASS + class=REQUIRES_SPECIALIST | Engenheiro júnior/cliente lê "PASSA" e entrega; exigência de especialista fica num aviso secundário. Risco profissional/legal direto. |
| **C-04** | **Sete inputs recolhidos mas nunca usados em cálculo**: `eccentricity_mm`, `centre_of_gravity_height_mm`, `exposure_class`, `hanger_rod_length_mm`, `base_plate_thickness_mm` (espessura indicada pelo utilizador é ignorada — dimensiona sempre auto), `fan_connection_type`, `weight_kg` (peso vazio). | `grep` nos engines: zero ocorrências fora de loads/checker | O utilizador altera a excentricidade ou o CG e o resultado não muda — confiança indevida em parâmetros "considerados". A altura do CG é precisamente o que gera derrube sísmico (ligado a C-01). |
| **C-05** | **HANGER: os varões roscados nunca são verificados como varões.** `calc_hanger` só verifica a viga; `calculate_anchor` corre sempre e assume **ancoragem embebida em betão** (hef, cone, fbd) mesmo quando o suporte está pendurado numa viga metálica. O PDF reporta "Profundidade de embebimento 100 mm" para um hanger. | `anchor.py:92-107`; `selector.py:218-231` | Verificação fisicamente errada para o tipo de suporte; o componente mais crítico do hanger (varão em tração + flambagem ao sismo) fica sem verificação dedicada. |
| **C-06** | **Modelo de ancoragens com direção de esforços errada.** `N_Ed = abs(V_z)` — a carga gravítica (compressão na base de um pedestal) é tratada como tração nos chumbadores; a tração real (derrube por sismo × altura do CG) nunca é calculada (C-01/C-04). Além disso recebe o combo transformado: para pedestal as ancoragens são dimensionadas para P/4 em vez da reação real por ancoragem. | `anchor.py:34-35`; `selector.py:219` | Resultado simultaneamente sobre-conservativo (gravidade como tração) e sub-conservativo (uplift sísmico ignorado) — i.e., não confiável em nenhuma direção. |
| **C-07** | **Política de escopo de peso incoerente**: README/UI "35–600 kg"; `validate` bloqueia só >2000 kg; `classify` exige especialista >500 kg; **não existe mínimo** (1 kg passa). | `validators.py:17`, `checker.py:43`, `streamlit_app.py:48`, README:50 | Casos fora da faixa anunciada são processados sem bloqueio nem aviso coerente. |
| **C-08** | **`pip install -e .` está quebrado**: `build-backend = "setuptools.backends.legacy:build"` não existe (correto: `setuptools.build_meta`). O README instrui `pip install -e .[dev]`. | Verificado: `ModuleNotFoundError: No module named 'setuptools.backends'` | Onboarding/CI impossíveis pela via documentada; falha de build. |

### HIGH

| ID | Achado | Evidência |
|---|---|---|
| H-01 | A secção é verificada **apenas contra a combinação governante** escolhida por max V_z — não há envelope por verificação (a sísmica poderia governar LTB/corte mesmo com V_z menor). | `section_verifier.find_passing_sections`, motores |
| H-02 | Peso próprio do suporte fixo em 15% nunca é confrontado com o perfil realmente escolhido (HEB pesado em vão longo pode exceder 15%); não iterativo nem parametrizável. | `loads.py:42` |
| H-03 | **RHS e UPN verificados com fórmulas de perfil I**: área de corte = alma única, I_w de perfil I, curva LTB "b" — sem ramo por família. Para RHS o corte fica subestimado ~2× (conservativo) e o LTB não tem significado; para UPN ignora-se a torção por excentricidade do centro de corte. | `section_verifier.py:40-105` |
| H-04 | **Excel e CSV não contêm warnings, limitations, assumptions nem disclaimer**; Excel não tem folha "Avisos"; CSV não tem campos de warnings/limitations; export sempre disponível mesmo com FAIL/REQUIRES_SPECIALIST, sem marca de água nem bloqueio. | `exports.py` (folhas: Resumo, Combinações, Secção, Mesa, Ancoragens, Ligações) |
| H-05 | `st.exception(err)` mostra o traceback completo ao utilizador final; sem modo debug separado; exceções de domínio (OutOfScope) e bugs aparecem da mesma forma. | `streamlit_app.py:237,565` |
| H-06 | Dedupe de citações por `standard_id` (`{c.standard_id: c}`) **perde cláusulas**: as duas citações EN1993-1-8 (base plate cl. 6.2.5 e ligações cl. 3+4+6) colapsam numa só. | `selector.py:302` |
| H-07 | **Sem rastreabilidade de versão**: outputs sem versão do software (hardcoded "SFSC v1.0" vs pyproject 1.0.0), sem versão/hash/data dos catálogos; `ReportContext.dataset_provenance` existe e **nunca é preenchido**; `prepared_by` default "SFSC v1.0" (relatório "preparado por software", sem campo de engenheiro responsável na UI). | `models.py:340`, `selector.py`, UI |
| H-08 | Estados prometidos nunca produzidos: `CheckerStatus.DATASET_MISSING/OUT_OF_SCOPE/WARNING` e `ClassificationLevel.PRELIMINARY` não são atribuídos em nenhum ponto — as situações correspondentes viram exceções não tratadas ou passam despercebidas. | grep nos engines |
| H-09 | Validações ausentes: `operating_weight_kg ≥ weight_kg` não verificado; sem limites para vão (ex.: 100 m passa), altura, excentricidade, CG, nº unidades × peso, footprint vs vão; sem validação específica por tipo de suporte além de CANTILEVER_1. | `validators.py`, `models.py` |
| H-10 | `get_seismic_factor` com zona inválida cai **silenciosamente** para a zona default — sem warning. | `seismic_catalog.py:40-42` |
| H-11 | COMBINED: split 70/30 mesa/pendurais é arbitrário, sem assumption ID dedicada; a força nos pendurais (`F_hanger_kN`) é calculada mas **os tirantes nunca são verificados**. | `support_types/combined.py` |
| H-12 | Base plate: usa `fan_units[0]` apenas (multi-unidade ignorado); bearing assume P/área total uniforme; parafusos verificados só ao corte vertical; crescimento L/B em passos de 25 mm acoplado nos dois eixos. | `base_plate.py:53-64` |
| H-13 | `sfsc.spec` contém caminho absoluto da máquina do autor (`C:/Users/Paulo Costa/...`); sem `version_file`; build irreproduzível noutra máquina sem edição manual. | `build_desktop/sfsc.spec:23-25` |
| H-14 | Sem CI (não existe `.github/`), sem lint/format/typecheck configurados, `requirements.txt` duplica o pyproject e mistura dev com runtime, sem pins/lockfile. | raiz do repo |

### MEDIUM

| ID | Achado |
|---|---|
| M-01 | `psi_0` declarado nos γ e nunca usado (não há segunda ação variável — ou se remove, ou se documenta porquê). |
| M-02 | `_load_yaml` devolve `{}` para ficheiro inexistente — catálogo ausente vira lista vazia silenciosa em vez de `DatasetMissingError`. Sem validação de schema dos YAML (ag_g negativo, campo em falta = KeyError em runtime). |
| M-03 | Modo VERIFY existe no modelo e no motor mas **não está exposto na UI** (`operation_mode` fixo em DIMENSION, linha 97) — README anuncia "sizing and verification workflows from the same interface". |
| M-04 | `context_for_section_choice` re-corre em VERIFY mas repõe o input original (DIMENSION) no contexto — o relatório resulta de um modo diferente do que declara; warnings/citações do segundo run substituem os do primeiro. |
| M-05 | UI monolítica (585 linhas, `main()` única); sem ajuda contextual na maioria dos campos; warnings críticos só na tab 6 (deviam aparecer acima das tabs); fator dinâmico não varia com `FanType`. |
| M-06 | `streamlit_app.py:7` insere a raiz do repo no `sys.path` (path errado para `import sfsc`; só funciona porque `app.py` já inseriu `src/`). |
| M-07 | Cobertura de testes sem casos negativos importantes: validators 65% (limite 2000 kg sem teste), anchor 63% (ramo FAIL sem teste), exceptions 37%; **nenhum teste de regressão numérica com valores esperados calculados à mão**; nenhum teste de consistência PDF↔Excel↔CSV; nenhum teste de YAML inválido; nenhum teste que detetasse C-01 (sismo). |
| M-08 | Catálogos sem proveniência (fonte dos perfis não declarada — presumivelmente ArcelorMittal/EN, mas não escrito), sem data/versão/hash; perfis L e C existem no enum mas não há catálogo. |
| M-09 | Launcher desktop: `private_mode=False` partilha perfil/cookies do WebView; logs de debug vão para `%TEMP%` sem rotação; `TargetCommitish="master"` default no release script; token via `git credential fill` (aceitável local, mas sem scope-check). |
| M-10 | LTB usa `Lcr_y` como comprimento de encurvadura lateral sem travamentos parametrizáveis; curva b fixa (αLT=0.34) independente de h/b; C1=1 implícito. Conservativo na maioria, mas não declarado. |

### LOW

L-01 `app.py`/UI com hacks de `sys.path` duplicados · L-02 `Start SFSC.bat` sem verificação do venv · L-03 `BatchRowResult` definido e nunca usado (modo batch inexistente) · L-04 acentuação inconsistente ("Espacamento") nos warnings · L-05 ícones/PNG soltos na raiz (`icone.png`).

---

## D. Melhorias prioritárias

| Prioridade | Área | Problema | Impacto | Solução proposta | Ficheiros prováveis | Testes necessários |
|---|---|---|---|---|---|---|
| P0 | Motor de cargas | C-01 sismo nunca verificado | Cálculo errado | Verificar a secção contra **todas** as combinações (envelope); cada motor transforma todas as combinações, não só a de max V_z; governante = a de maior η resultante | `support_types/*.py`, `section_verifier.py`, `selector.py` | Teste: Chile z3 vs Irlanda → η e/ou perfil têm de diferir; teste de envelope por verificação |
| P0 | Modelos/Reports | C-02 combinações incomparáveis | Relatório enganoso | Separar `LoadCombination` (ações totais) de `MemberForces` (esforços por elemento); tabela do relatório mostra ambas com legenda; `design_load_kN` renomeado/duplicado (total ULS + esforço no elemento) | `models.py`, `support_types/*`, `memorial_pdf.py`, `exports.py`, UI | Teste de monotonia ULS ≥ SLS na tabela; golden values |
| P0 | Assessment/UI/Reports | C-03 REQUIRES_SPECIALIST invisível | Risco legal | `assess_result` recebe classificação: se REQUIRES_SPECIALIST → headline própria âmbar/roxa ("REQUER ESPECIALISTA"), nunca verde; banner no topo da UI; faixa no PDF; coluna destacada no Excel/CSV | `assessment.py`, `streamlit_app.py`, `memorial_pdf.py`, `exports.py` | Teste: 540 kg → headline ≠ "PASSA - CONSERVADOR" em todos os outputs |
| P0 | Validação/Motores | C-04 inputs ignorados | Falsa confiança | Para cada input: usá-lo (excentricidade → M_z/M adicional; CG → derrube sísmico; rod_length → verificação dos varões) **ou** removê-lo da UI **ou** marcá-lo "apenas informativo" no label e no PDF | `validators.py`, motores, UI | Teste por input: variação do input ⇒ variação do output (ou label informativo) |
| P0 | Anchor/Hanger | C-05/C-06 modelo de ancoragem errado | Cálculo errado | Ramificar por tipo de suporte: hanger → verificação de varão (tração + interação, sem hef/betão); apoiados no piso → tração de ancoragem = uplift por derrube (E_h × h_CG / braço) com compressão gravítica a favor; passar reação real por ancoragem | `anchor.py`, `selector.py`, novo `engines/rods.py` | Casos manuais: pedestal com sismo alto → tração>0; hanger → sem campos de betão no PDF |
| P0 | Escopo de peso | C-07 três limites contraditórios | Interpretação errada | Política única (ver §4.3 abaixo) aplicada em validator + classify + UI + README + reports | `validators.py`, `checker.py`, UI, README, reports | Testes de fronteira: 34.9 / 35 / 500 / 600 / 600.1 / 1000 / 1000.1 kg |
| P0 | Packaging | C-08 build-backend inválido | Falha de build | `build-backend = "setuptools.build_meta"` | `pyproject.toml` | CI: `pip install -e .[dev]` num job |
| P1 | Section verifier | H-03 RHS/UPN com fórmulas de I | Cálculo impreciso | Ramo por família: RHS (Av = 2·h·t, sem LTB clássico), UPN (aviso de torção + restrição); ou restringir famílias a I até implementar | `section_verifier.py` | Teste por família com valores de referência |
| P1 | Reports | H-04 Excel/CSV sem avisos/disclaimer | Risco legal | Folha "Avisos & Pressupostos" no Excel; colunas `warnings_count`, `critical_warnings`, `classification`, `disclaimer` no CSV; linha de disclaimer em todas as folhas; export com confirmação/marca quando FAIL ou REQUIRES_SPECIALIST | `exports.py`, UI | Teste de presença de campos nos 3 formatos + consistência entre eles |
| P1 | Rastreabilidade | H-07 sem versão/proveniência | Baixa rastreabilidade | `__version__` única (lida do pyproject); hash SHA-256 + data de cada YAML em `dataset_provenance`; impresso no PDF/Excel/CSV; campo "Eng. responsável" na UI obrigatório p/ export | `config.py`, `selector.py`, reports, UI | Teste: provenance presente e estável |
| P1 | Erros | H-05/H-08 traceback exposto, estados mortos | Interpretação errada | Catch tipado na UI: `SFSCBaseError` → mensagem amigável + código; bug genérico → "erro interno" + log; `SFSC_DEBUG=1` mostra traceback; mapear `DatasetMissingError`→DATASET_MISSING, `OutOfScopeError`→OUT_OF_SCOPE no resultado em vez de explodir | `streamlit_app.py`, `selector.py`, `checker.py` | Testes de cada exceção → status/ecrã correto |
| P1 | Validação | H-09 limites permissivos | Cálculo fora do domínio | Tabela de limites por campo (ver §4.4); validação por tipo de suporte; `operating ≥ empty` | `validators.py`, `models.py` | Teste paramétrico por limite |
| P2 | Qualidade | H-14 sem CI/lint | Regressões | Ruff (lint+format), mypy gradual, pre-commit, GitHub Actions (pytest+cov mínimo 85%), requirements separados | novos configs | CI a verde |
| P2 | UI | M-03/M-05 VERIFY ausente, UI monolítica | UX/produto | Expor modo VERIFY; partir UI em `ui/components/`; avisos críticos acima das tabs; help por campo | `ui/` | AppTest por componente |
| P2 | Catálogos | M-02/M-08 sem schema/proveniência | Robustez | Schema Pydantic para cada YAML com `meta:` (source, edition, updated, version); falha explícita | `config.py`, `catalogs/`, YAMLs | Testes de YAML inválido |
| P3 | Desktop | H-13/M-09 build irreproduzível | Distribuição | Remover caminho absoluto; version_file gerado; checklist de release | `build_desktop/` | Smoke test do launcher |

### Política de escopo de peso proposta (resolve C-07)

| Faixa (peso total em operação) | Comportamento | Onde |
|---|---|---|
| < 35 kg | **Permitido com warning** "abaixo da faixa validada — verificar fixações leves" + classificação mínima PRELIMINARY | validator (warning), classify, UI, reports |
| 35 – 500 kg | Faixa normal → ENGINEERING_ESTIMATE | — |
| 500 – 600 kg | **REQUIRES_SPECIALIST** (mantém comportamento atual de classify) | classify + destaque C-03 |
| 600 – 1000 kg | **Permitido apenas com confirmação explícita na UI** ("fora da faixa do produto"), classificação REQUIRES_SPECIALIST, marca de água no PDF | validator (warning forte), UI gate, reports |
| > 1000 kg | **Bloqueado** — `OutOfScopeError` (baixar o limite atual de 2000) | validator |

Racional: 600 kg é a promessa do produto; 1000 kg dá margem para casos limítrofes documentados; 2000 kg não tem justificação escrita em lado nenhum do repo. Aplicar a mesma constante (`WEIGHT_POLICY` em módulo único, ex. `sfsc/policy.py`) em todos os pontos para nunca mais divergir.

---

## E. Plano de implementação por fases

Cada fase é entregável e testável de forma independente; nenhuma remove funcionalidade sem substituto.

### Fase 1 — Hardening técnico e segurança de interpretação *(antes de qualquer uso real)*
1. **F1.1** Corrigir build-backend (C-08) — 1 linha, desbloqueia tudo o resto.
2. **F1.2** Envelope de combinações + separação ações/esforços (C-01, C-02, H-01).
3. **F1.3** Ancoragens/varões por tipo de suporte (C-05, C-06).
4. **F1.4** `REQUIRES_SPECIALIST` dominante em UI/PDF/Excel/CSV (C-03); avisos críticos acima das tabs.
5. **F1.5** Política de peso unificada (C-07) em `sfsc/policy.py`.
6. **F1.6** Inputs ignorados: usar, remover ou rotular (C-04) — no mínimo: CG no derrube sísmico (junta com F1.3), excentricidade no momento, rod_length na verificação de varões; `base_plate_thickness_mm` respeitado em modo verificação de chapa; `exposure_class` → warning de corrosão/recomendação de proteção.
7. **F1.7** Tratamento de erros na UI sem traceback (H-05) + estados DATASET_MISSING/OUT_OF_SCOPE reais (H-08).
8. **F1.8** Validações de limites (H-09) e fallback sísmico com warning (H-10).
9. **F1.9** Wording: todos os módulos simplificados (base plate, solda, ligações, ancoragens, sismo) marcados "MODELO SIMPLIFICADO — estimativa" no resultado e nos 3 outputs; sismo classificado `preliminary`.

### Fase 2 — Qualidade de código e testes
1. **F2.1** CI GitHub Actions: `pip install -e .[dev]`, `pytest --cov` (gate 85%), Ruff check+format. 
2. **F2.2** Separar `requirements.txt` (runtime, com pins) / `requirements-dev.txt` / `requirements-build.txt`; pyproject como fonte. 
3. **F2.3** Ruff + Ruff-format + pre-commit; mypy em modo gradual (começar por `engines/` e `models.py`).
4. **F2.4** Testes prioritários (ver matriz §4.12): regressão numérica com valores manuais (1 caso por tipo de suporte × 2 países), fronteiras de peso, exceções, YAML inválido, consistência PDF↔Excel↔CSV, ramo FAIL do anchor, validators completos.
5. **F2.5** `validation_cases/` (ver §5.4) com runner pytest.

### Fase 3 — Reports e produto
1. **F3.1** Provenance + versões em todos os outputs (H-07); folha Avisos no Excel; campos no CSV (H-04); dedupe de citações por (standard, clause) (H-06).
2. **F3.2** PDF premium: capa, resumo executivo melhorado, memória de fórmulas por verificação (valores intermédios: Av, Vpl_Rd, Mcr, χ_LT…), watermark "PRELIMINAR"/"NÃO APROVADO" quando aplicável, bloco de assinatura/revisão.
3. **F3.3** Modo VERIFY na UI (M-03) + correção do `context_for_section_choice` (M-04).
4. **F3.4** Decomposição da UI em componentes (`ui/components/sidebar_*.py`, `results_*.py`) sem mudar identidade visual.
5. **F3.5** Modo batch (CSV/Excel in → tabela de resultados + relatórios individuais + consolidado), reutilizando `BatchRowResult`.

### Fase 4 — Desktop release e distribuição
1. **F4.1** `sfsc.spec` portátil (sem caminho absoluto; descoberta via `site`/`importlib`), `version_file` gerado do pyproject.
2. **F4.2** Launcher: shutdown limpo, log com rotação, porta documentada, `private_mode=True` (avaliar impacto em downloads).
3. **F4.3** Release: changelog, checklist (secção G), verificação de tamanho, instruções de falso positivo de antivírus.

### Fase 5 — Integração futura com Orzio
1. **F5.1** Export JSON canónico do `ReportContext` (`ctx.model_dump_json()`) com envelope `{schema_version, calc_id (uuid), project_id, support_id, software_version, dataset_provenance}`.
2. **F5.2** Quantidades: kg de aço (perfil × comprimento + chapas), nº/Ø ancoragens, volume de solda — novo `engines/quantities.py`, exposto no JSON/Excel para orçamentação.
3. **F5.3** Interface de serviço: `sfsc.api.run(input_dict) → report_dict` pura (sem Streamlit), pronta para FastAPI futura; testes de contrato do schema.

---

## F. Prompts de implementação por fase

### Prompt — Fase 1

```text
Contexto: repositório orzio-fan-support-calc (SFSC), software de apoio a cálculo estrutural.
Existe auditoria em docs/AUDITORIA_TECNICA_2026-06.md — lê primeiro as secções C e E (Fase 1).

Objetivo: eliminar os 8 achados CRITICAL (C-01..C-08) sem remover funcionalidades.

Escopo permitido: src/sfsc/** , tests/** , pyproject.toml, README.md. NÃO tocar em build_desktop/ nem reports além do estritamente necessário para C-02/C-03.

Tarefas, por ordem:
1. pyproject.toml: build-backend = "setuptools.build_meta". Verifica com pip install -e .[dev].
2. Cria src/sfsc/policy.py com a política de peso (35/500/600/1000 kg) da auditoria §D; usa-a em validators.py, checker.classify, UI e README.
3. Refatora motores de suporte para transformarem TODAS as combinações em esforços por elemento (novo modelo MemberForces ou campo explícito em LoadCombination com flag member_level: bool). A verificação de secção corre para todas as combinações; governante = maior η. design_load_kN passa a reportar a ULS total E o esforço no elemento separadamente.
4. anchor.py: ramo por tipo de suporte. HANGER → verificação de varão roscado (tração + corte, sem hef/betão; usa hanger_rod_length_mm para esbelteza se em compressão sísmica). Suportes no piso → tração por derrube: T = max(0, E_h·h_cg/braço − G/n); usa centre_of_gravity_height_mm.
5. assessment.py: assess_result(result) considera classification_level — REQUIRES_SPECIALIST nunca produz headline verde; nova headline "REQUER ESPECIALISTA". Propaga a UI (banner topo, antes das tabs), PDF (resumo executivo) e Excel/CSV.
6. eccentricity_mm entra no momento (M += P·e); exposure_class gera warning de proteção; base_plate_thickness_mm fornecido → modo verificação da chapa (não auto). Inputs que continuem informativos ganham "(informativo)" no label da UI e nota no PDF.
7. UI: substituir st.exception por tratamento tipado (SFSCBaseError → st.error com código; resto → mensagem genérica + logging; traceback só com SFSC_DEBUG=1).
8. selector.py: DatasetMissingError/OutOfScopeError viram status no resultado quando recuperáveis, exceção clara quando não.

Regras de segurança: não alterar valores de catálogo; não baixar nenhum coeficiente parcial; qualquer mudança de resultado numérico tem de ficar coberta por teste com valor esperado calculado à mão no docstring.

Testes obrigatórios: fronteiras de peso (34.9/35/500/600/600.1/1000/1000.1); Chile z3 vs Irlanda produz dimensionamento diferente; pedestal com sismo → tração de ancoragem > 0; hanger → resultado sem campos de betão; 540 kg → headline "REQUER ESPECIALISTA" em UI/PDF/Excel/CSV; cada exceção → ecrã/status correto.

Validação: python -m pytest -q (todos a passar) e pip install -e .[dev] limpo.
Resultado esperado: 48+ testes verdes, novos testes listados acima, README §scope atualizado.
Commit: "fix: corrige envelope sísmico, modelo de ancoragens, política de escopo e visibilidade de REQUIRES_SPECIALIST (auditoria Fase 1)"
```

### Prompt — Fase 2

```text
Contexto: SFSC pós-Fase 1. Lê docs/AUDITORIA_TECNICA_2026-06.md §E Fase 2 e §C (H-14, M-07).

Objetivo: infraestrutura de qualidade + testes de regressão numérica.

Escopo permitido: .github/workflows/**, pyproject.toml, requirements*.txt, .pre-commit-config.yaml, tests/**, validation_cases/**. Sem alterações de lógica de cálculo (só correções que os novos testes exponham, cada uma justificada no commit).

Tarefas:
1. Migrar config de deps: pyproject como fonte; requirements.txt (runtime, pins ~=), requirements-dev.txt, requirements-build.txt (pyinstaller, pywebview).
2. Ruff (lint+format, target py310) + pre-commit; aplicar formatação num commit isolado.
3. mypy gradual: strict em sfsc/models.py, sfsc/engines/**; ignore no resto com TODO.
4. GitHub Actions: job único ubuntu — pip install -e .[dev], ruff check, pytest --cov=src/sfsc --cov-fail-under=85.
5. validation_cases/: 6 casos (1 por tipo de suporte), cada um com input.json, expected.json (η, perfil, status, tolerância ±2%), memoria.md com cálculo manual; runner tests/test_validation_cases.py.
6. Testes novos: ramo FAIL de anchor.py; validators a 100%; YAML inválido (ag_g em falta, secção sem W_pl) → erro explícito; consistência PDF/Excel/CSV (mesmos status, classificação, η governante nos 3).

Validação: CI verde no PR; cobertura ≥85%.
Commit: "chore: CI, lint, typecheck e biblioteca de casos de validação (auditoria Fase 2)"
```

### Prompt — Fase 3

```text
Contexto: SFSC pós-Fase 2. Lê docs/AUDITORIA_TECNICA_2026-06.md §E Fase 3, achados H-04, H-06, H-07, M-03, M-04, M-05.

Objetivo: outputs profissionais e rastreáveis; UI componentizada com modo VERIFY.

Escopo: src/sfsc/reports/**, src/sfsc/ui/**, src/sfsc/config.py, src/sfsc/engines/selector.py, tests/**.

Tarefas:
1. Provenance: config.py calcula sha256+mtime de cada YAML; selector preenche dataset_provenance; __version__ lida do metadata do pacote; tudo impresso em PDF (rodapé+secção), Excel (folha Info) e CSV (colunas).
2. Excel: folha "Avisos e Pressupostos" (warnings com severidade, assumptions com descrição do assumptions.yaml, limitations). CSV: warnings_count, critical_warnings, classification, software_version, disclaimer.
3. PDF: capa (projeto, tag, revisão, eng. responsável), memória de fórmulas com valores intermédios (Av, Vpl_Rd, Mc_Rd, Mcr, χ_LT, f_jd, …), watermark diagonal "PRELIMINAR — NÃO APROVADO" quando status != PASS ou classificação REQUIRES_SPECIALIST, bloco assinatura/verificado por.
4. Dedupe de citações por (standard_id, clause) — não perder a segunda cláusula EN1993-1-8.
5. UI: campo obrigatório "Engenheiro responsável" antes de exportar; modo VERIFY exposto (radio Dimensionar/Verificar com família+designação); dividir streamlit_app.py em ui/components/ (sidebar_identification, sidebar_fan, sidebar_geometry, results_tabs, export_bar) mantendo visual.
6. Corrigir context_for_section_choice para registar no contexto que o perfil foi escolhido pelo utilizador (nota no PDF) e preservar warnings originais.

Testes: AppTest para modo VERIFY; presença de provenance nos 3 outputs; watermark quando FAIL; export bloqueado sem eng. responsável.
Validação: pytest -q; geração manual de 1 PDF de cada status para inspeção (anexar ao PR).
Commit: "feat: relatórios rastreáveis com provenance, modo VERIFY e UI componentizada (auditoria Fase 3)"
```

### Prompt — Fase 4

```text
Contexto: SFSC pós-Fase 3. Lê docs/AUDITORIA_TECNICA_2026-06.md §E Fase 4, achados H-13, M-09.

Objetivo: build desktop reprodutível e endurecido.

Escopo: build_desktop/**, pyproject.toml (scripts), docs/RELEASE_CHECKLIST.md.

Tarefas:
1. sfsc.spec: remover caminho absoluto; localizar site-packages via sysconfig/importlib; falhar com mensagem clara se streamlit não encontrado.
2. Gerar version_file Windows a partir da versão do pyproject (script build_desktop/make_version_file.py).
3. launcher.py: shutdown com terminate→wait→kill já existe — adicionar atexit, log com rotação (máx 1 MB), avaliar private_mode=True com teste manual de download (documentar a decisão no código).
4. publish_release.ps1: parametrizar branch (detetar default), nunca imprimir token, validar que o asset existe antes de criar release.
5. docs/RELEASE_CHECKLIST.md com a checklist da auditoria §G.

Regras: não alterar comportamento da app; testar pyinstaller em máquina/runner Windows antes de fechar.
Testes: test_desktop_launcher ampliado (porta ocupada → próxima; comando do servidor congelado vs dev).
Validação: pyinstaller build_desktop/sfsc.spec --noconfirm numa máquina limpa; smoke test do exe.
Commit: "build: spec portátil, version info e hardening do launcher (auditoria Fase 4)"
```

### Prompt — Fase 5

```text
Contexto: SFSC pós-Fase 4. Lê docs/AUDITORIA_TECNICA_2026-06.md §E Fase 5 e §5.3.

Objetivo: preparar integração Orzio — export JSON estruturado, quantidades e API interna pura.

Escopo: src/sfsc/api.py (novo), src/sfsc/engines/quantities.py (novo), src/sfsc/reports/export_json.py (novo), models.py (campos aditivos apenas), tests/**.

Tarefas:
1. export_json.py: envelope {schema_version: "1.0", calc_id: uuid4, created_at, software_version, dataset_provenance, input, result, assessment, warnings, citations, assumptions (expandidas do YAML), limitations}. Tudo via model_dump; sem campos novos obrigatórios (retrocompatível).
2. quantities.py: aço estrutural (kg = perfil×comprimento por tipo de suporte + chapas), ancoragens (n×Ø×hef), solda (mm de cordão×garganta). Marcar como "estimativa para orçamentação — não é lista de corte".
3. api.py: run_calculation(payload: dict) -> dict, sem dependência de Streamlit; validação de schema com erros estruturados {field, code, message}.
4. Botão "Download JSON" na UI ao lado dos outros exports.

Regras: nada de rede/upload nesta fase; schema documentado em docs/JSON_SCHEMA.md.
Testes: round-trip JSON (export → parse → mesmos valores); contrato do schema (chaves obrigatórias); quantidades com caso manual.
Validação: pytest -q.
Commit: "feat: export JSON estruturado, quantidades e API interna para integração Orzio (auditoria Fase 5)"
```

---

## G. Checklist final de release (desktop)

Antes de distribuir `SFSC.exe`:

- [ ] `pytest -q` — 100% a passar; cobertura ≥ 85%
- [ ] `pip install -e .[dev]` limpo numa venv nova (valida packaging)
- [ ] `ruff check` e `mypy` sem erros novos
- [ ] Casos de `validation_cases/` dentro das tolerâncias
- [ ] Build `pyinstaller build_desktop/sfsc.spec --noconfirm` em máquina limpa (sem caminho do dev)
- [ ] Versão do exe = versão do pyproject (Properties → Details no Windows)
- [ ] Smoke test: abre janela nativa, calcula caso hanger default, sem consola de erro
- [ ] PDF gerado: capa, provenance, disclaimer, watermark correta para FAIL e para REQUIRES_SPECIALIST
- [ ] Excel: todas as folhas, incl. Avisos & Pressupostos
- [ ] CSV: abre no Excel PT (separador/encoding), colunas de classificação e disclaimer presentes
- [ ] Validação manual de 2 casos por engenheiro (1 PASS, 1 REQUIRES_SPECIALIST) contra memória independente
- [ ] CHANGELOG.md atualizado; tag git criada
- [ ] LICENSE/disclaimer visível na UI (about) e no PORTABLE_README.txt
- [ ] Verificação VirusTotal do exe; instruções de falso positivo no release notes
- [ ] Tamanho do exe registado e comparado com release anterior (regressão de dependências)
- [ ] Instruções de uso e limitações de escopo (faixa de peso) no corpo do release

---

## Conclusões finais

**Corrigir antes de QUALQUER uso real (bloqueante):**
- C-01 (sismo ignorado), C-02 (combinações incoerentes), C-03 (REQUIRES_SPECIALIST invisível), C-05/C-06 (modelo de ancoragens), C-07 (escopo de peso), C-04 no mínimo na vertente "rotular inputs informativos". C-08 bloqueia o desenvolvimento, não o uso.

**Pode ficar para depois (não bloqueia piloto controlado pós-Fase 1):**
- Decomposição da UI, modo batch, PDF premium, modo VERIFY na UI, build desktop portátil, export JSON/Orzio, mypy completo.

**Deve ser validado por engenheiro estrutural independente (o software não se autovalida):**
- Os 6 modelos de suporte (em particular o split 70/30 do COMBINED e o M=5%·P·L do bracketed), o motor de cargas (combinações, fator dinâmico, 15% de peso próprio), o modelo sísmico simplificado (força estática equivalente sem espectro/fator de comportamento), as fórmulas de base plate, soldas e ligações simplificadas, e os dados dos catálogos (perfis, ag/g por zona, propriedades de aço). A biblioteca `validation_cases/` da Fase 2 é o veículo para essa validação — nenhum resultado deve ser tratado como mais do que estimativa de engenharia até esses casos estarem assinados por especialista.
