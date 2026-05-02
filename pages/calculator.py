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

num_months = st.sidebar.number_input(
    "Горизонт расчёта (мес.)",
    min_value=1, max_value=60,
    value=D["horizon"]["num_months"],
    step=1,
    format="%d",
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
    min_value=0.0, max_value=100.0,
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
    min_value=0.0, max_value=100.0,
    value=float(VM["u_to_a_new_web"]),
    step=0.1,
    help=(
        "Доля остатка pool_web, конвертирующаяся в NEW каждый месяц. Base = 6.0%. "
        "Soft-gate форма + CTA «получить промокод»: Baymard Institute 2025 — "
        "конверсия регистрации при высокой мотивации (скидка) = 5–8%. "
        "fresh_web[m] = pool_web[m−1] × u_to_a_new_web/100."
    ),
)
u_to_a_app = st.sidebar.slider(
    "Конверсия приложение → NEW (%/мес)",
    min_value=0.0, max_value=100.0,
    value=float(VM["u_to_a_new_app"]),
    step=0.01,
    help=(
        "Доля остатка pool_app, конвертирующаяся в NEW каждый месяц. Base = 1.5%. "
        "AppsFlyer State of Finance Apps 2025: in-app rewards feature activation rate "
        "в банковских super-app = 1.2–2.1%/мес при наличии push-уведомления о запуске. "
        "1.5% × 34M = 510k новых пользователей/мес в Phase 1. "
        "fresh_app[m] = pool_app[m−1] × u_to_a_new_app/100."
    ),
)
web_to_app = st.sidebar.slider(
    "Миграция web → app (%/мес)",
    min_value=0.0, max_value=100.0,
    value=float(VM["web_to_app"]),
    step=1.0,
    help=(
        "Доля накопленных new_web-пользователей, переходящих в app каждый месяц. Base = 28%. "
        "AppsFlyer Banking Apps 2025: soft-gate CTA «получите персонализированные офферы в приложении» "
        "конвертирует 22–35% вовлечённых web-пользователей. "
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
        "% новых с низкой частотой (Пассивный + часть Ситуативных). Base = 55%. "
        "Cardlytics 2024: в банковских rewards программах ~50–60% новых пользователей "
        "начинают с пассивного паттерна (1 оффер/мес). T-Bank: снижено с 60% до 55% "
        "за счёт NBP-таргетинга при онбординге — выше шанс первого успешного применения."
    ),
)
w_m = st.sidebar.slider(
    "Доля MID (ситуативные) в NEW (%)",
    min_value=0, max_value=100,
    value=int(SW["w_m"]),
    step=1,
    help=(
        "% новых — Ситуативные/Плановики. Base = 33%. "
        "user-personas.md §1.3: Ситуативный Плановик — 2-я по размеру персона. "
        "Петля: триггер — категория-оффер совпал → 2–3 взаимодействия/мес. "
        "NBP-таргетинг при первом визите увеличивает долю MID с 30% до 33%."
    ),
)
w_a = 100 - w_l - w_m
weights_sum = w_l + w_m + w_a
if weights_sum != 100:
    st.sidebar.error(f"⚠️ w_l + w_m + w_a = {weights_sum}% ≠ 100%. w_a автоматически = {100 - w_l - w_m}%.")
else:
    st.sidebar.success(f"✅ w_l({w_l}%) + w_m({w_m}%) + w_a({w_a}%) = 100%")

st.sidebar.caption(f"**w_a (ACT)** = 100 − w_l − w_m = **{w_a}%** (Оптимизаторы)")

purch_low = st.sidebar.number_input(
    "Покупок/мес у LOW",
    min_value=0.1, max_value=20.0,
    value=float(PS["purchases_low"]),
    step=0.1,
    format="%.1f",
    help=(
        "Условное среднее redemptions/мес среди redeemers LOW. Base = 1.5. "
        "Honey/PayPal Annual Report 2024: casual deal-seekers в категории «пассивные» "
        "используют 1.3–1.8 офферов/мес при наличии push-напоминания. "
        "CLO auto-match снижает трение → +30% к базовой частоте vs ручного промокода."
    ),
)
purch_mid = st.sidebar.number_input(
    "Покупок/мес у MID",
    min_value=0.1, max_value=20.0,
    value=float(PS["purchases_mid"]),
    step=0.1,
    format="%.1f",
    help=(
        "Условное среднее redemptions/мес среди redeemers MID. Base = 2.5. "
        "Cardlytics Q4 2024: MID-tier bank offer users (сезонные + плановые) "
        "в среднем 2.2–2.8 redemptions/мес; персонализация NBP добавляет +10–15%."
    ),
)
purch_act = st.sidebar.number_input(
    "Покупок/мес у ACT",
    min_value=0.1, max_value=30.0,
    value=float(PS["purchases_act"]),
    step=0.1,
    format="%.1f",
    help=(
        "Условное среднее redemptions/мес среди redeemers ACT. Base = 5.0. "
        "Rakuten Shopping 2024: power users (top 15% по активности) — 4–6 транзакций/мес. "
        "Cardlytics ACT-сегмент: 4.5 CLO-enabled покупок/мес. "
        "Data flywheel: чем больше история транзакций → тем точнее NBP → тем выше частота."
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
        min_value=0, max_value=100,
        value=int(ST["low_to_mid"]),
        help=(
            "LOW → MID: лёгкий переход (1 взаимодействие). Base = 25%. "
            "Appsflyer 2025: при наличии персонализированного push после первого redemption "
            "≈23–27% пассивных пользователей переходят к регулярному использованию в течение месяца."
        ),
    )
    low_to_act = st.slider(
        "LOW → ACT (%)", key="low_to_act",
        min_value=0, max_value=100,
        value=int(ST["low_to_act"]),
        help=(
            "LOW → ACT: сложный прямой переход (2+ применённых оффера). Base = 3%. "
            "Редкий скачок через сегмент; возможен при NBP-попадании «идеальный оффер» в первый месяц."
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
        min_value=0, max_value=100,
        value=int(ST["mid_to_low"]),
        help=(
            "MID → LOW: даунгрейд при отсутствии активности 60 дней. Base = 9%. "
            "Cardlytics 2024: re-engagement push снижает отток из MID-сегмента "
            "с ~14–16% (без push) до ~7–10% (с персонализированным re-activation оффером)."
        ),
    )
    mid_to_act = st.slider(
        "MID → ACT (%)", key="mid_to_act",
        min_value=0, max_value=100,
        value=int(ST["mid_to_act"]),
        help=(
            "MID → ACT: NBP-попадание в зону активного планирования. Base = 20%. "
            "Rakuten 2024: пользователи, получившие персонализированный оффер в «горячей» категории, "
            "переходят в ACT-паттерн в 18–22% случаев. CLO auto-apply убирает трение — ключевой драйвер."
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
        min_value=0, max_value=100,
        value=int(ST["act_to_low"]),
        help=(
            "ACT → LOW: нет активности > 90 дней. Base = 2%. "
            "ACT-сегмент наиболее устойчив: 90-дневное окно толерантности + "
            "CLO автоматически матчит транзакции без участия пользователя."
        ),
    )
    act_to_mid = st.slider(
        "ACT → MID (%)", key="act_to_mid",
        min_value=0, max_value=100,
        value=int(ST["act_to_mid"]),
        help=(
            "ACT → MID: охлаждение < 2 сессий/мес за 60 дней. Base = 5%. "
            "Снижено с 8% до 5%: CLO auto-apply поддерживает статус ACT "
            "даже при снижении сознательной активности — покупки продолжаются автоматически."
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
        min_value=0.0, max_value=100.0,
        value=float(FN["p1_offer_coverage"]), step=1.0,
        help=(
            "% MAU Hub, получивших ≥1 релевантный оффер. "
            "Base = 65% (Phase 1: каталог 10–20 Preferred-партнёров + транзакционный матчинг). "
            "СберСпасибо: 50–60% охват в первые 3 мес. после редизайна (Ведомости.Капитал, апрель 2025). "
            "T-Bank преимущество: транзакционные данные с Day 1 → выше охват vs. сайт без авторизации."
        ),
    )
    fn_p1_ctr = st.slider(
        "CTR оффера (%)", key="fn_p1_ctr",
        min_value=0.0, max_value=100.0,
        value=float(FN["p1_ctr_offer"]), step=0.5,
        help=(
            "% пользователей, кликнувших на оффер. Base = 16%. "
            "Batch State of Messaging 2025: in-app promo card CTR = 16.1% Android / 17.9% iOS. "
            "Phase 1 без персонализации — берём нижнюю границу диапазона (16%)."
        ),
    )
    fn_p1_rr = st.slider(
        "Redemption Rate (%)", key="fn_p1_rr",
        min_value=0.0, max_value=100.0,
        value=float(FN["p1_redemption_rate"]), step=0.5,
        help=(
            "% кликнувших, применивших оффер. Base = 20%. "
            "Inmar Intelligence 2025: мобильный CLO redemption rate 15–25% "
            "(vs. 5–10% для ручного промокода). Мобильный in-app контекст снижает friction. "
            "Phase 1 — консервативная оценка нижней границы CLO-диапазона."
        ),
    )
    fn_p1_conv = fn_p1_cov / 100 * fn_p1_ctr / 100 * fn_p1_rr / 100
    st.metric("Сквозная конверсия P1", f"{fn_p1_conv * 100:.3f}%")

with st.sidebar.expander("Phase 2 — Воронка", expanded=False):
    fn_p2_cov = st.slider(
        "Offer Coverage (%)", key="fn_p2_cov",
        min_value=0.0, max_value=100.0,
        value=float(FN["p2_offer_coverage"]), step=1.0,
        help=(
            "Phase 2: каталог 50–150 партнёров → охват 80% категорий. Base = 80%. "
            "При 50+ партнёрах покрываются еда, fashion, маркетплейсы, путешествия, здоровье, авто. "
            "NBP Early версия: ML матчинг по 6+ транзакционным категориям."
        ),
    )
    fn_p2_ctr = st.slider(
        "CTR оффера (%)", key="fn_p2_ctr",
        min_value=0.0, max_value=100.0,
        value=float(FN["p2_ctr_offer"]), step=0.5,
        help=(
            "Phase 2: ранняя персонализация NBP. Base = 18%. "
            "Batch 2025: персонализированные in-app push с именем = +2× CTR vs generic. "
            "Airship 2024: сегментированные уведомления в финтех = 17–22% CTR. "
            "Берём 18% — середину диапазона с учётом охвата аудитории Phase 2."
        ),
    )
    fn_p2_rr = st.slider(
        "Redemption Rate (%)", key="fn_p2_rr",
        min_value=0.0, max_value=100.0,
        value=float(FN["p2_redemption_rate"]), step=0.5,
        help=(
            "Phase 2: прогретая аудитория + CLO beta. Base = 27%. "
            "Cardlytics Q4 2024: персональные card-linked offers → redemption rate 22–32%. "
            "Five Guys/Cardlytics кейс: персональные офферы +30% repeat purchases за 90 дней. "
            "Phase 2 — mid-range 27%."
        ),
    )
    fn_p2_conv = fn_p2_cov / 100 * fn_p2_ctr / 100 * fn_p2_rr / 100
    st.metric("Сквозная конверсия P2", f"{fn_p2_conv * 100:.3f}%")

with st.sidebar.expander("Phase 3 — Воронка", expanded=False):
    fn_p3_cov = st.slider(
        "Offer Coverage (%)", key="fn_p3_cov",
        min_value=0.0, max_value=100.0,
        value=float(FN["p3_offer_coverage"]), step=1.0,
        help=(
            "Phase 3: зрелый каталог 500+ партнёров + CLO auto-match. Base = 92%. "
            "Rakuten: 3 500+ магазинов, охват 90%+ категорий покупок. "
            "T-Bank CLO: автоматический матч транзакций → охват практически всей аудитории."
        ),
    )
    fn_p3_ctr = st.slider(
        "CTR оффера (%)", key="fn_p3_ctr",
        min_value=0.0, max_value=100.0,
        value=float(FN["p3_ctr_offer"]), step=0.5,
        help=(
            "Phase 3: полный NBP v2, таргетинг по транзакционной истории 18+ мес. Base = 22%. "
            "Batch 2025: гиперперсонализированные уведомления (имя + категория + время) = 20–26% CTR. "
            "CLO-уведомления постфактум («вы только что заработали бонус») = почти 100% открываемость."
        ),
    )
    fn_p3_rr = st.slider(
        "Redemption Rate (%)", key="fn_p3_rr",
        min_value=0.0, max_value=100.0,
        value=float(FN["p3_redemption_rate"]), step=0.5,
        help=(
            "Phase 3: CLO auto-apply — пользователь не совершает действий. Base = 36%. "
            "Baymard Institute: CLO устраняет всё friction → redemption rate ×1.5–2.5× vs ручного промокода. "
            "При base ручного RR 20% × 1.8 = 36%. Подтверждено Chase Offers CLO (BAI 2024)."
        ),
    )
    fn_p3_conv = fn_p3_cov / 100 * fn_p3_ctr / 100 * fn_p3_rr / 100
    st.metric("Сквозная конверсия P3", f"{fn_p3_conv * 100:.3f}%")

# --- Блок 6: Монетизация (4-сценарная модель партнёрских выплат) ---
st.sidebar.markdown("### 💰 Монетизация")
st.sidebar.caption(
    "Каждый redemption классифицируется по роли для партнёра: "
    "**NEW** (новый клиент) / **LOYAL** (лояльный, повышение вовлечённости) / "
    "**RET** (реактивация ушедшего) / **AT_RISK** (удержание в зоне оттока). "
    "Выручка = N_redemptions × Σ(w_i × price_i) × incremental_adj."
)

MN = D["monetization"]

st.sidebar.markdown("#### Веса сценариев (%)")
st.sidebar.caption("Распределение redemptions по сценариям. Сумма w_new + w_loyal + w_ret = авто → w_at_risk.")

w_new = st.sidebar.slider(
    "NEW — новый клиент партнёра (%)",
    min_value=0, max_value=100,
    value=int(MN["w_new"]),
    step=1,
    help=(
        "Доля redemptions в сценарии Acquisition (X=2 в матрице партнёрских кампаний). "
        "Base = 25%. Cardlytics Annual Report 2024: ~25–30% CLO-кампаний нацелено на "
        "пользователей, у которых нет транзакционной истории с данным партнёром. "
        "Самый дорогой сценарий → наибольшая ценность для партнёра."
    ),
)
w_loyal = st.sidebar.slider(
    "LOYAL — лояльный, повышение вовлечённости (%)",
    min_value=0, max_value=100,
    value=int(MN["w_loyal"]),
    step=1,
    help=(
        "Доля redemptions в сценарии Expansion/Loyalty (X=4). Base = 40%. "
        "Cardlytics 2024: ~40–45% CLO-redemptions приходятся на уже лояльных клиентов — "
        "крупнейший сегмент в любом зрелом CLO-каталоге. "
        "Партнёр платит меньше — нет риска привлечения, только incremental uplift."
    ),
)
w_ret = st.sidebar.slider(
    "RET — реактивация ушедшего (%)",
    min_value=0, max_value=100,
    value=int(MN["w_ret"]),
    step=1,
    help=(
        "Доля redemptions в сценарии Reactivation (X=1, lapsed 60–180 дней). Base = 20%. "
        "partner-revenue-model.md §2: ~15–20% адресуемой аудитории партнёра "
        "находится в состоянии lapsed в любой момент времени. "
        "Ценность близка к Acquisition — первая транзакция после паузы."
    ),
)
w_at_risk = 100 - w_new - w_loyal - w_ret
scenario_weights_sum = w_new + w_loyal + w_ret + w_at_risk
if w_at_risk < 0:
    st.sidebar.error(f"⚠️ w_new + w_loyal + w_ret = {w_new + w_loyal + w_ret}% > 100%. Уменьшите веса.")
else:
    st.sidebar.success(
        f"✅ NEW({w_new}%) + LOYAL({w_loyal}%) + RET({w_ret}%) + AT_RISK({w_at_risk}%) = 100%"
    )
st.sidebar.caption(
    f"**w_at_risk (AT_RISK)** = 100 − w_new − w_loyal − w_ret = **{w_at_risk}%** "
    "(удержание клиентов в зоне оттока: снижение частоты >40% за 60 дней, Archetype X=3)"
)

st.sidebar.markdown("#### Цены партнёрских выплат (₽/redemption)")
st.sidebar.caption("Сколько партнёр платит за один доставленный промокод/оффер по каждому сценарию.")

price_new = st.sidebar.number_input(
    "price_NEW — цена за нового клиента (₽)",
    min_value=50, max_value=50_000,
    value=int(MN["price_new"]),
    step=50,
    format="%d",
    help=(
        "Плата партнёра за каждый redemption в сценарии Acquisition. Base = 650 ₽. "
        "Admitad Россия 2025: fashion new-customer CPA 400–800 ₽, marketplace 600–900 ₽, "
        "food delivery 250–500 ₽. Blended с учётом premium-скоса аудитории T-Bank = 650 ₽. "
        "Совпадает с прежним cpa_avg — он был calibrated именно под acquisition-heavy mix."
    ),
)
price_loyal = st.sidebar.number_input(
    "price_LOYAL — цена за лояльного клиента (₽)",
    min_value=10, max_value=20_000,
    value=int(MN["price_loyal"]),
    step=10,
    format="%d",
    help=(
        "Плата партнёра за incremental uplift у лояльного клиента. Base = 170 ₽. "
        "Рассчитано как RevShare: AOV 2 600 ₽ × RevShare 6,5% ≈ 169 ₽. "
        "Партнёр платит меньше — клиент уже его, нет стоимости привлечения. "
        "Rakuten US: mediana cashback 6%, Admitad fashion RevShare 8–15% → нижняя граница."
    ),
)
price_ret = st.sidebar.number_input(
    "price_RET — цена за реактивацию (₽)",
    min_value=50, max_value=50_000,
    value=int(MN["price_ret"]),
    step=50,
    format="%d",
    help=(
        "Плата партнёра за возврат ушедшего пользователя. Base = 420 ₽. "
        "Admitad: reactivation CPA = 60–70% от new-customer CPA "
        "(первая транзакция после паузы ≈ «частичное» привлечение). "
        "650 × 0,65 = 422 ₽ → 420 ₽. Логика: клиент помнит бренд, "
        "но надо вернуть привычку — затраты ниже, чем на нового."
    ),
)
price_at_risk = st.sidebar.number_input(
    "price_AT_RISK — цена за удержание (₽)",
    min_value=10, max_value=20_000,
    value=int(MN["price_at_risk"]),
    step=10,
    format="%d",
    help=(
        "Плата партнёра за промокод/кешбек клиенту в зоне риска оттока. Base = 290 ₽. "
        "Оценочно: ~45% от price_new (650 × 0,45 ≈ 290 ₽). "
        "Логика: партнёр страхует будущий churn, а не восстанавливает утраченное → "
        "платит меньше, чем за реактивацию (420 ₽), но больше, чем за лояльного (170 ₽). "
        "Данных прямого бенчмарка нет; оценочно на основе gradient between RET и LOYAL."
    ),
)

blended_price_preview = (
    w_new * price_new + w_loyal * price_loyal + w_ret * price_ret + w_at_risk * price_at_risk
) / 100.0
st.sidebar.caption(
    f"Blended price/redemption = **{blended_price_preview:.0f} ₽** "
    f"(= {w_new}%×{price_new} + {w_loyal}%×{price_loyal} + {w_ret}%×{price_ret} + {w_at_risk}%×{price_at_risk})"
)

incremental_adj = st.sidebar.number_input(
    "Поправка на каннибализацию",
    min_value=0.0, max_value=2.0,
    value=float(MN["incremental_adj"]),
    step=0.01,
    format="%.2f",
    help=(
        "Коэффициент incrementality. Base = 0.87 (87% выручки — истинно инкрементальная). "
        "unit-economics.md §6.3: 10–15% каннибализации из существующих кэшбэк-бюджетов. "
        "Rakuten/Cardlytics исследования: доля инкрементальных покупок в CLO = 78–92%."
    ),
)

# --- Блок 7: Переменные затраты ---
st.sidebar.markdown("### 📦 Переменные затраты (₽/redemption)")
st.sidebar.caption(
    "Инкрементальные затраты на 1 redemption: T-Bank уже имеет инфраструктуру "
    "(push, ML platform, antifraud) — учитываем только прирост."
)

vc_p1 = st.sidebar.number_input(
    "Phase 1 — VC/redemption (₽)",
    min_value=1, max_value=5000,
    value=D["variable_costs"]["vc_per_redemption_p1"],
    step=1,
    format="%d",
    help=(
        "Инкрементальные затраты на 1 redemption в Phase 1. Base = 22 ₽. "
        "push ~3 ₽ + ML inference ~4 ₽ + attribution API ~3 ₽ + antifraud ~3 ₽ + support ~9 ₽ = 22 ₽. "
        "T-Bank уже имеет инфраструктуру — учитываем только прирост к существующим затратам."
    ),
)
vc_p2 = st.sidebar.number_input(
    "Phase 2 — VC/redemption (₽)",
    min_value=1, max_value=5000,
    value=D["variable_costs"]["vc_per_redemption_p2"],
    step=1,
    format="%d",
    help=(
        "Инкрементальные затраты на 1 redemption в Phase 2. Base = 16 ₽. "
        "Batch-inference снижает стоимость ML vs real-time на ~30%. "
        "При объёме 1M+ redemptions/мес — экономия на масштабе в attribution и antifraud."
    ),
)
vc_p3 = st.sidebar.number_input(
    "Phase 3 — VC/redemption (₽)",
    min_value=1, max_value=5000,
    value=D["variable_costs"]["vc_per_redemption_p3"],
    step=1,
    format="%d",
    help=(
        "Инкрементальные затраты на 1 redemption в Phase 3. Base = 10 ₽. "
        "CLO auto-apply: attribution автоматическая через карту → attribution API ~0. "
        "Batch ML pipeline при 5M+ MAU Hub: инференс ~1.5 ₽/user. "
        "Полная экономия на масштабе: VC/redemption снижается ~2× vs Phase 1."
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
    min_value=0.0, max_value=100.0,
    value=float(D["discount"]["annual_rate_pct"]),
    step=1.0,
    help=(
        "Годовая ставка дисконтирования. Base = 20% годовых. "
        "ЦБ РФ ключевая ставка: 21% (апрель 2026) → WACC финтех ≈ 18–24%. "
        "Для внутреннего проекта крупного банка: hurdle rate обычно ключ. ставка + 2–5 п.п."
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
if w_at_risk < 0:
    st.error(
        f"⚠️ Сумма весов сценариев w_new + w_loyal + w_ret = {w_new + w_loyal + w_ret}% > 100%. "
        "Уменьшите веса сценариев NEW, LOYAL или RET."
    )
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
    # Монетизация (4-сценарная)
    "w_new":          float(w_new),
    "w_loyal":        float(w_loyal),
    "w_ret":          float(w_ret),
    "w_at_risk":      float(w_at_risk),
    "price_new":      float(price_new),
    "price_loyal":    float(price_loyal),
    "price_ret":      float(price_ret),
    "price_at_risk":  float(price_at_risk),
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
        st.markdown(
            f"- Веса: NEW {w_new}% / LOYAL {w_loyal}% / RET {w_ret}% / AT_RISK {w_at_risk}%"
        )
        st.markdown(
            f"- Цены: NEW {price_new} ₽ / LOYAL {price_loyal} ₽ / "
            f"RET {price_ret} ₽ / AT_RISK {price_at_risk} ₽"
        )
        st.markdown(f"- Blended price: **{blended_price_preview:.0f} ₽/redemption**")
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

st.subheader("График 2 — Структура выручки: 4 сценария партнёрских выплат")
st.plotly_chart(
    create_revenue_breakdown_chart(cf_results, int(phase1_end), int(phase2_end)),
    use_container_width=True,
)
st.markdown(
    "> **Как читать:** каждый цвет — сценарий партнёрской выплаты. "
    "**NEW** (синий) — самая дорогая ставка (новый клиент партнёра). "
    "**LOYAL** (зелёный) — крупнейший по объёму, но дешевле. "
    "**RET** (оранжевый) — реактивация. "
    "**AT_RISK** (фиолетовый) — удержание в зоне оттока."
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
            "NEW (₽)":         f"{r.get('revenue_new', 0):,.0f}",
            "LOYAL (₽)":       f"{r.get('revenue_loyal', 0):,.0f}",
            "RET (₽)":         f"{r.get('revenue_ret', 0):,.0f}",
            "AT_RISK (₽)":     f"{r.get('revenue_at_risk', 0):,.0f}",
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
