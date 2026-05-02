"""
Модуль расчёта выручки Unified Promo Hub.

Stock-and-Flow модель роста аудитории (заменяет S-кривую):

  MAU_web (сайт, константа) ──→ pool_web убывает ──→ fresh_web[m] ──→ new_web[m]
                                                                           │
                                                  (1 - web_to_app) копится │ web_to_app % мигрирует
                                                                           ↓
  MAU_app (приложение, константа) ──→ pool_app убывает ──→ fresh_app[m] ──→ graduating[m]
                                                                                 │
                                                              ┌──────────────────┘
                                                              │ w_l% → seg_low
                                                              │ w_m% → seg_mid
                                                              └ w_a% → seg_act
                                                            (+ ежемесячные переходы между сегментами)

Центральная формула выручки (4-сценарная модель партнёрских выплат):
    N_redemptions = MAU_hub × Coverage × CTR × RR × avg_rpu

    Каждый redemption классифицируется по сценарию с точки зрения партнёра:
        NEW      (w_new%)     — партнёр привлёк нового клиента          → price_new ₽
        LOYAL    (w_loyal%)   — лояльный клиент повышает вовлечённость   → price_loyal ₽
        RET      (w_ret%)     — реактивация ушедшего (lapsed 60+ дней)  → price_ret ₽
        AT_RISK  (w_at_risk%) — удержание клиента в зоне риска оттока   → price_at_risk ₽

    Revenue = N_redemptions
              × (w_new×price_new + w_loyal×price_loyal + w_ret×price_ret + w_at_risk×price_at_risk) / 100
              × incremental_adj

MAU_hub = new_app + seg_low + seg_mid + seg_act
           (только app-авторизованные; web-only — без атрибуции)

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
        Фазы: phase1_end, phase2_end

    Возвращает список словарей (один на каждый месяц), содержащих:
        month, phase, pool_web, pool_app, new_web, new_app, graduating,
        seg_low, seg_mid, seg_act, mau_hub, avg_rpu, n_redemptions,
        revenue_new, revenue_loyal, revenue_ret, revenue_at_risk, total_revenue
    """
    # ── Параметры посетителей ─────────────────────────────────────────────────
    MAU_web          = float(params["MAU_web"])
    MAU_app          = float(params["MAU_app"])
    overlap_pct      = float(params["overlap_web_app_pct"])
    u_web            = float(params["u_to_a_new_web"]) / 100.0
    u_app            = float(params["u_to_a_new_app"]) / 100.0
    w2a              = float(params["web_to_app"]) / 100.0

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

    if low_to_mid + low_to_act > 1.0 + 1e-9:
        raise ValueError(
            f"low_to_mid({low_to_mid*100}%) + low_to_act({low_to_act*100}%) "
            f"= {(low_to_mid+low_to_act)*100:.1f}% > 100%. Outflow из LOW не может превышать 100%."
        )
    if mid_to_low + mid_to_act > 1.0 + 1e-9:
        raise ValueError(
            f"mid_to_low({mid_to_low*100}%) + mid_to_act({mid_to_act*100}%) "
            f"= {(mid_to_low+mid_to_act)*100:.1f}% > 100%. Outflow из MID не может превышать 100%."
        )
    if act_to_low + act_to_mid > 1.0 + 1e-9:
        raise ValueError(
            f"act_to_low({act_to_low*100}%) + act_to_mid({act_to_mid*100}%) "
            f"= {(act_to_low+act_to_mid)*100:.1f}% > 100%. Outflow из ACT не может превышать 100%."
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


    # ── Инициализация (m = 0) ─────────────────────────────────────────────────
    # pool_web: только web-only посетители (overlap-пользователи исключены — они app-only)
    pool_web = MAU_web * (1.0 - overlap_pct / 100.0)
    pool_app = MAU_app

    new_web  = 0.0
    new_app  = 0.0
    seg_low  = 0.0
    seg_mid  = 0.0
    seg_act  = 0.0

    results = []

    for m in range(1, num_months + 1):

        # ── 1. Деплетирование пулов ───────────────────────────────────────────
        fresh_web = pool_web * u_web
        fresh_app = pool_app * u_app

        pool_web = max(0.0, pool_web * (1.0 - u_web))
        pool_app = max(0.0, pool_app * (1.0 - u_app))

        # ── 2. Буфер NEW-web (stock: накопленные web-new, ещё не мигрировавшие)
        new_web_next = fresh_web + new_web * (1.0 - w2a)

        # ── 3. NEW-app (ТОЛЬКО fresh из пула приложения; мигранты → graduating)
        new_app_next = fresh_app

        # ── 4. Graduating: app-new прошлого месяца + web-new прошлого месяца ×
        #        web_to_app (мигранты, переходящие в app именно в этом месяце)
        #    ВАЖНО: мигранты НЕ включаются в new_app_next → нет двойного счёта
        graduating = new_app + new_web * w2a

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

        # ── 6. Обновление сегментов ───────────────────────────────────────────
        seg_low_next = max(0.0, (
            new_to_low
            + seg_low * (1.0 - low_to_mid - low_to_act)
            + m2l
            + a2l
        ))
        seg_mid_next = max(0.0, (
            new_to_mid
            + seg_mid * (1.0 - mid_to_low - mid_to_act)
            + l2m
            + a2m
        ))
        seg_act_next = max(0.0, (
            new_to_act
            + seg_act * (1.0 - act_to_low - act_to_mid)
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
        phase = _get_phase(m, phase1_end, phase2_end)
        p = f"p{phase}"
        offer_coverage  = float(params[f"{p}_offer_coverage"]) / 100.0
        ctr_offer       = float(params[f"{p}_ctr_offer"])      / 100.0
        redemption_rate = float(params[f"{p}_redemption_rate"]) / 100.0

        n_redemptions = mau_hub * offer_coverage * ctr_offer * redemption_rate * avg_rpu

        revenue_new      = n_redemptions * (w_new     / 100.0) * price_new
        revenue_loyal    = n_redemptions * (w_loyal   / 100.0) * price_loyal
        revenue_ret      = n_redemptions * (w_ret     / 100.0) * price_ret
        revenue_at_risk  = n_redemptions * (w_at_risk / 100.0) * price_at_risk
        total_rev        = (revenue_new + revenue_loyal + revenue_ret + revenue_at_risk) * incr_adj

        results.append({
            "month":            m,
            "phase":            phase,
            "pool_web":         pool_web,
            "pool_app":         pool_app,
            "new_web":          new_web_next,
            "new_app":          new_app_next,
            "graduating":       graduating,
            "seg_low":          seg_low_next,
            "seg_mid":          seg_mid_next,
            "seg_act":          seg_act_next,
            "mau_hub":          mau_hub,
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
