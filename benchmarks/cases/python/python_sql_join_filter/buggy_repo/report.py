def paid_order_totals_by_customer(conn, city: str):
    rows = conn.execute(
        """
        SELECT c.name, COALESCE(SUM(o.total_cents), 0) AS paid_total
        FROM customers AS c
        LEFT JOIN orders AS o ON o.customer_id = c.id
        WHERE c.city = ?
          AND c.active = 1
          AND o.status = 'paid'
        GROUP BY c.id, c.name
        ORDER BY c.name
        """,
        (city,),
    ).fetchall()
    return [(name, paid_total) for name, paid_total in rows]
