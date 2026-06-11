# Caso 03 — Cantilever 2 (consolas simétricas), Reino Unido, S355

## Input
250 kg em operação, vão total L = 1600 mm (braço = 800 mm cada lado),
h = 600 mm, UK (ag/g = 0.05), S355.

## 1. Cargas (acções totais)

```
G_eq  = 250 × 9.80665/1000          = 2.45166 kN
G_tot = 1.15 × G_eq                 = 2.81941 kN
Q     = G_eq × 0.5                  = 1.22583 kN

ULS_fundamental: 1.35×2.81941 + 1.5×1.22583 = 3.80620 + 1.83875 = 5.64495 kN  ★
```

**Esperado: design_load_kN = 5.645** (norma estrutural: EN1993-1-1+UK_NA).

## 2. Esforços no elemento (cada braço recebe V/2)

```
V por braço    = 5.64495/2 = 2.82248 kN
M_braço        = (V/2) × L_braço = 2.82248 × 0.8 = 2.25798 kNm  ★ governa
M_central      = V × L/8 = 5.64495 × 1.6/8       = 1.12899 kNm
M_y = max(2.25798, 1.12899) = 2.2580 kNm
Lcr,y = L = 1600 mm, Lcr,z = 0.5L = 800 mm
```

## 3. Verificação da secção — IPE80 S355

```
Flexão: Mc_Rd = 23.2e3 × 355/1e6 = 8.236 kNm → η_bending = 2.2580/8.236 = 0.2742

LTB, Lcr = 1600 mm (mesma cadeia do caso 02, com fy = 355):
  Mcr  = 6.1404 kNm
  λ_LT = √(8.236/6.1404)                      = 1.1581
  φ_LT = 0.5(1+0.34(1.1581−0.4)+0.75·1.1581²) = 1.13187
  χ_LT = 1/(φ+√(φ²−0.75λ²))                   = 0.60371
  Mb_Rd = 0.60371 × 8.236                     = 4.9722 kNm
  η_LTB = 2.2580/4.9722                       = 0.4541   ★ governa
```

**Esperado: IPE80, η = 0.4541, governing_check = ltb.**

## 4. Ancoragens em parede

```
P por apoio = V_uls/2 = 2.82248 kN
M_fix = P × (L/2) = 2.82248 × 0.8 = 2.25798 kNm
braço = max(0.9×80, 150) = 150 mm; n = 4, n_t = 2
T = 2.25798/(0.15×2) = 7.527 kN → η_N = 7.527/50.81 = 0.1481
```

**Esperado: anchor_type=concrete, η_tração = 0.1481.**

## 5. Status e classificação

η < 0.90, 250 kg na faixa normal, ag = 0.05 → **PASS / ENGINEERING_ESTIMATE**.

## Observações técnicas

- Protege o mapeamento UK → EN1993-1-1+UK_NA e o modelo de braço simétrico
  (M_braço > M_central para carga concentrada nas extremidades).
