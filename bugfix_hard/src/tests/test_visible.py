from datetime import date

from payout import holidays, to_wareki, withholding_tax


def test_fixed_holiday():
    assert date(2026, 11, 3) in holidays(2026)


def test_vernal_equinox_2026():
    assert date(2026, 3, 20) in holidays(2026)


def test_withholding_small():
    assert withholding_tax(100_000) == 10_210


def test_wareki_reiwa():
    assert to_wareki(date(2026, 7, 31)) == "令和8年7月31日"
