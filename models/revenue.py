"""
Модуль расчёта выручки Unified Promo Hub.

Stock-and-Flow модель роста аудитории (заменяет S-кривую):

  MAU_web (сайт, растёт на r_web %/мес) ──→ pool_web пополняется инкрементом ──→ убывает ──→ fresh_web[m] ──→ new_web[m]
                                                                                                                        │
                                                                             (1 - web_to_app) копится                   │ web_to_app % мигрирует
                                                                                                                        ↓
  MAU_app (приложение, растёт на r_app %/мес) ──→ pool_app пополняется инкрементом ──→ убывает ──→ fresh_app[m] ──→ graduating[m]
                                                                                                                          │
                                                                                                   ┌──────────────────────┘
                                                                                                   │ w_l% → seg_low
                                                                                                   │ w_m% → seg_mid
                                                                                                   └ w_a% → seg_act
                                                                                                 (+ ежемесячные переходы между сегментами)

Динамика MAU платформы:
  MAU_web[m] = MAU_web_0 × (1 + r_web)^(m−1),   r_web = (1 + web_annual_growth/100)^(1/12) − 1
  MAU_app[m] = MAU_app_0 × (1 + r_app)^(m−1),   r_app = (1 + app_annual_growth/100)^(1/12) − 1

  Инкремент MAU в месяц m = MAU[m] − MAU[m−1] — новые пользователи платформы,
  которые ещё не попали в Hub → пополняют pool_web / pool_app перед деплетированием.

Центральная формула выручки (4-сценарная модель партнёрских выплат):

    n_redemptions = MAU_hub × Coverage × CTR × RR × avg_rpu

    ВАЖНО о размерности:
        avg_rpu = взвешенное среднее purchases_low/mid/act (офферов на пользователя в месяц).
        Поэтому n_redemptions = число ПОКУПОК (purchase events), а не число уникальных
        пользователей, применивших оффер. Это эквивалентно формуле:
            N_unique_redeemers × Avg_offers_per_user_per_month
        что соответствует unit-economics.md §2.1 (Avg_offers_used/user/мес = 1.2–2.8).

    Каждый redemption классифицируется по сценарию с точки зрения партнёра:
        NEW      (w_new%)     — партнёр привлёк нового клиента          → price_new ₽
        LOYAL    (w_loyal%)   — лояльный клиент повышает вовлечённость   → price_loyal ₽
        RET      (w_ret%)     — реактивация ушедшего (lapsed 60+ дней)  → price_ret ₽
        AT_RISK  (w_at_risk%) — удержание клиента в зоне риска оттока   → price_at_risk ₽

    Revenue = n_redemptions
              × (w_new×price_new + w_loyal×price_loyal + w_ret×price_ret + w_at_risk×price_at_risk) / 100
              × incremental_adj

MAU_hub = new_app + seg_low + seg_mid + seg_act
           (только app-авторизованные; web-only — без атрибуции)

Когортная реферальная модель:
    p{phase}_k_factor = годовой K-фактор (total referrals per cohort member over 12 months).
    Ежемесячная ставка = k_factor / 12.
    База = cum_graduating — кумулятивная сумма всех graduating, начиная с месяца 1.

    referral_new[m] = cum_graduating[m−1] × (k_factor / 12)

    Логика: пользователь, пришедший в месяц t, генерирует k/12 рефералов
    в каждый последующий месяц (итого k рефералов за 12 месяцев).
    Все прошлые когорты суммируются → рост линейный при постоянной органике,
    не экспоненциальный.

    Кап по pool_app сохраняется: рефералы конвертируют пользователей из пула,
    а не создают их «из воздуха».

Отток с платформы (platform churn):
    Пользователи, которые полностью перестают использовать хаб (не просто снижают активность,
    а уходят насовсем). Без этого параметра MAU_hub — поглощающий автомат: пользователи только
    перемещаются LOW↔MID↔ACT, но никогда не уходят → нереалистичный рост к 12M+ за 24 мес.

    hub_monthly_churn_low_pct  — ежемесячный отток из LOW (default 15%).
        Пассивные пользователи: попробовали один раз, не вернулись. Банковские app-фичи:
        60-day retention ~37–45% для non-core features (AppsFlyer 2025).
    hub_monthly_churn_mid_pct  — ежемесячный отток из MID (default 8%).
        Ситуативные: уходят в период без релевантных офферов.
    hub_monthly_churn_act_pct  — ежемесячный отток из ACT (default 3%).
        Power-users: CLO auto-apply поддерживает статус без явных действий.

    Churned пользователи покидают модель полностью (не попадают обратно в пул —
    чтобы не создавать «зомби-пользователей»).

Гарантии (guardrails):
    - w_l + w_m + w_a == 100% (с допуском 0.1)
    - w_new + w_loyal + w_ret + w_at_risk == 100% (с допуском 0.1)
    - low_to_mid + low_to_act ≤ 100%
    - mid_to_low + mid_to_act ≤ 100%
    - act_to_low + act_to_mid ≤ 100%
    - pool_web, pool_app, seg_X ≥ 0 (принудительно через max(0, ...))
    - Деление на MAU_hub защищено if-guard → fallback = rpu_new_blended
    - new_app[m] = ТОЛЬКО fresh_app[m]; мигранты web→app — через graduating (no double-count)
    - pool_web[0] инициализируется только web-only посетителями (overlap вычтен)
"""
from typing import Dict, List


def _get_phase(month: int, phase1_end: int, phase2_end: int) -> int:
    """Возвращает номер фазы (1, 2 или 3) для заданного месяца."""
    if month <= phase1_end:
        return 1
    if month <= phase2_end:
        return 2
    return 3


def calculate_model(params: Dict, num_months: int) -> List[Dict]:
    """
    Stateful stock-and-flow расчёт по месяцам.

    Параметры (ключи params):
        Посетители: MAU_web, MAU_app, overlap_web_app_pct,
                    u_to_a_new_web, u_to_a_new_app, web_to_app
        Динамика MAU (опционально, default=0):
            mau_web_annual_growth_pct — годовой % роста MAU сайта
            mau_app_annual_growth_pct — годовой % роста MAU приложения
        Веса сегментов: w_l, w_m, w_a  (сумма = 100)
        Покупки по сегменту: purchases_low, purchases_mid, purchases_act
        Переходы: low_to_mid, low_to_act, mid_to_low, mid_to_act,
                  act_to_low, act_to_mid
        Воронка: p1/p2/p3_offer_coverage, p1/p2/p3_ctr_offer,
                 p1/p2/p3_redemption_rate
        Монетизация (4-сценарная):
            Веса сценариев (%): w_new, w_loyal, w_ret, w_at_risk (сумма = 100)
            Цены (₽/redemption): price_new, price_loyal, price_ret, price_at_risk
            Поправка: incremental_adj
        Реферальный рост (фазовые): p1_k_factor, p2_k_factor, p3_k_factor
        Фазы: phase1_end, phase2_end

    Возвращает список словарей (один на каждый месяц), содержащих:
        month, phase, pool_web, pool_app, new_web, new_app, graduating,
        seg_low, seg_mid, seg_act, mau_hub, mau_web_cur, mau_app_cur,
        avg_rpu, n_redemptions,
        revenue_new, revenue_loyal, revenue_ret, revenue_at_risk, total_revenue
    """
    # ── Параметры посетителей ─────────────────────────────────────────────────
    MAU_web_0        = float(params["MAU_web"])
    MAU_app_0        = float(params["MAU_app"])
    overlap_pct      = float(params["overlap_web_app_pct"])
    u_web            = float(params["u_to_a_new_web"]) / 100.0
    u_app            = float(params["u_to_a_new_app"]) / 100.0
    w2a              = float(params["web_to_app"]) / 100.0

    # ── Динамика MAU платформы (помесячный рост) ──────────────────────────────
    # Годовой рост → месячный: r = (1 + annual/100)^(1/12) − 1
    # Если параметр не задан — нет роста (0%).
    web_annual_growth = float(params.get("mau_web_annual_growth_pct", 0.0))
    app_annual_growth = float(params.get("mau_app_annual_growth_pct", 0.0))
    r_web = (1.0 + web_annual_growth / 100.0) ** (1.0 / 12.0) - 1.0
    r_app = (1.0 + app_annual_growth / 100.0) ** (1.0 / 12.0) - 1.0

    # ── Веса и покупки по сегментам ───────────────────────────────────────────
    w_l = float(params["w_l"])
    w_m = float(params["w_m"])
    w_a = float(params["w_a"])
    if abs(w_l + w_m + w_a - 100.0) > 0.1:
        raise ValueError(
            f"w_l({w_l}) + w_m({w_m}) + w_a({w_a}) = {w_l+w_m+w_a} ≠ 100. "
            "Сумма весов сегментов должна равняться 100%."
        )

    purch_low  = float(params["purchases_low"])
    purch_mid  = float(params["purchases_mid"])
    purch_act  = float(params["purchases_act"])

    rpu_new_blended = (w_l * purch_low + w_m * purch_mid + w_a * purch_act) / 100.0

    # ── Переходы между сегментами ─────────────────────────────────────────────
    low_to_mid = float(params["low_to_mid"]) / 100.0
    low_to_act = float(params["low_to_act"]) / 100.0
    mid_to_low = float(params["mid_to_low"]) / 100.0
    mid_to_act = float(params["mid_to_act"]) / 100.0
    act_to_low = float(params["act_to_low"]) / 100.0
    act_to_mid = float(params["act_to_mid"]) / 100.0

    # ── Platform churn (полный выход с платформы, не перераспределение) ────────
    hub_churn_low = float(params.get("hub_monthly_churn_low_pct", 15.0)) / 100.0
    hub_churn_mid = float(params.get("hub_monthly_churn_mid_pct", 8.0))  / 100.0
    hub_churn_act = float(params.get("hub_monthly_churn_act_pct", 3.0))  / 100.0

    if low_to_mid + low_to_act + hub_churn_low > 1.0 + 1e-9:
        raise ValueError(
            f"low_to_mid({low_to_mid*100}%) + low_to_act({low_to_act*100}%) "
            f"+ hub_churn_low({hub_churn_low*100}%) "
            f"= {(low_to_mid+low_to_act+hub_churn_low)*100:.1f}% > 100%. Суммарный outflow из LOW превышает 100%."
        )
    if mid_to_low + mid_to_act + hub_churn_mid > 1.0 + 1e-9:
        raise ValueError(
            f"mid_to_low({mid_to_low*100}%) + mid_to_act({mid_to_act*100}%) "
            f"+ hub_churn_mid({hub_churn_mid*100}%) "
            f"= {(mid_to_low+mid_to_act+hub_churn_mid)*100:.1f}% > 100%. Суммарный outflow из MID превышает 100%."
        )
    if act_to_low + act_to_mid + hub_churn_act > 1.0 + 1e-9:
        raise ValueError(
            f"act_to_low({act_to_low*100}%) + act_to_mid({act_to_mid*100}%) "
            f"+ hub_churn_act({hub_churn_act*100}%) "
            f"= {(act_to_low+act_to_mid+hub_churn_act)*100:.1f}% > 100%. Суммарный outflow из ACT превышает 100%."
        )

    # ── Воронка и монетизация (4-сценарная) ──────────────────────────────────
    phase1_end = int(params["phase1_end"])
    phase2_end = int(params["phase2_end"])

    w_new      = float(params["w_new"])
    w_loyal    = float(params["w_loyal"])
    w_ret      = float(params["w_ret"])
    w_at_risk  = float(params["w_at_risk"])
    if abs(w_new + w_loyal + w_ret + w_at_risk - 100.0) > 0.1:
        raise ValueError(
            f"w_new({w_new}) + w_loyal({w_loyal}) + w_ret({w_ret}) + w_at_risk({w_at_risk}) "
            f"= {w_new+w_loyal+w_ret+w_at_risk} ≠ 100. "
            "Сумма весов сценариев монетизации должна равняться 100%."
        )

    price_new      = float(params["price_new"])
    price_loyal    = float(params["price_loyal"])
    price_ret      = float(params["price_ret"])
    price_at_risk  = float(params["price_at_risk"])
    incr_adj       = float(params["incremental_adj"])
    # K-фактор задаётся отдельно для каждой фазы — читается внутри loop через _get_phase


    # ── Инициализация (m = 0) ─────────────────────────────────────────────────
    # pool_web: только web-only посетители (overlap-пользователи исключены — они app-only)
    pool_web = MAU_web_0 * (1.0 - overlap_pct / 100.0)
    pool_app = MAU_app_0

    # Текущие MAU платформы (стартовые значения = базовые)
    mau_web_cur = MAU_web_0
    mau_app_cur = MAU_app_0

    new_web  = 0.0
    new_app  = 0.0
    seg_low  = 0.0
    seg_mid  = 0.0
    seg_act  = 0.0

    # Когортная реферальная база: кумулятивная сумма всех graduating (месяц 1..m−1)
    cum_graduating = 0.0

    results = []

    for m in range(1, num_months + 1):

        # ── 0. Фаза и фазовые параметры (определяем первыми — нужны в шаге 4) ─
        phase = _get_phase(m, phase1_end, phase2_end)
        p = f"p{phase}"
        # K-фактор растёт по фазам: P1 (нет петли) → P2 (шеринг web+бонус) → P3 (зрелая петля)
        k_factor = float(params.get(f"{p}_k_factor", 0.0))

        # ── 0а. Рост MAU платформы: новые пользователи платформы входят в pool ─
        # MAU_web[m] = MAU_web_0 × (1 + r_web)^(m−1); инкремент = MAU_web[m] − MAU_web[m−1]
        # Инкремент = новые пользователи платформы, которые ещё не конвертировались в Hub-пользователей.
        # Они пополняют pool перед деплетированием этого месяца.
        mau_web_new = MAU_web_0 * (1.0 + r_web) ** (m - 1)
        mau_app_new = MAU_app_0 * (1.0 + r_app) ** (m - 1)

        increment_web = max(0.0, mau_web_new - mau_web_cur)
        increment_app = max(0.0, mau_app_new - mau_app_cur)

        # Пополнение пулов: только web-only (overlap вычтен) + app-прирост
        pool_web = pool_web + increment_web * (1.0 - overlap_pct / 100.0)
        pool_app = pool_app + increment_app

        mau_web_cur = mau_web_new
        mau_app_cur = mau_app_new

        # ── 1. Деплетирование пулов ───────────────────────────────────────────
        fresh_web = pool_web * u_web
        fresh_app = pool_app * u_app

        pool_web = max(0.0, pool_web * (1.0 - u_web))
        pool_app = max(0.0, pool_app * (1.0 - u_app))

        # ── 2. Буфер NEW-web (stock: накопленные web-new, ещё не мигрировавшие)
        new_web_next = fresh_web + new_web * (1.0 - w2a)

        # ── 3. NEW-app (ТОЛЬКО fresh из пула приложения; мигранты → graduating)
        new_app_next = fresh_app

        # ── 4. Graduating: органика (app-new + web-мигранты) + рефералы
        #
        # Органика — пользователи из пулов (SEO / paid / прямой трафик):
        #   new_app   — fresh из пула приложения (прошлый месяц)
        #   new_web × w2a — накопленные web-new, мигрировавшие в app этом месяце
        #
        # Рефералы — КОГОРТНАЯ МОДЕЛЬ (k_factor = ГОДОВОЙ K):
        #   Каждый пользователь, пришедший в месяц t, генерирует k/12 рефералов
        #   в каждый последующий месяц. Итого k рефералов за 12 месяцев на человека.
        #
        #   referral_new[m] = cum_graduating[m−1] × (k_factor / 12)
        #
        #   где cum_graduating = кумулятивная сумма graduating из ВСЕХ прошлых месяцев.
        #   Это предотвращает экспоненциальный рост: при постоянной органике G рост
        #   рефералов линейный (~k/12 × G × m), а не множительный (1 + k)^m.
        #
        #   k_factor по фазам (ГОДОВОЙ K, не месячный):
        #     P1 (мес. 1–3):   k=0.03 → 0.0025/мес — органический «сарафан», нет фичи
        #     P2 (мес. 4–9):   k=0.10 → 0.0083/мес — запущен шеринг web+бонус
        #     P3 (мес. 10–18): k=0.30 → 0.025/мес  — зрелая петля + геймификация
        #
        #   Кап по pool_app сохраняется: рефералы конвертируют из пула, не создают новых.
        #
        # ВАЖНО: мигранты НЕ включаются в new_app_next → нет двойного счёта
        referral_raw  = cum_graduating * (k_factor / 12.0)
        referral_new  = min(pool_app, referral_raw)          # кап: не больше остатка пула
        pool_app      = max(0.0, pool_app - referral_new)    # рефералы истощают пул
        graduating    = new_app + new_web * w2a + referral_new

        new_to_low = (w_l / 100.0) * graduating
        new_to_mid = (w_m / 100.0) * graduating
        new_to_act = (w_a / 100.0) * graduating

        # ── 5. Переходы между сегментами (от прошлого месяца к текущему) ─────
        l2m = seg_low * low_to_mid
        l2a = seg_low * low_to_act
        m2l = seg_mid * mid_to_low
        m2a = seg_mid * mid_to_act
        a2l = seg_act * act_to_low
        a2m = seg_act * act_to_mid

        # ── 6. Обновление сегментов (с платформенным оттоком) ────────────────
        # hub_churn_X = доля пользователей, покидающих хаб насовсем (не перераспределяются).
        # Churned пользователи не возвращаются в пул — они уходят из модели полностью.
        seg_low_next = max(0.0, (
            new_to_low
            + seg_low * (1.0 - low_to_mid - low_to_act - hub_churn_low)
            + m2l
            + a2l
        ))
        seg_mid_next = max(0.0, (
            new_to_mid
            + seg_mid * (1.0 - mid_to_low - mid_to_act - hub_churn_mid)
            + l2m
            + a2m
        ))
        seg_act_next = max(0.0, (
            new_to_act
            + seg_act * (1.0 - act_to_low - act_to_mid - hub_churn_act)
            + l2a
            + m2a
        ))

        # ── 7. MAU_hub (только авторизованные app-пользователи) ──────────────
        mau_hub = new_app_next + seg_low_next + seg_mid_next + seg_act_next

        # ── 8. avg_rpu (динамический, на основе состава сегментов) ───────────
        if mau_hub > 0:
            avg_rpu = (
                new_app_next  * rpu_new_blended
                + seg_low_next  * purch_low
                + seg_mid_next  * purch_mid
                + seg_act_next  * purch_act
            ) / mau_hub
        else:
            avg_rpu = rpu_new_blended

        # ── 9. Воронка и выручка (4-сценарная модель) ────────────────────────
        # phase и p уже определены в шаге 0 (начало итерации)
        offer_coverage  = float(params[f"{p}_offer_coverage"]) / 100.0
        ctr_offer       = float(params[f"{p}_ctr_offer"])      / 100.0
        redemption_rate = float(params[f"{p}_redemption_rate"]) / 100.0

        n_redemptions = mau_hub * offer_coverage * ctr_offer * redemption_rate * avg_rpu

        # incremental_adj = 0.87: 13% redemptions каннибализируют продажи, которые
        # произошли бы без промокода → партнёр платит только за доказанные инкрементальные
        # переходы (аналог Ibotta ROAS / Cardlytics incrementality guarantee).
        #
        # Множитель перенесён внутрь по дистрибутивному тождеству ((a+b)×k = ak+bk),
        # чтобы stored-значения компонентов уже содержали поправку и сумма столбцов
        # на графике 2 точно совпадала с KPI-карточкой total_revenue.
        revenue_new      = n_redemptions * (w_new     / 100.0) * price_new     * incr_adj
        revenue_loyal    = n_redemptions * (w_loyal   / 100.0) * price_loyal   * incr_adj
        revenue_ret      = n_redemptions * (w_ret     / 100.0) * price_ret     * incr_adj
        revenue_at_risk  = n_redemptions * (w_at_risk / 100.0) * price_at_risk * incr_adj
        total_rev        = revenue_new + revenue_loyal + revenue_ret + revenue_at_risk
        # sum(компонентов) == total_revenue ✓  (все значения хранятся с ×incr_adj)

        # Обновляем когортную базу: добавляем graduating этого месяца.
        # Делается ПОСЛЕ вычисления referral_new, чтобы этот месяц вошёл в базу
        # только начиная со следующего месяца (без двойного счёта в текущем).
        cum_graduating += graduating

        results.append({
            "month":            m,
            "phase":            phase,
            "pool_web":         pool_web,
            "pool_app":         pool_app,
            "new_web":          new_web_next,
            "new_app":          new_app_next,
            "graduating":       graduating,
            "cum_graduating":   cum_graduating,
            "seg_low":          seg_low_next,
            "seg_mid":          seg_mid_next,
            "seg_act":          seg_act_next,
            "mau_hub":          mau_hub,
            "mau_web_cur":      mau_web_cur,
            "mau_app_cur":      mau_app_cur,
            "avg_rpu":          avg_rpu,
            "n_redemptions":    n_redemptions,
            "revenue_new":      revenue_new,
            "revenue_loyal":    revenue_loyal,
            "revenue_ret":      revenue_ret,
            "revenue_at_risk":  revenue_at_risk,
            "total_revenue":    total_rev,
        })

        # Сохраняем state для следующей итерации
        new_web  = new_web_next
        new_app  = new_app_next
        seg_low  = seg_low_next
        seg_mid  = seg_mid_next
        seg_act  = seg_act_next

    return results


def calculate_revenue_for_months(params: Dict, num_months: int) -> List[Dict]:
    """
    Обёртка над calculate_model() для совместимости с calculate_costs_for_months()
    и calculate_cash_flow_for_months().

    Возвращаемые словари содержат все поля stock-and-flow модели плюс
    поле 'total_revenue', ожидаемое cash_flow модулем.
    """
    return calculate_model(params, num_months)
