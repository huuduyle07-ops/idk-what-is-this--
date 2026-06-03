"""Phase 11-prep-cleanup-b1: History Archive/Delete UX tests."""
from __future__ import annotations
import json
from pathlib import Path
import pytest


# ---------------------------------------------------------------------------
# Helpers shared across tasks
# ---------------------------------------------------------------------------

def _write_sessions(path: Path, sessions: list[dict]) -> None:
    path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sessions_file(tmp_path, monkeypatch):
    """Redirect SESSION_FILE to a temp path with two seed sessions."""
    import web.session_store as ss
    f = tmp_path / "sessions.json"
    _write_sessions(f, [
        {"id": "sess_001", "title": "Session 1", "query": "q1"},
        {"id": "sess_002", "title": "Session 2", "query": "q2"},
    ])
    monkeypatch.setattr(ss, "SESSION_FILE", f)
    return f


# ---------------------------------------------------------------------------
# Task 1 — unit tests for list_sessions
# ---------------------------------------------------------------------------

def test_list_sessions_default_excludes_archived(tmp_path, monkeypatch):
    import web.session_store as ss
    f = tmp_path / "sessions.json"
    _write_sessions(f, [
        {"id": "a", "archived": True},
        {"id": "b"},
    ])
    monkeypatch.setattr(ss, "SESSION_FILE", f)
    result = ss.list_sessions()
    assert [s["id"] for s in result] == ["b"]


def test_list_sessions_include_archived(tmp_path, monkeypatch):
    import web.session_store as ss
    f = tmp_path / "sessions.json"
    _write_sessions(f, [
        {"id": "a", "archived": True},
        {"id": "b"},
    ])
    monkeypatch.setattr(ss, "SESSION_FILE", f)
    result = ss.list_sessions(include_archived=True)
    assert {s["id"] for s in result} == {"a", "b"}


def test_list_sessions_default_excludes_deleted(tmp_path, monkeypatch):
    import web.session_store as ss
    f = tmp_path / "sessions.json"
    _write_sessions(f, [
        {"id": "a", "deleted": True},
        {"id": "b"},
    ])
    monkeypatch.setattr(ss, "SESSION_FILE", f)
    result = ss.list_sessions()
    assert [s["id"] for s in result] == ["b"]


# ---------------------------------------------------------------------------
# Task 2 — unit tests for benchmark sidecar helpers
# ---------------------------------------------------------------------------

def _make_bench_dir(tmp_path: Path, filename: str = "benchmark_report_1000000000.json") -> tuple[Path, str]:
    """Create a minimal .agent/benchmarks dir with one report file."""
    repo = tmp_path / "repo"
    bench = repo / ".agent" / "benchmarks"
    bench.mkdir(parents=True)
    data = {"total": 10, "passed": 8, "failed": 2, "skipped": 0,
            "success_rate": 0.8, "duration_sec": 30}
    (bench / filename).write_text(json.dumps(data), encoding="utf-8")
    return repo, filename


def test_benchmark_meta_roundtrip(tmp_path):
    from core.benchmarks_view import read_benchmark_meta, write_benchmark_meta
    repo, filename = _make_bench_dir(tmp_path)
    assert read_benchmark_meta(repo) == {}
    write_benchmark_meta(repo, {filename: {"archived": True, "pinned": False}})
    meta = read_benchmark_meta(repo)
    assert meta[filename]["archived"] is True
    assert meta[filename]["pinned"] is False


def test_update_benchmark_entry_merges(tmp_path):
    from core.benchmarks_view import update_benchmark_entry, read_benchmark_meta
    repo, filename = _make_bench_dir(tmp_path)
    update_benchmark_entry(repo, filename, archived=True)
    entry = read_benchmark_meta(repo)[filename]
    assert entry["archived"] is True
    update_benchmark_entry(repo, filename, pinned=True)
    entry2 = read_benchmark_meta(repo)[filename]
    assert entry2["archived"] is True   # preserved
    assert entry2["pinned"] is True


def test_list_benchmark_reports_filters_archived(tmp_path):
    from core.benchmarks_view import update_benchmark_entry, list_benchmark_reports
    repo, filename = _make_bench_dir(tmp_path)
    # Default: report visible
    assert any(r["filename"] == filename for r in list_benchmark_reports(repo))
    # Archive it
    update_benchmark_entry(repo, filename, archived=True)
    # Default list hides it
    assert not any(r["filename"] == filename for r in list_benchmark_reports(repo))
    # include_archived shows it
    assert any(r["filename"] == filename for r in list_benchmark_reports(repo, include_archived=True))


# ---------------------------------------------------------------------------
# Task 3 — unit tests for dream run sidecar helpers
# ---------------------------------------------------------------------------

def _make_dream_run(
    tmp_path: Path,
    date: str = "2026-06-04",
    run: str = "010203-run",
) -> tuple[Path, str, str]:
    """Create a minimal dream run dir under tmp_path/repo."""
    repo = tmp_path / "repo"
    run_dir = repo / ".agent" / "dreams" / date / run
    run_dir.mkdir(parents=True)
    items = [{"idx": 1, "title": "Fix T", "status": "planned_no_patch"}]
    (run_dir / "list.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    return repo, date, run


def test_dream_meta_roundtrip(tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")
    assert da.read_dream_meta(str(repo)) == {}
    run_key = f"{date}/{run}"
    da.write_dream_meta(str(repo), {run_key: {"archived": True, "pinned": False, "deleted": False}})
    meta = da.read_dream_meta(str(repo))
    assert meta[run_key]["archived"] is True


def test_update_dream_entry_merges(tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")
    run_key = f"{date}/{run}"
    da.update_dream_entry(str(repo), run_key, archived=True)
    entry = da.read_dream_meta(str(repo))[run_key]
    assert entry["archived"] is True
    da.update_dream_entry(str(repo), run_key, pinned=True)
    entry2 = da.read_dream_meta(str(repo))[run_key]
    assert entry2["archived"] is True   # preserved
    assert entry2["pinned"] is True


def test_list_all_reports_filters_archived_and_deleted(tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")
    run_key = f"{date}/{run}"

    # Default: run is visible
    reports = da.list_all_reports(str(repo))
    assert any(r["run_id"] == run for r in reports)

    # Archive it — hidden by default, shown with include_archived
    da.update_dream_entry(str(repo), run_key, archived=True)
    assert not any(r["run_id"] == run for r in da.list_all_reports(str(repo)))
    assert any(r["run_id"] == run for r in da.list_all_reports(str(repo), include_archived=True))

    # Soft-delete — always hidden regardless of include_archived
    da.update_dream_entry(str(repo), run_key, archived=False, deleted=True)
    assert not any(r["run_id"] == run for r in da.list_all_reports(str(repo), include_archived=True))


# ---------------------------------------------------------------------------
# Integration tests 1–8 (require history_routes blueprint + app updates)
# ---------------------------------------------------------------------------

# Test 1
def test_archive_session_hides_from_default(client, sessions_file):
    resp = client.post(
        "/history/session/archive",
        data={"session_id": "sess_001", "archived": "true"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    resp2 = client.get("/history/sessions")
    assert resp2.status_code == 200
    ids = [s["id"] for s in resp2.get_json()["sessions"]]
    assert "sess_001" not in ids
    assert "sess_002" in ids


# Test 2
def test_archived_session_shown_with_include_archived(client, sessions_file):
    client.post(
        "/history/session/archive",
        data={"session_id": "sess_001", "archived": "true"},
    )
    resp = client.get("/history/sessions?include_archived=1")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.get_json()["sessions"]]
    assert "sess_001" in ids
    assert "sess_002" in ids


# Test 3
def test_benchmark_report_can_be_archived(client, tmp_path, monkeypatch):
    repo, filename = _make_bench_dir(tmp_path)

    resp = client.post(
        "/history/benchmark/update",
        data={"repo_path": str(repo), "filename": filename, "archived": "true"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    resp2 = client.get(f"/benchmarks/list?repo_path={repo}")
    assert resp2.status_code == 200
    reports = resp2.get_json()["reports"]
    assert not any(r["filename"] == filename for r in reports)


# Test 4
def test_pinned_benchmark_report_cannot_be_deleted(client, tmp_path, monkeypatch):
    repo, filename = _make_bench_dir(tmp_path)
    client.post(
        "/history/benchmark/update",
        data={"repo_path": str(repo), "filename": filename, "pinned": "true"},
    )
    resp = client.post(
        "/history/benchmark/delete",
        data={
            "repo_path": str(repo),
            "filename": filename,
            "confirm": "DELETE_BENCHMARK_REPORT",
        },
    )
    assert resp.status_code == 409
    assert "pinned" in resp.get_json()["error"]


# Test 5
def test_dream_run_can_be_archived(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")

    resp = client.post(
        "/history/dream/update",
        data={"repo_path": str(repo), "date": date, "run": run, "archived": "true"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    resp2 = client.get(f"/dream/reports?repo_path={repo}")
    assert resp2.status_code == 200
    reports = resp2.get_json()["reports"]
    assert not any(r["run_id"] == run for r in reports)


# Test 6
def test_pinned_dream_run_cannot_be_deleted(client, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo, date, run = _make_dream_run(tmp_path)
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo / ".agent" / "dreams")

    client.post(
        "/history/dream/update",
        data={"repo_path": str(repo), "date": date, "run": run, "pinned": "true"},
    )
    resp = client.post(
        "/history/dream/delete",
        data={
            "repo_path": str(repo),
            "date": date,
            "run": run,
            "confirm": "DELETE_DREAM_RUN",
        },
    )
    assert resp.status_code == 409
    assert "pinned" in resp.get_json()["error"]


# Test 7
def test_delete_requires_confirmation_token(client, sessions_file, tmp_path, monkeypatch):
    import core.dream_artifacts as da
    repo_b, filename = _make_bench_dir(tmp_path)
    repo_d, date, run = _make_dream_run(tmp_path, date="2026-06-04", run="020304-run")
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo_d / ".agent" / "dreams")

    # Session: wrong confirm
    r = client.post("/history/session/delete", data={"session_id": "sess_001", "confirm": "WRONG"})
    assert r.status_code == 400
    assert "DELETE_SESSION" in r.get_json()["error"]

    # Session: missing confirm
    r = client.post("/history/session/delete", data={"session_id": "sess_001"})
    assert r.status_code == 400

    # Benchmark: wrong confirm
    r = client.post("/history/benchmark/delete", data={
        "repo_path": str(repo_b), "filename": filename, "confirm": "WRONG",
    })
    assert r.status_code == 400
    assert "DELETE_BENCHMARK_REPORT" in r.get_json()["error"]

    # Dream: wrong confirm
    r = client.post("/history/dream/delete", data={
        "repo_path": str(repo_d), "date": date, "run": run, "confirm": "WRONG",
    })
    assert r.status_code == 400
    assert "DELETE_DREAM_RUN" in r.get_json()["error"]


# Test 8
def test_no_execution_routes_called(client, sessions_file, tmp_path, monkeypatch):
    import core.benchmark_web as bw
    import core.sleeping_consultant as sc
    import agents.gemini_client as gc
    import core.dream_artifacts as da

    def _raise(*a, **kw):
        raise AssertionError("execution route was called unexpectedly")

    monkeypatch.setattr(bw, "start_benchmark_run_async", _raise)
    monkeypatch.setattr(sc, "start_overnight_async", _raise)
    monkeypatch.setattr(gc, "run_gemini_request", _raise)

    repo_b, filename = _make_bench_dir(tmp_path)
    repo_d, date, run = _make_dream_run(tmp_path, date="2026-06-04", run="030405-run")
    monkeypatch.setattr(da, "dreams_root", lambda rp: repo_d / ".agent" / "dreams")

    # All 7 history routes must complete without triggering execution functions
    client.get("/history/sessions")
    client.post("/history/session/archive",
                data={"session_id": "sess_001", "archived": "true"})
    client.post("/history/session/delete",
                data={"session_id": "sess_001", "confirm": "DELETE_SESSION"})
    client.post("/history/benchmark/update",
                data={"repo_path": str(repo_b), "filename": filename, "archived": "true"})
    client.post("/history/benchmark/delete",
                data={"repo_path": str(repo_b), "filename": filename,
                      "confirm": "DELETE_BENCHMARK_REPORT"})
    client.post("/history/dream/update",
                data={"repo_path": str(repo_d), "date": date, "run": run, "archived": "true"})
    client.post("/history/dream/delete",
                data={"repo_path": str(repo_d), "date": date, "run": run,
                      "confirm": "DELETE_DREAM_RUN"})
    # If _raise was triggered, the test would have failed above
