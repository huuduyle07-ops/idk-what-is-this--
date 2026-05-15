import sqlite3

from transfer import transfer_funds


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            owner TEXT NOT NULL,
            balance_cents INTEGER NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO accounts (id, owner, balance_cents) VALUES (?, ?, ?)",
        [
            (1, "Ada", 10_000),
            (2, "Grace", 2_500),
        ],
    )
    conn.commit()
    return conn


def balances(conn):
    return dict(conn.execute("SELECT id, balance_cents FROM accounts ORDER BY id").fetchall())


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
    conn = make_db()

    transfer_funds(conn, 1, 2, 1_500)
    assert_equal(balances(conn), {1: 8_500, 2: 4_000}, "valid transfer should move funds")

    before = balances(conn)
    assert_raises(lambda: transfer_funds(conn, 1, 2, 20_000), "overdraft should fail")
    assert_equal(balances(conn), before, "overdraft should not change balances")

    before = balances(conn)
    assert_raises(lambda: transfer_funds(conn, 99, 2, 100), "missing source account should fail")
    assert_equal(balances(conn), before, "missing source should not change balances")

    before = balances(conn)
    assert_raises(lambda: transfer_funds(conn, 1, 99, 100), "missing destination account should fail")
    assert_equal(balances(conn), before, "missing destination should not change balances")

    before = balances(conn)
    assert_raises(lambda: transfer_funds(conn, 1, 2, 0), "zero transfer should fail")
    assert_equal(balances(conn), before, "zero transfer should not change balances")

    print("OK")


if __name__ == "__main__":
    main()
