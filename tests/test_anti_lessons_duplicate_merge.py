"""Phase 11.3 — Anti-Lesson Duplicate / Merge Polish.

Advisory duplicate detection for anti-lessons plus anti+anti merge hardening.
Everything here stays INERT (Phase 11.1/11.2 guarantees):

  * duplicate detection is advisory only — it never blocks, promotes, activates,
    or merges anything;
  * anti+anti merge yields a *candidate* anti-lesson with
    ``active_knowledge_allowed=False``;
  * normal+anti merge is still a hard block;
  * anti-lessons never reach live retrieval / the CONTROL prompt.

These tests also prove the touched core modules have no forbidden sinks.
"""
import ast
from pathlib import Path

import pytest

import config as config_module
from core import anti_lessons, control_engine, lesson_merge, lesson_retrieval, lesson_store
from core.lesson_duplicates import detect_anti_lesson_duplicates


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


def _anti_record(lesson_id, *, title="Do NOT do X", kind="anti_lesson",
                 tempting="wrap in try/except pass", why="hides the real bug",
                 safer="fix the root cause", evidence=None, related=None,
                 source_report=None):
    return {
        "id": lesson_id,
        "kind": kind,
        "title": title,
        "source": "manual",
        "source_report": source_report,
        "candidate": {
            "anti_lesson": True,
            "tempting_wrong_pattern": tempting,
            "why_wrong": why,
            "safer_alternative": safer,
            "evidence_refs": list(evidence or []),
            "related_lesson_ids": list(related or []),
        },
    }


def _count_lesson_files(tmp_path) -> int:
    root = tmp_path / ".agent" / "lessons"
    if not root.is_dir():
        return 0
    return len(list(root.rglob("*.json")))


# ── 1. pure duplicate detector ───────────────────────────────────────────────


def test_detector_catches_same_tempting_wrong_pattern():
    new = _anti_record("NEW", title="One title",
                       tempting="Wrap the failing call in try/except: pass")
    other = _anti_record("OLD", title="A totally different title",
                         tempting="wrap the failing call in try/except pass!",
                         why="some other reason", safer="some other alternative")
    result = detect_anti_lesson_duplicates(new, [other])
    assert result["duplicate_of"] == "OLD"
    assert any("tempting_wrong_pattern" in r for r in result["reasons"])
    assert any(p["lesson_id"] == "OLD" for p in result["possible_duplicates"])


def test_detector_catches_shared_evidence_refs():
    new = _anti_record("NEW", title="Title one", tempting="pattern one",
                       why="why one", safer="safer one",
                       evidence=["reports/run_42.json"])
    other = _anti_record("OLD", title="Title two", tempting="pattern two",
                         why="why two", safer="safer two",
                         evidence=["reports/run_42.json", "notes.md"])
    result = detect_anti_lesson_duplicates(new, [other])
    assert any(p["lesson_id"] == "OLD" for p in result["possible_duplicates"])
    assert any("evidence_refs" in r for r in result["reasons"])
    # Shared evidence alone is a weak signal — not a strong duplicate_of.
    assert result["duplicate_of"] is None


def test_detector_ignores_unrelated_anti_lessons():
    new = _anti_record("NEW", title="Avoid mutable default args",
                       tempting="use a list as a default argument",
                       why="it is shared across calls", safer="use a None sentinel")
    other = _anti_record("OLD", title="Do not catch broad exceptions",
                         tempting="except Exception everywhere",
                         why="it masks real bugs", safer="catch specific types",
                         evidence=["x.json"], related=["20260101_000000_000000"])
    result = detect_anti_lesson_duplicates(new, [other])
    assert result["duplicate_of"] is None
    assert result["possible_duplicates"] == []
    assert result["reasons"] == []


def test_detector_ignores_non_anti_records():
    """A normal lesson must never be reported as an anti-lesson duplicate."""
    new = _anti_record("NEW", tempting="the very same pattern")
    normal = _anti_record("NORMAL", kind="lesson", tempting="the very same pattern")
    result = detect_anti_lesson_duplicates(new, [normal])
    assert result["duplicate_of"] is None
    assert result["possible_duplicates"] == []


def test_detector_excludes_self_by_id():
    rec = _anti_record("SAME", tempting="identical pattern")
    result = detect_anti_lesson_duplicates(rec, [rec])
    assert result["duplicate_of"] is None
    assert result["possible_duplicates"] == []


# ── 2. store-aware wrapper ───────────────────────────────────────────────────


def test_find_anti_lesson_duplicates_reads_store(lessons_repo):
    a = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    b = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())  # same title+pattern
    result = anti_lessons.find_anti_lesson_duplicates(b)
    assert result["duplicate_of"] == a["id"]
    assert any(p["lesson_id"] == a["id"] for p in result["possible_duplicates"])


# ── 3. manual create route: duplicate warning metadata ───────────────────────


def test_route_returns_duplicate_warning_metadata(lessons_repo):
    first = _client().post("/lessons/anti/create", json=_valid_kwargs()).get_json()
    resp = _client().post("/lessons/anti/create", json=_valid_kwargs())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    warning = body["duplicate_warning"]
    assert warning["duplicate_of"] == first["lesson"]["id"]
    assert warning["reasons"]
    assert any(
        p["lesson_id"] == first["lesson"]["id"]
        for p in warning["possible_duplicates"]
    )
    # The advisory duplicate link is recorded on the new candidate (metadata only).
    assert body["lesson"]["duplicate_of"] == first["lesson"]["id"]


def test_route_no_duplicate_warning_when_unique(lessons_repo):
    resp = _client().post("/lessons/anti/create", json=_valid_kwargs())
    body = resp.get_json()
    assert body["duplicate_warning"]["duplicate_of"] is None
    assert body["duplicate_warning"]["possible_duplicates"] == []
    assert body["lesson"]["duplicate_of"] is None


def test_duplicate_warning_does_not_activate_or_promote(lessons_repo):
    _client().post("/lessons/anti/create", json=_valid_kwargs())
    resp = _client().post("/lessons/anti/create", json=_valid_kwargs())
    body = resp.get_json()
    lesson = body["lesson"]
    # A duplicate WAS detected …
    assert body["duplicate_warning"]["duplicate_of"]
    # … but nothing was promoted/activated.
    assert lesson["status"] == "candidate"
    assert lesson["active_knowledge_allowed"] is False
    active_dir = lessons_repo / ".agent" / "lessons" / "active"
    assert not any(active_dir.glob("*.json"))
    active_ids = {r["id"] for r in lesson_retrieval.list_active_lessons()}
    assert lesson["id"] not in active_ids


# ── 4. anti+anti merge polish ────────────────────────────────────────────────


def test_anti_plus_anti_merge_stays_candidate_anti(lessons_repo):
    a = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    b = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    new, superseded = lesson_merge.create_merge(
        [a["id"], b["id"]], "Merged anti", "", []
    )
    assert new["kind"] == "anti_lesson"
    assert new["status"] == "candidate"
    assert set(superseded) == {a["id"], b["id"]}
    reloaded = lesson_store.get_lesson_by_id(new["id"])
    assert reloaded["kind"] == "anti_lesson"
    assert reloaded["status"] == "candidate"


def test_anti_plus_anti_merge_preserves_inert_flag(lessons_repo):
    a = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    b = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    new, _ = lesson_merge.create_merge([a["id"], b["id"]], "Merged anti", "", [])
    assert new["active_knowledge_allowed"] is False
    reloaded = lesson_store.get_lesson_by_id(new["id"])
    assert reloaded["active_knowledge_allowed"] is False


def test_anti_plus_anti_merge_preserves_source_metadata(lessons_repo):
    a = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    b = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    new, _ = lesson_merge.create_merge([a["id"], b["id"]], "Merged anti", "", [])
    assert set(new["merge_sources"]) == {a["id"], b["id"]}
    assert {s["id"] for s in new["merge_sources_data"]} == {a["id"], b["id"]}
    assert new["supersedes"] == [a["id"], b["id"]]
    assert new["superseded_by"] is None
    assert new["duplicate_of"] is None


def test_normal_plus_anti_merge_still_hard_blocked(lessons_repo):
    normal = lesson_store.save_candidate_lesson(
        _candidate(), source="manual", title="Normal lesson"
    )
    anti = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    with pytest.raises(ValueError, match="anti-lesson"):
        lesson_merge.create_merge(
            [normal["id"], anti["id"]], "M", "", [], confirm_mix_kinds=True
        )


# ── 5. preview behavior ──────────────────────────────────────────────────────


def test_preview_merge_normal_plus_anti_warns_no_write(lessons_repo):
    normal = lesson_store.save_candidate_lesson(
        _candidate(), source="manual", title="Normal lesson"
    )
    anti = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    n = lesson_store.get_lesson_by_id(normal["id"])
    a = lesson_store.get_lesson_by_id(anti["id"])
    before = _count_lesson_files(lessons_repo)
    record, warnings = lesson_merge.preview_merge([n, a])
    assert any("mixing lesson kinds" in w for w in warnings)
    assert "id" not in record
    assert _count_lesson_files(lessons_repo) == before  # preview wrote nothing


def test_preview_merge_anti_plus_anti_reports_inert_outcome(lessons_repo):
    a = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    b = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    ra = lesson_store.get_lesson_by_id(a["id"])
    rb = lesson_store.get_lesson_by_id(b["id"])
    before = _count_lesson_files(lessons_repo)
    record, warnings = lesson_merge.preview_merge([ra, rb])
    assert record["kind"] == "anti_lesson"
    assert record["status"] == "candidate"
    assert record["active_knowledge_allowed"] is False
    assert "id" not in record
    assert _count_lesson_files(lessons_repo) == before  # preview wrote nothing
    # Overlap reasons surface (identical tempting_wrong_pattern from same kwargs).
    assert any("overlap" in w.lower() for w in warnings)


# ── 6. retrieval / CONTROL stay clean after duplicate + merge ────────────────


def test_no_active_retrieval_includes_anti_after_duplicate_and_merge(lessons_repo):
    a = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    b = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    new, _ = lesson_merge.create_merge([a["id"], b["id"]], "Merged anti", "", [])
    # Worst case: explicitly promote the merged anti-lesson into the active bucket.
    lesson_store.promote_lesson(new["id"])
    active_ids = {r["id"] for r in lesson_retrieval.list_active_lessons()}
    for lid in (a["id"], b["id"], new["id"]):
        assert lid not in active_ids


def test_control_prompt_excludes_anti_after_merge(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    a = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="ANTI_A_LEAK"))
    b = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="ANTI_B_LEAK"))
    new, _ = lesson_merge.create_merge(
        [a["id"], b["id"]], "ANTI_MERGED_LEAK", "", []
    )
    lesson_store.promote_lesson(new["id"])
    prompt = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    assert "ANTI_MERGED_LEAK" not in prompt
    assert "ANTI_A_LEAK" not in prompt
    assert "ANTI_B_LEAK" not in prompt


# ── 7. UI contract (parse index.html as text) ────────────────────────────────

_TMPL = TEMPLATE.read_text(encoding="utf-8")


def test_ui_renders_duplicate_badge():
    assert "lesson-badge--duplicate" in _TMPL
    assert "duplicate_of" in _TMPL


def test_ui_create_surfaces_duplicate_warning():
    assert "duplicate_warning" in _TMPL


# ── 8. forbidden sinks absent in the phase modules ───────────────────────────

PHASE_MODULES = ("anti_lessons.py", "lesson_duplicates.py")

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


def test_phase_modules_have_no_forbidden_sinks():
    for fname in PHASE_MODULES:
        tree = ast.parse((CORE_DIR / fname).read_text(encoding="utf-8"))
        imports = _imported_modules(tree)
        calls = _called_names(tree)
        roots = {name.split(".", 1)[0] for name in imports}
        assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), (fname, roots & FORBIDDEN_IMPORT_ROOTS)
        assert imports.isdisjoint(FORBIDDEN_IMPORTS), (fname, imports & FORBIDDEN_IMPORTS)
        assert calls.isdisjoint(FORBIDDEN_CALLS), (fname, calls & FORBIDDEN_CALLS)
