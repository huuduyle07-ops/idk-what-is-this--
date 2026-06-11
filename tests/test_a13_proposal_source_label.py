"""A.13 tests: Proposal Source Label Finalization.

New proposal lesson candidates created by the canonical P1 path use:
    source = "proposal_artifact"
    source_key = canonical proposal source key

Legacy patch_proposal/source_report compatibility is fully preserved.

Canonical identity (1-4):
1.  New create_lesson_from_proposal record uses source="proposal_artifact".
2.  New record includes canonical source_key in candidate.
3.  New record does not use "patch_proposal" as its primary source identity.
4.  source_report, if retained, is only compatibility/debug metadata (not the dedup key).

Duplicate compatibility (5-8):
5.  P1 detects existing proposal_artifact/source_key duplicate.
6.  P1 detects existing legacy patch_proposal/source_report duplicate (compat).
7.  P1 legacy duplicate result includes compatibility_duplicate=True.
8.  Legacy duplicate detection does not rewrite old record.

Cross-path compatibility (9-11):
9.  P4 seed_lessons_from_proposals detects new P1 proposal_artifact/source_key record.
10. P4 detects old patch_proposal/source_report record (covered by A.12; regression here).
11. P5 maybe_create_lesson_candidate_from_proposal detects new P1 proposal_artifact record.

Safety (12-16):
12. LESSON_AUTO_ACTIVE=true still lands proposal_artifact records as candidate-only.
13. active_knowledge_allowed is False for new proposal_artifact records.
14. config is restored after successful save.
15. config is restored after save error.
16. lesson_quality blocked output still goes blocked for proposal_artifact records.

Regression (17-21):
17. P2 run_patch_proposal_queue candidate path creates proposal_artifact records.
18. P3 web /proposals/promote delegates to P1 (mocked; source label from P1).
19. CANONICAL_PROPOSAL_SOURCE and LEGACY_PATCH_PROPOSAL_SOURCE constants exported.
20. Old records created with source="patch_proposal" are still accepted by lesson_store.
21. Dream path disabled no-op unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import lesson_store
from scripts import create_lesson_from_proposal as cl


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


def _write_artifacts(
    item_dir: Path,
    *,
    validation_ok: bool = True,
    apply_success: bool = True,
    changed_files=None,
    case_name: str = "python_a13_test",
    language: str = "python",
    category: str = "logic_validation",
    summary: str = "A.13 test proposal fix.",
    omit: tuple[str, ...] = (),
) -> None:
    item_dir.mkdir(parents=True, exist_ok=True)
    changed_files = list(changed_files or ["main.py"])

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
                    "target_snippet": "old",
                    "patched_snippet": "new",
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
            "duration_sec": 0.3,
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
    """Redirected lesson_store + proposals_root for isolation."""
    monkeypatch.setattr(lesson_store, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent")
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)

    proposals_root = tmp_path / ".agent" / "proposals"
    proposals_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cl, "_default_proposals_root", lambda: proposals_root)

    return tmp_path


def _item_dir(repo: Path, run: str = "20260611_100000", item: str = "01-a13") -> Path:
    return repo / ".agent" / "proposals" / run / item


# ---------------------------------------------------------------------------
# 1. New record uses source="proposal_artifact"
# ---------------------------------------------------------------------------


def test_a13_new_record_source_is_proposal_artifact(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert lesson["source"] == "proposal_artifact", (
        "A.13: new P1 records must use source='proposal_artifact'"
    )


# ---------------------------------------------------------------------------
# 2. New record includes canonical source_key
# ---------------------------------------------------------------------------


def test_a13_new_record_has_canonical_source_key(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    candidate = lesson.get("candidate") or {}
    assert "source_key" in candidate, "A.13: new P1 records must embed source_key in candidate"
    key = candidate["source_key"]
    assert isinstance(key, str) and key.strip(), "source_key must be a non-empty string"


# ---------------------------------------------------------------------------
# 3. New record does not use "patch_proposal" as primary source identity
# ---------------------------------------------------------------------------


def test_a13_new_record_does_not_use_patch_proposal_source(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert lesson["source"] != "patch_proposal", (
        "A.13: new P1 records must not use 'patch_proposal' as primary source"
    )


# ---------------------------------------------------------------------------
# 4. source_report retained as compatibility/debug metadata (not dedup key)
# ---------------------------------------------------------------------------


def test_a13_source_report_retained_as_compat_metadata(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    # source_report must still be present for backward compat
    assert lesson.get("source_report") == str(item_dir), (
        "A.13: source_report must be retained as compatibility metadata"
    )
    # But the dedup identity is now source_key, not source_report
    candidate = lesson.get("candidate") or {}
    assert "source_key" in candidate, "dedup identity must be in candidate.source_key"


# ---------------------------------------------------------------------------
# 5. P1 detects canonical proposal_artifact/source_key duplicate
# ---------------------------------------------------------------------------


def test_a13_p1_detects_canonical_source_key_duplicate(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    # Create first record via P1
    first = cl.create_lesson_from_proposal(item_dir, global_candidate=True)
    assert first.get("source") == "proposal_artifact"

    # Second call must detect the duplicate via source_key
    second = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert second.get("already_exists") is True, (
        "P1 must detect own-kind proposal_artifact/source_key duplicate"
    )
    assert second.get("id") == first.get("id")
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 6. P1 detects legacy patch_proposal/source_report duplicate
# 7. legacy duplicate returns compatibility_duplicate=True
# ---------------------------------------------------------------------------


def test_a13_p1_detects_legacy_patch_proposal_duplicate(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    # Create a pre-A.13 legacy record manually
    existing = lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["main.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="python_a13_test",
    )

    result = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert result.get("already_exists") is True, (
        "P1 must detect legacy patch_proposal/source_report duplicate"
    )
    assert result.get("compatibility_duplicate") is True, (
        "P1 must mark legacy match as compatibility_duplicate=True"
    )
    assert result.get("id") == existing.get("id")
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 8. Legacy duplicate detection does not rewrite old record
# ---------------------------------------------------------------------------


def test_a13_legacy_dedup_does_not_rewrite_record(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    existing = lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["main.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="original_case_a13",
    )
    original_source = existing.get("source")

    cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    lessons = lesson_store.list_lessons()
    assert len(lessons) == 1
    record = lessons[0]
    assert record["id"] == existing["id"], "existing record id must not change"
    assert record.get("source") == original_source, "existing record source must not change"
    assert record.get("source") == "patch_proposal", "legacy source must remain patch_proposal"
    old_candidate = record.get("candidate") or {}
    assert old_candidate.get("source_key") is None, (
        "legacy record must not be rewritten with source_key"
    )


# ---------------------------------------------------------------------------
# 9. P4 detects new P1 proposal_artifact/source_key record
# ---------------------------------------------------------------------------


def test_a13_p4_detects_new_p1_proposal_artifact_record(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # Create a new-style proposal_artifact record via P1
    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)
    assert lesson["source"] == "proposal_artifact"
    assert len(lesson_store.list_lessons()) == 1

    # P4 on the same proposal_dir must detect this as a duplicate
    from scripts.seed_lessons_from_proposals import seed_lessons_from_proposals

    summary = seed_lessons_from_proposals(
        proposal_refs=[item_dir],
        proposals_root=proposals_root,
        global_candidate=True,
    )

    assert summary["counts"]["duplicates"] == 1, (
        "P4 must detect new proposal_artifact/source_key record as duplicate"
    )
    assert summary["counts"]["created"] == 0
    assert len(lesson_store.list_lessons()) == 1, "P4 must not create a second lesson"


# ---------------------------------------------------------------------------
# 10. P4 still detects old patch_proposal/source_report records (regression)
# ---------------------------------------------------------------------------


def test_a13_p4_still_detects_old_patch_proposal_record(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # Create old-style record (no source_key)
    lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["main.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="python_a13_test",
    )

    from scripts.seed_lessons_from_proposals import seed_lessons_from_proposals

    summary = seed_lessons_from_proposals(
        proposal_refs=[item_dir],
        proposals_root=proposals_root,
        global_candidate=True,
    )

    assert summary["counts"]["duplicates"] == 1, (
        "P4 must still detect old patch_proposal/source_report records as duplicates"
    )
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 11. P5 detects new P1 proposal_artifact record as duplicate
# ---------------------------------------------------------------------------


def test_a13_p5_detects_new_p1_record(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    proposals_root = proposals_repo / ".agent" / "proposals"

    # Create a new-style proposal_artifact record
    cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    from core.lesson_auto_candidates import maybe_create_lesson_candidate_from_proposal

    result = maybe_create_lesson_candidate_from_proposal(
        item_dir,
        enabled=True,
        global_candidate=True,
        proposals_root=proposals_root,
    )

    assert result["status"] == "duplicate", (
        "P5 must detect new proposal_artifact/source_key record as duplicate"
    )
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 12. LESSON_AUTO_ACTIVE=True still lands proposal_artifact as candidate-only
# ---------------------------------------------------------------------------


def test_a13_auto_active_true_proposal_artifact_still_candidate(proposals_repo, monkeypatch):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)

    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert lesson["source"] == "proposal_artifact"
    assert lesson["status"] == "candidate"
    assert lesson["active_knowledge_allowed"] is False
    assert lesson_store.list_lessons(status="active") == []


# ---------------------------------------------------------------------------
# 13. active_knowledge_allowed is False for new proposal_artifact records
# ---------------------------------------------------------------------------


def test_a13_active_knowledge_allowed_false(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    lesson = cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert lesson["source"] == "proposal_artifact"
    assert lesson["active_knowledge_allowed"] is False


# ---------------------------------------------------------------------------
# 14. config is restored after successful save
# ---------------------------------------------------------------------------


def test_a13_config_restored_after_success(proposals_repo, monkeypatch):
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

    assert observed == [False], "LESSON_AUTO_ACTIVE must be False during save"
    assert lesson_store.config.LESSON_AUTO_ACTIVE is True, "flag must be restored after save"


# ---------------------------------------------------------------------------
# 15. config is restored after save error
# ---------------------------------------------------------------------------


def test_a13_config_restored_after_save_error(proposals_repo, monkeypatch):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)

    def fail_save(candidate, **kwargs):
        raise RuntimeError("injected A.13 save failure")

    monkeypatch.setattr(lesson_store, "save_candidate_lesson", fail_save)

    with pytest.raises(RuntimeError, match="injected A.13 save failure"):
        cl.create_lesson_from_proposal(item_dir, global_candidate=True)

    assert lesson_store.config.LESSON_AUTO_ACTIVE is True, (
        "LESSON_AUTO_ACTIVE must be restored even after save error"
    )


# ---------------------------------------------------------------------------
# 16. lesson_quality blocked output still goes blocked for proposal_artifact
# ---------------------------------------------------------------------------


def test_a13_blocked_quality_still_blocked(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir, validation_ok=False)

    lesson = cl.create_lesson_from_proposal(item_dir, allow_failed=True, global_candidate=True)

    assert lesson["source"] == "proposal_artifact"
    assert lesson["status"] == "blocked"
    assert lesson["active_knowledge_allowed"] is False
    assert lesson["evaluation"]["promotion"] == "blocked"


# ---------------------------------------------------------------------------
# 17. P2 run_patch_proposal_queue creates proposal_artifact records
# ---------------------------------------------------------------------------


def test_a13_p2_creates_proposal_artifact_record(proposals_repo):
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
    assert lessons[0]["source"] == "proposal_artifact", (
        "P2 creates lessons via P1 which now uses source='proposal_artifact'"
    )
    # source_report still present as compat metadata
    assert lessons[0].get("source_report") is not None


# ---------------------------------------------------------------------------
# 18. P3 web /proposals/promote still delegates to P1 (source comes from P1)
# ---------------------------------------------------------------------------


def test_a13_p3_route_still_delegates_to_p1(proposals_repo, monkeypatch):
    import web.app as webapp

    called = {}

    def fake_create(proposal_dir, **kwargs):
        called["proposal_dir"] = str(proposal_dir)
        return {
            "id": "a13-lesson-id",
            "status": "candidate",
            "scope": "global",
            "repo_scope_id": None,
            "active_knowledge_allowed": False,
            "source": "proposal_artifact",
            "evaluation": {"promotion": "auto_approved"},
        }

    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

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
# 19. Constants CANONICAL_PROPOSAL_SOURCE and LEGACY_PATCH_PROPOSAL_SOURCE exported
# ---------------------------------------------------------------------------


def test_a13_constants_exported():
    assert cl.CANONICAL_PROPOSAL_SOURCE == "proposal_artifact", (
        "CANONICAL_PROPOSAL_SOURCE must be 'proposal_artifact'"
    )
    assert cl.LEGACY_PATCH_PROPOSAL_SOURCE == "patch_proposal", (
        "LEGACY_PATCH_PROPOSAL_SOURCE must be 'patch_proposal'"
    )


# ---------------------------------------------------------------------------
# 20. Old records with source="patch_proposal" still accepted by lesson_store
# ---------------------------------------------------------------------------


def test_a13_legacy_source_still_accepted_by_lesson_store(proposals_repo):
    """lesson_store must still accept records with source='patch_proposal' (backward compat)."""
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    legacy = lesson_store.save_candidate_lesson(
        {"validation_ok": True, "changed_files": ["main.py"]},
        source="patch_proposal",
        source_report=str(item_dir),
        case_name="python_a13_test",
    )

    assert legacy["source"] == "patch_proposal"
    assert legacy["status"] == "candidate"
    assert len(lesson_store.list_lessons()) == 1


# ---------------------------------------------------------------------------
# 21. Dream path disabled no-op unchanged
# ---------------------------------------------------------------------------


def test_a13_dream_path_disabled_noop_unchanged():
    from core.lesson_auto_candidates import maybe_create_lesson_candidate_from_dream_item

    result = maybe_create_lesson_candidate_from_dream_item(
        "some/dream/item/dir",
        enabled=False,
    )
    assert result["status"] == "disabled"
    assert result["source"] == "dream_artifact"
