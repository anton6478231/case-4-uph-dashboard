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
import math
import datetime
import streamlit as st
import pandas as pd
from pathlib import Path

from models import (
    calculate_model,
    calculate_costs_for_months,
    calculate_cash_flow_for_months,
    discount_rnd_cash_flows,
    calculate_breakeven_month,
    calculate_RnD_cash_flows,
    get_total_RnD_investment,
    build_empty_matrix,
    ensure_matrix_size,
    DEFAULT_RND_CATEGORIES,
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


# Позволяет загрузить конфигурацию через Import — override хранится в session_state
D = st.session_state.get("_hub_config_override") or load_defaults()


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

# --- Блок 1.5: RnD / Pre-launch фаза ---
st.sidebar.markdown("### 🔬 RnD / Pre-launch фаза")
st.sidebar.caption(
    "Период разработки и тестирования до коммерческого запуска. "
    "Месяц 1 — только затраты на команду и инфраструктуру. "
    "Последний RnD месяц — пилот на малой выборке пользователей."
)

_RND_D = D.get("rnd", {})

rnd_enabled = st.sidebar.toggle(
    "Включить RnD фазу",
    value=bool(_RND_D.get("enabled", True)),
    help=(
        "При включении модель добавляет N предстартовых месяцев перед рыночной фазой. "
        "NPV и ROI пересчитываются с учётом смещения: рыночный месяц t "
        "дисконтируется как позиция (rnd_months + t) от момента инвестиций."
    ),
)

if rnd_enabled:
    rnd_months = st.sidebar.slider(
        "Длительность RnD фазы (мес.)",
        min_value=1, max_value=6,
        value=int(_RND_D.get("months", 2)),
        step=1,
        help=(
            "Количество предстартовых месяцев. Base = 2: "
            "месяц 1 — сборка команды + инфра MVP, "
            "месяц 2 — пилот на ограниченной аудитории. "
            "Бенчмарк: Chase Offers MVP-фаза 0–3 мес. (BAI 2024). "
            "Rakuten/Honey pre-launch: 2–4 мес. для первичного каталога партнёров."
        ),
    )

    st.sidebar.markdown("**Бюджет RnD фазы (₽/мес. по статьям)**")
    st.sidebar.caption(
        "Одинаковый бюджет по каждой статье на все RnD месяцы. "
        "Итоговые инвестиции = сумма всех затрат − пилотная выручка последнего месяца."
    )

    _rnd_defaults = _RND_D.get("monthly_costs", {
        "Зарплаты команды":          3_000_000,
        "Инфраструктура":              500_000,
        "Разработка/тестирование":   1_500_000,
        "Прочие расходы RnD":          500_000,
    })

    rnd_monthly_costs: dict = {}
    for cat in DEFAULT_RND_CATEGORIES:
        rnd_monthly_costs[cat] = st.sidebar.number_input(
            cat,
            min_value=0,
            max_value=50_000_000,
            value=_rnd_defaults.get(cat, 500_000),
            step=100_000,
            format="%d",
            key=f"rnd_cat_{cat}",
        )

    # Матрица: одинаковый бюджет на каждый RnD месяц
    rnd_costs_matrix = {
        cat: [float(v)] * rnd_months
        for cat, v in rnd_monthly_costs.items()
    }
    rnd_costs_matrix = ensure_matrix_size(rnd_costs_matrix, rnd_months)

    pilot_audience_pct = st.sidebar.slider(
        "Аудитория пилота (% от стартового MAU)",
        min_value=1, max_value=20,
        value=int(_RND_D.get("pilot_audience_pct", 5)),
        step=1,
        help=(
            "Масштаб пилота в последнем RnD месяце: доля от базовых MAU_web/MAU_app. "
            "5% = 15k пользователей сайта + 1.7M app — репрезентативная тестовая выборка. "
            "Пилотная выручка вычитается из общих RnD затрат при расчёте инвестиций."
        ),
    )

    _rnd_total_costs_preview = sum(
        v * rnd_months for v in rnd_monthly_costs.values()
    )
    st.sidebar.caption(
        f"Суммарный бюджет RnD: **{_rnd_total_costs_preview:,.0f} ₽** "
        f"за {rnd_months} мес. "
        f"(~{_rnd_total_costs_preview / 1_000_000:.1f}M ₽)"
    )
else:
    rnd_months = 0
    rnd_costs_matrix = build_empty_matrix(DEFAULT_RND_CATEGORIES, 1)
    pilot_audience_pct = 0

# --- Блок 2: Посетители (stock-and-flow) ---
st.sidebar.markdown("### 🌐 Посетители (stock-and-flow)")
st.sidebar.caption(
    "Два независимых входных потока. Каждый месяц MAU платформы растёт на заданный %, "
    "прирост пополняет убывающий пул потенциальных Hub-пользователей."
)

VM = D["visitor_model"]
MG = D.get("mau_growth", {})

mau_web = st.sidebar.number_input(
    "MAU сайта promokod.tbank.ru (старт)",
    min_value=10_000, max_value=10_000_000,
    value=int(VM["MAU_web"]),
    step=10_000,
    format="%d",
    help=(
        "Стартовое MAU сайта (месяц 0). Base = 300 000. "
        "Диапазон 200–600k (unit-economics.md §3). "
        "pool_web[0] = MAU_web × (1 − overlap%), т.е. только web-only посетители."
    ),
)
mau_app = st.sidebar.number_input(
    "MAU приложения T-Bank (старт)",
    min_value=1_000_000, max_value=100_000_000,
    value=int(VM["MAU_app"]),
    step=1_000_000,
    format="%d",
    help=(
        "Стартовое MAU приложения (месяц 0). Base = 34 000 000 (FY2025 IR T-Bank). "
        "pool_app[0] = MAU_app (перекрытие учтено в pool_web)."
    ),
)

with st.sidebar.expander("📈 Рост MAU платформы (%/год)", expanded=False):
    st.caption(
        "Ежегодный темп роста MAU сайта и приложения. Пересчитывается в помесячный: "
        "r = (1 + annual/100)^(1/12) − 1. Каждый месяц прирост MAU пополняет пул "
        "потенциальных пользователей Hub."
    )
    mau_web_annual_growth = st.slider(
        "Рост MAU сайта (%/год)",
        min_value=0.0, max_value=200.0,
        value=float(MG.get("web_annual_growth_pct", 35.0)),
        step=1.0,
        help=(
            "Годовой рост MAU promokod.tbank.ru. Base = 35%. "
            "Логика: Hub-запуск → редизайн сайта + SEO → органический рост. "
            "Бенчмарк: Honey/PayPal web трафик рос 40–60%/год в первые 2 года после запуска; "
            "Купонатор (РФ) ~20%/год при зрелости. 35% — умеренный сценарий для нового продукта. "
            "Годовой → месячный: (1,35)^(1/12) − 1 ≈ 2.54%/мес."
        ),
    )
    mau_app_annual_growth = st.slider(
        "Рост MAU приложения (%/год)",
        min_value=0.0, max_value=100.0,
        value=float(MG.get("app_annual_growth_pct", 18.0)),
        step=1.0,
        help=(
            "Годовой рост MAU T-Bank App. Base = 18%. "
            "Логика: T-Bank MAU вырос с ~27M (9М2024) до 34M (FY2025) = +26% за год. "
            "На горизонте 2 лет рост замедляется по мере насыщения: "
            "крупные super-app (Revolut, Grab) удерживают 15–20%/год при MAU >30M. "
            "18% — консервативный base. "
            "Годовой → месячный: (1,18)^(1/12) − 1 ≈ 1.39%/мес."
        ),
    )
    # Показываем итоговые MAU в конце горизонта
    mau_web_final = mau_web * (1.0 + mau_web_annual_growth / 100.0) ** (num_months / 12.0)
    mau_app_final = mau_app * (1.0 + mau_app_annual_growth / 100.0) ** (num_months / 12.0)
    st.caption(
        f"MAU сайта к месяцу {num_months}: **{mau_web_final:,.0f}** "
        f"(×{mau_web_final/mau_web:.1f}× от старта)"
    )
    st.caption(
        f"MAU приложения к месяцу {num_months}: **{mau_app_final/1_000_000:.1f}M** "
        f"(×{mau_app_final/mau_app:.2f}× от старта)"
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
        "Доля остатка pool_app, конвертирующаяся в NEW каждый месяц. Base = 1.0%. "
        "Компромисс между агрессивным 1.5% (давало 12M+ hub-пользователей = 35% аудитории "
        "T-Bank — нереалистично для одной новой фичи) и консервативным 0.5%. "
        "1.0% × 34M = 340k новых/мес → ~4–5M накопленных к мес.24 ≈ 12–14% проникновения "
        "с учётом platform churn (реальная активная база ~2.5–3.5M). "
        "Логика: T-Bank имеет преимущество перед нуля — промокоды уже существуют в app, "
        "продвижение через push-уведомления при запуске Hub даёт буст активации. "
        "Бенчмарк: СберСпасибо — фича активируется ~1%/мес от MAU Сбера в первые 12 мес. "
        "запуска персонализации (Ведомости, 2024, оценочно); "
        "AppsFlyer Finance Apps 2025: in-app rewards activation 0.6–1.2%/мес при наличии "
        "onboarding push. 1.0% — середина этого диапазона. "
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
with st.sidebar.expander("K-фактор по фазам", expanded=False):
    st.sidebar.caption(
        "Вирусный коэффициент: сколько новых пользователей приводит каждый "
        "существующий за месяц через шеринг промокодов. "
        "k = (доля шерящих) × (конверсия инвайта). "
        "Реферальный приток — КОГОРТНАЯ модель: referral_new[m] = cum_graduating[m−1] × (k_annual / 12). "
        "k_annual = годовой K-фактор: сколько рефералов генерирует 1 пользователь суммарно за 12 месяцев."
    )
    p1_k_factor = st.sidebar.slider(
        "K-фактор Phase 1 — годовой (мес. 1–3)",
        min_value=0.0, max_value=0.5,
        value=float(VM.get("p1_k_factor", 0.03)),
        step=0.01,
        help=(
            "ГОДОВОЙ K: каждый пришедший пользователь генерирует 0.03 реферала за 12 мес. "
            "Ежемесячная ставка = 0.03 / 12 = 0.0025. "
            "P1: реферальная петля не запущена, нет бонусов — только «сарафан». "
            "~5% шарят спонтанно × 60% конверсия. "
            "referral_new = cum_graduating × 0.0025 — пренебрежимо мал на старте."
        ),
    )
    p2_k_factor = st.sidebar.slider(
        "K-фактор Phase 2 — годовой (мес. 4–9)",
        min_value=0.0, max_value=0.5,
        value=float(VM.get("p2_k_factor", 0.10)),
        step=0.01,
        help=(
            "ГОДОВОЙ K: каждый пришедший пользователь генерирует 0.10 реферала за 12 мес. "
            "Ежемесячная ставка = 0.10 / 12 = 0.0083. "
            "P2: запущен Сценарий 4 «web+бонус» — кнопка «Поделиться» + +50–100₽. "
            "~15% шарят × 67% конверсия. "
            "Бенчмарк: Cash App referral k ≈ 0.08–0.12 годовой (BAI Banking Strategies 2023, оценочно)."
        ),
    )
    p3_k_factor = st.sidebar.slider(
        "K-фактор Phase 3 — годовой (мес. 10–18)",
        min_value=0.0, max_value=1.0,
        value=float(VM.get("p3_k_factor", 0.30)),
        step=0.01,
        help=(
            "ГОДОВОЙ K: каждый пришедший пользователь генерирует 0.30 реферала за 12 мес. "
            "Ежемесячная ставка = 0.30 / 12 = 0.025. "
            "P3: зрелая петля — геймификация streak, двусторонний бонус, A-ACT-евангелисты. "
            "50% A-ACT шарят × 60% конверсия = K=0.30. "
            "Бенчмарк: Ibotta год 3 — k ≈ 0.25–0.35 (Ibotta S-1, 2024, оценочно). "
            "При cum_graduating = 2M → +50K рефералов/мес — заметный, но не взрывной вклад."
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

# --- Блок 4.5: Отток с платформы ---
st.sidebar.markdown("### 🚪 Отток с платформы (Platform Churn)")
st.sidebar.caption(
    "Доля пользователей каждого сегмента, которые **полностью прекращают** использование хаба "
    "в данном месяце. Без этого параметра MAU_hub — поглощающий автомат: "
    "пользователи только переходят LOW↔MID↔ACT, но никогда не уходят насовсем, "
    "что завышает долгосрочную базу и раздувает ROI."
)

_PC_D = D.get("platform_churn", {})

with st.sidebar.expander("Ежемесячный отток по сегментам", expanded=True):
    hub_churn_low = st.slider(
        "Отток LOW → уход с платформы (%/мес)",
        min_value=0, max_value=50,
        value=int(_PC_D.get("hub_monthly_churn_low_pct", 15)),
        step=1,
        help=(
            "Доля LOW-пользователей, ежемесячно покидающих хаб насовсем. Base = 15%. "
            "Пассивные пользователи: попробовали один промокод, не вернулись. "
            "AppsFlyer Finance Apps 2025: 60-day retention для non-core banking feature "
            "= 35–45% → ежемесячный отток ≈ 14–18%. "
            "При 15%: 6-мес. retention = 85%^6 = 37.7%, 12-мес. = 85%^12 = 14.2%. "
            "Суммарный outflow LOW = low_to_mid + low_to_act + churn_low ≤ 100%."
        ),
    )
    hub_churn_mid = st.slider(
        "Отток MID → уход с платформы (%/мес)",
        min_value=0, max_value=50,
        value=int(_PC_D.get("hub_monthly_churn_mid_pct", 8)),
        step=1,
        help=(
            "Доля MID-пользователей, ежемесячно покидающих хаб. Base = 8%. "
            "Ситуативные пользователи: уходят в периоды без релевантных офферов "
            "(после Нового года, летом в off-season). "
            "При 8%: 6-мес. retention = 92%^6 = 60.6%, 12-мес. = 92%^12 = 36.8%. "
            "Cardlytics 2024: MID-tier inactive rate 6–10%/мес в CLO-программах без re-engagement push. "
            "Суммарный outflow MID = mid_to_low + mid_to_act + churn_mid ≤ 100%."
        ),
    )
    hub_churn_act = st.slider(
        "Отток ACT → уход с платформы (%/мес)",
        min_value=0, max_value=20,
        value=int(_PC_D.get("hub_monthly_churn_act_pct", 3)),
        step=1,
        help=(
            "Доля ACT-пользователей, ежемесячно покидающих хаб. Base = 3%. "
            "Power-users: CLO auto-apply удерживает статус даже без явных действий. "
            "При 3%: 6-мес. retention = 97%^6 = 83.2%, 12-мес. = 97%^12 = 69.4%. "
            "Rakuten 2024: top-tier пользователи churnat на уровне 2–4%/мес. "
            "Суммарный outflow ACT = act_to_low + act_to_mid + churn_act ≤ 100%."
        ),
    )
    low_total_out = low_to_mid + low_to_act + hub_churn_low
    mid_total_out = mid_to_low + mid_to_act + hub_churn_mid
    act_total_out = act_to_low + act_to_mid + hub_churn_act
    for _label, _out in [("LOW", low_total_out), ("MID", mid_total_out), ("ACT", act_total_out)]:
        if _out > 100:
            st.error(f"⚠️ Суммарный outflow {_label} = {_out}% > 100%! Уменьшите переходы или churn.")
        else:
            st.success(f"✅ Суммарный outflow {_label} = {_out}% (удержание {100 - _out}%)")

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
        "Плата партнёра за каждый redemption в сценарии Acquisition. Base = 200 ₽. "
        "Логика: Admitad Россия 2024 — blended CPA по всем категориям 150–350 ₽; "
        "фуд-доставка тянет среднее вниз (80–150 ₽), fashion 300–500 ₽, marketplace 200–400 ₽. "
        "200 ₽ = entry-level ставка нового продукта без трек-рекорда: партнёры "
        "стартуют с минимальных ставок и повышают их по мере доказательства инкрементальности. "
        "Cardlytics US: начальный CPA для малых партнёров ~$2–3 (≈180–270 ₽). "
        "При росте каталога и доказанном lift → переговоры на 300–500 ₽ (фаза 3)."
    ),
)
price_loyal = st.sidebar.number_input(
    "price_LOYAL — цена за лояльного клиента (₽)",
    min_value=10, max_value=20_000,
    value=int(MN["price_loyal"]),
    step=10,
    format="%d",
    help=(
        "Плата партнёра за incremental uplift у лояльного клиента. Base = 100 ₽. "
        "Рассчитано как RevShare: AOV 2 500 ₽ × RevShare 4% = 100 ₽. "
        "Консервативный RevShare 4% отражает: (1) партнёр уже владеет клиентом — "
        "incremental uplift труднее доказать в первых кварталах; "
        "(2) стартовые переговоры всегда начинаются с нижней границы диапазона. "
        "Admitad Россия 2024: базовые RevShare-ставки 3–6%; при наличии incrementality-отчёта "
        "вырастают до 6–12%. 100 ₽ = первый год без доказательств lift."
    ),
)
price_ret = st.sidebar.number_input(
    "price_RET — цена за реактивацию (₽)",
    min_value=50, max_value=50_000,
    value=int(MN["price_ret"]),
    step=50,
    format="%d",
    help=(
        "Плата партнёра за возврат ушедшего пользователя. Base = 150 ₽. "
        "Рассчитано как 75% от price_new: 200 × 0,75 = 150 ₽. "
        "Логика: клиент помнит бренд → затраты на возврат ниже, чем на нового, "
        "но требует более ценного оффера, чем удержание лояльного. "
        "Admitad: reactivation CPA стабильно составляет 60–80% от new-customer CPA "
        "по категориям fashion и marketplace (2024). "
        "150 ₽ = консервативный вход; при доказанном reactivation lift → 200–250 ₽."
    ),
)
price_at_risk = st.sidebar.number_input(
    "price_AT_RISK — цена за удержание (₽)",
    min_value=10, max_value=20_000,
    value=int(MN["price_at_risk"]),
    step=10,
    format="%d",
    help=(
        "Плата партнёра за промокод/кешбек клиенту в зоне риска оттока. Base = 100 ₽. "
        "Оценочно: 50% от price_new (200 × 0,50 = 100 ₽), на уровне price_LOYAL. "
        "Логика: churn-prevention — превентивный инструмент, партнёр страхует будущую выручку. "
        "Однако доказать факт «спасения» клиента сложнее, чем acquisition/reactivation → "
        "партнёры не готовы платить премиум без A/B-доказательств. "
        "100 ₽ = консервативная нижняя граница; после пилота с retention lift → 120–150 ₽. "
        "Прямого бенчмарка нет; оценка на основе Cardlytics retention campaign pricing (оценочно)."
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

if low_to_mid + low_to_act + hub_churn_low > 100:
    st.error(f"⚠️ Суммарный outflow LOW = {low_to_mid + low_to_act + hub_churn_low}% > 100%. Исправьте переходы или отток LOW.")
    st.stop()
if mid_to_low + mid_to_act + hub_churn_mid > 100:
    st.error(f"⚠️ Суммарный outflow MID = {mid_to_low + mid_to_act + hub_churn_mid}% > 100%. Исправьте переходы или отток MID.")
    st.stop()
if act_to_low + act_to_mid + hub_churn_act > 100:
    st.error(f"⚠️ Суммарный outflow ACT = {act_to_low + act_to_mid + hub_churn_act}% > 100%. Исправьте переходы или отток ACT.")
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
    "MAU_web":                    float(mau_web),
    "MAU_app":                    float(mau_app),
    "mau_web_annual_growth_pct":  float(mau_web_annual_growth),
    "mau_app_annual_growth_pct":  float(mau_app_annual_growth),
    "overlap_web_app_pct": float(overlap_pct),
    "u_to_a_new_web":     float(u_to_a_web),
    "u_to_a_new_app":     float(u_to_a_app),
    "web_to_app":         float(web_to_app),
    "p1_k_factor":        float(p1_k_factor),
    "p2_k_factor":        float(p2_k_factor),
    "p3_k_factor":        float(p3_k_factor),
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
    # Отток с платформы
    "hub_monthly_churn_low_pct": float(hub_churn_low),
    "hub_monthly_churn_mid_pct": float(hub_churn_mid),
    "hub_monthly_churn_act_pct": float(hub_churn_act),
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

# Рыночный CF дисконтируется со сдвигом rnd_months (если RnD включён)
cf_results = calculate_cash_flow_for_months(
    revenue_results,
    costs_results,
    annual_discount_rate=float(annual_discount_rate),
    month_offset=rnd_months,
)
breakeven = calculate_breakeven_month(cf_results)

# ── RnD фаза ────────────────────────────────────────────────────────────────
if rnd_enabled and rnd_months > 0:
    # Пилотная выручка: запускаем модель на 1 месяц с масштабированным MAU
    _pilot_scale = pilot_audience_pct / 100.0
    _params_pilot = dict(params)
    _params_pilot["MAU_web"] = float(mau_web) * _pilot_scale
    _params_pilot["MAU_app"] = float(mau_app) * _pilot_scale
    try:
        _pilot_rev = calculate_model(_params_pilot, 1)
        _pilot_costs = calculate_costs_for_months(_params_pilot, _pilot_rev)
        pilot_revenue = _pilot_rev[0]["total_revenue"]
    except Exception:
        pilot_revenue = 0.0

    RnD_cf_raw = calculate_RnD_cash_flows(rnd_months, rnd_costs_matrix, pilot_revenue)
    RnD_cf = discount_rnd_cash_flows(RnD_cf_raw, annual_discount_rate=float(annual_discount_rate))
    total_investment = get_total_RnD_investment(rnd_costs_matrix, rnd_months, pilot_revenue)

    # combined_cf = RnD месяцы + рыночные месяцы (для графиков)
    # cumulative CF в combined стартует с RnD и продолжается в рыночных
    _rnd_cum_cf_end = RnD_cf[-1]["cumulative_cash_flow"] if RnD_cf else 0.0
    _rnd_cum_npv_end = RnD_cf[-1]["cumulative_npv"] if RnD_cf else 0.0
    _market_cf_adjusted = []
    _running_cum_cf = _rnd_cum_cf_end
    _running_cum_npv = _rnd_cum_npv_end
    for row in cf_results:
        _running_cum_cf += row["cash_flow"]
        _running_cum_npv += row["discounted_cash_flow"]
        _market_cf_adjusted.append(dict(
            row,
            cumulative_cash_flow=_running_cum_cf,
            cumulative_npv=_running_cum_npv,
        ))
    combined_cf = RnD_cf + _market_cf_adjusted

    # Breakeven по combined timeline (RnD-дефицит + рыночные месяцы).
    # Используется в KPI-карточках и совпадает со звёздочкой на графике.
    breakeven_combined = calculate_breakeven_month(_market_cf_adjusted)

    # ROI год 1 — 12 месяцев от старта инвестиций
    # = все RnD месяцы + первые (12 - rnd_months) рыночных месяцев
    _year1_market_count = max(1, 12 - rnd_months)
    _year1_rnd_cf = sum(r["cash_flow"] for r in RnD_cf_raw)
    _year1_market_cf = sum(r["cash_flow"] for r in cf_results[:_year1_market_count])
    _year1_cf_total = _year1_rnd_cf + _year1_market_cf
    roi_year1 = (_year1_cf_total / total_investment * 100.0) if total_investment > 0 else None

    # NPV итог = накопленный NPV по всему combined (конец рыночной фазы)
    final_npv_combined = _market_cf_adjusted[-1]["cumulative_npv"] if _market_cf_adjusted else _rnd_cum_npv_end
else:
    RnD_cf = []
    combined_cf = cf_results
    pilot_revenue = 0.0
    total_investment = 0.0
    roi_year1 = None
    final_npv_combined = cf_results[-1]["cumulative_npv"] if cf_results else 0.0
    breakeven_combined = breakeven  # без RnD — combined совпадает с market-only

# ── «Год 1 проекта» — метрики на 12-й месяц от старта инвестиций ─────────────
# Проектный месяц 12 = RnD фаза + рыночная фаза.
# Рыночный индекс (0-based): max(0, 12 - rnd_months - 1)
# Если горизонт короче — берём последний доступный месяц.
_year12_market_idx = max(0, min(12 - rnd_months - 1, len(cf_results) - 1))

# MAU Hub (чёрная линия на графике 4) = mau_hub + new_web
# cf_results в этот момент ещё не обогащён new_web — используем revenue_results
_year12_rev_row = revenue_results[_year12_market_idx] if revenue_results else {}
mau_hub_year12 = (
    _year12_rev_row.get("mau_hub", 0.0) + _year12_rev_row.get("new_web", 0.0)
)

# NPV на проектный месяц 12 (combined timeline, включая RnD провал)
if rnd_enabled and rnd_months > 0 and _market_cf_adjusted:
    _y12_mkt_row = _market_cf_adjusted[_year12_market_idx]
    npv_year12 = _y12_mkt_row["cumulative_npv"]
else:
    # RnD выключен: берём из рыночных cf_results
    _y12_mkt_row = cf_results[_year12_market_idx] if cf_results else {}
    npv_year12 = _y12_mkt_row.get("cumulative_npv", 0.0)

# ROI год 1: уже вычислен выше как roi_year1 (та же логика — 12 мес. от инвестиций)

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
    row.setdefault("pool_web",    rev.get("pool_web", 0.0))
    row.setdefault("pool_app",    rev.get("pool_app", 0.0))
    row.setdefault("mau_web_cur", rev.get("mau_web_cur", float(mau_web)))
    row.setdefault("mau_app_cur", rev.get("mau_app_cur", float(mau_app)))


# ──────────────────────────────────────────────────────────────────────────────
# Конфигурация: экспорт / импорт
# ──────────────────────────────────────────────────────────────────────────────

st.sidebar.markdown("---")
with st.sidebar.expander("💾 Конфигурация (экспорт / импорт)", expanded=False):
    st.caption(
        "**Экспорт** — скачайте текущие параметры как JSON и отправьте разработчику. "
        "**Импорт** — загрузите ранее сохранённый JSON; параметры применятся сразу. "
        "**Сброс** — вернуть все значения к базовым defaults."
    )

    # ── Сборка снапшота из текущих переменных ────────────────────────────────
    _snapshot = {
        "schema_version": 1,
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "horizon": {
            "num_months":  int(num_months),
            "phase1_end":  int(phase1_end),
            "phase2_end":  int(phase2_end),
        },
        "mau_growth": {
            "web_annual_growth_pct": float(mau_web_annual_growth),
            "app_annual_growth_pct": float(mau_app_annual_growth),
        },
        "visitor_model": {
            "MAU_web":             int(mau_web),
            "MAU_app":             int(mau_app),
            "overlap_web_app_pct": float(overlap_pct),
            "u_to_a_new_web":      float(u_to_a_web),
            "u_to_a_new_app":      float(u_to_a_app),
            "web_to_app":          float(web_to_app),
            "p1_k_factor":         float(p1_k_factor),
            "p2_k_factor":         float(p2_k_factor),
            "p3_k_factor":         float(p3_k_factor),
        },
        "segment_weights": {
            "w_l": int(w_l),
            "w_m": int(w_m),
            "w_a": int(w_a),
        },
        "purchases_per_segment": {
            "purchases_low": float(purch_low),
            "purchases_mid": float(purch_mid),
            "purchases_act": float(purch_act),
        },
        "segment_transitions": {
            "low_to_mid": int(low_to_mid),
            "low_to_act": int(low_to_act),
            "mid_to_low": int(mid_to_low),
            "mid_to_act": int(mid_to_act),
            "act_to_low": int(act_to_low),
            "act_to_mid": int(act_to_mid),
        },
        "funnel": {
            "p1_offer_coverage":  float(fn_p1_cov),
            "p1_ctr_offer":       float(fn_p1_ctr),
            "p1_redemption_rate": float(fn_p1_rr),
            "p2_offer_coverage":  float(fn_p2_cov),
            "p2_ctr_offer":       float(fn_p2_ctr),
            "p2_redemption_rate": float(fn_p2_rr),
            "p3_offer_coverage":  float(fn_p3_cov),
            "p3_ctr_offer":       float(fn_p3_ctr),
            "p3_redemption_rate": float(fn_p3_rr),
        },
        "monetization": {
            "w_new":           int(w_new),
            "w_loyal":         int(w_loyal),
            "w_ret":           int(w_ret),
            "w_at_risk":       int(w_at_risk),
            "price_new":       int(price_new),
            "price_loyal":     int(price_loyal),
            "price_ret":       int(price_ret),
            "price_at_risk":   int(price_at_risk),
            "incremental_adj": float(incremental_adj),
        },
        "variable_costs": {
            "vc_per_redemption_p1": int(vc_p1),
            "vc_per_redemption_p2": int(vc_p2),
            "vc_per_redemption_p3": int(vc_p3),
        },
        "fixed_costs": {
            "p1_team":      int(fc_p1_team),
            "p1_infra":     int(fc_p1_infra),
            "p1_marketing": int(fc_p1_marketing),
            "p1_referral":  int(fc_p1_referral),
            "p2_team":      int(fc_p2_team),
            "p2_infra":     int(fc_p2_infra),
            "p2_marketing": int(fc_p2_marketing),
            "p2_referral":  int(fc_p2_referral),
            "p3_team":      int(fc_p3_team),
            "p3_infra":     int(fc_p3_infra),
            "p3_marketing": int(fc_p3_marketing),
            "p3_referral":  int(fc_p3_referral),
        },
        "discount": {
            "annual_rate_pct": float(annual_discount_rate),
        },
        "platform_churn": {
            "hub_monthly_churn_low_pct": int(hub_churn_low),
            "hub_monthly_churn_mid_pct": int(hub_churn_mid),
            "hub_monthly_churn_act_pct": int(hub_churn_act),
        },
        "rnd": {
            "enabled":            bool(rnd_enabled),
            "months":             int(rnd_months),
            "pilot_audience_pct": int(pilot_audience_pct) if rnd_enabled else 5,
            "monthly_costs":      {k: int(v) for k, v in rnd_monthly_costs.items()} if rnd_enabled else {},
        },
    }
    _snapshot_json = json.dumps(_snapshot, ensure_ascii=False, indent=2)

    # ── Экспорт ───────────────────────────────────────────────────────────────
    st.download_button(
        label="⬇️ Скачать конфигурацию (JSON)",
        data=_snapshot_json,
        file_name=f"hub_config_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
        use_container_width=True,
        help="Скачивает JSON со всеми текущими параметрами модели.",
    )

    # ── Импорт ────────────────────────────────────────────────────────────────
    st.markdown("**Загрузить конфигурацию:**")
    _uploaded = st.file_uploader(
        "Выберите JSON-файл конфигурации",
        type=["json"],
        key="config_uploader",
        label_visibility="collapsed",
    )
    if _uploaded is not None:
        try:
            _imported = json.loads(_uploaded.read().decode("utf-8"))
            # Сохраняем override и перезапускаем страницу
            st.session_state["_hub_config_override"] = _imported
            st.success("✅ Конфигурация загружена! Применяется...")
            st.rerun()
        except Exception as _e:
            st.error(f"❌ Ошибка парсинга JSON: {_e}")

    # ── Сброс к defaults ──────────────────────────────────────────────────────
    if st.session_state.get("_hub_config_override") is not None:
        st.info("ℹ️ Активна загруженная конфигурация.")
        if st.button("🔄 Сбросить к базовым defaults", use_container_width=True):
            del st.session_state["_hub_config_override"]
            st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# Краткая сводка в сайдбаре
# ──────────────────────────────────────────────────────────────────────────────

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Сводка")
total_rev    = sum(r["revenue"] for r in cf_results)
total_cost   = sum(r["total_costs"] for r in cf_results)
net_cf_total = sum(r["cash_flow"] for r in cf_results)
mau_end      = cf_results[-1]["mau_hub"] if cf_results else 0.0
avg_rpu_end  = cf_results[-1]["avg_rpu"] if cf_results else 0.0
seg_act_end  = cf_results[-1]["seg_act"] if cf_results else 0.0
pct_act_end  = (seg_act_end / mau_end * 100.0) if mau_end > 0 else 0.0

st.sidebar.markdown(f"**Выручка (рынок):** {format_currency_compact(total_rev)}")
st.sidebar.markdown(f"**Затраты (рынок):** {format_currency_compact(total_cost)}")
cf_color = "green" if net_cf_total >= 0 else "red"
st.sidebar.markdown(f"**Net CF (рынок):** :{cf_color}[{format_currency_compact(net_cf_total)}]")
npv_color = "green" if final_npv_combined >= 0 else "red"
st.sidebar.markdown(f"**NPV (combined):** :{npv_color}[{format_currency_compact(final_npv_combined)}]")
if rnd_enabled and total_investment > 0:
    inv_color = "orange"
    st.sidebar.markdown(f"**RnD инвестиции:** :{inv_color}[{format_currency_compact(total_investment)}]")
    if roi_year1 is not None:
        roi_color = "green" if roi_year1 >= 0 else "red"
        st.sidebar.markdown(f"**ROI год 1:** :{roi_color}[{roi_year1:.0f}%]")
if breakeven["reached"]:
    st.sidebar.markdown(f"**Breakeven (рынок):** :green[Месяц {breakeven['breakeven_month']}]")
else:
    st.sidebar.markdown(f"**Breakeven:** :red[Не достигнут за {num_months} мес.]")
st.sidebar.markdown(f"**MAU Hub (кон.):** {format_number_compact(mau_end)}")
st.sidebar.markdown(f"**avg_rpu (кон.):** {avg_rpu_end:.2f}")
st.sidebar.markdown(f"**%ACT (кон.):** {pct_act_end:.1f}%")


# ──────────────────────────────────────────────────────────────────────────────
# KPI-карточки
# ──────────────────────────────────────────────────────────────────────────────

display_kpi_cards(
    cf_results,
    breakeven_combined,
    int(num_months),
    total_investment=total_investment if rnd_enabled else None,
    roi_year1=roi_year1,
    rnd_months=rnd_months,
    final_npv_combined=final_npv_combined,
    mau_hub_year12=mau_hub_year12,
    npv_year12=npv_year12,
)

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
        st.markdown(f"- MAU_web (старт): **{format_number_compact(mau_web)}**")
        st.markdown(f"- MAU_app (старт): **{format_number_compact(mau_app)}**")
        st.markdown(f"- Рост MAU web/app: **{mau_web_annual_growth:.0f}% / {mau_app_annual_growth:.0f}%** год.")
        st.markdown(f"- Overlap: **{overlap_pct:.0f}%**")
        st.markdown(f"- u_web/u_app: **{u_to_a_web:.1f}% / {u_to_a_app:.2f}%**")
        st.markdown(f"- web→app: **{web_to_app:.0f}%**")
        st.markdown(f"- K-фактор P1/P2/P3 (годовой): **{p1_k_factor:.2f} / {p2_k_factor:.2f} / {p3_k_factor:.2f}** (мес. ставки: {p1_k_factor/12:.4f} / {p2_k_factor/12:.4f} / {p3_k_factor/12:.4f})")
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
    create_cash_flow_chart(
        cf_results,
        int(phase1_end),
        int(phase2_end),
        RnD_cf_results=RnD_cf if rnd_enabled and RnD_cf else None,
    ),
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

st.subheader("График 4 — Сегментная динамика: NEW / LOW / MID / ACT + Hub total")
st.plotly_chart(
    create_segment_dynamics_chart(revenue_results, int(phase1_end), int(phase2_end)),
    use_container_width=True,
)
st.markdown(
    "> **Как читать:** закрашенные области — сегменты авторизованных app Hub-пользователей. "
    "Серый (NEW) — свежие app-пользователи этого месяца. "
    "Синий (LOW) — пассивные. Жёлтый (MID) — ситуативные. Зелёный (ACT) — оптимизаторы. "
    "**Чёрная линия** — суммарный охват Hub (app + web): `mau_hub + new_web`. "
    "Превышает стек на величину web-only пользователей (не авторизованы в app). "
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
