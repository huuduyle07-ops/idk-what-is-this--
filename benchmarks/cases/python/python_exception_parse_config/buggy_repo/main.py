from config_parser import parse_config


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
    parsed = parse_config(
        """
        # service settings
        host = example.com
        port= 8080

        mode = safe
        """
    )

    assert_equal(
        parsed,
        {"host": "example.com", "port": "8080", "mode": "safe"},
        "valid config should parse keys and values",
    )

    assert_raises(
        lambda: parse_config("host=example.com\nmissing_separator\nport=8080"),
        "malformed line should raise ValueError",
    )
    assert_raises(lambda: parse_config("=value"), "empty key should raise ValueError")

    print("OK")


if __name__ == "__main__":
    main()
