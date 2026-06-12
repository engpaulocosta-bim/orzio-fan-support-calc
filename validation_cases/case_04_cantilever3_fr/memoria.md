# Caso 04 — Cantilever 3 (pórtico em U invertido), França zona 4, S355

## Input
300 kg em operação, viga L = 1500 mm, pilares h = 1000 mm, FR zona 4
(ag/g = 0.16 — Alpes/Pirenéus), S355, CG do ventilador a 300 mm.

## 1. Cargas (acções totais)

```
G_eq  = 300 × 9.80665/1000          = 2.94199 kN
G_tot = 1.15 × G_eq                 = 3.38329 kN
Q     = G_eq × 0.5                  = 1.47100 kN

ULS_fundamental: 1.35×3.38329 + 1.5×1.47100 = 4.56744 + 2.20650 = 6.77394 kN  ★
E_h = 0.16 × 3.38329 = 0.54133 kN
```

**Esperado: design_load_kN = 6.774.**

## 2. Esforços no elemento

```
Viga:  M_viga = V×L/4 = 6.77394 × 1.5/4 = 2.54023 kNm  ★ governa
Pilar: N = V/2 = 3.38697 kN; M_pilar (sísmica) = 0.54133 × 1.0/2 = 0.27067 kNm
M_y = max(2.54023, 0.27067) = 2.5402 kNm
Lcr,y = L = 1500 mm (viga), Lcr,z = h = 1000 mm (pilares)
```

## 3. Verificação da secção — IPE80 S355

```
Flexão: η_bending = 2.5402/8.236 = 0.3084

LTB, Lcr = 1500 mm:
  Mcr  = 6.6283 kNm
  λ_LT = √(8.236/6.6283)                      = 1.1147
  φ_LT = 0.5(1+0.34(1.1147−0.4)+0.75·1.1147²) = 1.08745
  χ_LT = 1/(φ+√(φ²−0.75λ²))                   = 0.62968
  Mb_Rd = 0.62968 × 8.236                     = 5.1861 kNm
  η_LTB = 2.5402/5.1861                       = 0.4898   ★ governa

Compressão pilar (cl. 6.2.4/6.3.1): η_axial = 0.0125, η_buckling_z = 0.0303
```

**Actualizado Phase 03 (2026-06-12):** Com o motor global frame (pórtico em U de 5 nós),
a carga vertical é aplicada no nó central da viga superior. Os momentos nos meios da viga
são menores do que a aproximação simplificada (V×L/4). Resultado do solver:

```
Membro member-beam-left (nó-top-left → nó-top-mid, L/2 = 0.75 m):
  M_j ≈ 1.590 kNm (momento no centro da viga)
  LTB, Lcr = 1500 mm (comprimento total da viga — override):
  η_LTB = 1.590/5.186 ≈ 0.3065   ★ governa
```

**Esperado (actualizado): IPE80, η ≈ 0.3065, governing_check = member-beam-left.ltb.**

## 4. Ancoragens no chão (derrube sísmico)

```
h_cg = 1000 + 300 = 1300 mm; M_ot = 0.54133 × 1.3 = 0.70373 kNm
braço = 0.8 × 0.9 m (footprint) = 0.72 m; n = 4, n_t = 2
T = max(0, 0.70373/(0.72×2) − 3.38329/4) = max(0, 0.48870 − 0.84582) = 0
```

O peso próprio vence o derrube → **η_tração = 0** (com nota no relatório).

## 5. Status e classificação

η < 0.90 → status **PASS**, mas **ag/g = 0.16 > 0.15** →
**classification = REQUIRES_SPECIALIST** (headline "REQUER ESPECIALISTA").

## Observações técnicas

- Caso de fronteira da regra sísmica de `classify` (0.16 vs limiar 0.15):
  protege a precedência da classificação sobre o status numérico (C-03).
- O momento sísmico no pilar não governa aqui; com h maior ou ag/g chileno
  passaria a governar — ver caso 05.
