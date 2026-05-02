"""
KPI-карточки для дашборда Unified Promo Hub.

11 метрик в четырёх строках:
  Строка 1 (3 col): Выручка     | Затраты      | Чистый CF
  Строка 2 (3 col): CF Breakeven| NPV (итог)   | MAU Hub (кон.)
  Строка 3 (3 col): Redemptions | NPV Breakeven| avg_rpu (кон.)
  Строка 4 (2 col): %ACT в MAU Hub            | Нереализованный потенциал пулов
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
    Отображает 11 KPI-карточек над графиками.

    cf_results — результат calculate_cash_flow_for_months()
                 (содержит поля stock-and-flow: avg_rpu, seg_act, mau_hub,
                  pool_web, pool_app из revenue-шага через cash_flow сборку)
    breakeven  — результат calculate_breakeven_month()
    num_months — горизонт расчёта
    """
    if not cf_results:
        st.warning("Нет данных для расчёта KPI.")
        return

    st.markdown(_KPI_CSS, unsafe_allow_html=True)

    total_revenue     = sum(r["revenue"] for r in cf_results)
    total_costs       = sum(r["total_costs"] for r in cf_results)
    net_cf            = sum(r["cash_flow"] for r in cf_results)
    mau_final         = cf_results[-1]["mau_hub"]
    total_redemptions = sum(r["n_redemptions"] for r in cf_results)
    final_npv         = cf_results[-1].get("cumulative_npv", 0.0)

    # Новые метрики из stock-and-flow
    avg_rpu_final     = cf_results[-1].get("avg_rpu", 0.0)
    seg_act_final     = cf_results[-1].get("seg_act", 0.0)
    pct_act_final     = (seg_act_final / mau_final * 100.0) if mau_final > 0 else 0.0
    pool_web_final    = cf_results[-1].get("pool_web", 0.0)
    pool_app_final    = cf_results[-1].get("pool_app", 0.0)
    pool_remaining    = pool_web_final + pool_app_final

    be_month     = breakeven.get("breakeven_month")
    npv_be_month = breakeven.get("npv_breakeven_month")

    # ── Строка 1: Выручка | Затраты | Чистый CF ──────────────────────────────
    r1c1, r1c2, r1c3 = st.columns(3)

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
                "Инкрементальные Fixed Costs (команда + инфра + B2B маркетинг + реферал) "
                "ступенчато по фазам + Variable Costs (₽/redemption)."
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
                f"Чистый денежный поток (не дисконтированный): {format_currency(net_cf)}. "
                "Сумма (Выручка − Затраты) по всем месяцам горизонта."
            ),
        )

    # ── Строка 2: CF Breakeven | NPV | MAU Hub ───────────────────────────────
    r2c1, r2c2, r2c3 = st.columns(3)

    with r2c1:
        if be_month:
            st.metric(
                label="CF Breakeven",
                value=f"Месяц {be_month}",
                delta="достигнут",
                delta_color="normal",
                help=(
                    f"Накопленный CF впервые ≥ 0 в месяце {be_month}. "
                    "Все инвестиции фаз 1–2 окуплены из прибыли Phase 3."
                ),
            )
        else:
            st.metric(
                label="CF Breakeven",
                value="—",
                delta=f"не достигнут за {num_months} мес.",
                delta_color="inverse",
                help=(
                    "Безубыточность не достигается в текущем горизонте. "
                    "Увеличьте горизонт или скорректируйте параметры."
                ),
            )

    with r2c2:
        npv_delta_color = "normal" if final_npv >= 0 else "inverse"
        st.metric(
            label=f"NPV за {num_months} мес.",
            value=format_currency_compact(final_npv),
            delta="положительный" if final_npv >= 0 else "отрицательный",
            delta_color=npv_delta_color,
            help=(
                f"Чистая приведённая стоимость: {format_currency(final_npv)}. "
                "NPV = Σ CF_t / (1 + r_мес)^t, где r_мес = (1 + r_год)^(1/12) − 1. "
                "Положительный NPV → проект создаёт стоимость при заданной ставке."
            ),
        )

    with r2c3:
        st.metric(
            label=f"MAU Hub (конец периода)",
            value=format_number_compact(mau_final),
            help=(
                f"MAU Unified Promo Hub в месяц {num_months}: {mau_final:,.0f} пользователей. "
                "Stock-and-flow: new_app + seg_low + seg_mid + seg_act. "
                "Только авторизованные app-пользователи с атрибуцией CPA/RevShare."
            ),
        )

    # ── Строка 3: Redemptions | NPV Breakeven | avg_rpu ──────────────────────
    r3c1, r3c2, r3c3 = st.columns(3)

    with r3c1:
        st.metric(
            label="Redemptions (суммарно)",
            value=format_number_compact(total_redemptions),
            help=(
                f"Суммарно {total_redemptions:,.0f} redemptions за горизонт. "
                "Каждый redemption = подтверждённое использование оффера "
                "(транзакция атрибутирована T-Bank)."
            ),
        )

    with r3c2:
        if npv_be_month:
            st.metric(
                label="NPV Breakeven",
                value=f"Месяц {npv_be_month}",
                delta="достигнут",
                delta_color="normal",
                help=(
                    f"Накопленный NPV впервые ≥ 0 в месяце {npv_be_month}. "
                    "NPV Breakeven наступает позже CF Breakeven."
                ),
            )
        else:
            st.metric(
                label="NPV Breakeven",
                value="—",
                delta=f"не достигнут за {num_months} мес.",
                delta_color="inverse",
                help=(
                    "NPV не выходит в плюс за текущий горизонт. "
                    "Увеличьте горизонт, снизьте ставку дисконтирования "
                    "или улучшите параметры воронки."
                ),
            )

    with r3c3:
        st.metric(
            label=f"avg_rpu (конец периода)",
            value=f"{avg_rpu_final:.2f} покупок",
            help=(
                f"Динамический avg redemptions per user в месяц {num_months}: "
                f"{avg_rpu_final:.3f} покупок/пользователь. "
                "Рассчитывается как взвешенное среднее по сегментам: "
                "(new_app × rpu_blended + low × purch_low + mid × purch_mid + act × purch_act) / MAU_hub."
            ),
        )

    # ── Строка 4: %ACT | Нереализованный потенциал ───────────────────────────
    r4c1, r4c2 = st.columns(2)

    with r4c1:
        st.metric(
            label=f"Доля ACT в MAU Hub (конец периода)",
            value=f"{pct_act_final:.1f}%",
            help=(
                f"ACT-пользователей (оптимизаторы): {seg_act_final:,.0f} из {mau_final:,.0f} "
                f"({pct_act_final:.1f}%) в месяц {num_months}. "
                "ACT генерируют {:.1f}× больше redemptions, чем LOW. "
                "Целевой показатель: >15% ACT к концу Phase 3.".format(
                    3.0 / 1.0 if 1.0 > 0 else 0
                )
            ),
        )

    with r4c2:
        st.metric(
            label="Остаток пулов (pool_web + pool_app)",
            value=format_number_compact(pool_remaining),
            help=(
                f"Нереализованный потенциал на конец горизонта: {pool_remaining:,.0f} человек. "
                f"pool_web = {pool_web_final:,.0f}, pool_app = {pool_app_final:,.0f}. "
                "Чем меньше остаток, тем больше потенциала конвертировано в MAU Hub. "
                "pool_app всегда большой — 34M × (1−u_app)^N при u_app = 0.5%."
            ),
        )
