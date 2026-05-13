PRODUCTS = {
    "keyboard": 120.0,
    "mouse": 50.0,
    "monitor": 300.0,
}


def get_price(product_name: str) -> float:
    if product_name not in PRODUCTS:
        raise ValueError("unknown product")
    return PRODUCTS[product_name]
