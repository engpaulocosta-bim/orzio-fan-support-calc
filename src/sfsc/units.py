"""Conversões de unidades — domínio estrutural."""
from __future__ import annotations

# ── Força ──────────────────────────────────────────────────────────────────────
def kn_to_n(kn: float) -> float:   return kn * 1_000.0
def n_to_kn(n: float)  -> float:   return n  / 1_000.0
def kgf_to_n(kgf: float) -> float: return kgf * G_GRAVITY
def kgf_to_kn(kgf: float) -> float: return kgf_to_n(kgf) / 1_000.0

# ── Momento ────────────────────────────────────────────────────────────────────
def knm_to_nm(knm: float) -> float:  return knm * 1_000.0
def nm_to_knm(nm: float)  -> float:  return nm  / 1_000.0
def knmm_to_knm(knmm: float) -> float: return knmm / 1_000.0

# ── Tensão ─────────────────────────────────────────────────────────────────────
def mpa_to_nmm2(mpa: float) -> float:   return mpa          # 1 MPa = 1 N/mm²
def nmm2_to_mpa(nmm2: float) -> float:  return nmm2
def kn_m2_to_mpa(knm2: float) -> float: return knm2 / 1_000.0
def pa_to_mpa(pa: float) -> float:      return pa / 1e6

# ── Comprimento ────────────────────────────────────────────────────────────────
def mm_to_m(mm: float) -> float:  return mm / 1_000.0
def m_to_mm(m: float)  -> float:  return m  * 1_000.0
def cm_to_mm(cm: float) -> float: return cm * 10.0
def mm_to_cm(mm: float) -> float: return mm / 10.0

# ── Inércia / módulo de secção ─────────────────────────────────────────────────
def cm4_to_mm4(cm4: float) -> float: return cm4 * 1e4
def mm4_to_cm4(mm4: float) -> float: return mm4 / 1e4
def cm4_to_m4(cm4: float) -> float:  return cm4 * 1e-8
def cm3_to_mm3(cm3: float) -> float: return cm3 * 1e3
def mm3_to_cm3(mm3: float) -> float: return mm3 / 1e3
def cm2_to_mm2(cm2: float) -> float: return cm2 * 1e2
def mm2_to_cm2(mm2: float) -> float: return mm2 / 1e2

# ── Massa / Peso ───────────────────────────────────────────────────────────────
def kg_to_kn(kg: float) -> float:    return kgf_to_kn(kg)
def tonne_to_kn(t: float) -> float:  return t * G_GRAVITY

# ── Constantes ─────────────────────────────────────────────────────────────────
G_GRAVITY: float = 9.80665   # m/s²
E_STEEL_GPA: float = 210.0   # GPa — módulo de elasticidade do aço estrutural
E_STEEL_MPA: float = 210_000.0  # MPa
E_STEEL_NMM2: float = 210_000.0  # N/mm²
