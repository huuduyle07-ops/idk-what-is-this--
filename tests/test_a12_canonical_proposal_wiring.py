"""A.12 tests: Canonical Proposal Candidate Creator Wiring.

Canonical behavior (P1):
1.  P1 creates proposal candidate with LESSON_AUTO_ACTIVE=True and still lands candidate-only.
2.  P1 creates/uses canonical source_key (embedded in candidate).
3.  P1 source_key matches P4's format for the same proposal_dir.
4.  P1 detects duplicate via canonical proposal_artifact/source_key (cross-path from P4).
5.  P1 detects duplicate via legacy patch_proposal/source_report.
6.  Legacy duplicate detection does not rewrite old records.

Delegation:
7.  P2 queue path delegates to canonical creator (characterization).
8.  P3 web /proposals/promote delegates to canonical creator (characterization).
9.  P4 seed_lessons_from_proposals detects compat duplicate from P1/P2/P3 old-style records.
10. P5 maybe_create_lesson_candidate_from_proposal inherits P4's compat dedup.
11. P6 create_lesson_candidate.py --proposal-dir chains through to compat dedup (via P5 → P4).

Safety:
12. LESSON_AUTO_ACTIVE is forced off during save in P1 with new source_key feature.
13. LESSON_AUTO_ACTIVE is restored after a save error in P1.
14. lesson_quality blocked output still goes blocked via P1.
15. No proposal path writes directly to active.
16. Dream path (maybe_create_lesson_candidate_from_dream_item disabled) is unchanged.

Import/side-effect guards (P1 module):
17. No model clients imported by canonical creator.
18. No Flask import in non-web helpers (P1 module).
19. No DB import at module level in P1.
20. No patch apply calls in P1.
21. No promotion call from candidate creation in P1.
22. No subprocess import in P1.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core import lesson_store
from scripts import create_lesson_from_proposal as cl

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_lesson_from_proposal.py"


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


def _write_artifacts(
    item_dir: Path,
    *,
    validation_ok: bool = True,
    apply_success: bool = True,
    changed_files=None,
    case_name: str = "python_discount_validation",
    language: str = "python",
    category: str = "logic_validation",
    summary: str = "Fix the discount validation logic.",
    omit: tuple[str, ...] = (),
) -> None:
    item_dir.mkdir(parents=True, exist_ok=True)
    changed_files = list(changed_files or ["pricing.py"])

    files = {
        "item.json": {
            "case_name": case_name,
            "language": language,
            "category": category,
        },
        "case.json": {
            "name": case_name,
            "language": language,
            "category": category,
            "expected_changed_files": changed_files,
            "forbidden_changed_files": [],
        },
        "patch_proposal.json": {
            "summary": summary,
            "patch_candidate": None,
            "patch_plan": [
                {
                    "op": "replace_snippet",
                    "relative_path": f,
                    "target_snippet": "x",
                    "patched_snippet": "y",
                }
                for f in changed_files
            ],
        },
        "apply_result.json": {
            "success": apply_success,
            "applied_ops": [
                {"op": "replace_snippet", "relative_path": f}
                for f in changed_files
            ],
            "diffs": [
                f"--- a/{f}\n+++ b/{f}\n@@ -1,1 +1,1 @@\n-old\n+new\n"
                for f in changed_files
            ],
            "rollback_performed": False,
        },
        "validation.json": {
            "ok": validation_ok,
            "validation_ok": validation_ok,
            "command": "python main.py",
            "duration_sec": 0.5,
            "output": "OK" if validation_ok else "FAIL",
        },
    }
    for name, data in files.items():
        if name in omit:
            continue
        (item_dir / name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


@pytest.fixture
def proposals_repo(tmp_path, monkeypatch):
    """Shared test environment: redirected lesson_store and proposals_root."""
    monkeypatch.setattr(lesson_store, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)

    proposals_root = tmp_path / ".agent" / "proposals"
    proposals_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cl, "_default_proposals_root", lambda: proposals_root)

    return tmp_path


def _item_dir(repo: Path, run: str = "20260601_120000", item: str = "01-test") -> Path:
    return repo / ".agent" / "proposals" / run / item


# ---------------------------------------------------------------------------
# 1. LESSON_AUTO_ACTIVE=True still lands candidate-only (A.6 guard preserved)
# ---------------------------------------------------------------------------


def test_p1_lesson_auto_active_true_still_candidate_not_active(proposals_repo, monkeypatch):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)

    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert lesson["status"] == "candidate"
    assert lesson["active_knowledge_allowed"] is False
    # flag restored
    assert lesson_store.config.LESSON_AUTO_ACTIVE is True
    assert lesson_store.list_lessons(status="active") == []


# ---------------------------------------------------------------------------
# 2. P1 embeds canonical source_key in candidate
# ---------------------------------------------------------------------------


def test_p1_candidate_has_source_key(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    candidate = lesson.get("candidate") or {}
    assert "source_key" in candidate, "P1 must embed source_key in candidate"
    key = candidate["source_key"]
    assert isinstance(key, str) and key.strip(), "source_key must be a non-empty string"


# ---------------------------------------------------------------------------
# 3. P1 source_key matches P4's format for the same proposal_dir
# ---------------------------------------------------------------------------


def test_p1_source_key_matches_p4_format(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # Compute P1's source_key
    artifacts = cl._load_artifacts(item_dir)
    p1_key = cl._canonical_proposal_source_key(item_dir, artifacts, proposals_root=proposals_root)

    # Compute P4's source_key by calling seed helpers directly
    from scripts.seed_lessons_from_proposals import (
        _as_str_list,
        _proposal_source_hash,
        _safe_relative,
    )

    proposal_ref = _safe_relative(item_dir, proposals_root)
    candidate_data = cl._build_candidate(artifacts)
    changed_files = _as_str_list(candidate_data.get("changed_files"))
    _, _, _, source_key_tail = _proposal_source_hash(
        artifacts["patch_proposal.json"],
        changed_files,
        artifacts["validation.json"],
    )
    p4_expected_key = f"{proposal_ref}:{source_key_tail}"

    assert p1_key == p4_expected_key, (
        f"P1 source_key {p1_key!r} must match P4's computed key {p4_expected_key!r}"
    )


# ---------------------------------------------------------------------------
# 4. P1 detects duplicate via canonical proposal_artifact/source_key (cross-path)
# ---------------------------------------------------------------------------


def test_p1_detects_cross_path_duplicate_via_source_key(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # Create a record via P4 (proposal_artifact/source_key identity)
    from scripts.seed_lessons_from_proposals import seed_lessons_from_proposals

    summary = seed_lessons_from_proposals(
        proposal_refs=[item_dir],
        proposals_root=proposals_root,
        global_candidate=True,
    )
    assert summary["counts"]["created"] + summary["counts"]["blocked"] == 1

    # P1 on the same proposal_dir should detect the duplicate
    result = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert result.get("already_exists") is True, (
        "P1 must detect cross-path duplicate created by P4 via source_key"
    )
    # No new lesson was created
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 5. P1 detects duplicate via legacy patch_proposal/source_report
# ---------------------------------------------------------------------------


def test_p1_detects_legacy_source_report_duplicate(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    # Create an old-style record with patch_proposal / source_report (no source_key)
    existing = lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["pricing.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="python_discount_validation",
    )

    result = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert result.get("already_exists") is True, (
        "P1 must detect legacy duplicate via patch_proposal/source_report"
    )
    assert result.get("compatibility_duplicate") is True, (
        "P1 must mark legacy source_report match as compatibility_duplicate"
    )
    assert result.get("id") == existing.get("id"), (
        "P1 must return the existing lesson id on legacy duplicate"
    )
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 6. Legacy duplicate detection does not rewrite old records
# ---------------------------------------------------------------------------


def test_p1_legacy_dedup_does_not_rewrite_old_record(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    existing = lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["pricing.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="original_case",
    )
    original_id = existing["id"]
    original_source = existing.get("source")

    # P1 detects duplicate and returns early
    cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    # The old record must be unchanged
    lessons = lesson_store.list_lessons()
    assert len(lessons) == 1
    record = lessons[0]
    assert record["id"] == original_id, "Existing record id must not change"
    assert record.get("source") == original_source, "Existing record source must not change"
    assert record.get("source_report") == str(item_dir), "Existing source_report must not change"
    # source_key must NOT have been written into the old record
    old_candidate = record.get("candidate") or {}
    assert "source_key" not in old_candidate or old_candidate.get("source_key") is None, (
        "Legacy record must not be rewritten with source_key"
    )


# ---------------------------------------------------------------------------
# 7. P2 queue path delegates to canonical creator (characterization)
# ---------------------------------------------------------------------------


def test_p2_delegates_to_p1_create_lesson_from_proposal(proposals_repo):
    """P2's _maybe_create_lesson_candidate delegates to create_lesson_from_proposal (P1).

    Verified by observing that the created lesson carries source='patch_proposal',
    which is set by P1 and not by any P2-private code.
    """
    from scripts import run_patch_proposal_queue as queue

    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    result = queue._maybe_create_lesson_candidate(
        item_dir=item_dir,
        item={"human_approved_for_proposal": True},
        apply_result={"success": True},
        validation={"validation_ok": True},
        create_lesson_candidates=True,
    )

    assert result.get("lesson_candidate_created") is True
    lessons = lesson_store.list_lessons()
    assert len(lessons) == 1
    assert lessons[0]["source"] == "patch_proposal", (
        "P2 must create a lesson via P1 (source='patch_proposal')"
    )


# ---------------------------------------------------------------------------
# 8. P3 web /proposals/promote delegates to canonical creator (characterization)
# ---------------------------------------------------------------------------


def test_p3_route_delegates_to_create_lesson_from_proposal(proposals_repo, monkeypatch):
    """P3 /proposals/promote imports and calls create_lesson_from_proposal (P1)."""
    import web.app as webapp

    called = {}

    def fake_create(proposal_dir, **kwargs):
        called["proposal_dir"] = str(proposal_dir)
        return {
            "id": "web-lesson-id",
            "status": "candidate",
            "scope": "global",
            "repo_scope_id": None,
            "active_knowledge_allowed": False,
            "evaluation": {"promotion": "auto_approved"},
        }

    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    def fake_resolve(raw, proposals_root=None):
        return item_dir

    monkeypatch.setattr("scripts.create_lesson_from_proposal._resolve_proposal_dir", fake_resolve)
    monkeypatch.setattr("scripts.create_lesson_from_proposal.create_lesson_from_proposal", fake_create)

    with webapp.app.test_client() as client:
        resp = client.post(
            "/proposals/promote",
            data={"proposal_dir": str(item_dir)},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "proposal_dir" in called, "P3 must call create_lesson_from_proposal"


# ---------------------------------------------------------------------------
# 9. P4 detects compat duplicate from old-style P1/P2/P3 records
# ---------------------------------------------------------------------------


def test_p4_detects_compat_duplicate_from_old_p1_record(proposals_repo):
    """P4 seed must detect an old patch_proposal/source_report record as a duplicate."""
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # Create an old-style P1 record (no source_key in candidate)
    lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["pricing.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="python_discount_validation",
    )
    assert len(lesson_store.list_lessons()) == 1

    # P4 on same proposal_dir must detect this as a compat duplicate
    from scripts.seed_lessons_from_proposals import seed_lessons_from_proposals

    summary = seed_lessons_from_proposals(
        proposal_refs=[item_dir],
        proposals_root=proposals_root,
        global_candidate=True,
    )

    assert summary["counts"]["duplicates"] == 1, (
        "P4 must count compat P1/P2/P3 record as a duplicate"
    )
    assert summary["counts"]["created"] == 0
    assert len(lesson_store.list_lessons()) == 1, "P4 must not create a new lesson"


# ---------------------------------------------------------------------------
# 10. P5 inherits P4's compat dedup
# ---------------------------------------------------------------------------


def test_p5_inherits_p4_compat_dedup(proposals_repo):
    """maybe_create_lesson_candidate_from_proposal routes through P4 which has compat dedup."""
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # Create old-style P1 record
    lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["pricing.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="python_discount_validation",
    )

    from core.lesson_auto_candidates import maybe_create_lesson_candidate_from_proposal

    result = maybe_create_lesson_candidate_from_proposal(
        item_dir,
        enabled=True,
        global_candidate=True,
        proposals_root=proposals_root,
    )

    assert result["status"] == "duplicate", (
        "P5 must report duplicate when P1-style record already exists"
    )
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 11. P6 chains through to compat dedup
# ---------------------------------------------------------------------------


def test_p6_chains_to_compat_dedup(proposals_repo, capsys):
    """create_lesson_candidate.py --proposal-dir routes P6 → P5 → P4 with compat dedup."""
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # Create old-style P1 record
    lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["pricing.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="python_discount_validation",
    )

    from scripts import create_lesson_candidate as p6_script

    # P6 calls P5 with enabled=True and global_candidate=True; patch proposals_root via env
    from core import lesson_auto_candidates

    original = lesson_auto_candidates.maybe_create_lesson_candidate_from_proposal

    def _wrapped(proposal_dir, repo_path=None, *, enabled=False, **kwargs):
        return original(proposal_dir, repo_path=repo_path, enabled=enabled,
                        proposals_root=proposals_root, **kwargs)

    import unittest.mock as mock
    with mock.patch.object(lesson_auto_candidates, "maybe_create_lesson_candidate_from_proposal", _wrapped):
        exit_code = p6_script._main([
            "--proposal-dir", str(item_dir),
            "--global-candidate",
        ])

    assert exit_code == 0
    out = capsys.readouterr().out
    result_data = json.loads(out)
    assert result_data["status"] == "duplicate", (
        "P6 must chain through P5→P4 and return duplicate status"
    )
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 12. LESSON_AUTO_ACTIVE forced off during P1 save (with source_key feature)
# ---------------------------------------------------------------------------


def test_p1_forces_lesson_auto_active_off_during_save_with_source_key(proposals_repo, monkeypatch):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)

    observed = []

    original_save = lesson_store.save_candidate_lesson

    def capturing_save(candidate, **kwargs):
        observed.append(lesson_store.config.LESSON_AUTO_ACTIVE)
        return original_save(candidate, **kwargs)

    monkeypatch.setattr(lesson_store, "save_candidate_lesson", capturing_save)

    cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert observed == [False], "LESSON_AUTO_ACTIVE must be False during save_candidate_lesson"
    assert lesson_store.config.LESSON_AUTO_ACTIVE is True, "flag must be restored after save"


# ---------------------------------------------------------------------------
# 13. LESSON_AUTO_ACTIVE restored after error
# ---------------------------------------------------------------------------


def test_p1_restores_lesson_auto_active_after_save_error(proposals_repo, monkeypatch):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)

    def fail_save(candidate, **kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(lesson_store, "save_candidate_lesson", fail_save)

    with pytest.raises(RuntimeError, match="injected failure"):
        cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert lesson_store.config.LESSON_AUTO_ACTIVE is True


# ---------------------------------------------------------------------------
# 14. lesson_quality blocked output still goes blocked via P1
# ---------------------------------------------------------------------------


def test_p1_lesson_quality_blocked_still_blocked(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    # validation_ok=False → lesson_quality blocks
    _write_artifacts(item_dir, validation_ok=False)

    lesson = cl.create_lesson_from_proposal(item_dir, allow_failed=True, global_candidate=True)

    assert lesson["status"] == "blocked"
    assert lesson["active_knowledge_allowed"] is False
    assert lesson["evaluation"]["promotion"] == "blocked"


# ---------------------------------------------------------------------------
# 15. No proposal path writes directly to active
# ---------------------------------------------------------------------------


def test_no_proposal_path_writes_to_active(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # P1
    cl.create_lesson_from_proposal(item_dir, global_candidate=True)
    assert lesson_store.list_lessons(status="active") == [], "P1 must not write to active"

    # Reset store
    for lesson in lesson_store.list_lessons():
        pass  # just enumerate; we won't delete — just check active is empty

    # P4 on a fresh item_dir2
    item_dir2 = _item_dir(proposals_repo, item="02-test")
    _write_artifacts(item_dir2)
    from scripts.seed_lessons_from_proposals import seed_lessons_from_proposals

    seed_lessons_from_proposals(
        proposal_refs=[item_dir2],
        proposals_root=proposals_root,
        global_candidate=True,
    )
    assert lesson_store.list_lessons(status="active") == [], "P4 must not write to active"


# ---------------------------------------------------------------------------
# 16. Dream path unchanged — disabled no-op still works
# ---------------------------------------------------------------------------


def test_dream_path_disabled_noop_unchanged():
    from core.lesson_auto_candidates import maybe_create_lesson_candidate_from_dream_item

    result = maybe_create_lesson_candidate_from_dream_item(
        "some/item/dir",
        enabled=False,
    )
    assert result["status"] == "disabled"
    assert result["source"] == "dream_artifact"


# ---------------------------------------------------------------------------
# 17–22. Import / side-effect guards for P1 module (AST checks)
# ---------------------------------------------------------------------------


def _all_imported_modules(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            modules.add(mod)
            modules.add(mod.split(".")[0])
            for alias in node.names:
                modules.add(alias.name)
    return modules


def _all_ast_call_names(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_p1_no_model_client_import():
    modules = _all_imported_modules(MODULE_PATH)
    for forbidden in ("anthropic", "openai", "sleeping_consultant"):
        assert not any(forbidden in m for m in modules), (
            f"P1 must not import model client: {forbidden}"
        )


def test_p1_no_flask_import():
    modules = _all_imported_modules(MODULE_PATH)
    assert "flask" not in modules, "P1 module must not import Flask"
    assert "web" not in {m.split(".")[0] for m in modules if m}, (
        "P1 module must not import web package"
    )


def test_p1_no_subprocess_import():
    modules = _all_imported_modules(MODULE_PATH)
    assert "subprocess" not in modules, "P1 module must not import subprocess"


def test_p1_no_patch_apply_call():
    calls = _all_ast_call_names(MODULE_PATH)
    for forbidden in ("apply_patch", "run_patch_plan_with_artifacts", "run_patch_plan"):
        assert forbidden not in calls, f"P1 module must not call {forbidden}"


def test_p1_no_promotion_call():
    calls = _all_ast_call_names(MODULE_PATH)
    assert "promote_lesson" not in calls, "P1 module must not call promote_lesson"


def test_p1_no_db_module_level_import():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE_PATH))
    top_level_modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            top_level_modules.add(mod)
    for forbidden in ("sqlalchemy", "database", "memory_store"):
        assert forbidden not in top_level_modules, (
            f"P1 must not have top-level DB import: {forbidden}"
        )
