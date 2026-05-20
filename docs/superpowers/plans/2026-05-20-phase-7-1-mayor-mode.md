# Phase 7.1 — Mayor Mode handoff + optional subagent runner (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Mayor Mode handoff system: operators can create bounded handoff notes for external agents (Codex / Claude Code / Gemini / other), and optionally run those agents in a temp clone — never against the real repo, never auto-applying patches.

**Architecture:** Three Python layers (`core/handoff_notes.py` pure storage, `scripts/create_handoff_note.py` CLI, `scripts/run_subagent_handoff.py` temp-clone runner) + four Flask routes + a Memory-tab UI panel. JSON-frontmatter markdown notes under `<AI-project>/.agent/handoffs/`; run artifacts under `<AI-project>/.agent/worker_runs/`. All path-traversal guarded.

**Tech Stack:** Python 3.10+, Flask (existing), pytest. Re-uses `core/brain_stamp.collect_brain_stamp`, the project's `_safe_rel_path` / path-traversal conventions, and `subprocess.run` with timeout. **No new pip dependencies.**

---

## File map

**Create:**
- `core/handoff_notes.py` — pure storage + validation
- `scripts/create_handoff_note.py` — CLI wrapper
- `scripts/run_subagent_handoff.py` — temp-clone runner with dry-run default
- `tests/test_handoff_notes.py` — unit tests for the core module
- `tests/test_run_subagent_handoff.py` — unit tests for the runner script
- `tests/test_handoff_routes.py` — Flask client tests for the four routes

**Modify:**
- `web/app.py` — append four route handlers after the existing `/proposals/promote` route
- `web/templates/index.html` — append a new `memory-section handoffs-section` block between `proposals-section` and `lessons-section`
- `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md` — append a Phase 7.1 status block

Total new lines (estimated): ~900 (core 250, scripts 450, tests 550, web 200, template 250).

---

## Task 1 — Skeleton: `core/handoff_notes.py` constants + helpers

**Files:**
- Create: `core/handoff_notes.py`
- Create: `tests/test_handoff_notes.py`

- [ ] **Step 1: Write the failing test**

`tests/test_handoff_notes.py`:
```python
"""Phase 7.1 — unit tests for core/handoff_notes.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import handoff_notes


def test_module_constants_are_correct():
    assert handoff_notes.VALID_WORKERS == {"codex", "claude-code", "gemini", "other"}
    assert handoff_notes.VALID_TASK_TYPES == {
        "proposal_only",
        "review_only",
        "explain_only",
        "benchmark_case",
        "research",
    }
    assert handoff_notes.VALID_STATUSES == {"draft", "ran", "failed", "archived"}
    assert "proposal only" in handoff_notes.DEFAULT_SAFETY_RULES
    assert "do not commit" in handoff_notes.DEFAULT_SAFETY_RULES
    assert ".env" in handoff_notes.DEFAULT_FORBIDDEN_FILES
    assert ".agent" in handoff_notes.DEFAULT_FORBIDDEN_FILES


def test_slug_alphanumeric():
    assert handoff_notes._slug("Fix Flaky Fixtures!") == "fix-flaky-fixtures"


def test_slug_collapses_separators():
    assert handoff_notes._slug("foo___bar---baz") == "foo-bar-baz"


def test_slug_truncates_to_60_chars():
    long = "a" * 200
    assert len(handoff_notes._slug(long)) == 60


def test_slug_fallback_when_empty():
    assert handoff_notes._slug("!!!") == "handoff"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_handoff_notes.py -v`
Expected: `ModuleNotFoundError: No module named 'core.handoff_notes'`

- [ ] **Step 3: Write minimal implementation**

`core/handoff_notes.py`:
```python
"""Phase 7.1 — bounded handoff notes for external coding agents.

Pure storage + validation. No subprocess, no Flask. Notes are markdown files
with JSON frontmatter under `<AI-project>/.agent/handoffs/`. Run artifacts
live elsewhere (see `scripts/run_subagent_handoff.py`).

Safety policy (enforced here, not at runtime):
  - notes default to proposal-only / do-not-apply / do-not-commit
  - default forbidden_files list always includes .env/.agent/.git/etc.
  - allowed_files entries that overlap defaults are recorded as
    safety_overrides for audit
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HANDOFF_ROOT = PROJECT_ROOT / ".agent" / "handoffs"


VALID_WORKERS = {"codex", "claude-code", "gemini", "other"}
VALID_TASK_TYPES = {
    "proposal_only",
    "review_only",
    "explain_only",
    "benchmark_case",
    "research",
}
VALID_STATUSES = {"draft", "ran", "failed", "archived"}

DEFAULT_SAFETY_RULES: list[str] = [
    "proposal only",
    "do not apply patch",
    "do not commit",
    "do not push",
    "do not edit .env/.agent/.git/node_modules/target/tests unless explicitly allowed",
    "return proposal.md and patch_plan.json if possible",
]

DEFAULT_FORBIDDEN_FILES: list[str] = [
    ".env",
    ".agent",
    ".git",
    "node_modules",
    "target",
    "tests",
]


def _slug(text: str, fallback: str = "handoff") -> str:
    out: list[str] = []
    for ch in (text or "").lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    value = "".join(out).strip("-")
    return value[:60] or fallback
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_handoff_notes.py -v`
Expected: 5 passing.

- [ ] **Step 5: Commit**

```bash
git add core/handoff_notes.py tests/test_handoff_notes.py
git commit -m "feat(handoff): scaffold core/handoff_notes constants + _slug helper"
```

---

## Task 2 — `create_handoff_note` writes a parseable note

**Files:**
- Modify: `core/handoff_notes.py`
- Modify: `tests/test_handoff_notes.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_handoff_notes.py`:
```python
@pytest.fixture
def handoff_root(tmp_path: Path) -> Path:
    return tmp_path / "handoffs"


def test_create_handoff_note_writes_file_with_expected_metadata(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="Fix flaky fixtures",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=None,
        allowed_files=["core/foo.py"],
        validation_command="python -m pytest tests/test_foo.py -v",
        context_summary="The foo module fixtures are flaky.",
        expected_output="proposal.md and patch_plan.json",
        handoff_root=handoff_root,
    )

    assert result["meta"]["title"] == "Fix flaky fixtures"
    assert result["meta"]["intended_worker"] == "codex"
    assert result["meta"]["task_type"] == "proposal_only"
    assert result["meta"]["status"] == "draft"
    assert result["meta"]["owner"] == "human"
    assert result["meta"]["allowed_files"] == ["core/foo.py"]

    path = Path(result["path"])
    assert path.is_file()
    assert path.parent == handoff_root
    assert path.suffix == ".md"
    assert "fix-flaky-fixtures" in path.name


def test_create_handoff_note_includes_default_safety_rules(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="t",
        intended_worker="codex",
        task_type="proposal_only",
        handoff_root=handoff_root,
    )
    rules = result["meta"]["safety_rules"]
    for required in handoff_notes.DEFAULT_SAFETY_RULES:
        assert required in rules


def test_create_handoff_note_merges_default_forbidden_files(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="t",
        intended_worker="codex",
        task_type="proposal_only",
        forbidden_files=["my_secrets.txt"],
        handoff_root=handoff_root,
    )
    forbidden = set(result["meta"]["forbidden_files"])
    assert "my_secrets.txt" in forbidden
    for d in handoff_notes.DEFAULT_FORBIDDEN_FILES:
        assert d in forbidden


def test_create_handoff_note_records_safety_override_when_allowed_overlaps(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="t",
        intended_worker="codex",
        task_type="proposal_only",
        allowed_files=["tests/test_foo.py"],
        handoff_root=handoff_root,
    )
    assert "tests/test_foo.py" in result["meta"]["safety_overrides"]
    assert "tests" not in [
        p for p in result["meta"]["forbidden_files"] if p == "tests/test_foo.py"
    ]


def test_create_handoff_note_rejects_unknown_worker(handoff_root):
    with pytest.raises(ValueError, match="intended_worker"):
        handoff_notes.create_handoff_note(
            title="t",
            intended_worker="nope",
            task_type="proposal_only",
            handoff_root=handoff_root,
        )


def test_create_handoff_note_rejects_unknown_task_type(handoff_root):
    with pytest.raises(ValueError, match="task_type"):
        handoff_notes.create_handoff_note(
            title="t",
            intended_worker="codex",
            task_type="bogus",
            handoff_root=handoff_root,
        )


def test_create_handoff_note_rejects_empty_title(handoff_root):
    with pytest.raises(ValueError, match="title"):
        handoff_notes.create_handoff_note(
            title="   ",
            intended_worker="codex",
            task_type="proposal_only",
            handoff_root=handoff_root,
        )


def test_create_handoff_note_rejects_unsafe_allowed_file(handoff_root):
    with pytest.raises(ValueError, match="allowed_files"):
        handoff_notes.create_handoff_note(
            title="t",
            intended_worker="codex",
            task_type="proposal_only",
            allowed_files=["../escape.txt"],
            handoff_root=handoff_root,
        )


def test_create_handoff_note_body_contains_context_summary(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="t",
        intended_worker="codex",
        task_type="proposal_only",
        context_summary="A unique context phrase ABC123",
        handoff_root=handoff_root,
    )
    text = Path(result["path"]).read_text(encoding="utf-8")
    assert "A unique context phrase ABC123" in text
    assert "## Context summary" in text
    assert "HANDOFF_META" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_handoff_notes.py -v`
Expected: 9 new tests fail with `AttributeError` (no `create_handoff_note`).

- [ ] **Step 3: Write minimal implementation**

Append to `core/handoff_notes.py`:
```python
_HANDOFF_META_RE = re.compile(
    r"<!--HANDOFF_META\s*(?P<json>\{.*?\})\s*HANDOFF_META-->",
    re.DOTALL,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_rel_path(raw: Any) -> str | None:
    text = str(raw or "").strip().replace("\\", "/")
    if not text or text.startswith("/"):
        return None
    parts = [p for p in text.split("/") if p]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def _validate_allowed_files(values: list[str] | None) -> list[str]:
    if not values:
        return []
    safe: list[str] = []
    for v in values:
        s = _safe_rel_path(v)
        if s is None:
            raise ValueError(f"allowed_files entry is not a safe relative path: {v!r}")
        if s not in safe:
            safe.append(s)
    return safe


def _validate_forbidden_files(values: list[str] | None) -> list[str]:
    if not values:
        return []
    safe: list[str] = []
    for v in values:
        s = _safe_rel_path(v)
        if s is None:
            # forbidden_files can be path prefixes like ".agent" — preserve raw
            text = str(v).strip().replace("\\", "/")
            if text:
                if text not in safe:
                    safe.append(text)
            continue
        if s not in safe:
            safe.append(s)
    return safe


def _merge_forbidden(
    user_forbidden: list[str], allowed: list[str]
) -> tuple[list[str], list[str]]:
    merged = list(user_forbidden)
    for d in DEFAULT_FORBIDDEN_FILES:
        if d not in merged:
            merged.append(d)
    overrides: list[str] = []
    final: list[str] = []
    for entry in merged:
        if any(a == entry or a.startswith(entry + "/") for a in allowed):
            overrides.append(entry)
            continue
        final.append(entry)
    # Allowed entries that are children of defaults: surface override too
    for a in allowed:
        for d in DEFAULT_FORBIDDEN_FILES:
            if (a == d or a.startswith(d + "/")) and a not in overrides:
                overrides.append(a)
    return final, overrides


def _merge_safety_rules(extra: list[str] | None) -> list[str]:
    rules = list(DEFAULT_SAFETY_RULES)
    for r in extra or []:
        s = str(r).strip()
        if s and s not in rules:
            rules.append(s)
    return rules


def _resolve_repo_path(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    return value


def _try_collect_brain_stamp(repo_path: str | None) -> dict[str, Any]:
    try:
        from core.brain_stamp import collect_brain_stamp

        target = repo_path or str(PROJECT_ROOT)
        return collect_brain_stamp(target) or {}
    except Exception:
        return {}


def _render_note_markdown(meta: dict[str, Any], context_summary: str, expected_output: str) -> str:
    meta_json = json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True)
    body_lines = [
        f"<!--HANDOFF_META\n{meta_json}\nHANDOFF_META-->",
        "",
        f"# {meta['title']}",
        "",
        "## Context summary",
        "",
        context_summary.strip() or "_No context summary provided._",
        "",
        "## Expected output",
        "",
        expected_output.strip() or "_No expected output declared._",
        "",
        "## Safety rules (advisory — enforced by the runner script too)",
        "",
    ]
    for rule in meta.get("safety_rules", []):
        body_lines.append(f"- {rule}")
    body_lines += [
        "",
        "## How to run this handoff manually",
        "",
        "Always run inside an isolated temp clone — never against the real repo.",
        "`scripts/run_subagent_handoff.py` does this for you when invoked",
        "with `--allow-run`.",
        "",
    ]
    return "\n".join(body_lines) + "\n"


def _resolve_handoff_root(handoff_root: Path | None) -> Path:
    root = Path(handoff_root) if handoff_root is not None else DEFAULT_HANDOFF_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_handoff_note(
    *,
    title: str,
    intended_worker: str,
    task_type: str,
    repo_path: str | None = None,
    allowed_files: list[str] | None = None,
    forbidden_files: list[str] | None = None,
    validation_command: str | None = None,
    context_summary: str = "",
    expected_output: str = "",
    extra_safety_rules: list[str] | None = None,
    handoff_root: Path | None = None,
) -> dict[str, Any]:
    title_clean = (title or "").strip()
    if not title_clean:
        raise ValueError("title must be a non-empty string")
    if intended_worker not in VALID_WORKERS:
        raise ValueError(
            f"intended_worker must be one of {sorted(VALID_WORKERS)}, got {intended_worker!r}"
        )
    if task_type not in VALID_TASK_TYPES:
        raise ValueError(
            f"task_type must be one of {sorted(VALID_TASK_TYPES)}, got {task_type!r}"
        )

    safe_allowed = _validate_allowed_files(allowed_files)
    user_forbidden = _validate_forbidden_files(forbidden_files)
    final_forbidden, overrides = _merge_forbidden(user_forbidden, safe_allowed)
    safety_rules = _merge_safety_rules(extra_safety_rules)
    repo = _resolve_repo_path(repo_path)
    brain_stamp = _try_collect_brain_stamp(repo)

    now = datetime.now(timezone.utc)
    created_iso = now.isoformat(timespec="seconds")
    slug = _slug(title_clean)
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}.md"

    root = _resolve_handoff_root(handoff_root)
    path = root / filename
    suffix = 1
    while path.exists():
        path = root / f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}-{suffix}.md"
        suffix += 1

    meta: dict[str, Any] = {
        "title": title_clean,
        "created_at": created_iso,
        "owner": "human",
        "intended_worker": intended_worker,
        "task_type": task_type,
        "repo_path": repo,
        "allowed_files": safe_allowed,
        "forbidden_files": final_forbidden,
        "validation_command": (validation_command or "").strip() or None,
        "status": "draft",
        "safety_rules": safety_rules,
        "safety_overrides": overrides,
        "slug": slug,
        "brain_stamp": brain_stamp,
    }
    path.write_text(_render_note_markdown(meta, context_summary, expected_output), encoding="utf-8")

    return {"path": str(path), "meta": meta, "slug": slug}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_handoff_notes.py -v`
Expected: 14 passing.

- [ ] **Step 5: Commit**

```bash
git add core/handoff_notes.py tests/test_handoff_notes.py
git commit -m "feat(handoff): create_handoff_note with default safety rules, forbidden-file merge, slug+brain stamp"
```

---

## Task 3 — `list_handoff_notes`, `read_handoff_note`, `update_handoff_status`

**Files:**
- Modify: `core/handoff_notes.py`
- Modify: `tests/test_handoff_notes.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_handoff_notes.py`:
```python
def _create(handoff_root, *, title="t", **kwargs):
    return handoff_notes.create_handoff_note(
        title=title,
        intended_worker="codex",
        task_type="proposal_only",
        handoff_root=handoff_root,
        **kwargs,
    )


def test_list_handoff_notes_returns_newest_first(handoff_root):
    import time

    a = _create(handoff_root, title="first")
    time.sleep(1.1)  # ensure distinct YYYYMMDD_HHMMSS prefix
    b = _create(handoff_root, title="second")
    listing = handoff_notes.list_handoff_notes(handoff_root=handoff_root)
    assert len(listing) == 2
    assert listing[0]["path"] == b["path"]
    assert listing[1]["path"] == a["path"]


def test_list_handoff_notes_excludes_archived_by_default(handoff_root):
    a = _create(handoff_root, title="keep")
    b = _create(handoff_root, title="archived")
    handoff_notes.update_handoff_status(b["path"], "archived", handoff_root=handoff_root)
    visible = handoff_notes.list_handoff_notes(handoff_root=handoff_root)
    paths = [item["path"] for item in visible]
    assert a["path"] in paths
    assert b["path"] not in paths

    everything = handoff_notes.list_handoff_notes(
        handoff_root=handoff_root, include_archived=True
    )
    paths = [item["path"] for item in everything]
    assert b["path"] in paths


def test_read_handoff_note_returns_meta_and_body(handoff_root):
    result = _create(handoff_root, title="readme", context_summary="hello")
    parsed = handoff_notes.read_handoff_note(result["path"], handoff_root=handoff_root)
    assert parsed["meta"]["title"] == "readme"
    assert "hello" in parsed["body"]


def test_read_handoff_note_blocks_path_traversal(handoff_root, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("not a handoff", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        handoff_notes.read_handoff_note(str(outside), handoff_root=handoff_root)


def test_update_handoff_status_writes_new_meta(handoff_root):
    result = _create(handoff_root, title="status-test")
    handoff_notes.update_handoff_status(result["path"], "ran", handoff_root=handoff_root)
    parsed = handoff_notes.read_handoff_note(result["path"], handoff_root=handoff_root)
    assert parsed["meta"]["status"] == "ran"


def test_update_handoff_status_rejects_unknown_status(handoff_root):
    result = _create(handoff_root, title="status-bad")
    with pytest.raises(ValueError, match="status"):
        handoff_notes.update_handoff_status(result["path"], "weird", handoff_root=handoff_root)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_handoff_notes.py -v`
Expected: 6 new tests fail (`AttributeError` for `list_handoff_notes` / `read_handoff_note` / `update_handoff_status`).

- [ ] **Step 3: Write minimal implementation**

Append to `core/handoff_notes.py`:
```python
def _resolve_note_path(raw: str | Path, handoff_root: Path | None) -> Path:
    root = _resolve_handoff_root(handoff_root).resolve()
    candidate = Path(raw).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError(f"handoff note path is outside {root}: {candidate}") from e
    if not candidate.is_file():
        raise FileNotFoundError(f"handoff note not found: {candidate}")
    return candidate


def _parse_meta_and_body(text: str) -> tuple[dict[str, Any], str]:
    match = _HANDOFF_META_RE.search(text)
    if not match:
        raise ValueError("handoff note is missing HANDOFF_META block")
    try:
        meta = json.loads(match.group("json"))
    except json.JSONDecodeError as e:
        raise ValueError(f"handoff note HANDOFF_META is not valid JSON: {e}") from e
    if not isinstance(meta, dict):
        raise ValueError("handoff note HANDOFF_META must be a JSON object")
    body = text[match.end():].lstrip("\n")
    return meta, body


def read_handoff_note(
    path: str | Path,
    handoff_root: Path | None = None,
) -> dict[str, Any]:
    resolved = _resolve_note_path(path, handoff_root)
    text = resolved.read_text(encoding="utf-8")
    meta, body = _parse_meta_and_body(text)
    return {"path": str(resolved), "meta": meta, "body": body, "raw": text}


def list_handoff_notes(
    handoff_root: Path | None = None,
    *,
    limit: int = 50,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    root = _resolve_handoff_root(handoff_root)
    if not root.is_dir():
        return []
    notes: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.md"), reverse=True):
        try:
            text = path.read_text(encoding="utf-8")
            meta, _body = _parse_meta_and_body(text)
        except (OSError, ValueError):
            continue
        if not include_archived and meta.get("status") == "archived":
            continue
        notes.append(
            {
                "path": str(path),
                "title": meta.get("title"),
                "status": meta.get("status"),
                "intended_worker": meta.get("intended_worker"),
                "task_type": meta.get("task_type"),
                "created_at": meta.get("created_at"),
                "slug": meta.get("slug"),
            }
        )
        if len(notes) >= max(1, limit):
            break
    return notes


def update_handoff_status(
    path: str | Path,
    status: str,
    handoff_root: Path | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}")
    resolved = _resolve_note_path(path, handoff_root)
    text = resolved.read_text(encoding="utf-8")
    meta, body = _parse_meta_and_body(text)
    meta["status"] = status
    meta["last_status_change_at"] = _now_iso()
    new_meta_json = json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True)
    new_text = (
        f"<!--HANDOFF_META\n{new_meta_json}\nHANDOFF_META-->\n\n{body.lstrip()}"
    )
    resolved.write_text(new_text, encoding="utf-8")
    return {"path": str(resolved), "meta": meta}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_handoff_notes.py -v`
Expected: 20 passing.

- [ ] **Step 5: Commit**

```bash
git add core/handoff_notes.py tests/test_handoff_notes.py
git commit -m "feat(handoff): list/read/update_handoff_status with path-traversal guard"
```

---

## Task 4 — `scripts/create_handoff_note.py` CLI

**Files:**
- Create: `scripts/create_handoff_note.py`
- Modify: `tests/test_handoff_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_handoff_notes.py`:
```python
def test_create_handoff_cli_writes_a_note(tmp_path, monkeypatch, capsys):
    from scripts import create_handoff_note as cli

    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", tmp_path / "handoffs")
    monkeypatch.setattr(
        "sys.argv",
        [
            "create_handoff_note.py",
            "--title", "CLI test",
            "--worker", "codex",
            "--task-type", "proposal_only",
            "--context-summary", "from CLI",
            "--validation-command", "echo ok",
            "--allowed-file", "core/foo.py",
            "--allowed-file", "tests/test_foo.py",
        ],
    )
    rc = cli.main()
    assert rc == 0

    listing = handoff_notes.list_handoff_notes(handoff_root=tmp_path / "handoffs")
    assert len(listing) == 1
    assert listing[0]["title"] == "CLI test"
    captured = capsys.readouterr()
    assert "handoffs" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_handoff_notes.py::test_create_handoff_cli_writes_a_note -v`
Expected: `ModuleNotFoundError: No module named 'scripts.create_handoff_note'`.

- [ ] **Step 3: Write minimal implementation**

`scripts/create_handoff_note.py`:
```python
#!/usr/bin/env python
"""Phase 7.1 — CLI to create a bounded handoff note without the web UI.

Wraps `core.handoff_notes.create_handoff_note`. Never executes any external
agent. Never modifies the real repo. Default behavior writes a single .md
file under `<AI-project>/.agent/handoffs/`.

Example:
    python scripts/create_handoff_note.py \\
        --title "Fix flaky fixtures" \\
        --worker codex \\
        --task-type proposal_only \\
        --allowed-file core/foo.py \\
        --validation-command "python -m pytest tests/test_foo.py -v"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import handoff_notes


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Create a bounded handoff note for an external coding agent.",
    )
    p.add_argument("--title", required=True)
    p.add_argument("--worker", required=True, choices=sorted(handoff_notes.VALID_WORKERS))
    p.add_argument(
        "--task-type", required=True, choices=sorted(handoff_notes.VALID_TASK_TYPES)
    )
    p.add_argument("--repo-path", default=None)
    p.add_argument("--allowed-file", action="append", default=[])
    p.add_argument("--forbidden-file", action="append", default=[])
    p.add_argument("--validation-command", default=None)
    p.add_argument("--context-summary", default="")
    p.add_argument("--expected-output", default="")
    p.add_argument("--extra-safety-rule", action="append", default=[])
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = handoff_notes.create_handoff_note(
            title=args.title,
            intended_worker=args.worker,
            task_type=args.task_type,
            repo_path=args.repo_path,
            allowed_files=args.allowed_file or None,
            forbidden_files=args.forbidden_file or None,
            validation_command=args.validation_command,
            context_summary=args.context_summary,
            expected_output=args.expected_output,
            extra_safety_rules=args.extra_safety_rule or None,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"created handoff note: {result['path']}")
    print(f"slug: {result['slug']}")
    print(f"status: {result['meta']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_handoff_notes.py::test_create_handoff_cli_writes_a_note -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/create_handoff_note.py tests/test_handoff_notes.py
git commit -m "feat(handoff): scripts/create_handoff_note CLI wrapper"
```

---

## Task 5 — `scripts/run_subagent_handoff.py` skeleton + dry-run path

**Files:**
- Create: `scripts/run_subagent_handoff.py`
- Create: `tests/test_run_subagent_handoff.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_run_subagent_handoff.py`:
```python
"""Phase 7.1 — tests for scripts/run_subagent_handoff.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import handoff_notes
from scripts import run_subagent_handoff as runner


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> dict:
    handoff_root = tmp_path / "handoffs"
    worker_runs_root = tmp_path / "worker_runs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "WORKER_RUNS_ROOT", worker_runs_root)
    return {
        "handoff_root": handoff_root,
        "worker_runs_root": worker_runs_root,
        "fake_repo": fake_repo,
    }


def _create_note(env, **overrides):
    kwargs = dict(
        title="run me",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(env["fake_repo"]),
        handoff_root=env["handoff_root"],
    )
    kwargs.update(overrides)
    return handoff_notes.create_handoff_note(**kwargs)


def test_dry_run_does_not_execute_subprocess(env, monkeypatch):
    note = _create_note(env)

    def fail(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called in dry-run")

    monkeypatch.setattr(runner.subprocess, "run", fail)

    result = runner.run_handoff(
        note_path=note["path"],
        allow_run=False,
    )

    assert result["dry_run"] is True
    assert result["exit_code"] is None
    assert "codex" in result["command"]
    artifact_dir = Path(result["artifact_dir"])
    assert (artifact_dir / "worker_run.json").is_file()
    assert (artifact_dir / "handoff.md").is_file()
    raw = (artifact_dir / "raw_output.txt").read_text(encoding="utf-8")
    assert raw == ""


def test_dry_run_does_not_change_handoff_status(env, monkeypatch):
    note = _create_note(env)
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    runner.run_handoff(note_path=note["path"], allow_run=False)
    parsed = handoff_notes.read_handoff_note(note["path"], handoff_root=env["handoff_root"])
    assert parsed["meta"]["status"] == "draft"


def test_dry_run_main_returns_zero(env, monkeypatch, capsys):
    note = _create_note(env)
    monkeypatch.setattr(sys, "argv", ["run_subagent_handoff.py", "--note", note["path"]])
    rc = runner.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out


def test_other_worker_without_command_refuses(env, monkeypatch):
    note = _create_note(env, intended_worker="other")
    result = runner.run_handoff(
        note_path=note["path"],
        allow_run=False,
        worker_override="other",
    )
    assert result["dry_run"] is True
    assert result["error"] is not None
    assert "worker_command" in result["error"]


def test_env_var_overrides_worker_command(env, monkeypatch):
    note = _create_note(env, intended_worker="gemini")
    monkeypatch.setenv("HANDOFF_GEMINI_CMD", "my-gemini --custom")
    result = runner.run_handoff(note_path=note["path"], allow_run=False)
    assert "my-gemini --custom" in result["command"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_run_subagent_handoff.py -v`
Expected: 5 failures with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`scripts/run_subagent_handoff.py`:
```python
#!/usr/bin/env python
"""Phase 7.1 — run a handoff note's worker command in a temp clone.

Default behavior is DRY RUN: print the would-be command and write a
worker_run.json with `dry_run: true`. The real subprocess only runs when
`--allow-run` is explicitly passed. The real repo is never modified.

CLI:
    python scripts/run_subagent_handoff.py --note <path>
    python scripts/run_subagent_handoff.py --note <path> --allow-run
    python scripts/run_subagent_handoff.py --note <path> --allow-run --timeout-sec 120
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import handoff_notes
from core.handoff_notes import _slug  # type: ignore[attr-defined]


HANDOFF_ROOT = PROJECT_ROOT / ".agent" / "handoffs"
WORKER_RUNS_ROOT = PROJECT_ROOT / ".agent" / "worker_runs"


WORKER_COMMAND_MAP: dict[str, str | None] = {
    "codex":       "codex exec --full-auto",
    "claude-code": "claude --print",
    "gemini":      "gemini --prompt-file HANDOFF.md",
    "other":       None,
}

_ENV_OVERRIDE_FOR_WORKER = {
    "codex":       "HANDOFF_CODEX_CMD",
    "claude-code": "HANDOFF_CLAUDE_CODE_CMD",
    "gemini":      "HANDOFF_GEMINI_CMD",
    "other":       "HANDOFF_OTHER_CMD",
}

_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".agent", "node_modules", "target",
    ".venv", "venv", "__pycache__", ".pytest_cache",
    "dist", "build",
)

DEFAULT_TIMEOUT_SEC = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_worker_command(worker: str, override: str | None) -> str | None:
    if override:
        return override.strip() or None
    env_var = _ENV_OVERRIDE_FOR_WORKER.get(worker)
    if env_var:
        env_value = os.environ.get(env_var, "").strip()
        if env_value:
            return env_value
    return WORKER_COMMAND_MAP.get(worker)


def _new_artifact_dir(slug: str) -> Path:
    WORKER_RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    base = WORKER_RUNS_ROOT / f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}"
    suffix = 1
    target = base
    while target.exists():
        target = WORKER_RUNS_ROOT / f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}-{suffix}"
        suffix += 1
    target.mkdir(parents=True)
    return target


def _write_artifacts(
    *,
    artifact_dir: Path,
    handoff_text: str,
    command: str | None,
    record: dict[str, Any],
    raw_output: str,
) -> None:
    (artifact_dir / "handoff.md").write_text(handoff_text, encoding="utf-8")
    (artifact_dir / "worker_command.txt").write_text((command or "") + "\n", encoding="utf-8")
    (artifact_dir / "raw_output.txt").write_text(raw_output, encoding="utf-8")
    (artifact_dir / "worker_run.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def run_handoff(
    *,
    note_path: str,
    allow_run: bool = False,
    worker_override: str | None = None,
    worker_command_override: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    handoff_root: Path | None = None,
) -> dict[str, Any]:
    root = handoff_root if handoff_root is not None else HANDOFF_ROOT
    parsed = handoff_notes.read_handoff_note(note_path, handoff_root=root)
    meta = parsed["meta"]
    handoff_text = parsed["raw"]
    slug = meta.get("slug") or _slug(meta.get("title") or "handoff")
    worker = (worker_override or meta.get("intended_worker") or "other").strip()
    command = _resolve_worker_command(worker, worker_command_override)
    artifact_dir = _new_artifact_dir(slug)

    error: str | None = None
    if not command:
        error = (
            "no worker_command resolved (set HANDOFF_<WORKER>_CMD env var or "
            "pass --worker-command)"
        )

    record: dict[str, Any] = {
        "dry_run": True,
        "started_at": _now_iso(),
        "finished_at": None,
        "duration_sec": 0.0,
        "exit_code": None,
        "timed_out": False,
        "command": command,
        "worker": worker,
        "handoff_path": parsed["path"],
        "artifact_dir": str(artifact_dir),
        "timeout_sec": int(timeout_sec),
        "error": error,
    }

    if not allow_run or error or meta.get("status") == "archived":
        if meta.get("status") == "archived" and not error:
            record["error"] = "handoff status is archived; refusing to run"
        _write_artifacts(
            artifact_dir=artifact_dir,
            handoff_text=handoff_text,
            command=command,
            record=record,
            raw_output="",
        )
        return record

    # --allow-run path will be filled in by Task 6.
    record["error"] = "allow_run path not implemented yet"
    _write_artifacts(
        artifact_dir=artifact_dir,
        handoff_text=handoff_text,
        command=command,
        record=record,
        raw_output="",
    )
    return record


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Run a handoff note's worker command in a temp clone.",
    )
    p.add_argument("--note", required=True)
    p.add_argument("--allow-run", action="store_true", default=False)
    p.add_argument("--worker", default=None, choices=sorted(handoff_notes.VALID_WORKERS))
    p.add_argument("--worker-command", default=None)
    p.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    args = p.parse_args(argv)

    try:
        result = run_handoff(
            note_path=args.note,
            allow_run=args.allow_run,
            worker_override=args.worker,
            worker_command_override=args.worker_command,
            timeout_sec=args.timeout_sec,
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if result.get("dry_run"):
        print("DRY RUN — no subprocess was executed.")
    print(f"command: {result.get('command')}")
    print(f"artifact_dir: {result.get('artifact_dir')}")
    if result.get("error"):
        print(f"error: {result.get('error')}", file=sys.stderr)
        return 2
    return 0 if (result.get("exit_code") in (None, 0) and not result.get("timed_out")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_run_subagent_handoff.py -v`
Expected: 5 passing.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_subagent_handoff.py tests/test_run_subagent_handoff.py
git commit -m "feat(handoff): run_subagent_handoff dry-run skeleton with worker command resolution"
```

---

## Task 6 — Implement `--allow-run` path: temp clone, subprocess, artifacts, status

**Files:**
- Modify: `scripts/run_subagent_handoff.py`
- Modify: `tests/test_run_subagent_handoff.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_run_subagent_handoff.py`:
```python
def _record_real_repo_state(repo: Path) -> dict[str, str]:
    import hashlib
    state: dict[str, str] = {}
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        state[rel] = h
    return state


def test_allow_run_uses_temp_clone_and_does_not_modify_real_repo(env, monkeypatch):
    note = _create_note(env)
    before = _record_real_repo_state(env["fake_repo"])

    captured: dict = {}

    class FakeCompleted:
        returncode = 0
        stdout = "worker says hi"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        # Confirm cwd is NOT the real repo.
        assert Path(kwargs["cwd"]).resolve() != env["fake_repo"].resolve()
        # Confirm HANDOFF.md is in the temp clone.
        assert (Path(kwargs["cwd"]) / "HANDOFF.md").is_file()
        # Simulate worker producing a proposal.md
        (Path(kwargs["cwd"]) / "proposal.md").write_text("worker-proposal", encoding="utf-8")
        return FakeCompleted()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_handoff(note_path=note["path"], allow_run=True)

    assert result["dry_run"] is False
    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    artifact_dir = Path(result["artifact_dir"])
    assert (artifact_dir / "raw_output.txt").read_text(encoding="utf-8") == "worker says hi"
    assert (artifact_dir / "proposal.md").read_text(encoding="utf-8") == "worker-proposal"

    after = _record_real_repo_state(env["fake_repo"])
    assert before == after, "real repo files must be byte-identical after --allow-run"


def test_allow_run_timeout_records_timed_out_true(env, monkeypatch):
    note = _create_note(env)

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_handoff(note_path=note["path"], allow_run=True, timeout_sec=1)

    assert result["timed_out"] is True
    assert result["dry_run"] is False

    parsed = handoff_notes.read_handoff_note(note["path"], handoff_root=env["handoff_root"])
    assert parsed["meta"]["status"] == "failed"


def test_allow_run_success_updates_status_to_ran(env, monkeypatch):
    note = _create_note(env)

    class FakeCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kw: FakeCompleted())
    runner.run_handoff(note_path=note["path"], allow_run=True)
    parsed = handoff_notes.read_handoff_note(note["path"], handoff_root=env["handoff_root"])
    assert parsed["meta"]["status"] == "ran"


def test_allow_run_non_zero_exit_updates_status_to_failed(env, monkeypatch):
    note = _create_note(env)

    class FakeCompleted:
        returncode = 3
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kw: FakeCompleted())
    runner.run_handoff(note_path=note["path"], allow_run=True)
    parsed = handoff_notes.read_handoff_note(note["path"], handoff_root=env["handoff_root"])
    assert parsed["meta"]["status"] == "failed"


def test_allow_run_skips_ignored_dirs_in_temp_clone(env, monkeypatch):
    (env["fake_repo"] / ".git").mkdir()
    (env["fake_repo"] / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (env["fake_repo"] / ".agent").mkdir()
    (env["fake_repo"] / ".agent" / "secret.txt").write_text("nope", encoding="utf-8")

    note = _create_note(env)

    seen: dict = {}

    def fake_run(cmd, **kwargs):
        cwd = Path(kwargs["cwd"])
        seen["has_git"] = (cwd / ".git").exists()
        seen["has_agent"] = (cwd / ".agent").exists()
        seen["has_src_foo"] = (cwd / "src" / "foo.py").exists()

        class C: returncode = 0; stdout = ""; stderr = ""
        return C()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.run_handoff(note_path=note["path"], allow_run=True)

    assert seen["has_git"] is False
    assert seen["has_agent"] is False
    assert seen["has_src_foo"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_run_subagent_handoff.py -v`
Expected: 5 new failures (current dry-run-only stub returns `error="allow_run path not implemented yet"`).

- [ ] **Step 3: Implement the --allow-run branch**

In `scripts/run_subagent_handoff.py`, replace the placeholder block at the end of `run_handoff()` (the section currently reading `record["error"] = "allow_run path not implemented yet"` plus its `_write_artifacts` call) with:

```python
    # --- Real run path -------------------------------------------------
    record["dry_run"] = False
    started = time.time()
    repo_path = meta.get("repo_path") or str(PROJECT_ROOT)
    repo_src = Path(repo_path).resolve()
    if not repo_src.is_dir():
        record["error"] = f"repo_path is not a directory: {repo_src}"
        record["finished_at"] = _now_iso()
        _write_artifacts(
            artifact_dir=artifact_dir,
            handoff_text=handoff_text,
            command=command,
            record=record,
            raw_output="",
        )
        handoff_notes.update_handoff_status(parsed["path"], "failed", handoff_root=root)
        return record

    raw_output = ""
    exit_code: int | None = None
    timed_out = False

    with tempfile.TemporaryDirectory(prefix="handoff-clone-", ignore_cleanup_errors=True) as tmp_dir:
        temp_clone = Path(tmp_dir) / "repo"
        shutil.copytree(repo_src, temp_clone, ignore=_COPY_IGNORE)
        (temp_clone / "HANDOFF.md").write_text(handoff_text, encoding="utf-8")

        try:
            completed = subprocess.run(
                shlex.split(command, posix=(os.name != "nt")),
                cwd=str(temp_clone),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, int(timeout_sec)),
                check=False,
            )
            exit_code = completed.returncode
            raw_output = (completed.stdout or "") + (completed.stderr or "")
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            raw_output = (stdout or "") + (stderr or "")
            record["error"] = f"subprocess timed out after {timeout_sec}s"
        except FileNotFoundError as exc:
            record["error"] = f"worker executable not found: {exc}"
        except Exception as exc:
            record["error"] = f"subprocess error: {type(exc).__name__}: {exc}"

        # Surface worker-produced artifacts from temp clone root.
        for filename in ("proposal.md", "patch_plan.json"):
            produced = temp_clone / filename
            if produced.is_file():
                shutil.copy2(produced, artifact_dir / filename)

    finished = time.time()
    record.update(
        finished_at=_now_iso(),
        duration_sec=round(finished - started, 3),
        exit_code=exit_code,
        timed_out=timed_out,
    )
    _write_artifacts(
        artifact_dir=artifact_dir,
        handoff_text=handoff_text,
        command=command,
        record=record,
        raw_output=raw_output,
    )

    final_status = "ran" if (exit_code == 0 and not timed_out and not record.get("error")) else "failed"
    handoff_notes.update_handoff_status(parsed["path"], final_status, handoff_root=root)
    return record
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_run_subagent_handoff.py -v`
Expected: 10 passing.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_subagent_handoff.py tests/test_run_subagent_handoff.py
git commit -m "feat(handoff): implement --allow-run temp-clone subprocess path with timeout + status update"
```

---

## Task 7 — Web routes: `/handoffs/create`, `/handoffs/list`, `/handoffs/run`, `/worker-runs/list`

**Files:**
- Modify: `web/app.py`
- Create: `tests/test_handoff_routes.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_handoff_routes.py`:
```python
"""Phase 7.1 — Flask client tests for the handoff routes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import handoff_notes
from scripts import run_subagent_handoff as runner


@pytest.fixture
def client(tmp_path, monkeypatch):
    handoff_root = tmp_path / "handoffs"
    worker_runs_root = tmp_path / "worker_runs"
    fake_repo = tmp_path / "repo"
    (fake_repo / "src").mkdir(parents=True)
    (fake_repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "HANDOFF_ROOT", handoff_root)
    monkeypatch.setattr(runner, "WORKER_RUNS_ROOT", worker_runs_root)

    from web import app as web_app

    monkeypatch.setattr(web_app, "_HANDOFF_ROOT", handoff_root, raising=False)
    monkeypatch.setattr(web_app, "_WORKER_RUNS_ROOT", worker_runs_root, raising=False)

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        c._handoff_root = handoff_root  # type: ignore[attr-defined]
        c._worker_runs_root = worker_runs_root  # type: ignore[attr-defined]
        c._fake_repo = fake_repo  # type: ignore[attr-defined]
        yield c


def test_handoffs_create_writes_note(client):
    resp = client.post(
        "/handoffs/create",
        data={
            "title": "From web",
            "intended_worker": "codex",
            "task_type": "proposal_only",
            "context_summary": "ctx",
            "validation_command": "echo ok",
            "allowed_files": "core/foo.py,tests/test_foo.py",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["meta"]["title"] == "From web"
    assert Path(body["handoff_path"]).is_file()


def test_handoffs_create_rejects_unknown_worker(client):
    resp = client.post(
        "/handoffs/create",
        data={
            "title": "x",
            "intended_worker": "bogus",
            "task_type": "proposal_only",
        },
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "intended_worker" in body["error"]


def test_handoffs_list_returns_recent(client):
    handoff_notes.create_handoff_note(
        title="a",
        intended_worker="codex",
        task_type="proposal_only",
        handoff_root=client._handoff_root,
    )
    resp = client.get("/handoffs/list")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert any(item["title"] == "a" for item in body["handoffs"])


def test_handoffs_run_dry_run_does_not_execute(client, monkeypatch):
    created = handoff_notes.create_handoff_note(
        title="dry",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(client._fake_repo),
        handoff_root=client._handoff_root,
    )

    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    resp = client.post(
        "/handoffs/run",
        data={"handoff_path": created["path"], "allow_run": "false"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["dry_run"] is True
    assert Path(body["artifact_dir"]).is_dir()


def test_worker_runs_list_returns_recent_runs(client, monkeypatch):
    created = handoff_notes.create_handoff_note(
        title="r",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=str(client._fake_repo),
        handoff_root=client._handoff_root,
    )
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    client.post("/handoffs/run", data={"handoff_path": created["path"], "allow_run": "false"})

    resp = client.get("/worker-runs/list")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["runs"]) >= 1
    assert "dry_run" in body["runs"][0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_handoff_routes.py -v`
Expected: 5 failures: `404 Not Found` for the routes.

- [ ] **Step 3: Add routes to `web/app.py`**

Append after the existing `/upload_folder` route handler (before `@app.route("/local_critique", ...)`):

```python
# --- Phase 7.1: Mayor Mode handoff routes ---------------------------------
from core import handoff_notes as _handoff_notes
from scripts import run_subagent_handoff as _handoff_runner


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for chunk in value.split(","):
        s = chunk.strip()
        if s and s not in out:
            out.append(s)
    return out


@app.route("/handoffs/create", methods=["POST"])
def handoffs_create_route():
    try:
        result = _handoff_notes.create_handoff_note(
            title=request.form.get("title", ""),
            intended_worker=request.form.get("intended_worker", ""),
            task_type=request.form.get("task_type", ""),
            repo_path=(request.form.get("repo_path") or "").strip() or None,
            allowed_files=_split_csv(request.form.get("allowed_files")),
            forbidden_files=_split_csv(request.form.get("forbidden_files")),
            validation_command=(request.form.get("validation_command") or "").strip() or None,
            context_summary=request.form.get("context_summary", ""),
            expected_output=request.form.get("expected_output", ""),
            extra_safety_rules=_split_csv(request.form.get("extra_safety_rules")),
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {
        "ok": True,
        "handoff_path": result["path"],
        "slug": result["slug"],
        "meta": result["meta"],
    }


@app.route("/handoffs/list", methods=["GET"])
def handoffs_list_route():
    include_archived = (request.values.get("include_archived") or "").lower() == "true"
    try:
        notes = _handoff_notes.list_handoff_notes(include_archived=include_archived)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {"ok": True, "handoffs": notes}


@app.route("/handoffs/run", methods=["POST"])
def handoffs_run_route():
    handoff_path = (request.form.get("handoff_path") or "").strip()
    if not handoff_path:
        return {"ok": False, "error": "handoff_path is required"}, 400
    allow_run = (request.form.get("allow_run") or "").lower() == "true"
    worker = (request.form.get("worker") or "").strip() or None
    worker_command = (request.form.get("worker_command") or "").strip() or None
    try:
        timeout_sec = int(request.form.get("timeout_sec") or _handoff_runner.DEFAULT_TIMEOUT_SEC)
    except ValueError:
        return {"ok": False, "error": "timeout_sec must be an integer"}, 400
    try:
        result = _handoff_runner.run_handoff(
            note_path=handoff_path,
            allow_run=allow_run,
            worker_override=worker,
            worker_command_override=worker_command,
            timeout_sec=timeout_sec,
        )
    except (ValueError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {
        "ok": True,
        "dry_run": result.get("dry_run"),
        "artifact_dir": result.get("artifact_dir"),
        "exit_code": result.get("exit_code"),
        "timed_out": result.get("timed_out"),
        "error": result.get("error"),
        "run": result,
    }


@app.route("/worker-runs/list", methods=["GET"])
def worker_runs_list_route():
    root = _handoff_runner.WORKER_RUNS_ROOT
    if not root.is_dir():
        return {"ok": True, "runs": []}
    runs: list[dict] = []
    try:
        dirs = sorted([d for d in root.iterdir() if d.is_dir()], reverse=True)
    except OSError as e:
        return {"ok": False, "error": str(e)}, 500
    for d in dirs[:50]:
        record_path = d / "worker_run.json"
        if not record_path.is_file():
            continue
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        runs.append({
            "artifact_dir": str(d),
            "name": d.name,
            "dry_run": record.get("dry_run"),
            "worker": record.get("worker"),
            "exit_code": record.get("exit_code"),
            "timed_out": record.get("timed_out"),
            "duration_sec": record.get("duration_sec"),
            "command": record.get("command"),
            "handoff_path": record.get("handoff_path"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "error": record.get("error"),
        })
    return {"ok": True, "runs": runs}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_handoff_routes.py -v`
Expected: 5 passing.

- [ ] **Step 5: Run the full handoff test suite to confirm nothing regressed**

Run: `python -m pytest tests/test_handoff_notes.py tests/test_run_subagent_handoff.py tests/test_handoff_routes.py -v`
Expected: 25 passing.

- [ ] **Step 6: Commit**

```bash
git add web/app.py tests/test_handoff_routes.py
git commit -m "feat(handoff): add /handoffs/create, /handoffs/list, /handoffs/run, /worker-runs/list routes"
```

---

## Task 8 — UI panel: "Mayor Mode (Handoffs)" in Memory tab

**Files:**
- Modify: `web/templates/index.html`

This task is template + JS only — no unit tests. After implementing, run a manual smoke test in the browser.

- [ ] **Step 1: Locate the proposals/lessons section seam**

Run: `python -c "import re; t=open('web/templates/index.html', encoding='utf-8').read(); m=[(i, line) for i, line in enumerate(t.splitlines(), 1) if 'memory-section lessons-section' in line]; print(m)"`
Expected: prints the single line number where `memory-section lessons-section` begins. Insert the handoff panel **immediately before** this line.

- [ ] **Step 2: Insert the handoff panel HTML**

Add this block immediately before the `<div class="memory-section lessons-section">` line:

```html
<!-- Phase 7.1: Mayor Mode handoff panel.
     Default = create note only. Running a subagent requires explicit opt-in
     via the "Allow running subagent in temp clone" checkbox. The real repo
     is never modified. Artifacts land in .agent/worker_runs/<run>/. -->
<div class="memory-section handoffs-section">
  <div class="proposals-header">
    <h3>Mayor Mode (Handoffs)</h3>
    <button type="button" class="memory-refresh" onclick="refreshHandoffs()"
            title="Re-scan .agent/handoffs/">⟳ Refresh</button>
  </div>
  <div class="proposals-note">
    Create a bounded handoff note for an external coding agent.
    <strong>Default = note only.</strong> Running the agent is opt-in,
    happens in a temp clone, and never modifies the real repo.
  </div>

  <details class="handoff-create">
    <summary>+ Create new handoff</summary>
    <div class="handoff-create__body">
      <label>Title
        <input type="text" id="handoffTitle" placeholder="Fix flaky fixtures in foo">
      </label>
      <label>Worker
        <select id="handoffWorker">
          <option value="codex">codex</option>
          <option value="claude-code">claude-code</option>
          <option value="gemini">gemini</option>
          <option value="other">other</option>
        </select>
      </label>
      <label>Task type
        <select id="handoffTaskType">
          <option value="proposal_only">proposal_only</option>
          <option value="review_only">review_only</option>
          <option value="explain_only">explain_only</option>
          <option value="benchmark_case">benchmark_case</option>
          <option value="research">research</option>
        </select>
      </label>
      <label>Allowed files (comma-separated, relative)
        <input type="text" id="handoffAllowed" placeholder="core/foo.py,tests/test_foo.py">
      </label>
      <label>Validation command (optional)
        <input type="text" id="handoffValidation" placeholder="python -m pytest tests/test_foo.py -v">
      </label>
      <label>Context summary
        <textarea id="handoffContext" rows="4" placeholder="What does the agent need to know?"></textarea>
      </label>
      <label>Expected output
        <textarea id="handoffExpected" rows="2" placeholder="proposal.md and patch_plan.json"></textarea>
      </label>
      <label class="handoff-allow-run">
        <input type="checkbox" id="handoffAllowRun">
        Allow running subagent in temp clone
      </label>
      <div class="handoff-warning">
        ⚠ Running may consume Claude/Codex quota. It will not apply changes
        to the real repo.
      </div>
      <div class="handoff-actions">
        <button type="button" onclick="createHandoff(false)">Create handoff</button>
        <button type="button" onclick="createHandoff(true)">Create + Run (in temp clone)</button>
      </div>
      <div id="handoffCreateStatus" class="proposals-status"></div>
    </div>
  </details>

  <div id="handoffsStatus" class="proposals-status"></div>
  <div id="handoffsList" class="proposals-list">
    <div class="health-empty">Click ⟳ Refresh to load handoffs.</div>
  </div>
</div>
```

- [ ] **Step 3: Add the JS — find a good spot near the proposals JS**

Run: `python -c "import re; t=open('web/templates/index.html', encoding='utf-8').read(); m=[(i, line) for i, line in enumerate(t.splitlines(), 1) if 'function refreshProposals' in line]; print(m)"`
Expected: prints line of `function refreshProposals(...)`. Insert the handoff JS immediately after that function ends.

- [ ] **Step 4: Add the JS block**

Add after the `refreshProposals` function (use the closing `}` of that function as anchor):

```javascript
async function refreshHandoffs() {
  const status = document.getElementById("handoffsStatus");
  const list = document.getElementById("handoffsList");
  status.textContent = "Loading handoffs...";
  try {
    const resp = await fetch("/handoffs/list");
    const body = await resp.json();
    if (!body.ok) {
      status.textContent = "Error: " + (body.error || "unknown");
      return;
    }
    if (!body.handoffs || body.handoffs.length === 0) {
      list.innerHTML = '<div class="health-empty">No handoffs yet. Use the form above to create one.</div>';
      status.textContent = "";
      return;
    }
    list.innerHTML = body.handoffs.map(h => `
      <div class="handoff-item" data-path="${_escapeHtml(h.path)}">
        <div class="handoff-item__head">
          <strong>${_escapeHtml(h.title || "(untitled)")}</strong>
          <span class="handoff-item__status handoff-item__status--${_escapeHtml(h.status || "draft")}">${_escapeHtml(h.status || "draft")}</span>
        </div>
        <div class="handoff-item__meta">
          worker: <code>${_escapeHtml(h.intended_worker || "?")}</code>
          · task: <code>${_escapeHtml(h.task_type || "?")}</code>
          · ${_escapeHtml(h.created_at || "")}
        </div>
        <div class="handoff-item__actions">
          <button type="button" onclick="runHandoff('${_escapeHtml(h.path)}', false)">Show command (dry run)</button>
          <button type="button" onclick="runHandoff('${_escapeHtml(h.path)}', true)">Run in temp clone</button>
        </div>
      </div>
    `).join("");
    status.textContent = `${body.handoffs.length} handoff(s).`;
  } catch (e) {
    status.textContent = "Error: " + e.message;
  }
}

async function createHandoff(thenRun) {
  const title = document.getElementById("handoffTitle").value.trim();
  const worker = document.getElementById("handoffWorker").value;
  const taskType = document.getElementById("handoffTaskType").value;
  const allowed = document.getElementById("handoffAllowed").value.trim();
  const validation = document.getElementById("handoffValidation").value.trim();
  const context = document.getElementById("handoffContext").value;
  const expected = document.getElementById("handoffExpected").value;
  const allowRunChecked = document.getElementById("handoffAllowRun").checked;
  const status = document.getElementById("handoffCreateStatus");

  if (!title) { status.textContent = "Title is required."; return; }

  if (thenRun && !allowRunChecked) {
    status.textContent =
      "Refusing: tick \"Allow running subagent in temp clone\" first.";
    return;
  }

  status.textContent = "Creating handoff...";
  try {
    const fd = new FormData();
    fd.append("title", title);
    fd.append("intended_worker", worker);
    fd.append("task_type", taskType);
    if (allowed) fd.append("allowed_files", allowed);
    if (validation) fd.append("validation_command", validation);
    if (context) fd.append("context_summary", context);
    if (expected) fd.append("expected_output", expected);
    const resp = await fetch("/handoffs/create", { method: "POST", body: fd });
    const body = await resp.json();
    if (!body.ok) {
      status.textContent = "Error: " + (body.error || "unknown");
      return;
    }
    status.textContent = "Created: " + body.handoff_path;

    if (thenRun) {
      await runHandoff(body.handoff_path, true);
    }
    refreshHandoffs();
  } catch (e) {
    status.textContent = "Error: " + e.message;
  }
}

async function runHandoff(handoffPath, allowRun) {
  const status = document.getElementById("handoffsStatus");
  status.textContent = allowRun ? "Running in temp clone..." : "Resolving command...";
  try {
    const fd = new FormData();
    fd.append("handoff_path", handoffPath);
    fd.append("allow_run", allowRun ? "true" : "false");
    const resp = await fetch("/handoffs/run", { method: "POST", body: fd });
    const body = await resp.json();
    if (!body.ok) {
      status.textContent = "Error: " + (body.error || "unknown");
      return;
    }
    const mode = body.dry_run ? "DRY RUN" : "RAN";
    const cmd = body.run && body.run.command ? body.run.command : "(no command resolved)";
    status.innerHTML =
      `<strong>${mode}</strong> — artifact dir: <code>${_escapeHtml(body.artifact_dir || "")}</code>` +
      `<br>command: <code>${_escapeHtml(cmd)}</code>`;
    refreshHandoffs();
  } catch (e) {
    status.textContent = "Error: " + e.message;
  }
}
```

- [ ] **Step 5: Smoke test in the browser**

Run: `python web/app.py` and open `http://127.0.0.1:5000` → Memory tab → expand "Mayor Mode (Handoffs)".

Verify:
1. Filling the form and clicking **Create handoff** (without ticking allow-run) creates a note under `.agent/handoffs/` and shows it in the list with status `draft`. No `.agent/worker_runs/` entry created.
2. Clicking **Show command (dry run)** on the new note shows the resolved command and creates a `worker_runs/<...>` entry with `dry_run: true`. Handoff status stays `draft`.
3. Clicking **Create + Run** **without** ticking the checkbox shows the refusal message and creates nothing extra.
4. Ticking the checkbox + **Create + Run**: with a working worker, creates a real run dir with `dry_run: false`. With a worker that doesn't exist on PATH, `error` is recorded in `worker_run.json` and handoff status becomes `failed`.

If any of the above misbehaves, stop and fix before committing.

- [ ] **Step 6: Commit**

```bash
git add web/templates/index.html
git commit -m "feat(handoff): Memory tab \"Mayor Mode\" panel — create + dry-run + opt-in temp-clone runner"
```

---

## Task 9 — Roadmap entry

**Files:**
- Modify: `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`

- [ ] **Step 1: Append the Phase 7.1 status block**

At the end of the file, append:

```markdown

---

## Phase 7.1 — Mayor Mode handoff + optional subagent runner (shipped 2026-05-20)

MVP for operator-driven external-agent handoffs. Built on top of the
existing `.agent/proposals/` patterns.

### What shipped

- `core/handoff_notes.py` — pure storage for `.agent/handoffs/<YYYYMMDD_HHMMSS>_<slug>.md` notes with JSON frontmatter, default safety rules, default forbidden files, brain stamp, and `safety_overrides` audit list when allowed_files overlaps a default-forbidden path.
- `scripts/create_handoff_note.py` — CLI wrapper, no web required.
- `scripts/run_subagent_handoff.py` — temp-clone runner. **Default: dry-run.** `--allow-run` is the only switch that actually executes a subprocess. Always copies the repo to a temp clone first; never writes back to the real repo. 300s default timeout, overridable with `--timeout-sec`. Worker command map (`codex / claude-code / gemini / other`) is env-var overridable (`HANDOFF_<WORKER>_CMD`).
- Web routes: `POST /handoffs/create`, `GET /handoffs/list`, `POST /handoffs/run`, `GET /worker-runs/list`.
- Memory tab: new "Mayor Mode (Handoffs)" panel with the explicit "Allow running subagent in temp clone" checkbox. Clicking "Create + Run" without ticking it is refused client-side.
- Tests: 25 covering core, runner script, and web routes. Real repo byte-identical assertion in the temp-clone test.

### Guardrails (verified by tests)

- Subagents do not run by default.
- Subagents never run in the real repo.
- Patches are never applied to the real repo.
- Nothing commits or pushes.
- Lessons are not auto-promoted.
- Patch-safety gate is unchanged.
- Dream / proposal / lesson flow is unchanged.

### 🤖 Claude-proposed follow-ups (Phase 7.1.1+, pending user decision)

These are extensions Claude observed while implementing 7.1. They are
**candidate scope, not yet sanctioned by the user**:

1. **"Create handoff from this item" button** on proposal cards and Dream item cards. Pre-fills title, repo_path, validation_command, and allowed_files from the source artifact. Low cost, high UX value once the panel is in place.
2. **Surface worker proposal.md back into the proposals queue.** If a temp-clone run produces a `proposal.md` and `patch_plan.json`, offer a one-click promotion path that opens a normal `.agent/proposals/<run>/<item>/` so the Patch Safety gate + lesson flow can run on it like any other proposal.
3. **Streaming worker output.** The current `/handoffs/run` route blocks until the subprocess exits, which can hit Flask's default request timeout for slow agents. Replace with an async runner + status polling, modeled on `core/proposal_runner.py`.
4. **Worker-quota meter.** Show a small estimate of "this handoff has X allowed_files and Y context tokens" to help operators gauge cost before clicking Run.
5. **Replay from a handoff note.** Add `python scripts/run_subagent_handoff.py --note <path> --replay` that re-runs an existing handoff with the same command but a fresh temp clone.
6. **Smoke test for the env-var override path.** Today the env-var override is unit-tested at the resolver level; an end-to-end test that actually shells out to a stub `HANDOFF_OTHER_CMD` script would catch shell-quoting bugs.
```

- [ ] **Step 2: Commit**

```bash
git add docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md
git commit -m "docs(roadmap): record Phase 7.1 Mayor Mode shipment + Claude-proposed 7.1.1 ideas"
```

---

## Self-review (run after writing all tasks)

**1. Spec coverage check** — every spec section mapped to a task:

| Spec section                                  | Task(s)        |
|-----------------------------------------------|----------------|
| core/handoff_notes.py public API              | 1, 2, 3        |
| scripts/create_handoff_note.py CLI            | 4              |
| scripts/run_subagent_handoff.py dry-run       | 5              |
| scripts/run_subagent_handoff.py --allow-run   | 6              |
| Default safety rules / forbidden files merge  | 2              |
| Slug sanitization                             | 1              |
| Path-traversal guards                         | 3, 7           |
| Timeout enforcement                           | 6              |
| Temp clone never touches real repo            | 6              |
| Artifacts written (handoff.md / raw_output / worker_command / worker_run.json / proposal.md / patch_plan.json) | 5, 6 |
| POST /handoffs/create                         | 7              |
| GET  /handoffs/list                           | 7              |
| POST /handoffs/run                            | 7              |
| GET  /worker-runs/list                        | 7              |
| Web UI panel                                  | 8              |
| Worker dropdown                               | 8              |
| "Allow running subagent in temp clone" checkbox | 8            |
| Warning text                                  | 8              |
| Roadmap entry                                 | 9              |

No gaps.

**2. Placeholder scan** — searched the plan for "TODO", "TBD", "implement later", "similar to". None found.

**3. Type consistency** — `run_handoff(...)` signature is the same in Task 5 declaration, Task 6 extension, Task 7 web route. `create_handoff_note(...)` keyword-only args match between core and CLI. `WORKER_RUNS_ROOT` named identically everywhere.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-20-phase-7-1-mayor-mode.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. Good for a 9-task plan with TDD discipline.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
