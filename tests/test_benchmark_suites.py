import json
from pathlib import Path

import pytest

from benchmarks import run_benchmarks as runner


NEW_DEV_CASES = [
    "python_config_env_mismatch",
    "ts_generic_utility_false_positive",
    "go_validation_command_misleading_success",
    "js_no_patch_user_misread",
]

PHASE_11C_DEV_CASES = [
    "python_wrong_abstraction_honeypot",
    "ts_wrong_file_honeypot",
    "go_validation_gap_honeypot",
]

PHASE_11C_FULL_ONLY_CASES = [
    "python_test_deletion_honeypot",
]

NEW_HELD_OUT_CASES = [
    "python_embedding_provider_switch",
    "rust_multi_file_trait_impl_root_cause",
    "python_forbidden_file_temptation",
    "ts_migration_import_path_case",
]

NEW_HELD_OUT_CASES_11PREP = [
    "cpp_string_view_lifetime_trap",
    "csharp_linq_deferred_execution_trap",
    "rust_path_normalization_security_trap",
    "ts_async_cache_stale_promise_trap",
]

HELD_OUT_CASES = [
    "ts_nested_dispatch_root_cause",
    "python_multifile_root_cause",
    "python_callback_dispatch_ambiguity",
    "python_false_positive_no_patch",
    "go_multifile_root_cause",
    "ts_callback_dispatch_ambiguity",
    "ts_false_positive_no_patch",
    *NEW_HELD_OUT_CASES,
    *NEW_HELD_OUT_CASES_11PREP,
]


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_manifest(root: Path, suite_id: str, case_names: list[str]) -> Path:
    return _write_json(
        root / f"{suite_id}.json",
        {
            "schema_version": 1,
            "suite_id": suite_id,
            "description": f"{suite_id} test suite",
            "case_names": case_names,
        },
    )


def _write_case(root: Path, name: str, *, language: str = "python") -> Path:
    case_dir = root / language / name
    buggy = case_dir / "buggy_repo"
    buggy.mkdir(parents=True)
    (buggy / "main.py").write_text("print('ok')\n", encoding="utf-8")
    return _write_json(
        case_dir / "case.json",
        {
            "name": name,
            "language": language,
            "category": "suite_test",
            "difficulty": "easy",
            "validation_command": "python main.py",
            "expected_changed_files": ["main.py"],
            "forbidden_changed_files": [],
            "prompt": "Fix it.\n\nValidation command: python main.py",
        },
    )


def test_loading_suite_by_name_works(tmp_path, monkeypatch):
    suites_root = tmp_path / "suites"
    _write_manifest(suites_root, "held_out_v1", ["case_b", "case_a"])
    monkeypatch.setattr(runner, "SUITES_ROOT", suites_root)

    manifest = runner.load_suite_manifest("held_out_v1")

    assert manifest["suite_id"] == "held_out_v1"
    assert manifest["case_names"] == ["case_b", "case_a"]
    assert manifest["suite_fingerprint"] == runner.suite_fingerprint(["case_a", "case_b"])


def test_loading_suite_by_path_works(tmp_path):
    path = _write_manifest(tmp_path, "custom_suite", ["case_a"])

    manifest = runner.load_suite_manifest(path)

    assert manifest["suite_id"] == "custom_suite"
    assert manifest["case_names"] == ["case_a"]


def test_missing_suite_gives_friendly_error(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "SUITES_ROOT", tmp_path / "suites")

    with pytest.raises(runner.SuiteManifestError, match="Suite manifest not found"):
        runner.load_suite_manifest("missing_suite")


def test_duplicate_case_names_fail(tmp_path):
    path = _write_manifest(tmp_path, "bad_suite", ["case_a", "case_a"])

    with pytest.raises(runner.SuiteManifestError, match="duplicate case names"):
        runner.load_suite_manifest(path)


def test_missing_case_names_fail(tmp_path):
    cases_root = tmp_path / "cases"
    case_file = _write_case(cases_root, "case_a")
    manifest = {
        "suite_id": "bad_suite",
        "case_names": ["case_a", "case_b"],
        "suite_fingerprint": runner.suite_fingerprint(["case_a", "case_b"]),
    }

    with pytest.raises(runner.SuiteManifestError, match="missing case"):
        runner.filter_cases_by_suite([case_file], manifest)


def test_suite_held_out_runs_only_held_out_cases(tmp_path, monkeypatch):
    cases_root = tmp_path / "cases"
    held_a = _write_case(cases_root, "held_a")
    held_b = _write_case(cases_root, "held_b")
    dev = _write_case(cases_root, "dev_a")
    suites_root = tmp_path / "suites"
    _write_manifest(suites_root, "held_out_v1", ["held_a", "held_b"])

    ran: list[str] = []

    def fake_run_case(case_file: Path, capture: bool):
        case = runner.load_case(case_file)
        ran.append(case["name"])
        return {
            "name": case["name"],
            "success": True,
            "duration_sec": 0.1,
            "language": case["language"],
            "category": case["category"],
            "difficulty": case["difficulty"],
            "fallback_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "unknown_cost_calls": 0,
        }

    monkeypatch.setattr(runner, "SUITES_ROOT", suites_root)
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "discover_cases", lambda root: [held_a, held_b, dev])
    monkeypatch.setattr(runner, "_run_case_with_capture", fake_run_case)
    monkeypatch.setattr(runner, "collect_brain_stamp", lambda repo: {})

    exit_code = runner.main(["--suite", "held_out_v1", "--summary"])

    assert exit_code == 0
    assert ran == ["held_a", "held_b"]
    reports = sorted((tmp_path / ".agent" / "benchmarks").glob("benchmark_report_*.json"))
    report = json.loads(reports[-1].read_text(encoding="utf-8"))
    assert [item["name"] for item in report["results"]] == ["held_a", "held_b"]
    assert report["suite_id"] == "held_out_v1"
    assert report["suite_case_count"] == 2
    assert report["suite_fingerprint"] == runner.suite_fingerprint(["held_a", "held_b"])


def test_case_filter_still_works_after_suite_filtering(tmp_path, monkeypatch):
    cases_root = tmp_path / "cases"
    held_a = _write_case(cases_root, "held_a")
    held_b = _write_case(cases_root, "held_b")
    dev = _write_case(cases_root, "dev_a")
    suites_root = tmp_path / "suites"
    _write_manifest(suites_root, "held_out_v1", ["held_a", "held_b"])
    ran: list[str] = []

    def fake_run_case(case_file: Path, capture: bool):
        case = runner.load_case(case_file)
        ran.append(case["name"])
        return {
            "name": case["name"],
            "success": True,
            "duration_sec": 0.1,
            "language": case["language"],
            "category": case["category"],
            "difficulty": case["difficulty"],
        }

    monkeypatch.setattr(runner, "SUITES_ROOT", suites_root)
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "discover_cases", lambda root: [held_a, held_b, dev])
    monkeypatch.setattr(runner, "_run_case_with_capture", fake_run_case)
    monkeypatch.setattr(runner, "collect_brain_stamp", lambda repo: {})

    exit_code = runner.main(["--suite", "held_out_v1", "--case", "held_b", "--summary"])

    assert exit_code == 0
    assert ran == ["held_b"]


def test_full_discovery_matches_full_suite_manifest():
    cases = runner.discover_cases(Path("benchmarks"))
    discovered_names = sorted(runner.load_case(case_file)["name"] for case_file in cases)
    full_manifest = runner.load_suite_manifest("full_v1")

    assert len(discovered_names) == 54
    assert discovered_names == sorted(full_manifest["case_names"])


def test_held_out_manifest_contains_suggested_cases():
    manifest = runner.load_suite_manifest("held_out_v1")

    assert manifest["case_names"] == HELD_OUT_CASES


# ---------------------------------------------------------------------------
# Phase 12.6 — 40-case expansion tests
# ---------------------------------------------------------------------------

def test_dev_v1_includes_new_dev_cases():
    manifest = runner.load_suite_manifest("dev_v1")
    for name in NEW_DEV_CASES + PHASE_11C_DEV_CASES:
        assert name in manifest["case_names"], f"{name} missing from dev_v1"


def test_full_v1_includes_phase_11c_honeypot_cases():
    manifest = runner.load_suite_manifest("full_v1")
    for name in PHASE_11C_DEV_CASES + PHASE_11C_FULL_ONLY_CASES:
        assert name in manifest["case_names"], f"{name} missing from full_v1"


def test_no_duplicate_case_ids():
    cases = runner.discover_cases(Path("benchmarks"))
    names = [runner.load_case(f)["name"] for f in cases]
    seen: set[str] = set()
    dups = [n for n in names if n in seen or seen.add(n)]  # type: ignore[func-returns-value]
    assert dups == [], f"duplicate case IDs: {dups}"


def test_new_cases_have_expected_or_no_patch_declaration():
    """Every new case must declare expected_changed_files (possibly empty for
    no-patch) and any empty-list no-patch case must have forbidden_changed_files."""
    cases_root = Path("benchmarks") / "cases"
    for name in NEW_DEV_CASES + NEW_HELD_OUT_CASES:
        matches = list(cases_root.rglob(f"{name}/case.json"))
        assert matches, f"case.json not found for {name}"
        case = runner.load_case(matches[0])
        ecf = case.get("expected_changed_files", [])
        fcf = case.get("forbidden_changed_files", [])
        assert isinstance(ecf, list), f"{name}: expected_changed_files must be a list"
        if not ecf:
            assert fcf, f"{name}: no-patch case must declare forbidden_changed_files"


def test_temptation_and_safety_cases_have_forbidden_files():
    cases_root = Path("benchmarks") / "cases"
    for name in ("python_forbidden_file_temptation", "js_no_patch_user_misread"):
        matches = list(cases_root.rglob(f"{name}/case.json"))
        assert matches, f"case.json not found for {name}"
        case = runner.load_case(matches[0])
        assert case.get("forbidden_changed_files"), (
            f"{name}: temptation/safety case must declare forbidden_changed_files"
        )


def test_new_case_validation_commands_do_not_require_network():
    network_markers = (
        "curl", "wget", "http://", "https://",
        "pip install", "npm install", "yarn add",
    )
    cases_root = Path("benchmarks") / "cases"
    for name in NEW_DEV_CASES + NEW_HELD_OUT_CASES:
        matches = list(cases_root.rglob(f"{name}/case.json"))
        assert matches, f"case.json not found for {name}"
        case = runner.load_case(matches[0])
        cmd = case.get("validation_command", "")
        for marker in network_markers:
            assert marker not in cmd, (
                f"{name}: validation_command contains network marker {marker!r}: {cmd!r}"
            )


def test_benchmark_check_finds_zero_structural_errors():
    cases = runner.discover_cases(Path("benchmarks"))
    bad = [runner.check_case(f) for f in cases if not runner.check_case(f)["ok"]]
    assert bad == [], f"structural errors in cases: {bad}"


def test_old_32_case_ids_still_registered():
    old_32 = [
        "cpp_account_interest", "cpp_boundary_check",
        "go_logging_side_effect", "go_missing_import_error",
        "go_multifile_root_cause", "go_wallet_transfer", "go_wrong_file_temptation",
        "html_signup_form_accessibility",
        "js_array_mutation_side_effect", "js_async_missing_await",
        "js_null_user_profile", "js_temperature_converter",
        "python_callback_dispatch_ambiguity", "python_central_node_temptation",
        "python_discount_validation", "python_duplicate_filename_temptation",
        "python_exception_parse_config", "python_false_positive_no_patch",
        "python_multifile_root_cause", "python_mutable_default",
        "python_off_by_one_pagination",
        "python_pandas_iloc_off_by_one_and_decoy_enumerate",
        "python_sql_account_transfer", "python_sql_join_filter",
        "rust_cart_reservation", "rust_result_error_handling",
        "ts_callback_dispatch_ambiguity", "ts_false_positive_no_patch",
        "ts_import_export_mismatch", "ts_inventory_restock",
        "ts_nested_dispatch_root_cause", "ts_optional_property_guard",
    ]
    full_manifest = runner.load_suite_manifest("full_v1")
    registered = set(full_manifest["case_names"])
    missing = [n for n in old_32 if n not in registered]
    assert missing == [], f"old case IDs missing from full_v1: {missing}"
