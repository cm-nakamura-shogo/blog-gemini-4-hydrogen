"""採点用の隠しテスト。モデルには見せない。

仕込んだバグとの対応:
  H1 振替休日が「翌日」固定で、連休に重なると消える      -> test_furikae_*
  H2 第n月曜日が、1日が月曜日の月で1週ずれる            -> test_nth_monday_*
  H3 国民の休日の条件が「前日または翌日」になっている    -> test_kokumin_*
  H4 100万円超で全額に20.42%を掛けている                -> test_withholding_over_*
  H5 源泉徴収の対象額に消費税を含めている              -> test_payout_*
  H6 休業日の支払日を後ろ倒しにしている                -> test_pay_*
  H7 年末年始を金融機関の休業日に含めていない          -> test_bank_year_end_*, test_pay_year_end
  H8 元号の境界を年だけで判定している                  -> test_wareki_*
"""

from datetime import date

import pytest

from payout import calc_payout, holidays, is_bank_holiday, payment_date, to_wareki, withholding_tax


# 祝日
def test_furikae_golden_week_2026():
    assert date(2026, 5, 6) in holidays(2026)


def test_furikae_simple_2027():
    assert date(2027, 3, 22) in holidays(2027)


def test_nth_monday_keirou_2025():
    h = holidays(2025)
    assert date(2025, 9, 15) in h and date(2025, 9, 22) not in h


def test_nth_monday_seijin_2029():
    assert date(2029, 1, 8) in holidays(2029)


def test_kokumin_silver_week_2026():
    assert date(2026, 9, 22) in holidays(2026)


def test_kokumin_not_after_single_holiday():
    h = holidays(2026)
    assert date(2026, 11, 4) not in h and date(2026, 11, 2) not in h


@pytest.mark.parametrize("year,count", [(2025, 19), (2026, 18), (2027, 17), (2029, 19)])
def test_holiday_count(year, count):
    assert len(holidays(year)) == count


# 金融機関の休業日
def test_bank_year_end_dec31():
    assert is_bank_holiday(date(2026, 12, 31))


def test_bank_year_end_jan2():
    assert is_bank_holiday(date(2026, 1, 2))


# 源泉徴収
def test_withholding_threshold():
    assert withholding_tax(1_000_000) == 102_100


def test_withholding_over_1_5m():
    assert withholding_tax(1_500_000) == 204_200


def test_withholding_over_just():
    assert withholding_tax(1_000_001) == 102_100


def test_payout_small():
    p = calc_payout(100_000, date(2026, 6, 10))
    assert (p.consumption_tax, p.withholding, p.amount) == (10_000, 10_210, 99_790)


def test_payout_large():
    p = calc_payout(1_500_000, date(2026, 6, 10))
    assert (p.withholding, p.amount) == (204_200, 1_445_800)


# 支払日
def test_pay_weekend_moves_earlier():
    # 5/31（日） -> 5/29（金）
    assert payment_date(date(2026, 4, 10)) == date(2026, 5, 29)


def test_pay_plain():
    assert payment_date(date(2026, 6, 10)) == date(2026, 7, 31)


def test_pay_year_end():
    # 12/31（木）は年末の休業日 -> 12/30（水）
    assert payment_date(date(2026, 11, 15)) == date(2026, 12, 30)


def test_pay_january():
    # 2027/1/31（日） -> 1/29（金）
    assert payment_date(date(2026, 12, 5)) == date(2027, 1, 29)


# 和暦
def test_wareki_heisei_last_day():
    assert to_wareki(date(2019, 4, 30)) == "平成31年4月30日"


def test_wareki_reiwa_first_day():
    assert to_wareki(date(2019, 5, 1)) == "令和元年5月1日"


def test_wareki_heisei_first_day():
    assert to_wareki(date(1989, 1, 8)) == "平成元年1月8日"


def test_wareki_before_heisei():
    with pytest.raises(ValueError):
        to_wareki(date(1989, 1, 7))
