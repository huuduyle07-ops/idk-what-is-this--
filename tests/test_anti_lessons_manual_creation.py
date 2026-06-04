"""Phase 11.2 — Manual Anti-Lesson Creation Route/UI.

Operator-driven manual creation of candidate anti-lessons via a core helper
(`core.anti_lessons.create_manual_anti_lesson`) and a POST route
(`/lessons/anti/create`). Manual anti-lessons reuse the Phase 11.1 storage path
(`kind="anti_lesson"`) and stay INERT:

  * status defaults to candidate, `active_knowledge_allowed=False`;
  * no auto-promotion, no active retrieval, no CONTROL prompt change;
  * required fields enforced, empty/meaningless rejected;
  * evidence file refs guarded against path traversal.

These tests also prove the new core module has no forbidden sinks and the UI
ships the creation form plus the inert-warning copy.
"""
import ast
from pathlib import Path

import pytest

import config as config_module
from core import anti_lessons, control_engine, lesson_retrieval, lesson_store


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = PROJECT_ROOT / "core"
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    """Redirect lesson storage to tmp_path/.agent and reset live flags."""
    fake = lambda repo_path=None: tmp_path / ".agent"
    monkeypatch.setattr(lesson_store, "get_agent_dir", fake)
    monkeypatch.setattr(config_module, "get_agent_dir", fake)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    monkeypatch.setattr(config_module, "ANTI_LESSONS_ENABLED", False, raising=False)
    return tmp_path


def _valid_kwargs(**overrides):
    base = dict(
        title="Do NOT swallow exceptions to make tests pass",
        tempting_wrong_pattern="Wrapping the call in try/except: pass to silence the failure.",
        why_wrong="It hides the real bug and the next run regresses silently.",
        safer_alternative="Fix the root cause or assert the expected error explicitly.",
    )
    base.update(overrides)
    return base


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


def _client():
    from web import app as web_app
    return web_app.app.test_client()


# ── core helper: create_manual_anti_lesson ───────────────────────────────────


def test_helper_creates_candidate_anti_lesson(lessons_repo):
    rec = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    assert rec["kind"] == "anti_lesson"
    assert rec["status"] == "candidate"
    assert rec["active_knowledge_allowed"] is False


def test_helper_preserves_evidence_and_source(lessons_repo):
    rec = anti_lessons.create_manual_anti_lesson(
        **_valid_kwargs(),
        summary="Custom summary",
        evidence_refs=["reports/run_42.json", "notes.md"],
        related_lesson_ids=["20260604_120000_000000"],
        tags=["python", "testing"],
        source="manual_ui",
        source_report="ui_session_20260604.json",
    )
    cand = rec["candidate"]
    assert cand["tempting_wrong_pattern"].startswith("Wrapping the call")
    assert cand["why_wrong"].startswith("It hides")
    assert cand["safer_alternative"].startswith("Fix the root cause")
    assert cand["evidence_refs"] == ["reports/run_42.json", "notes.md"]
    assert cand["related_lesson_ids"] == ["20260604_120000_000000"]
    assert rec["source"] == "manual_ui"
    assert rec["source_report"] == "ui_session_20260604.json"
    assert rec["summary"] == "Custom summary"

    # Survives a round-trip through the store.
    reloaded = lesson_store.get_lesson_by_id(rec["id"])
    assert reloaded["candidate"]["evidence_refs"] == ["reports/run_42.json", "notes.md"]
    assert reloaded["kind"] == "anti_lesson"


@pytest.mark.parametrize("missing", ["title", "tempting_wrong_pattern", "why_wrong", "safer_alternative"])
def test_helper_requires_core_fields(lessons_repo, missing):
    kwargs = _valid_kwargs()
    kwargs[missing] = "   "  # blank/whitespace must be rejected
    with pytest.raises(ValueError):
        anti_lessons.create_manual_anti_lesson(**kwargs)


def test_helper_rejects_path_traversal_evidence(lessons_repo):
    for bad in ("../../etc/passwd", "..\\..\\secret", "/etc/passwd", "C:\\Windows\\x"):
        with pytest.raises(ValueError):
            anti_lessons.create_manual_anti_lesson(
                **_valid_kwargs(), evidence_refs=[bad]
            )


def test_helper_never_auto_activates_even_with_flag(lessons_repo, monkeypatch):
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)
    rec = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    assert rec["status"] == "candidate"
    assert rec["active_knowledge_allowed"] is False


def test_helper_created_anti_lesson_not_in_active_retrieval(lessons_repo):
    rec = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    active_ids = {r["id"] for r in lesson_retrieval.list_active_lessons()}
    assert rec["id"] not in active_ids
    # Even after an explicit human promotion it stays out of live retrieval.
    lesson_store.promote_lesson(rec["id"])
    active_ids2 = {r["id"] for r in lesson_retrieval.list_active_lessons()}
    assert rec["id"] not in active_ids2


# ── route: POST /lessons/anti/create ─────────────────────────────────────────


def test_route_creates_candidate_anti_lesson(lessons_repo):
    resp = _client().post("/lessons/anti/create", json=_valid_kwargs())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["lesson"]["kind"] == "anti_lesson"
    assert body["lesson"]["status"] == "candidate"
    assert body["lesson"]["active_knowledge_allowed"] is False


def test_route_enforces_required_fields(lessons_repo):
    payload = _valid_kwargs()
    del payload["why_wrong"]
    resp = _client().post("/lessons/anti/create", json=payload)
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_route_preserves_evidence_and_source(lessons_repo):
    resp = _client().post(
        "/lessons/anti/create",
        json={
            **_valid_kwargs(),
            "evidence_refs": ["reports/run_42.json"],
            "related_lesson_ids": ["20260604_120000_000000"],
            "source": "manual_ui",
            "source_report": "ui_session.json",
        },
    )
    assert resp.status_code == 200
    lesson = resp.get_json()["lesson"]
    assert lesson["candidate"]["evidence_refs"] == ["reports/run_42.json"]
    assert lesson["candidate"]["related_lesson_ids"] == ["20260604_120000_000000"]
    assert lesson["source"] == "manual_ui"
    assert lesson["source_report"] == "ui_session.json"


def test_route_cannot_create_active_anti_lesson(lessons_repo):
    """Even if the payload tries to force activation, the result is candidate."""
    resp = _client().post(
        "/lessons/anti/create",
        json={
            **_valid_kwargs(),
            "status": "active",
            "active_knowledge_allowed": True,
            "kind": "lesson",
        },
    )
    assert resp.status_code == 200
    lesson = resp.get_json()["lesson"]
    assert lesson["status"] == "candidate"
    assert lesson["active_knowledge_allowed"] is False
    assert lesson["kind"] == "anti_lesson"
    # Nothing landed in the active bucket.
    active_dir = lessons_repo / ".agent" / "lessons" / "active"
    assert not any(active_dir.glob("*.json"))


def test_route_rejects_path_traversal_evidence(lessons_repo):
    resp = _client().post(
        "/lessons/anti/create",
        json={**_valid_kwargs(), "evidence_refs": ["../../etc/passwd"]},
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_route_created_anti_lesson_absent_from_control_prompt(lessons_repo, monkeypatch):
    """A manually created (candidate) anti-lesson must not surface in CONTROL,
    even with retrieval enabled."""
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    resp = _client().post(
        "/lessons/anti/create",
        json=_valid_kwargs(title="ANTI_LESSON_SHOULD_NOT_LEAK"),
    )
    assert resp.status_code == 200

    prompt = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    assert "ANTI_LESSON_SHOULD_NOT_LEAK" not in prompt


# ── UI contract (parse index.html as text) ───────────────────────────────────

_TMPL = TEMPLATE.read_text(encoding="utf-8")


def test_ui_has_anti_lesson_creation_form():
    assert 'id="antiLessonCreatePanel"' in _TMPL
    assert 'id="antiLessonTitle"' in _TMPL
    assert 'id="antiLessonTempting"' in _TMPL
    assert 'id="antiLessonWhyWrong"' in _TMPL
    assert 'id="antiLessonSaferAlt"' in _TMPL
    assert 'id="antiLessonCreateBtn"' in _TMPL


def test_ui_has_inert_warning_copy():
    assert (
        "Anti-lessons are stored as candidate memory only and are not used by CONTROL yet."
        in _TMPL
    )


def test_ui_js_posts_to_anti_create_route():
    assert "function createAntiLesson(" in _TMPL
    assert "/lessons/anti/create" in _TMPL


def test_ui_anti_form_does_not_send_active_state():
    # The form must never push status/active_knowledge_allowed=true to the route.
    assert "active_knowledge_allowed: true" not in _TMPL
    assert 'status: "active"' not in _TMPL


# ── forbidden sinks absent in the new core module ────────────────────────────

FORBIDDEN_IMPORT_ROOTS = {
    "agents", "benchmarks", "database", "docker", "google",
    "openai", "anthropic", "requests", "httpx", "subprocess", "socket",
}
FORBIDDEN_IMPORTS = {
    "core.sleeping_consultant", "core.dream_trials", "core.dream_artifacts",
    "core.dream_references", "core.proposal_runner", "core.run_lifecycle",
    "core.control_engine", "core.prompter", "core.lesson_retrieval",
    "patching", "patching.patch_plan_executor",
}
FORBIDDEN_CALLS = {
    "run_patch_plan_with_artifacts", "apply_patch_plan", "apply_patch",
    "run_benchmarks", "run_benchmark",
    "run_gemini", "run_gemini_request_2", "run_ollama", "run_deepseek",
    "ChatCompletion", "generate_content",
    "build_control_prompt", "build_prompt", "build_deepseek_review",
    "Popen", "check_call", "check_output", "system",
    "promote_lesson",
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


def test_anti_lessons_module_has_no_forbidden_sinks():
    tree = ast.parse((CORE_DIR / "anti_lessons.py").read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    calls = _called_names(tree)
    roots = {name.split(".", 1)[0] for name in imports}

    assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), roots & FORBIDDEN_IMPORT_ROOTS
    assert imports.isdisjoint(FORBIDDEN_IMPORTS), imports & FORBIDDEN_IMPORTS
    assert calls.isdisjoint(FORBIDDEN_CALLS), calls & FORBIDDEN_CALLS
