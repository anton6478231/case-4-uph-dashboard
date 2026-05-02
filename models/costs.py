"""
Модуль расчёта затрат Unified Promo Hub.

Переменные затраты (per redemption) снижаются с масштабом:
    Phase 1: vc_per_redemption_p1
    Phase 2: vc_per_redemption_p2
    Phase 3: vc_per_redemption_p3

Постоянные затраты (ступенчатый рост при переходе фаз):
    Phase 1: fixed_cost_p1
    Phase 2: fixed_cost_p2
    Phase 3: fixed_cost_p3

Все значения берутся из params — никаких хардкодных констант.
"""
from typing import Dict, List


def _get_phase(month: int, phase1_end: int, phase2_end: int) -> int:
    if month <= phase1_end:
        return 1
    if month <= phase2_end:
        return 2
    return 3


def calculate_monthly_costs(
    month: int,
    n_redemptions: float,
    params: Dict,
) -> Dict:
    """
    Расчёт затрат для одного месяца.

    Возвращает словарь с разбивкой на fixed / variable.
    """
    phase = _get_phase(month, params["phase1_end"], params["phase2_end"])

    # Переменные затраты — зависят от числа redemptions
    vc_map = {
        1: params["vc_per_redemption_p1"],
        2: params["vc_per_redemption_p2"],
        3: params["vc_per_redemption_p3"],
    }
    vc_per_red = vc_map[phase]
    variable_costs = n_redemptions * vc_per_red

    # Постоянные затраты — зависят только от фазы
    fc_map = {
        1: params["fixed_cost_p1"],
        2: params["fixed_cost_p2"],
        3: params["fixed_cost_p3"],
    }
    fixed_costs = fc_map[phase]

    total_costs = fixed_costs + variable_costs

    return {
        "month": month,
        "phase": phase,
        "fixed_costs": fixed_costs,
        "variable_costs": variable_costs,
        "vc_per_redemption": vc_per_red,
        "total_costs": total_costs,
    }


def calculate_costs_for_months(
    params: Dict,
    revenue_results: List[Dict],
) -> List[Dict]:
    """Рассчитывает затраты для каждого месяца, используя n_redemptions из revenue_results."""
    return [
        calculate_monthly_costs(
            month=r["month"],
            n_redemptions=r["n_redemptions"],
            params=params,
        )
        for r in revenue_results
    ]
