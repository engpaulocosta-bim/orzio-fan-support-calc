# Prompt para o Codex — SFSC solver v2 (grelha 2.5D, ELS, modal, perfil receptor, array de ventiladores)

> Este ficheiro é o briefing único para o agente de implementação (Codex). Foi
> preparado a partir de uma auditoria do código real em `master` (SFSC v1.2.0).
> Lê-o por inteiro antes de escrever qualquer código. Entrega **uma branch por
> fase, cada uma com o seu PR** — não juntes fases.

---

## 0. Contexto do produto e estado atual (lê primeiro)

SFSC (Steel Fan Support Calc) dimensiona suportes metálicos para ventiladores
industriais segundo EN 1993-1-1 / EN 1998-1 / EN 1990 (e NAs UK/FR, NBR, NCh).
Python 3.10, Pydantic v2, numpy ~1.26, Streamlit UI, relatório PDF (memorial),
i18n PT/EN/ES. Testes em `pytest`, organizados por fases (`tests/test_phaseNN_*.py`).

O que **já existe e funciona** (NÃO reescrever — estender):

- **Solver de pórtico 2D** em `src/sfsc/engines/global_frame.py`: montagem de
  rigidez direta, matriz de transformação, resolução `K·u=F`, extração de
  reações, deslocamentos nodais e esforços de extremidade de barra. Cada tipo de
  suporte é modelado como **uma viga/pórtico 2D representativo** no plano X-Z
  (3 GL por nó: ux, uz, ry).
- **Distribuição de cargas** em `src/sfsc/engines/load_surfaces.py`: superfícies
  (tramex/chapa), cargas manuais (ponto/linha/área), distribuição one-way por
  largura tributária, com tabela rastreável por viga.
- **Verificação de secção** em `src/sfsc/engines/section_verifier.py`, incluindo
  `verify_solver_member_envelope` que re-verifica a secção contra os esforços
  reais do solver (corte, flexão biaxial, LTB, encurvadura — EC3 6.2/6.3).
- **Verificador de ligações** em `src/sfsc/engines/connection_verifier.py`: base
  plate, transferência, grupo de ancoragens, usando reações reais do solver.
- **Camada de engenharia/estado** em `src/sfsc/engineering.py` que consolida
  estados (VERIFIED / SIMPLIFIED / NOT_VERIFIED / NOT_APPLICABLE / FAILED).
- Orquestrador: `src/sfsc/engines/selector.py::run_full_calculation`.

Limitações de fundo confirmadas pela auditoria (é isto que vais resolver):

1. **Sem grelha 2D.** A plataforma é N vigas paralelas tratadas como divisor
   aritmético (`load_per_beam = total / n_beams`), mas o modelo estrutural é
   **uma única viga**. Não há vigas transversais (travessas) nem nós de
   cruzamento. Ver `src/sfsc/engines/support_types/platform_frame_braced.py` e
   `global_frame.py::_build_platform_model`.
2. **Sem análise modal / frequência / ressonância.** Zero código de frequência.
   O fator dinâmico 1.5 (VDI 3840) é carga quase-estática — não-conservativo
   perto da ressonância.
3. **ELS desligado.** O solver calcula deslocamentos nodais (`uz_m`) mas
   `engineering.py` constrói o estado de serviceability com
   `displacement_results_available=False` **hardcoded** (~linha 900) e não há
   verificação de flecha contra limite.
4. **Perfil receptor não verificado.** `connection_verifier.py` não tem check do
   membro existente; `steel_fixation.py` mantém `receiving_member_checked=False`.
5. **Distribuição só one-way.** `LoadDistributionMethod` não tem `TWO_WAY`.
6. **Inconsistência solver-vs-fórmula na plataforma.** A seleção de secção usa
   esforços por viga (fórmula, carga `/n_beams`); o solver re-verifica aplicando
   carga **total** numa viga única. Dois níveis de carga a dimensionar o mesmo
   perfil (`selector.py:574-603`).

## Decisões de engenharia já tomadas pelo dono do produto (não voltar a perguntar)

- **Fase 1 — modelo:** grelha plana (**grillage 2.5D**), 3 GL por nó
  (uz vertical, rx, ry — rotações no plano da grelha). NÃO pórtico 3D completo.
- **Fase 2 — ELS:** limite de flecha default **L/250** (EN1990 Anexo A1 / EC3),
  **configurável** pelo utilizador (L/200, L/250, L/360, custom).
- **Fase 3 — ressonância:** regra de **faixa proibida**: a 1ª frequência própria
  da estrutura deve ficar **fora do intervalo [0.7, 1.3] × f_ventilador**
  (permite soluções acima OU abaixo). Aviso/estado se violado.
- **Entrega:** uma branch por fase + PR. Base sempre `master`.

## Regras de trabalho (obrigatórias)

- Trabalha sempre a partir de `master` atualizado. Uma branch por fase:
  `feat/fase1-grelha-2d`, `feat/fase2-els`, `feat/fase3-modal`,
  `feat/fase4-perfil-receptor`, `feat/fase5-array-ventiladores`. Abre um PR por
  fase contra `master` e **pára para revisão** antes de começar a fase seguinte.
- **Não partas nada do que já funciona.** Todos os testes existentes
  (`pytest -q`) têm de continuar verdes. Lint/format: `ruff check` e
  `ruff format` limpos; `mypy` sem novos erros (`python_version = 3.10`).
- Segue a convenção de fases nos testes: cria `tests/test_phase08_grillage.py`,
  `tests/test_phase09_serviceability.py`, etc. Cada fase entrega testes próprios.
- Mantém i18n: qualquer string visível ao utilizador entra em
  `src/sfsc/i18n/{pt,en,es}.json` por chave, nunca hardcoded.
- Mantém a rastreabilidade: novos módulos entram no `module_breakdown`, nas
  citações normativas e no hash de provenance, como os existentes.
- Preserva a classificação de segurança: nada passa a "VERIFIED" sem cálculo
  real por trás. Um módulo só fica verde quando há número e norma.
- Validação numérica: cada fase com cálculo estrutural novo traz **pelo menos um
  caso fechado verificável à mão** (ver "Critérios de validação" em cada fase).
- Commits em PT, mensagem clara. Termina cada commit com:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## FASE 1 — Grelha plana 2.5D (branch `feat/fase1-grelha-2d`)

**Objetivo:** substituir, para `PLATFORM_FRAME_BRACED`, a viga única por uma
grelha plana real com vigas longitudinais E transversais, distribuição two-way, e
esforços por barra vindos do solver. Resolve os pontos 1, 5 e 6 da auditoria.

**Modelo:**
- Plano da grelha = plano horizontal da plataforma. Nós numa malha
  longitudinal × transversal. **3 GL por nó:** deslocamento vertical `w` (fora do
  plano) e duas rotações `θx`, `θy`. Rigidez de barra de grelha = flexão (EI) +
  torção (GJ) — usar a matriz de rigidez de elemento de grelha (grid member),
  não a de pórtico plano. Reaproveita a infraestrutura de montagem/transformação
  de `global_frame.py` (mesma lógica de assembly, matriz de elemento diferente).
- Inputs novos no modelo (`models.py`): número de vigas longitudinais e
  transversais (já existe `platform_n_beams` — acrescentar `platform_n_crossbeams`
  ou equivalente), espaçamentos/posições, e posições de apoio (engaste, mãos-
  francesas, apoio em estrutura existente). Mantém retrocompatibilidade: se só
  houver vigas longitudinais, o resultado deve degradar para o comportamento
  atual sem regressão.
- Apoios coerentes com os casos reais: borda engastada (mãos-francesas) e/ou
  apoios verticais. Suporta o caso do utilizador: mesa de N vigas + travessas,
  engastada num lado + 2 mãos-francesas.

**Distribuição two-way (resolve ponto 5):**
- Adiciona `TWO_WAY` a `LoadDistributionMethod` (`enums.py`).
- Em `load_surfaces.py`, implementa distribuição two-way para painéis: regra
  prática por razão de aspeto (painel quase quadrado distribui ~igual nas duas
  direções; painel alongado tende a one-way na direção curta). Two-way deve ser
  o default quando existe grelha real (≥2 vigas em cada direção e razão de
  aspeto do painel entre ~0.5 e 2.0); caso contrário one-way.

**Consistência solver-vs-fórmula (resolve ponto 6):**
- O dimensionamento e a verificação final da secção passam a usar **os mesmos**
  esforços — os do solver de grelha. Elimina o caminho em que a fórmula divide
  por N mas o solver aplica o total numa viga. A divisão de carga passa a ser
  resultado físico do solver (rigidez relativa das vigas), não aritmética.

**Critérios de validação (obrigatórios):**
- Grelha de 1 vão com carga central conhecida reproduz, dentro de tolerância, a
  solução de viga biapoiada equivalente (`M = PL/4`, flecha `PL³/48EI`).
- Caso 2×2 de painéis simétricos com carga central distribui simetricamente
  (esforços iguais nas vigas simétricas) — testa o assembly e a simetria.
- Conservação de carga: soma das reações verticais = soma das cargas aplicadas.
- Todos os testes `test_phase03_global_frame.py` e `test_platform_model.py`
  existentes continuam verdes (ou são migrados explicitamente com justificação).

---

## FASE 2 — ELS / verificação de flecha (branch `feat/fase2-els`)

**Objetivo:** ligar os deslocamentos que o solver já calcula a uma verificação
real de flecha. Resolve o ponto 3. Vitória rápida, baixo risco — fazer logo a
seguir à Fase 1.

- Corrige a desconexão em `engineering.py`: o estado de serviceability deve usar
  os deslocamentos reais do solver, não `displacement_results_available=False`
  hardcoded. Quando o solver corre e há `uz_m`, o módulo ELS deve poder verificar.
- Verificação: flecha vertical máxima (combinação SLS característica) contra
  limite. **Default L/250**, configurável (L/200, L/250, L/360, custom) via input
  e UI. `L` = vão relevante da viga/painel governante.
- η_ELS = flecha / limite. Estado MARGINAL/FAIL conforme thresholds já usados no
  resto do sistema. Entra no `module_breakdown`, citações (EN1990 A1.4 / EC3) e
  i18n.
- O memorial PDF passa a mostrar a flecha calculada, o limite usado e o η.

**Validação:** viga biapoiada com carga central — flecha `PL³/48EI` confere com
fórmula fechada dentro de tolerância; η_ELS = (PL³/48EI)/(L/250) confere.

---

## FASE 3 — Análise modal / frequência / ressonância (branch `feat/fase3-modal`)

**Objetivo:** 1ª frequência própria da estrutura e verificação de afastamento à
excitação do ventilador. Resolve o ponto 2. Constrói sobre o K da grelha da Fase 1.

- Input novo: **frequência de excitação por ventilador** (Hz ou rpm → Hz). O
  utilizador inputa só a frequência de cada ventilador (já há `speed_rpm` no
  `FanUnit` — usar/derivar). Se houver várias unidades, considerar a banda de
  todas.
- Monta a **matriz de massa** `M` consistente (ou lumped, documentar a escolha)
  para o modelo de grelha. Massa = peso próprio da estrutura (já calculado) +
  massa dos ventiladores nos nós de aplicação.
- Resolve o problema de valores próprios generalizado `K·φ = ω²·M·φ`
  (`scipy.linalg.eigh` se aceitável adicionar scipy; caso contrário
  `numpy.linalg.eig` sobre `M⁻¹K` com cuidado numérico). 1ª frequência
  `f1 = ω1/(2π)`.
- **Verificação de ressonância (regra escolhida):** a estrutura passa se
  `f1` ficar **fora de [0.7, 1.3] × f_excitação** para todas as frequências de
  excitação. Se cair dentro da faixa proibida → estado FAIL/REQUIRES_SPECIALIST
  com mensagem clara (i18n) e citação (VDI 3840 / boas práticas de equipamento
  rotativo). Permite explicitamente soluções acima (over-tuned) e abaixo
  (under-tuned) da faixa.
- O memorial mostra `f1`, as `f_excitação`, a razão e o veredicto.
- **Nota explícita no relatório** sobre a limitação do fator estático 1.5 perto
  da ressonância, e como esta verificação a complementa.

**Validação:** viga biapoiada com massa central — `f1` confere com a fórmula
fechada `f1 = (1/2π)·√(48EI/(m·L³))` dentro de tolerância.

---

## FASE 4 — Verificação do perfil receptor (branch `feat/fase4-perfil-receptor`)

**Objetivo:** verificar o perfil metálico EXISTENTE onde o suporte é soldado/
aparafusado (as "vigas laranja" do caso real, fixação em estrutura metálica, sem
betão). Resolve o ponto 4. Módulo independente — pode correr em paralelo às
outras fases se necessário, mas entrega na ordem.

- Quando `support_fixation_medium == STEEL_STRUCTURE`, e o utilizador fornece a
  secção/material do perfil receptor (já há campos em `SteelFixationInput`:
  `receiving_member_section_id`, `receiving_member_material`), verificar o perfil
  receptor sob as **reações que o suporte lhe transmite** (vindas do solver):
  - axial, corte, flexão (eixo forte e fraco) — EC3 6.2/6.3;
  - **torção** (a reação do suporte aplica excentricidade → momento torsor no
    perfil receptor) — verificação de torção EC3 6.2.7 (pode ser simplificada,
    mas tem de existir e ser declarada);
  - interação flexão+torção e flexão+axial.
- `steel_fixation.py`: `receiving_member_checked` passa a `True` quando o perfil
  é fornecido e verificado; o aviso "verificar separadamente" só se mantém
  quando o utilizador NÃO fornece o perfil receptor.
- Novo módulo no `module_breakdown` (ex.: `RECEIVING_MEMBER`), com η, estado,
  citações e i18n. NÃO inventar resistência se faltar input — nesse caso fica
  `NOT_VERIFIED` com mensagem clara.
- **Frequência do perfil receptor:** fora do âmbito desta fase salvo se trivial;
  declarar como limitação. (A ressonância global é tratada na Fase 3.)

**Validação:** perfil receptor com esforço conhecido reproduz η de flexão/corte
calculável à mão; caso sem input de perfil receptor → `NOT_VERIFIED`, nunca verde.

---

## FASE 5 — Array de ventiladores posicionado (branch `feat/fase5-array-ventiladores`)

**Objetivo:** representar um conjunto de ventiladores iguais dispostos em matriz
(ex.: 2×3) como uma entidade, com cargas posicionadas na grelha — em vez de somar
pesos e dividir por N. Resolve o ponto 3 da lista do utilizador. Depende da
grelha da Fase 1.

- Abstração "array de ventiladores": o utilizador define arranjo (linhas ×
  colunas), passo entre unidades, e os dados de UMA unidade (peso operação,
  footprint, CG, frequência) — o sistema replica. Evita preencher um a um.
- As cargas das unidades entram **posicionadas** na grelha (reaproveita o
  mecanismo `manual_loads` ponto/área de `load_surfaces.py`, mapeando cada
  ventilador ao nó/painel correspondente), não como total agregado num só nó.
- A massa de cada unidade entra na matriz de massa da Fase 3 na sua posição real.
- UI (`sidebar_fan.py`): modo "array" além do modo "unidades individuais"
  existente. Retrocompatível.

**Validação:** array 1×1 reproduz exatamente o resultado de uma unidade única
(sem regressão); array 2×3 simétrico distribui carga simetricamente na grelha.

---

## Encerramento

No PR de cada fase, inclui no corpo: o que mudou, que casos de validação foram
adicionados e os seus resultados numéricos vs. solução fechada, e que limitações
permanecem. Termina o corpo do PR com:

🤖 Generated with [Claude Code](https://claude.com/claude-code)
