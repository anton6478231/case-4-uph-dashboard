"""
Модуль RnD-фазы: расходы до старта продаж (pre-launch).

Логика:
  - RnD фаза предшествует рыночной (market) фазе.
  - Месяц 1..N-1: только постоянные расходы, выручка = 0.
  - Последний месяц N: пилот на малой выборке → есть pilot_revenue.
  - Суммарные инвестиции = все RnD затраты − пилотная прибыль
    (net cash outflow за фазу).
  - NPV рыночных месяцев дисконтируется со сдвигом rnd_months
    (через month_offset в cash_flow.py).

Ключевые типы:

RnDCostsMatrix — dict[category_name -> list[float]]
    Ключ: название категории.
    Значение: список затрат длиной rnd_months (индекс = RnD месяц − 1).

RnDMonthResult — результат одного RnD месяца, phase="RnD".
"""

from __future__ import annotations

from typing import Dict, List


# ──────────────────────────────────────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────────────────────────────────────

RND_PHASE_LABEL = "RnD"
MARKET_PHASE_LABEL = "market"

MAX_RND_MONTHS = 12

DEFAULT_RND_CATEGORIES: List[str] = [
    "Зарплаты команды",
    "Инфраструктура",
    "Разработка/тестирование",
    "Прочие расходы RnD",
]


# ──────────────────────────────────────────────────────────────────────────────
# Основные функции
# ──────────────────────────────────────────────────────────────────────────────

def calculate_RnD_cash_flows(
    rnd_months: int,
    costs_matrix: Dict[str, List[float]],
    pilot_revenue: float = 0.0,
) -> List[Dict]:
    """
    Вычисляет денежный поток за каждый RnD месяц.

    Args:
        rnd_months:     количество RnD месяцев (≥ 1).
        costs_matrix:   {category_name: [cost_m1, cost_m2, ...]},
                        длина ≥ rnd_months; лишние игнорируются, недостающие = 0.
        pilot_revenue:  выручка от пилота в последнем RnD месяце (₽).

    Returns:
        Список словарей длиной rnd_months:
            month               — порядковый номер RnD месяца (1-based)
            phase               — "RnD"
            revenue             — 0.0 (месяцы 1..N-1) или pilot_revenue (месяц N)
            total_costs         — суммарные расходы месяца (₽)
            cash_flow           — revenue − total_costs (отрицательный в месяцах 1..N-1)
            cumulative_cash_flow — нарастающий итог CF с начала RnD
            breakdown           — {category_name: cost} для данного месяца
    """
    results: List[Dict] = []
    cumulative = 0.0

    for m in range(1, rnd_months + 1):
        breakdown: Dict[str, float] = {}
        for cat, monthly_list in costs_matrix.items():
            idx = m - 1
            val = float(monthly_list[idx]) if idx < len(monthly_list) else 0.0
            breakdown[cat] = val

        total_costs = sum(breakdown.values())

        # Последний RnD месяц — пилот с малой выборкой
        rev = pilot_revenue if m == rnd_months else 0.0
        cf = rev - total_costs
        cumulative += cf

        results.append({
            "month":                m,
            "phase":                RND_PHASE_LABEL,
            "revenue":              rev,
            "total_costs":          total_costs,
            "cash_flow":            cf,
            "cumulative_cash_flow": cumulative,
            "breakdown":            breakdown,
        })

    return results


def get_total_RnD_investment(
    costs_matrix: Dict[str, List[float]],
    rnd_months: int,
    pilot_revenue: float = 0.0,
) -> float:
    """
    Суммарные net-инвестиции RnD фазы (net cash outflow).

    total_investment = Σ затрат за все RnD месяцы − pilot_revenue
    Всегда ≥ 0 при корректных входах (расходы > пилотной выручки).
    """
    total_costs = sum(
        float(monthly_list[idx]) if idx < len(monthly_list) else 0.0
        for monthly_list in costs_matrix.values()
        for idx in range(rnd_months)
    )
    return max(0.0, total_costs - pilot_revenue)


def get_RnD_cost_by_month(
    costs_matrix: Dict[str, List[float]],
    rnd_months: int,
) -> List[float]:
    """Суммарные затраты RnD по каждому месяцу."""
    monthly_totals = []
    for m_idx in range(rnd_months):
        s = sum(
            float(vals[m_idx]) if m_idx < len(vals) else 0.0
            for vals in costs_matrix.values()
        )
        monthly_totals.append(s)
    return monthly_totals


def ensure_matrix_size(
    costs_matrix: Dict[str, List[float]],
    rnd_months: int,
) -> Dict[str, List[float]]:
    """
    Гарантирует, что каждый список в матрице имеет длину ровно rnd_months.
    Недостающие значения заполняются 0, лишние обрезаются.
    """
    result = {}
    for cat, vals in costs_matrix.items():
        padded = list(vals)
        while len(padded) < rnd_months:
            padded.append(0.0)
        result[cat] = padded[:rnd_months]
    return result


def build_empty_matrix(
    categories: List[str],
    rnd_months: int,
) -> Dict[str, List[float]]:
    """Создаёт нулевую матрицу расходов RnD."""
    return {cat: [0.0] * rnd_months for cat in categories}
