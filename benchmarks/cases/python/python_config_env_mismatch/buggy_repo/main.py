import os
from config import get_database_url, get_port


def assert_equal(actual, expected, msg):
    if actual != expected:
        raise AssertionError(f"{msg}: expected {expected!r}, got {actual!r}")


def main():
    os.environ["DATABASE_URL"] = "postgres://localhost/mydb"
    os.environ["SERVER_PORT"] = "9090"

    url = get_database_url()
    assert_equal(url, "postgres://localhost/mydb", "database URL")

    port = get_port()
    assert_equal(port, 9090, "server port")

    print("OK")


if __name__ == "__main__":
    main()
