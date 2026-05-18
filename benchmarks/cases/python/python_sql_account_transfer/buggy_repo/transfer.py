def transfer_funds(conn, source_account_id: int, destination_account_id: int, amount_cents: int) -> None:
    if amount_cents <= 0:
        raise ValueError("amount must be positive")

    # BUG: updates balances without checking account existence or available funds first.
    conn.execute(
        "UPDATE accounts SET balance_cents = balance_cents - ? WHERE id = ?",
        (amount_cents, source_account_id),
    )
    conn.execute(
        "UPDATE accounts SET balance_cents = balance_cents + ? WHERE id = ?",
        (amount_cents, destination_account_id),
    )
    conn.commit()
