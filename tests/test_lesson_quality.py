from core.lesson_quality import evaluate_lesson_candidate


def _valid_candidate(**overrides):
    candidate = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": ["src/app.py"],
        "diff_stats": {"added": 4, "removed": 2},
    }
    candidate.update(overrides)
    return candidate


def test_auto_approves_small_valid_candidate():
    result = evaluate_lesson_candidate(_valid_candidate())

    assert result["promotion"] == "auto_approved"
    assert result["active_knowledge_allowed"] is True
    assert result["score"] == 1.0


def test_missing_required_data_needs_human_review():
    candidate = _valid_candidate()
    del candidate["validation_ok"]

    result = evaluate_lesson_candidate(candidate)

    assert result["promotion"] == "needs_human_review"
    assert result["active_knowledge_allowed"] is False


def test_forbidden_files_block_promotion():
    result = evaluate_lesson_candidate(
        _valid_candidate(touched_forbidden_files=["secrets.env"])
    )

    assert result["promotion"] == "blocked"
    assert result["active_knowledge_allowed"] is False


def test_test_file_changes_block_promotion():
    result = evaluate_lesson_candidate(
        _valid_candidate(changed_files=["tests/test_app.py"])
    )

    assert result["promotion"] == "blocked"
    assert result["active_knowledge_allowed"] is False


def test_env_and_agent_changes_block_promotion():
    env_result = evaluate_lesson_candidate(_valid_candidate(changed_files=[".env"]))
    agent_result = evaluate_lesson_candidate(
        _valid_candidate(changed_files=[".agent/session.json"])
    )

    assert env_result["promotion"] == "blocked"
    assert agent_result["promotion"] == "blocked"


def test_benchmark_validation_files_block_promotion():
    result = evaluate_lesson_candidate(
        _valid_candidate(changed_files=["benchmarks/cases/python/foo/case.json"])
    )

    assert result["promotion"] == "blocked"
    assert result["active_knowledge_allowed"] is False


def test_unknown_patch_kind_needs_human_review():
    result = evaluate_lesson_candidate(_valid_candidate(patch_kind="unknown"))

    assert result["promotion"] == "needs_human_review"
    assert result["active_knowledge_allowed"] is False


def test_large_available_diff_needs_human_review():
    result = evaluate_lesson_candidate(_valid_candidate(diff_stats={"changed": 31}))

    assert result["promotion"] == "needs_human_review"
    assert result["active_knowledge_allowed"] is False


def test_malformed_diff_stats_needs_human_review():
    result = evaluate_lesson_candidate(_valid_candidate(diff_stats={}))

    assert result["promotion"] == "needs_human_review"
    assert result["active_knowledge_allowed"] is False


def test_failed_validation_blocks_promotion():
    result = evaluate_lesson_candidate(_valid_candidate(validation_ok=False))

    assert result["promotion"] == "blocked"
    assert result["active_knowledge_allowed"] is False
