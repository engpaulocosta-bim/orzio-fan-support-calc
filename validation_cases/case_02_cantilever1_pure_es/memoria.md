# Caso 02 — Cantilever 1 (consola pura), Espanha zona B, S275

## Input
180 kg em operação, consola L = 800 mm, h = 500 mm, ES zona B (ag/g = 0.08),
S275, fator dinâmico 1.5, sem excentricidade.

Este é o caso com η mais alto da biblioteca (0.74) — toda a cadeia LTB foi
verificada à mão de ponta a ponta.

## 1. Cargas (acções totais)

```
G_eq  = 180 × 9.80665/1000          = 1.76520 kN
G_tot = 1.15 × G_eq                 = 2.02998 kN
Q     = G_eq × 0.5                  = 0.88260 kN

ULS_fundamental: 1.35×2.02998 + 1.5×0.88260 = 2.74047 + 1.32390 = 4.06437 kN  ★
E_h (sísmica) = 0.08 × 2.02998 = 0.16240 kN  (não governa)
```

**Esperado: design_load_kN = 4.064.**

## 2. Esforços no elemento (consola pura)

```
M_y = V × L = 4.06437 × 0.8 = 3.25150 kNm   (momento de encastramento)
Lcr,y = 2L = 1600 mm (consola livre), Lcr,z = L = 800 mm
```

## 3. Verificação da secção — IPE80 S275

Catálogo IPE80: W_pl,y = 23.2 cm³, I_z = 8.49 cm⁴, h=80, b=46, tw=3.8, tf=5.2.

```
Flexão (cl. 6.2.5): Mc_Rd = 23.2e3 × 275/1e6  = 6.380 kNm
                    η_bending = 3.25150/6.380 = 0.5096

LTB (cl. 6.3.2), Lcr = 1600 mm:
  I_w  = 8.49e4 × 74.8²/4                     = 1.1875e8 mm⁶
  I_t  = (2×46×5.2³ + 69.6×3.8³)/3            = 5585 mm⁴
  Mcr  = (π/1600)·√(210000×8.49e4×81000×5585
         + (π×210000/1600)²×8.49e4×1.1875e8)  = 6.1404 kNm
  λ_LT = √(6.380/6.1404)                      = 1.0193
  φ_LT = 0.5(1+0.34(1.0193−0.4)+0.75·1.0193²) = 0.99491
  χ_LT = 1/(0.99491+√(0.99491²−0.75×1.0193²)) = 0.6878
  Mb_Rd = 0.6878 × 6.380                      = 4.3884 kNm
  η_LTB = 3.25150/4.3884                      = 0.7409   ★ governa
```

**Esperado: IPE80, η = 0.7409, governing_check = ltb.**

## 4. Ancoragens em parede (anchor_type = concrete)

Consola fixada em parede — tração pelo momento de encastramento:

```
M_fix = V_uls × L = 4.06437 × 0.8 = 3.25150 kNm
braço = max(0.9×h_secção, 150) = max(72, 150) = 150 mm = 0.15 m
n = 4, lado tracionado n_t = 2
T por ancoragem = 3.25150/(0.15×2) = 10.838 kN
Ø12 8.8: F_t,Rd = 0.9×800×88.22/1.25/1000 = 50.81 kN
η_N = 10.838/50.81 = 0.2133
```

**Esperado: anchor_type=concrete, η_tração = 0.2133.**

## 5. Status e classificação

η = 0.74 < 0.90, 180 kg na faixa normal, ag = 0.08 ≤ 0.15
→ **PASS / ENGINEERING_ESTIMATE**.

## Observações técnicas

- η_LTB ≈ 0.74 deixa folga real de 26% — qualquer regressão no Mcr, na curva b
  ou no Lcr da consola (2L) move este valor de forma detetável.
- A consola pura é o modelo onde o LTB governa com maior margem sobre a flexão
  pura (0.74 vs 0.51): protege a presença do check LTB no envelope.
