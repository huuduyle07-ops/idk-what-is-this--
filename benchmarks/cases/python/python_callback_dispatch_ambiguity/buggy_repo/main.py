from dispatcher import dispatch


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def main():
    order_result = dispatch(
        "order_placed",
        {"items": ["keyboard", "mouse"], "balance": 100.0, "amount": 30.0},
    )
    assert_equal(order_result, 70.0, "order_placed should subtract amount from balance")

    refund_result = dispatch(
        "refund",
        {"items": ["mouse"], "balance": 70.0, "amount": 25.0},
    )
    assert_equal(refund_result, 95.0, "refund should ADD amount back to balance")

    cancel_result = dispatch(
        "cancel",
        {"items": [], "balance": 95.0, "amount": 0.0},
    )
    assert_equal(cancel_result, 95.0, "cancel should leave balance unchanged")

    print("OK")


if __name__ == "__main__":
    main()
