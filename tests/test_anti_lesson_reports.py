"""Phase 11.4 — Anti-Lesson Evidence / Reporting Shadow Views.

A *read-only* reporting layer over stored anti-lessons. It summarizes them for
audit/explanation but changes nothing about live behavior:

  * builds structured JSON + a Markdown view (pure helpers);
  * a GET route that only reads from lesson storage;
  * anti-lessons stay inert — excluded from active retrieval and the CONTROL
    prompt even after the report route is hit.

These tests also prove the new module has no forbidden sinks and does not couple
CONTROL/prompter to the report.
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
from core.anti_lesson_reports import (
    GUARDRAIL_NOTE,
    build_anti_lesson_report,
    format_anti_lesson_report_markdown,
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


def _anti(lesson_id, *, status="candidate", scope="global", repo_scope_id=None,
          title="Do NOT do X", tempting="wrap in try/except pass",
          why="it hides the real bug", safer="fix the root cause",
          evidence=None, related=None, source="manual", source_report=None,
          duplicate_of=None, archived=False, superseded_by=None, tags=None):
    return {
        "id": lesson_id,
        "kind": "anti_lesson",
        "status": status,
        "scope": scope,
        "repo_scope_id": repo_scope_id,
        "title": title,
        "source": source,
        "source_report": source_report,
        "tags": list(tags or []),
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
        "archived": archived,
        "superseded_by": superseded_by,
    }


def _normal(lesson_id, *, title="Normal lesson", status="active"):
    return {
        "id": lesson_id,
        "kind": "lesson",
        "status": status,
        "scope": "global",
        "repo_scope_id": None,
        "title": title,
        "source": "manual",
        "source_report": None,
        "tags": [],
        "candidate": {},
        "duplicate_of": None,
        "archived": False,
        "superseded_by": None,
    }


def _snapshot(tmp_path):
    root = tmp_path / ".agent" / "lessons"
    out = {}
    if root.is_dir():
        for p in sorted(root.rglob("*.json")):
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


# ── 1. pure builder: counts ──────────────────────────────────────────────────


def test_report_counts_candidate_blocked_active():
    lessons = [
        _anti("20260101_000000_000001", status="candidate"),
        _anti("20260101_000000_000002", status="blocked"),
        _anti("20260101_000000_000003", status="active"),
        _normal("20260101_000000_000004"),  # ignored by the anti report
    ]
    report = build_anti_lesson_report(lessons)
    assert report["counts"]["total"] == 3
    assert report["counts"]["by_status"]["candidate"] == 1
    assert report["counts"]["by_status"]["blocked"] == 1
    assert report["counts"]["by_status"]["active"] == 1
    assert report["counts"]["by_kind"]["anti_lesson"] == 3


def test_report_separates_global_and_repo_scope():
    lessons = [
        _anti("20260101_000000_000001", scope="global"),
        _anti("20260101_000000_000002", scope="repo", repo_scope_id="repo-abc"),
    ]
    report = build_anti_lesson_report(lessons)
    assert report["counts"]["by_scope"]["global"] == 1
    assert report["counts"]["by_scope"]["repo"] == 1


# ── 2. duplicates / evidence / related ───────────────────────────────────────


def test_report_includes_duplicate_links_and_groups():
    a = _anti("20260101_000000_000001", tempting="the very same tempting pattern")
    b = _anti("20260101_000000_000002", tempting="the very same tempting pattern",
              duplicate_of="20260101_000000_000001")
    report = build_anti_lesson_report([a, b])
    assert any(link["duplicate_of"] == a["id"] for link in report["duplicate_links"])
    assert any(
        set(g["lesson_ids"]) >= {a["id"], b["id"]}
        for g in report["duplicate_groups"]
    )


def test_report_surfaces_evidence_and_related_ids():
    normal_id = "20260101_000000_000099"
    a = _anti("20260101_000000_000001",
              evidence=["reports/run_42.json"], related=[normal_id])
    normal = _normal(normal_id, title="Related normal lesson")
    report = build_anti_lesson_report([a, normal])
    row = next(r for r in report["candidates"] if r["id"] == a["id"])
    assert row["evidence_refs"] == ["reports/run_42.json"]
    assert row["related_lesson_ids"] == [normal_id]
    assert any(
        rel["related_id"] == normal_id and rel["anti_id"] == a["id"]
        for rel in report["related_normal_lessons"]
    )


def test_report_top_tempting_patterns():
    lessons = [
        _anti("20260101_000000_000001", tempting="Wrap in try/except pass"),
        _anti("20260101_000000_000002", tempting="wrap in try/except pass"),
        _anti("20260101_000000_000003", tempting="Use a mutable default arg"),
    ]
    report = build_anti_lesson_report(lessons)
    assert report["top_tempting_patterns"][0]["count"] == 2


# ── 3. archived / superseded / weak ──────────────────────────────────────────


def test_report_lists_archived_and_superseded():
    a = _anti("20260101_000000_000001", archived=True)
    b = _anti("20260101_000000_000002", superseded_by="20260101_000000_000001")
    report = build_anti_lesson_report([a, b])
    assert any(r["id"] == a["id"] for r in report["archived"])
    assert any(r["id"] == b["id"] for r in report["superseded"])
    assert report["counts"]["archived"] == 1
    assert report["counts"]["superseded"] == 1


def test_report_flags_weak_records():
    weak = _anti("20260101_000000_000001", why="   ")  # blank required field
    strong = _anti("20260101_000000_000002")
    report = build_anti_lesson_report([weak, strong])
    entry = next(r for r in report["weak_records"] if r["id"] == weak["id"])
    assert any("why_wrong" in m for m in entry["missing"])
    assert report["counts"]["weak"] == 1
    assert all(r["id"] != strong["id"] for r in report["weak_records"])


# ── 4. Markdown formatter ────────────────────────────────────────────────────


def test_markdown_includes_guardrail_and_title():
    report = build_anti_lesson_report([_anti("20260101_000000_000001")])
    md = format_anti_lesson_report_markdown(report)
    assert "Anti-Lesson Report" in md
    assert GUARDRAIL_NOTE in md


def test_markdown_has_expected_sections():
    report = build_anti_lesson_report([
        _anti("20260101_000000_000001"),
        _anti("20260101_000000_000002", why="  "),
    ])
    md = format_anti_lesson_report_markdown(report)
    assert "Candidate" in md
    assert "Weak" in md or "Incomplete" in md


# ── 5. route: read-only JSON / Markdown ──────────────────────────────────────


def test_route_returns_report_json(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    resp = _client().get("/lessons/anti/report")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["report"]["counts"]["total"] >= 1
    assert body["report"]["guardrail"] == GUARDRAIL_NOTE
    assert isinstance(body["report"]["generated_at"], str)


def test_route_returns_markdown_when_requested(lessons_repo):
    anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    resp = _client().get("/lessons/anti/report?format=markdown")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert GUARDRAIL_NOTE in body["markdown"]


def test_report_route_does_not_mutate_lesson_files(lessons_repo):
    a = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti A"))
    b = anti_lessons.create_manual_anti_lesson(**_valid_kwargs(title="Anti B"))
    # b is a duplicate of a, but the *report* must never write that link.
    before = _snapshot(lessons_repo)
    _client().get("/lessons/anti/report")
    _client().get("/lessons/anti/report?format=markdown")
    after = _snapshot(lessons_repo)
    assert before == after


# ── 6. retrieval / CONTROL stay clean after the report is requested ──────────


def test_active_retrieval_excludes_anti_after_report(lessons_repo):
    rec = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    lesson_store.promote_lesson(rec["id"])  # worst case: explicitly promoted
    _client().get("/lessons/anti/report")
    assert rec["id"] not in {r["id"] for r in lesson_retrieval.list_active_lessons()}
    found = lesson_retrieval.find_active_lessons(query="swallow exceptions")
    assert rec["id"] not in {r["id"] for r in found}


def test_control_prompt_excludes_anti_after_report(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    rec = anti_lessons.create_manual_anti_lesson(
        **_valid_kwargs(title="ANTI_REPORT_SHOULD_NOT_LEAK")
    )
    lesson_store.promote_lesson(rec["id"])
    _client().get("/lessons/anti/report")
    prompt = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    assert "ANTI_REPORT_SHOULD_NOT_LEAK" not in prompt


def test_control_and_prompter_do_not_import_report_module():
    for fname in ("control_engine.py", "prompter.py"):
        src = (CORE_DIR / fname).read_text(encoding="utf-8")
        assert "anti_lesson_reports" not in src


# ── 7. UI contract ───────────────────────────────────────────────────────────

_TMPL = TEMPLATE.read_text(encoding="utf-8")


def test_ui_has_anti_lesson_report_panel():
    assert 'id="antiLessonReportPanel"' in _TMPL
    assert "loadAntiLessonReport" in _TMPL


def test_ui_report_has_inert_warning():
    assert "Anti-lessons are report-only and are not used by CONTROL yet." in _TMPL


def test_ui_report_calls_read_only_route():
    assert "/lessons/anti/report" in _TMPL


# ── 8. forbidden sinks absent in the new module ──────────────────────────────

PHASE_MODULES = ("anti_lesson_reports.py",)

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
    "promote_lesson", "block_lesson", "archive_lesson", "create_merge",
    "save_candidate_lesson", "save_raw_lesson_record", "patch_lesson_fields",
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
