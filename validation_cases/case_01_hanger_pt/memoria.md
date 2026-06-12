# Caso 01 — Hanger, Portugal zona 1.3, S355

## Input
130 kg em operação (1 unidade), viga de apoio L = 1200 mm, varões h = 500 mm,
PT zona 1.3 (ag/g = 0.15), S355, fator dinâmico 1.5, sem excentricidade.

## 1. Cargas (acções totais)

```
G_eq  = 130 × 9.80665/1000          = 1.27486 kN
G_tot = 1.15 × G_eq                 = 1.46609 kN   (peso do suporte = 15%, A-GEN-001)
Q     = G_eq × (1.5 − 1.0)          = 0.63743 kN   (fator dinâmico, A-GEN-002)

ULS_fundamental: 1.35×G_tot + 1.5×Q = 1.97922 + 0.95614 = 2.93537 kN  ★ governa
ULS_seismic:     1.0×G_tot = 1.46609 kN  +  E_h = 0.15×1.46609 = 0.21991 kN
SLS:             G_tot + Q = 2.10352 kN
```

**Esperado: design_load_kN = 2.935** (ULS total).

## 2. Esforços no elemento (viga biapoiada, carga central)

```
M_y = V×L/4 = 2.93537 × 1.2/4       = 0.88061 kNm   (ULS fundamental)
M_z = V_y×L/4 = 0.21991 × 1.2/4     = 0.06597 kNm   (só na sísmica)
```

## 3. Verificação da secção — IPE80 S355 (perfil mais leve que verifica)

Catálogo IPE80: W_pl,y = 23.2 cm³, W_pl,z = 5.82 cm³, I_z = 8.49 cm⁴,
h=80, b=46, tw=3.8, tf=5.2. Lcr,y = L = 1200 mm (hanger).

```
Flexão (cl. 6.2.5): Mc_Rd = 23.2e3 × 355 / 1e6 = 8.236 kNm
                    η_bending = 0.88061/8.236 = 0.1069

LTB (cl. 6.3.2), Lcr = 1200 mm:
  I_w  = I_z(h−tf)²/4 = 8.49e4 × 74.8²/4      = 1.1875e8 mm⁶
  I_t  = (2btf³ + hw·tw³)/3                   = 5585 mm⁴
  Mcr  = (π/1200)·√(E·I_z·G·I_t + (πE/1200)²·I_z·I_w) = 8.7274 kNm
  λ_LT = √(W_pl·fy/Mcr) = √(8.236/8.7274)     = 0.9714
  φ_LT = 0.5(1+0.34(0.9714−0.4)+0.75·0.9714²) = 0.95103
  χ_LT = 1/(φ+√(φ²−0.75λ²))                   = 0.71709
  Mb_Rd = 0.71709 × 8.236                     = 5.906 kNm
  η_LTB = 0.88061/5.906                       = 0.1491   ★ governa
```

**Esperado: IPE80, η = 0.1491, governing_check = member-left.ltb, combinação ULS_fundamental.**

**Nota Phase 03 (2026-06-12):** Após extensão do motor global frame ao tipo HANGER,
o `governing_check` inclui agora o ID do membro (`member-left.ltb`) em vez de `ltb`.
A utilização e a combinação governante mantêm-se iguais ao cálculo manual.

## 4. Varões de suspensão (anchor_type = rod — sem betão)

```
N por varão = V_uls/4 = 0.73384 kN
Ø12 8.8: As = 0.78π×6² = 88.22 mm²; F_t,Rd = 0.9×800×88.22/1.25/1000 = 50.81 kN
η_N = 0.73384/50.81 = 0.0144
```

**Esperado: anchor_type=rod, 4×Ø12, hef = 0 (sem campos de betão).**

## 5. Status e classificação

η máx < 0.90, 130 kg ∈ [35, 500], ag = 0.15 ≤ 0.15 → **PASS / ENGINEERING_ESTIMATE**.

## Observações técnicas

- ag/g = 0.15 está exatamente no limiar de `classify` (> 0.15 dispararia
  REQUIRES_SPECIALIST) — este caso protege o comportamento da fronteira.
- O travamento lateral a meio vão pelos varões (Lcr,z = 0.5L) é assunção do
  modelo (A-STR-003); confirmar na obra que os varões travam de facto a viga.
