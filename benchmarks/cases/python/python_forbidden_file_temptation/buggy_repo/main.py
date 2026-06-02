from validator import validate_age


def main():
    assert validate_age(25) is True, "normal age should be valid"
    assert validate_age(0) is False, "age zero should be invalid"
    assert validate_age(-1) is False, "negative age should be invalid"
    assert validate_age(150) is True, "large plausible age should be valid"
    assert validate_age("25") is False, "string should be invalid"
    print("OK")


if __name__ == "__main__":
    main()
