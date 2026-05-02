"""
Страница «Калькулятор ФЭМ» — Unified Promo Hub.

Структура:
  1. Боковая панель: 8 блоков параметров (все конфигурируемые)
       Блок 1 — Горизонт планирования
       Блок 2 — Посетители (stock-and-flow: MAU_web, MAU_app, конверсии, миграция)
       Блок 3 — Поведенческие паттерны NEW (w_l/w_m/w_a, purchases per segment)
       Блок 4 — Переходы между сегментами (6 ставок low/mid/act)
       Блок 5 — Воронка конверсии (по фазам)
       Блок 6 — Монетизация
       Блок 7 — Переменные затраты
       Блок 8 — Постоянные затраты
       Блок 9 — Дисконтирование
  2. KPI-карточки (11 метрик, включая avg_rpu, %ACT, остаток пулов)
  3. График 1 — Cash Flow + Cumulative CF + NPV
  4. График 2 — Структура выручки
  5. График 3 — Структура затрат
  6. График 4 — Сегментная динамика (NEW / LOW / MID / ACT stacked area)
  7. Детальная таблица по месяцам (включая сегменты, avg_rpu, пулы)
"""
import json
import streamlit as st
import pandas as pd
from pathlib import Path

from models import (
    calculate_model,
    calculate_costs_for_months,
    calculate_cash_flow_for_months,
    calculate_breakeven_month,
)
from visualization import (
    create_cash_flow_chart,
    create_revenue_breakdown_chart,
    create_costs_structure_chart,
    create_segment_dynamics_chart,
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
    "**Stock-and-flow**: два входных потока (сайт + приложение) → убывающие пулы → "
    "сегменты NEW/LOW/MID/ACT с петлями привычек → динамический avg_rpu → выручка. "
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
    help=(
        "Период, на который строится финансовая модель. "
        "Base = 24 мес. — стандартный горизонт для оценки SaaS/платформ на стадии запуска "
        "(a16z, Sequoia: payback period финтех 6–18 мес.; окупаемость — в первые 12–18 мес.)."
    ),
)
phase1_end = st.sidebar.number_input(
    "Конец Phase 1 (мес.)",
    min_value=1, max_value=num_months,
    value=min(D["horizon"]["phase1_end"], num_months),
    step=1,
    help=(
        "До этого месяца включительно — Phase 1 (запуск). "
        "Base = 3 мес. — минимальный цикл для UX-редизайна + 10–20 Preferred-партнёров + "
        "первичной персонализации. Аналог: Chase Offers MVP-фаза 0–3 мес. (BAI 2024). "
        "Малая аудитория, высокие переменные затраты, CPA-only монетизация."
    ),
)
phase2_end = st.sidebar.number_input(
    "Конец Phase 2 (мес.)",
    min_value=int(phase1_end) + 1, max_value=num_months,
    value=min(D["horizon"]["phase2_end"], num_months),
    step=1,
    help=(
        "До этого месяца — Phase 2 (рост). Base = 9 мес. "
        "Реферал K=0,15–0,25 (Mike Crunch / Reforge 2024), web→app конверсия "
        "платящих 13,6% (AppsFlyer 2024), расширение каталога до 50–150 партнёров."
    ),
)

if phase2_end <= phase1_end:
    phase2_end = phase1_end + 1
    st.sidebar.warning(f"Phase 2 End скорректирован до {phase2_end}")

# --- Блок 2: Посетители (stock-and-flow) ---
st.sidebar.markdown("### 🌐 Посетители (stock-and-flow)")
st.sidebar.caption(
    "Два независимых входных потока. Каждый месяц фиксированное число посетителей "
    "конвертируется в NEW-пользователей из убывающего пула."
)

VM = D["visitor_model"]

mau_web = st.sidebar.number_input(
    "MAU сайта promokod.tbank.ru",
    min_value=10_000, max_value=10_000_000,
    value=int(VM["MAU_web"]),
    step=10_000,
    format="%d",
    help=(
        "Ежемесячные уникальные посетители сайта. Base = 300 000. "
        "Диапазон 200–600k (unit-economics.md §3). "
        "pool_web[0] = MAU_web × (1 − overlap%), т.е. только web-only посетители."
    ),
)
mau_app = st.sidebar.number_input(
    "MAU приложения T-Bank",
    min_value=1_000_000, max_value=100_000_000,
    value=int(VM["MAU_app"]),
    step=1_000_000,
    format="%d",
    help=(
        "Ежемесячная аудитория приложения. Base = 34 000 000 (FY2025 IR T-Bank). "
        "pool_app[0] = MAU_app (перекрытие учтено в pool_web)."
    ),
)
overlap_pct = st.sidebar.slider(
    "Перекрытие web ∩ app (%)",
    min_value=0.0, max_value=80.0,
    value=float(VM["overlap_web_app_pct"]),
    step=1.0,
    help=(
        "Доля посетителей сайта, которые уже используют приложение. Base = 30%. "
        "Вычитается из pool_web при инициализации, чтобы не двойной счёт: "
        "pool_web[0] = MAU_web × (1 − overlap/100)."
    ),
)
u_to_a_web = st.sidebar.slider(
    "Конверсия сайт → NEW (%/мес)",
    min_value=0.1, max_value=20.0,
    value=float(VM["u_to_a_new_web"]),
    step=0.1,
    help=(
        "Доля остатка pool_web, конвертирующаяся в NEW каждый месяц. Base = 4.0%. "
        "Регистрация на сайте; ниже ~5% soft-gate (unit-economics.md §3). "
        "fresh_web[m] = pool_web[m−1] × u_to_a_new_web/100."
    ),
)
u_to_a_app = st.sidebar.slider(
    "Конверсия приложение → NEW (%/мес)",
    min_value=0.01, max_value=5.0,
    value=float(VM["u_to_a_new_app"]),
    step=0.01,
    help=(
        "Доля остатка pool_app, конвертирующаяся в NEW каждый месяц. Base = 0.5%. "
        "0.5% × 34M = 170k/мес в Phase 1; согласуется с target MAU_hub = 1.5M за 9 мес. "
        "fresh_app[m] = pool_app[m−1] × u_to_a_new_app/100."
    ),
)
web_to_app = st.sidebar.slider(
    "Миграция web → app (%/мес)",
    min_value=0.0, max_value=60.0,
    value=float(VM["web_to_app"]),
    step=1.0,
    help=(
        "Доля накопленных new_web-пользователей, переходящих в app каждый месяц. Base = 20%. "
        "Soft-gate CTA «скачайте приложение» → 15–25% (AppsFlyer 2025). "
        "Мигранты: graduating[m] += new_web[m−1] × web_to_app/100. "
        "ВАЖНО: мигранты НЕ добавляются в new_app[m] — только через graduating, нет двойного счёта."
    ),
)

# --- Блок 3: Поведенческие паттерны NEW ---
st.sidebar.markdown("### 🧩 Поведенческие паттерны NEW")
st.sidebar.caption(
    "Распределение новых пользователей по поведенческому паттерну в первый месяц. "
    "Покупок — условное среднее среди redeemers. Сумма w_l + w_m + w_a = 100%."
)

SW = D["segment_weights"]
PS = D["purchases_per_segment"]

w_l = st.sidebar.slider(
    "Доля LOW (пассивные) в NEW (%)",
    min_value=0, max_value=100,
    value=int(SW["w_l"]),
    step=1,
    help=(
        "% новых с низкой частотой (Пассивный + часть Ситуативных). Base = 60%. "
        "~60% новых имеют низкую частоту (user-personas.md §1.3). "
        "Петля: триггер — транзакция/push → 1 взаимодействие/мес."
    ),
)
w_m = st.sidebar.slider(
    "Доля MID (ситуативные) в NEW (%)",
    min_value=0, max_value=100,
    value=int(SW["w_m"]),
    step=1,
    help=(
        "% новых — Ситуативные/Плановики. Base = 30%. "
        "Петля: триггер — категория-оффер совпал → 1–2 взаимодействия/мес."
    ),
)
w_a = 100 - w_l - w_m
weights_sum = w_l + w_m + w_a
if weights_sum != 100:
    st.sidebar.error(f"⚠️ w_l + w_m + w_a = {weights_sum}% ≠ 100%. w_a автоматически = {100 - w_l - w_m}%.")
else:
    st.sidebar.success(f"✅ w_l({w_l}%) + w_m({w_m}%) + w_a({w_a}%) = 100%")

st.sidebar.caption(f"**w_a (ACT)** = 100 − w_l − w_m = **{w_a}%** (Оптимизаторы)")

purch_low = st.sidebar.slider(
    "Покупок/мес у LOW",
    min_value=0.1, max_value=5.0,
    value=float(PS["purchases_low"]),
    step=0.1,
    help=(
        "Условное среднее redemptions/мес среди redeemers LOW. Base = 1.0. "
        "Редкое использование; conditional среди redeemers."
    ),
)
purch_mid = st.sidebar.slider(
    "Покупок/мес у MID",
    min_value=0.1, max_value=10.0,
    value=float(PS["purchases_mid"]),
    step=0.1,
    help=(
        "Условное среднее redemptions/мес среди redeemers MID. Base = 1.5. "
        "1–2 раза в месяц — ситуативное применение при подходящей категории."
    ),
)
purch_act = st.sidebar.slider(
    "Покупок/мес у ACT",
    min_value=0.1, max_value=15.0,
    value=float(PS["purchases_act"]),
    step=0.1,
    help=(
        "Условное среднее redemptions/мес среди redeemers ACT. Base = 3.0. "
        "Несколько офферов в месяц; data flywheel — чем больше использует, "
        "тем точнее NBP-персонализация."
    ),
)
rpu_blended_preview = (w_l * purch_low + w_m * purch_mid + w_a * purch_act) / 100.0
st.sidebar.caption(f"rpu_new_blended (месяц 1) = **{rpu_blended_preview:.2f}**")

# --- Блок 4: Переходы между сегментами ---
st.sidebar.markdown("### 🔄 Переходы между сегментами (%/мес)")
st.sidebar.caption(
    "Ежемесячные вероятности перехода. Outflow-суммы не могут превышать 100%."
)

ST = D["segment_transitions"]

with st.sidebar.expander("LOW → другие сегменты", expanded=False):
    low_to_mid = st.slider(
        "LOW → MID (%)", key="low_to_mid",
        min_value=0, max_value=80,
        value=int(ST["low_to_mid"]),
        help=(
            "LOW → MID: лёгкий переход (1 взаимодействие). Base = 20%. "
            "user-personas.md §1.5: ⬜ авто-триггер при 1+ активации оффера."
        ),
    )
    low_to_act = st.slider(
        "LOW → ACT (%)", key="low_to_act",
        min_value=0, max_value=50,
        value=int(ST["low_to_act"]),
        help=(
            "LOW → ACT: сложный переход (2+ применённых оффера). Base = 3%. "
            "user-personas.md §1.5: 🔴 редкий скачок; маловероятен без NBP-буста."
        ),
    )
    low_outflow = low_to_mid + low_to_act
    if low_outflow > 100:
        st.error(f"⚠️ Outflow LOW = {low_outflow}% > 100%!")
    else:
        st.success(f"✅ Outflow LOW = {low_outflow}% (удержание {100 - low_outflow}%)")

with st.sidebar.expander("MID → другие сегменты", expanded=False):
    mid_to_low = st.slider(
        "MID → LOW (%)", key="mid_to_low",
        min_value=0, max_value=50,
        value=int(ST["mid_to_low"]),
        help=(
            "MID → LOW: авто-даунгрейд при нет активности 60 дней. Base = 12%. "
            "user-personas.md §1.5: ⬜ авто-триггер."
        ),
    )
    mid_to_act = st.slider(
        "MID → ACT (%)", key="mid_to_act",
        min_value=0, max_value=50,
        value=int(ST["mid_to_act"]),
        help=(
            "MID → ACT: NBP-попадание в зону планирования. Base = 15%. "
            "user-personas.md §1.5: 🔴 требует персонализованного оффера."
        ),
    )
    mid_outflow = mid_to_low + mid_to_act
    if mid_outflow > 100:
        st.error(f"⚠️ Outflow MID = {mid_outflow}% > 100%!")
    else:
        st.success(f"✅ Outflow MID = {mid_outflow}% (удержание {100 - mid_outflow}%)")

with st.sidebar.expander("ACT → другие сегменты", expanded=False):
    act_to_low = st.slider(
        "ACT → LOW (%)", key="act_to_low",
        min_value=0, max_value=30,
        value=int(ST["act_to_low"]),
        help=(
            "ACT → LOW: нет активности > 90 дней. Base = 2%. "
            "user-personas.md §1.5: ⬜ ACT защищён дольше всего — 90-дневное окно."
        ),
    )
    act_to_mid = st.slider(
        "ACT → MID (%)", key="act_to_mid",
        min_value=0, max_value=30,
        value=int(ST["act_to_mid"]),
        help=(
            "ACT → MID: < 2 сессий/мес за 60 дней. Base = 8%. "
            "user-personas.md §1.5: ⬜ авто-триггер охлаждения."
        ),
    )
    act_outflow = act_to_low + act_to_mid
    if act_outflow > 100:
        st.error(f"⚠️ Outflow ACT = {act_outflow}% > 100%!")
    else:
        st.success(f"✅ Outflow ACT = {act_outflow}% (удержание {100 - act_outflow}%)")

# --- Блок 5: Воронка конверсии ---
st.sidebar.markdown("### 🔽 Воронка конверсии")

FN = D["funnel"]

with st.sidebar.expander("Phase 1 — Воронка", expanded=False):
    fn_p1_cov = st.slider(
        "Offer Coverage (%)", key="fn_p1_cov",
        min_value=10.0, max_value=100.0,
        value=float(FN["p1_offer_coverage"]), step=1.0,
        help=(
            "% MAU Hub, получивших ≥1 релевантный оффер. "
            "Base = 60% (Phase 1: каталог 10–20 Preferred-партнёров). "
            "СберСпасибо: 50% охват ML-персонализации (Ведомости.Капитал, апрель 2025)."
        ),
    )
    fn_p1_ctr = st.slider(
        "CTR оффера (%)", key="fn_p1_ctr",
        min_value=1.0, max_value=40.0,
        value=float(FN["p1_ctr_offer"]), step=0.5,
        help=(
            "% пользователей, кликнувших на оффер. "
            "Base = 12% (Phase 1, без персонализации). "
            "Batch Benchmark 2025: in-app promo card CTR = 16,1% Android / 17,9% iOS."
        ),
    )
    fn_p1_rr = st.slider(
        "Redemption Rate (%)", key="fn_p1_rr",
        min_value=1.0, max_value=60.0,
        value=float(FN["p1_redemption_rate"]), step=0.5,
        help=(
            "% применивших оффер. Base = 15% (Phase 1, холодная аудитория). "
            "Inmar digital coupon redemption 5,9–10% (США) + РФ-поправка +40–50% = 8–15%."
        ),
    )
    fn_p1_conv = fn_p1_cov / 100 * fn_p1_ctr / 100 * fn_p1_rr / 100
    st.metric("Сквозная конверсия P1", f"{fn_p1_conv * 100:.3f}%")

with st.sidebar.expander("Phase 2 — Воронка", expanded=False):
    fn_p2_cov = st.slider(
        "Offer Coverage (%)", key="fn_p2_cov",
        min_value=10.0, max_value=100.0,
        value=float(FN["p2_offer_coverage"]), step=1.0,
        help=(
            "Phase 2: каталог 50–150 партнёров → охват 75% категорий. Base = 75%. "
            "При 50+ партнёрах покрываются еда, fashion, маркетплейсы, путешествия, здоровье."
        ),
    )
    fn_p2_ctr = st.slider(
        "CTR оффера (%)", key="fn_p2_ctr",
        min_value=1.0, max_value=40.0,
        value=float(FN["p2_ctr_offer"]), step=0.5,
        help=(
            "Phase 2: ранняя персонализация NBP. Base = 14%. "
            "Batch 2025: in-app promo card 16,1–17,9%; персонализация push: +344% engagement."
        ),
    )
    fn_p2_rr = st.slider(
        "Redemption Rate (%)", key="fn_p2_rr",
        min_value=1.0, max_value=60.0,
        value=float(FN["p2_redemption_rate"]), step=0.5,
        help=(
            "Phase 2: аудитория прогревается. Base = 20%. "
            "Cardlytics/Five Guys: персональные офферы → +30% repeat sales за 90 дней."
        ),
    )
    fn_p2_conv = fn_p2_cov / 100 * fn_p2_ctr / 100 * fn_p2_rr / 100
    st.metric("Сквозная конверсия P2", f"{fn_p2_conv * 100:.3f}%")

with st.sidebar.expander("Phase 3 — Воронка", expanded=False):
    fn_p3_cov = st.slider(
        "Offer Coverage (%)", key="fn_p3_cov",
        min_value=10.0, max_value=100.0,
        value=float(FN["p3_offer_coverage"]), step=1.0,
        help=(
            "Phase 3: зрелый каталог 500+ партнёров + CLO auto-match. Base = 90%. "
            "Бенчмарк: Rakuten — 3 500+ магазинов (rakuten.com 2025)."
        ),
    )
    fn_p3_ctr = st.slider(
        "CTR оффера (%)", key="fn_p3_ctr",
        min_value=1.0, max_value=40.0,
        value=float(FN["p3_ctr_offer"]), step=0.5,
        help=(
            "Phase 3: полный NBP, таргетинг по транзакциям. Base = 18%. "
            "Batch 2025: in-app promo card CTR 16,1–17,9%; персонализация с именем: +2× CTR."
        ),
    )
    fn_p3_rr = st.slider(
        "Redemption Rate (%)", key="fn_p3_rr",
        min_value=1.0, max_value=60.0,
        value=float(FN["p3_redemption_rate"]), step=0.5,
        help=(
            "Phase 3: CLO auto-apply поднимает конверсию. Base = 28%. "
            "Baymard: CLO устраняет friction → redemption rate ×1,5–2× vs промокода."
        ),
    )
    fn_p3_conv = fn_p3_cov / 100 * fn_p3_ctr / 100 * fn_p3_rr / 100
    st.metric("Сквозная конверсия P3", f"{fn_p3_conv * 100:.3f}%")

# --- Блок 6: Монетизация ---
st.sidebar.markdown("### 💰 Монетизация")

cpa_avg = st.sidebar.slider(
    "Средний CPA (₽)",
    min_value=50, max_value=2000,
    value=D["monetization"]["cpa_avg"],
    step=10,
    help=(
        "Средняя ставка за verified redemption в CPA-кампаниях. Base = 500 ₽. "
        "Admitad/ActualTraffic РФ 2025: Яндекс.Плюс новый = 500 ₽, Кинопоиск = 436 ₽."
    ),
)
aov_avg = st.sidebar.slider(
    "Средний AOV (₽)",
    min_value=200, max_value=15000,
    value=D["monetization"]["aov_avg"],
    step=100,
    help=(
        "Средний чек в RevShare-кампаниях. Base = 2 000 ₽ (blended по каталогу). "
        "Data Insight Топ-100 интернет-магазинов 2024: еда = 2 070 ₽, WB = 870 ₽."
    ),
)
revshare_avg = st.sidebar.slider(
    "RevShare (%)",
    min_value=0.5, max_value=15.0,
    value=float(D["monetization"]["revshare_avg"]),
    step=0.5,
    help=(
        "% от AOV, который партнёр платит за redemption. Base = 5%. "
        "Honey/PayPal: cashback ставки 2–5%; Rakuten US: 1–10%, медиана ~6%."
    ),
)
share_cpa = st.sidebar.slider(
    "Доля CPA-кампаний (%)",
    min_value=0.0, max_value=100.0,
    value=float(D["monetization"]["share_cpa"]),
    step=1.0,
    help=(
        "% redemptions по CPA (остаток — RevShare). Base = 70%. "
        "На старте Acquisition + Reactivation доминируют → CPA primary."
    ),
)
incremental_adj = st.sidebar.slider(
    "Поправка на каннибализацию",
    min_value=0.50, max_value=1.00,
    value=float(D["monetization"]["incremental_adj"]),
    step=0.01,
    help=(
        "Коэффициент incrementality. Base = 0,87 (87% выручки — истинно новая). "
        "unit-economics.md §6.3: 10–15% каннибализации из кэшбэк-бюджетов."
    ),
)

# --- Блок 7: Переменные затраты ---
st.sidebar.markdown("### 📦 Переменные затраты (₽/redemption)")
st.sidebar.caption(
    "Инкрементальные затраты на 1 redemption: T-Bank уже имеет инфраструктуру "
    "(push, ML platform, antifraud) — учитываем только прирост."
)

vc_p1 = st.sidebar.slider(
    "Phase 1 — VC/redemption (₽)",
    min_value=5, max_value=100,
    value=D["variable_costs"]["vc_per_redemption_p1"],
    step=1,
    help=(
        "Инкрементальные затраты на 1 redemption в Phase 1. Base = 22 ₽. "
        "push ~3 + inference ~4 + attribution ~3 + antifraud ~3 + support ~9 = 22 ₽."
    ),
)
vc_p2 = st.sidebar.slider(
    "Phase 2 — VC/redemption (₽)",
    min_value=5, max_value=100,
    value=D["variable_costs"]["vc_per_redemption_p2"],
    step=1,
    help=(
        "Инкрементальные затраты на 1 redemption в Phase 2. Base = 16 ₽. "
        "Batch-inference снижает стоимость vs real-time на ~30%."
    ),
)
vc_p3 = st.sidebar.slider(
    "Phase 3 — VC/redemption (₽)",
    min_value=1, max_value=80,
    value=D["variable_costs"]["vc_per_redemption_p3"],
    step=1,
    help=(
        "Инкрементальные затраты на 1 redemption в Phase 3. Base = 10 ₽. "
        "Batch ML inference при высоком объёме; CLO auto-apply."
    ),
)

# --- Блок 8: Постоянные затраты ---
st.sidebar.markdown("### 🏢 Инкрементальные постоянные затраты (₽/мес)")
st.sidebar.caption(
    "Только прирост к текущим расходам Т-Банка: новые FTE, "
    "дополнительная инфра, B2B-маркетинг, реферальный бюджет."
)

FC = D["fixed_costs"]

with st.sidebar.expander("Phase 1 — Fixed Costs (итого ~6 млн/мес)", expanded=False):
    fc_p1_team = st.number_input(
        "Команда (₽/мес)", key="fc_p1_team",
        min_value=0, max_value=200_000_000,
        value=FC["p1_team"], step=500_000, format="%d",
        help="7 FTE × ~500 тыс. full-cost = 3,5 млн ₽/мес. Base = 3 500 000.",
    )
    fc_p1_infra = st.number_input(
        "Инфраструктура (₽/мес)", key="fc_p1_infra",
        min_value=0, max_value=100_000_000,
        value=FC["p1_infra"], step=100_000, format="%d",
        help="Инкрементальный CDN/ML inference/PostgreSQL. Base = 800 000.",
    )
    fc_p1_marketing = st.number_input(
        "Маркетинг B2B (₽/мес)", key="fc_p1_marketing",
        min_value=0, max_value=100_000_000,
        value=FC["p1_marketing"], step=100_000, format="%d",
        help="1–2 Partnership Manager + юридические расходы. Base = 1 200 000.",
    )
    fc_p1_referral = st.number_input(
        "Реферальная программа (₽/мес)", key="fc_p1_referral",
        min_value=0, max_value=50_000_000,
        value=FC["p1_referral"], step=100_000, format="%d",
        help="Реферальные бонусы Phase 1. Base = 500 000.",
    )
    fc_p1 = fc_p1_team + fc_p1_infra + fc_p1_marketing + fc_p1_referral
    st.metric("Итого Phase 1", f"{fc_p1 / 1_000_000:.1f} млн ₽/мес")

with st.sidebar.expander("Phase 2 — Fixed Costs (итого ~15 млн/мес)", expanded=False):
    fc_p2_team = st.number_input(
        "Команда (₽/мес)", key="fc_p2_team",
        min_value=0, max_value=200_000_000,
        value=FC["p2_team"], step=500_000, format="%d",
        help="15 FTE × ~530 тыс. full-cost = 8 млн ₽/мес. Base = 8 000 000.",
    )
    fc_p2_infra = st.number_input(
        "Инфраструктура (₽/мес)", key="fc_p2_infra",
        min_value=0, max_value=100_000_000,
        value=FC["p2_infra"], step=500_000, format="%d",
        help="Real-time NBP serving 3.2M MAU. Base = 2 500 000.",
    )
    fc_p2_marketing = st.number_input(
        "Маркетинг B2B (₽/мес)", key="fc_p2_marketing",
        min_value=0, max_value=100_000_000,
        value=FC["p2_marketing"], step=500_000, format="%d",
        help="Набор 50–150 партнёров, API-интеграции. Base = 3 000 000.",
    )
    fc_p2_referral = st.number_input(
        "Реферальная программа (₽/мес)", key="fc_p2_referral",
        min_value=0, max_value=50_000_000,
        value=FC["p2_referral"], step=500_000, format="%d",
        help="Рост реферальных бонусов Phase 2. Base = 1 500 000.",
    )
    fc_p2 = fc_p2_team + fc_p2_infra + fc_p2_marketing + fc_p2_referral
    st.metric("Итого Phase 2", f"{fc_p2 / 1_000_000:.1f} млн ₽/мес")

with st.sidebar.expander("Phase 3 — Fixed Costs (итого ~27 млн/мес)", expanded=False):
    fc_p3_team = st.number_input(
        "Команда (₽/мес)", key="fc_p3_team",
        min_value=0, max_value=300_000_000,
        value=FC["p3_team"], step=500_000, format="%d",
        help="25 FTE × ~560 тыс. full-cost = 14 млн ₽/мес. Base = 14 000 000.",
    )
    fc_p3_infra = st.number_input(
        "Инфраструктура (₽/мес)", key="fc_p3_infra",
        min_value=0, max_value=150_000_000,
        value=FC["p3_infra"], step=500_000, format="%d",
        help="CLO-интеграции, batch ML pipeline 6.5M MAU. Base = 5 000 000.",
    )
    fc_p3_marketing = st.number_input(
        "Маркетинг B2B (₽/мес)", key="fc_p3_marketing",
        min_value=0, max_value=100_000_000,
        value=FC["p3_marketing"], step=500_000, format="%d",
        help="Стратегические CLO-партнёрства, co-marketing. Base = 5 000 000.",
    )
    fc_p3_referral = st.number_input(
        "Реферальная программа (₽/мес)", key="fc_p3_referral",
        min_value=0, max_value=100_000_000,
        value=FC["p3_referral"], step=500_000, format="%d",
        help="Зрелая реферальная петля Phase 3. Base = 3 000 000.",
    )
    fc_p3 = fc_p3_team + fc_p3_infra + fc_p3_marketing + fc_p3_referral
    st.metric("Итого Phase 3", f"{fc_p3 / 1_000_000:.1f} млн ₽/мес")

# --- Блок 9: Дисконтирование ---
st.sidebar.markdown("### 📈 Дисконтирование (NPV)")

annual_discount_rate = st.sidebar.slider(
    "Ставка дисконтирования (% год.)",
    min_value=5.0, max_value=50.0,
    value=float(D["discount"]["annual_rate_pct"]),
    step=1.0,
    help=(
        "Годовая ставка дисконтирования. Base = 20% годовых. "
        "ЦБ РФ ключевая ставка: 21% (апрель 2026) → WACC финтех ≈ 18–24%."
    ),
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Сбросить к дефолтам"):
    st.cache_data.clear()
    st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Guardrail: веса сегментов
# ──────────────────────────────────────────────────────────────────────────────

if weights_sum != 100:
    st.error(
        f"⚠️ Сумма весов сегментов NEW = {weights_sum}% ≠ 100%. "
        f"w_a (ACT) автоматически = {w_a}%. Исправьте w_l и w_m в боковой панели."
    )
    st.stop()

if low_to_mid + low_to_act > 100:
    st.error(f"⚠️ Outflow из LOW = {low_to_mid + low_to_act}% > 100%. Исправьте переходы LOW.")
    st.stop()
if mid_to_low + mid_to_act > 100:
    st.error(f"⚠️ Outflow из MID = {mid_to_low + mid_to_act}% > 100%. Исправьте переходы MID.")
    st.stop()
if act_to_low + act_to_mid > 100:
    st.error(f"⚠️ Outflow из ACT = {act_to_low + act_to_mid}% > 100%. Исправьте переходы ACT.")
    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Сборка params — единый словарь для всех модулей
# ──────────────────────────────────────────────────────────────────────────────

params = {
    # Горизонт
    "num_months":  int(num_months),
    "phase1_end":  int(phase1_end),
    "phase2_end":  int(phase2_end),
    # Посетители (stock-and-flow)
    "MAU_web":            float(mau_web),
    "MAU_app":            float(mau_app),
    "overlap_web_app_pct": float(overlap_pct),
    "u_to_a_new_web":     float(u_to_a_web),
    "u_to_a_new_app":     float(u_to_a_app),
    "web_to_app":         float(web_to_app),
    # Веса и покупки по сегментам
    "w_l": float(w_l),
    "w_m": float(w_m),
    "w_a": float(w_a),
    "purchases_low":  float(purch_low),
    "purchases_mid":  float(purch_mid),
    "purchases_act":  float(purch_act),
    # Переходы
    "low_to_mid": float(low_to_mid),
    "low_to_act": float(low_to_act),
    "mid_to_low": float(mid_to_low),
    "mid_to_act": float(mid_to_act),
    "act_to_low": float(act_to_low),
    "act_to_mid": float(act_to_mid),
    # Воронка (по фазам)
    "p1_offer_coverage":  float(fn_p1_cov),
    "p1_ctr_offer":       float(fn_p1_ctr),
    "p1_redemption_rate": float(fn_p1_rr),
    "p2_offer_coverage":  float(fn_p2_cov),
    "p2_ctr_offer":       float(fn_p2_ctr),
    "p2_redemption_rate": float(fn_p2_rr),
    "p3_offer_coverage":  float(fn_p3_cov),
    "p3_ctr_offer":       float(fn_p3_ctr),
    "p3_redemption_rate": float(fn_p3_rr),
    # Монетизация
    "cpa_avg":        float(cpa_avg),
    "aov_avg":        float(aov_avg),
    "revshare_avg":   float(revshare_avg),
    "share_cpa":      float(share_cpa),
    "incremental_adj": float(incremental_adj),
    # Переменные затраты
    "vc_per_redemption_p1": float(vc_p1),
    "vc_per_redemption_p2": float(vc_p2),
    "vc_per_redemption_p3": float(vc_p3),
    # Постоянные затраты (агрегированные по фазе)
    "fixed_cost_p1": float(fc_p1),
    "fixed_cost_p2": float(fc_p2),
    "fixed_cost_p3": float(fc_p3),
}


# ──────────────────────────────────────────────────────────────────────────────
# Расчёт модели
# ──────────────────────────────────────────────────────────────────────────────

try:
    revenue_results = calculate_model(params, int(num_months))
except ValueError as e:
    st.error(f"❌ Ошибка модели: {e}")
    st.stop()

costs_results = calculate_costs_for_months(params, revenue_results)
cf_results = calculate_cash_flow_for_months(
    revenue_results,
    costs_results,
    annual_discount_rate=float(annual_discount_rate),
)
breakeven = calculate_breakeven_month(cf_results)

# Обогащаем cf_results полями из revenue_results для KPI-карточек и таблицы
_rev_map = {r["month"]: r for r in revenue_results}
for row in cf_results:
    rev = _rev_map.get(row["month"], {})
    row.setdefault("avg_rpu",    rev.get("avg_rpu", 0.0))
    row.setdefault("new_web",    rev.get("new_web", 0.0))
    row.setdefault("new_app",    rev.get("new_app", 0.0))
    row.setdefault("graduating", rev.get("graduating", 0.0))
    row.setdefault("seg_low",    rev.get("seg_low", 0.0))
    row.setdefault("seg_mid",    rev.get("seg_mid", 0.0))
    row.setdefault("seg_act",    rev.get("seg_act", 0.0))
    row.setdefault("pool_web",   rev.get("pool_web", 0.0))
    row.setdefault("pool_app",   rev.get("pool_app", 0.0))


# ──────────────────────────────────────────────────────────────────────────────
# Краткая сводка в сайдбаре
# ──────────────────────────────────────────────────────────────────────────────

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Сводка")
total_rev    = sum(r["revenue"] for r in cf_results)
total_cost   = sum(r["total_costs"] for r in cf_results)
net_cf_total = sum(r["cash_flow"] for r in cf_results)
final_npv    = cf_results[-1]["cumulative_npv"] if cf_results else 0.0
mau_end      = cf_results[-1]["mau_hub"] if cf_results else 0.0
avg_rpu_end  = cf_results[-1]["avg_rpu"] if cf_results else 0.0
seg_act_end  = cf_results[-1]["seg_act"] if cf_results else 0.0
pct_act_end  = (seg_act_end / mau_end * 100.0) if mau_end > 0 else 0.0

st.sidebar.markdown(f"**Выручка:** {format_currency_compact(total_rev)}")
st.sidebar.markdown(f"**Затраты:** {format_currency_compact(total_cost)}")
cf_color = "green" if net_cf_total >= 0 else "red"
st.sidebar.markdown(f"**Net CF:** :{cf_color}[{format_currency_compact(net_cf_total)}]")
npv_color = "green" if final_npv >= 0 else "red"
st.sidebar.markdown(f"**NPV:** :{npv_color}[{format_currency_compact(final_npv)}]")
if breakeven["reached"]:
    st.sidebar.markdown(f"**Breakeven:** :green[Месяц {breakeven['breakeven_month']}]")
else:
    st.sidebar.markdown(f"**Breakeven:** :red[Не достигнут за {num_months} мес.]")
st.sidebar.markdown(f"**MAU Hub (кон.):** {format_number_compact(mau_end)}")
st.sidebar.markdown(f"**avg_rpu (кон.):** {avg_rpu_end:.2f}")
st.sidebar.markdown(f"**%ACT (кон.):** {pct_act_end:.1f}%")


# ──────────────────────────────────────────────────────────────────────────────
# KPI-карточки
# ──────────────────────────────────────────────────────────────────────────────

display_kpi_cards(cf_results, breakeven, int(num_months))

st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# Информационный блок: текущие параметры
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
        st.markdown("**Stock-and-Flow**")
        st.markdown(f"- MAU_web: **{format_number_compact(mau_web)}**")
        st.markdown(f"- MAU_app: **{format_number_compact(mau_app)}**")
        st.markdown(f"- Overlap: **{overlap_pct:.0f}%**")
        st.markdown(f"- u_web/u_app: **{u_to_a_web:.1f}% / {u_to_a_app:.2f}%**")
        st.markdown(f"- web→app: **{web_to_app:.0f}%**")
    with col3:
        st.markdown("**Сегменты**")
        st.markdown(f"- w_l/w_m/w_a: **{w_l}/{w_m}/{w_a}%**")
        st.markdown(f"- purch_low/mid/act: **{purch_low:.1f}/{purch_mid:.1f}/{purch_act:.1f}**")
        st.markdown(f"- rpu_blended(m=1): **{rpu_blended_preview:.2f}**")
        st.markdown(f"- Фазы: M1–{phase1_end} / M{int(phase1_end)+1}–{phase2_end} / M{int(phase2_end)+1}–{num_months}")


# ──────────────────────────────────────────────────────────────────────────────
# График 1 — Cash Flow
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("График 1 — Cash Flow и NPV по месяцам")
st.plotly_chart(
    create_cash_flow_chart(cf_results, int(phase1_end), int(phase2_end)),
    use_container_width=True,
)
st.markdown(
    "> **Как читать:** зелёная линия (Выручка) пересекает красную (Затраты) — операционный breakeven. "
    "Фиолетовый пунктир (Cumulative CF) — накопленный поток. "
    "Оранжевый пунктир (Cumulative NPV) — дисконтированный поток."
)
st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# График 4 — Сегментная динамика
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("График 4 — Сегментная динамика: NEW / LOW / MID / ACT")
st.plotly_chart(
    create_segment_dynamics_chart(revenue_results, int(phase1_end), int(phase2_end)),
    use_container_width=True,
)
st.markdown(
    "> **Как читать:** каждый цвет — сегмент по поведенческому паттерну. "
    "Серый (NEW) — свежие app-пользователи этого месяца. "
    "Синий (LOW) — пассивные. Жёлтый (MID) — ситуативные. Зелёный (ACT) — оптимизаторы. "
    "Рост зелёного сегмента к концу горизонта — ключевой индикатор зрелости продукта."
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
    "> **Как читать:** синие сегменты (CPA) доминируют на старте. "
    "Зелёные (RevShare) растут по мере подключения Strategic-партнёров с высоким AOV."
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
    "> **Как читать:** красные сегменты (Fixed) — ступенчатый рост при переходе между фазами. "
    "Жёлтые (Variable) — нелинейный рост с числом redemptions. "
    "Variable costs на единицу снижаются с масштабом."
)
st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# Детальная таблица
# ──────────────────────────────────────────────────────────────────────────────

with st.expander("📋 Детальная таблица по месяцам", expanded=False):
    rows = []
    for r in cf_results:
        mau_h = r["mau_hub"]
        s_act = r.get("seg_act", 0.0)
        pct_a = (s_act / mau_h * 100.0) if mau_h > 0 else 0.0
        rows.append({
            "Мес.":             r["month"],
            "Фаза":             f"Phase {r['phase']}",
            "pool_web":         f"{r.get('pool_web', 0):,.0f}",
            "pool_app":         f"{r.get('pool_app', 0):,.0f}",
            "new_web":          f"{r.get('new_web', 0):,.0f}",
            "new_app":          f"{r.get('new_app', 0):,.0f}",
            "graduating":       f"{r.get('graduating', 0):,.0f}",
            "seg_LOW":          f"{r.get('seg_low', 0):,.0f}",
            "seg_MID":          f"{r.get('seg_mid', 0):,.0f}",
            "seg_ACT":          f"{s_act:,.0f}",
            "%ACT":             f"{pct_a:.1f}%",
            "MAU Hub":          f"{mau_h:,.0f}",
            "avg_rpu":          f"{r.get('avg_rpu', 0):.2f}",
            "Redemptions":      f"{r['n_redemptions']:,.0f}",
            "CPA (₽)":         f"{r['revenue_cpa']:,.0f}",
            "RS (₽)":          f"{r['revenue_rs']:,.0f}",
            "Выручка (₽)":     f"{r['revenue']:,.0f}",
            "Fixed (₽)":       f"{r['fixed_costs']:,.0f}",
            "Variable (₽)":    f"{r['variable_costs']:,.0f}",
            "Затраты (₽)":     f"{r['total_costs']:,.0f}",
            "CF мес. (₽)":     f"{r['cash_flow']:,.0f}",
            "Cum. CF (₽)":     f"{r['cumulative_cash_flow']:,.0f}",
            "Disc. f.":         f"{r['discount_factor']:.4f}",
            "PV(CF) (₽)":      f"{r['discounted_cash_flow']:,.0f}",
            "Cum. NPV (₽)":    f"{r['cumulative_npv']:,.0f}",
        })
    df = pd.DataFrame(rows)

    def _highlight_cf(val):
        try:
            num = float(val.replace(" ", "").replace(",", "").replace("%", ""))
            if num < 0:
                return "color: #EF4444"
            if num > 0:
                return "color: #10B981"
        except Exception:
            pass
        return ""

    styled = df.style.map(
        _highlight_cf,
        subset=["CF мес. (₽)", "Cum. CF (₽)", "PV(CF) (₽)", "Cum. NPV (₽)"]
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
