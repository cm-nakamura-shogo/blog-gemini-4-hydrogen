from datetime import date

REIWA_START = date(2019, 5, 1)


def to_wareki(d: date) -> str:
    if d < REIWA_START:
        raise ValueError("令和より前の日付は扱わない")
    year = d.year - 2018
    label = "元" if year == 1 else str(year)
    return f"令和{label}年{d.month}月{d.day}日"
