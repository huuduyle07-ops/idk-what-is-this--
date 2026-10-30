"""Durable learner-owned chat turns; model work happens outside transactions.

A request is reserved once before generation. Replaying a request never issues a
second generation, including after failure or lease expiry. This store contains
conversation text and retrieval snapshots, not source approval or mastery estimates.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import sqlite3
import time
import uuid

from .store import LearningError

MAX_CONVERSATIONS = 50
MAX_TURNS = 100
MAX_USER_CHARACTERS = 8000
MAX_ANSWER_CHARACTERS = 24000
MAX_CONTEXT_CHARACTERS = 48000
MAX_EVIDENCE_BYTES = 64 * 1024
TURN_LEASE_SECONDS = 120
_APPLICATION_ID = 0x43434831
_OWNER = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[a-f0-9]{32}\Z")
_REQUEST = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_ERROR = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_SCHEMA = (
    """CREATE TABLE conversations (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, create_request TEXT NOT NULL,
        title TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
        revision INTEGER NOT NULL, collection_id TEXT, collection_title TEXT,
        UNIQUE(owner, create_request))""",
    "CREATE INDEX owner_conversations ON conversations(owner, updated_at)",
    """CREATE TABLE turns (
        id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, request_id TEXT NOT NULL,
        text TEXT NOT NULL, answer TEXT, started_at REAL NOT NULL, finished_at REAL,
        status TEXT NOT NULL CHECK(status IN ('pending','completed','failed')),
        error_code TEXT, provider TEXT, model TEXT, evidence_json TEXT,
        FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
        UNIQUE(conversation_id, request_id))""",
    "CREATE INDEX conversation_turns ON turns(conversation_id, started_at)",
    "CREATE UNIQUE INDEX one_pending_turn ON turns(conversation_id) WHERE status='pending'",
)


def _now():
    return time.time()


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identity(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise LearningError("invalid_chat_input", "Định danh cuộc trò chuyện không hợp lệ.")
    return value


def _text(value, maximum):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(char) < 32 and char not in "\n\r\t" for char in value)):
        raise LearningError("invalid_chat_input", f"Nội dung cần từ 1–{maximum} ký tự hợp lệ.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise LearningError("invalid_chat_input", "Nội dung chứa ký tự Unicode không hợp lệ.") from None
    return value


def _missing():
    return LearningError("conversation_not_found", "Không tìm thấy cuộc trò chuyện.", 404)


def _storage_error():
    return LearningError("chat_storage_error", "Không đọc hoặc ghi được cuộc trò chuyện. Hãy kiểm tra kho lưu và thử lại.", 500)


def _evidence_json(evidence):
    if evidence is None:
        return None
    invalid = LearningError("invalid_chat_input", "Thông tin nguồn của câu trả lời không hợp lệ.")
    if (not isinstance(evidence, dict) or evidence.get("status") not in ("matched", "no_match")
            or not isinstance(evidence.get("sources"), list)
            or len(evidence["sources"]) > 32
            or any(not isinstance(source, dict) or not isinstance(source.get("citation_id"), str)
                   or not re.fullmatch(r"S[1-9][0-9]{0,3}", source["citation_id"])
                   for source in evidence["sources"])
            or any(not isinstance(evidence.get(key), list) or len(evidence[key]) > 128
                   or any(not isinstance(item, str) or len(item) > 80 for item in evidence[key])
                   for key in ("cited_ids", "invalid_citation_ids"))):
        raise invalid
    try:
        serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(serialized.encode("utf-8")) > MAX_EVIDENCE_BYTES:
            raise invalid
        return serialized
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise invalid from None


class ChatStore:
    def __init__(self, path: Path):
        self.path = Path(path).absolute()

    def _check_path(self):
        # The configured path is trusted; reject redirected parents, DB and
        # SQLite sidecars rather than following them outside that location.
        if any(parent.is_symlink() for parent in self.path.parents):
            raise _storage_error()
        parent = self.path.parent.resolve()
        for candidate in (self.path, *(Path(str(self.path) + suffix) for suffix in ("-journal", "-wal", "-shm"))):
            if (candidate.is_symlink() or candidate.resolve().parent != parent
                    or (candidate.exists() and not candidate.is_file())):
                raise _storage_error()

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
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            application = connection.execute("PRAGMA application_id").fetchone()[0]
            if create and version == 0 and application == 0:
                if connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise _storage_error()
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")
                connection.execute("PRAGMA user_version=2")
            elif application != _APPLICATION_ID or version not in {1, 2}:
                raise _storage_error()
            elif version == 1:
                # The transaction makes migration atomic across concurrent
                # requests and preserves every existing conversation and turn.
                connection.execute("ALTER TABLE conversations ADD COLUMN collection_id TEXT")
                connection.execute("ALTER TABLE conversations ADD COLUMN collection_title TEXT")
                connection.execute("ALTER TABLE turns ADD COLUMN evidence_json TEXT")
                connection.execute("PRAGMA user_version=2")
            yield connection
            connection.commit()
        except (sqlite3.Error, OSError, ValueError) as error:
            raise _storage_error() from error
        finally:
            if connection is not None:
                connection.close()  # Rolls back an unfinished transaction.

    @staticmethod
    def _conversation(connection, owner, conversation_id):
        if connection is None:
            raise _missing()
        row = connection.execute("SELECT * FROM conversations WHERE owner=? AND id=?", (owner, conversation_id)).fetchone()
        if row is None:
            raise _missing()
        return row

    @staticmethod
    def _expire(connection, conversation_id, now):
        changed = connection.execute(
            "UPDATE turns SET status='failed', error_code='chat_timeout', finished_at=? "
            "WHERE conversation_id=? AND status='pending' AND started_at<=?",
            (now, conversation_id, now - TURN_LEASE_SECONDS),
        ).rowcount
        if changed:
            connection.execute("UPDATE conversations SET revision=revision+1, updated_at=? WHERE id=?", (now, conversation_id))

    @staticmethod
    def _turns(connection, conversation_id):
        return connection.execute("SELECT * FROM turns WHERE conversation_id=? ORDER BY rowid", (conversation_id,)).fetchall()

    def _view(self, connection, owner, conversation_id):
        row = self._conversation(connection, owner, conversation_id)
        turns = self._turns(connection, conversation_id)
        messages = []
        for turn in turns:
            messages.append({"id": turn["id"] + "-user", "role": "user", "content": turn["text"],
                             "created_at": _iso(turn["started_at"]), "status": turn["status"]})
            if turn["status"] == "completed":
                messages.append({"id": turn["id"] + "-assistant", "role": "assistant", "content": turn["answer"],
                                 "created_at": _iso(turn["finished_at"]), "provider": turn["provider"], "model": turn["model"]})
                if turn["evidence_json"] is not None:
                    messages[-1]["evidence"] = json.loads(turn["evidence_json"])
        latest = turns[-1] if turns else None
        return {"id": row["id"], "title": row["title"], "created_at": _iso(row["created_at"]),
                "updated_at": _iso(row["updated_at"]), "revision": row["revision"], "messages": messages,
                "pending": {"request_id": latest["request_id"], "started_at": _iso(latest["started_at"])}
                if latest and latest["status"] == "pending" else None,
                "last_error": {"request_id": latest["request_id"], "code": latest["error_code"]}
                if latest and latest["status"] == "failed" else None,
                "collection": {"id": row["collection_id"], "title": row["collection_title"]} if row["collection_id"] else None,
                "grounding": "materials" if row["collection_id"] else "general"}

    def list(self, owner):
        _identity(owner, _OWNER)
        with self._database() as connection:
            if connection is None:
                return []
            ids = [row[0] for row in connection.execute("SELECT id FROM conversations WHERE owner=? ORDER BY updated_at DESC, id", (owner,))]
            result = []
            for conversation_id in ids:
                self._expire(connection, conversation_id, _now())
                view = self._view(connection, owner, conversation_id)
                result.append({key: view[key] for key in ("id", "title", "created_at", "updated_at", "revision", "pending", "collection", "grounding")}
                              | {"message_count": len(view["messages"])})
            return sorted(result, key=lambda item: (item["updated_at"], item["id"]), reverse=True)

    def create(self, owner, request_id, *, collection_id=None, collection_title=None):
        _identity(owner, _OWNER)
        _identity(request_id, _REQUEST)
        if collection_id is None:
            if collection_title is not None:
                raise LearningError("invalid_chat_input", "Tên bộ tài liệu cần đi kèm định danh bộ tài liệu.")
        else:
            _identity(collection_id, _ID)
            _text(collection_title, 200)
        with self._database(create=True) as connection:
            existing = connection.execute("SELECT id,collection_id,collection_title FROM conversations WHERE owner=? AND create_request=?", (owner, request_id)).fetchone()
            if existing:
                if (existing["collection_id"], existing["collection_title"]) != (collection_id, collection_title):
                    raise LearningError("chat_conflict", "Mã tạo hội thoại đã được dùng với bộ tài liệu khác.", 409)
                self._expire(connection, existing[0], _now())
                return self._view(connection, owner, existing[0])
            if connection.execute("SELECT count(*) FROM conversations WHERE owner=?", (owner,)).fetchone()[0] >= MAX_CONVERSATIONS:
                raise LearningError("chat_limit", "Đã đạt giới hạn cuộc trò chuyện. Hãy xóa một cuộc cũ để tạo mới.", 429)
            conversation_id, now = uuid.uuid4().hex, _now()
            connection.execute("INSERT INTO conversations(id,owner,create_request,title,created_at,updated_at,revision,collection_id,collection_title) "
                               "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                               (conversation_id, owner, request_id, "Cuộc trò chuyện mới", now, now, collection_id, collection_title))
            return self._view(connection, owner, conversation_id)

    def get(self, owner, conversation_id):
        _identity(owner, _OWNER)
        _identity(conversation_id, _ID)
        with self._database() as connection:
            self._conversation(connection, owner, conversation_id)
            self._expire(connection, conversation_id, _now())
            return self._view(connection, owner, conversation_id)

    def delete(self, owner, conversation_id):
        _identity(owner, _OWNER)
        _identity(conversation_id, _ID)
        with self._database() as connection:
            self._conversation(connection, owner, conversation_id)
            self._expire(connection, conversation_id, _now())
            if connection.execute("SELECT 1 FROM turns WHERE conversation_id=? AND status='pending'", (conversation_id,)).fetchone():
                raise LearningError("chat_busy", "Hãy đợi lượt trả lời kết thúc trước khi xóa cuộc trò chuyện.", 409)
            connection.execute("DELETE FROM conversations WHERE owner=? AND id=?", (owner, conversation_id))

    @staticmethod
    def _context(turns, current_text):
        pairs, size = [], len(current_text)
        for turn in reversed(turns):
            if turn["status"] != "completed":
                continue
            # Citation IDs are local to one retrieval snapshot. Sending old
            # labels into a fresh turn could silently attach them to new sources.
            answer = re.sub(r"\[S[1-9][0-9]*\]", "", turn["answer"]) if turn["evidence_json"] is not None else turn["answer"]
            length = len(turn["text"]) + len(answer)
            if size + length > MAX_CONTEXT_CHARACTERS:
                break
            pairs.append([{"role": "user", "content": turn["text"]}, {"role": "assistant", "content": answer}])
            size += length
        return [message for pair in reversed(pairs) for message in pair] + [{"role": "user", "content": current_text}]

    def begin_turn(self, owner, conversation_id, request_id, text, expected_revision):
        _identity(owner, _OWNER)
        _identity(conversation_id, _ID)
        _identity(request_id, _REQUEST)
        _text(text, MAX_USER_CHARACTERS)
        if type(expected_revision) is not int or not 0 <= expected_revision <= MAX_TURNS * 2:
            raise LearningError("invalid_chat_input", "Phiên bản cuộc trò chuyện không hợp lệ.")
        with self._database() as connection:
            self._conversation(connection, owner, conversation_id)
            self._expire(connection, conversation_id, _now())
            result = self._reserve(connection, owner, conversation_id, request_id, text, expected_revision)
        # A rejected new request must still commit the expired lease. No turn
        # was reserved when _reserve returns a validation/conflict error.
        if isinstance(result, LearningError):
            raise result
        return result

    def _reserve(self, connection, owner, conversation_id, request_id, text, expected_revision):
        turns = self._turns(connection, conversation_id)
        existing = next((turn for turn in turns if turn["request_id"] == request_id), None)
        if existing:
            if existing["text"] != text:
                return LearningError("chat_conflict", "Mã lượt gửi đã được dùng với nội dung khác.", 409)
            return {"claimed": False, "turn_id": existing["id"], "conversation": self._view(connection, owner, conversation_id), "messages": []}
        row = self._conversation(connection, owner, conversation_id)
        if any(turn["status"] == "pending" for turn in turns):
            return LearningError("chat_busy", "Cuộc trò chuyện đang có một lượt trả lời. Hãy chờ hoặc đọc lại trạng thái.", 409)
        if expected_revision != row["revision"]:
            return LearningError("chat_conflict", "Cuộc trò chuyện đã thay đổi. Hãy đọc lại trước khi gửi tiếp.", 409)
        if len(turns) >= MAX_TURNS:
            return LearningError("chat_limit", "Cuộc trò chuyện đã đạt giới hạn lượt gửi. Hãy tạo cuộc trò chuyện mới.", 429)
        turn_id, now = uuid.uuid4().hex, _now()
        connection.execute("INSERT INTO turns(id,conversation_id,request_id,text,started_at,status) VALUES (?,?,?,?,?,'pending')",
                           (turn_id, conversation_id, request_id, text, now))
        title = " ".join(text.split())[:80] if not turns else row["title"]
        connection.execute("UPDATE conversations SET title=?, revision=revision+1, updated_at=? WHERE id=?", (title, now, conversation_id))
        return {"claimed": True, "turn_id": turn_id, "conversation": self._view(connection, owner, conversation_id),
                "messages": self._context(turns, text)}

    def _settle(self, owner, conversation_id, turn_id, *, answer=None, provider=None, model=None, error_code=None, evidence_json=None):
        _identity(owner, _OWNER)
        _identity(conversation_id, _ID)
        _identity(turn_id, _ID)
        conflict = None
        with self._database() as connection:
            self._conversation(connection, owner, conversation_id)
            self._expire(connection, conversation_id, _now())
            turn = connection.execute("SELECT * FROM turns WHERE conversation_id=? AND id=?", (conversation_id, turn_id)).fetchone()
            if turn is None:
                raise _missing()
            if turn["status"] != "pending":
                if answer is None or (turn["status"] == "completed" and
                                      (turn["answer"], turn["provider"], turn["model"], turn["evidence_json"]) ==
                                      (answer, provider, model, evidence_json)):
                    return self._view(connection, owner, conversation_id)
                conflict = LearningError("chat_conflict", "Lượt trả lời này đã kết thúc; kết quả đến muộn không được ghi đè.", 409)
            else:
                now = _now()
                connection.execute("UPDATE turns SET status=?,answer=?,provider=?,model=?,error_code=?,finished_at=?,evidence_json=? WHERE id=?",
                                   ("completed" if answer is not None else "failed", answer, provider, model, error_code, now, evidence_json, turn_id))
                connection.execute("UPDATE conversations SET revision=revision+1,updated_at=? WHERE id=?", (now, conversation_id))
            view = self._view(connection, owner, conversation_id)
        if conflict:
            raise conflict
        return view

    def finish_turn(self, owner, conversation_id, turn_id, answer, provider, model, *, evidence=None):
        _text(answer, MAX_ANSWER_CHARACTERS)
        _text(provider, 80)
        _text(model, 200)
        return self._settle(owner, conversation_id, turn_id, answer=answer, provider=provider, model=model,
                            evidence_json=_evidence_json(evidence))

    def fail_turn(self, owner, conversation_id, turn_id, error_code):
        _identity(error_code, _ERROR)
        return self._settle(owner, conversation_id, turn_id, error_code=error_code)
