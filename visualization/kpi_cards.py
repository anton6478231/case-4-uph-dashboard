"""
KPI-карточки для дашборда Unified Promo Hub.

14 метрик в пяти строках:
  Строка 0 (3 col): ROI год 1   | NPV год 1    | MAU Hub год 1  ← месяц 12 от старта проекта
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
    total_investment: Optional[float] = None,
    roi_year1: Optional[float] = None,
    rnd_months: int = 0,
    final_npv_combined: Optional[float] = None,
    mau_hub_year12: float = 0.0,
    npv_year12: Optional[float] = None,
):
    """
    Отображает KPI-карточки над графиками.

    cf_results          — результат calculate_cash_flow_for_months() (рыночные месяцы)
    breakeven           — результат calculate_breakeven_month()
    num_months          — горизонт расчёта (рыночные месяцы)
    total_investment    — net cash outflow за RnD фазу (None если RnD выключен)
    roi_year1           — ROI за 12 мес. от старта инвестиций (None если RnD выключен)
    rnd_months          — длина RnD фазы (для подписей)
    final_npv_combined  — итоговый NPV с учётом RnD (None → берётся из cf_results)
    mau_hub_year12      — MAU Hub (черная линия: mau_hub + new_web) на проектный месяц 12
    npv_year12          — Накопленный NPV (combined) на проектный месяц 12
    """
    if not cf_results:
        st.warning("Нет данных для расчёта KPI.")
        return

    st.markdown(_KPI_CSS, unsafe_allow_html=True)

    # ── Строка 0: ROI | NPV год 1 | MAU Hub год 1  (месяц 12 от старта проекта) ─
    _year12_market = max(1, 12 - rnd_months)   # номер рыночного месяца, соответствующего году 1
    _y12_label = (
        f"Год 1 — проектный мес. 12"
        + (f" (рынок М{_year12_market})" if rnd_months > 0 else "")
    )
    st.markdown(f"#### 📍 {_y12_label}")
    st.caption(
        "Все три метрики — на 12-й месяц от старта инвестиций (включая RnD фазу), "
        "как видно на графиках. Ось X на графиках: RnD месяцы + рыночные месяцы = единая шкала."
    )
    r0c1, r0c2, r0c3 = st.columns(3)

    with r0c1:
        if roi_year1 is not None:
            roi_delta_color = "normal" if roi_year1 >= 0 else "inverse"
            st.metric(
                label="ROI год 1 (от старта инвестиций)",
                value=f"{roi_year1:.0f}%",
                delta="положительный" if roi_year1 >= 0 else "отрицательный",
                delta_color=roi_delta_color,
                help=(
                    f"ROI = (ΣCF за 12 мес. от инвестиций) / |RnD инвестиции| × 100%. "
                    f"Включает: RnD фазу ({rnd_months} мес.) + рыночные М1..М{_year12_market}. "
                    "Знаменатель — net cash outflow RnD фазы (затраты минус пилотная выручка). "
                    "Положительный ROI означает, что к 12-му месяцу инвестиции окупились."
                ),
            )
        else:
            st.metric(
                label="ROI год 1",
                value="—",
                help="Доступно только при включённой RnD фазе. Включите «RnD / Pre-launch фаза» в боковой панели.",
            )

    with r0c2:
        _npv12 = npv_year12 if npv_year12 is not None else 0.0
        npv12_delta_color = "normal" if _npv12 >= 0 else "inverse"
        st.metric(
            label=f"NPV на проектный мес. 12",
            value=format_currency_compact(_npv12),
            delta="положительный" if _npv12 >= 0 else "отрицательный",
            delta_color=npv12_delta_color,
            help=(
                f"Накопленный дисконтированный NPV на 12-й месяц от старта проекта "
                f"(combined timeline: RnD + рынок). "
                f"Совпадает с точкой М{_year12_market} рыночной шкалы на Графике 1 (Cumulative NPV). "
                "Отрицательный в первые месяцы — норма: RnD инвестиции ещё не отбиты. "
                f"Итоговый NPV за весь горизонт: {format_currency_compact(final_npv_combined or 0)}."
            ),
        )

    with r0c3:
        st.metric(
            label=f"MAU Hub (активный) на мес. 12",
            value=format_number_compact(mau_hub_year12),
            help=(
                f"Суммарный активный охват Hub на проектный месяц 12 "
                f"(рыночный М{_year12_market}): {mau_hub_year12:,.0f} пользователей. "
                "Соответствует чёрной линии на Графике 4 (Сегментная динамика): "
                "mau_hub (app: NEW + LOW + MID + ACT) + new_web (web-only авторизованные). "
                "Именно эта аудитория генерирует выручку через redemptions."
            ),
        )

    st.markdown("---")

    total_revenue     = sum(r["revenue"] for r in cf_results)
    total_costs       = sum(r["total_costs"] for r in cf_results)
    net_cf            = sum(r["cash_flow"] for r in cf_results)
    mau_final         = cf_results[-1]["mau_hub"]
    total_redemptions = sum(r["n_redemptions"] for r in cf_results)
    # NPV: предпочитаем combined (с RnD), иначе только рыночный
    final_npv = (
        final_npv_combined
        if final_npv_combined is not None
        else cf_results[-1].get("cumulative_npv", 0.0)
    )

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
                "4-сценарная модель партнёрских выплат: "
                "NEW (новый клиент партнёра) + LOYAL (лояльный, uplift) + "
                "RET (реактивация ушедшего) + AT_RISK (удержание в зоне оттока) — "
                "× поправку на каннибализацию."
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

    # ── Строка 5: RnD инвестиции (только если RnD включён) ──────────────────────
    if total_investment is not None and total_investment > 0:
        st.markdown("**— RnD фаза —**")
        st.metric(
            label="RnD инвестиции (net outflow)",
            value=format_currency_compact(total_investment),
            help=(
                f"Суммарный net cash outflow за RnD фазу: {format_currency(total_investment)}. "
                f"= Σ затрат за {rnd_months} мес. − пилотная выручка последнего месяца. "
                "Это знаменатель ROI (см. карточку «ROI год 1» выше) и база для combined NPV."
            ),
        )
