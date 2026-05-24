from handlers import handle_cancel, handle_order_placed, handle_refund


# Event name -> handler callable. Adding/removing entries here only changes
# routing; the actual event logic lives inside each handler.
HANDLERS = {
    "order_placed": handle_order_placed,
    "refund": handle_refund,
    "cancel": handle_cancel,
}


def dispatch(event_name: str, payload: dict) -> float:
    handler = HANDLERS.get(event_name)
    if handler is None:
        raise KeyError(f"no handler registered for {event_name!r}")
    return handler(payload)
