"""Verificação de secções metálicas — EC3 EN 1993-1-1 / NBR 8800 / NCh427."""
from __future__ import annotations
import math
import logging
from ..models import SteelSection, LoadCombination, SectionVerificationResult
from ..enums import SteelGrade, StructuralCode, CheckerStatus, SectionFamily
from ..catalogs.steel_grade_catalog import get_grade_spec, design_strength
from ..catalogs.steel_section_catalog import list_sections

logger = logging.getLogger("sfsc.section_verifier")

# Limite de utilização para selecção automática
MAX_UTILIZATION = 0.90


def verify_section(
    section: SteelSection,
    combination: LoadCombination,
    code: StructuralCode,
    steel_grade: SteelGrade,
    buckling_length_y_mm: float,
    buckling_length_z_mm: float,
) -> SectionVerificationResult:
    """
    Verifica uma secção metálica contra a combinação governante.
    Verificações: corte, flexão, encurvadura lateral (LTB), compressão (se N≠0).
    Retorna SectionVerificationResult com utilization_ratio = max de todas.
    """
    spec     = get_grade_spec(steel_grade)
    fy_mpa   = spec.fy_mpa
    E_mpa    = spec.E_mpa
    gamma_M0 = spec.gamma_M0
    gamma_M1 = spec.gamma_M1

    checks: dict[str, float] = {}
    warnings: list[str] = []
    assumptions = ["A-STR-001", "A-STR-002", "A-STR-003"]
    clauses: list[str] = []

    # ── 6.2.6 Resistência ao corte ────────────────────────────────────────────
    # Av ≈ hw × tw  (alma)
    hw_mm    = section.h_mm - 2 * section.tf_mm
    Av_mm2   = hw_mm * section.tw_mm
    Vpl_Rd_kN = (Av_mm2 * fy_mpa / math.sqrt(3)) / (gamma_M0 * 1000.0)
    V_Ed_kN  = max(abs(combination.V_z_kN), abs(combination.V_y_kN))
    eta_V    = V_Ed_kN / Vpl_Rd_kN if Vpl_Rd_kN > 0 else 0.0
    checks["shear_z"] = eta_V
    clauses.append("EN 1993-1-1 cl. 6.2.6")

    # Efeito de corte na flexão (cl. 6.2.8): se V_Ed > 0.5*Vpl_Rd, reduz fy
    rho_shear = 0.0
    if V_Ed_kN > 0.5 * Vpl_Rd_kN:
        rho_shear = (2 * V_Ed_kN / Vpl_Rd_kN - 1.0) ** 2
        warnings.append(
            f"V_Ed ({V_Ed_kN:.1f} kN) > 0.5×Vpl,Rd ({0.5*Vpl_Rd_kN:.1f} kN) — "
            "redução de fy por corte aplicada (cl. 6.2.8)"
        )

    # ── 6.2.5 Resistência à flexão (Mc,Rd) ───────────────────────────────────
    fy_eff   = fy_mpa * (1.0 - rho_shear)
    Mc_Rd_kNm = (section.W_pl_y_mm3 * fy_eff) / (gamma_M0 * 1e6)
    M_Ed_kNm  = abs(combination.M_y_kNm)
    eta_M    = M_Ed_kNm / Mc_Rd_kNm if Mc_Rd_kNm > 0 else 0.0
    checks["bending_y"] = eta_M
    clauses.append("EN 1993-1-1 cl. 6.2.5")

    # ── 6.3.2 Encurvadura lateral (LTB) ──────────────────────────────────────
    if M_Ed_kNm > 0 and buckling_length_y_mm > 0:
        Lcr_mm = buckling_length_y_mm
        # Momento crítico de encurvadura lateral (simplificado — secção em I)
        # M_cr = C1 * (π²EI_z/(Lcr²)) * sqrt(I_w/I_z + Lcr²*G*I_t/(π²*E*I_z))
        # Simplificação: usar curva de encurvadura lateral EC3 com lambda_LT
        I_z_mm4 = section.I_z_mm4
        I_y_mm4 = section.I_y_mm4
        # I_w (empenamento) ≈ I_z*(h-tf)²/4 para perfis em I
        h_eff_mm = section.h_mm - section.tf_mm
        I_w_mm6  = I_z_mm4 * (h_eff_mm**2) / 4.0
        # I_t (torção de St. Venant) ≈ (2*b*tf³ + hw*tw³) / 3
        I_t_mm4  = (2 * section.b_mm * section.tf_mm**3 +
                    (section.h_mm - 2*section.tf_mm) * section.tw_mm**3) / 3.0
        G_mpa    = spec.G_mpa

        Mcr_Nmm = (math.pi / Lcr_mm) * math.sqrt(
            E_mpa * I_z_mm4 * G_mpa * I_t_mm4 +
            (math.pi * E_mpa / Lcr_mm)**2 * I_z_mm4 * I_w_mm6
        )
        Mcr_kNm = Mcr_Nmm / 1e6

        W_pl_y_mm3 = section.W_pl_y_mm3
        lambda_LT = math.sqrt(W_pl_y_mm3 * fy_mpa / Mcr_Nmm) if Mcr_Nmm > 0 else 2.0

        # Curva b (perfis em I laminados h/b > 2 → curva b, αLT=0.34)
        alpha_LT = 0.34
        lambda_LT_0 = 0.4
        beta_LT = 0.75

        if lambda_LT <= lambda_LT_0:
            chi_LT = 1.0
        else:
            phi_LT = 0.5 * (1 + alpha_LT * (lambda_LT - lambda_LT_0) + beta_LT * lambda_LT**2)
            chi_LT = min(1.0, 1.0 / (phi_LT + math.sqrt(phi_LT**2 - beta_LT * lambda_LT**2)))

        Mb_Rd_kNm = chi_LT * W_pl_y_mm3 * fy_mpa / (gamma_M1 * 1e6)
        eta_LTB   = M_Ed_kNm / Mb_Rd_kNm if Mb_Rd_kNm > 0 else 0.0
        checks["ltb"] = eta_LTB
        clauses.append("EN 1993-1-1 cl. 6.3.2")

        if lambda_LT > 0.4:
            warnings.append(
                f"λ_LT = {lambda_LT:.2f} — encurvadura lateral considerada "
                f"(χ_LT = {chi_LT:.3f})"
            )

    # ── 6.2.4 Compressão (se esforço axial) ──────────────────────────────────
    if abs(combination.N_kN) > 0.01:
        Nc_Rd_kN = section.A_mm2 * fy_mpa / (gamma_M0 * 1000.0)
        eta_N    = abs(combination.N_kN) / Nc_Rd_kN
        checks["axial"] = eta_N
        clauses.append("EN 1993-1-1 cl. 6.2.4")

        # 6.3.1 Encurvadura por compressão
        if buckling_length_z_mm > 0:
            lam_z = (buckling_length_z_mm / section.i_z_mm) * math.sqrt(fy_mpa / (math.pi**2 * E_mpa))
            alpha_z = 0.49  # curva c
            phi_z   = 0.5 * (1 + alpha_z * (lam_z - 0.2) + lam_z**2)
            chi_z   = min(1.0, 1.0 / (phi_z + math.sqrt(phi_z**2 - lam_z**2)))
            Nb_Rd_kN = chi_z * section.A_mm2 * fy_mpa / (gamma_M1 * 1000.0)
            eta_buck = abs(combination.N_kN) / Nb_Rd_kN
            checks["buckling_z"] = eta_buck
            clauses.append("EN 1993-1-1 cl. 6.3.1")

    # ── Ratio governante ──────────────────────────────────────────────────────
    if not checks:
        checks["no_load"] = 0.0

    max_check  = max(checks, key=lambda k: checks[k])
    max_ratio  = checks[max_check]

    if max_ratio > 1.0:
        status = CheckerStatus.FAIL
    elif max_ratio > MAX_UTILIZATION:
        status = CheckerStatus.MARGINAL
    else:
        status = CheckerStatus.PASS

    return SectionVerificationResult(
        section=section,
        utilization_ratio=round(max_ratio, 4),
        utilization_by_check={k: round(v, 4) for k, v in checks.items()},
        governing_check=max_check,
        status=status,
        code_clause=" | ".join(dict.fromkeys(clauses)),
        warnings=warnings,
        assumptions_used=assumptions,
    )

def find_passing_sections(
    combinations: list[LoadCombination],
    code: StructuralCode,
    steel_grade: SteelGrade,
    preferred_families: list[SectionFamily],
    buckling_length_y_mm: float,
    buckling_length_z_mm: float,
    max_utilization: float = 1.0,
) -> list[SectionVerificationResult]:
    """Retorna todos os perfis que verificam, ordenados por peso crescente."""
    governing = max(combinations, key=lambda c: abs(c.V_z_kN))
    candidates: list[SectionVerificationResult] = []
    seen: set[tuple[SectionFamily, str]] = set()

    for family in preferred_families:
        for section in list_sections(family):
            key = (section.family, section.designation)
            if key in seen:
                continue
            seen.add(key)
            result = verify_section(
                section, governing, code, steel_grade,
                buckling_length_y_mm, buckling_length_z_mm,
            )
            if result.utilization_ratio <= max_utilization:
                candidates.append(result)

    return sorted(
        candidates,
        key=lambda r: (r.section.weight_kgm, r.section.family.value, r.section.designation),
    )


def auto_select_section(
    combinations: list[LoadCombination],
    code: StructuralCode,
    steel_grade: SteelGrade,
    preferred_families: list[SectionFamily],
    buckling_length_y_mm: float,
    buckling_length_z_mm: float,
    max_utilization: float = MAX_UTILIZATION,
) -> tuple[SteelSection, SectionVerificationResult]:
    """
    Itera catálogos (peso crescente) e retorna o perfil mais leve que verifica.
    Levanta OutOfScopeError se nenhum perfil satisfaz.
    """
    from ..exceptions import OutOfScopeError

    # Combinação governante = maior V_z
    governing = max(combinations, key=lambda c: abs(c.V_z_kN))

    for family in preferred_families:
        for section in list_sections(family):
            result = verify_section(
                section, governing, code, steel_grade,
                buckling_length_y_mm, buckling_length_z_mm,
            )
            if result.utilization_ratio <= max_utilization:
                logger.info(
                    "Seleccionado: %s  η=%.3f  check=%s",
                    section.designation, result.utilization_ratio, result.governing_check
                )
                return section, result

    raise OutOfScopeError(
        "Nenhum perfil no catálogo satisfaz as verificações EC3. "
        "Considere aço de maior grau ou perfil de catálogo externo.",
        parameter="utilization_ratio",
        limit=max_utilization,
    )
