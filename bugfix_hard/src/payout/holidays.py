from datetime import date, timedelta
from functools import cache

FIXED = [(1, 1), (2, 11), (2, 23), (4, 29), (5, 3), (5, 4), (5, 5), (8, 11), (11, 3), (11, 23)]
HAPPY_MONDAY = [(1, 2), (7, 3), (9, 3), (10, 2)]  # (月, 第n月曜日)


def nth_monday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    day = 8 - first.weekday() + 7 * (n - 1)
    return date(year, month, day)


def vernal_equinox(year: int) -> date:
    return date(year, 3, int(20.8431 + 0.242194 * (year - 1980) - (year - 1980) // 4))


def autumnal_equinox(year: int) -> date:
    return date(year, 9, int(23.2488 + 0.242194 * (year - 1980) - (year - 1980) // 4))


@cache
def holidays(year: int) -> frozenset[date]:
    """その年の祝日（振替休日と国民の休日を含む）。"""
    base = {date(year, m, d) for m, d in FIXED}
    base |= {nth_monday(year, m, n) for m, n in HAPPY_MONDAY}
    base |= {vernal_equinox(year), autumnal_equinox(year)}

    result = set(base)
    # 振替休日
    for d in base:
        if d.weekday() == 6:
            result.add(d + timedelta(days=1))
    # 国民の休日
    d = date(year, 1, 2)
    while d.year == year:
        prev, nxt = d - timedelta(days=1), d + timedelta(days=1)
        if d not in base and (prev in base or nxt in base) and d.weekday() != 6:
            if prev.month == d.month == nxt.month:
                result.add(d)
        d += timedelta(days=1)
    return frozenset(result)


def is_holiday(d: date) -> bool:
    return d in holidays(d.year)


def is_bank_holiday(d: date) -> bool:
    """金融機関の休業日かどうか。"""
    return d.weekday() >= 5 or is_holiday(d)
