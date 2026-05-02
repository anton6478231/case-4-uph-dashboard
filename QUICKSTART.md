# Unified Promo Hub — Калькулятор ФЭМ

**Автор:** Москалюк Антон, кейс 4, mini CEO 2026

## Запуск

```bash
cd "Москалюк_Антон_кейс_4_решение"
source venv/bin/activate
streamlit run app.py
```

Откроется браузер с адресом `http://localhost:8501`

## Структура приложения

### Страница 1 — Калькулятор ФЭМ
- Боковая панель: 18 конфигурируемых параметров в 6 блоках
- KPI-карточки: Выручка / Затраты / Чистый CF / Breakeven / MAU Hub / Redemptions
- График 1: Cash Flow (Revenue, Costs, CF, Cumulative CF)
- График 2: Структура выручки (CPA vs RevShare)
- График 3: Структура затрат (Fixed vs Variable)
- Детальная таблица по месяцам

### Страница 2 — Бизнес-логика
- Концепция трёхстороннего рынка
- Формулы выручки с пояснениями
- Логика роста MAU Hub (S-кривая по фазам)
- Структура затрат и бенчмарки
- Глоссарий терминов

## Параметры сайдбара

| Блок | Параметры |
|---|---|
| Горизонт | Месяцы расчёта (1–36), границы Phase 1 и Phase 2 |
| Аудитория | MAU T-Bank, % проникновения Phase 1/2/3 |
| Воронка | Offer Coverage, CTR, Redemption Rate |
| Монетизация | CPA_avg, AOV_avg, RevShare%, доля CPA, поправка на каннибализацию |
| Переменные затраты | VC/redemption отдельно для Phase 1/2/3 |
| Постоянные затраты | Fixed Cost/мес отдельно для Phase 1/2/3 |

## Структура кода

```
app.py                  # точка входа, st.navigation
pages/
  calculator.py         # UI калькулятора
  business_logic.py     # страница бизнес-логики
models/
  revenue.py            # MAU, воронка, CPA/RevShare
  costs.py              # Fixed + Variable по фазам
  cash_flow.py          # CF, cumulative, breakeven
visualization/
  charts.py             # 3 графика Plotly
  kpi_cards.py          # 6 KPI-метрик
utils/
  formatters.py         # форматирование чисел
config/
  defaults.json         # дефолтные параметры
```
