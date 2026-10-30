"""Local flashcards copied from completed practice; no model calls or grading.

Self-ratings schedule simple review intervals. They are observations, not mastery
scores. Answer/source snapshots survive edits or deletion of the original set.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import stat
import time
import unicodedata
import uuid

from .practice_store import _resolved
from .store import LearningError

MAX_DECKS = 30
MAX_CREATE_REQUESTS = 1000
MAX_ACTIONS = 500
MAX_JSON_BYTES = 128 * 1024
MAX_REVISION = 2**53 - 1
_APPLICATION_ID = 0x43464331
_OWNER = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[a-f0-9]{32}\Z")
_UNIT = re.compile(r"unit-[a-f0-9]{64}\Z")
_SOURCE = re.compile(r"sha256:[a-f0-9]{64}\Z")
_QUESTION = re.compile(r"q[1-5]\Z")
_REQUEST = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}\Z")
_SCHEMA = (
    """CREATE TABLE decks (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_id TEXT NOT NULL,
        revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL, state_json TEXT NOT NULL,
        created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(owner,request_id))""",
    "CREATE INDEX deck_owner_updated ON decks(owner,updated_at)",
    """CREATE TABLE create_requests (
        owner TEXT NOT NULL, request_id TEXT NOT NULL, deck_id TEXT NOT NULL,
        fingerprint TEXT NOT NULL, PRIMARY KEY(owner,request_id))""",
    """CREATE TABLE card_actions (
        deck_id TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
        request_id TEXT NOT NULL, request_json TEXT NOT NULL, event_json TEXT NOT NULL,
        PRIMARY KEY(deck_id,request_id))""",
)


def _error(code="flashcards_invalid", message="The flashcard request has invalid fields or values.", status=400):
    return LearningError(code, message, status)


def _storage():
    return _error("flashcards_storage_error", "Cannot read or save flashcards safely. Check the flashcard store.", 500)


def _missing():
    return _error("flashcards_not_found", "Flashcard deck not found.", 404)


def _conflict():
    return _error("flashcards_conflict", "Flashcards changed elsewhere. Read the saved version before continuing.", 409)


def _identity(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise _error()
    return value


def _text(value, maximum, *, single_line=False):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(unicodedata.category(c) == "Cs" or (ord(c) < 32 and (single_line or c not in "\n\r\t")) for c in value)):
        raise _error()
    return value


def _integer(value, maximum=MAX_REVISION):
    if type(value) is not int or not 0 <= value <= maximum:
        raise _error()
    return value


def _clock(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise _error()
    datetime.fromtimestamp(value, timezone.utc)
    return value


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value):
    try:
        result = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(result.encode("utf-8")) > MAX_JSON_BYTES:
            raise _error("flashcards_limit", "Flashcard data exceeds the storage limit.", 413)
        return result
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
    if not isinstance(value, dict) or set(value) != {"practice_id", "question_ids"}:
        raise _error()
    _identity(value["practice_id"], _ID)
    ids = value["question_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 5:
        raise _error()
    for item in ids:
        _identity(item, _QUESTION)
    if len(set(ids)) != len(ids):
        raise _error()
    return {"practice_id": value["practice_id"], "question_ids": sorted(ids)}


def _fingerprint(selection):
    return hashlib.sha256(_json(_selection(selection)).encode("utf-8")).hexdigest()


def _validate_snapshot(snapshot):
    if (not isinstance(snapshot, dict) or set(snapshot) != {"practice_id", "title", "scope", "provider", "model", "cards"}
            or snapshot["provider"] not in ("ollama", "gemini")):
        raise _error()
    _identity(snapshot["practice_id"], _ID)
    _identity(snapshot["model"], _MODEL)
    _text(snapshot["title"], 160)
    scope = snapshot["scope"]
    if not isinstance(scope, dict) or set(scope) != {"collection_id", "collection_title", "unit_ids", "count"}:
        raise _error()
    _identity(scope["collection_id"], _ID)
    _text(scope["collection_title"], 200, single_line=True)
    if type(scope["count"]) is not int or not 3 <= scope["count"] <= 5 or not isinstance(scope["unit_ids"], list) or not 1 <= len(scope["unit_ids"]) <= 8:
        raise _error()
    for uid in scope["unit_ids"]:
        _identity(uid, _UNIT)
    if len(set(scope["unit_ids"])) != len(scope["unit_ids"]):
        raise _error()
    cards = snapshot["cards"]
    if not isinstance(cards, list) or not 1 <= len(cards) <= 5:
        raise _error()
    seen = set()
    for card in cards:
        if not isinstance(card, dict) or set(card) != {"id", "front", "objective", "options", "answer", "needs_review_initial"}:
            raise _error()
        _identity(card["id"], _QUESTION)
        if card["id"] in seen or int(card["id"][1:]) > scope["count"] or type(card["needs_review_initial"]) is not bool:
            raise _error()
        seen.add(card["id"])
        _text(card["front"], 600)
        _text(card["objective"], 160)
        options = card["options"]
        if not isinstance(options, list) or len(options) != 4:
            raise _error()
        for index, option in enumerate(options):
            if not isinstance(option, dict) or set(option) != {"id", "text"} or option["id"] != "abcd"[index]:
                raise _error()
            _text(option["text"], 240)
        if len({" ".join(unicodedata.normalize("NFKC", option["text"]).split()).casefold() for option in options}) != 4:
            raise _error()
        answer = card["answer"]
        if (not isinstance(answer, dict) or set(answer) != {"text", "explanation", "evidence"}
                or answer["text"] not in [option["text"] for option in options]):
            raise _error()
        _text(answer["text"], 240)
        _text(answer["explanation"], 1000)
        evidence = answer["evidence"]
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= 2:
            raise _error()
        for source in evidence:
            expected = {"unit_id", "source_id", "source_name", "locator", "text", "origin"}
            if not isinstance(source, dict):
                raise _error()
            if source.get("origin") == "user_note":
                expected.add("annotation_revision")
                if type(source.get("annotation_revision")) is not int or source["annotation_revision"] < 1:
                    raise _error()
            elif source.get("origin") != "extracted":
                raise _error()
            if set(source) != expected:
                raise _error()
            _identity(source["unit_id"], _UNIT)
            _identity(source["source_id"], _SOURCE)
            if source["unit_id"] not in scope["unit_ids"]:
                raise _error()
            _text(source["source_name"], 500, single_line=True)
            _text(source["text"], 600)
            locator = source["locator"]
            if (not isinstance(locator, dict) or set(locator) != {"kind", "index"}
                    or locator["kind"] not in ("page", "slide", "paragraph", "table", "image")
                    or type(locator["index"]) is not int or locator["index"] < 1
                    or (source["origin"] == "user_note") != (locator["kind"] == "image")):
                raise _error()
    _json(snapshot)
    return deepcopy(snapshot)


def _snapshot(practice, question_ids):
    if not isinstance(practice, dict) or practice.get("status") != "completed":
        raise _error("flashcards_not_completed", "Complete the practice set before creating flashcards.", 409)
    selection = _selection({"practice_id": practice.get("id"), "question_ids": question_ids})
    questions = practice.get("questions")
    if not isinstance(questions, list):
        raise _error()
    by_id = {}
    for question in questions:
        if not isinstance(question, dict) or not isinstance(question.get("id"), str) or question["id"] in by_id:
            raise _error()
        by_id[question["id"]] = question
    cards = []
    for identifier in selection["question_ids"]:
        if identifier not in by_id:
            raise _error()
        question = by_id[identifier]
        if not {"question", "objective", "options", "answer", "first_try_correct", "hint_count", "solution_viewed", "answer_reviewed"} <= question.keys():
            raise _error()
        answer = question.get("answer")
        if not isinstance(answer, dict) or set(answer) != {"correct_option", "explanation", "evidence"}:
            raise _error()
        options = question.get("options")
        if not isinstance(options, list) or any(not isinstance(option, dict) for option in options):
            raise _error()
        chosen = next((option for option in options if option.get("id") == answer["correct_option"]), None)
        if chosen is None:
            raise _error()
        if (question.get("first_try_correct") is not None and type(question["first_try_correct"]) is not bool
                or type(question.get("hint_count")) is not int or not 0 <= question["hint_count"] <= 2
                or type(question.get("solution_viewed")) is not bool or type(question.get("answer_reviewed")) is not bool):
            raise _error()
        cards.append({"id": identifier, "front": question.get("question"), "objective": question.get("objective"),
                      "options": deepcopy(options), "answer": {"text": chosen.get("text"), "explanation": answer["explanation"], "evidence": deepcopy(answer["evidence"])},
                      "needs_review_initial": question["first_try_correct"] is False or question["hint_count"] > 0 or question["solution_viewed"] or question["answer_reviewed"]})
    return _validate_snapshot({"practice_id": practice["id"], "title": practice.get("title"), "scope": deepcopy(practice.get("scope")),
                               "provider": practice.get("provider"), "model": practice.get("model"), "cards": cards})


def _fresh_card(card, now):
    return {"revealed": False, "choices_viewed": False, "needs_review": card["needs_review_initial"],
            "due_at": now, "review_count": 0, "streak": 0, "last_rating": None}


class FlashcardStore:
    def __init__(self, path=Path(".agent/learning/flashcards.sqlite3")):
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
        row = connection.execute("SELECT * FROM decks WHERE owner=? AND id=?", (owner, identifier)).fetchone()
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
            _clock(row["created_at"])
            _clock(row["updated_at"])
            if row["updated_at"] < row["created_at"]:
                raise _storage()
            snapshot = _validate_snapshot(_read_json(row["snapshot_json"]))
            state = _read_json(row["state_json"])
            if not isinstance(state, dict) or set(state) != {"cards"} or not isinstance(state["cards"], dict) or set(state["cards"]) != {card["id"] for card in snapshot["cards"]}:
                raise _storage()
            for card in snapshot["cards"]:
                item = state["cards"][card["id"]]
                if not isinstance(item, dict) or set(item) != set(_fresh_card(card, row["created_at"])):
                    raise _storage()
                for key in ("revealed", "choices_viewed", "needs_review"):
                    if type(item[key]) is not bool:
                        raise _storage()
                _clock(item["due_at"])
                _integer(item["review_count"], MAX_ACTIONS)
                _integer(item["streak"], item["review_count"])
                if item["review_count"] == 0:
                    if item["last_rating"] is not None or item["streak"] != 0 or item["needs_review"] != card["needs_review_initial"] or item["due_at"] != row["created_at"]:
                        raise _storage()
                elif item["last_rating"] == "again":
                    if item["streak"] != 0 or not item["needs_review"]:
                        raise _storage()
                elif item["last_rating"] == "got_it":
                    if item["streak"] < 1 or item["needs_review"]:
                        raise _storage()
                else:
                    raise _storage()
            return snapshot, state
        except (LearningError, KeyError, TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as error:
            raise _storage() from error

    @staticmethod
    def _public(row):
        snapshot, state = FlashcardStore._decode(row)
        now = time.time()
        cards = []
        for card in snapshot["cards"]:
            saved = state["cards"][card["id"]]
            cards.append({"id": card["id"], "front": card["front"], "objective": card["objective"],
                          "choices": card["options"] if saved["choices_viewed"] else None,
                          "answer": card["answer"] if saved["revealed"] else None,
                          **{key: saved[key] for key in ("revealed", "choices_viewed", "needs_review", "review_count", "streak", "last_rating")},
                          "due_at": _iso(saved["due_at"]), "due": saved["due_at"] <= now})
        return {"id": row["id"], "request_id": row["request_id"], "revision": row["revision"],
                **{key: snapshot[key] for key in ("title", "practice_id", "scope", "provider", "model")},
                "cards": cards, "counts": {"total": len(cards), "due": sum(card["due"] for card in cards), "needs_review": sum(card["needs_review"] for card in cards)},
                "created_at": _iso(row["created_at"]), "updated_at": _iso(row["updated_at"])}

    def _lookup(self, connection, owner, request_id, fingerprint):
        if connection is None:
            return None
        previous = connection.execute("SELECT * FROM create_requests WHERE owner=? AND request_id=?", (owner, request_id)).fetchone()
        if previous is None:
            return None
        try:
            _identity(previous["deck_id"], _ID)
            _identity(previous["fingerprint"], _OWNER)
        except LearningError as error:
            raise _storage() from error
        if previous["fingerprint"] != fingerprint:
            raise _conflict()
        return self._public(self._row(connection, owner, previous["deck_id"]))

    def lookup_request(self, owner, request_id, selection):
        _identity(owner, _OWNER)
        _identity(request_id, _REQUEST)
        fingerprint = _fingerprint(selection)
        with self._database() as connection:
            return self._lookup(connection, owner, request_id, fingerprint)

    def create(self, owner, request_id, practice_public, question_ids):
        _identity(owner, _OWNER)
        _identity(request_id, _REQUEST)
        if not isinstance(practice_public, dict):
            raise _error()
        fingerprint = _fingerprint({"practice_id": practice_public.get("id"), "question_ids": question_ids})
        # A known request only needs the immutable selection, not a fresh copy
        # of a practice set that may already have been deleted.
        with self._database() as connection:
            existing = self._lookup(connection, owner, request_id, fingerprint)
            if existing is not None:
                return existing
        snapshot = _snapshot(practice_public, question_ids)
        with self._database(create=True) as connection:
            existing = self._lookup(connection, owner, request_id, fingerprint)
            if existing is not None:
                return existing
            if connection.execute("SELECT count(*) FROM decks WHERE owner=?", (owner,)).fetchone()[0] >= MAX_DECKS:
                raise _error("flashcards_limit", "Delete an old deck before creating another.", 429)
            if connection.execute("SELECT count(*) FROM create_requests WHERE owner=?", (owner,)).fetchone()[0] >= MAX_CREATE_REQUESTS:
                raise _error("flashcards_limit", "This owner reached the deck-request history limit.", 429)
            now, identifier = time.time(), uuid.uuid4().hex
            state = {"cards": {card["id"]: _fresh_card(card, now) for card in snapshot["cards"]}}
            _json({"snapshot": snapshot, "state": state})
            connection.execute("INSERT INTO decks VALUES (?,?,?,?,?,?,?,?)", (identifier, owner, request_id, 0, _json(snapshot), _json(state), now, now))
            connection.execute("INSERT INTO create_requests VALUES (?,?,?,?)", (owner, request_id, identifier, fingerprint))
            return self._public(self._row(connection, owner, identifier))

    def get(self, owner, deck_id):
        _identity(owner, _OWNER)
        _identity(deck_id, _ID)
        with self._database() as connection:
            return self._public(self._row(connection, owner, deck_id))

    def list(self, owner):
        _identity(owner, _OWNER)
        with self._database() as connection:
            if connection is None:
                return []
            rows = connection.execute("SELECT * FROM decks WHERE owner=? ORDER BY updated_at DESC,id", (owner,)).fetchall()
            if len(rows) > MAX_DECKS:
                raise _storage()
            views = [self._public(row) for row in rows]
            return [{key: view[key] for key in ("id", "revision", "title", "practice_id", "scope", "counts", "created_at", "updated_at")} for view in views]

    def delete(self, owner, deck_id):
        _identity(owner, _OWNER)
        _identity(deck_id, _ID)
        with self._database() as connection:
            row = self._row(connection, owner, deck_id)
            self._decode(row)
            connection.execute("DELETE FROM decks WHERE owner=? AND id=?", (owner, deck_id))
            return {"id": deck_id, "deleted": True}

    def act(self, owner, deck_id, action, payload, expected_revision, request_id):
        _identity(owner, _OWNER)
        _identity(deck_id, _ID)
        _identity(request_id, _REQUEST)
        _integer(expected_revision)
        if not isinstance(action, str) or action not in {"reveal", "choices", "hide", "rate"} or not isinstance(payload, dict):
            raise _error()
        if set(payload) != ({"card_id", "rating"} if action == "rate" else {"card_id"}):
            raise _error()
        _identity(payload["card_id"], _QUESTION)
        if action == "rate" and payload["rating"] not in ("again", "got_it"):
            raise _error()
        request_json = _json({"action": action, "payload": payload, "expected_revision": expected_revision})
        with self._database() as connection:
            row = self._row(connection, owner, deck_id)
            snapshot, state = self._decode(row)
            previous = connection.execute("SELECT request_json FROM card_actions WHERE deck_id=? AND request_id=?", (deck_id, request_id)).fetchone()
            if previous is not None:
                if previous[0] != request_json:
                    raise _conflict()
                return self._public(row)
            if row["revision"] != expected_revision:
                raise _conflict()
            if row["revision"] == MAX_REVISION or connection.execute("SELECT count(*) FROM card_actions WHERE deck_id=?", (deck_id,)).fetchone()[0] >= MAX_ACTIONS:
                raise _error("flashcards_limit", "This deck reached its action limit.", 429)
            if payload["card_id"] not in state["cards"]:
                raise _error()
            saved = state["cards"][payload["card_id"]]
            now = time.time()
            event = {"action": action, "card_id": payload["card_id"], "at": _iso(now),
                     "revealed_before": saved["revealed"], "choices_viewed": saved["choices_viewed"]}
            if action == "reveal":
                saved["revealed"] = True
            elif action == "choices":
                saved["choices_viewed"] = True
            elif action == "hide":
                saved.update(revealed=False, choices_viewed=False)
            else:
                if not saved["revealed"]:
                    raise _conflict()
                rating = payload["rating"]
                event.update(rating=rating, previous_due_at=_iso(saved["due_at"]))
                saved["review_count"] += 1
                saved["last_rating"] = rating
                saved["needs_review"] = rating == "again"
                if rating == "again":
                    saved["streak"] = 0
                    saved["due_at"] = now + 10 * 60
                else:
                    saved["streak"] += 1
                    days = 1 if saved["streak"] == 1 else 3 if saved["streak"] == 2 else 7
                    saved["due_at"] = now + days * 24 * 60 * 60
                saved.update(revealed=False, choices_viewed=False)
                event["next_due_at"] = _iso(saved["due_at"])
            _json({"snapshot": snapshot, "state": state})
            connection.execute("INSERT INTO card_actions VALUES (?,?,?,?)", (deck_id, request_id, request_json, _json(event)))
            connection.execute("UPDATE decks SET state_json=?,revision=revision+1,updated_at=? WHERE id=?", (_json(state), now, deck_id))
            return self._public(self._row(connection, owner, deck_id))
