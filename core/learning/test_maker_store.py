"""Owner-scoped seeded tests, saved work and explicit deterministic submission.

Draft reads never expose the answer key. Essay submissions stay pending human
review and never enter the automatic score. No model, network or execution tools.
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

from .store import LearningError
from .test_maker import catalog, build_test, validate_test, public_question, grade_question, validate_answer

MAX_TESTS = 30
MAX_CREATE_REQUESTS = 1000
MAX_ACTIONS = 200
MAX_JSON_BYTES = 128 * 1024
MAX_REVISION = 2**53 - 1
_APPLICATION_ID = 0x43544D31
_OWNER = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[a-f0-9]{32}\Z")
_REQUEST = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_SCHEMA = (
    """CREATE TABLE tests (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_id TEXT NOT NULL,
        revision INTEGER NOT NULL, status TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, answers_json TEXT NOT NULL, results_json TEXT,
        created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(owner,request_id))""",
    "CREATE INDEX test_owner_updated ON tests(owner,updated_at)",
    """CREATE TABLE create_requests (
        owner TEXT NOT NULL, request_id TEXT NOT NULL, test_id TEXT NOT NULL,
        fingerprint TEXT NOT NULL, PRIMARY KEY(owner,request_id))""",
    """CREATE TABLE test_actions (
        test_id TEXT NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
        request_id TEXT NOT NULL, request_json TEXT NOT NULL,
        PRIMARY KEY(test_id,request_id))""",
)


def _error(code="test_maker_invalid", message="The test request has invalid fields or values.", status=400):
    return LearningError(code, message, status)


def _storage():
    return _error("test_maker_storage_error", "Cannot read or save tests safely. Check the test store.", 500)


def _missing():
    return _error("test_maker_not_found", "Test not found.", 404)


def _conflict():
    return _error("test_maker_conflict", "The test changed or this request ID was reused. Read the saved version before continuing.", 409)


def _identity(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise _error()
    return value


def _integer(value, maximum=MAX_REVISION):
    if type(value) is not int or not 0 <= value <= maximum:
        raise _error()
    return value


def _timestamp(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise _storage()
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(raw.encode("utf-8")) > MAX_JSON_BYTES:
            raise _error("test_maker_limit", "The saved test exceeds its size limit.", 413)
        return raw
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise _error() from None


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _read_json(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
        raise _storage()
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def _selection(value):
    if not isinstance(value, dict) or set(value) != {"topic_ids", "seed"}:
        raise _error()
    _integer(value["seed"], 2**31 - 1)
    topics = value["topic_ids"]
    ordered = [topic["id"] for topic in catalog()]
    allowed = set(ordered)
    if (not isinstance(topics, list) or not 1 <= len(topics) <= len(allowed)
            or any(not isinstance(topic, str) or topic not in allowed for topic in topics)
            or len(set(topics)) != len(topics)):
        raise _error()
    return {"topic_ids": [topic for topic in ordered if topic in topics], "seed": value["seed"]}


def _fingerprint(selection):
    return hashlib.sha256(_json(_selection(selection)).encode("utf-8")).hexdigest()


def _answers(snapshot, value):
    if not isinstance(value, dict):
        raise _error()
    questions = {q["id"]: q for q in snapshot["questions"]}
    if set(value) - questions.keys():
        raise _error()
    return {identifier: validate_answer(questions[identifier], answer, allow_empty=True)
            for identifier, answer in sorted(value.items())}


def _results(snapshot, answers):
    items = [grade_question(q, answers.get(q["id"])) for q in snapshot["questions"]]
    automatic = [item for q, item in zip(snapshot["questions"], items) if q["kind"] != "essay"]
    essays = [item for q, item in zip(snapshot["questions"], items) if q["kind"] == "essay"]
    return {"items": items,
            "auto": {"earned": sum(item["earned"] for item in automatic), "possible": sum(item["possible"] for item in automatic)},
            "essay": {"answered": sum(item["status"] == "pending_review" for item in essays),
                      "pending": sum(item["status"] == "pending_review" for item in essays), "total": len(essays)},
            "message": "Automatic points cover numeric, matrix and diagram questions only. Essay answers require human review; the automatic score is not an overall grade or a mastery estimate."}


def _resolved(path):
    value = str(path.resolve())
    if os.name == "nt":
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
    return Path(value)


class TestMakerStore:
    def __init__(self, path=Path(".agent/learning/test_maker.sqlite3")):
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
                continue
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
            connection = sqlite3.connect(self.path.as_uri() + ("?mode=rwc" if create else "?mode=rw"), uri=True, timeout=5, isolation_level=None)
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
            elif version != 1 or application != _APPLICATION_ID:
                raise _storage()
            yield connection
            connection.commit()
        except (sqlite3.Error, OSError, ValueError, TypeError, UnicodeError, OverflowError, RecursionError) as error:
            raise _storage() from error
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _row(connection, owner, identifier):
        if connection is None:
            raise _missing()
        row = connection.execute("SELECT * FROM tests WHERE owner=? AND id=?", (owner, identifier)).fetchone()
        if row is None:
            raise _missing()
        return row

    @staticmethod
    def _decode(row):
        try:
            _identity(row["id"], _ID)
            _identity(row["owner"], _OWNER)
            _identity(row["request_id"], _REQUEST)
            _integer(row["revision"])
            _timestamp(row["created_at"])
            _timestamp(row["updated_at"])
            if row["status"] not in ("active", "submitted") or row["updated_at"] < row["created_at"]:
                raise _storage()
            snapshot = validate_test(_read_json(row["snapshot_json"]))
            raw_answers = _read_json(row["answers_json"])
            answers = _answers(snapshot, raw_answers)
            if _json(answers) != _json(raw_answers):
                raise _storage()
            results = None if row["results_json"] is None else _read_json(row["results_json"])
            if row["status"] == "active":
                if results is not None:
                    raise _storage()
            elif _json(results) != _json(_results(snapshot, answers)):
                raise _storage()
            return snapshot, answers, results
        except (LearningError, KeyError, TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as error:
            raise _storage() from error

    @staticmethod
    def _public(row):
        snapshot, answers, results = TestMakerStore._decode(row)
        return {"id": row["id"], "request_id": row["request_id"], "revision": row["revision"], "status": row["status"],
                **{key: snapshot[key] for key in ("title", "seed", "version", "topics")},
                "questions": [public_question(q) for q in snapshot["questions"]], "answers": answers, "results": results,
                "created_at": _timestamp(row["created_at"]), "updated_at": _timestamp(row["updated_at"])}

    def _lookup(self, connection, owner, request_id, fingerprint):
        if connection is None:
            return None
        previous = connection.execute("SELECT * FROM create_requests WHERE owner=? AND request_id=?", (owner, request_id)).fetchone()
        if previous is None:
            return None
        try:
            _identity(previous["test_id"], _ID)
            _identity(previous["fingerprint"], _OWNER)
        except LearningError as error:
            raise _storage() from error
        if previous["fingerprint"] != fingerprint:
            raise _conflict()
        return self._public(self._row(connection, owner, previous["test_id"]))

    def lookup_request(self, owner, request_id, selection):
        _identity(owner, _OWNER)
        _identity(request_id, _REQUEST)
        fingerprint = _fingerprint(selection)
        with self._database() as connection:
            return self._lookup(connection, owner, request_id, fingerprint)

    def create(self, owner, request_id, topic_ids, seed):
        _identity(owner, _OWNER)
        _identity(request_id, _REQUEST)
        selected = _selection({"topic_ids": topic_ids, "seed": seed})
        fingerprint = _fingerprint(selected)
        with self._database() as connection:
            existing = self._lookup(connection, owner, request_id, fingerprint)
            if existing is not None:
                return existing
        snapshot = validate_test(build_test(selected["topic_ids"], seed))
        _json(snapshot)
        with self._database(create=True) as connection:
            existing = self._lookup(connection, owner, request_id, fingerprint)
            if existing is not None:
                return existing
            if connection.execute("SELECT count(*) FROM tests WHERE owner=?", (owner,)).fetchone()[0] >= MAX_TESTS:
                raise _error("test_maker_limit", "Delete an old test before creating another.", 429)
            if connection.execute("SELECT count(*) FROM create_requests WHERE owner=?", (owner,)).fetchone()[0] >= MAX_CREATE_REQUESTS:
                raise _error("test_maker_limit", "This owner reached the test-request history limit.", 429)
            identifier, now = uuid.uuid4().hex, time.time()
            connection.execute("INSERT INTO tests VALUES (?,?,?,?,?,?,?,?,?,?)", (identifier, owner, request_id, 0, "active", _json(snapshot), _json({}), None, now, now))
            connection.execute("INSERT INTO create_requests VALUES (?,?,?,?)", (owner, request_id, identifier, fingerprint))
            return self._public(self._row(connection, owner, identifier))

    def get(self, owner, test_id):
        _identity(owner, _OWNER)
        _identity(test_id, _ID)
        with self._database() as connection:
            return self._public(self._row(connection, owner, test_id))

    def list(self, owner):
        _identity(owner, _OWNER)
        with self._database() as connection:
            if connection is None:
                return []
            rows = connection.execute("SELECT * FROM tests WHERE owner=? ORDER BY updated_at DESC,id", (owner,)).fetchall()
            if len(rows) > MAX_TESTS:
                raise _storage()
            views = [self._public(row) for row in rows]
            return [{**{key: view[key] for key in ("id", "revision", "status", "title", "seed", "version", "topics", "created_at", "updated_at")},
                     "question_count": len(view["questions"])} for view in views]

    def delete(self, owner, test_id):
        _identity(owner, _OWNER)
        _identity(test_id, _ID)
        with self._database() as connection:
            row = self._row(connection, owner, test_id)
            self._decode(row)
            connection.execute("DELETE FROM tests WHERE owner=? AND id=?", (owner, test_id))
            return {"id": test_id, "deleted": True}

    def act(self, owner, test_id, action, payload, expected_revision, request_id):
        _identity(owner, _OWNER)
        _identity(test_id, _ID)
        _identity(request_id, _REQUEST)
        _integer(expected_revision)
        if not isinstance(action, str) or action not in {"save", "submit"} or not isinstance(payload, dict) or set(payload) != {"answers"}:
            raise _error()
        request_json = _json({"action": action, "payload": payload, "expected_revision": expected_revision})
        with self._database() as connection:
            row = self._row(connection, owner, test_id)
            snapshot, saved, _ = self._decode(row)
            previous = connection.execute("SELECT request_json FROM test_actions WHERE test_id=? AND request_id=?", (test_id, request_id)).fetchone()
            if previous is not None:
                if previous[0] != request_json:
                    raise _conflict()
                return self._public(row)
            if row["revision"] != expected_revision or row["status"] != "active":
                raise _conflict()
            if row["revision"] == MAX_REVISION or connection.execute("SELECT count(*) FROM test_actions WHERE test_id=?", (test_id,)).fetchone()[0] >= MAX_ACTIONS:
                raise _error("test_maker_limit", "This test reached its action limit.", 429)
            answers = {**saved, **_answers(snapshot, payload["answers"])}
            results = _results(snapshot, answers) if action == "submit" else None
            _json({"snapshot": snapshot, "answers": answers, "results": results})
            connection.execute("INSERT INTO test_actions VALUES (?,?,?)", (test_id, request_id, request_json))
            connection.execute("UPDATE tests SET answers_json=?,results_json=?,status=?,revision=revision+1,updated_at=? WHERE id=?", (
                _json(answers), None if results is None else _json(results), "submitted" if action == "submit" else "active", time.time(), test_id))
            return self._public(self._row(connection, owner, test_id))
