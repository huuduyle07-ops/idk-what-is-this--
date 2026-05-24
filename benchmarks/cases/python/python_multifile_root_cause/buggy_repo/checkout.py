from pricing import calculate_subtotal


def process_order(line_item_prices: list[float]) -> float:
    # Delegates the math to pricing.calculate_subtotal — that helper owns the
    # rounding/summation rules. This file just adapts the order shape.
    return calculate_subtotal(line_item_prices)
