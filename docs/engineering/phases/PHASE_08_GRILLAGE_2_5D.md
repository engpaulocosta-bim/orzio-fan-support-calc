# Fase 08 - Grelha plana 2.5D

## Objetivo

Substituir o modelo de viga representativa da plataforma por uma grelha plana
com vigas longitudinais e travessas quando `platform_n_crossbeams >= 2`.
Entradas antigas, sem travessas, continuam a usar o caminho legado.

## Modelo implementado

- Três graus de liberdade por nó: deslocamento vertical `w` e rotações `rx`, `ry`.
- Barras com rigidez de flexão `EI` e torção de Saint-Venant `GJ`.
- Malha formada pelos cruzamentos das vigas longitudinais com as travessas.
- Plataforma com mão-francesa: borda de ligação restringida em `w`, `rx` e `ry`.
- Plataforma sem mão-francesa: apoios verticais nos quatro cantos.
- Carga vertical total aplicada nos nós centrais da grelha.
- Esforços de cada barra recuperados diretamente do solver.
- Seleção de perfil iterada com o peso próprio do perfil selecionado.
- Distribuição bidirecional por razão de aspeto, com conservação da carga.

## Validação numérica

Os casos estão em `tests/test_phase08_grillage.py`.

### Viga biapoiada equivalente

Dados:

- `P = 12 kN`
- `L = 4 m`
- `E = 210 000 000 kN/m²`
- `I = 8.0e-6 m4`

Solução fechada:

- `Mmax = P L / 4 = 12.0 kNm`
- `delta = P L3 / (48 E I) = 0.00952381 m`

O solver reproduz ambos os valores com tolerância relativa de `1e-8`.

### Grelha simétrica 2 x 2 painéis

Uma carga central de `10 kN` produz quatro reações iguais de `2.5 kN`.
As barras simétricas apresentam momentos de extremidade iguais em módulo.

### Conservação de carga

Para todos os casos testados, a soma das reações verticais coincide com a soma
das cargas verticais aplicadas. A distribuição two-way também conserva a carga
de área antes da aplicação ao solver.

## Rastreabilidade

- `dataset_provenance.solver_module = "grillage_2_5d"`
- `dataset_provenance.platform_grid` registra o número de vigas e travessas.
- O módulo `LOAD_DISTRIBUTION_SURFACE` fica `OK` apenas para distribuição
  bidirecional calculada numa grelha real sem pendências de revisão.
- Citação adicionada: EN 1993-1-1, cláusula 5.2.

## Limitações atuais

- O modelo é elástico linear.
- Ligações semirrígidas e não linearidade geométrica não são consideradas.
- A resposta horizontal e as diagonais permanecem verificadas pelo módulo
  separado de mão-francesa; a grelha resolve a resposta vertical da plataforma.
- A posição individual de cada ventilador ainda não é modelada. Nesta fase, a
  carga agregada é aplicada nos nós centrais; o array posicionado pertence à
  Fase 5 do solver v2.
- A constante de torção `J` é estimada pelas dimensões disponíveis no catálogo:
  parede fina fechada para RHS e soma de retângulos para perfis abertos.
