"""
Страница «Калькулятор ФЭМ» — Unified Promo Hub.

Структура:
  1. Боковая панель: 6 блоков параметров (все конфигурируемые)
  2. KPI-карточки (6 метрик)
  3. График 1 — Cash Flow
  4. График 2 — Структура выручки
  5. График 3 — Структура затрат
  6. Детальная таблица по месяцам
"""
import json
import streamlit as st
import pandas as pd
from pathlib import Path

from models import (
    calculate_revenue_for_months,
    calculate_costs_for_months,
    calculate_cash_flow_for_months,
    calculate_breakeven_month,
)
from visualization import (
    create_cash_flow_chart,
    create_revenue_breakdown_chart,
    create_costs_structure_chart,
    display_kpi_cards,
)
from utils import format_currency, format_currency_compact, format_number_compact


# ──────────────────────────────────────────────────────────────────────────────
# Загрузка defaults
# ──────────────────────────────────────────────────────────────────────────────

def load_defaults() -> dict:
    path = Path(__file__).parent.parent / "config" / "defaults.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


D = load_defaults()


# ──────────────────────────────────────────────────────────────────────────────
# Заголовок страницы
# ──────────────────────────────────────────────────────────────────────────────

st.title("Калькулятор ФЭМ — Unified Promo Hub")
st.markdown(
    "Финансово-экономическая модель платформы промокодов Т-Банка. "
    "Все параметры настраиваются в панели слева — модель пересчитывается автоматически."
)
st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# Боковая панель
# ──────────────────────────────────────────────────────────────────────────────

st.sidebar.header("⚙️ Параметры модели")
st.sidebar.caption("Измените любой параметр — все графики и KPI пересчитаются мгновенно.")

# --- Блок 1: Горизонт планирования ---
st.sidebar.markdown("### 📅 Горизонт планирования")

num_months = st.sidebar.slider(
    "Горизонт расчёта (мес.)",
    min_value=1, max_value=36,
    value=D["horizon"]["num_months"],
    help="Период, на который строится финансовая модель.",
)
phase1_end = st.sidebar.number_input(
    "Конец Phase 1 (мес.)",
    min_value=1, max_value=num_months,
    value=min(D["horizon"]["phase1_end"], num_months),
    step=1,
    help=(
        "До этого месяца включительно — Phase 1 (запуск). "
        "Малая аудитория, высокие переменные затраты, CPA-only."
    ),
)
phase2_end = st.sidebar.number_input(
    "Конец Phase 2 (мес.)",
    min_value=int(phase1_end) + 1, max_value=num_months,
    value=min(D["horizon"]["phase2_end"], num_months),
    step=1,
    help=(
        "До этого месяца — Phase 2 (рост). "
        "Реферал, web→app конверсия, расширение каталога."
    ),
)

# Защита от некорректного соотношения
if phase2_end <= phase1_end:
    phase2_end = phase1_end + 1
    st.sidebar.warning(f"Phase 2 End скорректирован до {phase2_end}")

# --- Блок 2: База аудитории ---
st.sidebar.markdown("### 👥 Аудитория")

mau_tbank = st.sidebar.number_input(
    "MAU T-Bank (базовая аудитория)",
    min_value=1_000_000, max_value=100_000_000,
    value=D["audience"]["mau_tbank"],
    step=1_000_000,
    format="%d",
    help="Общая ежемесячная аудитория Т-Банка. Источник: IR-отчёты FY2025 (~34 млн).",
)
mau_p1 = st.sidebar.slider(
    "Проникновение Phase 1 (%)",
    min_value=0.5, max_value=30.0,
    value=float(D["audience"]["mau_penetration_p1"]),
    step=0.1,
    help=(
        "% MAU T-Bank, пользующихся хабом в Phase 1. "
        "Дефолт 4.4% ≈ 1.5 млн — бенчмарк «buried section» в банковских приложениях."
    ),
)
mau_p2 = st.sidebar.slider(
    "Проникновение Phase 2 (%)",
    min_value=float(mau_p1), max_value=50.0,
    value=max(float(D["audience"]["mau_penetration_p2"]), float(mau_p1)),
    step=0.1,
    help=(
        "% MAU T-Bank в Phase 2. Дефолт 9.4% ≈ 3.2 млн. "
        "Рост за счёт реферальной петли и web→app конверсии."
    ),
)
mau_p3 = st.sidebar.slider(
    "Проникновение Phase 3 (%)",
    min_value=float(mau_p2), max_value=70.0,
    value=max(float(D["audience"]["mau_penetration_p3"]), float(mau_p2)),
    step=0.1,
    help=(
        "% MAU T-Bank в Phase 3. Дефолт 19% ≈ 6.5 млн. "
        "Self-serve кабинет, CLO-интеграции, cross-sell из других продуктов."
    ),
)

# --- Блок 3: Воронка конверсии ---
st.sidebar.markdown("### 🔽 Воронка конверсии")

FN = D["funnel"]

with st.sidebar.expander("Phase 1 — Воронка", expanded=False):
    fn_p1_cov = st.slider(
        "Offer Coverage (%)", key="fn_p1_cov",
        min_value=10.0, max_value=100.0,
        value=float(FN["p1_offer_coverage"]), step=1.0,
        help="% MAU Hub с ≥1 релевантным оффером. Phase 1: каталог ограничен ~60%.",
    )
    fn_p1_ctr = st.slider(
        "CTR оффера (%)", key="fn_p1_ctr",
        min_value=1.0, max_value=40.0,
        value=float(FN["p1_ctr_offer"]), step=0.5,
        help="% кликнувших. Phase 1: без персонализации ~12%.",
    )
    fn_p1_rr = st.slider(
        "Redemption Rate (%)", key="fn_p1_rr",
        min_value=1.0, max_value=60.0,
        value=float(FN["p1_redemption_rate"]), step=0.5,
        help="% применивших оффер. Phase 1: холодная аудитория ~15%.",
    )
    fn_p1_conv = fn_p1_cov / 100 * fn_p1_ctr / 100 * fn_p1_rr / 100
    st.metric("Сквозная конверсия P1", f"{fn_p1_conv * 100:.3f}%")

with st.sidebar.expander("Phase 2 — Воронка", expanded=False):
    fn_p2_cov = st.slider(
        "Offer Coverage (%)", key="fn_p2_cov",
        min_value=10.0, max_value=100.0,
        value=float(FN["p2_offer_coverage"]), step=1.0,
        help="Phase 2: каталог растёт, NBP начинает работать ~75%.",
    )
    fn_p2_ctr = st.slider(
        "CTR оффера (%)", key="fn_p2_ctr",
        min_value=1.0, max_value=40.0,
        value=float(FN["p2_ctr_offer"]), step=0.5,
        help="Phase 2: ранняя персонализация NBP ~14%.",
    )
    fn_p2_rr = st.slider(
        "Redemption Rate (%)", key="fn_p2_rr",
        min_value=1.0, max_value=60.0,
        value=float(FN["p2_redemption_rate"]), step=0.5,
        help="Phase 2: аудитория прогревается, реферальная петля ~20%.",
    )
    fn_p2_conv = fn_p2_cov / 100 * fn_p2_ctr / 100 * fn_p2_rr / 100
    st.metric("Сквозная конверсия P2", f"{fn_p2_conv * 100:.3f}%")

with st.sidebar.expander("Phase 3 — Воронка", expanded=False):
    fn_p3_cov = st.slider(
        "Offer Coverage (%)", key="fn_p3_cov",
        min_value=10.0, max_value=100.0,
        value=float(FN["p3_offer_coverage"]), step=1.0,
        help="Phase 3: зрелый каталог + CLO auto-match ~90%.",
    )
    fn_p3_ctr = st.slider(
        "CTR оффера (%)", key="fn_p3_ctr",
        min_value=1.0, max_value=40.0,
        value=float(FN["p3_ctr_offer"]), step=0.5,
        help="Phase 3: полный NBP, таргетинг по транзакциям ~18%.",
    )
    fn_p3_rr = st.slider(
        "Redemption Rate (%)", key="fn_p3_rr",
        min_value=1.0, max_value=60.0,
        value=float(FN["p3_redemption_rate"]), step=0.5,
        help="Phase 3: CLO auto-apply поднимает до ~28%; промокод ~20%.",
    )
    fn_p3_conv = fn_p3_cov / 100 * fn_p3_ctr / 100 * fn_p3_rr / 100
    st.metric("Сквозная конверсия P3", f"{fn_p3_conv * 100:.3f}%")

# --- Блок 4: Монетизация ---
st.sidebar.markdown("### 💰 Монетизация")

cpa_avg = st.sidebar.slider(
    "Средний CPA (₽)",
    min_value=50, max_value=2000,
    value=D["monetization"]["cpa_avg"],
    step=10,
    help=(
        "Средняя ставка за verified redemption в CPA-кампаниях. "
        "Диапазон: 150–1 200 ₽. Дефолт 500 ₽ — Acquisition + Reactivation."
    ),
)
aov_avg = st.sidebar.slider(
    "Средний AOV (₽)",
    min_value=200, max_value=15000,
    value=D["monetization"]["aov_avg"],
    step=100,
    help=(
        "Средний чек в RevShare-кампаниях. "
        "Еда ~800 ₽, fashion ~3 500 ₽, электроника ~8 000 ₽."
    ),
)
revshare_avg = st.sidebar.slider(
    "RevShare (%)",
    min_value=0.5, max_value=15.0,
    value=float(D["monetization"]["revshare_avg"]),
    step=0.5,
    help=(
        "% от AOV, который партнёр платит за redemption в RevShare-модели. "
        "Бенчмарк: Honey 2–5%, Rakuten 1–10%."
    ),
)
share_cpa = st.sidebar.slider(
    "Доля CPA-кампаний (%)",
    min_value=0.0, max_value=100.0,
    value=float(D["monetization"]["share_cpa"]),
    step=1.0,
    help=(
        "% redemptions, оплачиваемых по CPA (остаток — RevShare). "
        "На старте ~70% CPA (acquisition доминирует). "
        "В Phase 3 смещается к RevShare по мере роста Strategic-партнёров."
    ),
)
incremental_adj = st.sidebar.slider(
    "Поправка на каннибализацию",
    min_value=0.50, max_value=1.00,
    value=float(D["monetization"]["incremental_adj"]),
    step=0.01,
    help=(
        "Коэффициент incrementality: 0.87 означает, что 87% выручки — "
        "истинно новая, 13% — перераспределение из существующих кешбек-контрактов Т-Банка."
    ),
)

# --- Блок 5: Переменные затраты ---
st.sidebar.markdown("### 📦 Переменные затраты (₽/redemption)")

vc_p1 = st.sidebar.slider(
    "Phase 1 — VC/redemption (₽)",
    min_value=5, max_value=100,
    value=D["variable_costs"]["vc_per_redemption_p1"],
    step=1,
    help=(
        "Затраты на 1 redemption в Phase 1: push (~8 ₽) + NBP inference (~5 ₽) + "
        "attribution (~3 ₽) + antifraud (~5 ₽) + support (~15 ₽) ≈ 36 ₽."
    ),
)
vc_p2 = st.sidebar.slider(
    "Phase 2 — VC/redemption (₽)",
    min_value=5, max_value=100,
    value=D["variable_costs"]["vc_per_redemption_p2"],
    step=1,
    help="Снижается за счёт оптимизации: batch-inference, CDN-кеш, автоматизация модерации.",
)
vc_p3 = st.sidebar.slider(
    "Phase 3 — VC/redemption (₽)",
    min_value=1, max_value=80,
    value=D["variable_costs"]["vc_per_redemption_p3"],
    step=1,
    help="Phase 3: ML-inference дешевеет с объёмом, real-time → batch, меньше ручной поддержки.",
)

# --- Блок 6: Постоянные затраты ---
st.sidebar.markdown("### 🏢 Постоянные затраты (₽/мес)")

FC = D["fixed_costs"]

# Phase 1
with st.sidebar.expander("Phase 1 — Fixed Costs", expanded=False):
    fc_p1_team = st.number_input(
        "Команда (₽/мес)", key="fc_p1_team",
        min_value=0, max_value=200_000_000,
        value=FC["p1_team"], step=500_000, format="%d",
        help="ФОТ ~10–15 FTE: инженеры, дата-аналитик, PM, дизайнер, sales.",
    )
    fc_p1_infra = st.number_input(
        "Инфраструктура (₽/мес)", key="fc_p1_infra",
        min_value=0, max_value=100_000_000,
        value=FC["p1_infra"], step=500_000, format="%d",
        help="Облако, CDN, ML inference, мониторинг.",
    )
    fc_p1_marketing = st.number_input(
        "Маркетинг B2B (₽/мес)", key="fc_p1_marketing",
        min_value=0, max_value=100_000_000,
        value=FC["p1_marketing"], step=500_000, format="%d",
        help="Партнёрские переговоры, pitch-материалы, B2B events.",
    )
    fc_p1_referral = st.number_input(
        "Реферальная программа (₽/мес)", key="fc_p1_referral",
        min_value=0, max_value=50_000_000,
        value=FC["p1_referral"], step=500_000, format="%d",
        help="Бюджет реферальных бонусов для пользователей.",
    )
    fc_p1 = fc_p1_team + fc_p1_infra + fc_p1_marketing + fc_p1_referral
    st.metric("Итого Phase 1", f"{fc_p1 / 1_000_000:.1f} млн ₽/мес")

# Phase 2
with st.sidebar.expander("Phase 2 — Fixed Costs", expanded=False):
    fc_p2_team = st.number_input(
        "Команда (₽/мес)", key="fc_p2_team",
        min_value=0, max_value=200_000_000,
        value=FC["p2_team"], step=500_000, format="%d",
        help="ФОТ ~25 FTE: рост B2B sales, ML-инженеры, analytics.",
    )
    fc_p2_infra = st.number_input(
        "Инфраструктура (₽/мес)", key="fc_p2_infra",
        min_value=0, max_value=100_000_000,
        value=FC["p2_infra"], step=500_000, format="%d",
        help="Масштабирование облака, real-time recommendation serving.",
    )
    fc_p2_marketing = st.number_input(
        "Маркетинг B2B (₽/мес)", key="fc_p2_marketing",
        min_value=0, max_value=100_000_000,
        value=FC["p2_marketing"], step=500_000, format="%d",
        help="B2B sales активируется, партнёрские интеграции.",
    )
    fc_p2_referral = st.number_input(
        "Реферальная программа (₽/мес)", key="fc_p2_referral",
        min_value=0, max_value=50_000_000,
        value=FC["p2_referral"], step=500_000, format="%d",
        help="Рост реферальных бонусов с масштабом аудитории.",
    )
    fc_p2 = fc_p2_team + fc_p2_infra + fc_p2_marketing + fc_p2_referral
    st.metric("Итого Phase 2", f"{fc_p2 / 1_000_000:.1f} млн ₽/мес")

# Phase 3
with st.sidebar.expander("Phase 3 — Fixed Costs", expanded=False):
    fc_p3_team = st.number_input(
        "Команда (₽/мес)", key="fc_p3_team",
        min_value=0, max_value=300_000_000,
        value=FC["p3_team"], step=500_000, format="%d",
        help="ФОТ ~40–60 FTE: self-serve кабинет, Strategic CLO, платформа.",
    )
    fc_p3_infra = st.number_input(
        "Инфраструктура (₽/мес)", key="fc_p3_infra",
        min_value=0, max_value=150_000_000,
        value=FC["p3_infra"], step=500_000, format="%d",
        help="CLO-интеграции, batch ML pipeline, высоконагруженный бэкенд.",
    )
    fc_p3_marketing = st.number_input(
        "Маркетинг B2B (₽/мес)", key="fc_p3_marketing",
        min_value=0, max_value=100_000_000,
        value=FC["p3_marketing"], step=500_000, format="%d",
        help="Стратегические партнёрства, co-marketing кампании.",
    )
    fc_p3_referral = st.number_input(
        "Реферальная программа (₽/мес)", key="fc_p3_referral",
        min_value=0, max_value=100_000_000,
        value=FC["p3_referral"], step=500_000, format="%d",
        help="Зрелая реферальная петля с вирусным коэффициентом.",
    )
    fc_p3 = fc_p3_team + fc_p3_infra + fc_p3_marketing + fc_p3_referral
    st.metric("Итого Phase 3", f"{fc_p3 / 1_000_000:.1f} млн ₽/мес")

# Кнопка сброса к дефолтам
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Сбросить к дефолтам"):
    st.cache_data.clear()
    st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Сборка params — единый словарь для всех модулей
# ──────────────────────────────────────────────────────────────────────────────

params = {
    # Горизонт
    "num_months": int(num_months),
    "phase1_end": int(phase1_end),
    "phase2_end": int(phase2_end),
    # Аудитория
    "mau_tbank": float(mau_tbank),
    "mau_penetration_p1": float(mau_p1),
    "mau_penetration_p2": float(mau_p2),
    "mau_penetration_p3": float(mau_p3),
    # Воронка (по фазам)
    "p1_offer_coverage": float(fn_p1_cov),
    "p1_ctr_offer": float(fn_p1_ctr),
    "p1_redemption_rate": float(fn_p1_rr),
    "p2_offer_coverage": float(fn_p2_cov),
    "p2_ctr_offer": float(fn_p2_ctr),
    "p2_redemption_rate": float(fn_p2_rr),
    "p3_offer_coverage": float(fn_p3_cov),
    "p3_ctr_offer": float(fn_p3_ctr),
    "p3_redemption_rate": float(fn_p3_rr),
    # Монетизация
    "cpa_avg": float(cpa_avg),
    "aov_avg": float(aov_avg),
    "revshare_avg": float(revshare_avg),
    "share_cpa": float(share_cpa),
    "incremental_adj": float(incremental_adj),
    # Переменные затраты
    "vc_per_redemption_p1": float(vc_p1),
    "vc_per_redemption_p2": float(vc_p2),
    "vc_per_redemption_p3": float(vc_p3),
    # Постоянные затраты
    "fixed_cost_p1": float(fc_p1),
    "fixed_cost_p2": float(fc_p2),
    "fixed_cost_p3": float(fc_p3),
}


# ──────────────────────────────────────────────────────────────────────────────
# Расчёт модели
# ──────────────────────────────────────────────────────────────────────────────

revenue_results = calculate_revenue_for_months(params, int(num_months))
costs_results = calculate_costs_for_months(params, revenue_results)
cf_results = calculate_cash_flow_for_months(revenue_results, costs_results)
breakeven = calculate_breakeven_month(cf_results)


# ──────────────────────────────────────────────────────────────────────────────
# Краткая сводка в сайдбаре
# ──────────────────────────────────────────────────────────────────────────────

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Сводка")
total_rev = sum(r["revenue"] for r in cf_results)
total_cost = sum(r["total_costs"] for r in cf_results)
net_cf_total = sum(r["cash_flow"] for r in cf_results)

st.sidebar.markdown(f"**Выручка:** {format_currency_compact(total_rev)}")
st.sidebar.markdown(f"**Затраты:** {format_currency_compact(total_cost)}")
cf_color = "green" if net_cf_total >= 0 else "red"
st.sidebar.markdown(f"**Net CF:** :{cf_color}[{format_currency_compact(net_cf_total)}]")
if breakeven["reached"]:
    st.sidebar.markdown(f"**Breakeven:** :green[Месяц {breakeven['breakeven_month']}]")
else:
    st.sidebar.markdown(f"**Breakeven:** :red[Не достигнут за {num_months} мес.]")


# ──────────────────────────────────────────────────────────────────────────────
# KPI-карточки
# ──────────────────────────────────────────────────────────────────────────────

display_kpi_cards(cf_results, breakeven, int(num_months))

st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# Информационный блок: текущие параметры воронки
# ──────────────────────────────────────────────────────────────────────────────

with st.expander("📐 Параметры расчёта (текущие значения)", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Воронка по фазам**")
        st.markdown(f"- P1: Cov {fn_p1_cov:.0f}% · CTR {fn_p1_ctr:.1f}% · RR {fn_p1_rr:.1f}% → **{fn_p1_conv*100:.3f}%**")
        st.markdown(f"- P2: Cov {fn_p2_cov:.0f}% · CTR {fn_p2_ctr:.1f}% · RR {fn_p2_rr:.1f}% → **{fn_p2_conv*100:.3f}%**")
        st.markdown(f"- P3: Cov {fn_p3_cov:.0f}% · CTR {fn_p3_ctr:.1f}% · RR {fn_p3_rr:.1f}% → **{fn_p3_conv*100:.3f}%**")
        st.markdown(f"- Каннибализация: **{incremental_adj:.2f}**")
    with col2:
        st.markdown("**Монетизация**")
        st.markdown(f"- CPA_avg: **{format_currency(cpa_avg)}**")
        st.markdown(f"- AOV_avg: **{format_currency(aov_avg)}**")
        st.markdown(f"- RevShare: **{revshare_avg:.1f}%**")
        st.markdown(f"- Доля CPA: **{share_cpa:.0f}%**")
    with col3:
        st.markdown("**Фазы**")
        st.markdown(f"- Phase 1: М1–{phase1_end}")
        st.markdown(f"- Phase 2: М{int(phase1_end)+1}–{phase2_end}")
        st.markdown(f"- Phase 3: М{int(phase2_end)+1}–{num_months}")
        mau_end = cf_results[-1]["mau_hub"] if cf_results else 0
        st.markdown(f"- MAU Hub (конец): **{format_number_compact(mau_end)}**")


# ──────────────────────────────────────────────────────────────────────────────
# График 1 — Cash Flow
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("График 1 — Cash Flow по месяцам")
st.plotly_chart(
    create_cash_flow_chart(cf_results, int(phase1_end), int(phase2_end)),
    use_container_width=True,
)

st.markdown(
    "> **Как читать:** зелёная линия (Выручка) должна пересечь красную (Затраты) — "
    "это операционный breakeven. Фиолетовый пунктир (Cumulative CF) пересекает ноль — "
    "это точка окупаемости инвестиций."
)

st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# График 2 — Структура выручки
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("График 2 — Структура выручки: CPA vs RevShare")
st.plotly_chart(
    create_revenue_breakdown_chart(cf_results, int(phase1_end), int(phase2_end)),
    use_container_width=True,
)

st.markdown(
    "> **Как читать:** синие сегменты (CPA) доминируют на старте — партнёры платят за "
    "guaranteed-new клиентов. Зелёные сегменты (RevShare) растут по мере подключения "
    "Strategic-партнёров с высоким AOV."
)

st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# График 3 — Структура затрат
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("График 3 — Структура затрат: Fixed vs Variable")
st.plotly_chart(
    create_costs_structure_chart(cf_results, int(phase1_end), int(phase2_end)),
    use_container_width=True,
)

st.markdown(
    "> **Как читать:** красные сегменты (Fixed) — ступенчатый рост при переходе между фазами "
    "(команда, инфраструктура). Жёлтые (Variable) — нелинейный рост с числом redemptions. "
    "Разрыв между суммой затрат и выручкой — EBITDA."
)

st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# Детальная таблица
# ──────────────────────────────────────────────────────────────────────────────

with st.expander("📋 Детальная таблица по месяцам", expanded=False):
    rows = []
    for r in cf_results:
        rows.append({
            "Месяц": r["month"],
            "Фаза": f"Phase {r['phase']}",
            "MAU Hub": f"{r['mau_hub']:,.0f}",
            "Redemptions": f"{r['n_redemptions']:,.0f}",
            "Выручка CPA (₽)": f"{r['revenue_cpa']:,.0f}",
            "Выручка RevShare (₽)": f"{r['revenue_rs']:,.0f}",
            "Выручка итого (₽)": f"{r['revenue']:,.0f}",
            "Fixed Costs (₽)": f"{r['fixed_costs']:,.0f}",
            "Variable Costs (₽)": f"{r['variable_costs']:,.0f}",
            "Total Costs (₽)": f"{r['total_costs']:,.0f}",
            "Cash Flow (₽)": f"{r['cash_flow']:,.0f}",
            "Cumulative CF (₽)": f"{r['cumulative_cash_flow']:,.0f}",
        })
    df = pd.DataFrame(rows)

    def highlight_cf(val):
        try:
            num = float(val.replace(" ", "").replace(",", ""))
            if num < 0:
                return "color: #EF4444"
            if num > 0:
                return "color: #10B981"
        except Exception:
            pass
        return ""

    styled = df.style.map(highlight_cf, subset=["Cash Flow (₽)", "Cumulative CF (₽)"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
