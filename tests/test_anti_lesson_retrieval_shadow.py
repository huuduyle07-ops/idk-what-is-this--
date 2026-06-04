"""Phase 11.6 — Anti-Lesson Retrieval Shadow Mode.

A *read-only* shadow retrieval layer: for a given query/context, report which
anti-lessons would be relevant *if* anti-lessons were enabled later. It returns
matches only and never affects the live agent path:

  * ``build_anti_lesson_shadow_retrieval`` / ``format_..._markdown`` are pure
    (they take an already-loaded list and never touch the store);
  * ``load_anti_lesson_shadow_retrieval`` is the only store-aware entry — it
    *reads* lessons and never mutates anything;
  * nothing here injects into CONTROL, changes active retrieval, runs Dream / the
    mutation oracle / benchmarks / patching / a model, and nothing
    creates/promotes/blocks/merges a lesson.

These tests pin both the matcher behavior and the safety guarantees.
"""
import ast
from pathlib import Path

import pytest

import config as config_module
from core import (
    anti_lessons,
    control_engine,
    lesson_retrieval,
    lesson_store,
)
from core.anti_lesson_retrieval_shadow import (
    SHADOW_GUARDRAIL,
    build_anti_lesson_shadow_retrieval,
    format_anti_lesson_shadow_retrieval_markdown,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = PROJECT_ROOT / "core"
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    fake = lambda repo_path=None: tmp_path / ".agent"
    monkeypatch.setattr(lesson_store, "get_agent_dir", fake)
    monkeypatch.setattr(config_module, "get_agent_dir", fake)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    monkeypatch.setattr(config_module, "ANTI_LESSONS_ENABLED", False, raising=False)
    return tmp_path


# ── builders ─────────────────────────────────────────────────────────────────


def _anti(
    lesson_id,
    *,
    status="candidate",
    scope="global",
    repo_scope_id=None,
    title="Do NOT do X",
    summary="",
    tempting="wrap in try/except pass",
    why="it hides the real bug",
    safer="fix the root cause",
    evidence=None,
    related=None,
    source="manual",
    source_report=None,
    duplicate_of=None,
):
    return {
        "id": lesson_id,
        "kind": "anti_lesson",
        "status": status,
        "scope": scope,
        "repo_scope_id": repo_scope_id,
        "title": title,
        "summary": summary,
        "source": source,
        "source_report": source_report,
        "tags": [],
        "active_knowledge_allowed": False,
        "candidate": {
            "anti_lesson": True,
            "tempting_wrong_pattern": tempting,
            "why_wrong": why,
            "safer_alternative": safer,
            "evidence_refs": list(evidence or []),
            "related_lesson_ids": list(related or []),
        },
        "duplicate_of": duplicate_of,
        "archived": False,
        "superseded_by": None,
    }


def _normal(lesson_id, *, title="Normal lesson", status="active", summary=""):
    return {
        "id": lesson_id,
        "kind": "lesson",
        "status": status,
        "scope": "global",
        "repo_scope_id": None,
        "title": title,
        "summary": summary,
        "source": "manual",
        "source_report": None,
        "tags": [],
        "active_knowledge_allowed": status == "active",
        "candidate": {},
        "duplicate_of": None,
        "archived": False,
        "superseded_by": None,
    }


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


def _snapshot(tmp_path):
    root = tmp_path / ".agent" / "lessons"
    out = {}
    if root.is_dir():
        for p in sorted(root.rglob("*.json")):
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


# ── 1. matching: title / summary / tempting / why / safer ────────────────────


def test_matches_title_and_summary():
    a = _anti(
        "20260101_000000_000001",
        title="Avoid swallowing exceptions in retry loops",
        summary="exceptions should propagate",
        tempting="zzz",
    )
    result = build_anti_lesson_shadow_retrieval("swallowing exceptions retry", [a])
    m = result["selected_matches"][0]
    assert m["lesson_id"] == a["id"]
    assert m["score"] > 0
    assert any("title" in r for r in m["reasons"])
    assert any("summary" in r for r in m["reasons"])


def test_matches_tempting_wrong_pattern():
    a = _anti(
        "20260101_000000_000001",
        title="Unrelated heading",
        summary="",
        tempting="mutable default argument",
    )
    result = build_anti_lesson_shadow_retrieval("mutable default argument", [a])
    m = result["selected_matches"][0]
    assert any("tempting_wrong_pattern" in r for r in m["reasons"])


def test_matches_why_wrong_and_safer_alternative():
    a = _anti(
        "20260101_000000_000001",
        title="X",
        summary="",
        tempting="zzz",
        why="it hides the real bug",
        safer="assert the expected error explicitly",
    )
    r1 = build_anti_lesson_shadow_retrieval("hides the real bug", [a])
    assert any("why_wrong" in r for r in r1["selected_matches"][0]["reasons"])
    r2 = build_anti_lesson_shadow_retrieval("assert expected error", [a])
    assert any("safer_alternative" in r for r in r2["selected_matches"][0]["reasons"])


def test_optional_context_matches_evidence_and_related():
    a = _anti(
        "20260101_000000_000001",
        title="zzz",
        summary="",
        tempting="zzz",
        why="zzz",
        safer="zzz",
        evidence=["reports/run_42.json"],
        related=["20260101_000000_000099"],
    )
    result = build_anti_lesson_shadow_retrieval(
        "nomatchtokenhere",
        [a],
        context={
            "evidence_refs": ["reports/run_42.json"],
            "related_lesson_ids": ["20260101_000000_000099"],
        },
    )
    m = next(m for m in result["selected_matches"] if m["lesson_id"] == a["id"])
    assert any("evidence" in r or "related" in r for r in m["reasons"])


# ── 2. unrelated / normal lessons ────────────────────────────────────────────


def test_unrelated_anti_lessons_are_skipped():
    related = _anti("20260101_000000_000001", title="swallow exceptions", tempting="try/except pass")
    unrelated = _anti("20260101_000000_000002", title="widgets and gizmos", tempting="frobnicate")
    result = build_anti_lesson_shadow_retrieval("swallow exceptions", [related, unrelated])
    ids = {m["lesson_id"] for m in result["selected_matches"]}
    assert related["id"] in ids
    assert unrelated["id"] not in ids
    assert any(s["lesson_id"] == unrelated["id"] for s in result["skipped"])


def test_normal_lessons_never_returned():
    normal = _normal("20260101_000000_000001", title="swallow exceptions normal lesson")
    anti = _anti("20260101_000000_000002", title="swallow exceptions anti")
    result = build_anti_lesson_shadow_retrieval("swallow exceptions", [normal, anti])
    ids = {m["lesson_id"] for m in result["selected_matches"]}
    assert normal["id"] not in ids
    assert anti["id"] in ids
    assert result["total_anti_lessons_considered"] == 1


# ── 3. determinism / bounds / contract ───────────────────────────────────────


def test_deterministic_and_max_items_bounded():
    antis = [
        _anti(f"20260101_000000_00000{i}", title="swallow exceptions case")
        for i in range(1, 6)
    ]
    r1 = build_anti_lesson_shadow_retrieval("swallow exceptions", antis, max_items=2)
    r2 = build_anti_lesson_shadow_retrieval("swallow exceptions", antis, max_items=2)
    assert len(r1["selected_matches"]) == 2
    assert [m["lesson_id"] for m in r1["selected_matches"]] == [
        m["lesson_id"] for m in r2["selected_matches"]
    ]
    capped = [s for s in r1["skipped"] if "cap" in s["reason"].lower()]
    assert len(capped) == 3


def test_matches_marked_shadow_only():
    a = _anti("20260101_000000_000001", title="swallow exceptions")
    result = build_anti_lesson_shadow_retrieval("swallow exceptions", [a])
    assert result["selected_matches"][0]["shadow_only"] is True


def test_result_lists_blocked_actions():
    result = build_anti_lesson_shadow_retrieval("anything", [])
    for blocked in (
        "inject_into_control",
        "modify_active_retrieval",
        "patch",
        "benchmark",
        "dream",
        "model_call",
        "promote",
    ):
        assert blocked in result["blocked_actions"]


# ── 4. Markdown ──────────────────────────────────────────────────────────────


def test_markdown_includes_shadow_guardrail_and_query():
    result = build_anti_lesson_shadow_retrieval(
        "swallow exceptions", [_anti("20260101_000000_000001", title="swallow exceptions")]
    )
    md = format_anti_lesson_shadow_retrieval_markdown(result)
    assert SHADOW_GUARDRAIL in md
    assert "swallow exceptions" in md
    assert "shadow" in md.lower()


def test_markdown_lists_blocked_actions():
    result = build_anti_lesson_shadow_retrieval(
        "swallow exceptions", [_anti("20260101_000000_000001", title="swallow exceptions")]
    )
    md = format_anti_lesson_shadow_retrieval_markdown(result)
    assert "inject_into_control" in md
    assert "modify_active_retrieval" in md


# ── 5. route: read-only JSON / Markdown ──────────────────────────────────────


def test_route_requires_query(lessons_repo):
    resp = _client().get("/lessons/anti/shadow-retrieval")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_route_returns_json(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    resp = _client().get("/lessons/anti/shadow-retrieval?query=swallow+exceptions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["result"]["query"] == "swallow exceptions"
    assert body["result"]["guardrail"] == SHADOW_GUARDRAIL
    assert isinstance(body["result"]["generated_at"], str)
    assert body["result"]["total_anti_lessons_considered"] >= 1


def test_route_returns_markdown_when_requested(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    resp = _client().get("/lessons/anti/shadow-retrieval?query=swallow+exceptions&format=markdown")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert SHADOW_GUARDRAIL in body["markdown"]


def test_route_max_items_bounded(lessons_repo):
    for i in range(6):
        anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title=f"swallow exceptions {i}"))
    resp = _client().get("/lessons/anti/shadow-retrieval?query=swallow+exceptions&max_items=2")
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["result"]["selected_matches"]) <= 2


def test_shadow_route_does_not_mutate_lesson_files(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    before = _snapshot(lessons_repo)
    _client().get("/lessons/anti/shadow-retrieval?query=swallow+exceptions")
    _client().get("/lessons/anti/shadow-retrieval?query=swallow+exceptions&format=markdown")
    after = _snapshot(lessons_repo)
    assert before == after


# ── 6. retrieval / CONTROL stay clean after the shadow call ──────────────────


def test_active_retrieval_excludes_anti_after_shadow(lessons_repo):
    rec = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    lesson_store.promote_lesson(rec["id"])  # worst case: explicitly promoted
    _client().get("/lessons/anti/shadow-retrieval?query=swallow+exceptions")
    assert rec["id"] not in {r["id"] for r in lesson_retrieval.list_active_lessons()}
    found = lesson_retrieval.find_active_lessons(query="swallow exceptions")
    assert rec["id"] not in {r["id"] for r in found}


def test_control_prompt_excludes_anti_after_shadow(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    rec = anti_lessons.create_manual_anti_lesson(
        **_valid_kwargs(title="ANTI_SHADOW_SHOULD_NOT_LEAK")
    )
    lesson_store.promote_lesson(rec["id"])
    _client().get("/lessons/anti/shadow-retrieval?query=swallow+exceptions")
    prompt = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    assert "ANTI_SHADOW_SHOULD_NOT_LEAK" not in prompt


def test_control_retrieval_prompter_do_not_import_shadow_module():
    for fname in ("control_engine.py", "prompter.py", "lesson_retrieval.py"):
        src = (CORE_DIR / fname).read_text(encoding="utf-8")
        assert "anti_lesson_retrieval_shadow" not in src


# ── 7. UI contract ───────────────────────────────────────────────────────────

_TMPL = TEMPLATE.read_text(encoding="utf-8")


def _shadow_panel_slice():
    start = _TMPL.find('id="antiShadowRetrievalPanel"')
    end = _TMPL.find("<!-- /memory-anti-shadow-retrieval -->", start)
    assert start != -1 and end != -1, "shadow panel markers not found"
    return _TMPL[start:end]


def test_ui_has_shadow_panel():
    assert 'id="antiShadowRetrievalPanel"' in _TMPL
    assert "loadAntiShadowMatches" in _TMPL


def test_ui_has_shadow_warning():
    assert "Shadow retrieval is report-only and is not used by CONTROL yet." in _TMPL


def test_ui_calls_read_only_route():
    assert "/lessons/anti/shadow-retrieval" in _TMPL


def test_ui_shadow_panel_has_no_dangerous_controls():
    panel = _shadow_panel_slice().lower()
    for bad in ("enable anti-lessons", "inject", "promote", "run patch", "run dream"):
        assert bad not in panel


# ── 8. forbidden sinks absent in the new module ──────────────────────────────

PHASE_MODULES = ("anti_lesson_retrieval_shadow.py",)

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
    "run_gemini", "run_gemini_request_2", "run_ollama", "run_deepseek",
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


def test_shadow_module_has_no_forbidden_sinks():
    for fname in PHASE_MODULES:
        tree = ast.parse((CORE_DIR / fname).read_text(encoding="utf-8"))
        imports = _imported_modules(tree)
        calls = _called_names(tree)
        roots = {name.split(".", 1)[0] for name in imports}
        assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), (fname, roots & FORBIDDEN_IMPORT_ROOTS)
        assert imports.isdisjoint(FORBIDDEN_IMPORTS), (fname, imports & FORBIDDEN_IMPORTS)
        assert calls.isdisjoint(FORBIDDEN_CALLS), (fname, calls & FORBIDDEN_CALLS)
