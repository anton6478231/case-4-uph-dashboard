# Unified Promo Hub — Калькулятор ФЭМ

**Автор:** Москалюк Антон, кейс 4, mini CEO 2026

## Запуск

```bash
cd "Москалюк_Антон_кейс_4_решение"
source venv/bin/activate
streamlit run app.py
```

Откроется браузер с адресом `http://localhost:8501`

---

## Концепция модели

Калькулятор реализует **stock-and-flow модель роста** аудитории Unified Promo Hub — в отличие
от простой S-кривой, здесь явно отслеживается каждая когорта пользователей:

```
pool_web (сайт, убывает) ──→ fresh_web ──→ new_web буфер ──┐
                                                             │ web_to_app%
pool_app (app, убывает)  ──→ fresh_app ──→ new_app ──────────→ graduating
                                                             │
                                        graduating ──→ seg_low / seg_mid / seg_act
                                                    (+ ежемесячные переходы LOW↔MID↔ACT)

MAU_hub = new_app + seg_low + seg_mid + seg_act
```

Выручка считается по **4-сценарной модели** партнёрских выплат (lifecycle-стадия клиента):
- **NEW** (25%) → 650 ₽/redemption — Acquisition нового клиента партнёра
- **LOYAL** (40%) → 170 ₽/redemption — Expansion/RevShare-эквивалент
- **RET** (20%) → 420 ₽/redemption — Reactivation (lapsed 60+ дней)
- **AT_RISK** (15%) → 290 ₽/redemption — Retention/Anti-Churn

---

## Структура приложения

### Страница 1 — Калькулятор ФЭМ

**Боковая панель: 9 блоков параметров**

| Блок | Параметры |
|---|---|
| Горизонт | Месяцы расчёта, границы Phase 1 и Phase 2 |
| Посетители | MAU сайта и приложения, % перекрытия |
| Конверсии | u_to_a_new_web, u_to_a_new_app, web_to_app |
| Сегменты NEW | Доли LOW/MID/ACT, покупки/мес по сегменту |
| Переходы | Матрица 6 переходов между LOW/MID/ACT |
| Воронка | Offer Coverage, CTR, Redemption Rate (3 фазы) |
| Монетизация | Веса и цены 4 сценариев, Incremental_adj |
| Переменные затраты | VC/redemption для Phase 1/2/3 |
| Постоянные затраты | Fixed Cost/мес: команда, инфра, маркетинг, реферал |

**11 KPI-карточек:**
Суммарная выручка / Суммарные затраты / Чистый CF / Breakeven CF / Breakeven NPV /
MAU Hub (финал) / Redemptions (сумма) / avg_rpu (финал) / Доля ACT (%) / Остаток pool_web / Остаток pool_app

**4 графика Plotly:**
1. Cash Flow — Revenue / Costs / CF / Cumulative CF / Cumulative NPV + breakeven-маркеры
2. Структура выручки — stacked bar по 4 сценариям (NEW / LOYAL / RET / AT_RISK)
3. Структура затрат — Fixed vs Variable по фазам
4. Динамика сегментов — stacked area new_app / seg_low / seg_mid / seg_act

### Страница 2 — Бизнес-логика

- Концепция трёхстороннего рынка
- Формула выручки + мэппинг 4 сценариев на архетипы кампаний
- Логика роста MAU Hub (stock-and-flow) + рекуррентные формулы
- Структура затрат (инкрементальные FC и VC) с разъяснением vs full-cost
- Бенчмарки параметров с источниками + CLO-Premium объяснение для Phase 3
- Глоссарий (MAU Hub, CLO, NBP, avg_rpu, graduating и др.)

### Страница 3 — MVP Онбординг

- Прототип web-флоу: лендинг → авторизация → онбординг → персональные офферы
- Сегментация по activity score (new_web_1 / new_web_2 / new_web_3)
- Логика pick_promos: relevance, first_order filter, no category-mixing

---

## Структура кода

```
app.py                  # точка входа, st.navigation (3 страницы)
pages/
  calculator.py         # UI калькулятора (сайдбар + KPI + 4 графика)
  business_logic.py     # страница бизнес-логики (концепция, формулы, глоссарий)
  mvp_onboarding.py     # прототип web-флоу онбординга
models/
  revenue.py            # stock-and-flow + 4-сценарная монетизация
  costs.py              # Fixed + Variable затраты по фазам
  cash_flow.py          # CF, cumulative CF, NPV, breakeven
visualization/
  charts.py             # 4 графика Plotly
  kpi_cards.py          # 11 KPI-метрик
utils/
  formatters.py         # форматирование чисел (млрд/млн/тыс)
config/
  defaults.json         # дефолтные параметры (источник истины для модели)
```

---

## Ключевые допущения defaults.json

| Параметр | Значение | Обоснование |
|---|---|---|
| MAU_app | 34 000 000 | FY2025 IR T-Technologies |
| MAU_web | 300 000 | promokod.tbank.ru оценочно |
| u_to_a_new_app | 1.5% | 1.5% × 34M = 510k fresh/мес → Phase 1 MAU_hub ~1.0–1.5M |
| web_to_app | 28% | скорость миграции буфера new_web в app (не full-funnel 5%) |
| FC Phase 1 | 6M ₽/мес | инкрементальные затраты T-Bank (full-cost ~17M; см. unit-economics.md) |
| VC Phase 1 | 22 ₽ | прямые тех. затраты (full-cost ~36 ₽ включая antifraud+support) |
| Phase 3 воронка | 92%/22%/36% | CLO-Premium при 500+ партнёрах; Cardlytics CLO RR 35–55% |
| Incremental_adj | 0.87 | 13% каннибализация с кэшбэком T-Bank |
| Discount rate | 20%/год | стандарт для РФ-проектов |
