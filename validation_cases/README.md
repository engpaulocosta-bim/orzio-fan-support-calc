# Biblioteca de casos de validação — SFSC

Casos de referência com **memória de cálculo independente** (aritmética manual,
sem usar o motor) para validação de regressão numérica. Cada pasta contém:

| Ficheiro | Conteúdo |
|---|---|
| `input.json` | `FanSupportInput` serializado (round-trip Pydantic) |
| `expected.json` | Valores esperados + tolerâncias aceitáveis |
| `memoria.md` | Cálculo manual: cargas, esforços no elemento, verificação governante, status esperado e observações técnicas |

## Execução

Os casos correm automaticamente na suite (`tests/test_validation_cases.py`):

```bash
pytest tests/test_validation_cases.py -v
```

## Regras

- **Qualquer divergência fora da tolerância é uma regressão** — investigar antes
  de atualizar o `expected.json`. Atualizações de valores esperados exigem
  recalcular a memória manual correspondente e justificar no commit.
- As tolerâncias são apertadas de propósito (±2% relativo nos η e cargas):
  o objetivo é detetar mudanças de comportamento, não absorvê-las.
- Estes casos validam a **consistência interna** do motor face às fórmulas
  documentadas. **Não substituem** a validação por engenheiro estrutural
  independente exigida pela auditoria (secção G) — as próprias fórmulas
  simplificadas carecem de revisão externa antes de uso em projeto.

## Cobertura

| Caso | Tipo de suporte | País/zona | Particularidade |
|---|---|---|---|
| 01 | hanger | PT 1.3 | Varões roscados (anchor_type=rod) |
| 02 | cantilever_1 (pure) | ES B | η mais alto (0.74), LTB verificado à mão ponta-a-ponta |
| 03 | cantilever_2 | UK | Tração de ancoragem por momento de encastramento |
| 04 | cantilever_3 | FR 4 | ag=0.16 > 0.15 → REQUIRES_SPECIALIST |
| 05 | pedestal | CL 3 | Combinação sísmica governa; uplift de derrube > 0 |
| 06 | combined | BR II | Coeficientes NBR (1.4/1.4); fator mesa 0.70 |
