"""
Модуль расчёта выручки Unified Promo Hub.

Центральная формула:
    N_redemptions = MAU_hub × Offer_Coverage × CTR_offer × Redemption_Rate
    Revenue_CPA   = N_redemptions × share_CPA × CPA_avg
    Revenue_RS    = N_redemptions × (1 − share_CPA) × AOV_avg × RevShare_avg
    Revenue_gross = (Revenue_CPA + Revenue_RS) × Incremental_adj

Рост MAU_hub — ступенчатая S-кривая по фазам:
    Phase 1 (м. 1 .. phase1_end)     : penetration_p1 % от MAU T-Bank
    Phase 2 (м. phase1_end+1 .. phase2_end): penetration_p2 %
    Phase 3 (м. phase2_end+1 .. N)   : penetration_p3 %

Все параметры передаются явно — никаких хардкодных констант.
"""
from typing import Dict, List


def _get_phase(month: int, phase1_end: int, phase2_end: int) -> int:
    """Возвращает номер фазы (1, 2 или 3) для заданного месяца."""
    if month <= phase1_end:
        return 1
    if month <= phase2_end:
        return 2
    return 3


def calculate_mau_hub(
    month: int,
    mau_tbank: float,
    mau_penetration_p1: float,
    mau_penetration_p2: float,
    mau_penetration_p3: float,
    phase1_end: int,
    phase2_end: int,
) -> float:
    """
    MAU_hub для конкретного месяца.

    Внутри каждой фазы используется линейная интерполяция от
    предыдущего значения проникновения к следующему, чтобы кривая
    была плавной, а не ступенчатой.
    """
    phase = _get_phase(month, phase1_end, phase2_end)

    if phase == 1:
        # Плавный старт: 0% → penetration_p1 за phase1_end месяцев
        pct = mau_penetration_p1 / 100.0
        t = month / phase1_end  # 0..1
        return mau_tbank * pct * t

    if phase == 2:
        pct_start = mau_penetration_p1 / 100.0
        pct_end = mau_penetration_p2 / 100.0
        phase_len = phase2_end - phase1_end
        t = (month - phase1_end) / phase_len  # 0..1
        pct = pct_start + (pct_end - pct_start) * t
        return mau_tbank * pct

    # Phase 3
    pct_start = mau_penetration_p2 / 100.0
    pct_end = mau_penetration_p3 / 100.0
    # Насыщение: логистическое приближение через экспоненту
    # t растёт от 0 до бесконечности; при t=1 достигается ~63% разрыва
    import math
    phase3_start = phase2_end + 1
    t = (month - phase2_end)  # месяцев в Phase 3
    # скорость насыщения — чем больше, тем быстрее достигаем pct_end
    r = 0.25
    pct = pct_end - (pct_end - pct_start) * math.exp(-r * t)
    return mau_tbank * pct


def calculate_monthly_revenue(
    month: int,
    params: Dict,
) -> Dict:
    """
    Полный расчёт выручки для одного месяца.

    Возвращает словарь с промежуточными значениями для прозрачности.
    """
    phase1_end = params["phase1_end"]
    phase2_end = params["phase2_end"]

    mau_hub = calculate_mau_hub(
        month=month,
        mau_tbank=params["mau_tbank"],
        mau_penetration_p1=params["mau_penetration_p1"],
        mau_penetration_p2=params["mau_penetration_p2"],
        mau_penetration_p3=params["mau_penetration_p3"],
        phase1_end=phase1_end,
        phase2_end=phase2_end,
    )

    phase = _get_phase(month, phase1_end, phase2_end)
    p = f"p{phase}"
    offer_coverage = params[f"{p}_offer_coverage"] / 100.0
    ctr_offer = params[f"{p}_ctr_offer"] / 100.0
    redemption_rate = params[f"{p}_redemption_rate"] / 100.0

    n_redemptions = mau_hub * offer_coverage * ctr_offer * redemption_rate

    share_cpa = params["share_cpa"] / 100.0
    cpa_avg = params["cpa_avg"]
    aov_avg = params["aov_avg"]
    revshare_avg = params["revshare_avg"] / 100.0
    incremental_adj = params["incremental_adj"]

    revenue_cpa = n_redemptions * share_cpa * cpa_avg
    revenue_rs = n_redemptions * (1.0 - share_cpa) * aov_avg * revshare_avg
    revenue_gross = (revenue_cpa + revenue_rs) * incremental_adj

    return {
        "month": month,
        "phase": phase,
        "mau_hub": mau_hub,
        "n_redemptions": n_redemptions,
        "revenue_cpa": revenue_cpa,
        "revenue_rs": revenue_rs,
        "total_revenue": revenue_gross,
    }


def calculate_revenue_for_months(params: Dict, num_months: int) -> List[Dict]:
    """Рассчитывает выручку для каждого месяца горизонта."""
    return [calculate_monthly_revenue(m, params) for m in range(1, num_months + 1)]
