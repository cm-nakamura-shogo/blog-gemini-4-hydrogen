from datetime import date

ERAS = [  # (元号, 開始日)
    ("令和", date(2019, 5, 1)),
    ("平成", date(1989, 1, 8)),
]


def to_wareki(d: date) -> str:
    for name, start in ERAS:
        if d >= start:
            n = d.year - start.year + 1
            label = "元" if n == 1 else str(n)
            return f"{name}{label}年{d.month}月{d.day}日"
    raise ValueError("平成より前の日付は扱わない")
