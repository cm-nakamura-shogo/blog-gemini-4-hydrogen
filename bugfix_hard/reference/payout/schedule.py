import calendar
from datetime import date, timedelta

from .holidays import is_bank_holiday


def payment_date(accepted: date) -> date:
    """検収日から支払日を求める。"""
    year, month = (accepted.year + 1, 1) if accepted.month == 12 else (accepted.year, accepted.month + 1)
    d = date(year, month, calendar.monthrange(year, month)[1])
    while is_bank_holiday(d):
        d -= timedelta(days=1)
    return d
