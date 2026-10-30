"""Chat persistence, request ownership and generation-reservation behavior."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from copy import deepcopy

import pytest

from core.learning import chat_store as module
from core.learning.chat_store import ChatStore
from core.learning.store import LearningError

OWNER = "a" * 64
OTHER = "b" * 64
CREATE = "create-request-0001"
REQUEST = "message-request-0001"
COLLECTION = "c" * 32


def source_evidence():
    return {"status": "matched", "sources": [{
        "citation_id": "S1", "collection_id": COLLECTION,
        "source_id": "sha256:" + "d" * 64, "unit_id": "unit-" + "e" * 64,
        "title": "Java inheritance.pdf", "locator": {"kind": "page", "index": 3},
        "text": "A subclass can override an inherited method.", "start_char": 0, "end_char": 45,
        "origin": "extracted", "warnings": [],
    }], "cited_ids": ["S1"], "invalid_citation_ids": []}


@pytest.fixture
def store(tmp_path):
    return ChatStore(tmp_path / "chat" / "conversations.sqlite3")


def assert_error(code, call, *args):
    with pytest.raises(LearningError) as error:
        call(*args)
    assert error.value.code == code
    return error.value


def start(store, *, owner=OWNER, text="Giải thích kế thừa", request=REQUEST, conversation=None, revision=0):
    conversation = conversation or store.create(owner, CREATE)
    return store.begin_turn(owner, conversation["id"], request, text, revision)


def finish(store, claim, answer="Lớp con kế thừa hành vi từ lớp cha.", owner=OWNER):
    return store.finish_turn(owner, claim["conversation"]["id"], claim["turn_id"], answer, "local", "test-model")


def test_empty_reads_do_not_create_storage(store):
    assert store.list(OWNER) == []
    assert_error("conversation_not_found", store.get, OWNER, "c" * 32)
    assert not store.path.parent.exists()


def test_creation_is_idempotent_durable_and_owner_scoped(store):
    first = store.create(OWNER, CREATE)
    assert first["revision"] == 0 and first["messages"] == [] and first["grounding"] == "general"
    assert first["pending"] is None and first["last_error"] is None
    assert store.create(OWNER, CREATE) == first
    assert ChatStore(store.path).get(OWNER, first["id"]) == first
    second = store.create(OTHER, CREATE)
    assert second["id"] != first["id"]
    assert [row["id"] for row in store.list(OWNER)] == [first["id"]]
    for call, args in ((store.get, (OTHER, first["id"])), (store.delete, (OTHER, first["id"])),
                       (store.begin_turn, (OTHER, first["id"], REQUEST, "private?", 0))):
        assert_error("conversation_not_found", call, *args)


def test_turn_is_reserved_once_and_completed_exchange_is_reused(store):
    claim = start(store)
    conversation_id = claim["conversation"]["id"]
    assert claim["claimed"] and claim["conversation"]["revision"] == 1
    assert claim["messages"] == [{"role": "user", "content": "Giải thích kế thừa"}]
    assert claim["conversation"]["pending"]["request_id"] == REQUEST
    retry = start(store, conversation=claim["conversation"])
    assert retry["claimed"] is False and retry["turn_id"] == claim["turn_id"] and retry["messages"] == []
    completed = finish(store, claim)
    assert completed["revision"] == 2 and completed["pending"] is None
    assert [message["role"] for message in completed["messages"]] == ["user", "assistant"]
    assert completed["messages"][1]["provider"] == "local"
    assert finish(store, claim) == completed
    replay = start(store, conversation=completed)
    assert not replay["claimed"] and replay["conversation"] == completed
    followup = start(store, conversation=completed, text="Cho ví dụ Java", request="message-request-0002", revision=2)
    assert followup["messages"] == [
        {"role": "user", "content": "Giải thích kế thừa"},
        {"role": "assistant", "content": "Lớp con kế thừa hành vi từ lớp cha."},
        {"role": "user", "content": "Cho ví dụ Java"},
    ]
    assert ChatStore(store.path).get(OWNER, conversation_id)["revision"] == 3


def test_request_collision_stale_tab_busy_and_owner_cannot_overwrite(store):
    claim = start(store)
    cid = claim["conversation"]["id"]
    assert_error("chat_conflict", store.begin_turn, OWNER, cid, REQUEST, "changed", 0)
    assert_error("chat_busy", store.begin_turn, OWNER, cid, "message-request-0002", "second", 1)
    assert_error("conversation_not_found", store.finish_turn, OTHER, cid, claim["turn_id"], "answer", "local", "model")
    completed = finish(store, claim)
    assert_error("chat_conflict", store.begin_turn, OWNER, cid, "message-request-0002", "stale", 0)
    assert_error("chat_conflict", store.finish_turn, OWNER, cid, claim["turn_id"], "different answer", "local", "model")
    assert store.get(OWNER, cid) == completed


def test_concurrent_identical_requests_claim_generation_only_once(store):
    conversation = store.create(OWNER, CREATE)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: start(store, conversation=conversation), range(2)))
    assert sorted(result["claimed"] for result in results) == [False, True]
    assert len({result["turn_id"] for result in results}) == 1
    assert len(store.get(OWNER, conversation["id"])["messages"]) == 1


def test_failed_turn_stays_visible_but_is_not_sent_as_history_or_retried(store):
    first = start(store)
    complete = finish(store, first)
    failed = start(store, conversation=complete, text="question that failed", request="message-request-0002", revision=2)
    cid = complete["id"]
    view = store.fail_turn(OWNER, cid, failed["turn_id"], "provider_timeout")
    assert view["revision"] == 4 and view["messages"][-1]["content"] == "question that failed"
    assert view["last_error"] == {"request_id": "message-request-0002", "code": "provider_timeout"}
    replay = store.begin_turn(OWNER, cid, "message-request-0002", "question that failed", 2)
    assert not replay["claimed"] and replay["conversation"] == view
    assert store.fail_turn(OWNER, cid, failed["turn_id"], "provider_timeout") == view
    third = store.begin_turn(OWNER, cid, "message-request-0003", "explicit resend", 4)
    assert [message["content"] for message in third["messages"]] == [
        "Giải thích kế thừa", "Lớp con kế thừa hành vi từ lớp cha.", "explicit resend",
    ]
    assert third["conversation"]["last_error"] is None


def test_expiry_releases_pending_and_late_answer_cannot_override_new_turn(store, monkeypatch):
    monkeypatch.setattr(module, "_now", lambda: 1000.0)
    old = start(store)
    cid = old["conversation"]["id"]
    monkeypatch.setattr(module, "_now", lambda: 1120.0)
    expired = store.get(OWNER, cid)
    assert expired["revision"] == 2 and expired["pending"] is None
    assert expired["last_error"]["code"] == "chat_timeout"
    assert not store.begin_turn(OWNER, cid, REQUEST, "Giải thích kế thừa", 0)["claimed"]
    current = store.begin_turn(OWNER, cid, "message-request-0002", "new question", 2)
    assert_error("chat_conflict", finish, store, old)
    assert store.get(OWNER, cid)["pending"]["request_id"] == "message-request-0002"
    store.fail_turn(OWNER, cid, old["turn_id"], "provider_timeout")
    assert store.get(OWNER, cid)["pending"]["request_id"] == "message-request-0002"
    assert finish(store, current)["revision"] == 4


def test_pending_delete_is_blocked_then_cascades_all_turns(store):
    claim = start(store)
    cid = claim["conversation"]["id"]
    assert_error("chat_busy", store.delete, OWNER, cid)
    finish(store, claim)
    store.delete(OWNER, cid)
    assert store.list(OWNER) == []
    assert_error("conversation_not_found", store.get, OWNER, cid)
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT count(*) FROM turns").fetchone()[0] == 0


@pytest.mark.parametrize("action", ["begin", "finish"])
def test_expiry_is_persisted_even_when_incoming_request_is_rejected(store, monkeypatch, action):
    monkeypatch.setattr(module, "_now", lambda: 1000.0)
    claim = start(store)
    monkeypatch.setattr(module, "_now", lambda: 1120.0)
    if action == "begin":
        assert_error("chat_conflict", store.begin_turn, OWNER, claim["conversation"]["id"], "message-request-0002", "new", 1)
    else:
        assert_error("chat_conflict", finish, store, claim)
    # Inspect the persisted state without invoking get()'s own expiry step.
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT status,error_code FROM turns").fetchone() == ("failed", "chat_timeout")
        assert connection.execute("SELECT revision FROM conversations").fetchone()[0] == 2


def test_context_uses_newest_whole_pairs_and_stays_bounded(store):
    view = store.create(OWNER, CREATE)
    for index in range(3):
        claim = store.begin_turn(OWNER, view["id"], f"message-request-{index:04d}", str(index) * 8000, view["revision"])
        view = finish(store, claim, answer=str(index) * 24000)
    claim = store.begin_turn(OWNER, view["id"], "message-request-next", "next" * 2000, view["revision"])
    assert [message["role"] for message in claim["messages"]] == ["user", "assistant", "user"]
    assert claim["messages"][0]["content"] == "2" * 8000
    assert sum(len(message["content"]) for message in claim["messages"]) == 40000
    assert len(claim["conversation"]["messages"]) == 7  # Stored history remains complete.


def test_conversation_and_turn_quotas_allow_replays_without_extra_rows(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_CONVERSATIONS", 1)
    monkeypatch.setattr(module, "MAX_TURNS", 1)
    claim = start(store)
    complete = finish(store, claim)
    assert_error("chat_limit", store.create, OWNER, "create-request-0002")
    assert store.create(OWNER, CREATE) == complete
    assert_error("chat_limit", store.begin_turn, OWNER, complete["id"], "message-request-0002", "extra", 2)
    assert not start(store, conversation=complete)["claimed"]
    assert len(store.list(OWNER)) == 1


@pytest.mark.parametrize("text,revision", [(None, 0), (" ", 0), ("a" * 8001, 0), ("\ud800", 0), ("a\x00b", 0), ("valid", True), ("valid", -1)])
def test_invalid_user_input_does_not_reserve_turn(store, text, revision):
    view = store.create(OWNER, CREATE)
    assert_error("invalid_chat_input", store.begin_turn, OWNER, view["id"], REQUEST, text, revision)
    assert store.get(OWNER, view["id"]) == view


@pytest.mark.parametrize("owner,request_id", [("../x", CREATE), (OWNER, "short"), (OWNER, "á" * 20), (OWNER, "x" * 129)])
def test_invalid_identity_does_not_create_storage(store, owner, request_id):
    assert_error("invalid_chat_input", store.create, owner, request_id)
    assert not store.path.exists()


@pytest.mark.parametrize("answer", ["", "a" * 24001, "\udfff"])
def test_invalid_answer_does_not_finish_reserved_turn(store, answer):
    claim = start(store)
    assert_error("invalid_chat_input", finish, store, claim, answer)
    assert store.get(OWNER, claim["conversation"]["id"])["pending"] is not None


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_database_or_sidecar_directories_are_not_followed_or_replaced(store, suffix):
    obstacle = Path(str(store.path) + suffix)
    obstacle.mkdir(parents=True)
    existing = obstacle / "keep.txt"
    existing.write_text("keep", encoding="utf-8")
    assert_error("chat_storage_error", store.create, OWNER, CREATE)
    assert_error("chat_storage_error", store.list, OWNER)
    assert existing.read_text(encoding="utf-8") == "keep"


def test_unrelated_database_is_not_adopted_or_overwritten(store):
    store.path.parent.mkdir(parents=True)
    with sqlite3.connect(store.path) as connection:
        connection.execute("CREATE TABLE unrelated(secret TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('private')")
    before = store.path.read_bytes()
    assert_error("chat_storage_error", store.create, OWNER, CREATE)
    assert_error("chat_storage_error", store.list, OWNER)
    assert store.path.read_bytes() == before


def test_collection_scope_is_durable_and_cannot_change_on_create_retry(store):
    view = store.create(OWNER, CREATE, collection_id=COLLECTION, collection_title="Java OOP")
    assert view["grounding"] == "materials"
    assert view["collection"] == {"id": COLLECTION, "title": "Java OOP"}
    assert ChatStore(store.path).get(OWNER, view["id"]) == view
    assert store.create(OWNER, CREATE, collection_id=COLLECTION, collection_title="Java OOP") == view
    listing = store.list(OWNER)[0]
    assert listing["collection"] == view["collection"] and listing["grounding"] == "materials"
    for kwargs in ({}, {"collection_id": "f" * 32, "collection_title": "Java OOP"},
                   {"collection_id": COLLECTION, "collection_title": "Different title"}):
        with pytest.raises(LearningError) as error:
            store.create(OWNER, CREATE, **kwargs)
        assert error.value.code == "chat_conflict" and error.value.status_code == 409
    assert store.get(OWNER, view["id"]) == view
    assert store.list(OTHER) == []
    assert_error("conversation_not_found", store.get, OTHER, view["id"])
    general = store.create(OWNER, "create-request-0002")
    assert general["collection"] is None and general["grounding"] == "general"


@pytest.mark.parametrize("collection_id,title", [
    (None, "orphan title"), ("../other", "Java"), (COLLECTION, None), (COLLECTION, ""),
    (COLLECTION, "x" * 201), (COLLECTION, "\ud800"),
])
def test_invalid_collection_scope_does_not_create_database(store, collection_id, title):
    with pytest.raises(LearningError) as error:
        store.create(OWNER, CREATE, collection_id=collection_id, collection_title=title)
    assert error.value.code == "invalid_chat_input"
    assert not store.path.exists()


def test_evidence_snapshot_is_durable_owner_scoped_and_completion_is_idempotent(store):
    view = store.create(OWNER, CREATE, collection_id=COLLECTION, collection_title="Java")
    claim = start(store, conversation=view)
    evidence = source_evidence()
    args = (OWNER, view["id"], claim["turn_id"], "Subclass overrides its parent [S1].", "local", "model")
    complete = store.finish_turn(*args, evidence=evidence)
    assert complete["messages"][-1]["evidence"] == evidence
    assert "evidence" not in complete["messages"][0]
    assert ChatStore(store.path).get(OWNER, view["id"]) == complete
    # Canonical JSON makes key insertion order irrelevant on an exact retry.
    assert store.finish_turn(*args, evidence=dict(reversed(list(evidence.items())))) == complete
    changed = deepcopy(evidence)
    changed["sources"][0]["text"] = "Changed source after the answer"
    for retry in (None, changed):
        with pytest.raises(LearningError) as error:
            store.finish_turn(*args, evidence=retry)
        assert error.value.code == "chat_conflict"
    assert store.get(OWNER, view["id"]) == complete
    with pytest.raises(LearningError) as error:
        store.finish_turn(OTHER, *args[1:], evidence=evidence)
    assert error.value.code == "conversation_not_found"


def test_no_match_evidence_is_stored_without_fabricated_sources(store):
    view = store.create(OWNER, CREATE, collection_id=COLLECTION, collection_title="Java")
    claim = start(store, conversation=view)
    evidence = {"status": "no_match", "sources": [], "cited_ids": [], "invalid_citation_ids": []}
    result = store.finish_turn(OWNER, view["id"], claim["turn_id"], "No relevant passage found.", "local", "model", evidence=evidence)
    assert result["messages"][-1]["evidence"] == evidence


@pytest.mark.parametrize("change", [
    {"status": "invented"}, {"status": {}}, {"sources": "invalid"}, {"sources": [{}]},
    {"cited_ids": "S1"}, {"invalid_citation_ids": [object()]}, {"non_json": object()},
    {"bad_number": float("nan")}, {"invalid_text": "\udfff"}, {"oversize": "한" * 22000},
])
def test_invalid_or_oversized_evidence_does_not_complete_turn(store, change):
    claim = start(store)
    evidence = source_evidence() | change
    with pytest.raises(LearningError) as error:
        store.finish_turn(OWNER, claim["conversation"]["id"], claim["turn_id"], "Answer", "local", "model", evidence=evidence)
    assert error.value.code == "invalid_chat_input"
    assert store.get(OWNER, claim["conversation"]["id"])["pending"] is not None


def test_historical_citation_labels_are_removed_only_from_grounded_answers(store):
    claim = start(store)
    complete = finish(store, claim, answer="Literal [S1] in a general explanation.")
    second = start(store, conversation=complete, request="message-request-0002", revision=2)
    assert second["messages"][1]["content"] == "Literal [S1] in a general explanation."
    complete = store.finish_turn(OWNER, complete["id"], second["turn_id"], "Grounded [S1] and [S20].", "local", "model", evidence=source_evidence())
    third = start(store, conversation=complete, request="message-request-0003", revision=4)
    assert third["messages"][1]["content"] == "Literal [S1] in a general explanation."
    assert third["messages"][3]["content"] == "Grounded  and ."
    assert complete["messages"][-1]["content"] == "Grounded [S1] and [S20]."
    assert complete["messages"][-1]["evidence"] == source_evidence()


def test_v1_database_migration_preserves_existing_chat_and_accepts_new_sources(store):
    store.path.parent.mkdir(parents=True)
    old_id, old_turn = "1" * 32, "2" * 32
    with sqlite3.connect(store.path) as connection:
        connection.executescript("""
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, create_request TEXT NOT NULL,
                title TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                revision INTEGER NOT NULL, UNIQUE(owner, create_request));
            CREATE INDEX owner_conversations ON conversations(owner, updated_at);
            CREATE TABLE turns (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, request_id TEXT NOT NULL,
                text TEXT NOT NULL, answer TEXT, started_at REAL NOT NULL, finished_at REAL,
                status TEXT NOT NULL CHECK(status IN ('pending','completed','failed')),
                error_code TEXT, provider TEXT, model TEXT,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                UNIQUE(conversation_id, request_id));
            CREATE INDEX conversation_turns ON turns(conversation_id, started_at);
            CREATE UNIQUE INDEX one_pending_turn ON turns(conversation_id) WHERE status='pending';
            PRAGMA application_id=1128482865;
            PRAGMA user_version=1;
        """)
        connection.execute("INSERT INTO conversations VALUES(?,?,?,?,?,?,?)", (old_id, OWNER, CREATE, "Old lesson", 1000, 1001, 2))
        connection.execute("INSERT INTO turns VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                           (old_turn, old_id, REQUEST, "Old question", "Old answer [S1]", 1000, 1001, "completed", None, "local", "model"))
    migrated = store.get(OWNER, old_id)
    assert migrated["title"] == "Old lesson" and migrated["revision"] == 2
    assert migrated["grounding"] == "general" and migrated["collection"] is None
    assert [message["content"] for message in migrated["messages"]] == ["Old question", "Old answer [S1]"]
    assert "evidence" not in migrated["messages"][1]
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM turns").fetchone()[0] == 1
    assert store.create(OWNER, CREATE) == migrated
    new = store.create(OWNER, "create-request-0002", collection_id=COLLECTION, collection_title="New lesson")
    claim = start(store, conversation=new)
    done = store.finish_turn(OWNER, new["id"], claim["turn_id"], "New [S1]", "local", "model", evidence=source_evidence())
    assert done["messages"][-1]["evidence"] == source_evidence()
    assert store.get(OWNER, old_id) == migrated
