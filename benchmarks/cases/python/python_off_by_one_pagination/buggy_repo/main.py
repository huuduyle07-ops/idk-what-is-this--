from pagination import paginate


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
    values = [1, 2, 3, 4, 5, 6, 7]

    assert_equal(paginate(values, 1, 3), [1, 2, 3], "page 1 should include three items")
    assert_equal(paginate(values, 2, 3), [4, 5, 6], "page 2 should include three items")
    assert_equal(paginate(values, 3, 3), [7], "final partial page should include the remainder")
    assert_equal(paginate(values, 4, 3), [], "page beyond end should be empty")

    assert_raises(lambda: paginate(values, 0, 3), "page below 1 should fail")
    assert_raises(lambda: paginate(values, 1, 0), "per_page below 1 should fail")

    print("OK")


if __name__ == "__main__":
    main()
