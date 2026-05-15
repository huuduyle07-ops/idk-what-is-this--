import sqlite3

from report import paid_order_totals_by_customer


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            active INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            total_cents INTEGER NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO customers (id, name, city, active) VALUES (?, ?, ?, ?)",
        [
            (1, "Ada", "London", 1),
            (2, "Grace", "London", 1),
            (3, "Linus", "London", 0),
            (4, "Margaret", "Paris", 1),
            (5, "Barbara", "London", 1),
        ],
    )
    conn.executemany(
        "INSERT INTO orders (id, customer_id, status, total_cents) VALUES (?, ?, ?, ?)",
        [
            (1, 1, "paid", 1200),
            (2, 1, "pending", 900),
            (3, 3, "paid", 5000),
            (4, 4, "paid", 7000),
            (5, 5, "refunded", 300),
        ],
    )
    conn.commit()
    return conn


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def main():
    conn = make_db()

    assert_equal(
        paid_order_totals_by_customer(conn, "London"),
        [("Ada", 1200), ("Barbara", 0), ("Grace", 0)],
        "London report should include active customers and only paid totals",
    )
    assert_equal(
        paid_order_totals_by_customer(conn, "Paris"),
        [("Margaret", 7000)],
        "Paris report should include only Paris active customers",
    )
    assert_equal(
        paid_order_totals_by_customer(conn, "Berlin"),
        [],
        "city with no active customers should return an empty list",
    )

    print("OK")


if __name__ == "__main__":
    main()
