from pathlib import Path

from core.patch_safety import _CATEGORY_WHY, category_why, evaluate_patch_safety


def test_safe_path_passes():
    result = evaluate_patch_safety(["src/app.py"])
    assert result["ok"] is True
    assert result["blocked_paths"] == []
    assert result["reasons"] == []


def test_safe_nested_path_passes():
    result = evaluate_patch_safety(["src/utils/helpers.py", "lib/foo/bar.js"])
    assert result["ok"] is True


def test_empty_list_passes():
    result = evaluate_patch_safety([])
    assert result["ok"] is True


def test_env_file_blocked():
    result = evaluate_patch_safety([".env"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "env"


def test_dotenv_variant_blocked():
    result = evaluate_patch_safety([".env.local"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "env"


def test_test_dir_blocked():
    result = evaluate_patch_safety(["tests/test_app.py"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "test"


def test_test_suffix_blocked():
    result = evaluate_patch_safety(["src/foo.test.ts"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "test"


def test_test_prefix_blocked():
    result = evaluate_patch_safety(["test_module.py"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "test"


def test_agent_dir_blocked():
    result = evaluate_patch_safety([".agent/session.json"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "protected_dir"


def test_git_dir_blocked():
    result = evaluate_patch_safety([".git/config"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "protected_dir"


def test_node_modules_blocked():
    result = evaluate_patch_safety(["node_modules/foo/index.js"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "protected_dir"


def test_target_dir_blocked():
    result = evaluate_patch_safety(["target/release/bin"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "protected_dir"


def test_benchmark_case_blocked():
    result = evaluate_patch_safety(
        ["benchmarks/cases/python/foo/case.json"]
    )
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "benchmark_validation"


def test_benchmark_validate_script_blocked():
    result = evaluate_patch_safety(
        ["benchmarks/cases/python/foo/validate.py"]
    )
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "benchmark_validation"


def test_benchmark_expected_file_blocked():
    result = evaluate_patch_safety(
        ["benchmarks/cases/python/foo/expected_output.txt"]
    )
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "benchmark_validation"


def test_traversal_dotdot_blocked():
    result = evaluate_patch_safety(["../etc/passwd"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "traversal"


def test_traversal_absolute_unix_blocked():
    result = evaluate_patch_safety(["/etc/passwd"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "traversal"


def test_traversal_empty_blocked():
    result = evaluate_patch_safety([""])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "traversal"


def test_traversal_escapes_root(tmp_path):
    inner = tmp_path / "repo"
    inner.mkdir()
    result = evaluate_patch_safety(["../outside.txt"], project_root=inner)
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "traversal"


def test_within_root_passes(tmp_path):
    inner = tmp_path / "repo"
    inner.mkdir()
    result = evaluate_patch_safety(["src/main.py"], project_root=inner)
    assert result["ok"] is True


def test_multiple_paths_collect_all_failures():
    result = evaluate_patch_safety(["src/ok.py", ".env", "tests/test_a.py"])
    assert result["ok"] is False
    assert len(result["blocked_paths"]) == 2
    categories = {b["category"] for b in result["blocked_paths"]}
    assert categories == {"env", "test"}


def test_reasons_mirror_blocked_paths():
    result = evaluate_patch_safety([".env", "tests/test_x.py"])
    assert len(result["reasons"]) == 2
    assert result["reasons"] == [b["reason"] for b in result["blocked_paths"]]


def test_backslash_path_normalized():
    result = evaluate_patch_safety([".agent\\session.json"])
    assert result["ok"] is False
    assert result["blocked_paths"][0]["category"] == "protected_dir"


# --- why / override-hint field --------------------------------------------


def test_blocked_entry_includes_why_for_test_category():
    result = evaluate_patch_safety(["tests/test_app.py"])
    entry = result["blocked_paths"][0]
    assert "why" in entry
    why = entry["why"]
    # Tutor framing: explains the reasoning AND the override path.
    assert "test" in why.lower()
    assert "mask" in why.lower() or "bug" in why.lower()
    assert "override" in why.lower()
    assert "human approval" in why.lower()


def test_blocked_entry_includes_why_for_env_category():
    result = evaluate_patch_safety([".env"])
    entry = result["blocked_paths"][0]
    assert "secret" in entry["why"].lower() or "credential" in entry["why"].lower()
    assert "override" in entry["why"].lower()


def test_blocked_entry_includes_why_for_protected_dir():
    result = evaluate_patch_safety([".agent/session.json"])
    entry = result["blocked_paths"][0]
    assert "agent-owned" in entry["why"].lower() or "build" in entry["why"].lower()
    assert "override" in entry["why"].lower()


def test_blocked_entry_includes_why_for_benchmark_validation():
    result = evaluate_patch_safety(["benchmarks/cases/python/foo/case.json"])
    entry = result["blocked_paths"][0]
    assert "harness" in entry["why"].lower() or "success criteria" in entry["why"].lower()
    # Benchmark category has no "human approval" override — it points at the
    # Add Case UI instead. Locking that contract in so a future edit can't
    # silently promise an override that doesn't exist.
    assert "add case" in entry["why"].lower()


def test_traversal_why_is_hard_boundary_no_override():
    result = evaluate_patch_safety(["../etc/passwd"])
    entry = result["blocked_paths"][0]
    assert "hard safety boundary" in entry["why"].lower()
    # Traversal must NOT advertise a future override — it's a hard rule.
    assert "no override path" in entry["why"].lower()


def test_category_why_helper_returns_other_for_unknown():
    # Public helper falls back to the generic "other" rationale on unknown
    # categories so callers can render something rather than crashing.
    txt = category_why("does-not-exist")
    assert txt == _CATEGORY_WHY["other"]
