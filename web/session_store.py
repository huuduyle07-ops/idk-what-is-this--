from __future__ import annotations

import json
from pathlib import Path

SESSION_FILE = Path(__file__).parent / "sessions.json"


def load_sessions() -> list[dict]:
    if not SESSION_FILE.exists():
        return []
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_sessions(sessions: list[dict]) -> None:
    SESSION_FILE.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def find_session(session_id: str) -> dict | None:
    for s in load_sessions():
        if s.get("id") == session_id:
            return s
    return None


def list_sessions(
    include_archived: bool = False,
    include_deleted: bool = False,
) -> list[dict]:
    result = []
    for s in load_sessions():
        if s.get("deleted") and not include_deleted:
            continue
        if s.get("archived") and not include_archived:
            continue
        result.append(s)
    return result
