"""INDENT.RUNTIME.1 — language context transport & repair boundary.

Production files changed: core/code_dna.py, core/defect_probe.py,
core/paired_defect_probe.py, core/behavioral_matrix.py. This phase does not
fix core/code_dna.py::_classify_indent — see
docs/designs/2026-09-12-language-context-transport-and-repair-boundary.md.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import core.code_dna as code_dna_module
from core.behavioral_expectation import (
    SUBJECT_INDENTATION_STYLE,
    extract_behavioral_expectations,
)
from core.behavioral_matrix import build_behavioral_matrix
from core.code_dna import _classify_indent, compute_dna
from core.defect_probe import (
    EXPECTATION_BASIS_TASK_FACT_ADAPTER,
    INPUT_BASIS_TASK_FACT_ADAPTER,
    PROBE_BASIS_TASK_FACT_ADAPTER,
    _nested_indentation_fixture,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    build_python_function_probe,
    execute_defect_probe,
)
from core.indentation_observation import (
    assess_indentation_observation,
    observe_source_indentation,
)

ROOT = Path(__file__).resolve().parents[1]

T6_QUERY = "2-space indentation is classified as 4-space"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"


def _t6_fact():
    """Reproduced locally rather than cross-imported — matches this repo's
    convention (see tests/test_indent_semantics1.py's own copy)."""
    (fact,), truncated = extract_behavioral_expectations(T6_QUERY)
    assert truncated is False
    assert fact.subject_kind == SUBJECT_INDENTATION_STYLE
    return fact


def _t6_cases():
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=inspect.getsource(_classify_indent),
        candidate_eligible=True,
    )
    assert binding is not None
    fact = _t6_fact()
    contract = build_probe_contract_from_behavior_fact(target=binding, behavior_fact=fact)
    assert contract is not None
    return build_behavioral_matrix(probe_contract=contract, behavior_fact=fact)


PY_NESTED_2 = "def f(x):\n  if x:\n    return 1\n  return 2\n"
PY_NESTED_4 = "def f(x):\n    if x:\n        return 1\n    return 2\n"
#: The shape that actually reproduces the known T6 defect: real 2-space
#: source, deep enough that width>=4 lines outvote the width-2 ones. A
#: shallow 2-space sample (PY_NESTED_2 above) does NOT trigger it — that is
#: exactly why DEFECT.PROBE.LIVE.4/.5 built this depth-variant fixture.
KNOWN_DEFECT_2SPACE = _nested_indentation_fixture(2)
KNOWN_PRESERVED_4SPACE = _nested_indentation_fixture(4)
GO_TAB_FILE = "package main\n\nfunc main() {\n\tif true {\n\t\tprintln(1)\n\t}\n}\n"
JS_4SPACE_FILE = "function f(a) {\n    if (a) {\n        return 1;\n    }\n    return 2;\n}\n"
CPP_4SPACE_FILE = "int main() {\n    if (x) {\n        return 1;\n    }\n    return 0;\n}\n"


# ═══════════════════════════════════════════════════════════════════════════
# Task 1 — signature, compatibility, non-activation
# ═══════════════════════════════════════════════════════════════════════════


def test_language_is_keyword_only_with_a_none_default():
    sig = inspect.signature(_classify_indent)
    assert list(sig.parameters) == ["text", "language"]
    assert sig.parameters["language"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["language"].default is None


def test_the_one_argument_legacy_call_still_works():
    assert _classify_indent(PY_NESTED_4) == "4space"
    assert _classify_indent(PY_NESTED_2) == "2space"
    assert _classify_indent(GO_TAB_FILE) == "tab"


def test_a_positional_language_argument_is_rejected():
    with pytest.raises(TypeError):
        _classify_indent(PY_NESTED_4, "python")  # type: ignore[misc]


@pytest.mark.parametrize("language", [None, "python", "go", "javascript", "unknown"])
def test_the_current_body_ignores_language_and_stays_defective(language):
    """§9/§45 — the known T6 defect must still reproduce under every language."""
    assert _classify_indent(KNOWN_DEFECT_2SPACE, language=language) == "4space"
    assert _classify_indent(KNOWN_PRESERVED_4SPACE, language=language) == "4space"


def test_the_repair_seam_is_imported_but_never_called_by_the_current_body(monkeypatch):
    """§9/§26/§27 — dependency available is not dependency activated."""
    calls: list[str] = []

    def _boom(*args, **kwargs):
        calls.append("called")
        raise AssertionError("the repair seam must not be called by the current body")

    monkeypatch.setattr(code_dna_module, "observe_source_indentation", _boom)
    monkeypatch.setattr(code_dna_module, "assess_indentation_observation", _boom)

    assert _classify_indent(KNOWN_DEFECT_2SPACE, language="python") == "4space"
    assert calls == []


def test_the_seam_names_do_not_leak_the_solution():
    """§13 — architecture, not the answer; no short `indentation` identifier."""
    source = inspect.getsource(code_dna_module)
    tree = ast.parse(source)
    forbidden = {
        "structural_indent_fix",
        "correct_indent_classifier",
        "t6_solution",
        "gcd_indent_unit",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    assert names.isdisjoint(forbidden)


# ═══════════════════════════════════════════════════════════════════════════
# Task 2 — compute_dna language transport
# ═══════════════════════════════════════════════════════════════════════════


def _write_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_language_for_suffix_reuses_the_language_map_not_a_second_one():
    assert code_dna_module._language_for_suffix(".py") == "python"
    assert code_dna_module._language_for_suffix(".go") == "go"
    assert code_dna_module._language_for_suffix(".PY") == "python"
    assert code_dna_module._language_for_suffix(".zig") is None


@pytest.mark.parametrize(
    "filename, content, expected_indent",
    [
        ("a.py", KNOWN_PRESERVED_4SPACE, "4space"),
        # §16/§20/§45 — the known defect: a real 2-space Python file is still
        # misreported as 4space after this phase.
        ("a.py", KNOWN_DEFECT_2SPACE, "4space"),
        ("a.go", GO_TAB_FILE, "tab"),
        ("a.js", JS_4SPACE_FILE, "4space"),
        ("a.cpp", CPP_4SPACE_FILE, "4space"),
    ],
)
def test_compute_dna_repo_level_indent_is_behaviorally_unchanged(
    tmp_path, filename, content, expected_indent
):
    repo = _write_repo(tmp_path, {filename: content})
    dna = compute_dna(str(repo))
    assert dna["indent"] == expected_indent


def test_compute_dna_passes_each_files_own_language_not_a_repo_majority(
    tmp_path, monkeypatch
):
    """§7/§16 — language travels with the file compute_dna is currently reading."""
    seen: list[str | None] = []
    real = code_dna_module._classify_indent

    def spy(text, *, language=None):
        seen.append(language)
        return real(text, language=language)

    monkeypatch.setattr(code_dna_module, "_classify_indent", spy)
    repo = _write_repo(tmp_path, {"a.py": KNOWN_PRESERVED_4SPACE, "b.go": GO_TAB_FILE})
    compute_dna(str(repo))
    assert set(seen) == {"python", "go"}


def test_a_go_files_language_is_go_even_though_the_classifier_lives_in_a_py_file(
    tmp_path, monkeypatch
):
    """§15/§18 — no target-file language inference: core/code_dna.py is a .py
    file, but that must never make classified Go text become "python"."""
    seen: list[str | None] = []
    real = code_dna_module._classify_indent

    def spy(text, *, language=None):
        seen.append(language)
        return real(text, language=language)

    monkeypatch.setattr(code_dna_module, "_classify_indent", spy)
    repo = _write_repo(tmp_path, {"main.go": GO_TAB_FILE})
    compute_dna(str(repo))
    assert seen == ["go"]
    assert "python" not in seen


# ═══════════════════════════════════════════════════════════════════════════
# Task 8 — probe fingerprinting and the real worker (§37/§38)
# ═══════════════════════════════════════════════════════════════════════════


def _t6_binding():
    return build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=inspect.getsource(_classify_indent),
        candidate_eligible=True,
    )


def test_probe_fingerprint_differs_by_declared_language_alone():
    """§38 — two probes with identical text but different declared language
    must not share a fingerprint. Reuses the existing fingerprint semantics
    (identity_payload already echoes structured_input); no new primitive."""

    binding = _t6_binding()
    common = dict(
        target=binding,
        args=("x\n  y\n",),
        expected="2space",
        probe_basis=PROBE_BASIS_TASK_FACT_ADAPTER,
        input_basis=INPUT_BASIS_TASK_FACT_ADAPTER,
        expected_behavior_basis=EXPECTATION_BASIS_TASK_FACT_ADAPTER,
        provenance_reference="test",
    )
    py_contract = build_python_function_probe(**common, kwargs={"language": "python"})
    go_contract = build_python_function_probe(**common, kwargs={"language": "go"})

    assert py_contract.fingerprint != go_contract.fingerprint
    assert py_contract.structured_input["kwargs"] != go_contract.structured_input["kwargs"]


def test_the_worker_actually_forwards_kwargs_language_to_the_real_target():
    """§37 — direct proof, not inference: execute_defect_probe end to end,
    through the real static worker and its existing generic kwargs forwarding
    (core/defect_probe_worker.py::_run_python_function already does
    ``function(*args, **kwargs)`` -- unmodified by this phase)."""

    contract = build_python_function_probe(
        target=_t6_binding(),
        args=(KNOWN_DEFECT_2SPACE,),
        expected="2space",
        probe_basis=PROBE_BASIS_TASK_FACT_ADAPTER,
        input_basis=INPUT_BASIS_TASK_FACT_ADAPTER,
        expected_behavior_basis=EXPECTATION_BASIS_TASK_FACT_ADAPTER,
        provenance_reference="test",
        kwargs={"language": "python"},
    )
    receipt = execute_defect_probe(contract, repo_path=ROOT)

    # The unfixed body still says 4space even though it received language="python".
    assert receipt.observed == "4space"
    assert receipt.attempted is True


# ═══════════════════════════════════════════════════════════════════════════
# Task 9 — expressibility proof vs. the real safe_minimal gate (§21-25/§44)
# ═══════════════════════════════════════════════════════════════════════════

#: The shipped `_classify_indent` body, byte-identical to what shipped before
#: this phase (only the signature line above it changed). Reproduced locally
#: rather than cross-imported from tests/test_indent_semantics1.py, matching
#: this repo's convention of small per-file fixture constants.
T6_CLASSIFIER_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

#: §21 — test-only. Never shipped into _classify_indent. Uses only names the
#: repair seam already makes source-visible at module scope in
#: core/code_dna.py, so it faces the same signature and the same source the
#: real target function has -- the same novelty gate a real authored patch
#: to just the body would face.
RUNTIME1_TEST_ONLY_CORRECT_BODY = (
    "    return assess_indentation_observation(\n"
    "        observe_source_indentation(text, language=language)\n"
    "    ).value\n"
)


def test_the_shipped_body_constant_matches_the_live_source():
    assert T6_CLASSIFIER_BODY in inspect.getsource(_classify_indent)


def test_the_test_only_candidate_expresses_all_eight_cases_correctly():
    """§21 — the oracle's own semantics, called directly, close every case
    the real production matrix now declares a language for."""

    def candidate(text, *, language=None):
        return assess_indentation_observation(
            observe_source_indentation(text, language=language)
        ).value

    cases = _t6_cases()
    assert len(cases) == 8
    for case in cases:
        (text,) = case.contract.structured_input["args"]
        lang = case.contract.structured_input["kwargs"]["language"]
        assert candidate(text, language=lang) == case.expected, case.case_id


def _safe_minimal_admits(target: str, patched: str) -> tuple[bool, dict]:
    """The real safe_minimal gate on a throwaway stand-in state (no writes).
    Reproduced locally, matching tests/test_indent_semantics1.py's own
    ``_safe_minimal_admits`` helper rather than cross-imported."""

    import contextlib
    import io
    from types import SimpleNamespace

    import patching.patch_gates as gates

    state = SimpleNamespace(
        task_info={"patch_style": "safe_minimal"},
        patch_style="safe_minimal",
        language="python",
        json_block={
            "summary": "",
            "issues": [],
            "patch_candidate": {
                "file": T6_TARGET_FILE,
                "relative_path": T6_TARGET_FILE,
                "target_node_name": T6_TARGET_SYMBOL,
                "target_node_kind": "function",
                "target_snippet": target,
                "patched_snippet": patched,
            },
            "confidence": 0.9,
            "needs_escalation": False,
        },
        final_answer="",
        human_answer="",
    )
    with contextlib.redirect_stdout(io.StringIO()):
        gates._enforce_safe_minimal(state)
    return isinstance(state.json_block.get("patch_candidate"), dict), state.json_block


def test_real_safe_minimal_verdict_on_the_test_only_correct_candidate():
    """§21-25/§44 — the phase's primary evidence, measured against the real
    gate rather than assumed. REJECTED, for novel_external_reference: even
    though the repair seam makes assess_indentation_observation and
    observe_source_indentation source-visible at module scope, safe_minimal's
    allowed-identifier set is built only from target_snippet -- the function
    BODY text -- which never included those two names, so they read as
    unresolved regardless of the module-level import. `.value` (attribute
    access on the returned assessment) is separately flagged as an external
    surface. safe_minimal itself is unmodified by this phase (§22/§36)."""

    admitted, block = _safe_minimal_admits(
        T6_CLASSIFIER_BODY.rstrip("\n"), RUNTIME1_TEST_ONLY_CORRECT_BODY.rstrip("\n")
    )

    assert admitted is False
    assert block["candidate_novelty_reason"] == "novel_external_reference"
    assert set(block["candidate_novelty_blocking_reasons"]) == {
        "novel_external_reference",
        "unresolved_novel_identifier",
    }
    assert set(block["candidate_novelty_novel_identifiers"]) == {
        "assess_indentation_observation",
        "observe_source_indentation",
        "language",
        "value",
    }


def test_the_verdict_depends_on_whether_target_snippet_includes_the_signature():
    """§21-25 — this repo tests candidates two different ways: this suite and
    tests/test_indent_semantics1.py pass safe_minimal a body-only
    target_snippet; tests/test_patch_minimal_novelty_live.py's own
    T6_TARGET/_with_body convention passes the *full* function source
    (signature included). Both are exercised here because they give a
    different answer for one specific identifier.

    With the signature included, `language` already appears in
    target_snippet's own text (INDENT.RUNTIME.1 put it there), so it is no
    longer novel -- only the two repair-seam names and `.value` are. The
    overall verdict is unchanged (still rejected, still
    novel_external_reference): this narrows *why*, it does not flip the
    T6_REPAIR_EXPRESSIBLE_UNDER_CURRENT_POLICY answer.
    """

    full_target = inspect.getsource(_classify_indent)
    full_patched = full_target.replace(
        T6_CLASSIFIER_BODY, RUNTIME1_TEST_ONLY_CORRECT_BODY
    )
    assert full_patched != full_target  # the replace actually matched

    admitted, block = _safe_minimal_admits(
        full_target.rstrip("\n"), full_patched.rstrip("\n")
    )

    assert admitted is False
    assert block["candidate_novelty_reason"] == "novel_external_reference"
    assert "language" not in block["candidate_novelty_novel_identifiers"]
    assert set(block["candidate_novelty_novel_identifiers"]) == {
        "assess_indentation_observation",
        "observe_source_indentation",
        "value",
    }


def test_even_a_bare_reference_to_the_new_language_parameter_alone_is_rejected():
    """§21-24 — isolates the blocker from the repair seam, under the
    body-only target_snippet convention this suite and
    tests/test_indent_semantics1.py use (see the test above for the
    full-source convention, where this is not the case). Under body-only,
    `language` -- the function's own parameter, added by this very phase's
    signature change -- is itself unresolved to the gate whenever a patch
    merely uses it, independent of the repair seam existing at all. Whether
    that matters for a real authored candidate depends entirely on which
    snippet granularity CONTROL.LOCALIZE actually hands the author for this
    target; this phase does not settle that, only measures both."""

    admitted, block = _safe_minimal_admits(
        T6_CLASSIFIER_BODY.rstrip("\n"),
        ('    if language == "python":\n        return None\n' + T6_CLASSIFIER_BODY).rstrip(
            "\n"
        ),
    )

    assert admitted is False
    assert block["candidate_novelty_reason"] == "unresolved_novel_identifier"
    assert block["candidate_novelty_novel_identifiers"] == ["language"]


def test_every_case_contract_kwargs_language_matches_the_cases_declared_language():
    cases = _t6_cases()
    assert len(cases) == 8
    for case in cases:
        assert case.contract.structured_input["kwargs"] == {
            "language": case.input_language
        }, case.case_id


def test_the_matrix_still_declares_exactly_the_same_eight_languages():
    """§19 — no new case, no role/provenance change; only kwargs is new."""
    cases = _t6_cases()
    assert [case.input_language for case in cases] == [
        "python", "python", "python", "python", "python", "python", "python", "go",
    ]
