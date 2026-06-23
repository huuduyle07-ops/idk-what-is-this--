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


# ── synthetic registry builders ───────────────────────────────────────────────

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


# ── 5. model_calls_allowed true blocks ────────────────────────────────────────

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


# ── 7. merge_allowed true blocks ──────────────────────────────────────────────

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
    assert report["artifact_coverage"]["roots_missing"]


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


# ── 14. Markdown contains required sections and boundaries ─────────────────────

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
    allowed_top = {"__future__", "json", "pathlib", "re", "typing", "core"}
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
        "codex", "gemini", "deepseek", "call_model(", "launch_model(",
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


# ── External audit helpers ─────────────────────────────────────────────────────

def _audit_text_c2_csrf() -> str:
    return (
        "Tally (deduped across runs): 3 critical · ~15 high · ~30 medium · ~35 low.\n\n"
        "## Executive summary\n\n"
        "- No auth, no CSRF on web UI → unauthenticated RCE.\n\n"
        "## 🔴 CRITICAL (3)\n\n"
        "### C2. No authentication / CSRF on a web UI that performs destructive ops\n"
        "web/app.py:80-88 — No auth, no CSRF. CONFIRMED CRITICAL (unanimous)\n\n"
        "### Recalibrated priority\n"
        "1. **C2** (confirmed unauthenticated RCE, small fix) — do first.\n"
    )


def _audit_text_no_signals() -> str:
    return "All systems nominal. No critical findings identified.\n"


def _build_with_audit(audit_text=None, audit_path="docs/audit.md", **over) -> dict:
    kwargs = dict(
        registry_data=_registry(),
        artifact_root_records=_clean_roots(),
        docs=_docs(),
        report_id="r",
        created_at="t",
        repo_path=".",
        registry_path="docs/roadmap/phase_registry.json",
        external_audit_text=audit_text,
        external_audit_path=audit_path,
    )
    kwargs.update(over)
    return build_post_eval_cmd_checkpoint_audit(**kwargs)


# ── 13. missing external audit file produces warning but not blocker ──────────

def test_missing_external_audit_file_produces_warning_not_blocker():
    # Path provided but text=None (file not found) → warning, not blocker.
    report = _build_with_audit(audit_text=None, audit_path="docs/audit-missing.md")
    assert report["audit_status"] in (STATUS_PASS, STATUS_WARN)
    assert not any("external audit" in b.lower() for b in report["blockers"])
    assert any("external audit" in w.lower() for w in report["warnings"])


def test_no_external_audit_path_no_warning_and_human_choice():
    # No path provided at all → no external-audit warning, HUMAN_CHOICE branch.
    report = _build()
    assert not any("external audit" in w.lower() for w in report["warnings"])
    assert report.get("recommended_next_branch") == "HUMAN_CHOICE"


def test_missing_external_audit_recommended_human_choice():
    report = _build_with_audit(audit_text=None, audit_path="docs/audit.md")
    assert report.get("recommended_next_branch") == "HUMAN_CHOICE"


# ── 14. external audit with C2/web auth/CSRF signal recommends HARDEN.1 ───────

def test_external_audit_c2_csrf_recommends_harden_branch():
    report = _build_with_audit(audit_text=_audit_text_c2_csrf())
    assert report.get("recommended_next_branch") == "HARDEN"
    assert "HARDEN.1" in (report.get("recommended_next_phase") or "")


def test_external_audit_c2_csrf_recommended_step_is_start_hardening():
    report = _build_with_audit(audit_text=_audit_text_c2_csrf())
    assert report.get("recommended_next_step") == "start_hardening_branch"


def test_external_audit_no_signals_recommends_ux_or_harden():
    report = _build_with_audit(audit_text=_audit_text_no_signals())
    assert report.get("recommended_next_branch") == "UX_OR_HARDEN"


# ── 15. external audit critical/high tally summarized deterministically ────────

def test_external_audit_tally_summarized_deterministically():
    from core.post_eval_cmd_checkpoint_audit import parse_external_audit
    text = "Tally (deduped across runs): 3 critical · ~15 high · ~30 medium · ~35 low."
    r1 = parse_external_audit(text)
    r2 = parse_external_audit(text)
    assert r1 == r2
    assert r1["critical_count"] == 3
    assert r1["high_count"] == 15
    assert r1["medium_count"] == 30
    assert r1["low_count"] == 35


def test_external_audit_parse_c2_signals():
    from core.post_eval_cmd_checkpoint_audit import parse_external_audit
    result = parse_external_audit(_audit_text_c2_csrf())
    assert result["c2_web_auth_csrf_signal"] is True
    assert result["has_critical"] is True
    assert result["critical_count"] == 3


def test_external_audit_parse_no_signals():
    from core.post_eval_cmd_checkpoint_audit import parse_external_audit
    result = parse_external_audit(_audit_text_no_signals())
    assert result["c2_web_auth_csrf_signal"] is False
    assert result["has_critical"] is False
    assert result["critical_count"] == 0


# ── New required fields in report ─────────────────────────────────────────────

def test_report_has_external_audit_fields():
    report = _build_with_audit(audit_text=_audit_text_c2_csrf(), audit_path="docs/audit.md")
    for key in (
        "external_audit_path",
        "external_audit_summary",
        "critical_findings_snapshot",
        "recalibrated_risk_priority",
        "security_debt_carryover",
        "recommended_next_branch",
        "recommended_next_phase",
    ):
        assert key in report, f"Missing field: {key!r}"
    assert report["external_audit_path"] == "docs/audit.md"
    assert isinstance(report["external_audit_summary"], dict)


def test_report_external_audit_summary_structure():
    report = _build_with_audit(audit_text=_audit_text_c2_csrf())
    ea = report["external_audit_summary"]
    assert "critical_count" in ea
    assert "high_count" in ea
    assert "c2_web_auth_csrf_signal" in ea
    assert ea["critical_count"] == 3


# ── Markdown contains new sections ────────────────────────────────────────────

def test_markdown_contains_external_audit_sections():
    md = render_post_eval_cmd_checkpoint_audit_markdown(
        _build_with_audit(audit_text=_audit_text_c2_csrf())
    )
    low = md.lower()
    for section in (
        "## external audit summary",
        "## critical findings snapshot",
        "## recalibrated risk priority",
        "## security debt carryover",
        "## recommended next branch",
    ):
        assert section in low, f"Missing Markdown section: {section!r}"


# ── CLI accepts --external-audit flag ─────────────────────────────────────────

def _write_audit(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_cli_external_audit_flag_produces_harden_recommendation(tmp_path):
    repo = _seed_repo(tmp_path, include_roots=True)
    audit_file = tmp_path / "audit.md"
    _write_audit(audit_file, _audit_text_c2_csrf())
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--external-audit", str(audit_file),
        "--output-root", str(out),
        "--report-id", "ea",
        "--created-at", "t",
        "--allow-warnings",
    ])
    assert code == 0
    data = json.loads(
        (out / "post_eval_cmd_checkpoint_audit.json").read_text(encoding="utf-8")
    )
    assert data["recommended_next_branch"] == "HARDEN"
    assert "HARDEN.1" in data["recommended_next_phase"]


def test_cli_missing_external_audit_file_is_warning(tmp_path):
    repo = _seed_repo(tmp_path, include_roots=True)
    out = tmp_path / "out"
    code = script.main([
        "--repo-path", str(repo),
        "--registry", str(repo / "docs" / "roadmap" / "phase_registry.json"),
        "--external-audit", str(tmp_path / "nonexistent.md"),
        "--output-root", str(out),
        "--report-id", "ea",
        "--created-at", "t",
        "--allow-warnings",
    ])
    assert code == 0  # warning but allowed
    data = json.loads(
        (out / "post_eval_cmd_checkpoint_audit.json").read_text(encoding="utf-8")
    )
    assert data["audit_status"] == STATUS_WARN
    assert any("external audit" in w.lower() for w in data["warnings"])
