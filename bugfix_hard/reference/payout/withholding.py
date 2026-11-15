THRESHOLD = 1_000_000


def withholding_tax(base: int) -> int:
    """源泉徴収税額（1円未満切り捨て）。base は源泉徴収の対象額。"""
    if base <= THRESHOLD:
        return base * 1021 // 10000
    return THRESHOLD * 1021 // 10000 + (base - THRESHOLD) * 2042 // 10000
