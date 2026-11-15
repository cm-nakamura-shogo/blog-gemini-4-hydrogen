from dataclasses import dataclass

from .models import Line


@dataclass(frozen=True)
class Invoice:
    subtotal_by_rate: dict[int, int]  # 税率 -> 税抜合計
    tax_by_rate: dict[int, int]  # 税率 -> 消費税額
    total: int  # 請求額（税込）


def calc_invoice(lines: list[Line]) -> Invoice:
    subtotal_by_rate: dict[int, int] = {}
    for line in lines:
        if line.rate not in (8, 10):
            raise ValueError(f"unsupported rate: {line.rate}")
        subtotal_by_rate[line.rate] = subtotal_by_rate.get(line.rate, 0) + line.amount
    tax_by_rate = {rate: subtotal * rate // 100 for rate, subtotal in subtotal_by_rate.items()}
    total = sum(subtotal_by_rate.values()) + sum(tax_by_rate.values())
    return Invoice(subtotal_by_rate, tax_by_rate, total)
