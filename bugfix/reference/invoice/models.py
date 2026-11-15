from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    """請求書の明細。rate は 10 または 8（%）。"""

    name: str
    unit_price: int
    quantity: int
    rate: int

    @property
    def amount(self) -> int:
        return self.unit_price * self.quantity
