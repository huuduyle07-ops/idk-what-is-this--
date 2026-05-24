from shopping import calculate_cart_total


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def main():
    # All of these already pass — the code under test is correct.
    assert_equal(calculate_cart_total([]), 0.0, "empty cart")
    assert_equal(calculate_cart_total([10.0]), 10.0, "single-item cart")
    assert_equal(
        calculate_cart_total([1.5, 2.5, 3.0]),
        7.0,
        "three-item cart",
    )
    assert_equal(
        calculate_cart_total([100.0, 200.0, 300.0]),
        600.0,
        "large cart",
    )
    print("OK")


if __name__ == "__main__":
    main()
