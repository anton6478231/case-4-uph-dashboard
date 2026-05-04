"""
Графики для калькулятора Unified Promo Hub.

График 1 — Cash Flow: Revenue / Total Costs / CF / Cumulative CF по месяцам.
           Вертикальные линии на границах Phase 1→2→3.

График 2 — Структура выручки: 4 сценария партнёрских выплат (stacked bar):
           NEW / LOYAL / RET / AT_RISK.

График 3 — Структура затрат: Fixed Costs vs Variable Costs (stacked bar).

График 4 — Сегментная динамика: new_app / seg_low / seg_mid / seg_act (stacked area).
"""
from typing import List, Dict, Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────

def _phase_vlines(fig: go.Figure, phase1_end: int, phase2_end: int, num_months: int):
    """Добавляет вертикальные пунктирные линии на границах Phase 1→2 и Phase 2→3."""
    transitions = []
    if phase1_end < num_months:
        transitions.append((phase1_end + 0.5, "Phase 1 → 2", "#F59E0B"))
    if phase2_end < num_months:
        transitions.append((phase2_end + 0.5, "Phase 2 → 3", "#8B5CF6"))

    for x_pos, label, color in transitions:
        fig.add_vline(
            x=x_pos,
            line_dash="dash",
            line_color=color,
            line_width=1.5,
            opacity=0.7,
            annotation_text=label,
            annotation_position="top right",
            annotation_font_color=color,
            annotation_font_size=11,
        )


# ──────────────────────────────────────────────────────────────────────────────
# График 1 — Cash Flow
# ──────────────────────────────────────────────────────────────────────────────

def create_cash_flow_chart(
    cf_results: List[Dict],
    phase1_end: int,
    phase2_end: int,
    RnD_cf_results: Optional[List[Dict]] = None,
) -> go.Figure:
    """
    Линейный график Cash Flow и NPV по месяцам.

    Серии (рыночная фаза):
        Revenue         — зелёная (сплошная)
        Total Costs     — красная (сплошная)
        Cash Flow мес.  — синяя (сплошная)
        Cumulative CF   — фиолетовый пунктир
        Cumulative NPV  — оранжевый пунктир

    При RnD_cf_results:
        — RnD месяцы показываются с метками "RnD-N" на оси X
        — Серая затенённая зона для RnD периода
        — Вертикальная линия "RnD → Рынок" на границе
        — CF/Cumulative RnD — серые линии, препендированные перед рыночными
    """
    # ── Подготовка осей X ────────────────────────────────────────────────────
    rnd_months = len(RnD_cf_results) if RnD_cf_results else 0

    # Метки оси: "RnD-2", "RnD-1" ... "М1", "М2", ...
    # Для Plotly используем числовую ось с ticktext
    if RnD_cf_results:
        rnd_x      = list(range(-rnd_months + 1, 1))   # [-1, 0] при rnd=2, [-2,-1,0] при rnd=3
        rnd_labels = [f"RnD-{rnd_months - i}" for i in range(rnd_months)]
        # RnD-2 → позиция (-1), RnD-1 → позиция 0
        rnd_x = list(range(-(rnd_months - 1), 1))       # 0..rnd_months-1 → -(rnd-1)..0
    else:
        rnd_x = []
        rnd_labels = []

    market_x      = [r["month"] for r in cf_results]   # 1, 2, ... N
    market_labels = [f"М{m}" for m in market_x]

    all_x      = rnd_x + market_x
    all_labels = rnd_labels + market_labels

    # ── Данные рыночной фазы ─────────────────────────────────────────────────
    revenue     = [r["revenue"] for r in cf_results]
    total_costs = [r["total_costs"] for r in cf_results]
    cash_flow   = [r["cash_flow"] for r in cf_results]
    cumulative  = [r["cumulative_cash_flow"] for r in cf_results]
    cum_npv     = [r.get("cumulative_npv", 0) for r in cf_results]

    # ── Данные RnD фазы ──────────────────────────────────────────────────────
    if RnD_cf_results:
        rnd_rev      = [r["revenue"] for r in RnD_cf_results]
        rnd_costs    = [r["total_costs"] for r in RnD_cf_results]
        rnd_cf_vals  = [r["cash_flow"] for r in RnD_cf_results]
        rnd_cum_cf   = [r["cumulative_cash_flow"] for r in RnD_cf_results]
        rnd_cum_npv  = [r.get("cumulative_npv", 0) for r in RnD_cf_results]

        # Рыночная кумуляция должна продолжаться от конца RnD, а не стартовать с нуля.
        # cf_results хранит market-only cumulative (с нуля); добавляем накопленный RnD-дефицит.
        rnd_cf_offset  = rnd_cum_cf[-1]  if rnd_cum_cf  else 0.0
        rnd_npv_offset = rnd_cum_npv[-1] if rnd_cum_npv else 0.0
        cumulative = [v + rnd_cf_offset  for v in cumulative]
        cum_npv    = [v + rnd_npv_offset for v in cum_npv]
    else:
        rnd_rev = rnd_costs = rnd_cf_vals = rnd_cum_cf = rnd_cum_npv = []

    fig = go.Figure()

    # ── RnD зона: серый фон ───────────────────────────────────────────────────
    if RnD_cf_results and rnd_x:
        fig.add_vrect(
            x0=rnd_x[0] - 0.5,
            x1=0.5,
            fillcolor="rgba(156, 163, 175, 0.15)",
            layer="below",
            line_width=0,
            annotation_text="RnD фаза",
            annotation_position="top left",
            annotation_font_color="#6B7280",
            annotation_font_size=11,
        )
        # Граница RnD → Рынок
        fig.add_vline(
            x=0.5,
            line_dash="solid",
            line_color="#6B7280",
            line_width=1.5,
            opacity=0.8,
            annotation_text="RnD → Рынок",
            annotation_position="top right",
            annotation_font_color="#6B7280",
            annotation_font_size=11,
        )

    # ── RnD линии (серые) ─────────────────────────────────────────────────────
    if RnD_cf_results:
        fig.add_trace(go.Scatter(
            x=rnd_x, y=rnd_costs,
            mode="lines+markers",
            name="Затраты RnD",
            line=dict(color="#9CA3AF", width=2, dash="dash"),
            marker=dict(size=7),
            hovertemplate="%{x}: %{y:,.0f} ₽<extra>Затраты RnD</extra>",
        ))
        if any(v > 0 for v in rnd_rev):
            fig.add_trace(go.Scatter(
                x=rnd_x, y=rnd_rev,
                mode="lines+markers",
                name="Выручка RnD (пилот)",
                line=dict(color="#6EE7B7", width=2, dash="dash"),
                marker=dict(size=7),
                hovertemplate="%{x}: %{y:,.0f} ₽<extra>Пилот (RnD)</extra>",
            ))
        fig.add_trace(go.Scatter(
            x=rnd_x, y=rnd_cum_cf,
            mode="lines+markers",
            name="Cumulative CF (RnD)",
            line=dict(color="#8B5CF6", width=2, dash="dot"),
            marker=dict(size=5),
            hovertemplate="%{x}: %{y:,.0f} ₽<extra>Cum CF (RnD)</extra>",
        ))
        fig.add_trace(go.Scatter(
            x=rnd_x, y=rnd_cum_npv,
            mode="lines+markers",
            name="Cumulative NPV (RnD)",
            line=dict(color="#F97316", width=2, dash="dot"),
            marker=dict(size=5, symbol="diamond"),
            hovertemplate="%{x}: %{y:,.0f} ₽<extra>Cum NPV (RnD)</extra>",
        ))

    # ── Рыночные линии ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=market_x, y=revenue,
        mode="lines+markers",
        name="Выручка (Revenue)",
        line=dict(color="#10B981", width=3),
        marker=dict(size=7),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Выручка</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=market_x, y=total_costs,
        mode="lines+markers",
        name="Затраты (Total Costs)",
        line=dict(color="#EF4444", width=3),
        marker=dict(size=7),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Затраты</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=market_x, y=cash_flow,
        mode="lines+markers",
        name="Cash Flow (мес.)",
        line=dict(color="#3B82F6", width=2),
        marker=dict(size=6),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>CF мес.</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=market_x, y=cumulative,
        mode="lines+markers",
        name="Cumulative CF",
        line=dict(color="#8B5CF6", width=2, dash="dash"),
        marker=dict(size=5),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Cumulative CF</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=market_x, y=cum_npv,
        mode="lines+markers",
        name="Cumulative NPV (дисконт.)",
        line=dict(color="#F97316", width=2, dash="dot"),
        marker=dict(size=5, symbol="diamond"),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Cumulative NPV</extra>",
    ))

    # Нулевая линия
    fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)

    # CF Breakeven — звёздочка на кривой Cumulative CF
    # Используем скорректированный список cumulative (уже учитывает RnD-дефицит).
    for i, r in enumerate(cf_results):
        if cumulative[i] >= 0:
            fig.add_trace(go.Scatter(
                x=[r["month"]], y=[cumulative[i]],
                mode="markers",
                name=f"CF Breakeven (М{r['month']})",
                marker=dict(size=14, color="#8B5CF6", symbol="star"),
                hovertemplate=f"CF Breakeven: месяц {r['month']}<extra></extra>",
            ))
            break

    # NPV Breakeven — ромб на кривой Cumulative NPV
    for i, r in enumerate(cf_results):
        if cum_npv[i] >= 0:
            fig.add_trace(go.Scatter(
                x=[r["month"]], y=[cum_npv[i]],
                mode="markers",
                name=f"NPV Breakeven (М{r['month']})",
                marker=dict(size=14, color="#F97316", symbol="diamond"),
                hovertemplate=f"NPV Breakeven: месяц {r['month']}<extra></extra>",
            ))
            break

    _phase_vlines(fig, phase1_end, phase2_end, len(cf_results))

    # Подписи оси X: чередуем RnD и рыночные метки
    if RnD_cf_results:
        fig.update_xaxes(
            tickmode="array",
            tickvals=all_x,
            ticktext=all_labels,
        )

    fig.update_layout(
        title="График 1 — Cash Flow и NPV по месяцам",
        xaxis_title="Месяц (от старта инвестиций)" if RnD_cf_results else "Месяц",
        yaxis_title="Рубли (₽)",
        hovermode="x unified",
        template="plotly_white",
        height=540,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# График 2 — Структура выручки
# ──────────────────────────────────────────────────────────────────────────────

def create_revenue_breakdown_chart(
    cf_results: List[Dict],
    phase1_end: int,
    phase2_end: int,
) -> go.Figure:
    """
    Stacked bar: 4 сценария партнёрских выплат по месяцам.

    NEW      — партнёр платит за нового клиента (Acquisition, X=2).
    LOYAL    — партнёр платит за incremental uplift лояльного (Expansion, X=4).
    RET      — партнёр платит за реактивацию ушедшего (Reactivation, X=1).
    AT_RISK  — партнёр платит за удержание в зоне оттока (Anti-churn, X=3).

    Показывает, как меняется структура дохода по сценариям при росте каталога.
    """
    months       = [r["month"] for r in cf_results]
    rev_new      = [r.get("revenue_new",     0.0) for r in cf_results]
    rev_loyal    = [r.get("revenue_loyal",   0.0) for r in cf_results]
    rev_ret      = [r.get("revenue_ret",     0.0) for r in cf_results]
    rev_at_risk  = [r.get("revenue_at_risk", 0.0) for r in cf_results]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=months, y=rev_new,
        name="NEW (новый клиент)",
        marker_color="#3B82F6",
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>NEW</extra>",
    ))
    fig.add_trace(go.Bar(
        x=months, y=rev_loyal,
        name="LOYAL (лояльный)",
        marker_color="#10B981",
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>LOYAL</extra>",
    ))
    fig.add_trace(go.Bar(
        x=months, y=rev_ret,
        name="RET (реактивация)",
        marker_color="#F59E0B",
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>RET</extra>",
    ))
    fig.add_trace(go.Bar(
        x=months, y=rev_at_risk,
        name="AT_RISK (удержание)",
        marker_color="#8B5CF6",
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>AT_RISK</extra>",
    ))

    _phase_vlines(fig, phase1_end, phase2_end, len(cf_results))

    fig.update_layout(
        title="График 2 — Структура выручки: 4 сценария партнёрских выплат",
        xaxis_title="Месяц",
        yaxis_title="Рубли (₽)",
        barmode="stack",
        hovermode="x unified",
        template="plotly_white",
        height=440,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# График 3 — Структура затрат
# ──────────────────────────────────────────────────────────────────────────────

def create_costs_structure_chart(
    cf_results: List[Dict],
    phase1_end: int,
    phase2_end: int,
) -> go.Figure:
    """
    Stacked bar: Fixed Costs + Variable Costs по месяцам.

    Отражает ступенчатый рост постоянных затрат при переходе фаз
    и нелинейный рост переменных вместе с redemptions.
    """
    months = [r["month"] for r in cf_results]
    fixed = [r["fixed_costs"] for r in cf_results]
    variable = [r["variable_costs"] for r in cf_results]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=months, y=fixed,
        name="Постоянные затраты (Fixed)",
        marker_color="#EF4444",
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Fixed</extra>",
    ))
    fig.add_trace(go.Bar(
        x=months, y=variable,
        name="Переменные затраты (Variable)",
        marker_color="#F59E0B",
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Variable</extra>",
    ))

    _phase_vlines(fig, phase1_end, phase2_end, len(cf_results))

    fig.update_layout(
        title="График 3 — Структура затрат: Fixed vs Variable",
        xaxis_title="Месяц",
        yaxis_title="Рубли (₽)",
        barmode="stack",
        hovermode="x unified",
        template="plotly_white",
        height=440,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# График 4 — Сегментная динамика (stock-and-flow)
# ──────────────────────────────────────────────────────────────────────────────

def create_segment_dynamics_chart(
    revenue_results: List[Dict],
    phase1_end: int,
    phase2_end: int,
) -> go.Figure:
    """
    Stacked area chart: new_app / seg_low / seg_mid / seg_act по месяцам.
    Единая ось Y — все линии в одном масштабе, чтобы видеть долю покрытия MAU.

    Слои:
      • Stacked area: сегменты Hub (NEW + LOW + MID + ACT)
      • Линия Hub MAU total (app + web) — жирная чёрная
      • Линия MAU app (только приложение) — красная пунктирная, та же ось
      • Hover: показывает % покрытия Hub / MAU app

    Ожидает в revenue_results ключи: new_app, seg_low, seg_mid, seg_act,
    new_web, mau_hub, mau_web_cur, mau_app_cur, month.
    """
    months   = [r["month"]   for r in revenue_results]
    new_app  = [r.get("new_app", 0)  for r in revenue_results]
    seg_low  = [r.get("seg_low", 0)  for r in revenue_results]
    seg_mid  = [r.get("seg_mid", 0)  for r in revenue_results]
    seg_act  = [r.get("seg_act", 0)  for r in revenue_results]

    mau_hub_total = [
        r.get("mau_hub", 0) + r.get("new_web", 0)
        for r in revenue_results
    ]
    mau_app_only = [r.get("mau_app_cur", 0) for r in revenue_results]

    # Процент покрытия Hub от MAU приложения (для hover)
    coverage_pct = [
        (h / a * 100) if a > 0 else 0
        for h, a in zip(mau_hub_total, mau_app_only)
    ]

    fig = go.Figure()

    # ── Сегменты (stacked area) ───────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=months, y=new_app,
        mode="lines",
        name="NEW (fresh app)",
        stackgroup="one",
        fillcolor="rgba(156, 163, 175, 0.55)",
        line=dict(color="rgba(156, 163, 175, 0.8)", width=1),
        hovertemplate="М%{x}: %{y:,.0f}<extra>NEW (app)</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=seg_low,
        mode="lines",
        name="LOW (пассивные)",
        stackgroup="one",
        fillcolor="rgba(59, 130, 246, 0.50)",
        line=dict(color="rgba(59, 130, 246, 0.8)", width=1),
        hovertemplate="М%{x}: %{y:,.0f}<extra>LOW</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=seg_mid,
        mode="lines",
        name="MID (ситуативные)",
        stackgroup="one",
        fillcolor="rgba(245, 158, 11, 0.50)",
        line=dict(color="rgba(245, 158, 11, 0.8)", width=1),
        hovertemplate="М%{x}: %{y:,.0f}<extra>MID</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=seg_act,
        mode="lines",
        name="ACT (оптимизаторы)",
        stackgroup="one",
        fillcolor="rgba(16, 185, 129, 0.55)",
        line=dict(color="rgba(16, 185, 129, 0.8)", width=1),
        hovertemplate="М%{x}: %{y:,.0f}<extra>ACT</extra>",
    ))

    # ── Линия Hub total ───────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=months,
        y=mau_hub_total,
        mode="lines+markers",
        name="Hub MAU итого (app + web)",
        line=dict(color="#1E293B", width=2.5, dash="solid"),
        marker=dict(size=5, symbol="circle"),
        customdata=coverage_pct,
        hovertemplate="М%{x}: %{y:,.0f} (%{customdata:.1f}% от MAU app)<extra>Hub total</extra>",
    ))

    # ── Линия MAU приложения — потолок охвата ─────────────────────────────────
    fig.add_trace(go.Scatter(
        x=months,
        y=mau_app_only,
        mode="lines",
        name="MAU приложения T-Bank (потолок охвата)",
        line=dict(color="#DC2626", width=2, dash="dot"),
        hovertemplate="М%{x}: %{y:,.0f}<extra>MAU app (потолок)</extra>",
    ))

    _phase_vlines(fig, phase1_end, phase2_end, len(revenue_results))

    fig.update_layout(
        title="График 4 — Сегментная динамика и покрытие MAU: Hub vs T-Bank app",
        xaxis_title="Месяц",
        yaxis=dict(
            title="Пользователи",
            showgrid=True,
            rangemode="tozero",
            tickformat=".2s",
        ),
        hovermode="x unified",
        template="plotly_white",
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
