# Phase 7.2 — Worker Run Review / Import (Implementation Plan)

**Goal:** Ship the worker-run review and import layer: operators can browse `.agent/worker_runs/<run>/` from the Memory tab, view detail, and optionally import a complete run as a proposal under `.agent/proposals/`.

**Architecture:** One new pure module (`core/worker_runs.py`), two new web routes + one refactor, one UI subsection inside the existing Mayor Mode panel. **No new pip dependencies.** Real repo is never modified by this code path.

**Spec:** `docs/superpowers/specs/2026-05-21-phase-7-2-worker-run-review-design.md`

---

## File map

**Create:**
- `core/worker_runs.py` — `list / read / detect_worker_outputs / import_worker_run_as_proposal`
- `tests/test_worker_runs.py` — unit tests for the core module
- `tests/test_worker_runs_routes.py` — Flask client tests for the 3 routes

**Modify:**
- `web/app.py` — refactor `/worker-runs/list`, add `/worker-runs/view` and `/worker-runs/import`
- `web/templates/index.html` — append a "Worker Runs" subsection inside `handoffs-section`
- `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md` — Phase 7.2 shipped block

Estimated new lines: ~700 (core ~250, tests ~350, web ~80, template ~120, docs ~20).

---

## Task A — `core/worker_runs.py` (constants + list + read + detect + import)

**Files:**
- Create: `core/worker_runs.py`
- Create: `tests/test_worker_runs.py`

### TDD step list

1. **Write the failing tests first**, in `tests/test_worker_runs.py`. Tests cover:

```python
"""Phase 7.2 — unit tests for core/worker_runs.py."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import handoff_notes, worker_runs


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    worker_runs_root = tmp_path / "worker_runs"
    proposals_root = tmp_path / "proposals"
    handoff_root = tmp_path / "handoffs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(worker_runs, "DEFAULT_WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(worker_runs, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)

    return {
        "worker_runs_root": worker_runs_root,
        "proposals_root": proposals_root,
        "handoff_root": handoff_root,
        "fake_repo": fake_repo,
    }


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_run(env, run_id, *, complete=True, dry_run=False, handoff_title="Test"):
    """Synthesize a worker run dir resembling Phase 7.1 output."""
    run_dir = env["worker_runs_root"] / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # handoff.md (use real create_handoff_note to ensure parseable HANDOFF_META)
    note = handoff_notes.create_handoff_note(
        title=handoff_title,
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(env["fake_repo"]),
        handoff_root=env["handoff_root"],
    )
    handoff_text = Path(note["path"]).read_text(encoding="utf-8")
    (run_dir / "handoff.md").write_text(handoff_text, encoding="utf-8")

    # worker_run.json
    _write_json(run_dir / "worker_run.json", {
        "dry_run": dry_run,
        "started_at": "2026-05-21T01:02:03+00:00",
        "finished_at": "2026-05-21T01:02:15+00:00",
        "duration_sec": 12.4,
        "exit_code": 0,
        "timed_out": False,
        "command": "codex exec --full-auto",
        "worker": "codex",
        "handoff_path": note["path"],
        "artifact_dir": str(run_dir),
        "timeout_sec": 300,
        "error": None,
    })

    # raw_output.txt
    (run_dir / "raw_output.txt").write_text(
        "worker said:\n" + ("A" * 5000), encoding="utf-8"
    )

    # worker_command.txt
    (run_dir / "worker_command.txt").write_text("codex exec --full-auto\n", encoding="utf-8")

    if complete:
        (run_dir / "proposal.md").write_text("# Worker proposal\n\nDo X.\n", encoding="utf-8")
        _write_json(run_dir / "patch_plan.json", [
            {"op": "replace_snippet", "relative_path": "src/foo.py",
             "target_snippet": "x = 1", "patched_snippet": "x = 2"}
        ])

    return run_dir


def _real_repo_state(repo: Path) -> dict[str, str]:
    state: dict[str, str] = {}
    for p in repo.rglob("*"):
        if p.is_file():
            state[p.relative_to(repo).as_posix()] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    return state


# ---- list_worker_runs -------------------------------------------------------


def test_list_worker_runs_empty_returns_empty_list(env):
    assert worker_runs.list_worker_runs() == []


def test_list_worker_runs_returns_newest_first(env):
    import time

    _make_run(env, "20260521_010000_a", handoff_title="a")
    time.sleep(1.1)
    _make_run(env, "20260521_010002_b", handoff_title="b")
    runs = worker_runs.list_worker_runs()
    assert len(runs) == 2
    assert runs[0]["run_id"] == "20260521_010002_b"
    assert runs[1]["run_id"] == "20260521_010000_a"


def test_list_worker_runs_respects_limit(env):
    for i in range(5):
        _make_run(env, f"20260521_01000{i}_x{i}")
    runs = worker_runs.list_worker_runs(limit=3)
    assert len(runs) == 3


def test_list_worker_runs_includes_legacy_fields(env):
    """The legacy /worker-runs/list response shape must remain intact."""
    _make_run(env, "20260521_010203_foo")
    runs = worker_runs.list_worker_runs()
    item = runs[0]
    for legacy_key in (
        "artifact_dir", "name", "dry_run", "worker", "exit_code",
        "timed_out", "duration_sec", "command", "handoff_path",
        "started_at", "finished_at", "error",
    ):
        assert legacy_key in item, f"missing legacy field: {legacy_key}"


def test_list_worker_runs_includes_new_fields(env):
    _make_run(env, "20260521_010203_foo", handoff_title="Hello")
    runs = worker_runs.list_worker_runs()
    item = runs[0]
    assert item["run_id"] == "20260521_010203_foo"
    assert item["has_proposal_md"] is True
    assert item["has_patch_plan_json"] is True
    assert item["handoff_title"] == "Hello"


def test_list_worker_runs_skips_dirs_without_worker_run_json(env):
    (env["worker_runs_root"] / "20260521_999999_broken").mkdir(parents=True)
    runs = worker_runs.list_worker_runs()
    assert runs == []


# ---- read_worker_run --------------------------------------------------------


def test_read_worker_run_via_run_id_returns_full_detail(env):
    _make_run(env, "20260521_010203_foo", handoff_title="hello detail")
    detail = worker_runs.read_worker_run("20260521_010203_foo")
    assert detail["run_id"] == "20260521_010203_foo"
    assert detail["handoff_title"] == "hello detail"
    assert detail["has_proposal_md"] is True
    assert detail["has_patch_plan_json"] is True
    assert detail["raw_output_preview"].startswith("worker said:")
    assert len(detail["raw_output_preview"]) <= worker_runs.RAW_OUTPUT_PREVIEW_CHARS + 64


def test_read_worker_run_via_absolute_path(env):
    run_dir = _make_run(env, "20260521_010203_foo")
    detail = worker_runs.read_worker_run(str(run_dir))
    assert detail["run_id"] == "20260521_010203_foo"


def test_read_worker_run_blocks_path_traversal(env, tmp_path):
    outside = tmp_path / "outside_run"
    outside.mkdir()
    (outside / "worker_run.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        worker_runs.read_worker_run(str(outside))


def test_read_worker_run_missing_raises_file_not_found(env):
    with pytest.raises(FileNotFoundError):
        worker_runs.read_worker_run("20260521_000000_nope")


# ---- detect_worker_outputs --------------------------------------------------


def test_detect_worker_outputs_complete(env):
    run_dir = _make_run(env, "20260521_010203_complete")
    detect = worker_runs.detect_worker_outputs(run_dir)
    assert detect["complete"] is True
    assert detect["has_proposal_md"] is True
    assert detect["has_patch_plan_json"] is True
    assert detect["has_handoff_md"] is True
    assert detect["has_worker_run_json"] is True
    assert detect["missing"] == []


def test_detect_worker_outputs_incomplete(env):
    run_dir = _make_run(env, "20260521_010203_incomplete", complete=False)
    detect = worker_runs.detect_worker_outputs(run_dir)
    assert detect["complete"] is False
    assert detect["has_proposal_md"] is False
    assert detect["has_patch_plan_json"] is False
    assert "proposal.md" in detect["missing"]
    assert "patch_plan.json" in detect["missing"]


# ---- import_worker_run_as_proposal ------------------------------------------


def test_import_creates_proposal_dir_with_all_artifacts(env):
    run_dir = _make_run(env, "20260521_010203_imp", handoff_title="Import me")
    before = _real_repo_state(env["fake_repo"])

    result = worker_runs.import_worker_run_as_proposal(run_dir)

    proposal_dir = Path(result["proposal_dir"])
    assert proposal_dir.is_dir()
    for f in ("item.json", "source_metadata.json", "handoff.md",
              "worker_run.json", "proposal.md", "patch_plan.json", "raw_output.txt"):
        assert (proposal_dir / f).is_file(), f"missing {f}"

    item = json.loads((proposal_dir / "item.json").read_text(encoding="utf-8"))
    assert item["source"] == "worker_run"
    assert item["source_run_id"] == "20260521_010203_imp"
    assert item["worker"] == "codex"
    assert item["human_approved_for_proposal"] is False
    assert item["needs_revalidation"] is True
    assert item["title"] == "Import me"

    src = json.loads((proposal_dir / "source_metadata.json").read_text(encoding="utf-8"))
    assert src["source"] == "worker_run"
    assert src["source_run_dir"].endswith("20260521_010203_imp")
    assert set(src["imported_files"]) >= {"handoff.md", "worker_run.json",
                                          "proposal.md", "patch_plan.json", "raw_output.txt"}

    after = _real_repo_state(env["fake_repo"])
    assert before == after, "real repo must be byte-identical after import"


def test_import_refuses_incomplete_run(env):
    run_dir = _make_run(env, "20260521_010203_inc", complete=False)
    with pytest.raises(FileNotFoundError, match="incomplete"):
        worker_runs.import_worker_run_as_proposal(run_dir)


def test_import_refuses_dry_run(env):
    run_dir = _make_run(env, "20260521_010203_dry", dry_run=True)
    with pytest.raises(ValueError, match="dry-run"):
        worker_runs.import_worker_run_as_proposal(run_dir)


def test_import_refuses_path_outside_worker_runs(env, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    for f in ("handoff.md", "proposal.md", "patch_plan.json", "raw_output.txt"):
        (outside / f).write_text("x", encoding="utf-8")
    _write_json(outside / "worker_run.json", {"dry_run": False, "worker": "codex"})
    with pytest.raises(ValueError, match="outside"):
        worker_runs.import_worker_run_as_proposal(str(outside))


def test_import_handles_directory_collision(env):
    run_dir = _make_run(env, "20260521_010203_collide")
    first = worker_runs.import_worker_run_as_proposal(run_dir)
    second = worker_runs.import_worker_run_as_proposal(run_dir)
    assert first["proposal_dir"] != second["proposal_dir"]
    assert Path(first["proposal_dir"]).is_dir()
    assert Path(second["proposal_dir"]).is_dir()
```

2. **Run the tests** — `python -m pytest tests/test_worker_runs.py -v`. Expect `ModuleNotFoundError: No module named 'core.worker_runs'`.

3. **Write the implementation** in `core/worker_runs.py`:

```python
"""Phase 7.2 — review and import worker-run artifacts.

Reads Phase 7.1 output under `<AI-project>/.agent/worker_runs/<run>/` and,
when the operator chooses, imports a complete run into
`<AI-project>/.agent/proposals/<run>/01-<slug>/` so it can flow through the
existing proposal -> lesson review path.

Pure I/O + validation. No subprocess, no Flask. Never modifies the real
repo or the source worker_runs directory.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import handoff_notes
from core.handoff_notes import _slug  # type: ignore[attr-defined]


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKER_RUNS_ROOT = PROJECT_ROOT / ".agent" / "worker_runs"
DEFAULT_PROPOSALS_ROOT = PROJECT_ROOT / ".agent" / "proposals"

RAW_OUTPUT_PREVIEW_CHARS = 2000
_RAW_OUTPUT_TRUNCATION_MARKER = "\n…[truncated]\n"

REQUIRED_FILES_FOR_IMPORT: tuple[str, ...] = (
    "handoff.md",
    "worker_run.json",
    "proposal.md",
    "patch_plan.json",
)
_OPTIONAL_COPIED_FILES: tuple[str, ...] = ("raw_output.txt",)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_worker_runs_root(root: Path | None) -> Path:
    target = Path(root) if root is not None else DEFAULT_WORKER_RUNS_ROOT
    target.mkdir(parents=True, exist_ok=True)
    return target


def _resolve_proposals_root(root: Path | None) -> Path:
    target = Path(root) if root is not None else DEFAULT_PROPOSALS_ROOT
    target.mkdir(parents=True, exist_ok=True)
    return target


def _resolve_run_dir(path_or_id: str | Path, root: Path) -> Path:
    """Path-traversal guard. Returns a directory strictly under `root`."""
    raw = str(path_or_id).strip()
    if not raw:
        raise ValueError("worker run path/id is empty")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.expanduser().resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"worker run path is outside {root_resolved}: {candidate}"
        ) from exc
    if not candidate.is_dir():
        raise FileNotFoundError(f"worker run directory not found: {candidate}")
    return candidate


def _parse_worker_run_json(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "worker_run.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _parse_handoff_title(run_dir: Path) -> str | None:
    handoff_path = run_dir / "handoff.md"
    if not handoff_path.is_file():
        return None
    try:
        text = handoff_path.read_text(encoding="utf-8")
        meta, _body = handoff_notes._parse_meta_and_body(text)  # type: ignore[attr-defined]
        title = meta.get("title")
        return title if isinstance(title, str) and title.strip() else None
    except (OSError, ValueError):
        return None


def _raw_output_preview(run_dir: Path) -> str:
    path = run_dir / "raw_output.txt"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) <= RAW_OUTPUT_PREVIEW_CHARS:
        return text
    return text[:RAW_OUTPUT_PREVIEW_CHARS] + _RAW_OUTPUT_TRUNCATION_MARKER


def detect_worker_outputs(
    run_dir: str | Path,
    worker_runs_root: Path | None = None,
) -> dict[str, Any]:
    root = _resolve_worker_runs_root(worker_runs_root)
    resolved = _resolve_run_dir(run_dir, root)
    presence = {f: (resolved / f).is_file() for f in REQUIRED_FILES_FOR_IMPORT}
    missing = [f for f, present in presence.items() if not present]
    return {
        "has_handoff_md": presence["handoff.md"],
        "has_worker_run_json": presence["worker_run.json"],
        "has_proposal_md": presence["proposal.md"],
        "has_patch_plan_json": presence["patch_plan.json"],
        "missing": missing,
        "complete": not missing,
    }


def _build_run_summary(
    run_dir: Path,
    *,
    include_preview: bool,
) -> dict[str, Any]:
    record = _parse_worker_run_json(run_dir)
    detect = detect_worker_outputs(run_dir, worker_runs_root=run_dir.parent)
    started = record.get("started_at")
    summary: dict[str, Any] = {
        "run_id": run_dir.name,
        "path": str(run_dir),
        # Legacy /worker-runs/list compatibility fields:
        "artifact_dir": str(run_dir),
        "name": run_dir.name,
        # worker_run.json fields:
        "dry_run": record.get("dry_run"),
        "worker": record.get("worker"),
        "command": record.get("command"),
        "exit_code": record.get("exit_code"),
        "timed_out": record.get("timed_out"),
        "duration_sec": record.get("duration_sec"),
        "handoff_path": record.get("handoff_path"),
        "started_at": started,
        "finished_at": record.get("finished_at"),
        "error": record.get("error"),
        "created_at": started,
        # detect_worker_outputs fields:
        "has_proposal_md": detect["has_proposal_md"],
        "has_patch_plan_json": detect["has_patch_plan_json"],
        "has_handoff_md": detect["has_handoff_md"],
        "has_worker_run_json": detect["has_worker_run_json"],
        # parsed:
        "handoff_title": _parse_handoff_title(run_dir),
    }
    if include_preview:
        summary["raw_output_preview"] = _raw_output_preview(run_dir)
    return summary


def list_worker_runs(
    worker_runs_root: Path | None = None,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    root = _resolve_worker_runs_root(worker_runs_root)
    if not root.is_dir():
        return []
    try:
        dirs = sorted(
            (d for d in root.iterdir() if d.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for d in dirs:
        if not (d / "worker_run.json").is_file():
            continue
        out.append(_build_run_summary(d, include_preview=False))
        if len(out) >= max(1, limit):
            break
    return out


def read_worker_run(
    path_or_id: str | Path,
    worker_runs_root: Path | None = None,
) -> dict[str, Any]:
    root = _resolve_worker_runs_root(worker_runs_root)
    resolved = _resolve_run_dir(path_or_id, root)
    return _build_run_summary(resolved, include_preview=True)


def _proposal_destination(
    proposals_root: Path,
    slug: str,
) -> Path:
    now = datetime.now(timezone.utc)
    base_run = proposals_root / now.strftime("%Y%m%d_%H%M%S")
    suffix = 0
    run = base_run
    while run.exists():
        suffix += 1
        run = proposals_root / f"{now.strftime('%Y%m%d_%H%M%S')}-{suffix}"
    item_dir = run / f"01-{slug}"
    item_dir.mkdir(parents=True, exist_ok=False)
    return item_dir


def import_worker_run_as_proposal(
    run_dir: str | Path,
    worker_runs_root: Path | None = None,
    proposals_root: Path | None = None,
) -> dict[str, Any]:
    runs_root = _resolve_worker_runs_root(worker_runs_root)
    resolved = _resolve_run_dir(run_dir, runs_root)

    detect = detect_worker_outputs(resolved, worker_runs_root=runs_root)
    if not detect["complete"]:
        raise FileNotFoundError(
            f"worker run is incomplete: missing {', '.join(detect['missing'])}"
        )

    record = _parse_worker_run_json(resolved)
    if record.get("dry_run") is True:
        raise ValueError(
            "cannot import a dry-run worker output as a proposal"
        )

    title = _parse_handoff_title(resolved) or resolved.name
    slug = _slug(title)
    proposals_dst_root = _resolve_proposals_root(proposals_root)
    item_dir = _proposal_destination(proposals_dst_root, slug)

    imported_files: list[str] = []
    for filename in REQUIRED_FILES_FOR_IMPORT:
        shutil.copy2(resolved / filename, item_dir / filename)
        imported_files.append(filename)
    for filename in _OPTIONAL_COPIED_FILES:
        src = resolved / filename
        if src.is_file():
            shutil.copy2(src, item_dir / filename)
            imported_files.append(filename)

    now_iso = _now_iso()
    item = {
        "kind": "worker_run_import",
        "source": "worker_run",
        "source_run_id": resolved.name,
        "source_run_dir": str(resolved),
        "title": title,
        "worker": record.get("worker"),
        "imported_at": now_iso,
        "human_approved_for_proposal": False,
        "needs_revalidation": True,
    }
    source_metadata = {
        "source": "worker_run",
        "source_run_id": resolved.name,
        "source_run_dir": str(resolved),
        "handoff_path": record.get("handoff_path"),
        "worker": record.get("worker"),
        "command": record.get("command"),
        "imported_at": now_iso,
        "imported_files": imported_files,
    }
    (item_dir / "item.json").write_text(
        json.dumps(item, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    (item_dir / "source_metadata.json").write_text(
        json.dumps(source_metadata, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "proposal_dir": str(item_dir),
        "source_run_dir": str(resolved),
        "source_run_id": resolved.name,
        "item": item,
        "imported_at": now_iso,
    }
```

4. **Run the tests** — expect ~16 passing.

5. **Commit** — stage `core/worker_runs.py` and `tests/test_worker_runs.py` only.

```
feat(worker_runs): list/read/detect/import worker run artifacts as proposals

Pure storage + validation layer. Imports a complete worker run from
.agent/worker_runs/<run>/ into .agent/proposals/<run>/01-<slug>/ with a
synthetic item.json marking source=worker_run and needs_revalidation=true,
keeping the proposal -> lesson safety story intact (no auto-promotion;
operator must re-run through validation before lesson candidacy).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task B — Refactor `/worker-runs/list` to delegate

**Files:**
- Modify: `web/app.py`

The legacy `/worker-runs/list` handler reads the directory manually. Replace its body with a call to `core.worker_runs.list_worker_runs()`. The response shape stays identical because `list_worker_runs` is a strict superset of the legacy keys.

### TDD step list

1. **Verify the legacy shape contract** by extending an existing handoff routes test to assert the keys still exist after refactor. In `tests/test_handoff_routes.py`, augment `test_worker_runs_list_returns_recent_runs`:

After the existing `assert "dry_run" in body["runs"][0]`, add:

```python
    for legacy_key in ("artifact_dir", "name", "worker", "exit_code",
                       "timed_out", "duration_sec", "command",
                       "started_at", "finished_at", "error"):
        assert legacy_key in body["runs"][0], f"missing legacy key: {legacy_key}"
```

2. **Run the test** — should pass before the refactor (legacy code already returns these keys).

3. **Refactor `worker_runs_list_route` in `web/app.py`** (around line 1674-1706). Replace the body with:

```python
@app.route("/worker-runs/list", methods=["GET"])
def worker_runs_list_route():
    from core import worker_runs as _worker_runs
    try:
        runs = _worker_runs.list_worker_runs(
            worker_runs_root=_handoff_runner.WORKER_RUNS_ROOT,
        )
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {"ok": True, "runs": runs}
```

4. **Run the test** — should still pass; new behavior is a strict superset.

5. **Commit** — `web/app.py` and `tests/test_handoff_routes.py`.

```
refactor(web): /worker-runs/list now delegates to core.worker_runs.list_worker_runs

Preserves legacy response shape; new fields (run_id, handoff_title,
has_proposal_md, has_patch_plan_json, raw_output_preview omitted from list)
are additive. Behavior verified by extending test_worker_runs_list_returns_recent_runs.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task C — Add `/worker-runs/view` and `/worker-runs/import` routes

**Files:**
- Modify: `web/app.py`
- Create: `tests/test_worker_runs_routes.py`

### TDD step list

1. **Write the failing tests** in `tests/test_worker_runs_routes.py`:

```python
"""Phase 7.2 — Flask client tests for /worker-runs/view and /worker-runs/import."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import handoff_notes, worker_runs
from scripts import run_subagent_handoff as runner


@pytest.fixture
def client(tmp_path, monkeypatch):
    worker_runs_root = tmp_path / "worker_runs"
    proposals_root = tmp_path / "proposals"
    handoff_root = tmp_path / "handoffs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(worker_runs, "DEFAULT_WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(worker_runs, "DEFAULT_PROPOSALS_ROOT", proposals_root)
    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "WORKER_RUNS_ROOT", worker_runs_root)
    monkeypatch.setattr(runner, "HANDOFF_ROOT", handoff_root)

    from web import app as web_app
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        c._worker_runs_root = worker_runs_root  # type: ignore[attr-defined]
        c._proposals_root = proposals_root  # type: ignore[attr-defined]
        c._handoff_root = handoff_root  # type: ignore[attr-defined]
        c._fake_repo = fake_repo  # type: ignore[attr-defined]
        yield c


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_complete_run(client, run_id="20260521_010203_imp", title="Import me"):
    note = handoff_notes.create_handoff_note(
        title=title,
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(client._fake_repo),
        handoff_root=client._handoff_root,
    )
    handoff_text = Path(note["path"]).read_text(encoding="utf-8")
    run_dir = client._worker_runs_root / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "handoff.md").write_text(handoff_text, encoding="utf-8")
    _write_json(run_dir / "worker_run.json", {
        "dry_run": False, "worker": "codex", "command": "codex exec --full-auto",
        "exit_code": 0, "timed_out": False, "duration_sec": 5.0,
        "started_at": "2026-05-21T01:02:03+00:00",
        "finished_at": "2026-05-21T01:02:08+00:00",
        "handoff_path": note["path"],
        "artifact_dir": str(run_dir), "timeout_sec": 300, "error": None,
    })
    (run_dir / "raw_output.txt").write_text("hello world", encoding="utf-8")
    (run_dir / "worker_command.txt").write_text("codex exec --full-auto\n", encoding="utf-8")
    (run_dir / "proposal.md").write_text("# proposal\n", encoding="utf-8")
    _write_json(run_dir / "patch_plan.json", [{"op": "noop"}])
    return run_dir


def test_view_returns_full_detail(client):
    _make_complete_run(client, run_id="20260521_010203_view", title="V")
    resp = client.get("/worker-runs/view?run_id=20260521_010203_view")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    run = body["run"]
    assert run["run_id"] == "20260521_010203_view"
    assert run["handoff_title"] == "V"
    assert run["has_proposal_md"] is True
    assert "raw_output_preview" in run


def test_view_rejects_path_traversal(client, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "worker_run.json").write_text("{}", encoding="utf-8")
    resp = client.get(f"/worker-runs/view?path={outside.as_posix()}")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "outside" in body["error"]


def test_view_missing_run_returns_404(client):
    resp = client.get("/worker-runs/view?run_id=20260521_000000_nope")
    assert resp.status_code == 404


def test_view_requires_run_id_or_path(client):
    resp = client.get("/worker-runs/view")
    assert resp.status_code == 400


def _repo_state(repo: Path) -> dict[str, str]:
    return {
        p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in repo.rglob("*") if p.is_file()
    }


def test_import_creates_proposal_and_does_not_modify_real_repo(client):
    _make_complete_run(client, run_id="20260521_010203_imp", title="Imp")
    before = _repo_state(client._fake_repo)

    resp = client.post("/worker-runs/import",
                       data={"run_id": "20260521_010203_imp"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    proposal_dir = Path(body["proposal_dir"])
    assert proposal_dir.is_dir()
    assert (proposal_dir / "proposal.md").is_file()
    assert (proposal_dir / "patch_plan.json").is_file()
    assert (proposal_dir / "item.json").is_file()
    assert body["source_run_id"] == "20260521_010203_imp"

    after = _repo_state(client._fake_repo)
    assert before == after, "real repo unchanged by import"


def test_import_refuses_incomplete_run(client):
    run_dir = client._worker_runs_root / "20260521_010203_inc"
    run_dir.mkdir(parents=True)
    _write_json(run_dir / "worker_run.json", {"dry_run": False, "worker": "codex"})
    (run_dir / "handoff.md").write_text("x", encoding="utf-8")
    # no proposal.md, no patch_plan.json

    resp = client.post("/worker-runs/import",
                       data={"run_id": "20260521_010203_inc"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "incomplete" in body["error"]
    assert "proposal.md" in body["error"]
    assert "patch_plan.json" in body["error"]


def test_import_refuses_dry_run(client):
    _make_complete_run(client, run_id="20260521_010203_dry", title="D")
    # Flip the run to dry_run=True after creation.
    run_json_path = client._worker_runs_root / "20260521_010203_dry" / "worker_run.json"
    record = json.loads(run_json_path.read_text(encoding="utf-8"))
    record["dry_run"] = True
    run_json_path.write_text(json.dumps(record), encoding="utf-8")

    resp = client.post("/worker-runs/import",
                       data={"run_id": "20260521_010203_dry"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "dry-run" in body["error"]


def test_import_requires_run_id_or_path(client):
    resp = client.post("/worker-runs/import", data={})
    assert resp.status_code == 400
```

2. **Run the tests** — expect 404 / route-not-found failures.

3. **Add the routes** in `web/app.py` immediately after `worker_runs_list_route`:

```python
@app.route("/worker-runs/view", methods=["GET"])
def worker_runs_view_route():
    from core import worker_runs as _worker_runs
    run_id = (request.values.get("run_id") or "").strip()
    path = (request.values.get("path") or "").strip()
    if not run_id and not path:
        return {"ok": False, "error": "run_id or path is required"}, 400
    target = path or run_id
    try:
        run = _worker_runs.read_worker_run(
            target,
            worker_runs_root=_handoff_runner.WORKER_RUNS_ROOT,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}, 404
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {"ok": True, "run": run}


@app.route("/worker-runs/import", methods=["POST"])
def worker_runs_import_route():
    from core import worker_runs as _worker_runs
    run_id = (request.form.get("run_id") or "").strip()
    path = (request.form.get("path") or "").strip()
    if not run_id and not path:
        return {"ok": False, "error": "run_id or path is required"}, 400
    target = path or run_id
    try:
        result = _worker_runs.import_worker_run_as_proposal(
            target,
            worker_runs_root=_handoff_runner.WORKER_RUNS_ROOT,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}, 400
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {
        "ok": True,
        "proposal_dir": result["proposal_dir"],
        "source_run_id": result["source_run_id"],
        "item": result["item"],
    }
```

4. **Run the tests** — expect all green.

5. **Commit** — `web/app.py` and `tests/test_worker_runs_routes.py`.

```
feat(web): add /worker-runs/view + /worker-runs/import routes

view: returns full read_worker_run() detail by run_id or path,
with path-traversal guard and 404 for missing runs.
import: turns a complete (non-dry-run) worker_run into a proposal
artifact under .agent/proposals/<run>/01-<slug>/. Refuses incomplete
or dry-run worker outputs. Real repo unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task D — UI: Worker Runs subsection inside Mayor Mode panel

**Files:**
- Modify: `web/templates/index.html`

### Step 1 — Find the seam

Run: `python -c "import re; t=open('web/templates/index.html', encoding='utf-8').read(); ls=t.splitlines(); idx=[(i, l) for i, l in enumerate(ls, 1) if 'handoffsList' in l]; print(idx)"`

Insert the new Worker Runs subsection HTML immediately after the closing `</div>` of the `handoffs-section` (the line right after `<div id="handoffsList"` block ends with `</div></div>`).

### Step 2 — Add the HTML

Add this block as a sibling inside the Memory tab, immediately after the `handoffs-section` div:

```html
<!-- Phase 7.2: Worker Runs review/import.
     Reads .agent/worker_runs/. Importing a complete run lands a fresh
     artifact in .agent/proposals/<run>/01-<slug>/ which then flows through
     the existing proposal -> lesson review. No real-repo writes. -->
<div class="memory-section worker-runs-section">
  <div class="proposals-header">
    <h3>Worker Runs</h3>
    <button type="button" class="memory-refresh" onclick="refreshWorkerRuns()"
            title="Re-scan .agent/worker_runs/">⟳ Refresh</button>
  </div>
  <div class="proposals-note">
    Subagent runs from <code>.agent/worker_runs/</code>. Importing a
    complete (non-dry-run) run surfaces it in the Proposals section above
    so you can review the patch_plan.json before any lesson promotion.
  </div>
  <div id="workerRunsStatus" class="proposals-status"></div>
  <div id="workerRunsList" class="proposals-list">
    <div class="health-empty">Click ⟳ Refresh to load worker runs.</div>
  </div>
</div>
```

### Step 3 — Add the JS

After the `runHandoff` function in the template's JS block, add:

```javascript
// Phase 7.2 — Worker runs review/import
async function refreshWorkerRuns() {
  const status = document.getElementById("workerRunsStatus");
  const list = document.getElementById("workerRunsList");
  if (status) status.textContent = "Loading worker runs...";
  try {
    const resp = await fetch("/worker-runs/list");
    const body = await resp.json();
    if (!body.ok) {
      if (status) status.textContent = "Error: " + (body.error || "unknown");
      return;
    }
    if (!list) return;
    if (!body.runs || body.runs.length === 0) {
      list.innerHTML = '<div class="health-empty">No worker runs yet. Use Mayor Mode above to create + run a handoff.</div>';
      if (status) status.textContent = "";
      return;
    }
    list.innerHTML = body.runs.map(r => {
      const importBtn = (r.has_proposal_md && r.has_patch_plan_json && r.dry_run !== true)
        ? `<button type="button" onclick="importWorkerRun('${_escapeHtml(r.run_id).replace(/'/g, "\\'")}', this)">Import as proposal</button>`
        : `<button type="button" disabled title="Import disabled — missing proposal.md / patch_plan.json or run was dry-run">Import as proposal</button>`;
      const dryBadge = r.dry_run ? ` · <strong style="color:#a16207">DRY RUN</strong>` : "";
      const exitBadge = (r.exit_code !== null && r.exit_code !== undefined)
        ? ` · exit ${_escapeHtml(String(r.exit_code))}`
        : "";
      const propBadge = r.has_proposal_md ? "proposal.md ✓" : "proposal.md ✗";
      const planBadge = r.has_patch_plan_json ? "patch_plan.json ✓" : "patch_plan.json ✗";
      return `
        <div class="worker-run-item" data-run-id="${_escapeHtml(r.run_id)}" style="margin-bottom:12px; padding:12px; border:1px solid #e2e8f0; border-radius:6px; background:#f8fafc;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <strong>${_escapeHtml(r.handoff_title || r.run_id || "(unnamed)")}</strong>
            <span style="font-size:11px; color:#64748b;">${_escapeHtml(r.run_id || "")}</span>
          </div>
          <div style="font-size:12px; color:#64748b; margin-bottom:8px;">
            worker: <code>${_escapeHtml(r.worker || "?")}</code>${dryBadge}${exitBadge}
            · ${_escapeHtml(propBadge)} · ${_escapeHtml(planBadge)}
          </div>
          <div style="display:flex; gap:8px;">
            <button type="button" class="lesson-btn--secondary" onclick="viewWorkerRun('${_escapeHtml(r.run_id).replace(/'/g, "\\'")}', this)">View details</button>
            ${importBtn}
          </div>
          <div class="worker-run-detail" style="display:none; margin-top:10px; padding:8px; background:#fff; border:1px solid #e2e8f0; border-radius:4px; font-size:12px;"></div>
        </div>
      `;
    }).join("");
    if (status) status.textContent = `${body.runs.length} run(s).`;
  } catch (e) {
    if (status) status.textContent = "Error: " + e.message;
  }
}

async function viewWorkerRun(runId, btn) {
  const card = btn.closest(".worker-run-item");
  const detail = card.querySelector(".worker-run-detail");
  if (detail.style.display === "block") {
    detail.style.display = "none";
    return;
  }
  detail.textContent = "Loading...";
  detail.style.display = "block";
  try {
    const resp = await fetch("/worker-runs/view?run_id=" + encodeURIComponent(runId));
    const body = await resp.json();
    if (!body.ok) {
      detail.textContent = "Error: " + (body.error || "unknown");
      return;
    }
    const r = body.run;
    const preview = (r.raw_output_preview || "").substring(0, 1500);
    detail.innerHTML = `
      <div><strong>command:</strong> <code>${_escapeHtml(r.command || "")}</code></div>
      <div><strong>started:</strong> ${_escapeHtml(r.started_at || "")} · <strong>duration:</strong> ${_escapeHtml(String(r.duration_sec || ""))}s</div>
      <div style="margin-top:6px;"><strong>raw output (preview):</strong></div>
      <pre style="max-height:240px; overflow:auto; background:#0f172a; color:#e2e8f0; padding:8px; border-radius:4px; font-size:11px; white-space:pre-wrap;">${_escapeHtml(preview)}</pre>
    `;
  } catch (e) {
    detail.textContent = "Error: " + e.message;
  }
}

async function importWorkerRun(runId, btn) {
  const status = document.getElementById("workerRunsStatus");
  btn.disabled = true;
  if (status) status.textContent = "Importing " + runId + "...";
  try {
    const fd = new FormData();
    fd.append("run_id", runId);
    const resp = await fetch("/worker-runs/import", { method: "POST", body: fd });
    const body = await resp.json();
    if (!body.ok) {
      if (status) status.textContent = "Import failed: " + (body.error || "unknown");
      btn.disabled = false;
      return;
    }
    if (status) {
      status.innerHTML = `Imported to <code>${_escapeHtml(body.proposal_dir)}</code>. ` +
        `Refresh the Proposals section above to review before any lesson promotion.`;
    }
    if (typeof refreshProposals === "function") refreshProposals();
  } catch (e) {
    if (status) status.textContent = "Error: " + e.message;
    btn.disabled = false;
  }
}
```

### Step 4 — Smoke test

Run `python web/app.py`, open `http://127.0.0.1:5000`, go to Memory tab, expand Mayor Mode (Handoffs), and below it should be the new "Worker Runs" subsection. Click Refresh — if no worker runs exist yet, you should see the empty-state message.

If a worker_runs/ entry exists from earlier testing, the list should populate. View details should expand inline; Import as proposal should be disabled for dry-run / incomplete runs and enabled for complete real runs.

### Step 5 — Commit

```
feat(ui): Worker Runs subsection in Memory tab (view + import)

New panel under Mayor Mode listing .agent/worker_runs/ with View details
(inline raw output preview + command + duration) and Import as proposal
(disabled when proposal.md/patch_plan.json are missing or the run was a
dry-run). After import, points the operator at the Proposals section
for review before any lesson promotion.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Task E — Roadmap entry

**Files:**
- Modify: `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`

At the end of the file, append:

```markdown

---

## Phase 7.2 — Worker Run Review / Import (shipped 2026-05-21)

Spec: `docs/superpowers/specs/2026-05-21-phase-7-2-worker-run-review-design.md`
Plan: `docs/superpowers/plans/2026-05-21-phase-7-2-worker-run-review.md`

The bridge from Phase 7.1 worker outputs into the existing proposal review path. No execution, no validation, no apply.

### What this phase adds

- `core/worker_runs.py` — pure storage + validation. `list_worker_runs`, `read_worker_run`, `detect_worker_outputs`, `import_worker_run_as_proposal`. Path-traversal guarded against escaping `.agent/worker_runs/`. Never writes outside the new proposal dir.
- Web routes: `GET /worker-runs/view`, `POST /worker-runs/import`. `GET /worker-runs/list` refactored to delegate, preserving its legacy response shape.
- Memory tab: new "Worker Runs" subsection under Mayor Mode with View details (inline raw output preview) and Import as proposal (button disabled for dry-run / incomplete runs).
- Imported proposals land in `.agent/proposals/<run>/01-<slug>/` with a synthetic `item.json` (`source=worker_run`, `human_approved_for_proposal=false`, `needs_revalidation=true`) and a `source_metadata.json` pointing back to the original `worker_runs/` dir. The four required files (`handoff.md`, `worker_run.json`, `proposal.md`, `patch_plan.json`) plus optional `raw_output.txt` are copied across.
- Tests: ~20 covering list/read/detect/import + the 3 routes. Real-repo SHA-256 byte-identical assertion in the import tests.

### Guardrails (verified by tests)

- Subagents do not run in this slice.
- Worker output is never auto-applied to the real repo.
- Imported proposals carry `human_approved_for_proposal=false`, so `scripts/run_patch_proposal_queue.py` will skip them by default.
- The lesson-promotion path is unchanged: a worker-run import is intentionally NOT directly promotable because it lacks `apply_result.json` / `validation.json` / `case.json`. The operator must re-run through validation first.
- Patch Safety gate is unchanged.

### 🤖 Claude-proposed Phase 7.2.1+ follow-ups (pending user decision)

1. **Re-validate worker patch_plan in a temp clone.** The natural next slice. Takes an imported worker-run proposal, applies the patch_plan in a temp clone, runs a user-supplied or detected validation command, and stamps the proposal with `apply_result.json` + `validation.json` — at which point it becomes lesson-promotable like any other proposal.
2. **Diff preview against real repo.** Compute `git diff` between real repo state and the worker's patch_plan before import, so the operator can eyeball the change inline.
3. **Idempotency / dedup.** Hash the worker run's `(handoff.md + patch_plan.json)` and refuse re-import if the same proposal already exists.
4. **"Imported from worker_run" badge in the Proposals list.** The list view currently treats worker-run imports the same as normal proposals (because `item.json` is structurally compatible). A small visual badge would surface provenance.
5. **Tail-streaming raw_output.** For long worker runs, the inline preview is capped at 2000 chars. A "show full output" toggle that fetches the file in chunks would help debug timeouts.
```

Commit:

```
docs(roadmap): record Phase 7.2 Worker Run Review/Import shipment + 7.2.1 follow-ups

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Self-review checklist

- **Spec coverage:** core module functions ↔ Task A, route additions ↔ Tasks B+C, UI ↔ Task D, roadmap ↔ Task E. All four spec sections mapped.
- **No placeholders:** every step has the actual code or the exact command.
- **Type consistency:** `import_worker_run_as_proposal` returns `proposal_dir`, `source_run_dir`, `source_run_id`, `item`, `imported_at` — the same keys appear in the route response and the test assertions.
- **Stage discipline reminder for each commit:** only stage the files the task touched. No prior dirty files in the working tree right now, but staying explicit is cheap.

---

## Execution

Following the same pattern as 7.1: 5 tasks, TDD per task, one commit per task. Spec/plan are already on disk via this plan. The implementation will proceed inline through Tasks A → E.
