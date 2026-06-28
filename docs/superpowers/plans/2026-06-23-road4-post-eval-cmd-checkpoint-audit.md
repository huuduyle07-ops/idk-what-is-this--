# ROAD.4 Post-EVAL/CMD Checkpoint Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement ROAD.4, a report-only checkpoint audit that verifies EVAL.1–3 and CMD.1–4 are registered, complete, report-only, artifact-backed, and documented, then writes a deterministic JSON + Markdown audit report.

**Architecture:** `core/post_eval_cmd_checkpoint_audit.py` holds the pure builder (reusing `core.phase_picker.pick_phase_candidates` for authoritative registry state), `scripts/create_post_eval_cmd_checkpoint_audit.py` is the CLI entry point, and `tests/test_post_eval_cmd_checkpoint_audit.py` covers all 18 prescribed test cases. Four existing files need ripple updates: the phase registry JSON (add ROAD.4 entry), `tests/test_phase_registry.py` (16→17 phases, ROAD track 3→4), `tests/test_phase_picker.py` (complete_or_history 16→17), and the README + roadmap doc (mention ROAD.4).

**Tech Stack:** Python 3.x, stdlib only (`json`, `pathlib`, `typing`, `argparse`, `ast`). Single in-repo import: `core.phase_picker`. TDD with pytest.

---

## File Map

| Action | Path | Responsibility |
| --- | --- | --- |
| Create | `tests/test_post_eval_cmd_checkpoint_audit.py` | 18 prescribed test cases (TDD first) |
| Create | `core/post_eval_cmd_checkpoint_audit.py` | Pure builder + gather + write + Markdown render |
| Create | `scripts/create_post_eval_cmd_checkpoint_audit.py` | CLI: parse flags, call builder, write artifacts, exit code |
| Modify | `docs/roadmap/phase_registry.json` | Add ROAD.4 entry (17th phase, ROAD track, complete) |
| Modify | `tests/test_phase_registry.py` | 16→17 phase count, ROAD 3→4 track count |
| Modify | `tests/test_phase_picker.py` | complete_or_history 16→17, add ROAD.4 to shipped list |
| Modify | `README.md` | Add ROAD.4 section after CMD.4 section |
| Modify | `docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md` | Add ROAD.4 shipped note under ROAD section and recommended priority |

---

## Task 1: Write the Failing Tests

**Files:**
- Create: `tests/test_post_eval_cmd_checkpoint_audit.py`

- [ ] **Step 1: Create the test file**

```python
"""Tests for ROAD.4 — Post-EVAL/CMD Checkpoint Audit (report-only).

ROAD.4 reads the phase registry, EVAL/CMD artifact roots, and documentation,
then writes a deterministic checkpoint audit that verifies the completed EVAL and
CMD arcs. It does not choose new work, execute phases, call models, apply patches,
run validation, run benchmarks, contact network services, launch workers, push,
merge, or open PRs.

Covers the prescribed cases:
1.  valid complete EVAL/CMD registry produces pass.
2.  missing EVAL phase blocks.
3.  missing CMD phase blocks.
4.  non-complete required phase blocks.
5.  model_calls_allowed true blocks.
6.  network_allowed true blocks.
7.  merge_allowed true blocks.
8.  writes_real_repo true blocks.
9.  missing artifact root produces warning.
10. missing docs mention produces warning.
11. picker safe_to_prepare not empty produces warning.
12. picker top_recommendation not null produces warning.
13. pass_with_warnings with allow_warnings.
14. Markdown contains required sections and boundaries.
15. CLI writes JSON + Markdown.
16. CLI --json prints summary JSON.
17. guardrails are all false.
18. source contains no forbidden execution/model/network/patch/validation/
    benchmark/worker/DB/merge behavior.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.post_eval_cmd_checkpoint_audit import (
    DOC_PHASE_IDS,
    EXPECTED_ARTIFACT_ROOTS,
    GUARDRAIL_NOTE,
    PHASE_GUARDRAIL_FIELDS,
    REPORT_KIND,
    REQUIRED_CMD_PHASE_IDS,
    REQUIRED_EVAL_PHASE_IDS,
    REQUIRED_PHASE_IDS,
    STATUS_BLOCKED,
    STATUS_PASS,
    STATUS_WARN,
    build_post_eval_cmd_checkpoint_audit,
    gather_post_eval_cmd_checkpoint_inputs,
    render_post_eval_cmd_checkpoint_audit_markdown,
    write_post_eval_cmd_checkpoint_audit,
)
import scripts.create_post_eval_cmd_checkpoint_audit as script


# ── synthetic registry builders ──────────────────────────────────────────────

def _phase(pid, track=None, status="complete", **over) -> dict:
    data = {
        "phase_id": pid,
        "title": f"{pid} title",
        "track": track or pid.split(".")[0],
        "status": status,
        "summary": "Report-only phase.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/x.py", "tests/test_x.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/x.json"],
        "notes": ["Report-only."],
    }
    data.update(over)
    return data


def _all_phases(status_overrides=None, drop=(), phase_overrides=None) -> list:
    status_overrides = status_overrides or {}
    phase_overrides = phase_overrides or {}
    phases = []
    for pid in REQUIRED_PHASE_IDS:
        if pid in drop:
            continue
        p = _phase(pid, status=status_overrides.get(pid, "complete"))
        if pid in phase_overrides:
            p.update(phase_overrides[pid])
        phases.append(p)
    return phases


def _registry(phases=None, **over) -> dict:
    data = {
        "schema_version": "1.0",
        "updated_at": "2026-06-23T00:00:00+00:00",
        "phases": _all_phases() if phases is None else phases,
    }
    data.update(over)
    return data


# ── synthetic artifact root + docs builders ───────────────────────────────────

def _clean_roots() -> list:
    return [
        {"kind": kind, "rel": rel, "optional": opt, "present": True}
        for kind, rel, opt in EXPECTED_ARTIFACT_ROOTS
    ]


def _docs(readme_text=None, roadmap_text=None) -> list:
    all_ids = " ".join(DOC_PHASE_IDS)
    return [
        {
            "name": "README",
            "path": "README.md",
            "present": True,
            "text": all_ids if readme_text is None else readme_text,
        },
        {
            "name": "roadmap",
            "path": "docs/roadmap.md",
            "present": True,
            "text": all_ids if roadmap_text is None else roadmap_text,
        },
    ]


def _build(**over) -> dict:
    kwargs = dict(
        registry_data=_registry(),
        artifact_root_records=_clean_roots(),
        docs=_docs(),
        report_id="r",
        created_at="t",
        repo_path=".",
        registry_path="docs/roadmap/phase_registry.json",
    )
    kwargs.update(over)
    return build_post_eval_cmd_checkpoint_audit(**kwargs)


# ── 1. valid complete EVAL/CMD registry produces pass ─────────────────────────

def test_valid_complete_registry_produces_pass():
    report = _build()
    assert report["audit_status"] == STATUS_PASS == "pass"
    assert report["blockers"] == []
    assert report["warnings"] == []
    assert report["recommended_next_step"] == "freeze_eval_cmd_checkpoint"
    assert report["report_kind"] == REPORT_KIND == "post_eval_cmd_checkpoint_audit"
    assert report["eval_arc_summary"]["all_complete"] is True
    assert report["cmd_arc_summary"]["all_complete"] is True
    assert report["guardrail_summary"]["all_clear"] is True


def test_report_has_all_required_fields():
    report = _build(report_id="rid", created_at="2026-06-23T00:00:00+00:00")
    for key in (
        "report_id", "created_at", "repo_path", "registry_path",
        "audit_status", "audit_reason",
        "registry_summary", "phase_picker_summary",
        "eval_arc_summary", "cmd_arc_summary",
        "artifact_coverage", "documentation_coverage",
        "validation_story", "guardrail_summary",
        "open_questions", "recommended_next_step",
        "warnings", "blockers", "boundaries",
    ):
        assert key in report, key
    assert report["report_id"] == "rid"
    assert report["created_at"] == "2026-06-23T00:00:00+00:00"


# ── 2. missing EVAL phase blocks ──────────────────────────────────────────────

def test_missing_eval_phase_blocks():
    for missing_pid in REQUIRED_EVAL_PHASE_IDS:
        report = _build(registry_data=_registry(phases=_all_phases(drop=[missing_pid])))
        assert report["audit_status"] == STATUS_BLOCKED, missing_pid
        assert any(missing_pid in b for b in report["blockers"]), missing_pid
        assert report["eval_arc_summary"]["all_complete"] is False


# ── 3. missing CMD phase blocks ───────────────────────────────────────────────

def test_missing_cmd_phase_blocks():
    for missing_pid in REQUIRED_CMD_PHASE_IDS:
        report = _build(registry_data=_registry(phases=_all_phases(drop=[missing_pid])))
        assert report["audit_status"] == STATUS_BLOCKED, missing_pid
        assert any(missing_pid in b for b in report["blockers"]), missing_pid
        assert report["cmd_arc_summary"]["all_complete"] is False


# ── 4. non-complete required phase blocks ─────────────────────────────────────

def test_non_complete_required_phase_blocks():
    for pid in REQUIRED_PHASE_IDS:
        report = _build(
            registry_data=_registry(phases=_all_phases(status_overrides={pid: "proposed"}))
        )
        assert report["audit_status"] == STATUS_BLOCKED, pid
        assert any(pid in b for b in report["blockers"]), pid


# ── 5. model_calls_allowed true blocks ───────────────────────────────────────

def test_model_calls_allowed_true_blocks():
    for pid in REQUIRED_PHASE_IDS:
        report = _build(
            registry_data=_registry(
                phases=_all_phases(phase_overrides={pid: {"model_calls_allowed": True}})
            )
        )
        assert report["audit_status"] == STATUS_BLOCKED, pid
        assert any("model_calls_allowed" in b for b in report["blockers"]), pid


# ── 6. network_allowed true blocks ────────────────────────────────────────────

def test_network_allowed_true_blocks():
    for pid in REQUIRED_PHASE_IDS:
        report = _build(
            registry_data=_registry(
                phases=_all_phases(phase_overrides={pid: {"network_allowed": True}})
            )
        )
        assert report["audit_status"] == STATUS_BLOCKED, pid
        assert any("network_allowed" in b for b in report["blockers"]), pid


# ── 7. merge_allowed true blocks ─────────────────────────────────────────────

def test_merge_allowed_true_blocks():
    for pid in REQUIRED_PHASE_IDS:
        report = _build(
            registry_data=_registry(
                phases=_all_phases(phase_overrides={pid: {"merge_allowed": True}})
            )
        )
        assert report["audit_status"] == STATUS_BLOCKED, pid
        assert any("merge_allowed" in b for b in report["blockers"]), pid


# ── 8. writes_real_repo true blocks ───────────────────────────────────────────

def test_writes_real_repo_true_blocks():
    for pid in REQUIRED_PHASE_IDS:
        report = _build(
            registry_data=_registry(
                phases=_all_phases(phase_overrides={pid: {"writes_real_repo": True}})
            )
        )
        assert report["audit_status"] == STATUS_BLOCKED, pid
        assert any("writes_real_repo" in b for b in report["blockers"]), pid


# ── 9. missing artifact root produces warning (not blocker) ───────────────────

def test_missing_artifact_root_produces_warning():
    roots = _clean_roots()
    roots[0]["present"] = False
    report = _build(artifact_root_records=roots)
    assert report["audit_status"] == STATUS_WARN
    assert report["blockers"] == []
    assert report["warnings"]
    missing = report["artifact_coverage"]["roots_missing"]
    assert missing


def test_all_missing_artifact_roots_still_only_warn():
    roots = [{**r, "present": False} for r in _clean_roots()]
    report = _build(artifact_root_records=roots)
    assert report["audit_status"] == STATUS_WARN
    assert report["blockers"] == []
    assert len(report["artifact_coverage"]["roots_missing"]) == len(EXPECTED_ARTIFACT_ROOTS)


# ── 10. missing docs mention produces warning ──────────────────────────────────

def test_missing_docs_mention_produces_warning():
    present_ids = " ".join(pid for pid in DOC_PHASE_IDS if pid != "EVAL.2")
    report = _build(docs=_docs(readme_text=present_ids, roadmap_text=present_ids))
    doc = report["documentation_coverage"]
    assert "EVAL.2" in doc["missing_phase_mentions"]
    assert report["audit_status"] == STATUS_WARN
    assert any("EVAL.2" in w for w in report["warnings"])


def test_full_doc_mention_has_no_doc_warning():
    report = _build()
    doc = report["documentation_coverage"]
    assert doc["missing_phase_mentions"] == []
    assert set(doc["checked_phase_ids"]) == set(DOC_PHASE_IDS)


# ── 11. picker safe_to_prepare not empty produces warning ─────────────────────

def test_picker_safe_to_prepare_not_empty_produces_warning():
    # Add a proposed safe phase; EVAL/CMD phases are still complete → no blockers.
    extra = _phase("NEXT.1", track="NEXT", status="proposed")
    phases = _all_phases() + [extra]
    report = _build(registry_data=_registry(phases=phases))
    assert report["phase_picker_summary"]["safe_to_prepare_count"] > 0
    assert report["audit_status"] == STATUS_WARN
    assert report["blockers"] == []
    assert any("safe" in w.lower() or "candidate" in w.lower() for w in report["warnings"])


# ── 12. picker top_recommendation not null produces warning ───────────────────

def test_picker_top_recommendation_not_null_produces_warning():
    extra = _phase("NEXT.1", track="NEXT", status="proposed")
    phases = _all_phases() + [extra]
    report = _build(registry_data=_registry(phases=phases))
    assert report["phase_picker_summary"]["top_recommendation"] is not None
    assert report["audit_status"] == STATUS_WARN
    assert any("recommend" in w.lower() for w in report["warnings"])


# ── 13. pass_with_warnings with allow_warnings (CLI) ─────────────────────────

def _write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _seed_repo(tmp_path: Path, *, include_roots=True, docs_ids=None) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs" / "roadmap").mkdir(parents=True, exist_ok=True)
    _write_json(repo / "docs" / "roadmap" / "phase_registry.json", _registry())
    if include_roots:
        for _kind, rel, _opt in EXPECTED_ARTIFACT_ROOTS:
            (repo / rel).mkdir(parents=True, exist_ok=True)
    ids = " ".join(docs_ids if docs_ids is not None else DOC_PHASE_IDS)
    (repo / "README.md").write_text(ids, encoding="utf-8")
    roadmap_dir = repo / "docs"
    roadmap_dir.mkdir(parents=True, exist_ok=True)
    (roadmap_dir / "AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md").write_text(
        ids, encoding="utf-8"
    )
    return repo


def test_pass_with_warnings_allows_zero_exit(tmp_path):
    # Missing artifact roots → pass_with_warnings; --allow-warnings → exit 0.
    repo = _seed_repo(tmp_path, include_roots=False)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "w",
        "--created-at", "t",
        "--allow-warnings",
    ])
    assert code == 0
    data = json.loads(
        (out / "post_eval_cmd_checkpoint_audit.json").read_text(encoding="utf-8")
    )
    assert data["audit_status"] == STATUS_WARN


def test_pass_with_warnings_exits_nonzero_without_flag(tmp_path):
    repo = _seed_repo(tmp_path, include_roots=False)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "w",
        "--created-at", "t",
    ])
    assert code != 0


# ── 14. Markdown contains required sections and boundaries ────────────────────

def test_markdown_contains_required_sections():
    md = render_post_eval_cmd_checkpoint_audit_markdown(_build())
    assert "# Post-EVAL/CMD Checkpoint Audit" in md
    low = md.lower()
    for section in (
        "## summary",
        "## registry summary",
        "## phase picker summary",
        "## eval arc summary",
        "## cmd arc summary",
        "## artifact coverage",
        "## documentation coverage",
        "## validation story",
        "## guardrail summary",
        "## open questions",
        "## recommended next step",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    low = render_post_eval_cmd_checkpoint_audit_markdown(_build()).lower()
    assert "does not choose new work" in low
    assert "does not execute phases" in low
    assert "does not call models" in low
    assert "does not apply patches" in low
    assert "does not run validation" in low
    assert "does not run benchmarks" in low
    assert "does not contact network services" in low
    assert "does not launch workers" in low
    assert "does not push, merge, or open prs" in low
    assert "report-only checkpoint audit" in low


# ── 15. CLI writes JSON + Markdown ────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    repo = _seed_repo(tmp_path, include_roots=True)
    out = tmp_path / "out"
    res = script.run_create_post_eval_cmd_checkpoint_audit(
        repo_path=str(repo),
        registry=str(repo / "docs" / "roadmap" / "phase_registry.json"),
        output_root=str(out),
        report_id="cli",
        created_at="2026-06-23T00:00:00+00:00",
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file() and mp.is_file()
    assert jp.name == "post_eval_cmd_checkpoint_audit.json"
    assert mp.name == "post_eval_cmd_checkpoint_audit.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["report_id"] == "cli"
    assert data["audit_status"] == STATUS_PASS


def test_cli_exits_zero_on_pass(tmp_path):
    repo = _seed_repo(tmp_path, include_roots=True)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
    ])
    assert code == 0


def test_cli_exits_nonzero_on_blocked(tmp_path):
    repo = _seed_repo(tmp_path, include_roots=True)
    # Remove EVAL.1 from registry → blocked.
    _write_json(
        repo / "docs" / "roadmap" / "phase_registry.json",
        _registry(phases=_all_phases(drop=["EVAL.1"])),
    )
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "x",
        "--created-at", "t",
    ])
    assert code != 0
    data = json.loads(
        (out / "post_eval_cmd_checkpoint_audit.json").read_text(encoding="utf-8")
    )
    assert data["audit_status"] == STATUS_BLOCKED


# ── 16. CLI --json prints summary JSON ────────────────────────────────────────

def test_cli_json_flag_prints_summary_json(tmp_path, capsys):
    repo = _seed_repo(tmp_path, include_roots=True)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--output-root", str(out),
        "--report-id", "j",
        "--created-at", "t",
        "--json",
    ])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "j"
    assert printed["report_kind"] == "post_eval_cmd_checkpoint_audit"
    assert printed["audit_status"] == STATUS_PASS


# ── 17. guardrails are all false ──────────────────────────────────────────────

def test_guardrails_are_all_false():
    report = _build()
    gs = report["guardrail_summary"]
    road4 = gs["road4_guardrails"]
    for key, val in road4.items():
        assert val is False, f"ROAD.4 guardrail {key!r} is not False"
    assert gs["phase_guardrail_violations"] == []
    assert gs["all_clear"] is True


def test_validation_story_shows_not_run():
    vs = _build()["validation_story"]
    assert vs["validation_run"] is False
    assert "note" in vs


def test_boundaries_list_is_complete():
    report = _build()
    boundaries = report.get("boundaries") or []
    low = " ".join(b.lower() for b in boundaries)
    assert "does not choose new work" in low
    assert "does not execute phases" in low
    assert "does not call models" in low
    assert "does not apply patches" in low
    assert "does not run validation" in low
    assert "does not run benchmarks" in low
    assert "does not contact network services" in low
    assert "does not launch workers" in low
    assert "does not push, merge, or open prs" in low
    assert "report-only checkpoint audit" in low


# ── 18. forbidden-token / import guards (source-only) ─────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "post_eval_cmd_checkpoint_audit.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_post_eval_cmd_checkpoint_audit.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_or_phase_modules():
    allowed_top = {"__future__", "json", "pathlib", "typing", "core"}
    allowed_core = {"core.phase_picker", "core.phase_registry"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            if top == "core":
                assert module in allowed_core, f"ROAD.4 may only import {allowed_core!r}, got {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "check_output", "check_call", "shutil", "copytree"):
        assert bad not in _BOTH, f"Found execution primitive: {bad!r}"


def test_no_model_clients():
    for bad in (
        "anthropic", "openai", "litellm", "ollama", "bedrock", "generativeai",
        "claude", "codex", "gemini", "deepseek", "call_model(", "launch_model(",
    ):
        assert bad not in _BOTH, f"Found model client token: {bad!r}"


def test_no_network_or_send():
    for bad in (
        "requests", "httpx", "urllib", "socket", "aiohttp", "webhook",
        "api.telegram.org", "sendMessage", "send_message(", "bot_token",
        "api.github.com", "PyGithub", "from github", "import github", "gh pr",
        "n8n.cloud", "n8n.io", "execute_workflow(",
    ):
        assert bad not in _BOTH, f"Found network/send token: {bad!r}"


def test_no_git_commands():
    for bad in (
        "git push", "git checkout", "git branch", "git commit", "git merge",
        "git clone", "git log", "git status", "git_command(",
    ):
        assert bad not in _BOTH, f"Found git command: {bad!r}"


def test_no_validation_or_benchmark_execution():
    for bad in (
        "run_safe_validation", "SafeValidationCommand", "validation_execution",
        "run_benchmarks", "create_managed_sandbox", "apply_candidate_in_sandbox",
    ):
        assert bad not in _BOTH, f"Found validation/benchmark execution token: {bad!r}"


def test_no_patch_apply():
    for bad in ("generate_patch", "apply_patch(", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token: {bad!r}"


def test_no_worker_launch():
    for bad in (
        "import_proposal", "proposal_runner", "launch_worker(", "worker_launch(",
        "spawn_worker", "run_worker(",
    ):
        assert bad not in _BOTH, f"Found worker launch token: {bad!r}"


def test_no_database_writes():
    for bad in ("sqlite3", "psycopg", "pymongo", "INSERT INTO", "cursor(", "vector_db", "vectordb"):
        assert bad not in _BOTH, f"Found database token: {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token: {bad!r}"


def test_guardrail_note_is_report_only():
    assert "report-only" in GUARDRAIL_NOTE.lower()
    assert _build()["guardrail_note"] == GUARDRAIL_NOTE


# ── constants ──────────────────────────────────────────────────────────────────

def test_required_phase_ids_match_spec():
    assert REQUIRED_EVAL_PHASE_IDS == ("EVAL.1", "EVAL.2", "EVAL.3")
    assert REQUIRED_CMD_PHASE_IDS == ("CMD.1", "CMD.2", "CMD.3", "CMD.4")
    assert REQUIRED_PHASE_IDS == REQUIRED_EVAL_PHASE_IDS + REQUIRED_CMD_PHASE_IDS


def test_doc_phase_ids_include_road4():
    assert "ROAD.4" in DOC_PHASE_IDS
    assert set(REQUIRED_PHASE_IDS) <= set(DOC_PHASE_IDS)


def test_phase_guardrail_fields_match_spec():
    assert set(PHASE_GUARDRAIL_FIELDS) == {
        "model_calls_allowed", "network_allowed", "merge_allowed", "writes_real_repo"
    }


def test_expected_artifact_roots_match_spec():
    paths = {rel for _kind, rel, _opt in EXPECTED_ARTIFACT_ROOTS}
    assert ".agent/eval/benchmark_run_ledger" in paths
    assert ".agent/eval/benchmark_report_compare" in paths
    assert ".agent/eval/flake_classification_report" in paths
    assert ".agent/commander/contracts" in paths
    assert ".agent/commander/decomposition_previews" in paths
    assert ".agent/commander/budget_previews" in paths
    assert ".agent/commander/readiness_reports" in paths
    assert len(EXPECTED_ARTIFACT_ROOTS) == 7


def test_status_and_next_step_constants():
    assert STATUS_PASS == "pass"
    assert STATUS_WARN == "pass_with_warnings"
    assert STATUS_BLOCKED == "blocked"


def test_build_does_not_mutate_inputs():
    registry = _registry()
    roots = _clean_roots()
    docs = _docs()
    snap = copy.deepcopy([registry, roots, docs])
    build_post_eval_cmd_checkpoint_audit(
        registry_data=registry,
        artifact_root_records=roots,
        docs=docs,
        report_id="r",
        created_at="t",
    )
    assert [registry, roots, docs] == snap


def test_report_bytes_are_deterministic(tmp_path):
    repo = _seed_repo(tmp_path, include_roots=True)

    def run(name: str) -> str:
        res = script.run_create_post_eval_cmd_checkpoint_audit(
            repo_path=str(repo),
            registry=str(repo / "docs" / "roadmap" / "phase_registry.json"),
            output_root=str(tmp_path / name),
            report_id="fixed",
            created_at="2026-06-23T12:00:00+00:00",
        )
        return Path(res["json_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


def test_gather_inputs_tolerates_missing_everything(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    inputs = gather_post_eval_cmd_checkpoint_inputs(str(repo), str(repo / "missing.json"))
    assert inputs["registry_data"] is None
    assert inputs["registry_load_error"]
    assert len(inputs["artifact_root_records"]) == len(EXPECTED_ARTIFACT_ROOTS)
    assert all(r["present"] is False for r in inputs["artifact_root_records"])
    assert isinstance(inputs["docs"], list) and inputs["docs"]
```

- [ ] **Step 2: Run the tests to confirm they all fail (import error expected)**

```bash
python -m pytest tests/test_post_eval_cmd_checkpoint_audit.py -q 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'core.post_eval_cmd_checkpoint_audit'`

- [ ] **Step 3: Commit the failing test file**

```bash
git add tests/test_post_eval_cmd_checkpoint_audit.py
git commit -m "test: add ROAD.4 post-EVAL/CMD checkpoint audit test suite (failing)"
```

---

## Task 2: Implement the Core Module

**Files:**
- Create: `core/post_eval_cmd_checkpoint_audit.py`

- [ ] **Step 1: Create the core module**

```python
"""ROAD.4 — Post-EVAL/CMD Checkpoint Audit (report-only).

Reads the phase registry, the phase picker state, EVAL artifact root
directories, CMD artifact root directories, and project documentation, then
writes a deterministic JSON + Markdown checkpoint audit that verifies the
completed EVAL and CMD arcs: all seven required phases (EVAL.1–3, CMD.1–4)
are registered, complete, report-only, artifact-backed, and documented.

Core principle: ROAD.4 audits the completed EVAL/CMD arcs. ROAD.4 does not
choose new work, execute phases, call models, apply patches, run validation,
run benchmarks, contact network services, launch workers, push, merge, or
open PRs. ROAD.4 is a report-only checkpoint audit.

Reuses ``core.phase_picker.pick_phase_candidates`` for authoritative
registry validity, bucket counts, safe-candidate count, and top
recommendation. The picker classifies metadata only; nothing is run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.phase_picker import pick_phase_candidates


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "post_eval_cmd_checkpoint_audit"

REQUIRED_EVAL_PHASE_IDS: tuple[str, ...] = ("EVAL.1", "EVAL.2", "EVAL.3")
REQUIRED_CMD_PHASE_IDS: tuple[str, ...] = ("CMD.1", "CMD.2", "CMD.3", "CMD.4")
REQUIRED_PHASE_IDS: tuple[str, ...] = REQUIRED_EVAL_PHASE_IDS + REQUIRED_CMD_PHASE_IDS

DOC_PHASE_IDS: tuple[str, ...] = REQUIRED_PHASE_IDS + ("ROAD.4",)

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

EXPECTED_ARTIFACT_ROOTS: tuple[tuple[str, str, bool], ...] = (
    ("eval_benchmark_run_ledger", ".agent/eval/benchmark_run_ledger", True),
    ("eval_benchmark_report_compare", ".agent/eval/benchmark_report_compare", True),
    ("eval_flake_classification_report", ".agent/eval/flake_classification_report", True),
    ("cmd_contracts", ".agent/commander/contracts", True),
    ("cmd_decomposition_previews", ".agent/commander/decomposition_previews", True),
    ("cmd_budget_previews", ".agent/commander/budget_previews", True),
    ("cmd_readiness_reports", ".agent/commander/readiness_reports", True),
)

DEFAULT_README_REL = "README.md"
DEFAULT_ROADMAP_REL = "docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md"

JSON_NAME = "post_eval_cmd_checkpoint_audit.json"
MD_NAME = "post_eval_cmd_checkpoint_audit.md"

STATUS_PASS = "pass"
STATUS_WARN = "pass_with_warnings"
STATUS_BLOCKED = "blocked"

NEXT_STEP_BY_STATUS: dict[str, str] = {
    STATUS_PASS: "freeze_eval_cmd_checkpoint",
    STATUS_WARN: "resolve_warnings_before_next_branch",
    STATUS_BLOCKED: "fix_blockers_before_next_branch",
}

GUARDRAIL_NOTE = (
    "Post-EVAL/CMD Checkpoint Audit is report-only: it reads the phase registry, the "
    "phase picker state, EVAL and CMD artifact roots, and documentation, then verifies "
    "the completed EVAL and CMD arcs agree. ROAD.4 does not choose new work, execute "
    "phases, call models, apply patches, run validation, run benchmarks, contact network "
    "services, launch workers, push, merge, or open PRs. ROAD.4 is a report-only checkpoint audit."
)

ROAD4_BOUNDARIES: tuple[str, ...] = (
    "ROAD.4 does not choose new work.",
    "ROAD.4 does not execute phases.",
    "ROAD.4 does not call models.",
    "ROAD.4 does not apply patches.",
    "ROAD.4 does not run validation.",
    "ROAD.4 does not run benchmarks.",
    "ROAD.4 does not contact network services.",
    "ROAD.4 does not launch workers.",
    "ROAD.4 does not push, merge, or open PRs.",
    "ROAD.4 is a report-only checkpoint audit.",
)


# ── Small helpers ──────────────────────────────────────────────────────────────

def _str(v: Any, default: str = "") -> str:
    return str(v) if v is not None else default


def _norm_path(v: Any) -> str:
    return str(v).replace("\\", "/").strip()


def _md(v: Any) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def _lower(v: bool) -> str:
    return str(bool(v)).lower()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ── ROAD.4 own guardrails ──────────────────────────────────────────────────────

def _road4_guardrails() -> dict[str, bool]:
    """ROAD.4's own boundary booleans — it performs none of these actions."""
    return {
        "chooses_work": False,
        "executes_phases": False,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "worker_launch_performed": False,
        "merge_performed": False,
    }


# ── Phase-level guardrail check ───────────────────────────────────────────────

def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    """Return names of guardrail fields that are True in a phase dict."""
    return [f for f in PHASE_GUARDRAIL_FIELDS if phase.get(f) is True]


# ── Arc summary ────────────────────────────────────────────────────────────────

def _build_arc_summary(
    arc_name: str,
    required_ids: tuple[str, ...],
    registry_data: Any,
) -> dict[str, Any]:
    root = registry_data if isinstance(registry_data, dict) else {}
    raw_phases = root.get("phases", [])
    phase_map: dict[str, dict[str, Any]] = {}
    if isinstance(raw_phases, list):
        for p in raw_phases:
            if isinstance(p, dict) and p.get("phase_id"):
                phase_map[str(p["phase_id"])] = p

    phase_checks: list[dict[str, Any]] = []
    all_complete = True
    all_guardrails_ok = True

    for pid in required_ids:
        phase = phase_map.get(pid)
        present = phase is not None
        complete = present and str(phase.get("status", "")) == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        guardrails_ok = present and not violations
        if not complete:
            all_complete = False
        if not guardrails_ok:
            all_guardrails_ok = False
        phase_checks.append({
            "phase_id": pid,
            "present": present,
            "status": _str(phase.get("status", "")) if present else "(missing)",
            "complete": complete,
            "guardrails_ok": guardrails_ok,
            "guardrail_violations": violations,
        })

    return {
        "arc": arc_name,
        "required_phases": list(required_ids),
        "phase_checks": phase_checks,
        "all_complete": all_complete,
        "all_guardrails_ok": all_guardrails_ok,
    }


# ── Artifact coverage ──────────────────────────────────────────────────────────

def _build_artifact_coverage(artifact_root_records: Any) -> dict[str, Any]:
    records = list(artifact_root_records) if isinstance(artifact_root_records, (list, tuple)) else []
    roots_checked: list[dict[str, Any]] = []
    roots_present: list[str] = []
    roots_missing: list[str] = []
    for rec in records:
        rec = rec if isinstance(rec, dict) else {}
        kind = _str(rec.get("kind"))
        rel = _str(rec.get("rel"))
        optional = rec.get("optional", True) is not False
        present = bool(rec.get("present"))
        roots_checked.append({"kind": kind, "path": rel, "optional": optional, "present": present})
        (roots_present if present else roots_missing).append(rel)
    return {
        "roots_checked": roots_checked,
        "roots_present": roots_present,
        "roots_missing": roots_missing,
        "all_present": not roots_missing,
    }


# ── Documentation coverage ────────────────────────────────────────────────────

def _build_documentation_coverage(docs: Any) -> dict[str, Any]:
    docs = list(docs) if isinstance(docs, (list, tuple)) else []
    texts: dict[str, str] = {}
    doc_records: list[dict[str, Any]] = []
    for entry in docs:
        entry = entry if isinstance(entry, dict) else {}
        name = _str(entry.get("name"))
        present = bool(entry.get("present", True))
        text = _str(entry.get("text"))
        texts[name] = text
        doc_records.append({"name": name, "path": _norm_path(entry.get("path", "")), "present": present})

    readme_text = texts.get("README") or texts.get("readme") or ""
    roadmap_text = texts.get("roadmap") or texts.get("ROADMAP") or ""
    readme_path = next(
        (d["path"] for d in doc_records if d["name"] in ("README", "readme")), DEFAULT_README_REL
    )
    roadmap_path = next(
        (d["path"] for d in doc_records if d["name"] in ("roadmap", "ROADMAP")), DEFAULT_ROADMAP_REL
    )

    mentions: dict[str, dict[str, bool]] = {}
    missing_everywhere: list[str] = []
    for pid in DOC_PHASE_IDS:
        in_readme = pid in readme_text
        in_roadmap = pid in roadmap_text
        mentioned = in_readme or in_roadmap
        mentions[pid] = {"in_readme": in_readme, "in_roadmap": in_roadmap, "mentioned": mentioned}
        if not mentioned:
            missing_everywhere.append(pid)

    return {
        "readme_path": readme_path,
        "roadmap_path": roadmap_path,
        "docs": doc_records,
        "checked_phase_ids": list(DOC_PHASE_IDS),
        "mentions": mentions,
        "missing_phase_mentions": missing_everywhere,
    }


# ── Pure audit builder ─────────────────────────────────────────────────────────

def build_post_eval_cmd_checkpoint_audit(
    *,
    registry_data: Any,
    artifact_root_records: Any = (),
    docs: Any = (),
    registry_load_error: str = "",
    report_id: str = "",
    created_at: str = "",
    repo_path: str = "",
    registry_path: str = "",
) -> dict[str, Any]:
    """Build the ROAD.4 audit report from pre-gathered inputs.

    Pure: never reads files, writes files, runs commands, or contacts anything.
    ``registry_data`` is the parsed registry dict (or None on load failure);
    ``artifact_root_records`` is a list of {kind, rel, optional, present} dicts
    (directories, not JSON files); ``docs`` is a list of {name, path, present,
    text} dicts.
    """
    pick = pick_phase_candidates(registry_data)
    registry_valid = bool(pick.get("registry_valid"))
    registry_errors = list(pick.get("errors") or [])
    registry_warnings = list(pick.get("warnings") or [])
    phase_count = int(pick.get("phase_count", 0) or 0)
    buckets = pick.get("buckets") or {}
    safe = list(buckets.get("safe_to_prepare") or [])
    safe_to_prepare_count = len(safe)
    top_recommendation = pick.get("top_recommendation")

    blockers: list[str] = []
    warnings: list[str] = []

    if registry_load_error:
        blockers.append(f"phase registry could not be read: {registry_load_error}")
    if not registry_valid:
        detail = "; ".join(registry_errors[:5])
        blockers.append("phase registry is invalid" + (f": {detail}" if detail else ""))

    eval_arc = _build_arc_summary("EVAL", REQUIRED_EVAL_PHASE_IDS, registry_data)
    cmd_arc = _build_arc_summary("CMD", REQUIRED_CMD_PHASE_IDS, registry_data)

    all_checks = eval_arc["phase_checks"] + cmd_arc["phase_checks"]
    for check in all_checks:
        pid = check["phase_id"]
        if not check["present"]:
            blockers.append(f"required phase {pid} is not present in the registry")
        elif not check["complete"]:
            blockers.append(f"required phase {pid} is not complete (status: {check['status']})")
        for field in check.get("guardrail_violations") or []:
            blockers.append(f"phase {pid} has {field}=true; report-only arc violated")

    if safe_to_prepare_count > 0:
        ids = ", ".join(_str(s.get("phase_id")) for s in safe)
        warnings.append(
            f"phase picker reports {safe_to_prepare_count} safe-to-prepare candidate(s) ({ids}); "
            "expected all EVAL/CMD work complete"
        )
    if top_recommendation is not None:
        top_id = _str(top_recommendation.get("phase_id")) if isinstance(top_recommendation, dict) else ""
        warnings.append(f"phase picker still recommends work: {top_id or '(candidate)'}")

    artifact_coverage = _build_artifact_coverage(artifact_root_records)
    for rel in artifact_coverage["roots_missing"]:
        warnings.append(f"expected artifact root not present: {rel}")

    doc_coverage = _build_documentation_coverage(docs)
    for pid in doc_coverage["missing_phase_mentions"]:
        warnings.append(f"phase {pid} is not mentioned in the README or roadmap documentation")

    validation_story = {
        "validation_run": False,
        "note": (
            "ROAD.4 does not run validation commands. The validation commands stored in "
            "the registry for each phase were run externally by the human operator. "
            "No validation results are generated or interpreted by ROAD.4."
        ),
    }

    phase_violations = [
        {"phase_id": c["phase_id"], "field": f}
        for c in all_checks
        for f in (c.get("guardrail_violations") or [])
    ]
    guardrail_summary = {
        "road4_guardrails": _road4_guardrails(),
        "phase_guardrail_fields_checked": list(PHASE_GUARDRAIL_FIELDS),
        "phase_guardrail_violations": phase_violations,
        "all_clear": not phase_violations,
    }

    open_questions: list[str] = []
    if artifact_coverage["roots_missing"]:
        open_questions.append(
            "Some expected artifact root directories are absent. "
            "Were all EVAL/CMD phases run and artifacts written before this audit?"
        )
    if doc_coverage["missing_phase_mentions"]:
        open_questions.append(
            "Some phases are not mentioned in the README or roadmap. "
            "Should documentation be updated before freezing this checkpoint?"
        )

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)

    if blockers:
        status = STATUS_BLOCKED
        reason = f"{len(blockers)} blocker(s) prevent checkpoint passage"
    elif warnings:
        status = STATUS_WARN
        reason = f"{len(warnings)} warning(s) noted; checkpoint passes with warnings"
    else:
        status = STATUS_PASS
        reason = "all EVAL/CMD phases complete, report-only, artifact-backed, and documented"

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": _str(report_id),
        "created_at": _str(created_at),
        "repo_path": _norm_path(repo_path) if repo_path else "",
        "registry_path": _norm_path(registry_path) if registry_path else "",
        "audit_status": status,
        "audit_reason": reason,
        "registry_summary": {
            "registry_valid": registry_valid,
            "phase_count": phase_count,
            "errors": registry_errors,
            "warnings": registry_warnings,
        },
        "phase_picker_summary": {
            "safe_to_prepare_count": safe_to_prepare_count,
            "top_recommendation": top_recommendation,
            "all_work_complete": safe_to_prepare_count == 0 and top_recommendation is None,
        },
        "eval_arc_summary": eval_arc,
        "cmd_arc_summary": cmd_arc,
        "artifact_coverage": artifact_coverage,
        "documentation_coverage": doc_coverage,
        "validation_story": validation_story,
        "guardrail_summary": guardrail_summary,
        "open_questions": open_questions,
        "recommended_next_step": NEXT_STEP_BY_STATUS[status],
        "warnings": warnings,
        "blockers": blockers,
        "boundaries": list(ROAD4_BOUNDARIES),
    }


# ── Markdown renderer ──────────────────────────────────────────────────────────

def render_post_eval_cmd_checkpoint_audit_markdown(report: dict[str, Any]) -> str:
    """Render the ROAD.4 audit as operator-readable Markdown."""
    lines: list[str] = [
        "# Post-EVAL/CMD Checkpoint Audit",
        "",
        f"> {report.get('guardrail_note', GUARDRAIL_NOTE)}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(report.get('repo_path') or '(none)')}`",
        f"- **Registry path:** `{_md(report.get('registry_path') or '(none)')}`",
        f"- **Audit status:** `{_md(report.get('audit_status') or '(none)')}`",
        f"- **Audit reason:** {_md(report.get('audit_reason') or '(none)')}",
        f"- **Recommended next step:** `{_md(report.get('recommended_next_step') or '(none)')}`",
        "",
    ]

    lines += ["## Registry Summary", ""]
    reg = report.get("registry_summary") or {}
    lines.append(f"- **Registry valid:** {_lower(bool(reg.get('registry_valid')))}")
    lines.append(f"- **Phase count:** {reg.get('phase_count', 0)}")
    errors = reg.get("errors") or []
    if errors:
        lines += ["", "**Registry errors:**", ""]
        lines += [f"- {_md(e)}" for e in errors]
    lines.append("")

    lines += ["## Phase Picker Summary", ""]
    picker = report.get("phase_picker_summary") or {}
    lines.append(f"- **Safe-to-prepare count:** {picker.get('safe_to_prepare_count', 0)}")
    top = picker.get("top_recommendation")
    if isinstance(top, dict):
        top_text = f"{_md(top.get('phase_id', ''))} ({_md(top.get('title', ''))})"
    else:
        top_text = "(none)"
    lines.append(f"- **Top recommendation:** {top_text}")
    lines.append(f"- **All work complete:** {_lower(bool(picker.get('all_work_complete')))}")
    lines.append("")

    def _arc_section(header: str, arc: dict[str, Any]) -> None:
        lines.extend([f"## {header}", ""])
        lines.append(f"- **All complete:** {_lower(bool(arc.get('all_complete')))}")
        lines.append(f"- **All guardrails ok:** {_lower(bool(arc.get('all_guardrails_ok')))}")
        checks = arc.get("phase_checks") or []
        if checks:
            lines.extend([
                "",
                "| Phase | Present | Status | Complete | Guardrails OK | Violations |",
                "| --- | --- | --- | --- | --- | --- |",
            ])
            for c in checks:
                viols = ", ".join(c.get("guardrail_violations") or []) or "(none)"
                lines.append(
                    f"| {_md(c.get('phase_id'))} | {_lower(bool(c.get('present')))} | "
                    f"{_md(c.get('status'))} | {_lower(bool(c.get('complete')))} | "
                    f"{_lower(bool(c.get('guardrails_ok')))} | {_md(viols)} |"
                )
        lines.append("")

    _arc_section("EVAL Arc Summary", report.get("eval_arc_summary") or {})
    _arc_section("CMD Arc Summary", report.get("cmd_arc_summary") or {})

    lines += ["## Artifact Coverage", ""]
    art = report.get("artifact_coverage") or {}
    lines.append(f"- **All present:** {_lower(bool(art.get('all_present')))}")
    lines.append(f"- **Missing:** {', '.join(art.get('roots_missing') or []) or '(none)'}")
    roots = art.get("roots_checked") or []
    if roots:
        lines += ["", "| Kind | Path | Optional | Present |", "| --- | --- | --- | --- |"]
        for r in roots:
            lines.append(
                f"| {_md(r.get('kind'))} | `{_md(r.get('path'))}` | "
                f"{_lower(bool(r.get('optional')))} | {_lower(bool(r.get('present')))} |"
            )
    lines.append("")

    lines += ["## Documentation Coverage", ""]
    doc = report.get("documentation_coverage") or {}
    lines.append(f"- **README:** `{_md(doc.get('readme_path') or '(none)')}`")
    lines.append(f"- **Roadmap:** `{_md(doc.get('roadmap_path') or '(none)')}`")
    missing_docs = doc.get("missing_phase_mentions") or []
    lines.append(f"- **Phases missing from docs:** {', '.join(missing_docs) or '(none)'}")
    mentions = doc.get("mentions") or {}
    if mentions:
        lines += ["", "| Phase | In README | In roadmap |", "| --- | --- | --- |"]
        for pid in doc.get("checked_phase_ids") or []:
            entry = mentions.get(pid) or {}
            lines.append(
                f"| {_md(pid)} | {_lower(bool(entry.get('in_readme')))} | "
                f"{_lower(bool(entry.get('in_roadmap')))} |"
            )
    lines.append("")

    lines += ["## Validation Story", ""]
    vs = report.get("validation_story") or {}
    lines.append(f"- **Validation run:** {_lower(bool(vs.get('validation_run')))}")
    lines.append(f"- {_md(vs.get('note') or '(none)')}")
    lines.append("")

    lines += ["## Guardrail Summary", ""]
    gs = report.get("guardrail_summary") or {}
    lines.append(f"- **All clear:** {_lower(bool(gs.get('all_clear')))}")
    viols = gs.get("phase_guardrail_violations") or []
    if viols:
        lines += ["", "**Phase guardrail violations:**", ""]
        for v in viols:
            lines.append(f"- `{_md(v.get('field'))}` is true in phase `{_md(v.get('phase_id'))}`")
    else:
        lines.append("- No required phase reports any execution power.")
    road4_g = gs.get("road4_guardrails") or {}
    if road4_g:
        lines += ["", "**ROAD.4 own guardrails (all false):**", ""]
        for k, v in sorted(road4_g.items()):
            lines.append(f"- `{_md(k)}`: {_lower(bool(v))}")
    lines.append("")

    lines += ["## Open Questions", ""]
    oq = report.get("open_questions") or []
    if oq:
        for q in oq:
            lines.append(f"- {_md(q)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Recommended Next Step", ""]
    lines.append(f"- `{_md(report.get('recommended_next_step') or '(none)')}`")
    lines.append("")

    lines += ["## Warnings", ""]
    wlist = report.get("warnings") or []
    if wlist:
        for w in wlist:
            lines.append(f"- {_md(w)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Blockers", ""]
    blist = report.get("blockers") or []
    if blist:
        for b in blist:
            lines.append(f"- {_md(b)}")
    else:
        lines.append("_None — the EVAL and CMD arcs are complete._")
    lines.append("")

    lines += ["## Boundaries", ""]
    for b in (report.get("boundaries") or list(ROAD4_BOUNDARIES)):
        lines.append(f"- {_md(b)}")
    lines.append("")

    return "\n".join(lines) + "\n"


# ── Input gathering (read-only) ───────────────────────────────────────────────

def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read or parse {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def gather_post_eval_cmd_checkpoint_inputs(
    repo_path: str | Path,
    registry_path: str | Path,
) -> dict[str, Any]:
    """Read registry, artifact root dirs, and docs. Pure read-only."""
    repo = Path(repo_path)
    registry_data, registry_load_error = _load_json_object(Path(registry_path))

    artifact_root_records: list[dict[str, Any]] = []
    for kind, rel, optional in EXPECTED_ARTIFACT_ROOTS:
        target = repo / rel
        artifact_root_records.append({
            "kind": kind,
            "rel": rel,
            "optional": optional,
            "present": target.is_dir(),
        })

    docs: list[dict[str, Any]] = []
    for name, rel in (("README", DEFAULT_README_REL), ("roadmap", DEFAULT_ROADMAP_REL)):
        target = repo / rel
        present = target.is_file()
        text = ""
        if present:
            try:
                text = target.read_text(encoding="utf-8")
            except OSError:
                present = False
        docs.append({"name": name, "path": rel, "present": present, "text": text})

    return {
        "registry_data": registry_data,
        "registry_load_error": registry_load_error,
        "artifact_root_records": artifact_root_records,
        "docs": docs,
    }


# ── Report writing ─────────────────────────────────────────────────────────────

def write_post_eval_cmd_checkpoint_audit(
    repo_path: str | Path,
    registry_path: str | Path,
    output_dir: str | Path,
    *,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Gather inputs, build the audit, write JSON + Markdown. Returns {ok, json_path, md_path, report}."""
    inputs = gather_post_eval_cmd_checkpoint_inputs(repo_path, registry_path)
    report = build_post_eval_cmd_checkpoint_audit(
        registry_data=inputs["registry_data"],
        registry_load_error=inputs["registry_load_error"],
        artifact_root_records=inputs["artifact_root_records"],
        docs=inputs["docs"],
        report_id=report_id,
        created_at=created_at,
        repo_path=str(repo_path),
        registry_path=str(registry_path),
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_post_eval_cmd_checkpoint_audit_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
```

- [ ] **Step 2: Run the core tests (exclude CLI tests that need the script)**

```bash
python -m pytest tests/test_post_eval_cmd_checkpoint_audit.py -q -k "not cli and not seed_repo and not tmp_path" 2>&1 | tail -20
```

Expected: most unit tests pass; CLI-requiring tests skip or fail on import.

- [ ] **Step 3: Commit**

```bash
git add core/post_eval_cmd_checkpoint_audit.py
git commit -m "feat: implement ROAD.4 post-EVAL/CMD checkpoint audit core module"
```

---

## Task 3: Implement the CLI Script

**Files:**
- Create: `scripts/create_post_eval_cmd_checkpoint_audit.py`

- [ ] **Step 1: Create the script**

```python
"""ROAD.4 — Create Post-EVAL/CMD Checkpoint Audit (CLI).

Reads the phase registry, EVAL/CMD artifact roots, and documentation, then
writes a deterministic JSON + Markdown checkpoint audit under the output root.

Report-only: audits the completed EVAL and CMD arcs without choosing work,
executing phases, calling models, applying patches, running validation or
benchmarks, contacting network services, launching workers, pushing, merging,
or opening PRs.

Exit codes: 0 when audit_status is ``pass`` (or ``pass_with_warnings`` with
``--allow-warnings``); nonzero when ``blocked`` (or ``pass_with_warnings``
without ``--allow-warnings``).

Usage:
    python scripts/create_post_eval_cmd_checkpoint_audit.py \\
        --repo-path . \\
        --registry docs/roadmap/phase_registry.json \\
        --json --allow-warnings
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.post_eval_cmd_checkpoint_audit import (  # noqa: E402
    GUARDRAIL_NOTE,
    STATUS_BLOCKED,
    STATUS_WARN,
    write_post_eval_cmd_checkpoint_audit,
)

DEFAULT_REPO_PATH = "."
DEFAULT_REGISTRY = "docs/roadmap/phase_registry.json"
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "roadmap" / "post_eval_cmd_checkpoint")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_report_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'report'}_post-eval-cmd-checkpoint"


def run_create_post_eval_cmd_checkpoint_audit(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    registry: str = DEFAULT_REGISTRY,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    report_id: str | None = None,
    created_at: str | float | None = None,
) -> dict[str, Any]:
    """Build and write the ROAD.4 audit. Returns {ok, json_path, md_path, report, audit_status}."""
    created_iso = _resolve_created_at(created_at)
    final_report_id = report_id or _default_report_id(created_iso)
    result = write_post_eval_cmd_checkpoint_audit(
        repo_path,
        registry,
        output_root,
        report_id=final_report_id,
        created_at=created_iso,
    )
    result["audit_status"] = result["report"].get("audit_status")
    return result


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    print("ROAD.4 — Post-EVAL/CMD Checkpoint Audit")
    print("=" * 40)
    print(f"Report id          : {report.get('report_id')}")
    print(f"Repo path          : {report.get('repo_path')}")
    print(f"Registry           : {report.get('registry_path')}")
    print(f"Audit status       : {report.get('audit_status')}")
    print(f"Audit reason       : {report.get('audit_reason')}")
    print(f"Recommended next   : {report.get('recommended_next_step')}")
    reg = report.get("registry_summary") or {}
    print(f"Registry valid     : {reg.get('registry_valid')}")
    print(f"Phase count        : {reg.get('phase_count')}")
    eval_arc = report.get("eval_arc_summary") or {}
    print(f"EVAL arc complete  : {eval_arc.get('all_complete')}")
    cmd_arc = report.get("cmd_arc_summary") or {}
    print(f"CMD arc complete   : {cmd_arc.get('all_complete')}")
    for b in report.get("blockers") or []:
        print(f"  BLOCKER: {b}")
    for w in report.get("warnings") or []:
        print(f"  WARNING: {w}")
    print(f"JSON               : {result['json_path']}")
    print(f"Markdown           : {result['md_path']}")
    print(f"\n> {GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ROAD.4: read the phase registry, EVAL/CMD artifact roots, and docs and write a "
            "checkpoint audit of the completed EVAL and CMD arcs. Report-only."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Path to registry JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Output directory.")
    parser.add_argument("--report-id", default=None, help="Deterministic report id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Created-at timestamp (ISO-8601 or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print report JSON to stdout.")
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Exit 0 even when audit_status is 'pass_with_warnings'.",
    )
    args = parser.parse_args(argv)

    result = run_create_post_eval_cmd_checkpoint_audit(
        repo_path=args.repo_path,
        registry=args.registry,
        output_root=args.output_root,
        report_id=args.report_id,
        created_at=args.created_at,
    )

    if args.json:
        print(json.dumps(result["report"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    status = result["audit_status"]
    if status == STATUS_BLOCKED:
        return 1
    if status == STATUS_WARN and not args.allow_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run all prescribed tests**

```bash
python -m pytest tests/test_post_eval_cmd_checkpoint_audit.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add scripts/create_post_eval_cmd_checkpoint_audit.py
git commit -m "feat: implement ROAD.4 create_post_eval_cmd_checkpoint_audit script"
```

---

## Task 4: Update the Phase Registry

**Files:**
- Modify: `docs/roadmap/phase_registry.json`

- [ ] **Step 1: Add the ROAD.4 entry to the end of the `phases` array and update `updated_at`**

In `docs/roadmap/phase_registry.json`, change `"updated_at": "2026-06-22T00:00:00+00:00"` to `"updated_at": "2026-06-23T00:00:00+00:00"` and append this entry after CMD.4:

```json
    {
      "phase_id": "ROAD.4",
      "title": "Post-EVAL/CMD Checkpoint Audit",
      "track": "ROAD",
      "status": "complete",
      "summary": "Report-only checkpoint audit that verifies EVAL.1-3 and CMD.1-4 are registered, complete, report-only, artifact-backed, and documented.",
      "automation_level": "LOCAL_0_OBSERVE",
      "budget_tier": "local_only",
      "risk_level": "low",
      "allowed_files": [
        "core/post_eval_cmd_checkpoint_audit.py",
        "scripts/create_post_eval_cmd_checkpoint_audit.py",
        "tests/test_post_eval_cmd_checkpoint_audit.py",
        "tests/test_phase_registry.py",
        "tests/test_phase_picker.py",
        "docs/roadmap/phase_registry.json",
        "README.md",
        "docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md"
      ],
      "forbidden_files": [
        ".env",
        ".git",
        ".agent/private",
        "secrets",
        "credentials"
      ],
      "validation": [
        "python -m compileall -q core scripts web tests benchmarks",
        "python -m pytest tests/test_post_eval_cmd_checkpoint_audit.py -q",
        "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
        "python scripts/create_post_eval_cmd_checkpoint_audit.py --repo-path . --registry docs/roadmap/phase_registry.json --json --allow-warnings",
        "python -m pytest -q",
        "python benchmarks/run_benchmarks.py --check"
      ],
      "human_approval_required": true,
      "merge_allowed": false,
      "network_allowed": false,
      "model_calls_allowed": false,
      "writes_real_repo": false,
      "requires_sandbox": false,
      "prerequisites": [
        "CMD.4"
      ],
      "expected_artifacts": [
        ".agent/roadmap/post_eval_cmd_checkpoint/post_eval_cmd_checkpoint_audit.json",
        ".agent/roadmap/post_eval_cmd_checkpoint/post_eval_cmd_checkpoint_audit.md"
      ],
      "notes": [
        "Report-only checkpoint audit, shipped 2026-06-23. Reads the phase registry, EVAL.1-3 and CMD.1-4 artifact roots, and documentation; writes a deterministic JSON/Markdown checkpoint audit of the completed EVAL and CMD arcs. Does not choose work, execute phases, call models, apply patches, run validation, run benchmarks, contact network services, launch workers, push, merge, or open PRs."
      ]
    }
```

- [ ] **Step 2: Validate the updated registry**

```bash
python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json
```

Expected: `"is_valid": true`, `"errors": []`

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap/phase_registry.json
git commit -m "feat: register ROAD.4 in phase registry (17th phase, ROAD track)"
```

---

## Task 5: Update Ripple Tests

**Files:**
- Modify: `tests/test_phase_registry.py`
- Modify: `tests/test_phase_picker.py`

- [ ] **Step 1: Update `test_phase_registry.py`**

Find `test_seed_registry_has_expected_phases` (around line 520). Make two changes:

Change the set assertion to include `"ROAD.4"`:
```python
    assert {
        "ROAD.1", "ROAD.2", "ROAD.3", "ROAD.4", "AUTO.2a", "AUTO.2b", "AUTO.2c",
        "MODEL.1", "MODEL.2", "MODEL.3", "EVAL.1", "EVAL.2", "EVAL.3", "CMD.1", "CMD.2", "CMD.3", "CMD.4",
    } <= ids
    assert len(data["phases"]) == 17
```

Find `test_seed_registry_summary_counts` (around line 542). Change the ROAD count from 3 to 4:
```python
    assert report["counts_by_track"] == {"AUTO": 3, "CMD": 4, "EVAL": 3, "MODEL": 3, "ROAD": 4}
```

- [ ] **Step 2: Update `test_phase_picker.py`**

Find `test_seed_registry_produces_expected_buckets` (around line 553). Update the comment and bucket count:
```python
    # ROAD.1, ROAD.2, ROAD.3, ROAD.4, AUTO.2a, AUTO.2b, AUTO.2c, MODEL.1, MODEL.2,
    # MODEL.3, EVAL.1, EVAL.2, EVAL.3, CMD.1, CMD.2, CMD.3, and CMD.4 are shipped (complete);
    # no proposed seed phase remains safe.
    assert report["bucket_counts"] == {
        "safe_to_prepare": 0,
        "sandbox_required": 0,
        "human_approval_required": 0,
        "blocked": 0,
        "deferred_or_parked": 0,
        "complete_or_history": 17,
    }
    # ROAD.4 shipped; there is no remaining seed recommendation.
    assert report["top_recommendation"] is None
```

Find `test_seed_shipped_phases_are_complete_and_not_recommended` (around line 580). Add `"ROAD.4"` to the shipped list:
```python
    shipped = ["ROAD.1", "ROAD.2", "ROAD.3", "ROAD.4", "AUTO.2a", "AUTO.2b", "AUTO.2c", "MODEL.1", "MODEL.2", "MODEL.3", "EVAL.1", "EVAL.2", "EVAL.3", "CMD.1", "CMD.2", "CMD.3", "CMD.4"]
```

Also find `test_seed_safe_candidates_sorted_deterministically` (around line 572). Update the comment:
```python
    # Completed ROAD.1/ROAD.2/ROAD.3/ROAD.4/AUTO.2a/AUTO.2b/AUTO.2c/MODEL.1/MODEL.2/MODEL.3/EVAL.1/EVAL.2/EVAL.3/CMD.1/CMD.2/CMD.3/CMD.4 all drop out.
    assert ids == []
```

- [ ] **Step 3: Run the updated registry and picker tests**

```bash
python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase_registry.py tests/test_phase_picker.py
git commit -m "test: update phase registry and picker tests for ROAD.4 (17 phases)"
```

---

## Task 6: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md`

- [ ] **Step 1: Add ROAD.4 section to README.md**

After the `## Commander Readiness Report (CMD.4)` section (which ends around line 1630), insert:

```markdown
## Post-EVAL/CMD Checkpoint Audit (ROAD.4)

ROAD.4 is the **checkpoint** that closes the EVAL and CMD arcs. It reads the
phase registry, EVAL.1–3 and CMD.1–4 artifact root directories, and project
documentation, then writes a deterministic audit that verifies all seven
required phases are registered, complete, report-only, artifact-backed, and
mentioned in the docs.

```bash
python scripts/create_post_eval_cmd_checkpoint_audit.py \
    --repo-path . \
    --registry docs/roadmap/phase_registry.json \
    --json --allow-warnings
```

- It writes `.agent/roadmap/post_eval_cmd_checkpoint/post_eval_cmd_checkpoint_audit.json`
  and `.agent/roadmap/post_eval_cmd_checkpoint/post_eval_cmd_checkpoint_audit.md`.
- Audit statuses are `pass`, `pass_with_warnings`, and `blocked`. The CLI
  exits nonzero on `blocked`, and on `pass_with_warnings` unless
  `--allow-warnings` is given.
- Per-phase guardrail checks confirm that no EVAL or CMD phase has
  `model_calls_allowed`, `network_allowed`, `merge_allowed`, or
  `writes_real_repo` set to `true`.
- **ROAD.4 does not choose new work, execute phases, call models, apply
  patches, run validation, run benchmarks, contact network services, launch
  workers, push, merge, or open PRs.** It is a report-only checkpoint audit.

Important files:

- `core/post_eval_cmd_checkpoint_audit.py`
- `scripts/create_post_eval_cmd_checkpoint_audit.py`
- `tests/test_post_eval_cmd_checkpoint_audit.py`
```

- [ ] **Step 2: Update the roadmap doc**

In `docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md`, find the ROAD section (around line 15) and add ROAD.4:

In section `### ROAD: Governance, Registry, Picker, Audit` (around line 15), add after the ROAD.3 bullet:
```
- ROAD.4 completed the post-EVAL/CMD checkpoint audit.
```

In the `### Branch CMD — Commander Mode` phases list (around line 121–126), add after CMD.4:
```
- ROAD.4 — Post-EVAL/CMD Checkpoint Audit — shipped 2026-06-23 (complete).
```

In section `## 5. Recommended Priority` (around line 185), update the description under CMD to note ROAD.4:
Find the sentence: "CMD.4 is shipped as a report-only Commander Readiness / Stop Condition Report..."
Append: "ROAD.4 is also shipped as a report-only post-EVAL/CMD checkpoint audit that verifies the completed EVAL and CMD arcs are registered, complete, report-only, artifact-backed, and documented."

- [ ] **Step 3: Verify docs mention all DOC_PHASE_IDS**

```bash
python -c "
from core.post_eval_cmd_checkpoint_audit import DOC_PHASE_IDS
readme = open('README.md').read()
roadmap = open('docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md').read()
missing = [pid for pid in DOC_PHASE_IDS if pid not in readme and pid not in roadmap]
print('Missing:', missing or 'none')
"
```

Expected: `Missing: none`

- [ ] **Step 4: Commit**

```bash
git add README.md "docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md"
git commit -m "docs: add ROAD.4 section to README and roadmap"
```

---

## Task 7: Run Full Validation Suite

**Files:** (none — validation only)

- [ ] **Step 1: Compile-all**

```bash
python -m compileall -q core scripts web tests benchmarks
```

Expected: no output (no errors).

- [ ] **Step 2: Run ROAD.4 tests specifically**

```bash
python -m pytest tests/test_post_eval_cmd_checkpoint_audit.py -q
```

Expected: all tests pass, 0 failures.

- [ ] **Step 3: Validate the phase registry**

```bash
python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json
```

Expected: `"is_valid": true`, `"errors": []`, `"phase_count": 17`.

- [ ] **Step 4: Run the CLI against the real repo**

```bash
python scripts/create_post_eval_cmd_checkpoint_audit.py --repo-path . --registry docs/roadmap/phase_registry.json --json --allow-warnings
```

Expected: JSON output with `"audit_status": "pass"` or `"pass_with_warnings"` (warnings are acceptable if artifact roots are present but docs are missing ROAD.4 before the doc update lands). No `"blocked"` status expected.

- [ ] **Step 5: Verify the artifacts were written**

```bash
python -c "
from pathlib import Path
j = Path('.agent/roadmap/post_eval_cmd_checkpoint/post_eval_cmd_checkpoint_audit.json')
m = Path('.agent/roadmap/post_eval_cmd_checkpoint/post_eval_cmd_checkpoint_audit.md')
print('JSON:', j.is_file(), j)
print('Markdown:', m.is_file(), m)
"
```

Expected: both `True`.

- [ ] **Step 6: Run the full test suite**

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 7: Run benchmark check**

```bash
python benchmarks/run_benchmarks.py --check
```

Expected: exits 0.

- [ ] **Step 8: Final commit with audit artifacts**

```bash
git add .agent/roadmap/post_eval_cmd_checkpoint/
git commit -m "feat: complete ROAD.4 post-EVAL/CMD checkpoint audit with artifacts"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Covered by |
| --- | --- |
| Core file `post_eval_cmd_checkpoint_audit.py` | Task 2 |
| Script `create_post_eval_cmd_checkpoint_audit.py` | Task 3 |
| Test file (18 prescribed cases) | Task 1 |
| All 7 EVAL/CMD phases checked | `_build_arc_summary`, tests 2–8 |
| `model_calls_allowed` / `network_allowed` / `merge_allowed` / `writes_real_repo` → blocks | tests 5–8 |
| Missing artifact dirs → warning | test 9 |
| Missing docs → warning | test 10 |
| Picker safe_to_prepare > 0 → warning | test 11 |
| Picker top_recommendation not null → warning | test 12 |
| `pass_with_warnings` + `--allow-warnings` → exit 0 | test 13 |
| All 14 Markdown sections + 10 boundary statements | test 14 |
| CLI writes `.json` + `.md` | test 15 |
| CLI `--json` prints JSON | test 16 |
| All ROAD.4 guardrails False | test 17 |
| 10 source-level forbidden-token categories | test 18 |
| Registry JSON updated (17 phases, ROAD 4) | Task 4 |
| `test_phase_registry.py` ripple | Task 5 |
| `test_phase_picker.py` ripple | Task 5 |
| README + roadmap mention ROAD.4 | Task 6 |
| Output at `.agent/roadmap/post_eval_cmd_checkpoint/` | Core + script |
| Status names `pass` / `pass_with_warnings` / `blocked` | Constants |
| Recommended next steps per status | `NEXT_STEP_BY_STATUS` |

**Placeholder scan:** None found. All code blocks are complete.

**Type consistency:** `build_post_eval_cmd_checkpoint_audit` → `write_post_eval_cmd_checkpoint_audit` → `run_create_post_eval_cmd_checkpoint_audit` → `main`. All use `str | Path` / `str | float | None` consistently. `_build_arc_summary` returns `dict[str, Any]` with `phase_checks: list[dict]` — tests reference `c["phase_id"]`, `c["guardrail_violations"]` consistent with builder.
