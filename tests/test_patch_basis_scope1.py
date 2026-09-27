"""PATCH.BASIS.SCOPE.1 measured same-file repair-scope regressions."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from core.control_engine import build_control_prompt
from core.repair_scope import (
    MAX_REPAIR_MEMBERS,
    REPAIR_SCOPE_BUDGET_EXCEEDED,
    REPAIR_SCOPE_COMPLETE,
    REPAIR_SCOPE_CROSS_FILE_REQUIRED,
    REPAIR_SCOPE_INCOMPLETE,
    build_repair_scope,
)
from core.repository_identity import derive_repository_id


JAVA = """public class MainApp {
    void m1() {
        int a = missingOne;
    }

    void m2() {
        int b = missingTwo;
    }

    static void m3() {
        int c = missingThree;
        int d = missingFour;
        int e = missingFive;
    }

    void helper() {
        int safe = 1;
    }

    void unrelated() {
        int safe = 2;
    }
}
"""


def _line(source: str, needle: str) -> int:
    return next(index for index, row in enumerate(source.splitlines(), start=1) if needle in row)


def _write(tmp_path: Path, source: str = JAVA) -> Path:
    (tmp_path / "MainApp.java").write_text(source, encoding="utf-8", newline="")
    return tmp_path


def _control_fingerprint(control: dict) -> str:
    return hashlib.sha256(json.dumps(
        control, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def _receipt(repo: Path, source: str, locations: list[dict], *, control_fingerprint: str = "a" * 64) -> dict:
    return {
        "ran": True,
        "ok": False,
        "category": "build_error",
        "evidence_source": "PREFLIGHT.REQUEST.1",
        "evidence_kind": "compile_evidence",
        "measured": True,
        "receipt_fingerprint": "b" * 64,
        "control_sha256": control_fingerprint,
        "repository_id": derive_repository_id(repo),
        "source_fingerprints": [{
            "path": "MainApp.java",
            "sha256": hashlib.sha256((repo / "MainApp.java").read_bytes()).hexdigest(),
        }],
        "locations": locations,
        "targets": [{"path": "MainApp.java", "errors": len(locations), "warnings": 0}],
    }


def _locations(source: str, *needles: str) -> list[dict]:
    return [
        {
            "kind": "compiler_error",
            "language": "java",
            "file": "MainApp.java",
            "line": _line(source, needle),
            "col": 17,
            "severity": "error",
            "message": f"cannot find symbol: {needle}",
        }
        for needle in needles
    ]


def _scope(repo: Path, receipt: dict, *, control_fingerprint: str = "a" * 64):
    return build_repair_scope(
        repo_path=repo,
        primary_file="MainApp.java",
        primary_symbol="m1",
        primary_kind="function",
        language="java",
        preflight=receipt,
        receipt_control_fingerprint=control_fingerprint,
    )


def test_five_measured_diagnostics_become_three_source_ordered_members(tmp_path):
    repo = _write(tmp_path)
    receipt = _receipt(repo, JAVA, _locations(
        JAVA, "missingOne", "missingTwo", "missingThree", "missingFour", "missingFive",
    ))

    scope = _scope(repo, receipt)

    assert scope.status == REPAIR_SCOPE_COMPLETE
    assert (scope.primary_file, scope.primary_symbol) == ("MainApp.java", "m1")
    assert [member.symbol for member in scope.members] == ["m1", "m2", "m3"]
    assert [len(member.diagnostics) for member in scope.members] == [1, 1, 3]
    assert all(member.source_snippet in JAVA for member in scope.members)
    assert scope.reason == "source_definition_order"


def test_neighbouring_methods_without_measured_errors_never_enter_scope(tmp_path):
    repo = _write(tmp_path)
    scope = _scope(repo, _receipt(repo, JAVA, _locations(JAVA, "missingOne", "missingThree")))

    assert scope.status == REPAIR_SCOPE_COMPLETE
    assert [member.symbol for member in scope.members] == ["m1", "m3"]
    assert {member.symbol for member in scope.members}.isdisjoint({"m2", "helper", "unrelated"})


def test_one_member_control_deduplicates_without_widening(tmp_path):
    repo = _write(tmp_path)
    scope = _scope(repo, _receipt(repo, JAVA, _locations(JAVA, "missingOne")))

    assert scope.status == REPAIR_SCOPE_COMPLETE
    assert [member.symbol for member in scope.members] == ["m1"]


def test_primary_target_must_be_in_the_measured_scope(tmp_path):
    repo = _write(tmp_path)
    scope = _scope(repo, _receipt(repo, JAVA, _locations(JAVA, "missingTwo")))

    assert scope.status == REPAIR_SCOPE_INCOMPLETE
    assert scope.reason == "primary_target_excluded"


def test_cross_file_compiler_error_is_typed_not_silently_widened(tmp_path):
    repo = _write(tmp_path)
    locations = _locations(JAVA, "missingOne") + [{
        "kind": "compiler_error", "language": "java", "file": "Twosum.java",
        "line": 2, "col": 1, "severity": "error", "message": "broken",
    }]
    receipt = _receipt(repo, JAVA, locations)
    receipt["targets"][0]["errors"] = 1

    scope = _scope(repo, receipt)

    assert scope.status == REPAIR_SCOPE_CROSS_FILE_REQUIRED
    assert scope.members == ()


def test_other_failed_target_is_cross_file_even_when_its_location_is_missing(tmp_path):
    repo = _write(tmp_path)
    receipt = _receipt(repo, JAVA, _locations(JAVA, "missingOne"))
    receipt["targets"].append({"path": "Twosum.java", "errors": 1, "warnings": 0})

    scope = _scope(repo, receipt)

    assert (scope.status, scope.reason) == (
        REPAIR_SCOPE_CROSS_FILE_REQUIRED,
        "compiler_errors_in_another_file",
    )


def test_unscoped_file_level_error_fails_closed(tmp_path):
    repo = _write(tmp_path)
    location = _locations(JAVA, "missingOne")[0]
    location["line"] = 1  # the class declaration owns no eligible method

    scope = _scope(repo, _receipt(repo, JAVA, [location]))

    assert (scope.status, scope.reason) == (REPAIR_SCOPE_INCOMPLETE, "unscoped_compiler_diagnostic")


def test_malformed_typed_diagnostic_fails_closed_instead_of_crashing(tmp_path):
    repo = _write(tmp_path)
    location = _locations(JAVA, "missingOne")[0]
    location["line"] = "not-a-line"

    scope = _scope(repo, _receipt(repo, JAVA, [location]))

    assert (scope.status, scope.reason) == (REPAIR_SCOPE_INCOMPLETE, "malformed_typed_diagnostic")


def test_ambiguous_structural_owner_fails_closed(tmp_path, monkeypatch):
    repo = _write(tmp_path)
    from core import repair_scope

    monkeypatch.setattr(repair_scope, "structural_definitions", lambda *_: {
        "available": True,
        "definitions": [
            {"name": "m1", "kind": "function", "start_line": 2, "end_line": 5, "content": "one"},
            {"name": "m1", "kind": "function", "start_line": 2, "end_line": 5, "content": "two"},
        ],
    })
    scope = _scope(repo, _receipt(repo, JAVA, _locations(JAVA, "missingOne")))

    assert (scope.status, scope.reason) == (REPAIR_SCOPE_INCOMPLETE, "ambiguous_compiler_diagnostic")


@pytest.mark.parametrize("change", ["source", "repository", "control"])
def test_receipt_binding_mismatch_fails_closed(tmp_path, change):
    repo = _write(tmp_path)
    receipt = _receipt(repo, JAVA, _locations(JAVA, "missingOne"))
    control = "a" * 64
    if change == "source":
        (repo / "MainApp.java").write_text(JAVA + "// changed\n", encoding="utf-8")
        expected = "source_fingerprint_mismatch"
    elif change == "repository":
        receipt["repository_id"] = "other-" + "0" * 32
        expected = "repository_identity_mismatch"
    else:
        control = "c" * 64
        expected = "control_fingerprint_mismatch"

    scope = _scope(repo, receipt, control_fingerprint=control)

    assert (scope.status, scope.reason) == (REPAIR_SCOPE_INCOMPLETE, expected)


def test_over_budget_scope_is_refused_without_truncation(tmp_path):
    methods = "\n".join(
        f"    void m{index}() {{ int x = missing{index}; }}"
        for index in range(MAX_REPAIR_MEMBERS + 1)
    )
    source = f"public class MainApp {{\n{methods}\n}}\n"
    repo = _write(tmp_path, source)
    locations = _locations(source, *(f"missing{index}" for index in range(MAX_REPAIR_MEMBERS + 1)))
    scope = _scope(repo, _receipt(repo, source, locations))

    assert (scope.status, scope.reason) == (REPAIR_SCOPE_BUDGET_EXCEEDED, "definition_count_budget_exceeded")


def test_diagnostic_message_text_never_selects_a_neighbouring_symbol(tmp_path):
    repo = _write(tmp_path)
    locations = _locations(JAVA, "missingOne")
    locations[0]["message"] = "cannot find symbol: m2 helper unrelated"

    scope = _scope(repo, _receipt(repo, JAVA, locations))

    assert [member.symbol for member in scope.members] == ["m1"]


def test_short_and_long_definition_identifiers_group_by_structural_lines(tmp_path):
    source = JAVA.replace(
        "    void helper() {\n",
        "    void a() { int x = missingShort; }\n\n"
        "    void longDescriptiveRepairMethod() { int x = missingLong; }\n\n"
        "    void helper() {\n",
    )
    repo = _write(tmp_path, source)
    scope = _scope(repo, _receipt(repo, source, _locations(
        source, "missingOne", "missingShort", "missingLong",
    )))

    assert [member.symbol for member in scope.members] == [
        "m1", "a", "longDescriptiveRepairMethod",
    ]


def test_author_prompt_receives_the_complete_multi_member_scope(tmp_path):
    repo = _write(tmp_path)
    control = {
        "repo_path": str(repo),
        "query": "fix compiler errors",
        "top_hypothesis": {"symbol": "MainApp.java::m1", "likely_issue": "compile_error"},
        "hypotheses": [{"symbol": "MainApp.java::m1", "likely_issue": "compile_error"}],
        "related_snippets": [],
        "patch_style": "safe_minimal",
    }
    control["preflight_validation"] = _receipt(
        repo, JAVA, _locations(JAVA, "missingOne", "missingTwo", "missingThree", "missingFour", "missingFive"),
        control_fingerprint=_control_fingerprint(control),
    )

    prompt = build_control_prompt(control, "fix compiler errors", repo_path=str(repo))

    assert "[MEASURED REPAIR SCOPE — authoritative compiler evidence]" in prompt
    assert '"symbol": "m1"' in prompt
    assert '"symbol": "m2"' in prompt
    assert '"symbol": "m3"' in prompt
    assert '"symbol": "helper"' not in prompt
    assert control["patch_intent"]["target_symbol"] == "m1"
    assert control["repair_scope"]["status"] == REPAIR_SCOPE_COMPLETE


def test_scope_builder_has_no_model_or_repository_discovery_calls():
    source = Path("core/repair_scope.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {"walk", "scandir", "listdir", "glob", "rglob", "run_gemini_request"}
    assert not any(
        isinstance(node, ast.Call)
        and (getattr(node.func, "id", None) or getattr(node.func, "attr", None)) in forbidden_calls
        for node in ast.walk(tree)
    )


def test_phase_is_registered_as_a_completed_patch_basis_remediation():
    registry = json.loads(Path("docs/roadmap/phase_registry.json").read_text(encoding="utf-8"))
    phase = next(item for item in registry["phases"] if item["phase_id"] == "PATCH.BASIS.SCOPE.1")

    assert phase["status"] == "complete"
    assert phase["track"] == "CONTROL"
    assert phase["prerequisites"] == ["PATCH.BASIS.TARGET.1"]
    assert {"core/repair_scope.py", "tests/test_patch_basis_scope1.py"} <= set(phase["allowed_files"])
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
