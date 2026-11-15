"""採点用の隠しテスト。モデルには見せない。

仕込んだバグとの対応:
  B1 消費税を明細ごとに端数処理している        -> test_tax_*
  B2 20日締めで20日当日を翌月に回している        -> test_closing_20th_on_20th, test_due_20th_on_20th
  B3 営業日判定が祝日を見ていない                -> test_holiday_*
  B4 12月締めの翌月末で月が13になる              -> test_due_december_*
  B5 令和元年を「令和1年」と書く                 -> test_wareki_gannen_*
"""

from datetime import date

import pytest

from invoice import Line, calc_invoice, closing_date, due_date, to_wareki
from invoice.calendar_jp import is_business_day, next_business_day

LINES = [
    Line("食品A", 199, 3, 8),
    Line("食品B", 99, 7, 8),
    Line("日用品C", 333, 3, 10),
    Line("日用品D", 101, 1, 10),
]


def test_tax_by_rate():
    inv = calc_invoice(LINES)
    assert inv.subtotal_by_rate == {8: 1290, 10: 1100}
    assert inv.tax_by_rate == {8: 103, 10: 110}


def test_tax_total():
    assert calc_invoice(LINES).total == 2603


def test_closing_20th_on_20th():
    assert closing_date(date(2026, 8, 20), "20th") == date(2026, 8, 20)


def test_closing_20th_on_21st():
    assert closing_date(date(2026, 12, 21), "20th") == date(2027, 1, 20)


def test_due_20th_on_20th():
    assert due_date(date(2026, 8, 20), "20th") == date(2026, 9, 30)


def test_due_weekend():
    # 4/30 締め -> 5/31（日） -> 6/1（月）
    assert due_date(date(2026, 4, 10), "month_end") == date(2026, 6, 1)


def test_holiday_is_not_business_day():
    assert not is_business_day(date(2026, 11, 23))


def test_holiday_next_business_day():
    # 5/2（土）から 5/3〜5/6 の祝日を越えて 5/7（木）
    assert next_business_day(date(2026, 5, 2)) == date(2026, 5, 7)


def test_due_december_month_end():
    # 12/31 締め -> 2027/1/31（日） -> 2/1（月）
    assert due_date(date(2026, 12, 10), "month_end") == date(2027, 2, 1)


def test_due_december_20th():
    # 11/25 取引 -> 12/20 締め -> 2027/1/31（日） -> 2/1（月）
    assert due_date(date(2026, 11, 25), "20th") == date(2027, 2, 1)


def test_wareki_gannen_first_day():
    assert to_wareki(date(2019, 5, 1)) == "令和元年5月1日"


def test_wareki_gannen_last_day():
    assert to_wareki(date(2019, 12, 31)) == "令和元年12月31日"


def test_wareki_second_year():
    assert to_wareki(date(2020, 1, 1)) == "令和2年1月1日"


def test_wareki_before_reiwa():
    with pytest.raises(ValueError):
        to_wareki(date(2019, 4, 30))
