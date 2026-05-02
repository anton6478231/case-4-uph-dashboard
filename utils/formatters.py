"""
Вспомогательные функции форматирования чисел для отображения в UI.
"""


def format_currency(value: float, suffix: str = " ₽") -> str:
    """Форматирует число как рубли с разделителями тысяч."""
    if value is None:
        return "—"
    return f"{value:,.0f}{suffix}".replace(",", " ")


def format_currency_compact(value: float) -> str:
    """
    Компактный формат: млрд / млн / тыс / просто число.
    Используется в KPI-карточках где мало места.
    """
    if value is None:
        return "—"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""

    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.1f} млрд ₽"
    if abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.1f} млн ₽"
    if abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:.1f} тыс ₽"
    return f"{sign}{abs_val:.0f} ₽"


def format_number_compact(value: float) -> str:
    """Компактный формат числа без знака рубля (для MAU, redemptions и т.п.)."""
    if value is None:
        return "—"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""

    if abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.1f} млн"
    if abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:.0f} тыс"
    return f"{sign}{abs_val:.0f}"


def format_pct(value: float, decimals: int = 1) -> str:
    """Форматирует дробь (0..1) как проценты."""
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%"
