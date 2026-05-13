def calculate_final_price(base_price: float, discount_percent: float) -> float:
    # BUG: allows negative prices and invalid discounts over 100%.
    discount_amount = base_price * (discount_percent / 100)
    return base_price - discount_amount
