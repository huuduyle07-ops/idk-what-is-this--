from pricing import calculate_final_price
from product_catalog import get_price


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def assert_raises(fn, message):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(message)


def main():
    keyboard = get_price("keyboard")

    assert_equal(calculate_final_price(keyboard, 0), 120.0, "0 percent discount should keep price")
    assert_equal(calculate_final_price(keyboard, 25), 90.0, "25 percent discount should work")
    assert_equal(calculate_final_price(keyboard, 100), 0.0, "100 percent discount should be free")

    assert_raises(
        lambda: calculate_final_price(keyboard, -10),
        "negative discount should fail",
    )

    assert_raises(
        lambda: calculate_final_price(keyboard, 150),
        "discount over 100 should fail",
    )

    assert_raises(
        lambda: calculate_final_price(-20, 10),
        "negative base price should fail",
    )

    print("OK")


if __name__ == "__main__":
    main()
