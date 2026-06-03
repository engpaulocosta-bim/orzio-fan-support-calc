"""Dimensionamento de ancoragens (varões roscados / chumbadores)."""
from __future__ import annotations
import math
from ..models import FanSupportInput, LoadCombination, AnchorResult
from ..enums import StructuralCode, CheckerStatus

_FCK: dict[str, float] = {
    "C20/25": 20.0, "C25/30": 25.0, "C30/37": 30.0,
    "C35/45": 35.0, "C40/50": 40.0,
}

# Tensão de cedência e rotura de varões roscados [MPa]
_ROD_GRADES: dict[str, tuple[float, float]] = {
    "5.8": (400.0, 500.0),
    "8.8": (640.0, 800.0),
    "10.9":(900.0, 1000.0),
    "A4-70": (450.0, 700.0),  # inox AISI 316
}


def calculate_anchor(
    inp: FanSupportInput,
    combination: LoadCombination,
    code: StructuralCode,
    concrete_grade: str = "C25/30",
    rod_grade: str = "8.8",
) -> AnchorResult:
    """
    Dimensiona ancoragens conforme EN 1992-4 (EC) / BS 8539 (UK) / NBR 6122 (BR).
    """
    warnings: list[str] = []
    fck = _FCK.get(concrete_grade, 25.0)

    N_Ed_kN = abs(combination.V_z_kN)  # carga vertical → tracção nos varões
    V_Ed_kN = abs(combination.V_y_kN)  # carga horizontal → corte

    fy_rod, fu_rod = _ROD_GRADES.get(rod_grade, (640.0, 800.0))
    gamma_Ms = 1.25   # coeficiente parcial do aço (ancoragem)

    # ── Escolher diâmetro mínimo ──────────────────────────────────────────────
    diameters = [12.0, 16.0, 20.0, 24.0, 30.0]
    n_anchors = 4  # ponto de partida: 4 ancoragens

    best = None
    for d_mm in diameters:
        As_mm2 = 0.78 * math.pi * (d_mm / 2.0)**2

        # Capacidade de tracção por varão
        N_Rd_s_kN = (fu_rod * As_mm2) / (gamma_Ms * 1000.0)
        # Capacidade de corte por varão
        V_Rd_s_kN = (0.6 * fu_rod * As_mm2) / (gamma_Ms * 1000.0)

        eta_N = N_Ed_kN / (n_anchors * N_Rd_s_kN)
        eta_V = V_Ed_kN / (n_anchors * V_Rd_s_kN)

        # Interacção EN 1992-4 cl. 7.2.2: (N/N_Rd)^1.5 + (V/V_Rd)^1.5 ≤ 1
        eta_comb = eta_N**1.5 + eta_V**1.5

        if eta_comb <= 1.0 and eta_N <= 0.90 and eta_V <= 0.90:
            best = (d_mm, n_anchors, N_Rd_s_kN, V_Rd_s_kN, eta_N, eta_V, eta_comb)
            break

        # Tentar com mais ancoragens
        for n in [6, 8]:
            eta_N2 = N_Ed_kN / (n * N_Rd_s_kN)
            eta_V2 = V_Ed_kN / (n * V_Rd_s_kN)
            eta_c2 = eta_N2**1.5 + eta_V2**1.5
            if eta_c2 <= 1.0 and eta_N2 <= 0.90 and eta_V2 <= 0.90:
                best = (d_mm, n, N_Rd_s_kN, V_Rd_s_kN, eta_N2, eta_V2, eta_c2)
                break
        if best:
            break

    if best is None:
        # Usar máximo disponível e marcar FAIL
        d_mm = 30.0
        n_anchors = 8
        As_mm2 = 0.78 * math.pi * (d_mm / 2.0)**2
        N_Rd_s_kN = (fu_rod * As_mm2) / (gamma_Ms * 1000.0)
        V_Rd_s_kN = (0.6 * fu_rod * As_mm2) / (gamma_Ms * 1000.0)
        eta_N = N_Ed_kN / (n_anchors * N_Rd_s_kN)
        eta_V = V_Ed_kN / (n_anchors * V_Rd_s_kN)
        eta_comb = eta_N**1.5 + eta_V**1.5
        best = (d_mm, n_anchors, N_Rd_s_kN, V_Rd_s_kN, eta_N, eta_V, eta_comb)
        warnings.append(
            "CRÍTICO: Ancoragem máxima (Ø30mm × 8) ainda insuficiente. "
            "Verificar com engenheiro de estruturas."
        )

    d_mm, n_anchors, N_Rd_kN, V_Rd_kN, eta_N, eta_V, eta_comb = best

    # ── Profundidade de embebimento ───────────────────────────────────────────
    # hef mínimo: 8×d (EN 1992-4 tabela)
    hef_mm = max(8.0 * d_mm, 100.0)

    # Verificação de pull-out (bond): Nbd = pi*d*hef*fbd
    fbd_mpa = 0.7 * 2.25 * (fck / 25.0)**0.5  # tensão de aderência [MPa]
    N_bd_kN = math.pi * d_mm * hef_mm * fbd_mpa / 1000.0

    if N_bd_kN < N_Ed_kN / n_anchors:
        # Aumentar profundidade
        hef_mm = (N_Ed_kN / n_anchors * 1000.0) / (math.pi * d_mm * fbd_mpa)
        hef_mm = math.ceil(hef_mm / 10.0) * 10.0
        warnings.append(
            f"Profundidade aumentada para {hef_mm:.0f} mm "
            "para garantir resistência ao arranque."
        )

    # Status
    if eta_comb > 1.0 or eta_N > 1.0 or eta_V > 1.0:
        status = CheckerStatus.FAIL
    elif eta_comb > 0.90:
        status = CheckerStatus.MARGINAL
    else:
        status = CheckerStatus.PASS

    # Cláusula conforme código
    if code.value.startswith("EN"):
        clause = "EN 1992-4 cl. 7.2.1 + 7.2.2"
    elif code == StructuralCode.NBR_8800:
        clause = "NBR 6122 (simplificado)"
    else:
        clause = "EN 1992-4 cl. 7.2.1 (referência)"

    return AnchorResult(
        n_anchors=n_anchors,
        anchor_diameter_mm=d_mm,
        embedment_depth_mm=round(hef_mm, 0),
        tensile_capacity_kN=round(n_anchors * N_Rd_kN, 2),
        shear_capacity_kN=round(n_anchors * V_Rd_kN, 2),
        utilization_tension=round(eta_N, 4),
        utilization_shear=round(eta_V, 4),
        utilization_combined=round(eta_comb, 4),
        status=status,
        code_clause=clause,
        warnings=warnings,
    )
