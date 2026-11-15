import calendar
from datetime import date

from .calendar_jp import next_business_day


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def closing_date(trade_date: date, closing: str) -> date:
    """取引日と締め方（"month_end" または "20th"）から締め日を返す。"""
    if closing == "month_end":
        return month_end(trade_date.year, trade_date.month)
    if closing == "20th":
        if trade_date.day <= 20:
            return date(trade_date.year, trade_date.month, 20)
        if trade_date.month == 12:
            return date(trade_date.year + 1, 1, 20)
        return date(trade_date.year, trade_date.month + 1, 20)
    raise ValueError(f"unknown closing: {closing}")


def due_date(trade_date: date, closing: str) -> date:
    """支払期日（締め日の翌月末、休日なら翌営業日）を返す。"""
    c = closing_date(trade_date, closing)
    y, m = (c.year + 1, 1) if c.month == 12 else (c.year, c.month + 1)
    return next_business_day(month_end(y, m))
