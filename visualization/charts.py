"""
Графики для калькулятора Unified Promo Hub.

График 1 — Cash Flow: Revenue / Total Costs / CF / Cumulative CF по месяцам.
           Вертикальные линии на границах Phase 1→2→3.

График 2 — Структура выручки: CPA Revenue vs RevShare Revenue (stacked bar).

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
) -> go.Figure:
    """
    Линейный график Cash Flow и NPV по месяцам.

    Серии:
        Revenue         — зелёная (сплошная)
        Total Costs     — красная (сплошная)
        Cash Flow мес.  — синяя (сплошная)
        Cumulative CF   — фиолетовый пунктир
        Cumulative NPV  — оранжевый пунктир (дисконтированный поток)
    """
    months = [r["month"] for r in cf_results]
    revenue = [r["revenue"] for r in cf_results]
    total_costs = [r["total_costs"] for r in cf_results]
    cash_flow = [r["cash_flow"] for r in cf_results]
    cumulative = [r["cumulative_cash_flow"] for r in cf_results]
    cumulative_npv = [r.get("cumulative_npv", 0) for r in cf_results]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=months, y=revenue,
        mode="lines+markers",
        name="Выручка (Revenue)",
        line=dict(color="#10B981", width=3),
        marker=dict(size=7),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Выручка</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=total_costs,
        mode="lines+markers",
        name="Затраты (Total Costs)",
        line=dict(color="#EF4444", width=3),
        marker=dict(size=7),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Затраты</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=cash_flow,
        mode="lines+markers",
        name="Cash Flow (мес.)",
        line=dict(color="#3B82F6", width=2),
        marker=dict(size=6),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>CF мес.</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=cumulative,
        mode="lines+markers",
        name="Cumulative CF",
        line=dict(color="#8B5CF6", width=2, dash="dash"),
        marker=dict(size=5),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Cumulative CF</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=cumulative_npv,
        mode="lines+markers",
        name="Cumulative NPV (дисконт.)",
        line=dict(color="#F97316", width=2, dash="dot"),
        marker=dict(size=5, symbol="diamond"),
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>Cumulative NPV</extra>",
    ))

    # Нулевая линия
    fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)

    # CF Breakeven — звёздочка
    for r in cf_results:
        if r["cumulative_cash_flow"] >= 0:
            fig.add_trace(go.Scatter(
                x=[r["month"]], y=[0],
                mode="markers",
                name=f"CF Breakeven (М{r['month']})",
                marker=dict(size=14, color="#8B5CF6", symbol="star"),
                hovertemplate=f"CF Breakeven: месяц {r['month']}<extra></extra>",
            ))
            break

    # NPV Breakeven — ромб
    for r in cf_results:
        if r.get("cumulative_npv", -1) >= 0:
            fig.add_trace(go.Scatter(
                x=[r["month"]], y=[0],
                mode="markers",
                name=f"NPV Breakeven (М{r['month']})",
                marker=dict(size=14, color="#F97316", symbol="diamond"),
                hovertemplate=f"NPV Breakeven: месяц {r['month']}<extra></extra>",
            ))
            break

    _phase_vlines(fig, phase1_end, phase2_end, len(cf_results))

    fig.update_layout(
        title="График 1 — Cash Flow и NPV по месяцам",
        xaxis_title="Месяц",
        yaxis_title="Рубли (₽)",
        hovermode="x unified",
        template="plotly_white",
        height=520,
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
    Stacked bar: CPA Revenue vs RevShare Revenue по месяцам.

    Показывает, как меняется структура дохода при росте каталога партнёров
    и сдвиге mix CPA → RevShare.
    """
    months = [r["month"] for r in cf_results]
    rev_cpa = [r["revenue_cpa"] for r in cf_results]
    rev_rs = [r["revenue_rs"] for r in cf_results]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=months, y=rev_cpa,
        name="CPA-выручка",
        marker_color="#3B82F6",
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>CPA</extra>",
    ))
    fig.add_trace(go.Bar(
        x=months, y=rev_rs,
        name="RevShare-выручка",
        marker_color="#10B981",
        hovertemplate="М%{x}: %{y:,.0f} ₽<extra>RevShare</extra>",
    ))

    _phase_vlines(fig, phase1_end, phase2_end, len(cf_results))

    fig.update_layout(
        title="График 2 — Структура выручки: CPA vs RevShare",
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

    Показывает, как накапливается аудитория по поведенческим паттернам
    и как растёт доля ACT-пользователей к концу горизонта.

    Ожидает в revenue_results ключи: new_app, seg_low, seg_mid, seg_act, month.
    """
    months   = [r["month"]   for r in revenue_results]
    new_app  = [r.get("new_app", 0)  for r in revenue_results]
    seg_low  = [r.get("seg_low", 0)  for r in revenue_results]
    seg_mid  = [r.get("seg_mid", 0)  for r in revenue_results]
    seg_act  = [r.get("seg_act", 0)  for r in revenue_results]

    fig = go.Figure()

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

    _phase_vlines(fig, phase1_end, phase2_end, len(revenue_results))

    fig.update_layout(
        title="График 4 — Сегментная динамика: NEW / LOW / MID / ACT",
        xaxis_title="Месяц",
        yaxis_title="Пользователи",
        hovermode="x unified",
        template="plotly_white",
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
