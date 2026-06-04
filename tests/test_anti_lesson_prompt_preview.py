"""Phase 11.7a — Anti-Lesson CONTROL Block Formatter (pure preview only).

A *pure* formatter that shows what an anti-lesson CONTROL block *would* look like
— without wiring it into CONTROL, active retrieval, patching, Dream, benchmarks,
or model calls:

  * ``build_anti_lesson_control_block_preview`` / ``format_..._markdown`` are pure
    (they take an already-built shadow-retrieval result and never touch the store);
  * the optional ``/lessons/anti/control-preview`` route reads lessons via the
    existing shadow loader and never mutates anything;
  * nothing here injects into CONTROL, changes active retrieval, runs Dream / the
    mutation oracle / benchmarks / patching / a model, and nothing
    creates/promotes/blocks/merges a lesson.

These tests pin both the formatter behavior and the safety guarantees.
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
from core.anti_lesson_prompt_preview import (
    PREVIEW_LABEL,
    build_anti_lesson_control_block_preview,
    format_anti_lesson_control_block_markdown,
)
from core.anti_lesson_retrieval_shadow import build_anti_lesson_shadow_retrieval


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


def _shadow(query, antis, **kw):
    return build_anti_lesson_shadow_retrieval(query, antis, **kw)


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


# ── 1. pure formatter content ────────────────────────────────────────────────


def test_preview_includes_tempting_why_and_safer():
    a = _anti(
        "20260101_000000_000001",
        title="swallow exceptions",
        tempting="wrap call in try/except pass",
        why="it masks the real failure",
        safer="assert the expected error explicitly",
    )
    preview = build_anti_lesson_control_block_preview(_shadow("swallow exceptions", [a]))
    item = preview["items"][0]
    assert item["lesson_id"] == a["id"]
    assert item["tempting_wrong_pattern"] == "wrap call in try/except pass"
    assert item["why_wrong"] == "it masks the real failure"
    assert item["safer_alternative"] == "assert the expected error explicitly"

    md = format_anti_lesson_control_block_markdown(preview)
    assert "wrap call in try/except pass" in md
    assert "it masks the real failure" in md
    assert "assert the expected error explicitly" in md


def test_preview_carries_evidence_and_duplicate_of():
    a = _anti(
        "20260101_000000_000001",
        title="swallow exceptions",
        evidence=["reports/run_42.json"],
        duplicate_of="20260101_000000_000099",
    )
    preview = build_anti_lesson_control_block_preview(_shadow("swallow exceptions", [a]))
    item = preview["items"][0]
    assert item["evidence_refs"] == ["reports/run_42.json"]
    assert item["duplicate_of"] == "20260101_000000_000099"


def test_preview_items_marked_shadow_only_and_preview_only():
    a = _anti("20260101_000000_000001", title="swallow exceptions")
    preview = build_anti_lesson_control_block_preview(_shadow("swallow exceptions", [a]))
    assert preview["preview_only"] is True
    assert preview["items"][0]["shadow_only"] is True


# ── 2. bounds / empty ────────────────────────────────────────────────────────


def test_preview_max_items_bounded():
    antis = [
        _anti(f"20260101_000000_00000{i}", title="swallow exceptions case")
        for i in range(1, 6)
    ]
    shadow = _shadow("swallow exceptions", antis, max_items=5)
    preview = build_anti_lesson_control_block_preview(shadow, max_items=2)
    assert len(preview["items"]) == 2
    assert preview["max_items"] == 2
    assert preview["source_total_matches"] == 5


def test_preview_handles_empty_shadow_result():
    for empty in ({}, {"selected_matches": []}, build_anti_lesson_shadow_retrieval("nope", [])):
        preview = build_anti_lesson_control_block_preview(empty)
        assert preview["items"] == []
        md = format_anti_lesson_control_block_markdown(preview)
        assert PREVIEW_LABEL in md
        assert isinstance(md, str) and md.strip()


# ── 3. guardrail label ───────────────────────────────────────────────────────


def test_preview_markdown_contains_not_injected_guardrail():
    a = _anti("20260101_000000_000001", title="swallow exceptions")
    preview = build_anti_lesson_control_block_preview(_shadow("swallow exceptions", [a]))
    md = format_anti_lesson_control_block_markdown(preview)
    assert "PREVIEW ONLY" in md
    assert "NOT INJECTED" in md.upper()
    assert PREVIEW_LABEL == preview["label"]


def test_preview_lists_blocked_actions():
    preview = build_anti_lesson_control_block_preview({})
    for blocked in ("inject_into_control", "modify_active_retrieval", "patch", "promote"):
        assert blocked in preview["blocked_actions"]


# ── 4. route: read-only JSON / Markdown ──────────────────────────────────────


def test_route_requires_query(lessons_repo):
    resp = _client().get("/lessons/anti/control-preview")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_route_returns_json(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    resp = _client().get("/lessons/anti/control-preview?query=swallow+exceptions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["preview"]["query"] == "swallow exceptions"
    assert body["preview"]["preview_only"] is True
    assert body["preview"]["label"] == PREVIEW_LABEL
    assert isinstance(body["preview"]["generated_at"], str)


def test_route_returns_markdown_when_requested(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    resp = _client().get("/lessons/anti/control-preview?query=swallow+exceptions&format=markdown")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert PREVIEW_LABEL in body["markdown"]


def test_route_max_items_bounded(lessons_repo):
    for i in range(6):
        anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title=f"swallow exceptions {i}"))
    resp = _client().get("/lessons/anti/control-preview?query=swallow+exceptions&max_items=2")
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["preview"]["items"]) <= 2


def test_route_does_not_mutate_lesson_files(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    before = _snapshot(lessons_repo)
    _client().get("/lessons/anti/control-preview?query=swallow+exceptions")
    _client().get("/lessons/anti/control-preview?query=swallow+exceptions&format=markdown")
    after = _snapshot(lessons_repo)
    assert before == after


# ── 5. retrieval / CONTROL stay clean after the preview call ─────────────────


def test_active_retrieval_excludes_anti_after_preview(lessons_repo):
    rec = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    lesson_store.promote_lesson(rec["id"])  # worst case: explicitly promoted
    _client().get("/lessons/anti/control-preview?query=swallow+exceptions")
    assert rec["id"] not in {r["id"] for r in lesson_retrieval.list_active_lessons()}
    found = lesson_retrieval.find_active_lessons(query="swallow exceptions")
    assert rec["id"] not in {r["id"] for r in found}


def test_control_prompt_excludes_anti_after_preview(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    rec = anti_lessons.create_manual_anti_lesson(
        **_valid_kwargs(title="ANTI_PREVIEW_SHOULD_NOT_LEAK")
    )
    lesson_store.promote_lesson(rec["id"])
    _client().get("/lessons/anti/control-preview?query=swallow+exceptions")
    prompt = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    assert "ANTI_PREVIEW_SHOULD_NOT_LEAK" not in prompt


def test_control_retrieval_prompter_do_not_import_preview_module():
    for fname in ("control_engine.py", "prompter.py", "lesson_retrieval.py"):
        src = (CORE_DIR / fname).read_text(encoding="utf-8")
        assert "anti_lesson_prompt_preview" not in src


# ── 6. UI contract ───────────────────────────────────────────────────────────

_TMPL = TEMPLATE.read_text(encoding="utf-8")


def _preview_panel_slice():
    start = _TMPL.find('id="antiControlPreviewPanel"')
    end = _TMPL.find("<!-- /memory-anti-control-preview -->", start)
    assert start != -1 and end != -1, "control preview panel markers not found"
    return _TMPL[start:end]


def test_ui_has_preview_panel():
    assert 'id="antiControlPreviewPanel"' in _TMPL
    assert "loadAntiControlPreview" in _TMPL


def test_ui_has_preview_warning():
    assert "Preview only. This block is not injected into CONTROL." in _TMPL


def test_ui_calls_read_only_route():
    assert "/lessons/anti/control-preview" in _TMPL


def test_ui_preview_panel_has_no_dangerous_controls():
    panel = _preview_panel_slice()
    # The required warning legitimately says "not injected into CONTROL"; the guard
    # targets dangerous *controls*, so strip the warning paragraph before scanning.
    w_start = panel.find('class="anti-lesson-report__warning"')
    if w_start != -1:
        w_end = panel.find("</p>", w_start)
        panel = panel[:w_start] + panel[w_end:]
    panel = panel.lower()
    for bad in ("enable anti-lessons", "inject", "promote", "toggle", "run patch", "run dream"):
        assert bad not in panel


# ── 7. forbidden sinks absent in the new module ──────────────────────────────

PHASE_MODULES = ("anti_lesson_prompt_preview.py",)

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


def test_preview_module_has_no_forbidden_sinks():
    for fname in PHASE_MODULES:
        tree = ast.parse((CORE_DIR / fname).read_text(encoding="utf-8"))
        imports = _imported_modules(tree)
        calls = _called_names(tree)
        roots = {name.split(".", 1)[0] for name in imports}
        assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), (fname, roots & FORBIDDEN_IMPORT_ROOTS)
        assert imports.isdisjoint(FORBIDDEN_IMPORTS), (fname, imports & FORBIDDEN_IMPORTS)
        assert calls.isdisjoint(FORBIDDEN_CALLS), (fname, calls & FORBIDDEN_CALLS)
