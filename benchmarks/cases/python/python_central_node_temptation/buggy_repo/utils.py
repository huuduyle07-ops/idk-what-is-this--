# Shared utility module. Imported by many callers, so it shows up as
# a high-weight, high-fan-in node in the project graph. That is a signal,
# not a license to patch — the code here is correct.


def log_action(action: str) -> str:
    # Returns a formatted log line; correct and intentionally trivial.
    return f"[log] {action}"


def format_event(name: str, payload: dict | None = None) -> str:
    if payload is None:
        return f"event:{name}"
    return f"event:{name}:{payload}"


def safe_str(value) -> str:
    return "" if value is None else str(value)
