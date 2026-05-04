"""
Unified Promo Hub — Финансово-экономическая модель
Москалюк Антон, кейс 4, mini CEO 2026

Запуск:
    cd "Москалюк_Антон_кейс_4_решение"
    streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="UPH FEM — Unified Promo Hub",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

calculator_page = st.Page(
    "pages/calculator.py",
    title="Калькулятор ФЭМ",
    icon="📊",
    default=True,
)

business_logic_page = st.Page(
    "pages/business_logic.py",
    title="Бизнес-логика",
    icon="📖",
)

mvp_onboarding_page = st.Page(
    "pages/mvp_onboarding.py",
    title="MVP: Онбординг",
    icon="🛍️",
)

case_answers_page = st.Page(
    "pages/case_answers.py",
    title="Ответы на задачи кейса",
    icon="📋",
)

business_case_page = st.Page(
    "pages/business_case_page.py",
    title="Условие кейса",
    icon="📄",
)

pg = st.navigation([
    calculator_page,
    business_logic_page,
    mvp_onboarding_page,
    case_answers_page,
    business_case_page,
])
pg.run()
