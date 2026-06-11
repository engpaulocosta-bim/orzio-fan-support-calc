# Caso 05 — Pedestal, Chile zona 3, S355 — combinação sísmica governa

## Input
320 kg em operação, patins L = 1200 mm, pés h = 800 mm, CL zona 3
(ag/g = 0.40), S355, CG do ventilador a 300 mm, footprint 900×700 mm.

Este caso protege a correção C-01 da auditoria: a combinação sísmica TEM de
governar o dimensionamento e gerar tração de derrube nas ancoragens.

## 1. Cargas (acções totais — coeficientes NCh: γG = 1.4, γQ = 1.6)

```
G_eq  = 320 × 9.80665/1000          = 3.13813 kN
G_tot = 1.15 × G_eq                 = 3.60885 kN
Q     = G_eq × 0.5                  = 1.56906 kN

ULS_fundamental: 1.4×3.60885 + 1.6×1.56906 = 5.05239 + 2.51050 = 7.56289 kN
ULS_seismic:     1.0×G_tot = 3.60885 kN; E_h = 0.40×3.60885 = 1.44354 kN
```

**Esperado: design_load_kN = 7.563** (ULS total — nível de acções).

## 2. Esforços no patim — a sísmica governa

```
Fundamental: q = (7.56289/2)/1.2 = 3.15120 kN/m
             M = q×1.2²/8 = 0.56722 kNm        (sem componente horizontal)

Sísmica:     q = (3.60885/2)/1.2 = 1.50369 kN/m
             M_patim = q×1.2²/8 = 0.27066 kNm
             M_sismo = E_h×h/2 = 1.44354×0.8/2 = 0.57742 kNm
             M = 0.27066 + 0.57742 = 0.84808 kNm   ★ GOVERNA (> 0.56722)
```

**Esperado: governing_combination = ULS_seismic.**

## 3. Verificação da secção — IPE80 S355

```
LTB, Lcr = 1200 mm (cadeia idêntica ao caso 01):
  Mb_Rd = 0.71709 × 8.236 = 5.906 kNm
  η_LTB = 0.84808/5.906 = 0.1436   ★ governa
```

**Esperado: IPE80, η = 0.1436, check = ltb, combinação ULS_seismic.**

## 4. Ancoragens no chão — tração de derrube > 0

```
h_cg = 800 + 300 = 1100 mm
M_ot = 1.44354 × 1.1 = 1.58789 kNm
braço = 0.8 × 0.9 = 0.72 m; n = 4, n_t = 2
T = max(0, 1.58789/(0.72×2) − 3.60885/4)
  = max(0, 1.10270 − 0.90221) = 0.20049 kN > 0
η_N = 0.20049/50.81 = 0.0039
```

**Esperado: anchor_type=concrete, η_tração = 0.0039 (> 0).**

## 5. Status e classificação

η < 0.90 → **PASS**, mas ag/g = 0.40 ≫ 0.15 → **REQUIRES_SPECIALIST**.

## Observações técnicas

- Antes da correção C-01, este caso dava M_sismo = 0 e η ≈ 0.096
  (0.56722/5.906) com a fundamental a "governar" — qualquer regressão no
  envelope reverte governing_combination para ULS_fundamental e este teste falha.
- A tração de derrube é pequena porque o CG é baixo; com CG a 800 mm o
  modelo dá T ≈ 0.66 kN — o sinal (≠ 0) é o que este caso protege.
