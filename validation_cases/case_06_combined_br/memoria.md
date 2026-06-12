# Caso 06 — Combined (mesa + pendurais), Brasil zona II, S355

## Input
200 kg em operação, mesa L = 1500 mm, h = 700 mm, BR zona II (ag/g = 0.10),
S355. Sem molas (anti_vibration = none).

## 1. Cargas (acções totais — coeficientes NBR: γG = 1.4, γQ = 1.4)

```
G_eq  = 200 × 9.80665/1000          = 1.96133 kN
G_tot = 1.15 × G_eq                 = 2.25553 kN
Q     = G_eq × 0.5                  = 0.98067 kN

ULS_fundamental: 1.4×(2.25553 + 0.98067) = 1.4×3.23620 = 4.53067 kN  ★
E_h = 0.10 × 2.25553 = 0.22555 kN
```

**Esperado: design_load_kN = 4.531** (norma estrutural: NBR_8800).

## 2. Esforços na mesa (modelo pedestal × fator mesa 0.70)

```
Base pedestal (fundamental):
  q = (4.53067/2)/1.5 = 1.51022 kN/m
  M_patim = q×1.5²/8 = 0.42475 kNm
  V_patim = 4.53067/4 = 1.13267 kN

Mesa (70% da carga — pendurais absorvem 30% + horizontal):
  M_y = 0.70 × 0.42475 = 0.29733 kNm
  V   = 0.70 × 1.13267 = 0.79287 kN
  F_pendural = (0.30×V_z + E_h)/4 por tirante
```

## 3. Verificação da secção — IPE80 S355

```
LTB, Lcr = 1500 mm (cadeia idêntica ao caso 04):
  Mb_Rd = 0.62968 × 8.236 = 5.1861 kNm
  η_LTB = 0.29733/5.1861 = 0.0573   ★ governa
```

**Actualizado Phase 03 (2026-06-12):** Com o motor global frame (viga simplesmente apoiada
de 3 nós, carga central), a carga total V_z é aplicada no nó central. O momento no meio
da viga é determinado pelo solver directamente, incluindo o factor mesa (70%) que entra nas
combinações. Resultado:

```
M_j (member-left, ULS_fundamental) ≈ 0.848 kNm
  (aplica o factor mesa na combinação antes de enviar ao solver)
  LTB, Lcr = 1500 mm: η_LTB = 0.848/... ≈ 0.3276   ★ governa
```

**Esperado (actualizado): IPE80, η ≈ 0.3276, governing_check = member-left.ltb.**

## 4. Ancoragens no chão

```
h_cg = 700 + 300 = 1000 mm; M_ot = 0.22555 × 1.0 = 0.22555 kNm
braço = 0.72 m; T = max(0, 0.22555/1.44 − 2.25553/4)
     = max(0, 0.15664 − 0.56388) = 0 → η_tração = 0
```

## 5. Status e classificação

η < 0.90, 200 kg na faixa normal, ag = 0.10 ≤ 0.15, sem molas
→ **PASS / ENGINEERING_ESTIMATE**.

## Observações técnicas

- Protege os coeficientes NBR (1.4/1.4) e o fator mesa 0.70 do modelo
  COMBINED — o split 70/30 é uma assunção de engenharia ainda por validar
  externamente (auditoria H-11); este caso fixa o comportamento atual.
- Com anti_vibration = springs a classificação passaria a REQUIRES_SPECIALIST
  (coberto por teste de integração CASE-10).
