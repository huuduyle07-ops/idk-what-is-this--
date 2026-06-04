"""Phase 11.7c — Default-Off CONTROL Anti-Lesson Injection (two-key gate).

The FIRST behavior-changing anti-lesson slice. ``build_control_prompt`` may now
append an ``[ANTI-LESSONS / DO NOT REPEAT — EXPERIMENTAL]`` block, but ONLY when
BOTH keys are turned:

  1. ``config.ANTI_LESSONS_CONTROL_ENABLED`` is true (server flag, default off),
  2. the specific request explicitly passes ``anti_lesson_control_requested=True``.

If either key is missing, the prompt is byte-identical to Phase 11.7b. These
tests pin the two-key gate, the byte-identical disabled path, the bounded/labeled
block, that active retrieval is unchanged and anti-lessons stay excluded from it,
the per-run-only UI/route wiring, and the absence of forbidden sinks.
"""
import ast
import inspect
from pathlib import Path

import pytest

import config as config_module
from core import anti_lessons, control_engine, lesson_retrieval, lesson_store
from core.anti_lesson_control_injection import (
    ANTI_LESSON_CONTROL_HEADER,
    build_anti_lesson_control_block,
    summarize_anti_lesson_control_injection,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = PROJECT_ROOT / "core"
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
APP_PY = PROJECT_ROOT / "web" / "app.py"
CONFIG_PY = PROJECT_ROOT / "config.py"


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    fake = lambda repo_path=None: tmp_path / ".agent"
    monkeypatch.setattr(lesson_store, "get_agent_dir", fake)
    monkeypatch.setattr(config_module, "get_agent_dir", fake)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    monkeypatch.setattr(config_module, "ANTI_LESSONS_ENABLED", False, raising=False)
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", False, raising=False)
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", False, raising=False)
    return tmp_path


# ── builders ─────────────────────────────────────────────────────────────────


def _anti(**overrides):
    base = dict(
        title="swallow exceptions to make tests pass",
        tempting_wrong_pattern="Wrap the call in try/except: pass to silence the failure.",
        why_wrong="It hides the real bug and the next run regresses silently.",
        safer_alternative="Fix the root cause or assert the expected error explicitly.",
    )
    base.update(overrides)
    return anti_lessons.create_manual_anti_lesson(**base)


def _normal_candidate(**overrides):
    base = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": ["src/app.py"],
        "diff_stats": {"added": 4, "removed": 2},
    }
    base.update(overrides)
    return base


def _save_active_lesson(*, title, summary="swallow exceptions advisory hint"):
    rec = lesson_store.save_candidate_lesson(
        _normal_candidate(), source="manual", title=title, summary=summary
    )
    return lesson_store.promote_lesson(rec["id"])


def _control_result():
    return {
        "top_hypothesis": {
            "symbol": "foo",
            "likely_issue": "off-by-one",
            "confidence": 0.8,
            "recommended_action": "fix",
            "language": "python",
            "reasons": ["test reason"],
        },
        "patch_intent": {
            "language": "python",
            "source_snippet": "def foo():\n    pass\n",
            "file": "src/foo.py",
            "target_symbol": "foo",
            "target_node_kind": "function",
        },
        "preflight_validation": {},
        "related_snippets": [],
        "scout": {"request_type": "bug_fix"},
        "phantom_limb": {"findings": []},
        "patch_style": "safe_minimal",
        "code_dna_prompt": "REPO STYLE: idiomatic python",
    }


def _prompt(repo, **kw):
    return control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(repo), **kw
    )


def _snapshot(tmp_path):
    root = tmp_path / ".agent" / "lessons"
    out = {}
    if root.is_dir():
        for p in sorted(root.rglob("*.json")):
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


# ── 1. config flag default off ───────────────────────────────────────────────


def test_config_flag_exists_and_defaults_off():
    assert hasattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED")
    assert isinstance(config_module.ANTI_LESSONS_CONTROL_ENABLED, bool)
    src = CONFIG_PY.read_text(encoding="utf-8")
    # Default literal must be "false" so an unset env yields False.
    assert 'os.getenv("ANTI_LESSONS_CONTROL_ENABLED", "false")' in src


# ── 2. two-key gate at the helper boundary ───────────────────────────────────


def test_block_requires_both_keys(lessons_repo, monkeypatch):
    _anti(title="swallow exceptions anti")

    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", False)
    assert build_anti_lesson_control_block(
        str(lessons_repo), "swallow exceptions", requested=True
    ) == ""

    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    assert build_anti_lesson_control_block(
        str(lessons_repo), "swallow exceptions", requested=False
    ) == ""

    assert build_anti_lesson_control_block(
        str(lessons_repo), "swallow exceptions", requested=True
    ) != ""


# ── 3. disabled prompt is byte-identical to 11.7b ────────────────────────────


def test_disabled_paths_are_byte_identical(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    _save_active_lesson(title="active advisory about swallow exceptions")
    _anti(title="swallow exceptions anti A")
    _anti(title="swallow exceptions anti B")

    # Baseline: the pre-11.7c call shape (no new args at all).
    baseline = _prompt(lessons_repo)

    # flag false + request false
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", False)
    assert _prompt(lessons_repo, anti_lesson_control_requested=False) == baseline
    # flag false + request true
    assert _prompt(lessons_repo, anti_lesson_control_requested=True) == baseline
    # flag true + request false
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    assert _prompt(lessons_repo, anti_lesson_control_requested=False) == baseline


def test_request_only_without_config_does_nothing(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", False)
    _anti(title="swallow exceptions anti")
    prompt = _prompt(lessons_repo, anti_lesson_control_requested=True)
    assert ANTI_LESSON_CONTROL_HEADER not in prompt


def test_config_only_without_request_does_nothing(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    _anti(title="swallow exceptions anti")
    prompt = _prompt(lessons_repo, anti_lesson_control_requested=False)
    assert ANTI_LESSON_CONTROL_HEADER not in prompt


# ── 4. config + request injects a clearly labeled block ──────────────────────


def test_two_keys_inject_labeled_block(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    _anti(title="swallow exceptions anti")
    prompt = _prompt(lessons_repo, anti_lesson_control_requested=True)
    assert ANTI_LESSON_CONTROL_HEADER in prompt
    assert "EXPERIMENTAL" in prompt
    assert "DO NOT REPEAT" in prompt


def test_injected_block_includes_tempting_why_safer(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    _anti(
        title="swallow exceptions anti",
        tempting_wrong_pattern="TEMPTING_WRONG_MARKER wrap in try/except pass",
        why_wrong="WHY_WRONG_MARKER it hides the real bug",
        safer_alternative="SAFER_MARKER assert the expected error explicitly",
    )
    prompt = _prompt(lessons_repo, anti_lesson_control_requested=True)
    assert "TEMPTING_WRONG_MARKER" in prompt
    assert "WHY_WRONG_MARKER" in prompt
    assert "SAFER_MARKER" in prompt


def test_injected_block_carries_evidence_refs(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    _anti(title="swallow exceptions anti", evidence_refs=["reports/run_42.json"])
    prompt = _prompt(lessons_repo, anti_lesson_control_requested=True)
    assert "reports/run_42.json" in prompt


# ── 5. max anti-lessons bounded ──────────────────────────────────────────────


def test_injected_block_bounded(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    for i in range(8):
        _anti(title=f"swallow exceptions anti {i}")

    # Default cap is 3.
    block = build_anti_lesson_control_block(
        str(lessons_repo), "swallow exceptions", requested=True
    )
    assert 1 <= block.count("tempting_wrong_pattern:") <= 3

    # A higher explicit request is still hard-capped (max 5).
    block_big = build_anti_lesson_control_block(
        str(lessons_repo), "swallow exceptions", requested=True, max_items=50
    )
    assert block_big.count("tempting_wrong_pattern:") <= 5


# ── 6. normal active lessons unaffected; anti stays out of active retrieval ───


def test_active_lessons_still_present_alongside_injection(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    _save_active_lesson(title="ACTIVE_ADVISORY about swallow exceptions")
    _anti(title="swallow exceptions anti")
    prompt = _prompt(lessons_repo, anti_lesson_control_requested=True)
    assert "[ACTIVE LESSONS" in prompt
    assert "ACTIVE_ADVISORY" in prompt
    assert ANTI_LESSON_CONTROL_HEADER in prompt


def test_anti_lessons_excluded_from_active_retrieval_after_injection(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    rec = _anti(title="swallow exceptions anti")
    lesson_store.promote_lesson(rec["id"])  # worst case: explicitly promoted
    _prompt(lessons_repo, anti_lesson_control_requested=True)
    assert rec["id"] not in {r["id"] for r in lesson_retrieval.list_active_lessons()}
    found = lesson_retrieval.find_active_lessons(query="swallow exceptions")
    assert rec["id"] not in {r["id"] for r in found}


# ── 7. read-only: prompt building never mutates the store ─────────────────────


def test_prompt_building_does_not_mutate_lesson_files(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    _anti(title="swallow exceptions anti A")
    _anti(title="swallow exceptions anti B")
    before = _snapshot(lessons_repo)
    _prompt(lessons_repo, anti_lesson_control_requested=True)
    after = _snapshot(lessons_repo)
    assert before == after


# ── 8. new optional parameter, old callers unaffected ────────────────────────


def test_build_control_prompt_old_signature_still_works(lessons_repo):
    prompt = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    assert "[USER]" in prompt
    sig = inspect.signature(control_engine.build_control_prompt)
    param = sig.parameters.get("anti_lesson_control_requested")
    assert param is not None
    assert param.default is False
    assert param.kind == inspect.Parameter.KEYWORD_ONLY


# ── 9. per-run metadata only ──────────────────────────────────────────────────


def test_summary_records_per_run_metadata_only(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", True)
    _anti(title="swallow exceptions anti")
    meta = summarize_anti_lesson_control_injection(
        str(lessons_repo), "swallow exceptions", requested=True
    )
    assert set(meta.keys()) == {
        "requested",
        "enabled_by_config",
        "injected",
        "selected_count",
    }
    assert meta["requested"] is True
    assert meta["enabled_by_config"] is True
    assert meta["injected"] is True
    assert meta["selected_count"] >= 1


def test_summary_not_injected_when_disabled(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "ANTI_LESSONS_CONTROL_ENABLED", False)
    _anti(title="swallow exceptions anti")
    meta = summarize_anti_lesson_control_injection(
        str(lessons_repo), "swallow exceptions", requested=True
    )
    assert meta["enabled_by_config"] is False
    assert meta["injected"] is False


# ── 10. UI: per-run checkbox only, no global/persistent toggle ────────────────

_TMPL = TEMPLATE.read_text(encoding="utf-8")


def test_ui_has_per_run_anti_lesson_checkbox():
    assert 'id="antiLessonControlForRun"' in _TMPL
    assert "Include anti-lesson warning block for this run" in _TMPL


def test_ui_shows_per_run_requirement_warning():
    assert (
        "Requires server flag ANTI_LESSONS_CONTROL_ENABLED=true. "
        "Does not save a global setting." in _TMPL
    )


def test_ui_sends_per_request_field():
    assert "anti_lesson_control_requested" in _TMPL


def test_ui_anti_lesson_control_is_per_run_only():
    start = _TMPL.find("<!-- anti-lesson-control-per-run -->")
    end = _TMPL.find("<!-- /anti-lesson-control-per-run -->", start)
    assert start != -1 and end != -1, "per-run anti-lesson control markers not found"
    region = _TMPL[start:end].lower()
    for bad in (
        "always use anti-lessons",
        "enable anti-lessons globally",
        "auto-enable",
        "persistent setting",
        "save global",
    ):
        assert bad not in region
    # It must be a checkbox (per-run), not a saved server toggle.
    assert 'type="checkbox"' in _TMPL[start:end]


# ── 11. route wires the per-request flag only ────────────────────────────────

_APP = APP_PY.read_text(encoding="utf-8")


def test_route_reads_per_request_flag():
    assert 'request.form.get("anti_lesson_control_requested"' in _APP


def test_route_passes_flag_to_build_control_prompt():
    assert "anti_lesson_control_requested=" in _APP


def test_route_does_not_persist_global_anti_lesson_control_setting():
    # The route never flips the server flag or writes it anywhere.
    assert 'os.environ["ANTI_LESSONS_CONTROL_ENABLED"]' not in _APP
    assert "ANTI_LESSONS_CONTROL_ENABLED =" not in _APP


# ── 12. forbidden sinks absent in the new module ─────────────────────────────

PHASE_MODULES = ("anti_lesson_control_injection.py",)

FORBIDDEN_IMPORT_ROOTS = {
    "agents", "benchmarks", "database", "docker", "google",
    "openai", "anthropic", "requests", "httpx", "subprocess", "socket",
}
FORBIDDEN_IMPORTS = {
    "core.sleeping_consultant", "core.dream_trials", "core.dream_artifacts",
    "core.dream_references", "core.proposal_runner", "core.run_lifecycle",
    "core.control_engine", "core.prompter", "core.lesson_retrieval",
    "core.mutation_oracle",
    "patching", "patching.patch_plan_executor",
}
FORBIDDEN_CALLS = {
    "run_patch_plan_with_artifacts", "apply_patch_plan", "apply_patch",
    "run_benchmarks", "run_benchmark",
    "run_gemini", "run_gemini_request", "run_ollama", "run_deepseek",
    "ChatCompletion", "generate_content",
    "build_control_prompt", "build_prompt", "build_deepseek_review",
    "Popen", "check_call", "check_output", "system",
    "promote_lesson", "block_lesson", "archive_lesson", "create_merge",
    "save_candidate_lesson", "save_raw_lesson_record", "patch_lesson_fields",
    "create_manual_anti_lesson",
}


def _imported_modules(tree):
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def test_injection_module_has_no_forbidden_sinks():
    for fname in PHASE_MODULES:
        tree = ast.parse((CORE_DIR / fname).read_text(encoding="utf-8"))
        imports = _imported_modules(tree)
        calls = _called_names(tree)
        roots = {name.split(".", 1)[0] for name in imports}
        assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), (fname, roots & FORBIDDEN_IMPORT_ROOTS)
        assert imports.isdisjoint(FORBIDDEN_IMPORTS), (fname, imports & FORBIDDEN_IMPORTS)
        assert calls.isdisjoint(FORBIDDEN_CALLS), (fname, calls & FORBIDDEN_CALLS)
