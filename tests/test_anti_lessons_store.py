"""Phase 11.1 — Anti-Lesson Data Model + Store Safety.

Anti-lessons are stored as a first-class lesson ``kind`` but stay INERT:

  * never auto-activated (even with ``LESSON_AUTO_ACTIVE`` on),
  * ``active_knowledge_allowed`` is always false,
  * never retrieval-eligible in the current live path (gated by the reserved,
    default-off ``ANTI_LESSONS_ENABLED`` placeholder flag), and
  * never mergeable with a normal lesson (hard block).

These tests pin those guarantees and prove the forbidden sinks (model/API,
patch, benchmark, Dream, subprocess, Docker) are absent from the modules this
phase touches, and that the CONTROL prompt is unaffected.
"""
import ast
import json
from pathlib import Path

import pytest

import config as config_module
from core import control_engine, lesson_merge, lesson_retrieval, lesson_store


THIS_FILE = Path(__file__).resolve()
CORE_DIR = THIS_FILE.parents[1] / "core"


def _candidate(**overrides):
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


def _control_result():
    """Minimal control_result that hits the normal bug-fix prompt branch.

    Mirrors tests/test_control_prompt_lessons.py so the CONTROL-prompt
    behavioral test exercises the same code path.
    """
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


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    """Redirect lesson storage to tmp_path/.agent and reset all live flags.

    Patches both ``lesson_store.get_agent_dir`` (storage internals) and
    ``config.get_agent_dir`` (lesson_retrieval scope resolution), mirroring
    tests/test_lesson_retrieval.py. Forces every gating flag to its inert
    default so each test starts from the shipped (off) configuration.
    """
    fake = lambda repo_path=None: tmp_path / ".agent"
    monkeypatch.setattr(lesson_store, "get_agent_dir", fake)
    monkeypatch.setattr(config_module, "get_agent_dir", fake)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    monkeypatch.setattr(config_module, "ANTI_LESSONS_ENABLED", False, raising=False)
    return tmp_path


def _save_lesson(lessons_repo, **kwargs):
    kwargs.setdefault("source", "manual")
    return lesson_store.save_candidate_lesson(_candidate(), **kwargs)


def _save_anti(lessons_repo, **kwargs):
    kwargs.setdefault("source", "manual")
    return lesson_store.save_candidate_lesson(_candidate(), kind="anti_lesson", **kwargs)


def _candidate_bucket(lessons_repo: Path, lesson_id: str) -> Path:
    return lessons_repo / ".agent" / "lessons" / "candidate" / f"{lesson_id}.json"


# ── 1. kind helpers ──────────────────────────────────────────────────────────


def test_normalize_lesson_kind_defaults_missing_to_lesson():
    assert lesson_store.normalize_lesson_kind(None) == "lesson"
    assert lesson_store.normalize_lesson_kind("") == "lesson"
    assert lesson_store.normalize_lesson_kind("   ") == "lesson"


def test_normalize_lesson_kind_passes_known_kinds():
    assert lesson_store.normalize_lesson_kind("lesson") == "lesson"
    assert lesson_store.normalize_lesson_kind("anti_lesson") == "anti_lesson"


def test_normalize_lesson_kind_rejects_unknown():
    with pytest.raises(ValueError):
        lesson_store.normalize_lesson_kind("bogus_kind")


def test_validate_lesson_kind_accepts_known_rejects_unknown():
    assert lesson_store.validate_lesson_kind("lesson") == "lesson"
    assert lesson_store.validate_lesson_kind("anti_lesson") == "anti_lesson"
    with pytest.raises(ValueError):
        lesson_store.validate_lesson_kind("bogus_kind")
    # validate does NOT supply a default — None is rejected.
    with pytest.raises(ValueError):
        lesson_store.validate_lesson_kind(None)


def test_is_anti_lesson_true_only_for_anti_kind():
    assert lesson_store.is_anti_lesson({"kind": "anti_lesson"}) is True
    assert lesson_store.is_anti_lesson({"kind": "lesson"}) is False
    assert lesson_store.is_anti_lesson({}) is False           # missing → not anti
    assert lesson_store.is_anti_lesson({"kind": "weird"}) is False
    assert lesson_store.is_anti_lesson(None) is False         # lenient, no raise
    assert lesson_store.is_anti_lesson("nope") is False


# ── 2. kind defaulting / validation on the record ────────────────────────────


def test_missing_kind_defaults_to_lesson_on_save(lessons_repo):
    saved = _save_lesson(lessons_repo)
    assert saved["kind"] == "lesson"


def test_legacy_record_without_kind_field_reads_back_as_lesson(lessons_repo):
    """A pre-kind record on disk (no ``kind`` field) normalizes to 'lesson'."""
    saved = _save_lesson(lessons_repo)
    path = _candidate_bucket(lessons_repo, saved["id"])
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["kind"]
    path.write_text(json.dumps(data), encoding="utf-8")

    reloaded = lesson_store.get_lesson_by_id(saved["id"])
    assert reloaded["kind"] == "lesson"


def test_save_with_invalid_kind_is_rejected(lessons_repo):
    with pytest.raises(ValueError):
        lesson_store.save_candidate_lesson(_candidate(), kind="not_a_kind")


# ── 3. anti-lesson save / create behavior ────────────────────────────────────


def test_anti_lesson_saved_as_candidate(lessons_repo):
    saved = _save_anti(lessons_repo)
    assert saved["kind"] == "anti_lesson"
    assert saved["status"] == "candidate"
    assert saved["active_knowledge_allowed"] is False
    assert _candidate_bucket(lessons_repo, saved["id"]).is_file()


def test_anti_lesson_active_knowledge_allowed_forced_false(lessons_repo):
    saved = _save_anti(lessons_repo)
    assert saved["active_knowledge_allowed"] is False


def test_anti_lesson_not_auto_activated_even_when_flag_on(lessons_repo, monkeypatch):
    """With LESSON_AUTO_ACTIVE on, an auto-approved NORMAL lesson lands active,
    but the same auto-approved candidate saved as an anti-lesson stays a
    candidate and is never marked active knowledge."""
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)

    normal = _save_lesson(lessons_repo)
    assert normal["status"] == "active"  # sanity: the flag does promote normals

    anti = _save_anti(lessons_repo)
    assert anti["kind"] == "anti_lesson"
    assert anti["status"] == "candidate"
    assert anti["active_knowledge_allowed"] is False
    # The quality guard still ran and its verdict is preserved...
    assert anti["evaluation"]["promotion"] == "auto_approved"
    # ...but the auto-approval did NOT auto-activate the anti-lesson.


def test_anti_lesson_blocked_verdict_still_routes_to_blocked(lessons_repo):
    """Anti-lessons may exist as blocked: a forbidden-file candidate still
    routes to the blocked bucket (it just never auto-activates)."""
    anti = lesson_store.save_candidate_lesson(
        _candidate(touched_forbidden_files=["secrets.env"]),
        kind="anti_lesson",
        source="manual",
    )
    assert anti["kind"] == "anti_lesson"
    assert anti["status"] == "blocked"
    assert anti["active_knowledge_allowed"] is False


def test_anti_lesson_preserves_source_and_evidence(lessons_repo):
    cand = _candidate(language="python", evidence="tempting-but-wrong pattern X")
    saved = lesson_store.save_candidate_lesson(
        cand,
        kind="anti_lesson",
        source="dream",
        source_report="dream_report_20260604_120000.json",
        case_name="python_tempting_antipattern",
        title="Do NOT use a mutable default argument",
        summary="Avoid the tempting mutable-default-arg pattern.",
    )

    assert saved["source"] == "dream"
    assert saved["source_report"] == "dream_report_20260604_120000.json"
    assert saved["candidate"] == cand          # candidate/evidence preserved verbatim
    assert saved["candidate"]["evidence"] == "tempting-but-wrong pattern X"
    assert isinstance(saved["evaluation"], dict)  # evaluation preserved

    reloaded = lesson_store.get_lesson_by_id(saved["id"])
    assert reloaded["kind"] == "anti_lesson"
    assert reloaded["candidate"] == cand
    assert reloaded["source"] == "dream"
    assert reloaded["source_report"] == "dream_report_20260604_120000.json"


# ── 4. retrieval guard ───────────────────────────────────────────────────────


def test_active_anti_lesson_not_retrieval_eligible(lessons_repo):
    """Even an EXPLICITLY-promoted (status=active) anti-lesson must never
    surface in live active retrieval while ANTI_LESSONS_ENABLED is off.

    A normal active lesson with the same matchable content IS surfaced, proving
    the test is not vacuously passing.
    """
    normal = _save_lesson(lessons_repo, title="NORMAL active lesson", summary="off-by-one")
    lesson_store.promote_lesson(normal["id"])

    anti = _save_anti(lessons_repo, title="Tempting antipattern", summary="off-by-one")
    promoted = lesson_store.promote_lesson(anti["id"])
    # Explicit promotion is a human action (not auto-activation): it does move
    # the file into the active bucket. This is the worst case for the guard.
    assert promoted["status"] == "active"
    assert promoted["kind"] == "anti_lesson"

    active = lesson_retrieval.list_active_lessons()
    active_ids = {r["id"] for r in active}
    assert normal["id"] in active_ids                 # normal active → eligible
    assert anti["id"] not in active_ids               # anti active → excluded
    assert all(not lesson_store.is_anti_lesson(r) for r in active)

    found = lesson_retrieval.find_active_lessons(query="off-by-one")
    found_ids = {r["id"] for r in found}
    assert normal["id"] in found_ids
    assert anti["id"] not in found_ids


def test_anti_lessons_enabled_flag_is_the_retrieval_gate(lessons_repo, monkeypatch):
    """The exclusion is gated by the reserved ANTI_LESSONS_ENABLED placeholder,
    fail-closed. Phase 11.1 ships it OFF (active anti-lessons excluded); forcing
    it on (a future Phase 11 slice) would surface them — proving the guard reads
    the flag and is not dead code. The flag is not wired into CONTROL/UI."""
    anti = _save_anti(lessons_repo, title="Tempting antipattern")
    lesson_store.promote_lesson(anti["id"])

    # Shipped default (off): excluded.
    assert anti["id"] not in {r["id"] for r in lesson_retrieval.list_active_lessons()}

    # Forced on: the guard lets it through.
    monkeypatch.setattr(config_module, "ANTI_LESSONS_ENABLED", True, raising=False)
    assert anti["id"] in {r["id"] for r in lesson_retrieval.list_active_lessons()}


def test_active_anti_lesson_absent_from_control_prompt(lessons_repo, monkeypatch):
    """With retrieval enabled, an active anti-lesson must NOT appear in the
    CONTROL prompt, while a normal active lesson with the same query match does.
    Proves anti-lessons stay out of the live CONTROL path with no CONTROL
    changes required."""
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)

    normal = lesson_store.save_candidate_lesson(
        _candidate(),
        source="manual",
        case_name="python_off_by_one_pagination",
        title="NORMAL_LESSON_SHOULD_APPEAR",
        summary="Fix the off-by-one in pagination.",
    )
    lesson_store.promote_lesson(normal["id"])

    anti = lesson_store.save_candidate_lesson(
        _candidate(),
        kind="anti_lesson",
        source="manual",
        case_name="python_off_by_one_pagination",
        title="ANTI_LESSON_SHOULD_NOT_LEAK",
        summary="Do not apply this tempting off-by-one shortcut.",
    )
    lesson_store.promote_lesson(anti["id"])

    prompt = control_engine.build_control_prompt(
        _control_result(), "off-by-one", repo_path=str(lessons_repo)
    )

    assert "[ACTIVE LESSONS" in prompt                  # retrieval path is live
    assert "NORMAL_LESSON_SHOULD_APPEAR" in prompt      # normal lesson surfaces
    assert "ANTI_LESSON_SHOULD_NOT_LEAK" not in prompt  # anti-lesson excluded


# ── 5. merge safety ──────────────────────────────────────────────────────────


def test_merge_normal_plus_anti_is_blocked(lessons_repo):
    normal = _save_lesson(lessons_repo)
    anti = _save_anti(lessons_repo)
    with pytest.raises(ValueError, match="anti-lesson"):
        lesson_merge.create_merge(
            [normal["id"], anti["id"]], title="M", summary="", tags=[]
        )


def test_merge_normal_plus_anti_blocked_even_with_confirm(lessons_repo):
    """The normal+anti block is hard: confirm_mix_kinds cannot override it."""
    normal = _save_lesson(lessons_repo)
    anti = _save_anti(lessons_repo)
    with pytest.raises(ValueError, match="anti-lesson"):
        lesson_merge.create_merge(
            [normal["id"], anti["id"]],
            title="M",
            summary="",
            tags=[],
            confirm_mix_kinds=True,
        )


def test_merge_anti_plus_anti_creates_candidate_anti(lessons_repo):
    a = _save_anti(lessons_repo, title="Anti A")
    b = _save_anti(lessons_repo, title="Anti B")

    new, superseded = lesson_merge.create_merge(
        [a["id"], b["id"]], title="Merged anti", summary="", tags=[]
    )

    assert new["kind"] == "anti_lesson"
    assert new["status"] == "candidate"
    assert new["active_knowledge_allowed"] is False
    assert set(superseded) == {a["id"], b["id"]}

    reloaded = lesson_store.get_lesson_by_id(new["id"])
    assert reloaded["kind"] == "anti_lesson"
    assert reloaded["status"] == "candidate"
    assert reloaded["active_knowledge_allowed"] is False


def test_merged_anti_lesson_cannot_be_auto_active(lessons_repo, monkeypatch):
    """Even with LESSON_AUTO_ACTIVE on, an anti+anti merge stays a candidate."""
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)
    a = _save_anti(lessons_repo)
    b = _save_anti(lessons_repo)
    new, _ = lesson_merge.create_merge(
        [a["id"], b["id"]], title="M", summary="", tags=[]
    )
    assert new["status"] == "candidate"
    assert new["active_knowledge_allowed"] is False


# ── 6. archive / supersede compatibility ─────────────────────────────────────


def test_anti_lesson_archive_is_soft_and_preserves_kind(lessons_repo):
    anti = _save_anti(lessons_repo)
    archived = lesson_merge.archive_lesson(anti["id"])
    assert archived["archived"] is True
    assert archived["kind"] == "anti_lesson"

    # No hard delete: the record is still readable and still an anti-lesson.
    reloaded = lesson_store.get_lesson_by_id(anti["id"])
    assert reloaded["archived"] is True
    assert reloaded["kind"] == "anti_lesson"
    assert _candidate_bucket(lessons_repo, anti["id"]).is_file()


def test_anti_lesson_supersede_metadata_preserved(lessons_repo):
    anti = _save_anti(lessons_repo)
    lesson_store.patch_lesson_fields(
        anti["id"], {"superseded_by": "20240101_000000_000001"}
    )
    reloaded = lesson_store.get_lesson_by_id(anti["id"])
    assert reloaded["superseded_by"] == "20240101_000000_000001"
    assert reloaded["kind"] == "anti_lesson"  # kind survives a field patch


# ── 7. forbidden sinks absent in the phase modules ───────────────────────────

PHASE_MODULES = ("lesson_store.py", "lesson_merge.py", "lesson_retrieval.py")

FORBIDDEN_IMPORT_ROOTS = {
    "agents", "benchmarks", "database", "docker", "google",
    "openai", "anthropic", "requests", "httpx", "subprocess", "socket",
}
FORBIDDEN_IMPORTS = {
    "core.sleeping_consultant", "core.dream_trials", "core.dream_artifacts",
    "core.dream_references", "core.proposal_runner", "core.run_lifecycle",
    "core.control_engine", "core.prompter",
    "patching", "patching.patch_plan_executor",
}
FORBIDDEN_CALLS = {
    # patch execution
    "run_patch_plan_with_artifacts", "apply_patch_plan", "apply_patch",
    # benchmark execution
    "run_benchmarks", "run_benchmark",
    # model / API
    "run_gemini", "run_gemini_request_2", "run_ollama", "run_deepseek",
    "ChatCompletion", "generate_content",
    # CONTROL / prompt building (proves no CONTROL coupling)
    "build_control_prompt", "build_prompt", "build_deepseek_review",
    # subprocess
    "Popen", "check_call", "check_output", "system",
}


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def test_phase_modules_have_no_forbidden_sinks():
    for fname in PHASE_MODULES:
        tree = ast.parse((CORE_DIR / fname).read_text(encoding="utf-8"))
        imports = _imported_modules(tree)
        calls = _called_names(tree)
        roots = {name.split(".", 1)[0] for name in imports}

        assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), (
            fname, roots & FORBIDDEN_IMPORT_ROOTS,
        )
        assert imports.isdisjoint(FORBIDDEN_IMPORTS), (
            fname, imports & FORBIDDEN_IMPORTS,
        )
        assert calls.isdisjoint(FORBIDDEN_CALLS), (
            fname, calls & FORBIDDEN_CALLS,
        )
