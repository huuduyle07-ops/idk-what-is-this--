def calculate_subtotal(prices: list[float]) -> float:
    # BUG: drops the last line item — should sum all entries.
    return float(sum(prices[:-1]))
