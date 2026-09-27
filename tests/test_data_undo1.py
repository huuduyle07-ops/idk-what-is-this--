"""DATA-01 production HTTP regression and exact durable Undo contract; offline."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading

import pytest

from core import undo_backup as backups
from core.undo_backup import BackupArtifact, BackupError, UndoBackupStore, mutation_lock

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", "")
    from web import app as web_app, session_store
    from web.routes import patch_routes

    directory = tmp_path / "backups"
    directory.mkdir()
    monkeypatch.setattr(web_app, "BACKUP_DIR", directory)
    monkeypatch.setattr(patch_routes, "BACKUP_DIR", directory)
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(patch_routes, "get_default_validation_command", lambda *args: None)
    monkeypatch.setitem(web_app.app.config, "TESTING", True)

    def deny_network(*args, **kwargs):
        raise AssertionError("DATA.UNDO.1 is offline")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir(); b.mkdir()
    (a / "app.py").write_bytes(b"A before\r\n")
    (b / "app.py").write_bytes(b"B before\n")
    return web_app.app.test_client(), UndoBackupStore(directory), a, b


def mutate(store, repo, relative="app.py", after=b"after\n"):
    with mutation_lock:
        pending = store.prepare(repo, relative)
        (repo / relative).write_bytes(after)
        return store.complete(pending, repo, relative)


def undo(env, repo, artifact, **extra):
    response = env[0].post("/undo_patch", data={
        "repo_path": str(repo), "backup_id": artifact.backup_id, "file": "app.py", **extra,
    })
    assert response.is_json and response.status_code == 200
    return response.get_json()


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_primary_http_cross_repo_data01_rejected_without_any_file_change(env):
    _, store, a, b = env
    artifact = mutate(store, a)
    before = snapshot(a.parent)
    result = undo(env, b, artifact)
    assert result["success"] is False and result["code"] == "backup_repo_mismatch"
    assert snapshot(a.parent) == before
    assert store.lookup(artifact.backup_id) == artifact


def test_same_path_two_repositories_have_distinct_authority(env):
    _, store, a, b = env
    a0, b0 = (a / "app.py").read_bytes(), (b / "app.py").read_bytes()
    aa, bb = mutate(store, a), mutate(store, b)
    assert aa.backup_id != bb.backup_id and aa.transaction_id != bb.transaction_id
    assert aa.canonical_repository_identity != bb.canonical_repository_identity
    assert undo(env, a, bb)["code"] == "backup_repo_mismatch"
    assert undo(env, b, aa)["code"] == "backup_repo_mismatch"
    assert undo(env, a, aa)["success"] and (b / "app.py").read_bytes() == b"after\n"
    assert undo(env, b, bb)["success"]
    assert (a / "app.py").read_bytes() == a0 and (b / "app.py").read_bytes() == b0


def test_same_repo_two_transactions_require_exact_current_version(env):
    _, store, a, _ = env
    v0 = (a / "app.py").read_bytes()
    one = mutate(store, a, after=b"v1")
    two = mutate(store, a, after=b"v2")
    assert one.backup_id != two.backup_id and one.transaction_id != two.transaction_id
    before = snapshot(a.parent)
    assert undo(env, a, one)["code"] == "stale_target"
    assert snapshot(a.parent) == before
    assert undo(env, a, two)["success"] and (a / "app.py").read_bytes() == b"v1"
    assert undo(env, a, one)["success"] and (a / "app.py").read_bytes() == v0


@pytest.mark.parametrize("change", [b"manual later edit\r\n", None])
def test_later_user_edit_or_absence_preserved(env, change):
    _, store, a, _ = env
    artifact = mutate(store, a)
    if change is None:
        (a / "app.py").unlink()
    else:
        (a / "app.py").write_bytes(change)
    before = snapshot(a.parent)
    assert undo(env, a, artifact)["code"] == "stale_target"
    assert snapshot(a.parent) == before


def test_tampered_backup_retained(env):
    _, store, a, _ = env
    artifact = mutate(store, a)
    (store.directory / f"{artifact.backup_id}.bak").write_bytes(b"corruption")
    before = snapshot(a.parent)
    assert undo(env, a, artifact)["code"] == "backup_integrity_failed"
    assert snapshot(a.parent) == before


@pytest.mark.parametrize("field,value", [
    ("canonical_repository_identity", "other-" + "1" * 32),
    ("repository_relative_path", "other.py"),
    ("repository_relative_path", "../escape.py"),
    ("before_sha256", "0" * 64), ("backup_bytes_sha256", "0" * 64),
    ("expected_post_sha256", "0" * 64), ("transaction_id", "1" * 32),
    ("schema_version", True), ("before_exists", False), ("expected_post_exists", False),
])
def test_metadata_tamper_fails_closed(env, field, value):
    _, store, a, _ = env
    artifact = mutate(store, a)
    record = asdict(artifact); record[field] = value
    (store.directory / f"{artifact.backup_id}.json").write_text(json.dumps(record))
    before = snapshot(a.parent)
    assert undo(env, a, artifact)["code"] == "backup_metadata_invalid"
    assert snapshot(a.parent) == before


@pytest.mark.parametrize("relative", ["../outside.py", "..\\outside.py", "/outside.py", "C:\\outside.py", "C:outside.py", "\\\\server\\share\\app.py"])
def test_request_and_self_consistent_metadata_cannot_traverse(env, relative):
    _, store, a, _ = env
    artifact = mutate(store, a)
    before = snapshot(a.parent)
    assert undo(env, a, artifact, file=relative)["code"] == "backup_target_invalid"
    assert snapshot(a.parent) == before
    # Even a newly seeded internally consistent record cannot bypass the gate.
    record = replace(artifact, repository_relative_path=relative)
    record = replace(record, backup_id=record.identity_id())
    (store.directory / f"{record.backup_id}.json").write_text(json.dumps(asdict(record)))
    before = snapshot(a.parent)
    assert undo(env, a, record)["code"] == "backup_target_invalid"
    assert snapshot(a.parent) == before


def test_target_and_transaction_crosschecks(env):
    _, store, a, _ = env
    (a / "src").mkdir(); (a / "src/app.py").write_bytes(b"other")
    artifact = mutate(store, a)
    before = snapshot(a.parent)
    assert undo(env, a, artifact, file="src/app.py")["code"] == "backup_target_mismatch"
    assert undo(env, a, artifact, transaction_id="0" * 32)["code"] == "backup_transaction_mismatch"
    assert snapshot(a.parent) == before


def test_same_basename_different_directories_do_not_collide(env):
    _, store, a, _ = env
    (a / "src").mkdir(); (a / "src/app.py").write_bytes(b"nested")
    first, second = mutate(store, a), mutate(store, a, "src/app.py")
    assert first.backup_id != second.backup_id
    assert first.repository_relative_path != second.repository_relative_path
    assert undo(env, a, second)["code"] == "backup_target_mismatch"
    assert undo(env, a, second, file="src/app.py")["success"]
    assert (a / "app.py").read_bytes() == b"after\n"


def test_windows_case_and_separator_identity(env):
    _, store, a, _ = env
    (a / "src").mkdir(); (a / "src/app.py").write_bytes(b"original")
    artifact = mutate(store, a, "src/app.py")
    alias = ".\\SRC\\APP.PY" if os.name == "nt" else "./src/app.py"
    assert undo(env, a, artifact, file=alias)["success"]
    assert (a / "src/app.py").read_bytes() == b"original"


def test_existing_symlink_policy_and_retargeting(env):
    _, store, a, b = env

    def link_directory(link, target):
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=True)

    def unlink_directory(link):
        if os.name == "nt":
            os.rmdir(link)  # removes only the junction, never its target
        else:
            link.unlink()

    (a / "src").mkdir(); (a / "src/app.py").write_bytes(b"linked original")
    link_directory(a / "alias", a / "src")
    artifact = mutate(store, a, "alias/app.py")
    assert artifact.repository_relative_path == "src/app.py"
    assert undo(env, a, artifact, file="alias/app.py")["success"]
    artifact = mutate(store, a, "src/app.py")
    unlink_directory(a / "alias"); link_directory(a / "alias", b)
    before = snapshot(a.parent)
    assert undo(env, a, artifact, file="alias/app.py")["code"] == "backup_target_invalid"
    assert snapshot(a.parent) == before
    # The physical metadata target itself may not be redirected outside either.
    (a / "src/app.py").unlink(); (a / "src").rmdir(); link_directory(a / "src", b)
    assert undo(env, a, artifact, file="src/app.py")["code"] == "backup_target_invalid"


def test_copied_storage_does_not_rebind_repository(env, tmp_path):
    _, store, a, b = env
    import shutil
    artifact = mutate(store, a)
    copy = UndoBackupStore(tmp_path / "moved" / "B")
    shutil.copytree(store.directory, copy.directory)
    before = snapshot(tmp_path)
    assert copy.undo(b, artifact.backup_id)["code"] == "backup_repo_mismatch"
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("original", [b"", b"one\r\ntwo\r\n", b"one\ntwo\n", b"no terminal newline", "한글 café\r\n".encode(), b"\x00\xff\xfe\r\n"])
def test_exact_bytes_post_hash_and_one_shot_consumption(env, original):
    _, store, a, _ = env
    (a / "app.py").write_bytes(original)
    artifact = mutate(store, a)
    result = undo(env, a, artifact)
    assert result["success"] and result["restored_sha256"] == hashlib.sha256(original).hexdigest()
    assert (a / "app.py").read_bytes() == original
    assert not (store.directory / f"{artifact.backup_id}.bak").exists()
    assert (store.directory / f"{artifact.backup_id}.consumed.json").is_file()
    before = snapshot(a.parent)
    assert undo(env, a, artifact)["code"] == "backup_already_consumed"
    assert snapshot(a.parent) == before


@pytest.mark.parametrize("failure", ["replace", "post_verify"])
def test_restore_failure_never_consumes_or_claims_success(env, monkeypatch, failure):
    _, store, a, _ = env
    artifact = mutate(store, a)
    original = backups._atomic_replace_bytes

    def broken(path, raw):
        if path == a / "app.py":
            if failure == "replace":
                raise OSError("injected replace failure")
            return original(path, b"injected wrong final bytes")
        return original(path, raw)

    monkeypatch.setattr(backups, "_atomic_replace_bytes", broken)
    result = undo(env, a, artifact)
    assert not result["success"]
    assert store.lookup(artifact.backup_id) == artifact
    assert (store.directory / f"{artifact.backup_id}.bak").read_bytes() == b"A before\r\n"
    if failure == "replace":
        assert (a / "app.py").read_bytes() == b"after\n"


def test_atomic_replace_failure_keeps_complete_target_and_backup(env, monkeypatch):
    _, store, a, _ = env
    artifact = mutate(store, a)
    before = snapshot(a.parent)
    original = os.replace

    def refuse(source, destination):
        if Path(destination) == a / "app.py":
            assert Path(source).parent == a
            assert Path(source).read_bytes() == b"A before\r\n"
            assert (a / "app.py").read_bytes() == b"after\n"
            raise PermissionError("injected atomic replacement refusal")
        return original(source, destination)

    monkeypatch.setattr(os, "replace", refuse)
    assert undo(env, a, artifact)["code"] == "backup_io_failed"
    assert snapshot(a.parent) == before  # includes temporary-file cleanup


def test_producer_does_not_walk_repository_or_backup_inventory(env, monkeypatch):
    _, store, a, _ = env

    def no_walk(*args, **kwargs):
        raise AssertionError("Durable Undo production is bounded to exact paths")

    monkeypatch.setattr(Path, "glob", no_walk); monkeypatch.setattr(Path, "rglob", no_walk)
    monkeypatch.setattr(os, "walk", no_walk)
    artifact = mutate(store, a)
    assert undo(env, a, artifact)["success"]


@pytest.mark.parametrize("boundary", ["prepare", "complete"])
def test_apply_backup_io_failures_are_separate_from_executor_truth(env, monkeypatch, boundary):
    client, store, a, _ = env
    old = b"def advance(value):\r\n    return value + 1\r\n"
    (a / "app.py").write_bytes(old)

    def refuse(*args, **kwargs):
        raise OSError("injected backup storage failure")

    monkeypatch.setattr(UndoBackupStore, boundary, refuse)
    payload = {"undo_backup": {"backup_id": "f" * 64}, "patch_candidate": {
        "relative_path": "app.py", "file": "app.py", "target_node_name": "advance", "target_node_kind": "function",
        "target_snippet": old.decode().replace("\r\n", "\n"), "patched_snippet": "def advance(value):\n    return value + 2\n",
    }}
    result = client.post("/apply_patch", data={"repo_path": str(a), "patch": json.dumps(payload)}).get_json()
    if boundary == "prepare":
        assert not result["success"] and result["code"] == "backup_io_failed"
        assert (a / "app.py").read_bytes() == old
    else:
        assert result["success"] and result["backup_error"]["code"] == "backup_io_failed", result
        assert result["backup_id"] is None and result["undo_backup"] is None
        assert json.loads(result["patch"])["undo_backup"] is None
        assert b"+ 2" in (a / "app.py").read_bytes()
        pending = list(store.directory.glob("pending-*.bak"))
        assert len(pending) == 1 and pending[0].read_bytes() == old


def test_legacy_path_only_and_pathlike_ids_fail_without_scanning(env, monkeypatch):
    client, store, a, _ = env
    legacy = store.directory.parent / "app.py_123456.bak"
    legacy.write_bytes(b"legacy A bytes")
    before = snapshot(a.parent)

    def no_walk(*args, **kwargs):
        raise AssertionError("Undo must not enumerate backup or repository trees")

    with monkeypatch.context() as guard:
        guard.setattr(Path, "glob", no_walk); guard.setattr(Path, "rglob", no_walk)
        guard.setattr(os, "walk", no_walk)
        for bad in ("", "../app.py_123456.bak", str(legacy), "app.py", "0" * 64):
            result = client.post("/undo_patch", data={"repo_path": str(a), "file": "app.py", "backup_id": bad}).get_json()
            assert not result["success"]
            assert result["code"] in {"backup_id_required", "backup_not_found"}
    assert snapshot(a.parent) == before


def test_created_file_undo_stays_unsupported(env):
    _, store, a, _ = env
    assert mutate(store, a, "created.py") is None
    assert (a / "created.py").read_bytes() == b"after\n"


def test_durable_lookup_in_fresh_python_process(env):
    _, store, a, _ = env
    artifact = mutate(store, a)
    code = "from core.undo_backup import UndoBackupStore; from pathlib import Path; import json,sys; print(json.dumps(UndoBackupStore(Path(sys.argv[1])).undo(sys.argv[2],sys.argv[3])))"
    result = subprocess.run([sys.executable, "-c", code, str(store.directory.parent), str(a), artifact.backup_id], cwd=ROOT, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["success"]
    assert (a / "app.py").read_bytes() == b"A before\r\n"


def test_validation_through_consumption_is_serialized(env, monkeypatch):
    _, store, a, _ = env
    artifact = mutate(store, a)
    entered, release, competing = threading.Event(), threading.Event(), threading.Event()
    original = backups._atomic_replace_bytes

    def paused(path, raw):
        entered.set()
        assert release.wait(5)
        original(path, raw)

    monkeypatch.setattr(backups, "_atomic_replace_bytes", paused)
    results = []
    first = threading.Thread(target=lambda: results.append(store.undo(a, artifact.backup_id)))

    def second_operation():
        competing.set()
        results.append(store.undo(a, artifact.backup_id))

    second = threading.Thread(target=second_operation)
    first.start()
    assert entered.wait(5)
    second.start(); assert competing.wait(5)
    assert not results
    release.set(); first.join(5); second.join(5)
    assert len(results) == 2
    assert results[0]["success"] and results[1]["code"] == "backup_already_consumed"


def test_real_apply_receipt_session_reload_and_undo(env):
    client, store, a, _ = env
    from web import session_store
    old = b"def advance(value):\r\n    return value + 1\r\n"
    (a / "app.py").write_bytes(old)
    session_store.save_sessions([{"id": "undo-session", "repo_path": str(a), "result": {}}])
    patch = {"relative_path": "app.py", "file": "app.py", "target_node_name": "advance",
             "target_node_kind": "function", "target_snippet": old.decode().replace("\r\n", "\n"),
             "patched_snippet": "def advance(value):\n    return value + 2\n"}
    response = client.post("/apply_patch", data={"repo_path": str(a), "patch": json.dumps(patch), "session_id": "undo-session"})
    result = response.get_json()
    assert result["success"], result
    record = store.lookup(result["backup_id"])
    persisted = json.loads(session_store.find_session("undo-session")["result"]["patch"])
    assert persisted["undo_backup"] == result["undo_backup"] == json.loads(result["patch"])["undo_backup"]
    assert persisted["undo_backup"]["transaction_id"] == record.transaction_id
    # A second HTTP request carries only the receipt obtained from disk.
    undone = client.post("/undo_patch", data={"repo_path": str(a), "file": "app.py", **persisted["undo_backup"]}).get_json()
    assert undone["success"] and (a / "app.py").read_bytes() == old


def test_bounded_authority_and_frontend_transport_regression():
    from web.app import undo_patch
    from web.routes.patch_routes import apply_patch
    route = inspect.getsource(undo_patch)
    assert 'request.form.get("backup_id"' in route and "UndoBackupStore" in route
    for unsafe in ("glob(", "sorted(", "latest", "backup_key_for_path", "write_text("):
        assert unsafe not in route
    producer = inspect.getsource(apply_patch)
    assert "with mutation_lock:" in producer and "store.prepare(" in producer and "store.complete(" in producer
    assert "backup_key_for_path" not in producer and ".glob(" not in producer
    text = (ROOT / "web/templates/index.html").read_text(encoding="utf-8")
    handler = text[text.index("function undoPatch()"):text.index("function escapeHtml")]
    assert "undoBackup = parsed.undo_backup" in handler
    assert 'backup_id: undoBackup?.backup_id || ""' in handler
    # UX-03 is closed by UX.STATE.1: Undo success now derives from this owner's
    # structured response instead of an unconditional "undone" label.
    assert 'last_action: "undone"' not in handler
    assert "WorkbenchState.undoOutcome(data, undoBackup)" in handler


def test_invalid_metadata_is_structured_json(env):
    _, store, a, _ = env
    artifact = mutate(store, a)
    for raw in (b"{", b"[]", b"null", b"\xff"):
        (store.directory / f"{artifact.backup_id}.json").write_bytes(raw)
        assert undo(env, a, artifact)["code"] == "backup_metadata_invalid"


def test_original_data01_route_reproduces_red_from_recorded_entry(tmp_path):
    from flask import Flask, request
    fixture = json.loads((ROOT / "tests/fixtures/data_undo1_reversal.json").read_text(encoding="utf-8"))
    app = Flask("legacy-data01-proof")
    a, b, storage = tmp_path / "A", tmp_path / "B", tmp_path / "backups"
    a.mkdir(); b.mkdir(); storage.mkdir()
    (a / "app.py").write_bytes(b"A current\n")
    (b / "app.py").write_bytes(b"B current\n")
    artifact = storage / "app.py_1234567890.0.bak"
    artifact.write_bytes(b"A before\n")
    namespace = {"app": app, "request": request, "Path": Path, "BACKUP_DIR": storage}
    exec(fixture["undo_route_before"], namespace)
    response = app.test_client().post("/undo_patch", data={"repo_path": str(b), "file": "app.py"})
    assert response.get_json()["success"]
    assert (b / "app.py").read_text() == "A before\n"
    assert (a / "app.py").read_bytes() == b"A current\n"
    assert not artifact.exists()


def test_frozen_entry_hashes_and_reviewable_reversal():
    from tests._data_undo1_maintenance import before_data_undo1
    fixture = json.loads((ROOT / "tests/fixtures/data_undo1_frozen_boundaries.json").read_text(encoding="utf-8"))
    for name, digest in fixture["sha256"].items():
        assert hashlib.sha256(before_data_undo1(name)).hexdigest() == digest, name


def test_one_registered_phase_in_existing_track():
    from core.phase_registry import load_phase_registry, validate_phase_registry
    from core.phase_picker import pick_phase_candidates
    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    assert validate_phase_registry(registry)["is_valid"]
    phases = [p for p in registry["phases"] if p["phase_id"] == "DATA.UNDO.1"]
    assert len(phases) == 1
    assert phases[0]["track"] == "HARDEN" and phases[0]["status"] == "complete"
    assert not phases[0]["network_allowed"] and not phases[0]["model_calls_allowed"]
    assert pick_phase_candidates(registry)["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_production_browser_handler_transports_persisted_receipt():
    from playwright.sync_api import sync_playwright
    text = (ROOT / "web/templates/index.html").read_text(encoding="utf-8")
    handler = text[text.index("function undoPatch()"):text.index("function escapeHtml")]
    state_owner = (ROOT / "web/static/workbench_state.js").read_text(encoding="utf-8")
    saved = {"patch_candidate": {"relative_path": "src/app.py"},
             "undo_backup": {"backup_id": "a" * 64, "transaction_id": "b" * 32}}
    requests = []
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        page = browser.new_page()

        def respond(route):
            if route.request.method == "POST":
                from urllib.parse import parse_qs
                requests.append(parse_qs(route.request.post_data))
                route.fulfill(json={"success": False, "message": "stale_target"})
            else:
                route.fulfill(content_type="text/html", body='<input name="repo_path" value="repo"><pre id="patchRawJson"></pre>')

        page.route("**/*", respond)
        for _ in range(2):
            page.goto("http://data-undo.test/")
            # UX.STATE.1: the handler reads the persisted receipt from the page's
            # workflow-state owner, hydrated from the same saved payload.
            page.add_script_tag(content=state_owner)
            page.evaluate("(value) => WorkbenchState.hydrate({repository: 'repo', candidateText: JSON.stringify(value)})", saved)
            page.add_script_tag(content='window.alert = () => {};\n' + handler)
            page.evaluate("undoPatch()")
            # UX-03 closed: success:false is a failed action, never "undone".
            page.wait_for_function('WorkbenchState.snapshot().action.status === "failed"')
            assert page.evaluate("WorkbenchState.snapshot().action.code") == "undo_failed"
        browser.close()
    assert len(requests) == 2
    for payload in requests:
        assert payload == {"repo_path": ["repo"], "file": ["src/app.py"],
                           "backup_id": ["a" * 64], "transaction_id": ["b" * 32]}
