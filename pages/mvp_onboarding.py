"""
MVP Onboarding — прототип пользовательского пути на сайте промокодов Т-Банка

Демонстрирует 5-шаговый флоу:
  Шаг 0: Лендинг (структура promokod.tbank.ru) + баннер авторизации
  Шаг 1: Форма входа (телефон / e-mail)
  Шаг 2: Ввод кода из SMS / письма (пустышка)
  Шаг 3: Онбординг-опрос (3 экрана → частотная матрица → сегмент new_web_N)
  Шаг 4: Топ-3 промокода + сводка подписки по расписанию
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Для дома", "Техника", "Одежда", "Книги",
    "Зоотовары", "Продукты", "Спорт", "Детские товары",
]

POPULAR_SHOPS = [
    ("AliExpress",        24),
    ("Золотое Яблоко",    10),
    ("Tutu.ru",            7),
    ("Купибилет",          7),
    ("Genotek",           25),
    ("Divan.ru",          10),
]

FRESH_DEALS = [
    {
        "shop": "Отели Т-Банка",
        "desc": "Скидка до 20% на первое бронирование",
        "code": "ВЕСНА",
    },
    {
        "shop": "Kanzler",
        "desc": "Скидка до 50% на мужскую одежду",
        "code": "KANZLER50",
    },
    {
        "shop": "Альпина книги",
        "desc": "Скидка 500 ₽ при покупке от 2 000 ₽",
        "code": "ALPINA500",
    },
]

EXPIRING_DEALS = [
    {
        "shop": "Яндекс Афиша",
        "desc": "Скидка 10% на концерт «Баста — Guf» при покупке от 3 000 ₽",
        "ttl": "1 день",
    },
    {
        "shop": "Яндекс Афиша",
        "desc": "Скидка 400 ₽ на юбилейный концерт «Руки вверх!» от 3 000 ₽",
        "ttl": "1 день",
    },
]

# Частотные варианты по категориям
FREQ_OPTIONS = {
    "Одежда и обувь":         ["Не покупаю", "Раз в квартал", "Раз в месяц", "Раз в неделю"],
    "Продукты и рестораны":   ["Не покупаю", "Раз в месяц", "Раз в неделю", "Несколько раз в неделю"],
    "Путешествия и отели":    ["Не путешествую", "Раз в год", "Раз в полгода", "Раз в квартал"],
    "Техника и электроника":  ["Не покупаю", "Раз в год", "Раз в полгода", "Раз в квартал"],
    "Красота и здоровье":     ["Не покупаю", "Раз в квартал", "Раз в месяц", "Раз в неделю"],
    "Дом и интерьер":         ["Не покупаю", "Раз в год", "Раз в полгода", "Раз в квартал"],
}

# Предиктивные интервалы рассылки (текст для сводки, индекс = балл 0–3)
FREQ_LABELS = {
    "Одежда и обувь":        ["—", "раз в квартал (за 2 нед. до цикла)", "раз в месяц (за 5 дней)", "каждую неделю (пн)"],
    "Продукты и рестораны":  ["—", "раз в месяц", "раз в неделю", "2–3 раза в неделю"],
    "Путешествия и отели":   ["—", "раз в год (за 4 нед. до поездки)", "раз в полгода", "раз в квартал"],
    "Техника и электроника": ["—", "раз в год (перед 11.11/Чёрной пятницей)", "раз в полгода", "раз в квартал"],
    "Красота и здоровье":    ["—", "раз в квартал (за 5 дней до «дна» запасов)", "раз в месяц", "каждую неделю"],
    "Дом и интерьер":        ["—", "раз в год (весна/осень)", "раз в полгода", "раз в квартал"],
}

PROMO_CATALOG = {
    "Одежда и обувь": [
        {"shop": "Kanzler",      "desc": "Скидка до 50% на мужскую одежду",             "code": "KANZLER50"},
        {"shop": "BRANDSHOP",    "desc": "Скидка 10% на брендовую одежду",              "code": "BRAND10"},
        {"shop": "SuperStep",    "desc": "Скидка 15% на брендовые кроссовки от 5 000 ₽","code": "STEP15"},
    ],
    "Продукты и рестораны": [
        {"shop": "Яндекс Еда",   "desc": "Скидка 300 ₽ на первый заказ от 800 ₽",      "code": "YEDA300"},
        {"shop": "Delivery Club","desc": "Бесплатная доставка на 3 заказа",              "code": "DCFREE3"},
        {"shop": "ВкусВилл",     "desc": "Скидка 10% на весь заказ онлайн",             "code": "VV10"},
    ],
    "Путешествия и отели": [
        {"shop": "Отели Т-Банка","desc": "Скидка до 20% на первое бронирование",        "code": "ВЕСНА"},
        {"shop": "Tutu.ru",      "desc": "Скидка 500 ₽ на авиабилеты от 3 000 ₽",       "code": "TUTU500"},
        {"shop": "Купибилет",    "desc": "Кэшбэк 7% на ж/д билеты",                    "code": "KUP7"},
    ],
    "Техника и электроника": [
        {"shop": "DNS",          "desc": "Скидка 5% на смартфоны и планшеты",           "code": "DNS5"},
        {"shop": "Ситилинк",     "desc": "Скидка 3 000 ₽ на ноутбуки от 50 000 ₽",     "code": "SL3000"},
        {"shop": "AliExpress",   "desc": "Скидка 8% на электронику от 2 000 ₽",         "code": "ALI8"},
    ],
    "Красота и здоровье": [
        {"shop": "Золотое Яблоко","desc": "Скидка 15% на уходовую косметику",           "code": "ZYA15"},
        {"shop": "iHerb",         "desc": "Скидка 10% на первый заказ",                "code": "IHERB10"},
        {"shop": "Genotek",       "desc": "Скидка 20% на тест ДНК",                    "code": "GEN20"},
    ],
    "Дом и интерьер": [
        {"shop": "Divan.ru",     "desc": "Скидка 10% на диваны и кресла",              "code": "DIVAN10"},
        {"shop": "IKEA",         "desc": "Скидка 500 ₽ при покупке от 5 000 ₽",        "code": "IKEA500"},
        {"shop": "Все инструменты","desc": "Скидка 7% на весь ассортимент",            "code": "TOOL7"},
    ],
}

SEGMENT_NAMES = {
    "new_web_1": "Пассивный подписчик",
    "new_web_2": "Регулярный покупатель",
    "new_web_3": "Активный охотник за скидками",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def init_state():
    defaults = {
        "mvp_step": 0,
        "auth_contact": "",
        "auth_method": "Телефон",
        "onb_screen": "3a",
        "onb_activity": 0,
        "freq_matrix": {cat: 0 for cat in FREQ_OPTIONS},
        "channel_score": 0,
        "channel_label": "по e-mail",
        "segment": None,
        "top_category": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def go_to(step: int):
    st.session_state["mvp_step"] = step


def compute_segment():
    activity_score = st.session_state["onb_activity"]
    channel_score  = st.session_state["channel_score"]
    max_freq_score = max(st.session_state["freq_matrix"].values())
    total = activity_score + channel_score + max_freq_score

    if total <= 2:
        seg = "new_web_1"
    elif total <= 5:
        seg = "new_web_2"
    else:
        seg = "new_web_3"

    top_cat = max(
        st.session_state["freq_matrix"],
        key=lambda c: st.session_state["freq_matrix"][c],
    )
    if st.session_state["freq_matrix"][top_cat] == 0:
        top_cat = "Одежда и обувь"

    st.session_state["segment"]     = seg
    st.session_state["top_category"] = top_cat


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def inject_css():
    st.markdown("""
    <style>
    /* Шапка */
    .tbank-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #FFDD2D;
        padding: 12px 24px;
        border-radius: 12px;
        margin-bottom: 16px;
    }
    .tbank-logo {
        font-size: 22px;
        font-weight: 800;
        color: #000;
        letter-spacing: -0.5px;
    }
    .tbank-logo span { color: #333; font-weight: 400; font-size: 14px; }

    /* Баннер авторизации */
    .auth-banner {
        background: linear-gradient(135deg, #FFDD2D 0%, #FFB800 100%);
        border-radius: 16px;
        padding: 28px 32px;
        margin: 16px 0 24px 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
    }
    .auth-banner-text h2 { margin: 0 0 6px 0; font-size: 22px; color: #000; }
    .auth-banner-text p  { margin: 0; font-size: 14px; color: #333; }

    /* Категории */
    .cat-chip {
        display: inline-block;
        background: #F5F5F5;
        border-radius: 20px;
        padding: 6px 14px;
        margin: 4px;
        font-size: 13px;
        font-weight: 500;
        color: #222;
        cursor: pointer;
        border: 1px solid #E0E0E0;
    }

    /* Карточка магазина */
    .shop-card {
        background: #FAFAFA;
        border: 1px solid #EBEBEB;
        border-radius: 12px;
        padding: 14px 12px;
        text-align: center;
        height: 90px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .shop-card b { font-size: 13px; }
    .shop-card small { color: #888; font-size: 11px; }

    /* Карточка акции */
    .deal-card {
        background: #fff;
        border: 1px solid #E8E8E8;
        border-radius: 12px;
        padding: 16px;
        height: 100%;
    }
    .deal-card .shop-name { font-weight: 700; font-size: 14px; margin-bottom: 4px; }
    .deal-card .deal-desc { font-size: 13px; color: #444; margin-bottom: 10px; }
    .deal-code {
        background: #F5F5F5;
        border: 1px dashed #CCC;
        border-radius: 6px;
        padding: 4px 10px;
        font-family: monospace;
        font-size: 13px;
        letter-spacing: 1px;
    }

    /* Карточка истекающей акции */
    .expiring-card {
        background: #FFF8E7;
        border: 1px solid #FFD54F;
        border-radius: 12px;
        padding: 14px;
    }
    .expiring-ttl {
        background: #FF5722;
        color: #fff;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 6px;
    }

    /* Форма авторизации */
    .auth-card {
        max-width: 400px;
        margin: 40px auto;
        background: #fff;
        border: 1px solid #E8E8E8;
        border-radius: 20px;
        padding: 36px 32px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    }
    .auth-card h2 { text-align: center; margin-bottom: 24px; }

    /* Шаг онбординга */
    .onb-card {
        max-width: 640px;
        margin: 0 auto;
        background: #fff;
        border: 1px solid #E8E8E8;
        border-radius: 20px;
        padding: 36px 32px;
    }
    .onb-progress { font-size: 12px; color: #888; margin-bottom: 20px; }

    /* Карточка промокода */
    .promo-card {
        background: #fff;
        border: 2px solid #FFDD2D;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 12px;
        position: relative;
    }
    .promo-badge {
        position: absolute;
        top: 12px; right: 14px;
        background: #FFDD2D;
        border-radius: 8px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 700;
    }
    .promo-shop { font-weight: 700; font-size: 16px; margin-bottom: 4px; }
    .promo-desc { color: #555; font-size: 13px; margin-bottom: 12px; }
    .promo-code-box {
        background: #F5F5F5;
        border: 1.5px dashed #999;
        border-radius: 8px;
        padding: 8px 14px;
        font-family: monospace;
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 1.5px;
        display: inline-block;
    }

    /* Сводка подписки */
    .subscription-card {
        background: linear-gradient(135deg, #E8F5E9 0%, #F1F8E9 100%);
        border: 1.5px solid #A5D6A7;
        border-radius: 16px;
        padding: 24px 28px;
        margin-top: 24px;
    }
    .subscription-card h4 { margin: 0 0 16px 0; font-size: 16px; }
    .sub-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #C8E6C9; font-size: 13px; }
    .sub-row:last-child { border-bottom: none; }
    .sub-cat { font-weight: 600; }
    .sub-interval { color: #388E3C; }

    /* Сегментный бейдж */
    .seg-badge {
        display: inline-block;
        background: #222;
        color: #FFDD2D;
        border-radius: 8px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 700;
        margin-top: 4px;
    }

    /* Скрыть стандартный st header */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Шаг 0: Лендинг
# ---------------------------------------------------------------------------

def render_landing():
    # Шапка
    col_logo, col_btn = st.columns([8, 2])
    with col_logo:
        st.markdown(
            '<div class="tbank-logo">Т‑Банк <span>Промокоды</span></div>',
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button("Войти", key="header_login", type="primary", use_container_width=True):
            go_to(1)
            st.rerun()

    st.divider()

    # Баннер авторизации
    st.markdown("""
    <div class="auth-banner">
      <div class="auth-banner-text">
        <h2>Промокоды, подобранные лично для вас</h2>
        <p>Авторизуйтесь — и мы будем присылать промокоды точно в тот момент,<br>
           когда вы обычно делаете покупки. Никакого спама, только нужные предложения.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_cta, _ = st.columns([2, 5])
    with col_cta:
        if st.button("Получить личные промокоды", key="banner_cta", type="primary", use_container_width=True):
            go_to(1)
            st.rerun()

    st.markdown("---")

    # Категории
    st.markdown("### Найдите лучшие промокоды в подборках Т‑Банка")
    chips_html = "".join(f'<span class="cat-chip">{c}</span>' for c in CATEGORIES)
    st.markdown(chips_html, unsafe_allow_html=True)

    st.markdown("---")

    # Популярные магазины
    st.markdown("### Популярные магазины")
    cols = st.columns(6)
    for i, (shop, cnt) in enumerate(POPULAR_SHOPS):
        with cols[i]:
            st.markdown(
                f'<div class="shop-card"><b>{shop}</b><br><small>{cnt} промокодов</small></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Свежие акции
    st.markdown("### Свежие акции и промокоды")
    cols = st.columns(3)
    for i, deal in enumerate(FRESH_DEALS):
        with cols[i]:
            st.markdown(f"""
            <div class="deal-card">
              <div class="shop-name">{deal['shop']}</div>
              <div class="deal-desc">{deal['desc']}</div>
              <span class="deal-code">{deal['code']}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Истекающие
    st.markdown("### Срок промокода истекает — успейте воспользоваться")
    cols = st.columns(2)
    for i, deal in enumerate(EXPIRING_DEALS):
        with cols[i]:
            st.markdown(f"""
            <div class="expiring-card">
              <span class="expiring-ttl">⏰ {deal['ttl']}</span>
              <div style="font-weight:700;margin-bottom:4px;">{deal['shop']}</div>
              <div style="font-size:13px;color:#555;">{deal['desc']}</div>
            </div>
            """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Шаг 1: Форма авторизации
# ---------------------------------------------------------------------------

def render_auth_form():
    st.markdown(
        '<div class="tbank-logo" style="margin-bottom:24px;">Т‑Банк <span>Промокоды</span></div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("## Войдите в Т‑Банк")
        st.caption("Для подписки на персональные промокоды")

        method = st.radio(
            "Способ входа",
            ["Телефон", "E-mail"],
            horizontal=True,
            key="auth_method_select",
        )
        st.session_state["auth_method"] = method

        if method == "Телефон":
            contact = st.text_input("Номер телефона", placeholder="+7 (___) ___-__-__", key="auth_input")
        else:
            contact = st.text_input("E-mail адрес", placeholder="example@mail.ru", key="auth_input")

        st.session_state["auth_contact"] = contact

        st.markdown("<br>", unsafe_allow_html=True)

        col_back, col_next = st.columns([1, 2])
        with col_back:
            if st.button("← Назад", use_container_width=True):
                go_to(0)
                st.rerun()
        with col_next:
            if st.button("Получить код", type="primary", use_container_width=True):
                if contact and len(contact.strip()) >= 5:
                    go_to(2)
                    st.rerun()
                else:
                    st.warning("Введите телефон или e-mail")

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("Нажимая «Получить код», вы соглашаетесь с условиями обработки персональных данных.")


# ---------------------------------------------------------------------------
# Шаг 2: OTP-пустышка
# ---------------------------------------------------------------------------

def render_auth_verify():
    st.markdown(
        '<div class="tbank-logo" style="margin-bottom:24px;">Т‑Банк <span>Промокоды</span></div>',
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])
    with center:
        contact = st.session_state.get("auth_contact", "")
        method  = st.session_state.get("auth_method", "Телефон")
        channel = "SMS" if method == "Телефон" else "письмо на почту"

        st.markdown(f"## Введите код")
        st.caption(f"Мы отправили {channel} на **{contact}**")

        code = st.text_input(
            "Код подтверждения",
            placeholder="Например: 1234",
            max_chars=6,
            key="otp_input",
        )

        st.markdown("<br>", unsafe_allow_html=True)

        col_back, col_next = st.columns([1, 2])
        with col_back:
            if st.button("← Назад", use_container_width=True):
                go_to(1)
                st.rerun()
        with col_next:
            if st.button("Войти", type="primary", use_container_width=True):
                if code and len(code.strip()) >= 1:
                    go_to(3)
                    st.rerun()
                else:
                    st.warning("Введите любой код из поля выше")

        st.caption("Демо-режим: подойдёт любой код.")


# ---------------------------------------------------------------------------
# Шаг 3: Онбординг (3 экрана)
# ---------------------------------------------------------------------------

def render_onboarding():
    st.markdown(
        '<div class="tbank-logo" style="margin-bottom:8px;">Т‑Банк <span>Промокоды</span></div>',
        unsafe_allow_html=True,
    )

    screen = st.session_state.get("onb_screen", "3a")

    # Прогресс-бар
    progress_map = {"3a": 0.33, "3b": 0.66, "3c": 0.99}
    step_label   = {"3a": "Шаг 1 из 3", "3b": "Шаг 2 из 3", "3c": "Шаг 3 из 3"}
    st.progress(progress_map[screen], text=f"Настройка подписки — {step_label[screen]}")

    if screen == "3a":
        _render_onb_3a()
    elif screen == "3b":
        _render_onb_3b()
    else:
        _render_onb_3c()


def _render_onb_3a():
    st.markdown("### Расскажите о себе")
    st.markdown("Мы настроим расписание рассылки, чтобы промокоды приходили когда нужно — не раньше и не позже.")

    st.markdown("<br>", unsafe_allow_html=True)

    activity = st.radio(
        "Как часто вы в целом делаете онлайн-покупки?",
        options=[
            "Реже раза в месяц",
            "1–3 раза в месяц",
            "Раз в неделю и чаще",
        ],
        index=st.session_state["onb_activity"],
        key="radio_3a",
    )

    score_map = {
        "Реже раза в месяц": 0,
        "1–3 раза в месяц":  1,
        "Раз в неделю и чаще": 2,
    }

    st.markdown("<br>", unsafe_allow_html=True)

    col_back, col_next = st.columns([1, 2])
    with col_back:
        if st.button("← Назад", use_container_width=True):
            go_to(2)
            st.rerun()
    with col_next:
        if st.button("Далее →", type="primary", use_container_width=True):
            st.session_state["onb_activity"] = score_map[activity]
            st.session_state["onb_screen"]   = "3b"
            st.rerun()


def _render_onb_3b():
    st.markdown("### Как часто вы покупаете в этих категориях?")
    st.markdown(
        "Выберите частоту для каждой категории. Это поможет нам понять, "
        "**когда именно** присылать промокод — за несколько дней до вашей следующей покупки."
    )
    st.markdown("<br>", unsafe_allow_html=True)

    freq_matrix = dict(st.session_state["freq_matrix"])

    for cat, options in FREQ_OPTIONS.items():
        current_idx = freq_matrix.get(cat, 0)
        col_label, col_radio = st.columns([2, 5])
        with col_label:
            st.markdown(f"**{cat}**")
        with col_radio:
            selected = st.radio(
                cat,
                options=options,
                index=current_idx,
                key=f"radio_{cat}",
                horizontal=True,
                label_visibility="collapsed",
            )
        freq_matrix[cat] = options.index(selected)
        st.divider()

    st.markdown("<br>", unsafe_allow_html=True)

    col_back, col_next = st.columns([1, 2])
    with col_back:
        if st.button("← Назад", use_container_width=True):
            st.session_state["onb_screen"] = "3a"
            st.rerun()
    with col_next:
        if st.button("Далее →", type="primary", use_container_width=True):
            st.session_state["freq_matrix"] = freq_matrix
            st.session_state["onb_screen"]  = "3c"
            st.rerun()


def _render_onb_3c():
    st.markdown("### Как удобнее получать промокоды?")
    st.markdown("Выберите канал — мы будем слать предложения именно туда.")
    st.markdown("<br>", unsafe_allow_html=True)

    channel = st.radio(
        "Канал доставки",
        options=[
            "По e-mail (еженедельный дайджест)",
            "Push-уведомления в браузере",
            "В приложении Т‑Банка (если установлено)",
        ],
        key="radio_3c",
    )

    channel_score_map = {
        "По e-mail (еженедельный дайджест)":       0,
        "Push-уведомления в браузере":              1,
        "В приложении Т‑Банка (если установлено)": 2,
    }
    channel_label_map = {
        "По e-mail (еженедельный дайджест)":       "по e-mail",
        "Push-уведомления в браузере":              "push в браузере",
        "В приложении Т‑Банка (если установлено)": "в приложении Т‑Банка",
    }

    st.markdown("<br>", unsafe_allow_html=True)

    col_back, col_next = st.columns([1, 2])
    with col_back:
        if st.button("← Назад", use_container_width=True):
            st.session_state["onb_screen"] = "3b"
            st.rerun()
    with col_next:
        if st.button("Получить мои промокоды →", type="primary", use_container_width=True):
            st.session_state["channel_score"] = channel_score_map[channel]
            st.session_state["channel_label"] = channel_label_map[channel]
            compute_segment()
            go_to(4)
            st.rerun()


# ---------------------------------------------------------------------------
# Шаг 4: Результат
# ---------------------------------------------------------------------------

def render_result():
    st.markdown(
        '<div class="tbank-logo" style="margin-bottom:16px;">Т‑Банк <span>Промокоды</span></div>',
        unsafe_allow_html=True,
    )

    segment    = st.session_state.get("segment", "new_web_2")
    top_cat    = st.session_state.get("top_category", "Одежда и обувь")
    freq_matrix = st.session_state.get("freq_matrix", {})
    channel    = st.session_state.get("channel_label", "по e-mail")
    seg_name   = SEGMENT_NAMES.get(segment, segment)

    st.success(f"Подписка оформлена! Ваш профиль покупателя: **{seg_name}**")

    st.markdown(f"### Топ‑3 промокода для вас сегодня")
    st.caption(f"Подобраны по вашей главной категории: **{top_cat}**")

    promos = PROMO_CATALOG.get(top_cat, PROMO_CATALOG["Одежда и обувь"])
    cols = st.columns(3)
    for i, promo in enumerate(promos[:3]):
        with cols[i]:
            st.markdown(f"""
            <div class="promo-card">
              <span class="promo-badge">Для вас</span>
              <div class="promo-shop">{promo['shop']}</div>
              <div class="promo-desc">{promo['desc']}</div>
              <span class="promo-code-box">{promo['code']}</span>
            </div>
            """, unsafe_allow_html=True)

    # Сводка подписки
    active_cats = {cat: score for cat, score in freq_matrix.items() if score > 0}

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="subscription-card-header">
      <b>📬 Расписание вашей подписки</b>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        meta_col1, meta_col2 = st.columns([3, 3])
        with meta_col1:
            st.caption(f"Канал: **{channel}**")
        with meta_col2:
            st.caption(f"Профиль: **{seg_name}**")

        st.divider()

        if active_cats:
            for cat, score in sorted(active_cats.items(), key=lambda x: -x[1]):
                interval = FREQ_LABELS.get(cat, ["—"] * 4)[score]
                row_l, row_r = st.columns([3, 4])
                with row_l:
                    st.markdown(f"**{cat}**")
                with row_r:
                    st.markdown(f":green[{interval}]")
        else:
            st.caption("Категории не выбраны — вы будете получать общую подборку")

    # Миграционный CTA для new_web_2 и new_web_3
    if segment in ("new_web_2", "new_web_3"):
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(
            "**Хотите получать промокоды ещё быстрее?** "
            "В приложении Т‑Банка они появляются сразу — без ожидания дайджеста. "
            "Плюс персонализация на основе ваших транзакций."
        )
        col_app, _ = st.columns([2, 5])
        with col_app:
            st.button("Установить приложение Т‑Банка", type="primary", use_container_width=True)

    # Разбор сегментации «под капотом» — для проверяющих
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔍 Как работает сегментация (для проверяющих)"):
        activity_score = st.session_state.get("onb_activity", 0)
        channel_score  = st.session_state.get("channel_score", 0)
        freq_matrix    = st.session_state.get("freq_matrix", {})
        max_freq_score = max(freq_matrix.values()) if freq_matrix else 0
        top_freq_cat   = max(freq_matrix, key=lambda c: freq_matrix[c]) if freq_matrix else "—"
        total_score    = activity_score + channel_score + max_freq_score

        activity_labels = {0: "Реже раза в месяц", 1: "1–3 раза в месяц", 2: "Раз в неделю и чаще"}
        channel_labels  = {0: "e-mail", 1: "push в браузере", 2: "приложение Т‑Банка"}

        st.markdown("**Входные сигналы опроса:**")
        st.markdown(f"""
| Вопрос | Ответ | Балл |
|--------|-------|------|
| 3а. Общая онлайн-активность | {activity_labels.get(activity_score, '?')} | **{activity_score}** |
| 3б. Макс. балл по матрице категорий | {top_freq_cat} | **{max_freq_score}** |
| 3в. Канал доставки | {channel_labels.get(channel_score, '?')} | **{channel_score}** |
| **Итого** | | **{total_score}** |
""")

        st.markdown("**Матрица частот по категориям:**")
        freq_rows = "\n".join(
            f"| {cat} | {FREQ_OPTIONS[cat][score]} | {score} |"
            for cat, score in freq_matrix.items()
        )
        st.markdown(f"""
| Категория | Частота | Балл |
|-----------|---------|------|
{freq_rows}
""")

        st.markdown("**Правило сегментации:**")
        st.markdown("""
| Сумма баллов | Сегмент | Описание |
|---|---|---|
| 0 – 2 | `new_web_1` | Пассивный подписчик — редкие покупки, e-mail |
| 3 – 5 | `new_web_2` | Регулярный покупатель — знает что хочет, ждёт скидку |
| 6 – 7 | `new_web_3` | Активный охотник — покупает часто, готов к app-миграции |
""")

        st.success(f"Ваш итог: **{total_score} баллов** → сегмент **{segment}** ({seg_name})")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Вернуться на главную", use_container_width=False):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ---------------------------------------------------------------------------
# Роутер
# ---------------------------------------------------------------------------

def main():
    init_state()
    inject_css()

    step = st.session_state.get("mvp_step", 0)

    if step == 0:
        render_landing()
    elif step == 1:
        render_auth_form()
    elif step == 2:
        render_auth_verify()
    elif step == 3:
        render_onboarding()
    elif step == 4:
        render_result()


main()
