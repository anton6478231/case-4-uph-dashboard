"""
KPI-карточки для дашборда Unified Promo Hub.

6 метрик в двух строках по 3 колонки:
  Выручка  |  Затраты      |  Чистый CF
  Breakeven|  MAU Hub (кон)|  N redemptions
"""
import streamlit as st
from typing import List, Dict, Optional
from utils.formatters import (
    format_currency,
    format_currency_compact,
    format_number_compact,
)

_KPI_CSS = """
<style>
section.main div[data-testid="stMetric"] {
    min-width: 0;
    padding: 0.5rem 0.4rem;
    background: #F9FAFB;
    border-radius: 0.5rem;
    border: 1px solid #E5E7EB;
}
section.main div[data-testid="stMetric"] label {
    white-space: normal !important;
    word-break: break-word;
    line-height: 1.3;
    font-size: 0.78rem;
    color: #6B7280;
}
section.main div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    white-space: normal !important;
    word-break: break-word;
    line-height: 1.2;
    font-size: clamp(0.9rem, 2.2vw, 1.2rem);
    font-weight: 700;
    color: #111827;
}
</style>
"""


def display_kpi_cards(
    cf_results: List[Dict],
    breakeven: Dict,
    num_months: int,
):
    """
    Отображает 6 KPI-карточек над графиками.

    cf_results — результат calculate_cash_flow_for_months()
    breakeven  — результат calculate_breakeven_month()
    num_months — горизонт расчёта
    """
    if not cf_results:
        st.warning("Нет данных для расчёта KPI.")
        return

    st.markdown(_KPI_CSS, unsafe_allow_html=True)

    total_revenue = sum(r["revenue"] for r in cf_results)
    total_costs = sum(r["total_costs"] for r in cf_results)
    net_cf = sum(r["cash_flow"] for r in cf_results)
    mau_final = cf_results[-1]["mau_hub"]
    total_redemptions = sum(r["n_redemptions"] for r in cf_results)

    be_month = breakeven["breakeven_month"] if breakeven["reached"] else None

    r1c1, r1c2, r1c3 = st.columns(3)
    r2c1, r2c2, r2c3 = st.columns(3)

    with r1c1:
        st.metric(
            label=f"Выручка за {num_months} мес.",
            value=format_currency_compact(total_revenue),
            help=(
                f"Суммарная выручка за горизонт {num_months} мес: {format_currency(total_revenue)}. "
                "CPA + RevShare × поправку на каннибализацию."
            ),
        )

    with r1c2:
        st.metric(
            label=f"Затраты за {num_months} мес.",
            value=format_currency_compact(total_costs),
            help=(
                f"Суммарные затраты: {format_currency(total_costs)}. "
                "Fixed Costs (ступенчатый рост по фазам) + Variable Costs (₽/redemption)."
            ),
        )

    with r1c3:
        delta_color = "normal" if net_cf >= 0 else "inverse"
        st.metric(
            label=f"Чистый CF за {num_months} мес.",
            value=format_currency_compact(net_cf),
            delta="прибыль" if net_cf >= 0 else "убыток",
            delta_color=delta_color,
            help=(
                f"Чистый денежный поток: {format_currency(net_cf)}. "
                "Сумма (Выручка − Затраты) по всем месяцам горизонта."
            ),
        )

    with r2c1:
        if be_month:
            st.metric(
                label="Breakeven",
                value=f"Месяц {be_month}",
                delta="достигнут",
                delta_color="normal",
                help=(
                    f"Накопленный CF впервые ≥ 0 в месяце {be_month}. "
                    "До этого суммарные затраты превышали выручку."
                ),
            )
        else:
            st.metric(
                label="Breakeven",
                value="—",
                delta=f"не достигнут за {num_months} мес.",
                delta_color="inverse",
                help=(
                    "Безубыточность не достигается в текущем горизонте. "
                    "Увеличьте горизонт или скорректируйте параметры воронки / монетизации."
                ),
            )

    with r2c2:
        st.metric(
            label=f"MAU Hub (конец периода)",
            value=format_number_compact(mau_final),
            help=(
                f"MAU Unified Promo Hub в месяц {num_months}: {mau_final:,.0f} пользователей. "
                "Растёт по S-кривой от Phase 1 к Phase 3."
            ),
        )

    with r2c3:
        st.metric(
            label=f"Redemptions (суммарно)",
            value=format_number_compact(total_redemptions),
            help=(
                f"Суммарно {total_redemptions:,.0f} redemptions за горизонт. "
                "Каждый redemption = подтверждённое использование оффера."
            ),
        )
