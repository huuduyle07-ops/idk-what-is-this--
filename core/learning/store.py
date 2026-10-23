"""Owner-scoped, durable sessions for the first authored Teacher pilot.

No execution, network, model calls, or learner mastery estimation happens here.
Independent outcomes are observations on individual items, not proficiency scores.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .lesson import CONTENT_VERSION, ITEMS, LESSON, RUBRIC_VERSION

MAX_SESSIONS_PER_OWNER = 50
MAX_ACTIONS_PER_SESSION = 100


class LearningError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _text(value: Any, field: str, maximum: int, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise LearningError("invalid_input", f"{field} phải là chuỗi {'0' if empty else '1'}–{maximum} ký tự.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise LearningError("invalid_input", f"{field} chứa ký tự Unicode không hợp lệ.") from None
    return value


def _fresh_item() -> dict:
    return {
        "hint_count": 0, "solution_viewed": False, "attempts": 0,
        "selected_option": None, "reflection": "", "feedback": None,
        "independent_result": "not_observed", "assisted_success": False,
    }


def _assistance(state: dict) -> str:
    if state["solution_viewed"]:
        return "solution"
    if state["hint_count"]:
        return "hint"
    if state["attempts"]:
        return "feedback"
    return "none"


def _public(row: sqlite3.Row, state: dict | None = None) -> dict:
    state = state if state is not None else json.loads(row["state_json"])
    authored_items = state["authored_items"]
    index = state["current_index"]
    current = state["items"][index]
    authored = authored_items[index]
    successes = sum(item["independent_result"] == "success" for item in state["items"])
    failures = sum(item["independent_result"] == "failure" for item in state["items"])
    assisted = sum(item["assisted_success"] and item["independent_result"] != "success" for item in state["items"])
    answered = sum(item["attempts"] > 0 for item in state["items"])
    message = (
        f"Đã trả lời {answered}/{len(authored_items)} bài. Đúng không trợ giúp ở lần thử đầu: {successes}; "
        f"sai ở lần thử không trợ giúp đầu: {failures}; hoàn thành đúng sau trợ giúp: {assisted}. "
        "Nhãn không trợ giúp chỉ xét gợi ý và phản hồi trong phiên này; không xác minh tài liệu hoặc AI bên ngoài. "
        "Kết quả này chưa đủ để kết luận mức thành thạo hoặc khả năng nhớ lâu. "
        "Phần giải thích tự viết được lưu để tự xem lại, chưa được chấm tự động."
    )
    return {
        "id": row["id"], "revision": row["revision"], "status": state["status"],
        "lesson": dict(state["lesson"]), "current_index": index, "total_items": len(authored_items),
        "items": [
            {
                "id": item["id"], "title": item["title"],
                "status": "answered" if saved["attempts"] else ("current" if i == index else "pending"),
                "independent_result": saved["independent_result"],
                "solution_viewed": saved["solution_viewed"],
            }
            for i, (item, saved) in enumerate(zip(authored_items, state["items"]))
        ],
        "item": {
            "id": authored["id"], "title": authored["title"],
            "filename": authored["filename"], "code": authored["code"],
            "question": authored["question"], "options": [dict(option) for option in authored["options"]],
            "hints": list(authored["hints"][:current["hint_count"]]),
            "hint_count": current["hint_count"], "total_hints": len(authored["hints"]),
            "feedback": current["feedback"],
            "solution": {"body": authored["explanation"], "evidence_lines": list(authored["evidence_lines"])}
            if current["solution_viewed"] else None,
            "reflection": current["reflection"], "answered": current["attempts"] > 0,
            "selected_option": current["selected_option"], "assistance": _assistance(current),
        },
        "summary": {
            "independent_successes": successes, "independent_failures": failures,
            "assisted_successes": assisted, "answered_count": answered, "message": message,
        },
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


class LearningStore:
    """Create one store for an SQLite path; connections are opened per operation."""

    def __init__(self, path: str | Path):
        self._keeper: sqlite3.Connection | None = None
        if str(path) == ":memory:":
            self._path = f"file:learning_{uuid.uuid4().hex}?mode=memory&cache=shared"
            self._uri = True
            # A shared memory database survives the per-operation connections.
            self._keeper = sqlite3.connect(self._path, uri=True, check_same_thread=False)
        else:
            database = Path(path)
            database.parent.mkdir(parents=True, exist_ok=True)
            self._path = str(database)
            self._uri = False
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS learning_sessions (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS learning_sessions_owner_updated
                    ON learning_sessions(owner_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS learning_events (
                    session_id TEXT NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL, request_id TEXT,
                    request_json TEXT NOT NULL, event_json TEXT NOT NULL, response_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, revision), UNIQUE (session_id, request_id)
                );
            """)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._path, timeout=5, uri=self._uri)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA secure_delete = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _owner(owner_id: Any) -> str:
        return _text(owner_id, "owner_id", 200)

    @staticmethod
    def _row(conn: sqlite3.Connection, owner_id: str, session_id: str) -> sqlite3.Row:
        _text(session_id, "session_id", 128)
        row = conn.execute(
            "SELECT * FROM learning_sessions WHERE id = ? AND owner_id = ?", (session_id, owner_id),
        ).fetchone()
        if row is None:
            raise LearningError("not_found", "Không tìm thấy phiên học.", 404)
        return row

    @staticmethod
    def _event(action: str, payload: dict, revision: int, timestamp: str, item_id: str | None, state: dict) -> dict:
        return {
            "action": action, "payload": payload, "revision": revision, "timestamp": timestamp,
            "item_id": item_id, "lesson_id": state["lesson"]["id"], "lesson_version": state["lesson"]["version"],
            "rubric_version": state["rubric_version"], "content_version": state["content_version"],
            "assessment_method": "authored_multiple_choice_rubric",
        }

    def create(self, owner_id: str) -> dict:
        owner_id = self._owner(owner_id)
        session_id = str(uuid.uuid4())
        now = _timestamp()
        # Pin both learner-facing content and the private rubric for durable resume.
        # Later edits of the authored lesson affect only newly created sessions.
        state = {
            "status": "active", "current_index": 0, "items": [_fresh_item() for _ in ITEMS],
            "lesson": dict(LESSON), "authored_items": ITEMS,
            "rubric_version": RUBRIC_VERSION, "content_version": CONTENT_VERSION,
        }
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute("SELECT count(*) FROM learning_sessions WHERE owner_id = ?", (owner_id,)).fetchone()[0]
            if count >= MAX_SESSIONS_PER_OWNER:
                raise LearningError("session_limit", "Đã đạt giới hạn phiên học. Hãy xuất rồi xóa một phiên cũ trước khi tạo mới.")
            conn.execute(
                "INSERT INTO learning_sessions VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, owner_id, 0, _json(state), now, now),
            )
            result = _public(self._row(conn, owner_id, session_id), state)
            conn.execute(
                "INSERT INTO learning_events VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, 0, None, "{}", _json(self._event("created", {}, 0, now, None, state)), _json(result)),
            )
        return result

    def latest(self, owner_id: str) -> dict | None:
        sessions = self.list_recent(owner_id, limit=1)
        return sessions[0] if sessions else None

    def list_recent(self, owner_id: str, limit: int = 10) -> list[dict]:
        owner_id = self._owner(owner_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise LearningError("invalid_input", "limit phải là số nguyên từ 1 đến 50.")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM learning_sessions WHERE owner_id = ? ORDER BY updated_at DESC, id DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
            return [_public(row) for row in rows]

    def get(self, owner_id: str, session_id: str) -> dict:
        owner_id = self._owner(owner_id)
        with self._connect() as conn:
            return _public(self._row(conn, owner_id, session_id))

    def act(self, owner_id: str, session_id: str, action: str, payload: dict,
            expected_revision: int, request_id: str) -> dict:
        owner_id = self._owner(owner_id)
        _text(request_id, "request_id", 128)
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise LearningError("invalid_input", "expected_revision phải là số nguyên không âm.")
        if not isinstance(action, str) or action not in {"answer", "hint", "solution", "next"}:
            raise LearningError("invalid_action", "Thao tác học không được hỗ trợ.")
        if not isinstance(payload, dict):
            raise LearningError("invalid_input", "payload phải là object.")
        allowed = {"option_id", "reflection"} if action == "answer" else set()
        if set(payload) - allowed:
            raise LearningError("invalid_input", "payload chứa trường không được hỗ trợ.")
        if action == "answer":
            _text(payload.get("option_id"), "option_id", 64)
            _text(payload.get("reflection", ""), "reflection", 4000, empty=True)
        request = _json({"action": action, "payload": payload, "expected_revision": expected_revision})
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row(conn, owner_id, session_id)
            previous = conn.execute(
                "SELECT request_json, response_json FROM learning_events WHERE session_id = ? AND request_id = ?",
                (session_id, request_id),
            ).fetchone()
            if previous is not None:
                if previous["request_json"] != request:
                    raise LearningError("request_collision", "request_id đã được dùng cho yêu cầu khác.", 409)
                return json.loads(previous["response_json"])
            if row["revision"] != expected_revision:
                raise LearningError("revision_conflict", "Phiên học đã thay đổi. Hãy tải lại phiên trước khi tiếp tục.", 409)
            if row["revision"] >= MAX_ACTIONS_PER_SESSION:
                raise LearningError("action_limit", "Phiên này đã đạt giới hạn thao tác. Bạn có thể xuất dữ liệu hoặc tạo phiên mới.")
            state = json.loads(row["state_json"])
            if state["status"] != "active":
                raise LearningError("session_completed", "Phiên học đã kết thúc; hãy tạo phiên mới để thử lại.")
            index = state["current_index"]
            current = state["items"][index]
            authored_items = state["authored_items"]
            authored = authored_items[index]
            if action == "answer":
                if payload["option_id"] not in {option["id"] for option in authored["options"]}:
                    raise LearningError("invalid_option", "Lựa chọn không thuộc bài hiện tại.")
                assistance = _assistance(current)
                correct = payload["option_id"] == authored["correct_option"]
                if assistance == "none":
                    current["independent_result"] = "success" if correct else "failure"
                elif correct:
                    current["assisted_success"] = True
                current["attempts"] += 1
                current["selected_option"] = payload["option_id"]
                current["reflection"] = payload.get("reflection", "")
                current["feedback"] = {
                    "correct": correct, "heading": "Đúng với bài này" if correct else "Chưa đúng ở lần thử này",
                    "body": authored["explanation"] if correct else authored["hints"][0],
                    "evidence_lines": list(authored["evidence_lines"]) if correct else [],
                    "assistance": assistance,
                }
            elif action == "hint":
                if current["hint_count"] >= len(authored["hints"]):
                    raise LearningError("no_more_hints", "Bạn đã xem hết gợi ý của bài này.")
                current["hint_count"] += 1
            elif action == "solution":
                if current["solution_viewed"]:
                    raise LearningError("already_revealed", "Lời giải của bài này đã được mở.")
                current["solution_viewed"] = True
            elif action == "next":
                if not current["attempts"] and not current["solution_viewed"]:
                    raise LearningError("answer_required", "Hãy thử trả lời hoặc mở lời giải trước khi sang bài tiếp theo.")
                if index == len(authored_items) - 1:
                    state["status"] = "completed"
                else:
                    state["current_index"] += 1
            revision = row["revision"] + 1
            now = _timestamp()
            conn.execute(
                "UPDATE learning_sessions SET revision = ?, state_json = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
                (revision, _json(state), now, session_id, owner_id),
            )
            result = _public(self._row(conn, owner_id, session_id), state)
            event = self._event(action, dict(payload), revision, now, authored["id"], state)
            event["request_id"] = request_id
            if action == "answer":
                event["observation"] = {
                    "correct": correct, "assistance": assistance,
                    "independent_result": current["independent_result"], "reflection_assessed": False,
                }
            conn.execute(
                "INSERT INTO learning_events VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, revision, request_id, request, _json(event), _json(result)),
            )
            return result

    def export(self, owner_id: str, session_id: str) -> dict:
        owner_id = self._owner(owner_id)
        with self._connect() as conn:
            # Keep the session and its event history in one read snapshot.
            conn.execute("BEGIN")
            row = self._row(conn, owner_id, session_id)
            events = conn.execute(
                "SELECT event_json FROM learning_events WHERE session_id = ? ORDER BY revision", (session_id,),
            ).fetchall()
            return {
                "format_version": "1", "exported_at": _timestamp(), "session": _public(row),
                "events": [json.loads(event["event_json"]) for event in events],
                "assessment_note": "Chấm lựa chọn theo rubric soạn sẵn; không chạy Java và không chấm lời giải thích tự viết.",
            }

    def delete(self, owner_id: str, session_id: str) -> None:
        owner_id = self._owner(owner_id)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._row(conn, owner_id, session_id)
            conn.execute("DELETE FROM learning_sessions WHERE id = ? AND owner_id = ?", (session_id, owner_id))
