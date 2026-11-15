from dataclasses import dataclass
from datetime import date

from .schedule import payment_date
from .withholding import withholding_tax


@dataclass(frozen=True)
class Payout:
    fee: int  # 報酬額（税抜）
    consumption_tax: int  # 消費税額
    withholding: int  # 源泉徴収税額
    amount: int  # 支払額
    pay_on: date  # 支払日


def calc_payout(fee: int, accepted: date) -> Payout:
    tax = fee * 10 // 100
    wh = withholding_tax(fee)
    return Payout(fee, tax, wh, fee + tax - wh, payment_date(accepted))
