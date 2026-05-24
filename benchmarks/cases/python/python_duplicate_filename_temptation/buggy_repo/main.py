from app.config import get_max_retries


def main():
    retries = get_max_retries()
    if retries != 3:
        raise AssertionError(
            f"app.config.get_max_retries should return 3 at runtime, got {retries}"
        )
    print("OK")


if __name__ == "__main__":
    main()
