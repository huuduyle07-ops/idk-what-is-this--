"""Phase 11.7b — Default-Off CONTROL Anti-Lesson Preview Report.

Shows the anti-lesson CONTROL preview *beside* real CONTROL/debug context without
appending it to the actual CONTROL prompt:

  * ``build_anti_lesson_control_preview_report`` / ``format_..._markdown`` are pure
    (they take an already-loaded list and never touch the store);
  * ``load_anti_lesson_control_preview_report`` is the only store-aware entry — it
    *reads* lessons and never mutates anything;
  * nothing here injects into CONTROL, calls ``build_control_prompt``, changes
    active retrieval, runs Dream / the mutation oracle / benchmarks / patching / a
    model, and nothing creates/promotes/blocks/merges a lesson.

These tests pin both the report behavior and the safety guarantees, including that
``build_control_prompt`` output is byte-identical before and after the route call.
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
from core.anti_lesson_control_report import (
    build_anti_lesson_control_preview_report,
    format_anti_lesson_control_preview_report_markdown,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = PROJECT_ROOT / "core"
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"

CONTROL_UNCHANGED_STATEMENT = "This report does not modify build_control_prompt output."
NOT_INJECTED_STATEMENT = "Anti-lessons are not injected into CONTROL in this phase."


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
    title="Do NOT do X",
    summary="",
    tempting="wrap in try/except pass",
    why="it hides the real bug",
    safer="fix the root cause",
    evidence=None,
    related=None,
    duplicate_of=None,
):
    return {
        "id": lesson_id,
        "kind": "anti_lesson",
        "status": status,
        "scope": "global",
        "repo_scope_id": None,
        "title": title,
        "summary": summary,
        "source": "manual",
        "source_report": None,
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


# ── 1. report content ────────────────────────────────────────────────────────


def test_report_includes_shadow_matches_and_preview_block():
    a = _anti("20260101_000000_000001", title="swallow exceptions", tempting="try/except pass")
    report = build_anti_lesson_control_preview_report("swallow exceptions", [a])
    shadow_ids = {m["lesson_id"] for m in report["shadow_retrieval"]["selected_matches"]}
    block_ids = {it["lesson_id"] for it in report["preview_block"]["items"]}
    assert a["id"] in shadow_ids
    assert a["id"] in block_ids
    assert report["query"] == "swallow exceptions"


def test_report_states_actual_control_unchanged():
    report = build_anti_lesson_control_preview_report("q", [])
    notes = " ".join(report["notes"])
    assert CONTROL_UNCHANGED_STATEMENT in notes
    assert NOT_INJECTED_STATEMENT in notes
    assert report["control_prompt_status"] == "unchanged"
    assert report["anti_lesson_injection"] == "not_injected"
    assert report["report_only"] is True


def test_report_lists_blocked_actions():
    report = build_anti_lesson_control_preview_report("q", [])
    for blocked in ("inject_into_control", "modify_active_retrieval", "patch", "promote"):
        assert blocked in report["blocked_actions"]


def test_report_max_items_bounds_preview_block():
    antis = [
        _anti(f"20260101_000000_00000{i}", title="swallow exceptions case")
        for i in range(1, 6)
    ]
    report = build_anti_lesson_control_preview_report("swallow exceptions", antis, max_items=2)
    assert len(report["preview_block"]["items"]) == 2


# ── 2. Markdown ──────────────────────────────────────────────────────────────


def test_markdown_includes_guardrail_statements():
    a = _anti("20260101_000000_000001", title="swallow exceptions")
    report = build_anti_lesson_control_preview_report("swallow exceptions", [a])
    md = format_anti_lesson_control_preview_report_markdown(report)
    assert CONTROL_UNCHANGED_STATEMENT in md
    assert NOT_INJECTED_STATEMENT in md
    assert "swallow exceptions" in md


def test_markdown_handles_empty_report():
    report = build_anti_lesson_control_preview_report("nope", [])
    md = format_anti_lesson_control_preview_report_markdown(report)
    assert isinstance(md, str) and md.strip()
    assert CONTROL_UNCHANGED_STATEMENT in md


# ── 3. route: read-only JSON / Markdown ──────────────────────────────────────


def test_route_requires_query(lessons_repo):
    resp = _client().get("/lessons/anti/control-preview-report")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_route_returns_json(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    resp = _client().get("/lessons/anti/control-preview-report?query=swallow+exceptions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["report"]["query"] == "swallow exceptions"
    assert body["report"]["control_prompt_status"] == "unchanged"
    assert isinstance(body["report"]["generated_at"], str)
    assert "shadow_retrieval" in body["report"]
    assert "preview_block" in body["report"]


def test_route_returns_markdown_when_requested(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    resp = _client().get("/lessons/anti/control-preview-report?query=swallow+exceptions&format=markdown")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert CONTROL_UNCHANGED_STATEMENT in body["markdown"]


def test_route_max_items_bounded(lessons_repo):
    for i in range(6):
        anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title=f"swallow exceptions {i}"))
    resp = _client().get("/lessons/anti/control-preview-report?query=swallow+exceptions&max_items=2")
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["report"]["preview_block"]["items"]) <= 2


def test_route_does_not_mutate_lesson_files(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    before = _snapshot(lessons_repo)
    _client().get("/lessons/anti/control-preview-report?query=swallow+exceptions")
    _client().get("/lessons/anti/control-preview-report?query=swallow+exceptions&format=markdown")
    after = _snapshot(lessons_repo)
    assert before == after


# ── 4. CONTROL prompt is byte-identical around the route call ────────────────


def test_build_control_prompt_unchanged_around_route(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    rec = anti_lessons.create_manual_anti_lesson(
        **_valid_kwargs(title="ANTI_REPORT_SHOULD_NOT_LEAK")
    )
    lesson_store.promote_lesson(rec["id"])  # worst case: explicitly promoted
    before = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    _client().get("/lessons/anti/control-preview-report?query=swallow+exceptions")
    after = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    assert before == after
    assert "ANTI_REPORT_SHOULD_NOT_LEAK" not in after


def test_active_retrieval_excludes_anti_after_report(lessons_repo):
    rec = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    lesson_store.promote_lesson(rec["id"])
    _client().get("/lessons/anti/control-preview-report?query=swallow+exceptions")
    assert rec["id"] not in {r["id"] for r in lesson_retrieval.list_active_lessons()}
    found = lesson_retrieval.find_active_lessons(query="swallow exceptions")
    assert rec["id"] not in {r["id"] for r in found}


def test_control_retrieval_prompter_do_not_import_report_module():
    for fname in ("control_engine.py", "prompter.py", "lesson_retrieval.py"):
        src = (CORE_DIR / fname).read_text(encoding="utf-8")
        assert "anti_lesson_control_report" not in src


# ── 5. UI contract ───────────────────────────────────────────────────────────

_TMPL = TEMPLATE.read_text(encoding="utf-8")


def _report_panel_slice():
    start = _TMPL.find('id="antiControlPreviewReportPanel"')
    end = _TMPL.find("<!-- /memory-anti-control-preview-report -->", start)
    assert start != -1 and end != -1, "control preview report panel markers not found"
    return _TMPL[start:end]


def test_ui_has_report_panel():
    assert 'id="antiControlPreviewReportPanel"' in _TMPL
    assert "loadAntiControlPreviewReport" in _TMPL


def test_ui_has_report_warning():
    assert "Report only. The actual CONTROL prompt is unchanged." in _TMPL


def test_ui_calls_read_only_route():
    assert "/lessons/anti/control-preview-report" in _TMPL


def test_ui_report_panel_has_no_dangerous_controls():
    panel = _report_panel_slice()
    # The required warning legitimately mentions CONTROL; the guard targets
    # dangerous *controls*, so strip the warning paragraph before scanning.
    w_start = panel.find('class="anti-lesson-report__warning"')
    if w_start != -1:
        w_end = panel.find("</p>", w_start)
        panel = panel[:w_start] + panel[w_end:]
    panel = panel.lower()
    for bad in ("enable", "inject", "apply", "promote", "run patch", "run dream"):
        assert bad not in panel


# ── 6. forbidden sinks absent in the new module ──────────────────────────────

PHASE_MODULES = ("anti_lesson_control_report.py",)

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


def test_report_module_has_no_forbidden_sinks():
    for fname in PHASE_MODULES:
        tree = ast.parse((CORE_DIR / fname).read_text(encoding="utf-8"))
        imports = _imported_modules(tree)
        calls = _called_names(tree)
        roots = {name.split(".", 1)[0] for name in imports}
        assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), (fname, roots & FORBIDDEN_IMPORT_ROOTS)
        assert imports.isdisjoint(FORBIDDEN_IMPORTS), (fname, imports & FORBIDDEN_IMPORTS)
        assert calls.isdisjoint(FORBIDDEN_CALLS), (fname, calls & FORBIDDEN_CALLS)
