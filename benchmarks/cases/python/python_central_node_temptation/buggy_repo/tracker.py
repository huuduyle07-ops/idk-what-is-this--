from utils import format_event, log_action, safe_str


_EVENT_LOG: list[str] = []


def track_event(name: str, payload: dict | None = None) -> str:
    line = log_action(format_event(safe_str(name), payload))
    _EVENT_LOG.append(line)
    return line


def event_log() -> list[str]:
    return list(_EVENT_LOG)
