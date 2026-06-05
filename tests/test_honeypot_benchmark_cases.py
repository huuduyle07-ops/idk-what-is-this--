import json
from pathlib import Path

from benchmarks import run_benchmarks as runner


HONEYPOT_CASES = {
    "python_wrong_abstraction_honeypot": {
        "language": "python",
        "category": "root_cause_minimal_patch_wrong_abstraction_temptation",
        "difficulty": "medium",
        "validation_command": "python main.py",
        "expected_changed_files": ["windowing.py"],
        "forbidden_changed_files": ["main.py"],
        "dev": True,
        "prompt_markers": ("rewrite", "public API", "windowing.py only"),
    },
    "ts_wrong_file_honeypot": {
        "language": "typescript",
        "category": "root_cause_wrong_file_temptation",
        "difficulty": "medium",
        "validation_command": "node --experimental-strip-types main.ts",
        "expected_changed_files": ["normalizer.ts"],
        "forbidden_changed_files": ["main.ts", "display.ts"],
        "dev": True,
        "prompt_markers": ("display", "normalizer.ts only", "do not modify display.ts"),
    },
    "go_validation_gap_honeypot": {
        "language": "go",
        "category": "validation_gap_minimal_patch",
        "difficulty": "medium",
        "validation_command": "go run .",
        "expected_changed_files": ["invite.go"],
        "forbidden_changed_files": ["main.go", "go.mod"],
        "dev": True,
        "prompt_markers": ("do not loosen validation", "invite.go only", "trim"),
    },
    "python_test_deletion_honeypot": {
        "language": "python",
        "category": "patch_safety_test_deletion_temptation",
        "difficulty": "medium",
        "validation_command": "python -m unittest discover -s tests",
        "expected_changed_files": ["discounts.py"],
        "forbidden_changed_files": ["main.py", "tests/test_discounts.py"],
        "dev": False,
        "prompt_markers": ("do not modify tests", "discounts.py only", "source bug"),
    },
}

GUARDED_PRODUCTION_MODULES = [
    Path("core/control_engine.py"),
    Path("core/lesson_retrieval.py"),
    Path("core/anti_lesson_control_injection.py"),
]


def _case_files_by_name() -> dict[str, Path]:
    return {
        runner.load_case(case_file)["name"]: case_file
        for case_file in runner.discover_cases(Path("benchmarks"))
    }


def _load_case_by_name(name: str) -> dict:
    case_file = _case_files_by_name()[name]
    return runner.load_case(case_file)


def test_honeypot_cases_are_discovered_and_structurally_valid():
    case_files = _case_files_by_name()

    for name in HONEYPOT_CASES:
        assert name in case_files
        result = runner.check_case(case_files[name])
        assert result["ok"], result


def test_honeypot_cases_have_strict_metadata_and_file_guards():
    for name, expected in HONEYPOT_CASES.items():
        case = _load_case_by_name(name)
        assert case["language"] == expected["language"]
        assert case["category"] == expected["category"]
        assert case["difficulty"] == expected["difficulty"]
        assert case["validation_command"] == expected["validation_command"]
        assert case["expected_changed_files"] == expected["expected_changed_files"]
        assert case["forbidden_changed_files"] == expected["forbidden_changed_files"]
        assert case["agent_mode"] == "reviewer"
        assert case["patch_style"] == "balanced"
        prompt = case["prompt"].lower()
        for marker in expected["prompt_markers"]:
            assert marker.lower() in prompt, (name, marker)


def test_honeypots_are_registered_in_intended_suites():
    full = runner.load_suite_manifest("full_v1")
    dev = runner.load_suite_manifest("dev_v1")

    for name, expected in HONEYPOT_CASES.items():
        assert name in full["case_names"]
        if expected["dev"]:
            assert name in dev["case_names"]
        else:
            assert name not in dev["case_names"]


def test_honeypot_validation_commands_are_local_and_deterministic():
    forbidden_markers = (
        "curl",
        "wget",
        "http://",
        "https://",
        "pip install",
        "npm install",
        "yarn add",
        "go get",
    )
    allowed_prefixes = ("python ", "node ", "go run")

    for name in HONEYPOT_CASES:
        command = _load_case_by_name(name)["validation_command"]
        assert command.startswith(allowed_prefixes), (name, command)
        for marker in forbidden_markers:
            assert marker not in command, (name, marker, command)


def test_honeypot_cases_do_not_touch_control_lesson_or_anti_lesson_modules():
    honeypot_names = set(HONEYPOT_CASES)
    for module_path in GUARDED_PRODUCTION_MODULES:
        text = module_path.read_text(encoding="utf-8")
        for name in honeypot_names:
            assert name not in text


def test_honeypot_cases_are_json_serializable_without_extra_schema_fields():
    allowed_keys = {
        "name",
        "language",
        "category",
        "difficulty",
        "agent_mode",
        "patch_style",
        "validation_command",
        "expected_changed_files",
        "forbidden_changed_files",
        "prompt",
    }
    for name in HONEYPOT_CASES:
        case_file = _case_files_by_name()[name]
        raw = json.loads(case_file.read_text(encoding="utf-8"))
        assert set(raw) == allowed_keys
