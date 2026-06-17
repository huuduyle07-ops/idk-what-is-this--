"""Tests for AUTO.1c — Sandbox Patch Candidate Evaluation.

Covers the prescribed cases:
1.  a safe patch applies inside the sandbox only.
2.  the real repo remains unchanged.
3.  a forbidden-path patch is rejected.
4.  a parent-traversal path is rejected.
5.  an empty patch is rejected.
6.  a huge patch is blocked (or allowed only when explicitly marked).
7.  a blocked AUTO.1a contract refuses to run.
8.  a self-approval contract refuses to run.
9.  an auto-merge contract refuses to run.
10. validation runs through the A.18 safe path only.
11. no validation declared -> validation skipped.
12. validation side effects are reported.
13. patch apply failure is reported, with no retry loop.
14. cleanup removes only the managed sandbox.
15. Markdown contains summary / patch safety / validation / side effects / boundaries.
16. JSON contains all guardrail booleans.
17. CLI writes JSON + Markdown.
18. deterministic `--trial-id` and `--created-at`.
19. no forbidden imports / calls (model client, patch generation, real-repo
    patch apply, Dream, Project Evolution, network, lesson promotion, proposal
    import, worker launch, remote git host / chat / external automation, or
    auto-merge).
"""
from __future__ import annotations

import ast
import difflib
import json
from pathlib import Path

from core.sandbox_patch_candidate_evaluation import (
    MAX_PATCH_LINES,
    PATCH_EVAL_VERDICTS,
    REPORT_KIND,
    apply_candidate_in_sandbox,
    classify_patch_safety,
    evaluate_patch_candidate,
    parse_unified_diff,
    patch_contract_block_reason,
    render_patch_candidate_evaluation_markdown,
)
from core.validation_side_effects import snapshot_repo_files
import scripts.evaluate_sandbox_patch_candidate as script


# ── helpers ───────────────────────────────────────────────────────────────────

FOO_BEFORE = "a = 1\nb = 2\nc = 3\n"
FOO_AFTER = "a = 1\nb = 20\nc = 3\n"


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "core").mkdir(parents=True)
    (repo / "core" / "foo.py").write_text(FOO_BEFORE, encoding="utf-8")
    (repo / "writer.py").write_text(
        "with open('side_effect.txt', 'w', encoding='utf-8') as f:\n"
        "    f.write('hello')\n",
        encoding="utf-8",
    )
    for d in (".git", ".agent"):
        (repo / d).mkdir()
        (repo / d / "marker").write_text("x", encoding="utf-8")
    return repo


def _patch(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _foo_patch() -> str:
    return _patch("core/foo.py", FOO_BEFORE, FOO_AFTER)


def _new_file_patch(path: str, lines: list[str]) -> str:
    body = "".join(f"+{ln}\n" for ln in lines)
    return f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def _ok_contract(**over) -> dict:
    base = {
        "verdict": "eligible_for_review",
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "automation_level": "SANDBOX_2_DRAFT_PATCH",
        "sandbox_required": True,
        "human_approval_required": True,
    }
    base.update(over)
    return base


def _evaluate(repo: Path, tmp_path: Path, *, patch_text: str, name: str, **over) -> dict:
    params = dict(
        repo_path=str(repo),
        contract=_ok_contract(),
        patch_text=patch_text,
        validation_commands=[],
        sandbox_root=str(tmp_path / f"sb_{name}"),
        trial_id=name,
        created_at="x",
    )
    params.update(over)
    return evaluate_patch_candidate(**params)


# ── 1. safe patch applies inside sandbox only ─────────────────────────────────

def test_safe_patch_applies_inside_sandbox_only(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(
        repo,
        tmp_path,
        patch_text=_foo_patch(),
        name="t1",
        validation_commands=[["python", "-m", "compileall", "-q", "core"]],
    )
    assert rec["verdict"] == "patch_candidate_passed"
    assert rec["patch_applied_to_sandbox"] is True
    sandbox_foo = Path(rec["sandbox_path"]) / "core" / "foo.py"
    assert sandbox_foo.read_text(encoding="utf-8") == FOO_AFTER
    # real repo file untouched
    assert (repo / "core" / "foo.py").read_text(encoding="utf-8") == FOO_BEFORE
    assert "core/foo.py" in rec["patch_changed_files"]


def test_new_file_patch_creates_file_in_sandbox(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_new_file_patch("pkg/new.txt", ["hi", "there"]), name="t1b")
    assert rec["patch_applied_to_sandbox"] is True
    created = Path(rec["sandbox_path"]) / "pkg" / "new.txt"
    assert created.read_text(encoding="utf-8") == "hi\nthere\n"
    assert not (repo / "pkg" / "new.txt").exists()


# ── 2. real repo remains unchanged ────────────────────────────────────────────

def test_real_repo_remains_unchanged(tmp_path):
    repo = _make_repo(tmp_path)
    before = snapshot_repo_files(str(repo))
    rec = _evaluate(
        repo,
        tmp_path,
        patch_text=_foo_patch(),
        name="t2",
        validation_commands=[["python", "writer.py"]],
    )
    after = snapshot_repo_files(str(repo))
    assert before == after
    assert rec["real_repo_modified"] is False


# ── 3-5. patch safety rejections ──────────────────────────────────────────────

def test_forbidden_path_patch_rejected(tmp_path):
    repo = _make_repo(tmp_path)
    patch = _patch(".env", "SECRET=old\n", "SECRET=new\n")
    rec = _evaluate(repo, tmp_path, patch_text=patch, name="t3")
    assert rec["verdict"] == "patch_candidate_rejected_by_safety"
    assert rec["patch_applied_to_sandbox"] is False
    assert rec["patch_safety"]["rejected_paths"]


def test_secrets_path_patch_rejected(tmp_path):
    repo = _make_repo(tmp_path)
    patch = _new_file_patch("secrets/key.txt", ["abc"])
    rec = _evaluate(repo, tmp_path, patch_text=patch, name="t3b")
    assert rec["verdict"] == "patch_candidate_rejected_by_safety"


def test_parent_traversal_path_rejected(tmp_path):
    repo = _make_repo(tmp_path)
    patch = _patch("../evil.py", "x = 1\n", "x = 2\n")
    rec = _evaluate(repo, tmp_path, patch_text=patch, name="t4")
    assert rec["verdict"] == "patch_candidate_rejected_by_safety"
    assert rec["patch_applied_to_sandbox"] is False


def test_empty_patch_rejected(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text="   \n", name="t5")
    assert rec["verdict"] == "patch_candidate_rejected_by_safety"
    assert rec["patch_safety"]["empty"] is True


# ── 6. huge patch blocked unless explicitly allowed ───────────────────────────

def test_huge_patch_blocked(tmp_path):
    repo = _make_repo(tmp_path)
    big = [f"line_{i}" for i in range(MAX_PATCH_LINES + 50)]
    patch = _new_file_patch("pkg/huge.txt", big)
    rec = _evaluate(repo, tmp_path, patch_text=patch, name="t6")
    assert rec["verdict"] == "patch_candidate_rejected_by_safety"
    assert rec["patch_safety"]["too_large"] is True


def test_huge_patch_allowed_when_marked(tmp_path):
    repo = _make_repo(tmp_path)
    big = [f"line_{i}" for i in range(MAX_PATCH_LINES + 50)]
    patch = _new_file_patch("pkg/huge.txt", big)
    rec = _evaluate(repo, tmp_path, patch_text=patch, name="t6b", allow_large=True)
    assert rec["verdict"] != "patch_candidate_rejected_by_safety"
    assert rec["patch_applied_to_sandbox"] is True


# ── 7-9. contract gate refusals ───────────────────────────────────────────────

def test_blocked_contract_refuses(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_foo_patch(), name="t7", contract=_ok_contract(verdict="blocked"))
    assert rec["verdict"] == "blocked_by_contract"
    assert rec["sandbox_created"] is False


def test_self_approval_contract_refuses(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_foo_patch(), name="t8", contract=_ok_contract(self_approval_allowed=True))
    assert rec["verdict"] == "blocked_by_contract"


def test_auto_merge_contract_refuses(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_foo_patch(), name="t9", contract=_ok_contract(eligible_for_auto_merge=True))
    assert rec["verdict"] == "blocked_by_contract"


def test_below_sandbox_level_refuses_unless_test_mode(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_foo_patch(), name="t9b", contract=_ok_contract(automation_level="LOCAL_0_OBSERVE"))
    assert rec["verdict"] == "blocked_by_contract"
    rec2 = _evaluate(
        repo,
        tmp_path,
        patch_text=_foo_patch(),
        name="t9c",
        contract=_ok_contract(automation_level="LOCAL_0_OBSERVE"),
        allow_below_sandbox_level=True,
    )
    assert rec2["verdict"] != "blocked_by_contract"


def test_patch_contract_block_reason_direct():
    assert patch_contract_block_reason(_ok_contract()) == ""
    assert patch_contract_block_reason(_ok_contract(verdict="blocked"))
    assert patch_contract_block_reason(_ok_contract(automation_level="LOCAL_1_PREPARE"))
    assert patch_contract_block_reason(
        _ok_contract(automation_level="LOCAL_1_PREPARE"), allow_below_sandbox_level=True
    ) == ""


# ── 10-12. validation behaviour ───────────────────────────────────────────────

def test_validation_runs_through_safe_path_only(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(
        repo,
        tmp_path,
        patch_text=_foo_patch(),
        name="t10",
        validation_commands=[["python", "-m", "compileall", "-q", "core"]],
    )
    assert rec["validation_run_by_tool"] is True
    assert rec["validation_commands"][0]["exit_code"] == 0
    assert rec["verdict"] == "patch_candidate_passed"


def test_unsafe_validation_command_is_blocked(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(
        repo,
        tmp_path,
        patch_text=_foo_patch(),
        name="t10b",
        validation_commands=[["bash", "-c", "echo hi"]],
    )
    assert rec["validation_commands"][0]["blocked"] is True
    assert rec["verdict"] == "patch_candidate_failed_validation"


def test_no_validation_declared_is_skipped(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_foo_patch(), name="t11", validation_commands=[])
    assert rec["verdict"] == "validation_skipped"
    assert rec["validation_run_by_tool"] is False
    assert rec["patch_applied_to_sandbox"] is True


def test_validation_side_effects_reported(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(
        repo,
        tmp_path,
        patch_text=_foo_patch(),
        name="t12",
        validation_commands=[["python", "writer.py"]],
    )
    created = [e["path"] for e in rec["validation_side_effects"]["created"]]
    assert "side_effect.txt" in created
    assert rec["side_effects_sandbox_only"] is True
    # the patch side effects record the patched file
    patch_changed = [e["path"] for e in rec["patch_side_effects"]["modified"]]
    assert "core/foo.py" in patch_changed


def test_failing_validation_marks_failed(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "boom.py").write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
    rec = _evaluate(
        repo,
        tmp_path,
        patch_text=_foo_patch(),
        name="t12b",
        validation_commands=[["python", "boom.py"]],
    )
    assert rec["verdict"] == "patch_candidate_failed_validation"
    assert rec["validation_commands"][0]["exit_code"] == 2


# ── 13. patch apply failure reported, no retry ────────────────────────────────

def test_patch_apply_failure_reported(tmp_path):
    repo = _make_repo(tmp_path)
    # context that does not exist in the sandbox file
    bad_patch = (
        "--- a/core/foo.py\n+++ b/core/foo.py\n@@ -1,1 +1,1 @@\n-z = 9\n+z = 99\n"
    )
    rec = _evaluate(repo, tmp_path, patch_text=bad_patch, name="t13")
    assert rec["verdict"] == "patch_candidate_failed_apply"
    assert rec["patch_applied_to_sandbox"] is False
    assert rec["apply_error"]
    # nothing was written: the sandbox file is unchanged
    sandbox_foo = Path(rec["sandbox_path"]) / "core" / "foo.py"
    assert sandbox_foo.read_text(encoding="utf-8") == FOO_BEFORE


# ── 14. cleanup removes only the managed sandbox ──────────────────────────────

def test_cleanup_removes_managed_sandbox(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_foo_patch(), name="t14", cleanup=True)
    assert rec["cleanup_performed"] is True
    assert not Path(rec["sandbox_path"]).exists()


def test_no_cleanup_keeps_sandbox(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_foo_patch(), name="t14b", cleanup=False)
    assert rec["cleanup_performed"] is False
    assert Path(rec["sandbox_path"]).is_dir()


# ── 15. Markdown sections ─────────────────────────────────────────────────────

def test_markdown_contains_required_sections(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(
        repo,
        tmp_path,
        patch_text=_foo_patch(),
        name="t15",
        validation_commands=[["python", "-m", "compileall", "-q", "core"]],
    )
    md = render_patch_candidate_evaluation_markdown(rec)
    assert "# Sandbox Patch Candidate Evaluation" in md
    assert "## Summary" in md
    assert "## Patch Safety" in md
    assert "## Validation" in md
    assert "## Side Effects" in md
    assert "## Boundaries" in md
    low = md.lower()
    assert "does not generate patches" in low
    assert "does not call models" in low
    assert "does not modify the real repo" in low
    assert "does not push, merge, open prs" in low
    assert "human approval is required before any real repo change" in low


# ── 16. guardrail booleans ────────────────────────────────────────────────────

def test_json_contains_all_guardrail_booleans(tmp_path):
    repo = _make_repo(tmp_path)
    rec = _evaluate(repo, tmp_path, patch_text=_foo_patch(), name="t16")
    boolean_keys = (
        "sandbox_created",
        "sandbox_only",
        "patch_candidate_supplied",
        "patch_generated",
        "patch_applied_to_sandbox",
        "patch_applied_to_real_repo",
        "real_repo_modified",
        "validation_run_by_tool",
        "benchmark_run_by_tool",
        "model_call_performed",
        "worker_launch_performed",
        "push_performed",
        "merge_performed",
        "self_approval_allowed",
        "eligible_for_auto_merge",
        "human_approval_required",
        "cleanup_performed",
    )
    for key in boolean_keys:
        assert key in rec, key
        assert isinstance(rec[key], bool), key
    assert rec["sandbox_only"] is True
    assert rec["patch_candidate_supplied"] is True
    assert rec["patch_generated"] is False
    assert rec["patch_applied_to_real_repo"] is False
    assert rec["real_repo_modified"] is False
    assert rec["model_call_performed"] is False
    assert rec["worker_launch_performed"] is False
    assert rec["push_performed"] is False
    assert rec["merge_performed"] is False
    assert rec["self_approval_allowed"] is False
    assert rec["eligible_for_auto_merge"] is False
    assert rec["human_approval_required"] is True
    assert rec["report_kind"] == REPORT_KIND
    assert rec["verdict"] in PATCH_EVAL_VERDICTS


# ── 17. CLI writes JSON + Markdown ────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    repo = _make_repo(tmp_path)
    patch_file = tmp_path / "candidate.patch"
    patch_file.write_text(_foo_patch(), encoding="utf-8")
    out = tmp_path / "out"
    res = script.run_evaluate_sandbox_patch_candidate(
        repo_path=str(repo),
        patch_file=str(patch_file),
        contract=_ok_contract(),
        validation_commands=[],
        sandbox_root=str(tmp_path / "sb"),
        trial_id="cli1",
        created_at="2026-06-17T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file()
    assert mp.is_file()
    assert jp.parent.name == "cli1"
    assert jp.name == "patch_candidate_evaluation.json"
    assert mp.name == "patch_candidate_evaluation.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["trial_id"] == "cli1"
    assert data["patch_applied_to_sandbox"] is True


def test_cli_main_smoke(tmp_path):
    repo = _make_repo(tmp_path)
    patch_file = tmp_path / "candidate.patch"
    patch_file.write_text(_foo_patch(), encoding="utf-8")
    out = tmp_path / "out"
    code = script.main(
        [
            "--repo-path",
            str(repo),
            "--patch-file",
            str(patch_file),
            "--trial-id",
            "clim",
            "--created-at",
            "2026-06-17T00:00:00+00:00",
            "--sandbox-root",
            str(tmp_path / "sb"),
            "--output-root",
            str(out),
            "--validation-json",
            '["python", "-m", "compileall", "-q", "core"]',
        ]
    )
    assert code == 0
    data = json.loads((out / "clim" / "patch_candidate_evaluation.json").read_text(encoding="utf-8"))
    assert data["verdict"] == "patch_candidate_passed"


def test_cli_requires_patch_file(tmp_path):
    repo = _make_repo(tmp_path)
    res = script.run_evaluate_sandbox_patch_candidate(
        repo_path=str(repo),
        patch_file=None,
        patch_text=None,
        contract=_ok_contract(),
        trial_id="x",
        created_at="x",
        output_root=str(tmp_path / "out"),
    )
    assert res["ok"] is False
    assert "patch" in res["error"].lower()


# ── 18. deterministic --trial-id and --created-at ─────────────────────────────

def test_deterministic_trial_id_and_created_at(tmp_path):
    repo = _make_repo(tmp_path)

    def run(name: str) -> dict:
        return script.run_evaluate_sandbox_patch_candidate(
            repo_path=str(repo),
            patch_text=_foo_patch(),
            patch_file="candidate.patch",
            contract=_ok_contract(verdict="blocked"),
            validation_commands=[],
            sandbox_root=str(tmp_path / "sb"),
            trial_id="fixed",
            created_at="2026-06-17T12:00:00+00:00",
            output_root=str(tmp_path / name),
        )

    a = run("a")
    b = run("b")
    da = Path(a["json_path"]).read_text(encoding="utf-8")
    db = Path(b["json_path"]).read_text(encoding="utf-8")
    assert da == db
    data = json.loads(da)
    assert data["trial_id"] == "fixed"
    assert data["created_at"] == "2026-06-17T12:00:00+00:00"
    assert data["verdict"] == "blocked_by_contract"


# ── parser / applier unit checks ──────────────────────────────────────────────

def test_parse_unified_diff_counts(tmp_path):
    parsed = parse_unified_diff(_foo_patch())
    assert parsed["file_count"] == 1
    assert parsed["touched_paths"] == ["core/foo.py"]
    assert parsed["added_total"] == 1
    assert parsed["removed_total"] == 1


def test_classify_patch_safety_empty():
    parsed = parse_unified_diff("")
    safety = classify_patch_safety(parsed, ".", allow_large=False)
    assert safety["ok"] is False
    assert safety["empty"] is True


def test_apply_candidate_in_sandbox_direct(tmp_path):
    sandbox = tmp_path / "sandbox"
    (sandbox / "core").mkdir(parents=True)
    (sandbox / "core" / "foo.py").write_text(FOO_BEFORE, encoding="utf-8")
    parsed = parse_unified_diff(_foo_patch())
    result = apply_candidate_in_sandbox(str(sandbox), parsed)
    assert result["ok"] is True
    assert (sandbox / "core" / "foo.py").read_text(encoding="utf-8") == FOO_AFTER


# ── 19. import / side-effect guard ────────────────────────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "sandbox_patch_candidate_evaluation.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "evaluate_sandbox_patch_candidate.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_safe():
    allowed_top = {"__future__", "json", "os", "shutil", "pathlib", "typing", "dataclasses", "re", "core"}
    allowed_core = {
        "core.sandbox_self_evolution_runner",
        "core.sandbox_self_evolution_trial",
        "core.validation_execution",
        "core.validation_side_effects",
        "core.patch_safety",
    }
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            if top == "core":
                assert module in allowed_core, f"Unexpected core import: {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_model_clients():
    for bad in (
        "anthropic",
        "openai",
        "litellm",
        "ollama",
        "bedrock",
        "generativeai",
        "claude",
        "codex",
        "gemini",
        "deepseek",
    ):
        assert bad not in _BOTH, f"Found model client token {bad!r}"


def test_no_patch_generation_or_real_repo_apply():
    for bad in ("generate_patch", "apply_patch", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_network_or_external_automation():
    for bad in (
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "telegram",
        "n8n",
        "github",
    ):
        assert bad not in _BOTH, f"Found network/automation token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "launch_worker", "worker_launch(", "spawn_worker"):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"
