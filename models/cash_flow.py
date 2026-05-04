"""
Модуль денежного потока Unified Promo Hub.

Cash Flow    = Revenue − Total Costs
Cumulative CF = накопленный Cash Flow с месяца 1
NPV          = сумма дисконтированных CF; месячная ставка выводится из годовой:
               r_monthly = (1 + annual_rate/100)^(1/12) − 1
Breakeven    = первый месяц, когда Cumulative CF ≥ 0
NPV Breakeven= первый месяц, когда Cumulative NPV ≥ 0

RnD интеграция:
  - month_offset в calculate_cash_flow_for_months сдвигает базу дисконтирования
    рыночных месяцев на длину RnD фазы, сохраняя нумерацию М1…Mn.
  - discount_rnd_cash_flows дисконтирует RnD CF по тем же правилам (m = 1..N).
  - combined_npv = RnD NPV + Market NPV.
"""
from typing import Dict, List, Optional


def calculate_cash_flow_for_months(
    revenue_results: List[Dict],
    costs_results: List[Dict],
    annual_discount_rate: float = 20.0,
    month_offset: int = 0,
) -> List[Dict]:
    """
    Сшивает revenue и costs в единый cash flow по месяцам.

    annual_discount_rate — ставка дисконтирования, % годовых.
    month_offset         — сдвиг базы дисконтирования (= rnd_months при RnD фазе):
                           PV(CF_t) = CF_t / (1 + r_m)^(month_offset + t)
                           Нумерация месяцев в таблице/графиках остаётся М1…Mn.
    """
    monthly_rate = (1.0 + annual_discount_rate / 100.0) ** (1.0 / 12.0) - 1.0

    cumulative = 0.0
    cumulative_npv = 0.0
    results = []

    for rev, cost in zip(revenue_results, costs_results):
        month = rev["month"]
        revenue = rev["total_revenue"]
        total_costs = cost["total_costs"]
        cf = revenue - total_costs
        cumulative += cf

        discount_factor = 1.0 / (1.0 + monthly_rate) ** (month_offset + month)
        discounted_cf = cf * discount_factor
        cumulative_npv += discounted_cf

        results.append({
            "month": month,
            "phase": rev["phase"],
            "mau_hub": rev["mau_hub"],
            "n_redemptions": rev["n_redemptions"],
            "revenue": revenue,
            "revenue_new":      rev.get("revenue_new", 0.0),
            "revenue_loyal":    rev.get("revenue_loyal", 0.0),
            "revenue_ret":      rev.get("revenue_ret", 0.0),
            "revenue_at_risk":  rev.get("revenue_at_risk", 0.0),
            "fixed_costs": cost["fixed_costs"],
            "variable_costs": cost["variable_costs"],
            "total_costs": total_costs,
            "cash_flow": cf,
            "cumulative_cash_flow": cumulative,
            "ebitda": cf,
            "discount_factor": discount_factor,
            "discounted_cash_flow": discounted_cf,
            "cumulative_npv": cumulative_npv,
        })

    return results


def discount_rnd_cash_flows(
    rnd_cf_results: List[Dict],
    annual_discount_rate: float = 20.0,
) -> List[Dict]:
    """
    Добавляет дисконтированные значения к RnD CF.

    RnD месяц m дисконтируется как PV = CF / (1+r)^m (m = 1..rnd_months),
    т.е. с нулевой точки отсчёта — начало инвестиций.

    Возвращает тот же список с добавленными полями:
        discount_factor, discounted_cash_flow, cumulative_npv.
    """
    monthly_rate = (1.0 + annual_discount_rate / 100.0) ** (1.0 / 12.0) - 1.0

    cumulative_npv = 0.0
    results = []

    for row in rnd_cf_results:
        m = row["month"]
        cf = row["cash_flow"]
        discount_factor = 1.0 / (1.0 + monthly_rate) ** m
        discounted_cf = cf * discount_factor
        cumulative_npv += discounted_cf

        updated = dict(row)
        updated["discount_factor"] = discount_factor
        updated["discounted_cash_flow"] = discounted_cf
        updated["cumulative_npv"] = cumulative_npv
        results.append(updated)

    return results


def calculate_breakeven_month(cash_flow_results: List[Dict]) -> Dict:
    """
    Находит breakeven по обычному CF и по NPV.

    Возвращает:
        reached             : bool (CF breakeven)
        breakeven_month     : int | None
        final_cumulative    : float
        npv_reached         : bool
        npv_breakeven_month : int | None
        final_npv           : float
    """
    cf_breakeven = None
    npv_breakeven = None

    for row in cash_flow_results:
        if cf_breakeven is None and row["cumulative_cash_flow"] >= 0:
            cf_breakeven = row["month"]
        if npv_breakeven is None and row.get("cumulative_npv", -1) >= 0:
            npv_breakeven = row["month"]
        if cf_breakeven is not None and npv_breakeven is not None:
            break

    final = cash_flow_results[-1]["cumulative_cash_flow"] if cash_flow_results else 0.0
    final_npv = cash_flow_results[-1].get("cumulative_npv", 0.0) if cash_flow_results else 0.0

    return {
        "reached": cf_breakeven is not None,
        "breakeven_month": cf_breakeven,
        "final_cumulative": final,
        "npv_reached": npv_breakeven is not None,
        "npv_breakeven_month": npv_breakeven,
        "final_npv": final_npv,
    }
