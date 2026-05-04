"""
Страница «Анализ рынка» — Unified Promo Hub

Содержание:
  §1 — TAM / SAM / SOM (в пользователях, совместимо с 1-pager)
  §2 — Динамика рынка e-com РФ 2022–2025
  §3 — Конкурентный ландшафт (таблица + матрица позиционирования 2×2)
  §4 — Поведение пользователей: точки входа, кэшбэк vs промокод
  §5 — Незанятая ниша: наше УЦП

Источники: desk-research апрель–май 2026, опрос (n=35),
  Data Insight eCommerce 2026, АКАР 2025, АРИР 2025, Frank RG 2025,
  Cardlytics 10-K FY2024, ВЦИОМ янв 2026.

🔴 — маркер расхождения с цифрами 1-pager-v1-source.md
     (логика совместима, расходятся только числа)
"""

import plotly.graph_objects as go
import streamlit as st

# ── палитра ───────────────────────────────────────────────────────────────────
YELLOW  = "#FFDD2D"
TEAL    = "#1B8EF2"
RED     = "#F24B1B"
GREEN   = "#29CC7A"
PURPLE  = "#9B59B6"
ORANGE  = "#E67E22"
GRAY    = "#95A5A6"
DARK    = "#2C3E50"
COLORS_MULTI = [TEAL, YELLOW, RED, GREEN, PURPLE, ORANGE, GRAY]


# ── вспомогательные функции ───────────────────────────────────────────────────
def hbar(labels, values, title, height=None, color=None):
    if height is None:
        height = max(260, 40 * len(labels) + 100)
    colors = [color or TEAL] * len(labels) if color else COLORS_MULTI[:len(labels)]
    fig = go.Figure(go.Bar(
        x=values, y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v}" for v in values],
        textposition="outside",
    ))
    fig.update_layout(
        title_text=title, title_font_size=13,
        xaxis=dict(range=[0, max(values) * 1.3]),
        margin=dict(t=50, b=20, l=10, r=60),
        height=height,
        showlegend=False,
    )
    return fig


def vbar(x_labels, y_values, title, height=340, color=None):
    colors = color if isinstance(color, list) else [color or TEAL] * len(x_labels)
    fig = go.Figure(go.Bar(
        x=x_labels, y=y_values,
        marker_color=colors,
        text=[f"{v}" for v in y_values],
        textposition="outside",
    ))
    fig.update_layout(
        title_text=title, title_font_size=13,
        yaxis=dict(range=[0, max(y_values) * 1.25]),
        margin=dict(t=50, b=20, l=10, r=20),
        height=height,
        showlegend=False,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# ЗАГОЛОВОК
# ══════════════════════════════════════════════════════════════════════════════
st.title("Анализ рынка — Unified Promo Hub")
st.markdown(
    "Антон Москалюк · mini CEO 2026 · 2026-05-04  \n"
    "Источники: desk-research (112+ источников, апрель–май 2026), "
    "опрос (n=35, Google Forms), Data Insight, АКАР, АРИР, Frank RG, ВЦИОМ."
)
st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# §1 — TAM / SAM / SOM
# ══════════════════════════════════════════════════════════════════════════════
st.header("§1 — TAM / SAM / SOM")
st.markdown(
    "Оценка в **пользователях** — соответствует 1-pager. "
    "Справочно: оценка в рублях — ниже."
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("TAM", "60 млн", help="Все онлайн-покупатели РФ (расчёт: e-com GMV 13,4 трлн ₽ ÷ средний чек)")
    st.caption("Все онлайн-покупатели РФ  \n_Data Insight eCommerce 2026_")
with col2:
    st.metric("SAM", "10 млн", help="Клиенты Т-Банка с ≥1 онлайн-покупкой в мес. (оценочно)")
    st.caption("Клиенты Т-Банка с ≥1 онлайн-покупкой/мес  \n_(оценочно, на основе 34M MAU × ~30% доля онлайн-активных)_")
with col3:
    st.metric("SOM", "2,8 млн", help="MAU Unified Promo Hub к месяцу 12 — base-сценарий ФЭМ")
    st.caption("MAU Unified Promo Hub к мес. 12 (base, ФЭМ)  \n_внутренний прогноз, см. Калькулятор ФЭМ_")

st.markdown("")
st.markdown("**Воронка TAM → SAM → SOM** (концентрические уровни):")

fig_funnel = go.Figure(go.Funnel(
    y=["TAM — все онлайн-покупатели РФ", "SAM — клиенты Т-Банка (онлайн-активные)", "SOM — MAU UPH к мес. 12"],
    x=[60_000_000, 10_000_000, 2_800_000],
    textinfo="value+percent initial",
    marker=dict(color=[TEAL, YELLOW, GREEN]),
    connector=dict(line=dict(color=GRAY, dash="dot", width=1)),
))
fig_funnel.update_layout(
    margin=dict(t=20, b=20, l=10, r=10),
    height=260,
)
st.plotly_chart(fig_funnel, use_container_width=True)

with st.expander("📐 Оценка в рублях (справочно, другая методика)"):
    st.markdown("""
| Уровень | Диапазон | Логика |
|---|---|---|
| **TAM** (performance-пул РФ) | **350–440 млрд ₽** | Интернет-реклама и продвижение АРИР 2025: 1,57 трлн ₽; performance-сегмент ~25% |
| **SAM** (партнёрский промо-пул онлайн) | **60–130 млрд ₽** | Промоиндустрия АКАР 2025 (60,9 млрд ₽) + top-down: 13,4 трлн × 20–35% × 3–8% комиссии |
| **SOM** (доля Т-Банка в горизонте 3 лет) | **3–10 млрд ₽** | MAU 34M × проникновение промо 5–20% × ARPU ~200–500 ₽/год (оценочно) |

_Источники: Data Insight eCommerce 2026, АКАР 2025, АРИР 2025; оценочно._
""")

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# §2 — ДИНАМИКА РЫНКА
# ══════════════════════════════════════════════════════════════════════════════
st.header("§2 — Динамика рынка e-com РФ 2022–2025")

col_a, col_b = st.columns(2)
with col_a:
    fig_ecom = go.Figure()
    years = ["2022", "2023", "2024", "2025"]
    gmv   = [5.7, 7.85, 11.2, 13.4]
    fig_ecom.add_trace(go.Bar(
        x=years, y=gmv,
        marker_color=[TEAL, TEAL, TEAL, GREEN],
        text=[f"{v} трлн ₽" for v in gmv],
        textposition="outside",
        name="e-com GMV",
    ))
    fig_ecom.update_layout(
        title_text="e-com GMV РФ (трлн ₽), Data Insight",
        yaxis=dict(range=[0, 16], title="трлн ₽"),
        margin=dict(t=50, b=20, l=10, r=10),
        height=300,
        showlegend=False,
    )
    st.plotly_chart(fig_ecom, use_container_width=True)
    st.caption("Рост в **2,35×** за 3 года (2022→2025). Источник: Data Insight eCommerce 2026.")

with col_b:
    fig_promo = go.Figure()
    p_years = ["2024", "2025"]
    p_vals  = [66.2, 60.9]
    fig_promo.add_trace(go.Bar(
        x=p_years, y=p_vals,
        marker_color=[TEAL, ORANGE],
        text=[f"{v} млрд ₽" for v in p_vals],
        textposition="outside",
        name="Промоиндустрия АКАР",
    ))
    fig_promo.update_layout(
        title_text="Промоиндустрия АКАР (млрд ₽)",
        yaxis=dict(range=[0, 80], title="млрд ₽"),
        margin=dict(t=50, b=20, l=10, r=10),
        height=300,
        showlegend=False,
    )
    st.plotly_chart(fig_promo, use_container_width=True)
    st.caption(
        "Классическая промоиндустрия −8% в 2025. "
        "Причина: бюджеты уходят **внутрь маркетплейсов** и в digital-performance (АРИР +28%). "
        "Наш продукт должен стать **распределителем трафика** при помощи предиктивных акций "
        "— расширяем концепцию от страницы с промокодами до полноценного targeting-слоя."
    )

st.markdown("")
col_c, col_d = st.columns(2)
with col_c:
    st.metric("Доля маркетплейсов в заказах (2025)", "81%",
              help="WB, Ozon, Яндекс Маркет и др. — Data Insight 2026")
    st.caption("_Data Insight eCommerce 2026_")
with col_d:
    st.metric("Интернет-реклама и продвижение (АРИР 2025)", "1,57 трлн ₽",
              delta="+28% г/г", delta_color="normal")
    st.caption("_АРИР 2025 — там, где сейчас деньги_")

st.info(
    "**Инсайт:** e-com растёт, но промо-бюджеты перетекают в **измеримый digital-результат** "
    "(performance, retail-media внутри маркетплейсов). "
    "Деньги идут туда, где можно измерить результат — UPH должен стоять именно в этой цепочке."
)
st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# §3 — КОНКУРЕНТНЫЙ ЛАНДШАФТ
# ══════════════════════════════════════════════════════════════════════════════
st.header("§3 — Конкурентный ландшафт")

st.subheader("3.1 Ключевые игроки")
st.markdown("""
| Игрок | Тип | Аудитория | Модель | Персонализация промо |
|---|---|---|---|---|
| **Т-Банк (UPH — цель)** | Банк | **34 млн MAU** (FY2025) | CPA + RevShare | ML на транзакциях 34М клиентов — **конкурентный актив** |
| **Т-Банк (сейчас)** | Банк | 34 млн MAU, MAU промо-раздела н/д | Каталог ~1 125 магазинов | Слабая — раздел «утоплен» в кэшбэке |
| **СберСпасибо** | Банк | **100 млн** участников (фев 2026) | Баллы + CPA/RS в экосистеме | Персонализация с 04.2024; Мегамаркет |
| **Яндекс Плюс** | Небанк | **47,5 млн** подписчиков (+21% г/г, фев 2026) | Подписка + баллы партнёров | Экосистемная (поиск + стриминг + доставка) |
| **ВТБ** | Банк | **~15,5 млн** под программой | Рублёвый кэшбэк (RS) | Только выбор категорий, нет промокодов |
| **Letyshops** | Небанк | **~29 млн** глобально | CPA-кэшбэк | По категориям магазинов |
| **SEO-агрегаторы** (promokodus, promokod.ru) | Небанк | 0,5–1 млн SE-визитов/мес | CPA + display | Отсутствует |
""")
st.caption(
    "⚠️ Методологическое предупреждение: Сбер «100 млн» — зарегистрированных в программе; "
    "Яндекс «47,5 млн» — активные платные подписчики; "
    "Т-Банк «34 млн» — active clients с транзакцией за период. Нельзя сравнивать напрямую."
)

st.subheader("3.2 Матрица позиционирования 2×2")
st.markdown("**Ось X: Персонализация промо · Ось Y: Охват аудитории**")

fig_matrix = go.Figure()

players = [
    # name, personalization (0–10), reach (millions), color, size
    ("SEO-агрегаторы", 1.0, 1.0,    GRAY,   14),
    ("Letyshops",       2.5, 10.0,   ORANGE, 16),
    ("ВТБ",            3.0, 15.5,   TEAL,   18),
    ("Т-Банк сейчас",  4.0, 34.0,   YELLOW, 20),
    ("Яндекс Плюс",    5.5, 47.5,   RED,    24),
    ("СберСпасибо",    5.0, 100.0,  PURPLE, 30),
    ("Т-Банк ЦЕЛЬ",    9.5, 34.0,   GREEN,  22),
]

for name, pers, reach, color, size in players:
    fig_matrix.add_trace(go.Scatter(
        x=[pers], y=[reach],
        mode="markers+text",
        marker=dict(size=size, color=color, line=dict(width=1, color="white")),
        text=[name],
        textposition="top center" if name != "Т-Банк сейчас" else "bottom center",
        name=name,
    ))

# Стрелка: Т-Банк сейчас → Т-Банк ЦЕЛЬ
fig_matrix.add_annotation(
    x=9.5, y=34.0,
    ax=4.0, ay=34.0,
    xref="x", yref="y",
    axref="x", ayref="y",
    showarrow=True,
    arrowhead=3,
    arrowcolor=GREEN,
    arrowwidth=2,
)

# Квадрант "белое пятно"
fig_matrix.add_shape(
    type="rect",
    x0=7.5, x1=10.5, y0=20, y1=60,
    fillcolor=GREEN, opacity=0.07,
    line=dict(color=GREEN, width=1, dash="dot"),
)
fig_matrix.add_annotation(
    x=9.0, y=55,
    text="Незанятая ниша<br>(высокая персонализация<br>+ значимый охват)",
    showarrow=False,
    font=dict(color=GREEN, size=11),
    align="center",
)

fig_matrix.update_layout(
    xaxis=dict(title="Персонализация промо (0 — нет, 10 — максимум)", range=[0, 11]),
    yaxis=dict(title="Охват аудитории (млн)", range=[0, 115]),
    margin=dict(t=20, b=40, l=60, r=20),
    height=480,
    showlegend=False,
)
st.plotly_chart(fig_matrix, use_container_width=True)
st.success(
    "**Ключевой вывод:** Сбер и Яндекс не займут нишу «высокая персонализация промо» — "
    "им достаточно охвата. Т-Банку не нужно догонять их по масштабу. "
    "Задача — переместиться **вправо** по оси персонализации при сохранении 34M MAU. "
    "Это белое пятно на карте."
)

st.subheader("3.3 Тепловая карта конкуренции")
st.markdown("""
| Зона | Плотность | Кто |
|---|---|---|
| Банковский кэшбэк по категориям | 🔴 Очень высокая | ВТБ, Альфа, Газпромбанк, Райффайзен |
| Супер-подписки | 🔴 Очень высокая | Яндекс Плюс (47,5М), СберСпасибо (100М) |
| Маркетплейс-промо | 🟠 Высокая | WB, Ozon — deep discounts + кошельки |
| Affiliate/кэшбэк-браузер | 🟠 Высокая | Letyshops; Honey умирает |
| SEO-агрегаторы | 🟡 Средняя | ~0,5–1 млн SE-визитов/мес у крупных |
| **Банковский CLO (Card-Linked Offer) + персонализация** | 🟢 Слабая | **Незанятая ниша — цель UPH (Unified Promo Hub)** |
""")
st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# §4 — ПОВЕДЕНИЕ ПОЛЬЗОВАТЕЛЕЙ
# ══════════════════════════════════════════════════════════════════════════════
st.header("§4 — Поведение пользователей")

st.subheader("4.1 Точки входа: где ищут промокод")

col_e, col_f = st.columns([3, 2])
with col_e:
    st.plotly_chart(hbar(
        labels=["Поисковик (Яндекс/Google)", "Не ищу — само попадается",
                "Агрегаторы", "Мобильное приложение банка",
                "Сайт самого магазина", "Telegram-каналы", "Другое"],
        values=[66, 49, 29, 26, 26, 14, 6],
        title="Где ищут промокод (опрос, n=35, мультивыбор, %)",
        color=TEAL,
    ), use_container_width=True)
    st.caption("Опрос, n=35, Google Forms, 2026-04-29–05-04. Convenience sample, 18–24 лет, МСК/СПб.")

with col_f:
    st.markdown("**Прокси-данные (репрезентативные выборки)**")
    st.markdown("""
| Метрика | Значение | Источник |
|---|---|---|
| Начинают поиск **товаров** с агрегаторов/маркетплейсов | **64%** | ВЦИОМ, янв 2026, n=1500 |
| Начинают с поисковиков | **27%** | ВЦИОМ, там же |
| Стали чаще искать через поисковик ради экономии | **62%** | Ашманов и партнёры, сен 2025, n=1000 |
| Используют только Яндекс при поиске товаров | **71%** (vs 54% в 2022) | Там же |
| Банк как точка входа | Не упоминается | ВЦИОМ 2026; Frank RG 2025 |
""")
    st.warning(
        "**Банк не стоит в цепочке привычки** при поиске промокода. "
        "Даже 26% через банк-приложение (опрос) — это уже **сконвертированный** сегмент, "
        "а не «потерянный трафик»."
    )

st.subheader("4.2 Барьеры при использовании промокодов")
st.plotly_chart(hbar(
    labels=["Промокод не сработал / недействителен", "Трудно найти для нужного магазина",
            "Не знал о разделе в банке", "Условия непонятны / мелкий шрифт",
            "Кэшбэк выгоднее", "Нет проблем — пользуюсь легко"],
    values=[69, 54, 31, 23, 14, 11],
    title="Что мешало использовать промокод (опрос, n=35, мультивыбор, %)",
    color=RED,
), use_container_width=True)
st.info(
    "**Инсайт:** главный враг промокода — **ненадёжность (69%)** и **сложность поиска (54%)**, "
    "а не предпочтение кэшбэка (14%). "
    "Это значит: решение — не убирать промокоды, а устранить transaction cost поиска + ввода."
)

st.subheader("4.3 Кэшбэк vs промокод: в чём настоящий конкурент")

col_g, col_h = st.columns(2)
with col_g:
    st.plotly_chart(hbar(
        labels=["Кэшбэк начисляется автоматически",
                "Промокод нужно искать — это время",
                "Не уверен(а), что сработает",
                "Не нужно вводить код",
                "Кэшбэк не кажется проще",
                "Промокод не выгоднее"],
        values=[51, 43, 29, 29, 20, 11],
        title="Почему кэшбэк проще промокода? (опрос, мультивыбор, %)",
        color=ORANGE,
    ), use_container_width=True)

with col_h:
    st.markdown("**Количественные бенчмарки (desk-research)**")
    st.markdown("""
| Метрика | Значение | Источник |
|---|---|---|
| Пользовались банковским кэшбэком | **69%** россиян | НАФИ |
| «Лучше меньше, но рублями» | **68%** | Romir, апрель 2024 |
| Ценят выбор категорий кэшбэка | **67%** | Frank RG 2025 |
| Партнёрские офферы в лояльности | **39%** | Frank RG 2025 |
| Конверсия с промокодом vs без | **~1,5–2×** | Kokoc Group / ECOMHUB |
| Доля заказов с промокодом в CPA-сетях | **21%** (2024, рост с 19%) | Admitad / 27 млн заказов |
""")
    st.success(
        "**Ключевой вывод:** кэшбэк выигрывает не выгодой, а **пассивностью** (51%). "
        "Задача UPH — сделать промокод таким же пассивным: "
        "triggered delivery до открытия корзины = нулевой transaction cost. "
        "_(Другими словами — оптимизировать процесс поиска и выбора перед покупкой)_"
    )

st.subheader("4.4 Предиктивный оффер: реакция пользователей")
c1, c2 = st.columns(2)
with c1:
    fig_q7b = go.Figure(go.Pie(
        labels=["Вот это да! Именно так банк должен работать",
                "Интересно, но немного жутковато",
                "Нейтрально",
                "Раздражает"],
        values=[49, 29, 20, 3],
        marker=dict(colors=[GREEN, YELLOW, TEAL, RED]),
        textinfo="percent+label",
        hole=0.35,
    ))
    fig_q7b.update_layout(
        title_text="Q7б: предиктивный оффер до покупки (n=35)",
        margin=dict(t=50, b=20, l=10, r=10),
        height=320,
    )
    st.plotly_chart(fig_q7b, use_container_width=True)
with c2:
    st.markdown("**77% позитивных/заинтересованных** (49% + 28%)")
    st.markdown("""
Пример из анкеты:
> «Вы обычно заказываете еду в пятницу — вот промокод −200₽ на четверг»
> «До 8 марта 12 дней — вот скидка на цветы, как в прошлом году»

**Privacy concern (29%)** — требует UX-объяснения «почему именно вам»  
(прозрачный CTA: «На основе ваших покупок»).

Только **3% (n=1) негативных** — это пренебрежимо малый сигнал.
""")
st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# §5 — УЦП: НЕЗАНЯТАЯ НИША
# ══════════════════════════════════════════════════════════════════════════════
st.header("§5 — Незанятая ниша: УЦП Unified Promo Hub")

st.markdown("""
**Рыночная логика в одной фразе:**
> *Пассивная акция формирует лояльность, активная — инициирует покупку.*

Никто из конкурентов не совмещает три вещи одновременно:
""")

col_i, col_j, col_k = st.columns(3)
with col_i:
    st.markdown("#### 🏦 Транзакционные данные")
    st.markdown(
        "**34 млн клиентов**, ~9,8 трлн ₽ GMV карт (FY2025). "
        "Банк видит каждую покупку через MCC-коды. "
        "Ни один агрегатор этого не имеет."
    )
with col_j:
    st.markdown("#### 🎯 Targeting по сегментам")
    st.markdown(
        "Партнёр настраивает **кого** ему нужно: "
        "новых, ушедших, рискованных, лояльных. "
        "Акцию на главном экране показываем только конкретным категориям пользователей, которые требуются партнёру."
    )
with col_k:
    st.markdown("#### ⚡ Момент планирования")
    st.markdown(
        "Оффер появляется **до** открытия корзины — "
        "в зоне планирования (3–10 дней по паттернам трат). "
        "Не после покупки, не случайно."
    )

st.markdown("")
st.markdown("**Сравнение с главными конкурентами по 5 параметрам:**")

params = ["Транзакционные данные", "Targeting по сегментам",
          "Moment-of-planning delivery", "Incremental GMV метрика", "Гибридный путь web→app"]
competitors_scores = {
    "Т-Банк UPH (цель)": [5, 5, 5, 5, 5],
    "СберСпасибо":        [4, 3, 2, 1, 2],
    "Яндекс Плюс":        [2, 3, 3, 1, 3],
    "SEO-агрегаторы":     [1, 1, 1, 1, 2],
}
colors_radar = [GREEN, PURPLE, RED, GRAY]

fig_radar = go.Figure()
for i, (name, scores) in enumerate(competitors_scores.items()):
    fig_radar.add_trace(go.Scatterpolar(
        r=scores + [scores[0]],
        theta=params + [params[0]],
        fill="toself" if name == "Т-Банк UPH (цель)" else "none",
        name=name,
        line=dict(color=colors_radar[i], width=2),
        opacity=0.85 if name == "Т-Банк UPH (цель)" else 0.6,
    ))
fig_radar.update_layout(
    polar=dict(
        radialaxis=dict(visible=True, range=[0, 5]),
    ),
    margin=dict(t=20, b=20, l=20, r=20),
    height=400,
    legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
)
st.plotly_chart(fig_radar, use_container_width=True)

st.markdown("**Монетизационная модель (совместима с 1-pager §6):**")
col_l, col_m = st.columns(2)
with col_l:
    st.markdown("""
**CPA** (Cost Per Action) за каждый подтверждённый redemption:
- **50–300 ₽** — повторные заказы, FMCG, еда
- **300–1 000 ₽** — high-ticket: путешествия, электроника, финпродукты

**RevShare** — **3–8%** от GMV транзакции
""")
with col_m:
    st.markdown("""
**Партнёр платит только за:**
- ✅ Доказанный приток нужного **сегмента**
- ✅ Verified redemption (транзакция атрибутирована)
- ✅ Incremental GMV — не «cannibal» клиентов, которые купили бы и без промо

**Anti-Honey принцип:** атрибуция прозрачна для партнёра;
алгоритм ранжирует по ценности для **пользователя**, не только по марже банка.
""")

st.markdown("")
st.subheader("Сводное УЦП по сторонам платформы")
st.markdown("""
| Сторона | Что получает | Почему не получает этого сейчас |
|---|---|---|
| **Пользователь** | Персональный оффер без поиска в момент планирования покупки | Раздел «утоплен»; 40% awareness-барьер (опрос Q8) |
| **Партнёр** | Нужный сегмент клиентов + метрика incremental GMV | Нет targeting по транзакциям; ROI промо непрозрачен |
| **Т-Банк** | CPA/RevShare-выручка + рост MAU раздела + data flywheel | Нет Unified Promo Hub — два разрозненных канала без ML-слоя |
""")

st.markdown("---")
st.caption(
    "Источники: Data Insight eCommerce 2026 · АКАР 2025 · АРИР 2025 · Frank RG 2025 · "
    "ВЦИОМ январь 2026 (n=1500) · Ашманов и партнёры сентябрь 2025 (n=1000) · "
    "T-Technologies FY2025 IR · Cardlytics 10-K FY2024 · Admitad / ECOMHUB 2024 · "
    "Опрос (n=35, Google Forms, 2026-04-29–05-04, convenience sample, МСК/СПб, 18–24 лет) · "
    "Все данные из опроса — направленные тренды, не репрезентативная статистика."
)
