"""Phase 11.5 — Reverse Dream / Adversarial Replay planning layer.

A *dry-run* planner that reads existing local evidence (lessons + anti-lessons)
and proposes which targets would be worth attacking in a future adversarial
replay — and explicitly never attacks anything:

  * ``build_reverse_dream_plan`` / ``format_reverse_dream_plan_markdown`` are pure
    (they take an already-loaded list and never touch the store);
  * ``load_reverse_dream_plan`` is the only store-aware entry — it *reads* lessons
    and never mutates anything;
  * nothing here runs Dream, the mutation oracle, benchmarks, patching, or a
    model, and nothing creates/promotes/blocks a lesson.

These tests pin both the planner behavior and the safety guarantees (read-only,
no execution, anti-lessons stay inert, CONTROL/retrieval unchanged).
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
from core.reverse_dream_planner import (
    DRY_RUN_GUARDRAIL,
    build_reverse_dream_plan,
    format_reverse_dream_plan_markdown,
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


# ── fixtures / builders ──────────────────────────────────────────────────────


def _normal(
    lesson_id,
    *,
    title="Normal lesson",
    status="candidate",
    scope="global",
    repo_scope_id=None,
    active=False,
    confidence=0.0,
    validation_ok=None,
    files_touched=None,
    changed_lines=None,
    evidence=None,
    related=None,
    source="manual",
    source_report=None,
):
    candidate: dict = {}
    if validation_ok is not None:
        candidate["validation_ok"] = validation_ok
    if files_touched is not None:
        candidate["files_touched"] = list(files_touched)
    if changed_lines is not None:
        candidate["diff_stats"] = {"changed_lines": changed_lines}
    if evidence is not None:
        candidate["evidence_refs"] = list(evidence)
    if related is not None:
        candidate["related_lesson_ids"] = list(related)
    return {
        "id": lesson_id,
        "kind": "lesson",
        "status": status,
        "scope": scope,
        "repo_scope_id": repo_scope_id,
        "title": title,
        "source": source,
        "source_report": source_report,
        "tags": [],
        "active_knowledge_allowed": bool(active),
        "confidence": confidence,
        "candidate": candidate,
        "evaluation": {"score": confidence},
        "duplicate_of": None,
        "archived": False,
        "superseded_by": None,
    }


def _anti(
    lesson_id,
    *,
    status="candidate",
    scope="global",
    repo_scope_id=None,
    title="Do NOT do X",
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


def _valid_kwargs(**overrides):
    base = dict(
        title="Do NOT swallow exceptions to make tests pass",
        tempting_wrong_pattern="Wrapping the call in try/except: pass to silence the failure.",
        why_wrong="It hides the real bug and the next run regresses silently.",
        safer_alternative="Fix the root cause or assert the expected error explicitly.",
    )
    base.update(overrides)
    return base


def _normal_candidate(**over):
    base = {"validation_ok": True, "summary": "did X to fix Y"}
    base.update(over)
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


# ── 1. selection: active / broad-patch normal lessons ────────────────────────


def test_selects_active_broad_patch_normal_lesson():
    risky = _normal("20260101_000000_000001", active=True, changed_lines=120)
    plain = _normal("20260101_000000_000002", evidence=["reports/small.json"])
    plan = build_reverse_dream_plan([risky, plain])

    ids = {t["target_id"] for t in plan["selected_targets"]}
    assert risky["id"] in ids
    target = next(t for t in plan["selected_targets"] if t["target_id"] == risky["id"])
    assert "active_knowledge" in target["risk_signals"]
    assert "broad_patch" in target["risk_signals"]
    # the plain, well-grounded, non-risky lesson is not attacked
    assert plain["id"] not in ids
    assert any(
        s["target_id"] == plain["id"] and "no risk signals" in s["reason"].lower()
        for s in plan["skipped"]
    )


def test_selects_high_confidence_and_passed_validation():
    hc = _normal("20260101_000000_000001", confidence=0.95)
    pv = _normal("20260101_000000_000002", validation_ok=True)
    plan = build_reverse_dream_plan([hc, pv])

    ids = {t["target_id"] for t in plan["selected_targets"]}
    assert hc["id"] in ids and pv["id"] in ids
    hct = next(t for t in plan["selected_targets"] if t["target_id"] == hc["id"])
    pvt = next(t for t in plan["selected_targets"] if t["target_id"] == pv["id"])
    assert "high_confidence" in hct["risk_signals"]
    assert "passed_validation" in pvt["risk_signals"]


def test_selects_broad_patch_by_files_touched():
    wide = _normal(
        "20260101_000000_000001",
        files_touched=["a.py", "b.py", "c.py", "d.py"],
    )
    plan = build_reverse_dream_plan([wide])
    target = plan["selected_targets"][0]
    assert "broad_patch" in target["risk_signals"]


def test_flags_weak_or_missing_validation_context():
    weak = _normal("20260101_000000_000001", active=True)  # no evidence / no validation
    plan = build_reverse_dream_plan([weak])
    target = plan["selected_targets"][0]
    assert "weak_or_missing_validation_context" in target["risk_signals"]


# ── 2. related anti-lessons as supporting evidence ───────────────────────────


def test_links_related_anti_lessons():
    normal = _normal("20260101_000000_000001", active=True)
    anti = _anti("20260101_000000_000002", related=["20260101_000000_000001"])
    plan = build_reverse_dream_plan([normal, anti])

    target = next(t for t in plan["selected_targets"] if t["target_id"] == normal["id"])
    assert "has_related_anti_lesson" in target["risk_signals"]
    assert any(a["id"] == anti["id"] for a in target["related_anti_lessons"])


def test_anti_lessons_never_primary_targets():
    anti = _anti("20260101_000000_000001", related=["20260101_000000_000002"])
    normal = _normal("20260101_000000_000002", active=True)
    plan = build_reverse_dream_plan([anti, normal])

    sel_ids = {t["target_id"] for t in plan["selected_targets"]}
    assert anti["id"] not in sel_ids
    assert normal["id"] in sel_ids
    # anti surfaces as supporting evidence on the normal target...
    target = next(t for t in plan["selected_targets"] if t["target_id"] == normal["id"])
    assert any(a["id"] == anti["id"] for a in target["related_anti_lessons"])
    # ...and is recorded under skipped as supporting-evidence-only
    assert any(
        s["target_id"] == anti["id"] and "supporting evidence" in s["reason"].lower()
        for s in plan["skipped"]
    )


def test_flags_duplicate_anti_lesson_warning():
    normal = _normal(
        "20260101_000000_000001",
        active=True,
        related=["20260101_000000_000002", "20260101_000000_000003"],
    )
    a = _anti("20260101_000000_000002", tempting="the very same tempting pattern",
              related=["20260101_000000_000001"])
    b = _anti("20260101_000000_000003", tempting="the very same tempting pattern",
              related=["20260101_000000_000001"], duplicate_of="20260101_000000_000002")
    plan = build_reverse_dream_plan([normal, a, b])

    target = next(t for t in plan["selected_targets"] if t["target_id"] == normal["id"])
    assert "anti_lesson_duplicate_warning" in target["risk_signals"]


# ── 3. allowed / blocked actions contract ────────────────────────────────────


def test_targets_carry_allowed_and_blocked_actions():
    normal = _normal("20260101_000000_000001", active=True)
    plan = build_reverse_dream_plan([normal])
    target = plan["selected_targets"][0]
    assert target["allowed_actions"] == ["report_only"]
    for blocked in (
        "run_dream",
        "run_mutation_oracle",
        "create_anti_lesson",
        "patch",
        "benchmark",
        "model_call",
    ):
        assert blocked in target["blocked_actions"]


def test_suggested_future_checks_present():
    normal = _normal("20260101_000000_000001", active=True, changed_lines=200)
    plan = build_reverse_dream_plan([normal])
    target = plan["selected_targets"][0]
    assert isinstance(target["suggested_future_checks"], list)
    assert target["suggested_future_checks"]
    assert isinstance(target["reason_to_attack"], str) and target["reason_to_attack"]


# ── 4. cap / totals (no silent truncation) ───────────────────────────────────


def test_respects_max_items_and_reports_total():
    normals = [
        _normal(f"20260101_000000_00000{i}", active=True) for i in range(1, 6)
    ]
    plan = build_reverse_dream_plan(normals, max_items=2)
    assert plan["total_candidates"] == 5
    assert len(plan["selected_targets"]) == 2
    capped = [s for s in plan["skipped"] if "cap" in s["reason"].lower()]
    assert len(capped) == 3


# ── 5. Markdown formatter ────────────────────────────────────────────────────


def test_markdown_contains_dry_run_guardrail():
    plan = build_reverse_dream_plan([_normal("20260101_000000_000001", active=True)])
    md = format_reverse_dream_plan_markdown(plan)
    assert "Reverse Dream" in md
    assert DRY_RUN_GUARDRAIL in md
    assert "dry-run plan" in md.lower()


def test_markdown_lists_blocked_actions_and_checks():
    plan = build_reverse_dream_plan(
        [_normal("20260101_000000_000001", active=True, changed_lines=200)]
    )
    md = format_reverse_dream_plan_markdown(plan)
    assert "run_mutation_oracle" in md
    assert "create_anti_lesson" in md


# ── 6. route: read-only JSON / Markdown ──────────────────────────────────────


def test_route_returns_plan_json(lessons_repo):
    rec = lesson_store.save_candidate_lesson(
        _normal_candidate(), title="Active lesson", source="manual"
    )
    lesson_store.promote_lesson(rec["id"])
    resp = _client().get("/lessons/anti/reverse-dream-plan")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert isinstance(body["plan"]["generated_at"], str)
    assert body["plan"]["guardrail"]
    assert any(
        t["target_id"] == rec["id"] for t in body["plan"]["selected_targets"]
    )


def test_route_returns_markdown_when_requested(lessons_repo):
    rec = lesson_store.save_candidate_lesson(
        _normal_candidate(), title="Active lesson", source="manual"
    )
    lesson_store.promote_lesson(rec["id"])
    resp = _client().get("/lessons/anti/reverse-dream-plan?format=markdown")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert DRY_RUN_GUARDRAIL in body["markdown"]


def test_plan_route_does_not_mutate_lesson_files(lessons_repo):
    rec = lesson_store.save_candidate_lesson(
        _normal_candidate(), title="Active lesson", source="manual"
    )
    lesson_store.promote_lesson(rec["id"])
    anti_lessons.create_manual_anti_lesson(
        **_valid_kwargs(related_lesson_ids=[rec["id"]])
    )
    before = _snapshot(lessons_repo)
    _client().get("/lessons/anti/reverse-dream-plan")
    _client().get("/lessons/anti/reverse-dream-plan?format=markdown")
    after = _snapshot(lessons_repo)
    assert before == after


# ── 7. retrieval / CONTROL stay clean after the plan is requested ────────────


def test_active_retrieval_excludes_anti_after_plan(lessons_repo):
    rec = anti_lessons.create_manual_anti_lesson(**_valid_kwargs())
    lesson_store.promote_lesson(rec["id"])  # worst case: explicitly promoted
    _client().get("/lessons/anti/reverse-dream-plan")
    assert rec["id"] not in {r["id"] for r in lesson_retrieval.list_active_lessons()}
    found = lesson_retrieval.find_active_lessons(query="swallow exceptions")
    assert rec["id"] not in {r["id"] for r in found}


def test_control_prompt_excludes_anti_after_plan(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    rec = anti_lessons.create_manual_anti_lesson(
        **_valid_kwargs(title="ANTI_PLAN_SHOULD_NOT_LEAK")
    )
    lesson_store.promote_lesson(rec["id"])
    _client().get("/lessons/anti/reverse-dream-plan")
    prompt = control_engine.build_control_prompt(
        _control_result(), "swallow exceptions", repo_path=str(lessons_repo)
    )
    assert "ANTI_PLAN_SHOULD_NOT_LEAK" not in prompt


def test_control_and_prompter_do_not_import_planner():
    for fname in ("control_engine.py", "prompter.py"):
        src = (CORE_DIR / fname).read_text(encoding="utf-8")
        assert "reverse_dream_planner" not in src


# ── 8. UI contract ───────────────────────────────────────────────────────────

_TMPL = TEMPLATE.read_text(encoding="utf-8")


def test_ui_has_reverse_dream_panel():
    assert 'id="reverseDreamPlanPanel"' in _TMPL
    assert "loadReverseDreamPlan" in _TMPL


def test_ui_has_dry_run_warning():
    assert (
        "Dry-run only. No adversarial execution or anti-lesson creation happens here."
        in _TMPL
    )


def test_ui_calls_read_only_route():
    assert "/lessons/anti/reverse-dream-plan" in _TMPL


def test_ui_has_no_run_reverse_dream_button():
    low = _TMPL.lower()
    assert "run reverse dream" not in low
    assert "/reverse-dream/run" not in _TMPL


# ── 9. forbidden sinks absent in the new module ──────────────────────────────

PHASE_MODULES = ("reverse_dream_planner.py",)

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


def test_planner_module_has_no_forbidden_sinks():
    for fname in PHASE_MODULES:
        tree = ast.parse((CORE_DIR / fname).read_text(encoding="utf-8"))
        imports = _imported_modules(tree)
        calls = _called_names(tree)
        roots = {name.split(".", 1)[0] for name in imports}
        assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), (fname, roots & FORBIDDEN_IMPORT_ROOTS)
        assert imports.isdisjoint(FORBIDDEN_IMPORTS), (fname, imports & FORBIDDEN_IMPORTS)
        assert calls.isdisjoint(FORBIDDEN_CALLS), (fname, calls & FORBIDDEN_CALLS)
