def handle_order_placed(payload: dict) -> float:
    return float(payload["balance"]) - float(payload["amount"])


def handle_refund(payload: dict) -> float:
    # BUG: refund should ADD the refunded amount back to the balance,
    # not subtract it. The dispatcher correctly routes "refund" here —
    # the defect is in this handler, not in the dispatcher.
    return float(payload["balance"]) - float(payload["amount"])


def handle_cancel(payload: dict) -> float:
    return float(payload["balance"])
