"""
Модуль денежного потока Unified Promo Hub.

Cash Flow    = Revenue − Total Costs
Cumulative CF = накопленный Cash Flow с месяца 1
EBITDA       = то же, что Cash Flow (нет амортизации / процентных расходов в этой модели)

Breakeven    = первый месяц, когда Cumulative CF ≥ 0
"""
from typing import Dict, List, Optional


def calculate_cash_flow_for_months(
    revenue_results: List[Dict],
    costs_results: List[Dict],
) -> List[Dict]:
    """
    Сшивает результаты revenue и costs в единый cash flow по месяцам.
    Cumulative CF накапливается нарастающим итогом.
    """
    cumulative = 0.0
    results = []

    for rev, cost in zip(revenue_results, costs_results):
        month = rev["month"]
        revenue = rev["total_revenue"]
        total_costs = cost["total_costs"]
        cf = revenue - total_costs
        cumulative += cf

        results.append({
            "month": month,
            "phase": rev["phase"],
            "mau_hub": rev["mau_hub"],
            "n_redemptions": rev["n_redemptions"],
            "revenue": revenue,
            "revenue_cpa": rev["revenue_cpa"],
            "revenue_rs": rev["revenue_rs"],
            "fixed_costs": cost["fixed_costs"],
            "variable_costs": cost["variable_costs"],
            "total_costs": total_costs,
            "cash_flow": cf,
            "cumulative_cash_flow": cumulative,
            "ebitda": cf,
        })

    return results


def calculate_breakeven_month(cash_flow_results: List[Dict]) -> Dict:
    """
    Находит первый месяц, когда накопленный CF ≥ 0.

    Возвращает:
        reached       : bool
        breakeven_month: int | None
        final_cumulative: float
    """
    for row in cash_flow_results:
        if row["cumulative_cash_flow"] >= 0:
            return {
                "reached": True,
                "breakeven_month": row["month"],
                "final_cumulative": row["cumulative_cash_flow"],
            }

    final = cash_flow_results[-1]["cumulative_cash_flow"] if cash_flow_results else 0.0
    return {
        "reached": False,
        "breakeven_month": None,
        "final_cumulative": final,
    }
