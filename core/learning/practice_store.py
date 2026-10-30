"""Durable owner-scoped generated practice; no model calls or mastery claims.

Generation requests are reserved once. Source snapshots and answer keys stay
pinned for the lifetime of a set, including after the original material changes.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import uuid

from .practice_generation import validate_prepared_practice, validate_practice_bundle
from .store import LearningError

MAX_PRACTICES = 30
MAX_GENERATION_REQUESTS = 1000
MAX_ACTIONS = 100
MAX_JSON_BYTES = 128 * 1024
GENERATION_LEASE_SECONDS = 180
MAX_REVISION = 2**53 - 1
_APPLICATION_ID = 0x43505231
_OWNER = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[a-f0-9]{32}\Z")
_UNIT = re.compile(r"unit-[a-f0-9]{64}\Z")
_REQUEST = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_STATUSES = {"generating", "draft", "active", "completed", "failed"}
_SCHEMA = (
    """CREATE TABLE practices (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_id TEXT NOT NULL,
        revision INTEGER NOT NULL, status TEXT NOT NULL,
        prepared_json TEXT NOT NULL, bundle_json TEXT, state_json TEXT NOT NULL,
        created_at REAL NOT NULL, updated_at REAL NOT NULL,
        UNIQUE(owner, request_id))""",
    "CREATE INDEX practice_owner_updated ON practices(owner, updated_at)",
    """CREATE TABLE generation_requests (
        owner TEXT NOT NULL, request_id TEXT NOT NULL, practice_id TEXT NOT NULL,
        fingerprint TEXT NOT NULL, PRIMARY KEY(owner, request_id))""",
    """CREATE TABLE practice_actions (
        practice_id TEXT NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
        request_id TEXT NOT NULL, request_json TEXT NOT NULL,
        PRIMARY KEY(practice_id, request_id))""",
)


def _error(code="practice_invalid", message="The practice request has invalid fields or values.", status=400):
    return LearningError(code, message, status)


def _storage():
    return _error("practice_storage_error", "Cannot read or save practice safely. Check the practice store.", 500)


def _missing():
    return _error("practice_not_found", "Practice not found.", 404)


def _conflict():
    return _error("practice_conflict", "Practice changed or this request ID was used for a different action. Reload and try again.", 409)


def _identity(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise _error()
    return value


def _revision(value):
    if type(value) is not int or not 0 <= value <= MAX_REVISION:
        raise _error()
    return value


def _text(value, maximum, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip())
            or any((ord(char) < 32 and char not in "\n\r\t") or 0xD800 <= ord(char) <= 0xDFFF for char in value)):
        raise _error()
    return value


def _json(value):
    try:
        result = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(result.encode("utf-8")) > MAX_JSON_BYTES:
            raise _error("practice_limit", "Practice data exceeds the storage limit.", 413)
        return result
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise _error() from None


def _strict_pairs(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate JSON key")
        data[key] = value
    return data


def _read_json(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
        raise _storage()
    return json.loads(raw, object_pairs_hook=_strict_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def _selection(value):
    if not isinstance(value, dict) or set(value) != {"collection_id", "unit_ids", "count"}:
        raise _error()
    _identity(value["collection_id"], _ID)
    units = value["unit_ids"]
    if (not isinstance(units, list) or not 1 <= len(units) <= 8 or type(value["count"]) is not int
            or value["count"] not in {3, 4, 5}):
        raise _error()
    for unit_id in units:
        _identity(unit_id, _UNIT)
    if len(set(units)) != len(units):
        raise _error()
    return {"collection_id": value["collection_id"], "unit_ids": sorted(units), "count": value["count"]}


def _fingerprint(selection):
    return hashlib.sha256(_json(_selection(selection)).encode("utf-8")).hexdigest()


def _prepared_selection(prepared):
    return {key: prepared["scope"][key] for key in ("collection_id", "unit_ids", "count")}


def _fresh_item():
    return {"hint_count": 0, "answer_reviewed": False, "solution_viewed": False,
            "attempts": 0, "selected_option": None, "reflection": "", "feedback": None,
            "first_try_correct": None, "correct_after_help": False}


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _resolved(path):
    # Windows can return the extended-path spelling while another connection
    # creates/removes a journal. Both spellings name the same confined path.
    value = str(path.resolve())
    if os.name == "nt":
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
    return Path(value)


class PracticeStore:
    def __init__(self, path=Path(".agent/learning/practice.sqlite3")):
        self.path = Path(path).absolute()

    def _check_path(self):
        if any(parent.is_symlink() for parent in self.path.parents):
            raise _storage()
        parent = _resolved(self.path.parent)
        for candidate in (self.path, *(Path(str(self.path) + suffix) for suffix in ("-journal", "-wal", "-shm"))):
            if candidate.is_symlink() or _resolved(candidate).parent != parent:
                raise _storage()
            try:
                mode = candidate.lstat().st_mode
            except FileNotFoundError:
                continue  # SQLite may remove a journal between these checks.
            if not stat.S_ISREG(mode):
                raise _storage()

    @contextmanager
    def _database(self, *, create=False):
        connection = None
        try:
            self._check_path()
            if not create and not self.path.exists():
                yield None
                return
            if create:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path.as_uri() + ("?mode=rwc" if create else "?mode=rw"),
                                         uri=True, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA secure_delete=ON")
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            application = connection.execute("PRAGMA application_id").fetchone()[0]
            if create and version == 0 and application == 0:
                if connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise _storage()
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")
                connection.execute("PRAGMA user_version=1")
            elif application != _APPLICATION_ID or version != 1:
                raise _storage()
            yield connection
            connection.commit()
        except (sqlite3.Error, OSError, ValueError, UnicodeError, OverflowError, RecursionError) as error:
            raise _storage() from error
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _row(connection, owner, practice_id):
        if connection is None:
            raise _missing()
        row = connection.execute("SELECT * FROM practices WHERE owner=? AND id=?", (owner, practice_id)).fetchone()
        if row is None:
            raise _missing()
        return row

    @staticmethod
    def _decode(row):
        try:
            _identity(row["id"], _ID)
            _identity(row["owner"], _OWNER)
            _identity(row["request_id"], _REQUEST)
            _revision(row["revision"])
            if row["status"] not in _STATUSES:
                raise _storage()
            for name in ("created_at", "updated_at"):
                if not isinstance(row[name], (int, float)) or not math.isfinite(row[name]) or row[name] < 0:
                    raise _storage()
                _iso(row[name])
            if row["updated_at"] < row["created_at"]:
                raise _storage()
            prepared = validate_prepared_practice(_read_json(row["prepared_json"]))
            bundle = None if row["bundle_json"] is None else validate_practice_bundle(_read_json(row["bundle_json"]), prepared)
            state = _read_json(row["state_json"])
            if not isinstance(state, dict) or set(state) != {"current_index", "items"} or not isinstance(state["items"], list):
                raise _storage()
            if type(state["current_index"]) is not int:
                raise _storage()
            if row["status"] in {"generating", "failed"}:
                if bundle is not None or state != {"current_index": 0, "items": []}:
                    raise _storage()
            else:
                if bundle is None or len(state["items"]) != len(bundle["questions"]) or not 0 <= state["current_index"] < len(state["items"]):
                    raise _storage()
                if row["status"] == "draft" and state["current_index"] != 0:
                    raise _storage()
                for index, item in enumerate(state["items"]):
                    if not isinstance(item, dict) or set(item) != set(_fresh_item()):
                        raise _storage()
                    if type(item["hint_count"]) is not int or not 0 <= item["hint_count"] <= 2:
                        raise _storage()
                    if type(item["attempts"]) is not int or not 0 <= item["attempts"] <= MAX_ACTIONS:
                        raise _storage()
                    if any(type(item[key]) is not bool for key in ("answer_reviewed", "solution_viewed", "correct_after_help")):
                        raise _storage()
                    if item["first_try_correct"] is not None and type(item["first_try_correct"]) is not bool:
                        raise _storage()
                    _text(item["reflection"], 1600, empty=True)
                    if item["selected_option"] not in (None, "a", "b", "c", "d"):
                        raise _storage()
                    feedback = item["feedback"]
                    if feedback is not None:
                        if not isinstance(feedback, dict) or set(feedback) != {"correct", "message"} or type(feedback["correct"]) is not bool:
                            raise _storage()
                        _text(feedback["message"], 200)
                    if item["attempts"] and (feedback is None or item["selected_option"] is None or item["first_try_correct"] is None):
                        raise _storage()
                    if not item["attempts"] and any(item[key] is not None for key in ("feedback", "selected_option", "first_try_correct")):
                        raise _storage()
                    if not item["attempts"] and (item["reflection"] or item["correct_after_help"]):
                        raise _storage()
                    if feedback is not None and feedback["correct"] != (item["selected_option"] == bundle["questions"][index]["correct_option"]):
                        raise _storage()
                    if item["attempts"] == 1 and item["first_try_correct"] != feedback["correct"]:
                        raise _storage()
                    if index > state["current_index"] and any(item[key] for key in ("attempts", "hint_count", "solution_viewed", "correct_after_help")):
                        raise _storage()
                    resolved = item["solution_viewed"] or bool(feedback and feedback["correct"])
                    if (index < state["current_index"] or row["status"] == "completed") and not resolved:
                        raise _storage()
                    if row["status"] == "draft" and any(item[key] for key in ("attempts", "hint_count", "solution_viewed", "correct_after_help")):
                        raise _storage()
                if row["status"] == "completed" and state["current_index"] != len(state["items"]) - 1:
                    raise _storage()
            _json({"prepared": prepared, "bundle": bundle, "state": state})
            return prepared, bundle, state
        except (LearningError, KeyError, TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as error:
            raise _storage() from error

    def _expire(self, connection, row):
        self._decode(row)
        if row["status"] == "generating" and row["created_at"] <= time.time() - GENERATION_LEASE_SECONDS:
            if row["revision"] == MAX_REVISION:
                raise _storage()
            connection.execute("UPDATE practices SET status='failed',revision=revision+1,updated_at=? WHERE id=?", (time.time(), row["id"]))
            row = self._row(connection, row["owner"], row["id"])
        return row

    @staticmethod
    def _public(row):
        prepared, bundle, state = PracticeStore._decode(row)
        questions = []
        if bundle:
            for question, saved in zip(bundle["questions"], state["items"]):
                revealed = saved["answer_reviewed"] or saved["solution_viewed"] or bool(saved["feedback"] and saved["feedback"]["correct"])
                public = {key: question[key] for key in ("id", "objective", "question", "options")}
                public.update({key: saved[key] for key in ("hint_count", "attempts", "selected_option", "reflection", "feedback",
                                                          "answer_reviewed", "solution_viewed", "first_try_correct")})
                public.update({"hints": question["hints"][:saved["hint_count"]], "total_hints": len(question["hints"]),
                               "answer": {key: question[key] for key in ("correct_option", "explanation", "evidence")} if revealed else None})
                questions.append(public)
        summary = {"answered_count": sum(item["attempts"] > 0 for item in state["items"]),
                   "first_try_correct": sum(item["first_try_correct"] is True for item in state["items"]),
                   "correct_after_help": sum(item["correct_after_help"] for item in state["items"]),
                   "answers_reviewed_before_start": sum(item["answer_reviewed"] for item in state["items"]),
                   "message": "Results compare selections with an AI-generated draft answer key, which may be wrong. First-try counts include reviewed answers and do not establish independent performance or mastery. Reflections are saved, not automatically graded."}
        return {"id": row["id"], "request_id": row["request_id"], "revision": row["revision"], "status": row["status"],
                "title": bundle["title"] if bundle else "Practice from " + prepared["scope"]["collection_title"],
                "scope": prepared["scope"], "provider": bundle["provider"] if bundle else None,
                "model": bundle["model"] if bundle else None,
                "error": {"code": "practice_generation_failed", "message": "Practice could not be generated. Create a new request to try again."} if row["status"] == "failed" else None,
                "questions": questions, "current_index": state["current_index"], "total_items": prepared["scope"]["count"],
                "summary": summary, "created_at": _iso(row["created_at"]), "updated_at": _iso(row["updated_at"])}

    def _lookup(self, connection, owner, request_id, fingerprint):
        if connection is None:
            return None
        previous = connection.execute("SELECT * FROM generation_requests WHERE owner=? AND request_id=?", (owner, request_id)).fetchone()
        if previous is None:
            return None
        try:
            _identity(previous["practice_id"], _ID)
            _identity(previous["fingerprint"], _OWNER)
        except LearningError as error:
            raise _storage() from error
        if previous["fingerprint"] != fingerprint:
            raise _conflict()
        row = self._row(connection, owner, previous["practice_id"])
        prepared, _, _ = self._decode(row)
        if row["request_id"] != request_id or _fingerprint(_prepared_selection(prepared)) != fingerprint:
            raise _storage()
        return self._public(self._expire(connection, row))

    def lookup_request(self, owner, request_id, selection):
        _identity(owner, _OWNER)
        _identity(request_id, _REQUEST)
        fingerprint = _fingerprint(selection)
        with self._database() as connection:
            return self._lookup(connection, owner, request_id, fingerprint)

    def reserve(self, owner, request_id, prepared):
        _identity(owner, _OWNER)
        _identity(request_id, _REQUEST)
        _json(prepared)
        prepared = validate_prepared_practice(prepared)
        fingerprint = _fingerprint(_prepared_selection(prepared))
        with self._database(create=True) as connection:
            previous = self._lookup(connection, owner, request_id, fingerprint)
            if previous is not None:
                return {"claimed": False, "practice": previous}
            if connection.execute("SELECT count(*) FROM practices WHERE owner=?", (owner,)).fetchone()[0] >= MAX_PRACTICES:
                raise _error("practice_limit", "Delete an old practice set before creating another.", 429)
            if connection.execute("SELECT count(*) FROM generation_requests WHERE owner=?", (owner,)).fetchone()[0] >= MAX_GENERATION_REQUESTS:
                raise _error("practice_limit", "This owner reached the generation-request history limit.", 429)
            practice_id, now = uuid.uuid4().hex, time.time()
            connection.execute("INSERT INTO practices VALUES (?,?,?,?,?,?,?,?,?,?)", (practice_id, owner, request_id, 0, "generating", _json(prepared), None, _json({"current_index": 0, "items": []}), now, now))
            connection.execute("INSERT INTO generation_requests VALUES (?,?,?,?)", (owner, request_id, practice_id, fingerprint))
            return {"claimed": True, "practice": self._public(self._row(connection, owner, practice_id))}

    def get(self, owner, practice_id):
        _identity(owner, _OWNER)
        _identity(practice_id, _ID)
        with self._database() as connection:
            return self._public(self._expire(connection, self._row(connection, owner, practice_id)))

    def list(self, owner):
        _identity(owner, _OWNER)
        with self._database() as connection:
            if connection is None:
                return []
            rows = connection.execute("SELECT * FROM practices WHERE owner=? ORDER BY updated_at DESC,id", (owner,)).fetchall()
            if len(rows) > MAX_PRACTICES:
                raise _storage()
            views = [self._public(self._expire(connection, row)) for row in rows]
            return sorted(({key: view[key] for key in ("id", "request_id", "revision", "status", "title", "scope", "error", "current_index", "total_items", "summary", "created_at", "updated_at")} for view in views), key=lambda view: (view["updated_at"], view["id"]), reverse=True)

    def finish(self, owner, practice_id, request_id, bundle):
        _identity(owner, _OWNER)
        _identity(practice_id, _ID)
        _identity(request_id, _REQUEST)
        with self._database() as connection:
            row = self._row(connection, owner, practice_id)
            if row["request_id"] != request_id:
                raise _conflict()
            row = self._expire(connection, row)
            if row["status"] == "failed":
                return self._public(row)
            prepared, existing, _ = self._decode(row)
            _json(bundle)
            bundle = validate_practice_bundle(bundle, prepared)
            if existing is not None:
                if existing != bundle:
                    raise _conflict()
                return self._public(row)
            state = {"current_index": 0, "items": [_fresh_item() for _ in bundle["questions"]]}
            _json({"prepared": prepared, "bundle": bundle, "state": state})
            connection.execute("UPDATE practices SET bundle_json=?,state_json=?,status='draft',revision=revision+1,updated_at=? WHERE id=?", (_json(bundle), _json(state), time.time(), practice_id))
            return self._public(self._row(connection, owner, practice_id))

    def fail(self, owner, practice_id, request_id):
        _identity(owner, _OWNER)
        _identity(practice_id, _ID)
        _identity(request_id, _REQUEST)
        with self._database() as connection:
            row = self._row(connection, owner, practice_id)
            self._decode(row)
            if row["request_id"] != request_id:
                raise _conflict()
            if row["status"] == "generating":
                connection.execute("UPDATE practices SET status='failed',revision=revision+1,updated_at=? WHERE id=?", (time.time(), practice_id))
            return self._public(self._row(connection, owner, practice_id))

    def delete(self, owner, practice_id):
        _identity(owner, _OWNER)
        _identity(practice_id, _ID)
        with self._database() as connection:
            row = self._expire(connection, self._row(connection, owner, practice_id))
            if row["status"] == "generating":
                raise _conflict()
            connection.execute("DELETE FROM practices WHERE owner=? AND id=?", (owner, practice_id))
            return {"id": practice_id, "deleted": True}

    def act(self, owner, practice_id, action, payload, expected_revision, request_id):
        _identity(owner, _OWNER)
        _identity(practice_id, _ID)
        _identity(request_id, _REQUEST)
        _revision(expected_revision)
        if not isinstance(action, str) or action not in {"review_answer", "start", "answer", "hint", "solution", "next"} or not isinstance(payload, dict):
            raise _error()
        keys = {"item_id", "option_id", "reflection"} if action == "answer" else ({"item_id"} if action in {"review_answer", "hint", "solution"} else set())
        if set(payload) != keys:
            raise _error()
        if "item_id" in payload and (not isinstance(payload["item_id"], str) or not re.fullmatch(r"q[1-5]", payload["item_id"])):
            raise _error()
        if action == "answer":
            if not isinstance(payload["option_id"], str) or payload["option_id"] not in {"a", "b", "c", "d"}:
                raise _error()
            _text(payload["reflection"], 1600, empty=True)
        request_json = _json({"action": action, "payload": payload, "expected_revision": expected_revision})
        with self._database() as connection:
            row = self._row(connection, owner, practice_id)
            prepared, bundle, state = self._decode(row)
            previous = connection.execute("SELECT request_json FROM practice_actions WHERE practice_id=? AND request_id=?", (practice_id, request_id)).fetchone()
            if previous is not None:
                if previous[0] != request_json:
                    raise _conflict()
                return self._public(row)
            if expected_revision != row["revision"]:
                raise _conflict()
            if row["revision"] == MAX_REVISION or connection.execute("SELECT count(*) FROM practice_actions WHERE practice_id=?", (practice_id,)).fetchone()[0] >= MAX_ACTIONS:
                raise _error("practice_limit", "This practice set reached its action limit.", 429)
            status = row["status"]
            if action == "review_answer" and status == "draft":
                index = next((index for index, question in enumerate(bundle["questions"]) if question["id"] == payload["item_id"]), None)
                if index is None:
                    raise _error()
                state["items"][index]["answer_reviewed"] = True
            elif action == "start" and status == "draft":
                status = "active"
            elif status == "active" and action in {"answer", "hint", "solution", "next"}:
                index = state["current_index"]
                question, saved = bundle["questions"][index], state["items"][index]
                if action != "next" and payload["item_id"] != question["id"]:
                    raise _conflict()
                if action == "answer":
                    correct = payload["option_id"] == question["correct_option"]
                    helped = saved["answer_reviewed"] or saved["solution_viewed"] or saved["hint_count"] > 0 or saved["attempts"] > 0
                    if saved["attempts"] == 0:
                        saved["first_try_correct"] = correct
                    saved.update({"attempts": saved["attempts"] + 1, "selected_option": payload["option_id"], "reflection": payload["reflection"],
                                  "feedback": {"correct": correct, "message": "Matches the generated answer key." if correct else "Does not match the generated answer key. Try again or use a hint."},
                                  "correct_after_help": saved["correct_after_help"] or (correct and helped)})
                elif action == "hint":
                    if saved["hint_count"] >= len(question["hints"]):
                        raise _conflict()
                    saved["hint_count"] += 1
                elif action == "solution":
                    saved["solution_viewed"] = True
                else:
                    if not (saved["feedback"] and saved["feedback"]["correct"]) and not saved["solution_viewed"]:
                        raise _conflict()
                    if index == len(state["items"]) - 1:
                        status = "completed"
                    else:
                        state["current_index"] += 1
            else:
                raise _conflict()
            _json({"prepared": prepared, "bundle": bundle, "state": state})
            connection.execute("INSERT INTO practice_actions VALUES (?,?,?)", (practice_id, request_id, request_json))
            connection.execute("UPDATE practices SET state_json=?,status=?,revision=revision+1,updated_at=? WHERE id=?", (_json(state), status, time.time(), practice_id))
            return self._public(self._row(connection, owner, practice_id))
