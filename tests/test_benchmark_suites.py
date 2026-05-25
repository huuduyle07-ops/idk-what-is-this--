import json
from pathlib import Path

import pytest

from benchmarks import run_benchmarks as runner


HELD_OUT_CASES = [
    "ts_nested_dispatch_root_cause",
    "python_multifile_root_cause",
    "python_callback_dispatch_ambiguity",
    "python_false_positive_no_patch",
    "go_multifile_root_cause",
    "ts_callback_dispatch_ambiguity",
    "ts_false_positive_no_patch",
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

    assert len(discovered_names) == 31
    assert discovered_names == sorted(full_manifest["case_names"])


def test_held_out_manifest_contains_suggested_cases():
    manifest = runner.load_suite_manifest("held_out_v1")

    assert manifest["case_names"] == HELD_OUT_CASES
