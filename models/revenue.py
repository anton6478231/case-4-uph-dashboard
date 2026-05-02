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

Центральная формула выручки:
    N_redemptions = MAU_hub × Coverage × CTR × RR × avg_rpu
    Revenue_CPA   = N_redemptions × share_CPA × CPA_avg
    Revenue_RS    = N_redemptions × (1 − share_CPA) × AOV_avg × RevShare_avg
    Revenue_gross = (Revenue_CPA + Revenue_RS) × incremental_adj

MAU_hub = new_app + seg_low + seg_mid + seg_act
           (только app-авторизованные; web-only — без атрибуции CPA/RevShare)

Гарантии (guardrails):
    - w_l + w_m + w_a == 100% (с допуском 0.1)
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
        Монетизация: cpa_avg, aov_avg, revshare_avg, share_cpa, incremental_adj
        Фазы: phase1_end, phase2_end

    Возвращает список словарей (один на каждый месяц), содержащих:
        month, phase, pool_web, pool_app, new_web, new_app, graduating,
        seg_low, seg_mid, seg_act, mau_hub, avg_rpu, n_redemptions,
        revenue_cpa, revenue_rs, total_revenue
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

    # ── Воронка и монетизация ─────────────────────────────────────────────────
    phase1_end = int(params["phase1_end"])
    phase2_end = int(params["phase2_end"])

    cpa_avg       = float(params["cpa_avg"])
    aov_avg       = float(params["aov_avg"])
    revshare_avg  = float(params["revshare_avg"]) / 100.0
    share_cpa     = float(params["share_cpa"])    / 100.0
    incr_adj      = float(params["incremental_adj"])

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

        # ── 9. Воронка и выручка ──────────────────────────────────────────────
        phase = _get_phase(m, phase1_end, phase2_end)
        p = f"p{phase}"
        offer_coverage  = float(params[f"{p}_offer_coverage"]) / 100.0
        ctr_offer       = float(params[f"{p}_ctr_offer"])      / 100.0
        redemption_rate = float(params[f"{p}_redemption_rate"]) / 100.0

        n_redemptions = mau_hub * offer_coverage * ctr_offer * redemption_rate * avg_rpu

        revenue_cpa = n_redemptions * share_cpa * cpa_avg
        revenue_rs  = n_redemptions * (1.0 - share_cpa) * aov_avg * revshare_avg
        total_rev   = (revenue_cpa + revenue_rs) * incr_adj

        results.append({
            "month":        m,
            "phase":        phase,
            "pool_web":     pool_web,
            "pool_app":     pool_app,
            "new_web":      new_web_next,
            "new_app":      new_app_next,
            "graduating":   graduating,
            "seg_low":      seg_low_next,
            "seg_mid":      seg_mid_next,
            "seg_act":      seg_act_next,
            "mau_hub":      mau_hub,
            "avg_rpu":      avg_rpu,
            "n_redemptions": n_redemptions,
            "revenue_cpa":  revenue_cpa,
            "revenue_rs":   revenue_rs,
            "total_revenue": total_rev,
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
