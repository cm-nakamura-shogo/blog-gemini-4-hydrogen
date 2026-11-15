from datetime import date

from invoice import Line, calc_invoice, closing_date, due_date, to_wareki


def test_single_rate():
    inv = calc_invoice([Line("用紙", 1000, 3, 10)])
    assert inv.subtotal_by_rate == {10: 3000}
    assert inv.tax_by_rate == {10: 300}
    assert inv.total == 3300


def test_month_end_closing():
    assert closing_date(date(2026, 6, 15), "month_end") == date(2026, 6, 30)


def test_due_date_plain():
    # 2026/6/30 締め -> 7/31（金）
    assert due_date(date(2026, 6, 15), "month_end") == date(2026, 7, 31)


def test_wareki():
    assert to_wareki(date(2026, 7, 31)) == "令和8年7月31日"
