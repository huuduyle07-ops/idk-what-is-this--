"""PATCH.AUTHOR.LIVE.2 — self-contained authoring contract parity.

Round 9 produced the measurement this phase answers.  The single
verification-guided revision call ran, the model materially improved the
implementation strategy, and the result was discarded before it reached
candidate normalization because its envelope was::

    {"target_snippet": "...", "replacement_snippet": "..."}

The parser refused it as ``revision_output_carried_no_patch_candidate``, and
that refusal was correct.  Comparing the two prompts established why: the
initial-draft prompt carried ``patch_candidate``, ``patched_snippet``, the
operation shapes, the output-only rule and the ``safe_minimal`` identifier
constraints; the revision prompt carried none of them and said only "return the
normal patch-candidate JSON schema and nothing else".  The provider call is
stateless, so "the normal schema" named a protocol that call had never seen.

This suite pins the fix and, just as hard, pins what the fix is *not*:

* the parser stays strict — the captured Round-9 response is still invalid, and
  ``replacement_snippet``/``replacement``/``new_snippet``/``diff_text``/a bare
  object/a missing wrapper are all still refused;
* ``PATCH.MINIMAL`` stays authoritative — the Round-9 substance, correctly
  enveloped, now parses and is then rejected for its novel ``lstrip`` member,
  which is this phase succeeding rather than failing;
* the contract carries no solution advice, the revision budget is still one,
  and no authority, retrieval, traversal or model call is widened.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import time
from pathlib import Path
from typing import Any

import pytest

from _harness_maintenance import before_harness_remediation

from core import control_engine
from core import patch_authoring_contract as contract_module
from core import pipeline
from core import prompter
from core.agent_state import AgentState
from core.behavioral_expectation import extract_behavioral_expectations
from core.behavioral_matrix import (
    CANDIDATE_FIXED,
    CANDIDATE_PRESERVED,
    MATRIX_FIXED_AND_PRESERVED,
)
from core.candidate_revision import (
    MAX_REVISION_CALLS_PER_RUN,
    OUTCOME_REVISED_CANDIDATE_REJECTED,
    OUTCOME_REVISED_CANDIDATE_VERIFIED,
    OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE,
    OUTPUT_NO_PATCHED_SNIPPET,
    OUTPUT_NO_PATCH_CANDIDATE,
    PROMPT_TEMPLATE_CONSTANTS,
    assess_candidate_revision,
    build_revision_prompt,
    candidate_revision_guardrails,
    parse_revised_candidate,
)
from core.candidate_verification import REJECTED, VERIFIED
from core.code_dna import _classify_indent
from core.defect_probe import (
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    execute_defect_probe,
)
from core.local_binding_novelty import REASON_NOVEL_EXTERNAL_REFERENCE
from core.patch_authoring_contract import (
    AUTHORING_CONTRACT_VERSION,
    PATCH_RESPONSE_SCHEMA,
    PatchAuthoringContract,
    patch_authoring_contract_guardrails,
    render_patch_authoring_contract,
)
from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT
from core.phase_registry import load_phase_registry
from graph.schema import build_graph
from patching import patch_gates


ROOT = Path(__file__).resolve().parents[1]
PHASE = "PATCH.AUTHOR.LIVE.2"

T6_QUERY = "2-space indentation is classified as 4-space"
T6_TASK = f"Fix this bug: {T6_QUERY}"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"
T6_TARGET = inspect.getsource(_classify_indent)

T6_BODY = (
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
assert T6_BODY in T6_TARGET, "the shipped _classify_indent body moved"


def _with_body(body: str) -> str:
    return T6_TARGET.replace(T6_BODY, body)


#: The behaviorally dead guard: byte-changing, admitted by the novelty rule and
#: behaviorally identical to the baseline.  PATCH.AUTHOR.LIVE.1's eligible
#: Candidate0, reused unchanged so this phase measures the same starting point.
DEAD_GUARD_BODY = T6_BODY.replace(
    '        elif line.startswith("  "):\n',
    '        elif line.startswith("  ") and not line.startswith("    "):\n',
)
assert DEAD_GUARD_BODY != T6_BODY

#: §27 — the Round-9 Candidate1 implementation substance, as DEFECT.PROBE.LIVE.5
#: reconstructed it from the captured provider response.  It is carried here to
#: be re-enveloped, not to be endorsed: it uses the novel member ``lstrip``.
ROUND9_SUBSTANCE_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    "        stripped = line.lstrip('\\n\\r')\n"
    '        if not stripped or stripped[0] not in " \\t":\n'
    "            continue\n"
    '        indent = len(stripped) - len(stripped.lstrip(" \\t"))\n'
    '        if "\\t" in stripped[:indent]:\n'
    '            counts["tab"] += 1\n'
    "        elif indent % 4 == 0:\n"
    '            counts["4space"] += 1\n'
    "        elif indent % 2 == 0:\n"
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

#: §13/§28 — the already-established local-only implementation form: three
#: bounded local bindings, no novel member, no import, within the changed-line
#: cap, and correct under all five LIVE.5 cases.  Test-only; it is never applied
#: to the shipped ``_classify_indent``.  INDENT.SEMANTICS.1's eight-case matrix
#: rejects it on its two Python structural cases, so the proof that needs it
#: verified declares the five-case oracle.
CORRECT_LOCAL_ONLY_BODY = (
    "    counts = Counter()\n"
    "    unit = 0\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    "            continue\n"
    '        counts["space"] += 1\n'
    "        width = 0\n"
    "        for ch in line:\n"
    '            if ch != " ":\n'
    "                break\n"
    "            width += 1\n"
    "        while width:\n"
    "            unit, width = width, unit % width\n"
    '    if unit and counts["space"] >= counts["tab"]:\n'
    '        return "2space" if unit <= 2 else "4space"\n'
    '    return "tab" if counts["tab"] else None\n'
)

#: §25/§26 — the captured Round-9 envelope.  Two keys, no wrapper, and the
#: replacement bytes under a name the runtime does not read.
ROUND9_RAW_RESPONSE = json.dumps(
    {
        "target_snippet": T6_TARGET,
        "replacement_snippet": _with_body(ROUND9_SUBSTANCE_BODY),
    }
)


def _contract(style: str = "safe_minimal") -> PatchAuthoringContract:
    return render_patch_authoring_contract(style=style, source_snippet=T6_TARGET)


# ═══════════════════════════════════════════════════════════════════════════
# §2/§3/§6 — the shared contract, and what it must contain
# ═══════════════════════════════════════════════════════════════════════════


def test_the_contract_names_the_wrapper_and_both_snippet_fields():
    """§6/§7 — a stateless reader can build the envelope from this text alone."""

    text = _contract().text
    for field in (
        '"patch_candidate"',
        '"target_snippet"',
        '"patched_snippet"',
        '"relative_path"',
        '"file"',
        '"target_node_name"',
        '"target_node_kind"',
    ):
        assert field in text, field


def test_the_contract_specifies_the_operation_shapes():
    """§4 — operation types and their required fields, not just the candidate."""

    text = _contract().text
    for token in ('"op"', '"create_file"', '"replace_snippet"', '"content"', '"patch_plan"'):
        assert token in text, token


def test_the_contract_carries_the_output_only_requirement():
    """§4 — one shape, and nothing around it."""

    text = _contract().text
    assert "Output EITHER patch_candidate OR patch_plan, never both." in text
    assert "Use patch_candidate ONLY. Do NOT emit patch_plan." in text
    assert "Return JSON:" in text


def test_the_contract_carries_the_safe_minimal_identifier_constraints():
    """§9/§22 — the constraints the initial author already had, reused."""

    text = _contract().text
    assert "SAFE_MINIMAL — HARD CONSTRAINTS:" in text
    assert "authoritative baseline bindings" in text
    assert "FORBIDDEN in patched_snippet:" in text
    assert "New imports, new helper functions, new type declarations." in text
    # LIVE.3 projects names through policy-owned scope, outside the wire contract.
    assert "permitted bounded candidate-local bindings" in text


def test_the_identifier_list_comes_from_the_supplied_source_and_nothing_else():
    """§22/§23 — no repository is rescanned to build the contract."""

    narrow = render_patch_authoring_contract(
        style="safe_minimal", source_snippet="def f(alpha):\n    return alpha\n"
    )
    assert "authoritative baseline bindings" in narrow.text
    assert "'counts'" not in narrow.text
    assert "'most_common'" not in narrow.text

    tree = ast.parse((ROOT / "core" / "patch_authoring_contract.py").read_text(encoding="utf-8"))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (called & {"open", "exec", "eval", "compile", "input", "__import__"})
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    assert modules <= {"__future__", "dataclasses", "hashlib", "re"}


@pytest.mark.parametrize("style", ["safe_minimal", "balanced", "vibe"])
def test_the_contract_renders_deterministically(style):
    """§21 — same inputs, same bytes.  No clock, no set ordering, no model."""

    first = render_patch_authoring_contract(style=style, source_snippet=T6_TARGET)
    for _ in range(25):
        again = render_patch_authoring_contract(style=style, source_snippet=T6_TARGET)
        assert again.text == first.text
        assert again.fingerprint == first.fingerprint
    assert first.version == AUTHORING_CONTRACT_VERSION
    assert len(first.fingerprint) == 64
    assert first.text == "\n\n".join(part for part in first.sections if part.strip())


def test_style_changes_contract_and_source_identity_belongs_to_scope():
    """§5 — the fingerprint identifies contract content, and only that."""

    base = _contract()
    assert base.fingerprint != _contract("balanced").fingerprint
    assert base.fingerprint != _contract("vibe").fingerprint
    assert (
        base.fingerprint
        == render_patch_authoring_contract(
            style="safe_minimal", source_snippet="def other():\n    return 1\n"
        ).fingerprint
    )


#: §11's own list, and the spellings the correct answer happens to use.
FORBIDDEN_TECHNIQUE_WORDS = (
    "gcd",
    "lstrip",
    "strip",
    "greatest common divisor",
    "indentation unit",
    "leading space",
    "count the",
    "branch order",
    "reorder",
    "divisor",
    "modulo",
    "loop over",
    "minimum indentation",
    "width counting",
)


@pytest.mark.parametrize("style", ["safe_minimal", "balanced", "vibe"])
def test_the_contract_contains_no_task_specific_solution_advice(style):
    """§11 — the contract is about the wire, never about the answer."""

    contract = render_patch_authoring_contract(style=style, source_snippet=T6_TARGET)
    lowered = contract.text.lower()
    for word in FORBIDDEN_TECHNIQUE_WORDS:
        assert word not in lowered, word

    # No task text, no shipped body, no candidate body — the contract is about
    # the wire and never about this subject.
    for leak in (T6_QUERY, T6_TASK, T6_BODY, CORRECT_LOCAL_ONLY_BODY, ROUND9_SUBSTANCE_BODY):
        assert leak not in contract.text
    assert "2space" not in lowered

    # The one place a T6 name may appear is the identifier list, which reflects
    # the bounded source back at the author exactly as the initial draft does.
    # It is a name, not a technique, and it is the same list either author gets.
    for line in contract.text.splitlines():
        if T6_TARGET_SYMBOL in line:
            assert line.startswith("Identifiers visible in source:"), line


def test_the_contract_never_asks_for_hidden_reasoning():
    """§9 of LIVE.1, still true once the contract joined the request."""

    lowered = _contract().text.lower()
    for phrase in ("chain of thought", "think step", "explain why", "critique", "reflect"):
        assert phrase not in lowered


def test_the_guardrails_say_what_this_phase_refuses():
    guardrails = patch_authoring_contract_guardrails()

    assert guardrails["initial_draft_and_revision_share_one_contract"] is True
    assert guardrails["contract_rendering_is_deterministic"] is True
    for key in (
        "contract_performs_retrieval",
        "contract_traverses_the_repository",
        "contract_makes_model_calls",
        "contract_makes_network_calls",
        "contract_loosens_the_candidate_parser",
        "contract_aliases_replacement_snippet",
        "contract_repairs_provider_output",
        "contract_replaces_safe_minimal",
        "contract_grants_execution_authority",
        "contract_contains_task_specific_solution_advice",
    ):
        assert guardrails[key] is False, key

    revision = candidate_revision_guardrails()
    assert revision["revision_receives_the_initial_authoring_contract"] is True
    assert revision["revision_and_initial_draft_share_one_contract"] is True
    assert revision["revision_prompt_is_self_contained_about_the_wire_contract"] is True
    for key in (
        "revision_contract_supplies_implementation_hints",
        "revision_output_parser_accepts_field_aliases",
        "malformed_revision_output_is_repaired",
        "prompt_compliance_can_substitute_for_a_deterministic_gate",
    ):
        assert revision[key] is False, key
    assert revision["max_revision_calls_per_run"] == MAX_REVISION_CALLS_PER_RUN == 1


# ═══════════════════════════════════════════════════════════════════════════
# §1/§29/§30/§31 — parity, and the drift guards
# ═══════════════════════════════════════════════════════════════════════════


def _t6_control_result() -> dict[str, Any]:
    return {
        "repo_path": str(ROOT),
        "patch_style": "safe_minimal",
        "live_route": {"selected_workflow": "defect_repair_patch"},
        "top_hypothesis": {
            "symbol": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
            "likely_issue": "misclassification",
            "localization_score": 12.0,
            "language": "python",
            "reasons": ["identifier token match"],
        },
        "patch_intent": {
            "file": T6_TARGET_FILE,
            "relative_path": T6_TARGET_FILE,
            "target_file": T6_TARGET_FILE,
            "target_symbol": T6_TARGET_SYMBOL,
            "target_node_name": T6_TARGET_SYMBOL,
            "target_node_kind": "function",
            "language": "python",
            "source_snippet": T6_TARGET,
        },
        "patch_candidate_state": {
            "defect_established": True,
            "defect_grounded": True,
            "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
            "eligible_for_patch_safety_handoff": True,
        },
        "preflight_validation": {"outcome": "failed"},
        "related_snippets": [],
        "scout": {"request_type": "bug_fix"},
        "phantom_limb": {"findings": []},
        "code_dna_prompt": "REPO STYLE: 4-space indent. Match this in patched_snippet.",
    }


def _draft_prompt(monkeypatch, control_result: dict[str, Any]) -> str:
    """The initial-draft prompt for a control result that reached handoff.

    ``refresh_control_safety`` recomputes ``patch_candidate_state`` from real
    grounding evidence; neutralising it lets this hand-built state through to
    the normal localized bug-fix branch, which is the branch the live T6 draft
    call takes and the branch whose contract this phase shares.
    """

    monkeypatch.setattr(control_engine, "refresh_control_safety", lambda result: result)
    return control_engine.build_control_prompt(
        dict(control_result), T6_TASK, repo_path=str(ROOT)
    )


def test_the_initial_draft_prompt_carries_every_contract_section(monkeypatch):
    """§29 — the shared material appears verbatim in the draft request."""

    control_result = _t6_control_result()
    contract = control_engine.authoring_contract_for_control_result(control_result)
    prompt = _draft_prompt(monkeypatch, control_result)

    for section in contract.sections:
        assert section.strip()
        assert section in prompt


def test_the_revision_prompt_carries_the_whole_contract():
    """§14 — the revision request answers the wire questions on its own."""

    contract = control_engine.authoring_contract_for_control_result(_t6_control_result())
    prompt = build_revision_prompt(_revision_evidence(), contract)

    assert contract.text in prompt
    for question in (
        '"patch_candidate"',
        '"target_snippet"',
        '"patched_snippet"',
        "Return JSON:",
        "SAFE_MINIMAL — HARD CONSTRAINTS:",
    ):
        assert question in prompt, question
    # And it says so in its own words too, so the shape is not only implied.
    assert "PATCH CANDIDATE CONTRACT" in prompt
    assert "no other spelling is read" in prompt


def test_both_authoring_paths_render_the_same_contract_fingerprint(monkeypatch):
    """§29/§30 — byte parity of the shared component, for the same context."""

    control_result = _t6_control_result()
    draft_contract = control_engine.authoring_contract_for_control_result(control_result)
    revision_contract = control_engine.authoring_contract_for_control_result(
        dict(control_result)
    )

    assert draft_contract.text == revision_contract.text
    assert draft_contract.fingerprint == revision_contract.fingerprint
    assert draft_contract.version == revision_contract.version

    # And the whole prompts are deliberately NOT equal: the two calls carry
    # different evidence, and forcing them identical would mean sending the
    # revision the first draft's framing instead of its counterexamples.
    draft = _draft_prompt(monkeypatch, control_result)
    revision = build_revision_prompt(_revision_evidence(), revision_contract)
    assert draft != revision
    assert "REVISION REQUEST" not in draft
    assert "[CONTROL]" not in revision


def test_changing_the_authoritative_contract_moves_both_prompts(monkeypatch):
    """§30 — the drift guard: one producer, so one edit reaches both callers."""

    sentinel = "SENTINEL-CONTRACT-EDIT-9f2a"

    def moved(style: str) -> str:
        return f"{sentinel} for {style}"

    monkeypatch.setattr(contract_module, "patch_output_format_block", moved)

    control_result = _t6_control_result()
    contract = control_engine.authoring_contract_for_control_result(control_result)
    assert sentinel in contract.text

    draft = _draft_prompt(monkeypatch, control_result)
    revision = build_revision_prompt(_revision_evidence(), contract)
    assert sentinel in draft, "the initial draft stopped using the shared renderer"
    assert sentinel in revision, "the revision stopped using the shared renderer"


def test_the_safe_minimal_constraints_have_one_producer(monkeypatch):
    """§31 — the identifier/FORBIDDEN material cannot drift between the two."""

    sentinel = "SENTINEL-SAFE-MINIMAL-4c71"
    monkeypatch.setattr(
        contract_module, "safe_minimal_forbidden_block", lambda source: sentinel
    )

    control_result = _t6_control_result()
    contract = control_engine.authoring_contract_for_control_result(control_result)
    assert contract.candidate_language_block == sentinel

    assert sentinel in _draft_prompt(monkeypatch, control_result)
    assert sentinel in build_revision_prompt(_revision_evidence(), contract)


def test_there_is_exactly_one_definition_of_the_candidate_schema():
    """§2 — extracted, not copy-pasted.  Two definitions could disagree."""

    # The response envelope is assigned in exactly one production module.
    definitions = []
    for path in sorted((ROOT / "core").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name)
                and target.id == "PATCH_RESPONSE_SCHEMA"
                for target in node.targets
            ):
                definitions.append(path.name)
    assert definitions == ["patch_authoring_contract.py"], definitions
    assert prompter.PATCH_RESPONSE_SCHEMA is PATCH_RESPONSE_SCHEMA

    # The two control_engine entry points are delegations, holding no contract
    # text of their own; a re-inlined copy would show up as a string literal.
    tree = ast.parse((ROOT / "core" / "control_engine.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name not in {"_safe_minimal_forbidden_block", "_patch_output_format_block"}:
            continue
        literals = [
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        ]
        assert literals == [ast.get_docstring(node, clean=False)], node.name

    # And the revision module describes no schema of its own.
    revision_source = (ROOT / "core" / "candidate_revision.py").read_text(encoding="utf-8")
    for literal in (
        '"patch_candidate": {',
        '"patched_snippet": "..."',
        "FORBIDDEN in patched_snippet",
        "Return JSON:",
    ):
        assert literal not in revision_source, literal


def test_the_contract_heading_is_a_declared_template_constant():
    """LIVE.1's closed-template rule still holds with the contract in place."""

    headings = [
        c for c in PROMPT_TEMPLATE_CONSTANTS if c.startswith("PATCH CANDIDATE CONTRACT")
    ]
    assert len(headings) == 1
    lowered = headings[0].lower()
    for word in FORBIDDEN_TECHNIQUE_WORDS:
        assert word not in lowered, word


# ═══════════════════════════════════════════════════════════════════════════
# §8/§25/§26 — the parser did not move
# ═══════════════════════════════════════════════════════════════════════════


def _revision_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "task_route": {"selected_workflow": "defect_repair_patch"},
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "payload": {
            "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
            "candidate_effect_status": "mutating",
            "candidate_probe_apply_status": "applied",
            "candidate_fingerprint": "f" * 64,
            "probe_fingerprint": "b" * 64,
            "behavioral_matrix_status": "still_reproduced",
            "behavioral_matrix": {"candidate_fingerprint": "f" * 64},
            "behavioral_matrix_cases": [
                {
                    "case_id": "indentation_style.primary.2space",
                    "role": "primary_defect",
                    "provenance": "explicit_user_fact",
                    "expected": "2space",
                    "candidate_observed": "4space",
                    "candidate_status": "still_reproduced",
                },
                {
                    "case_id": "indentation_style.preserve.4space",
                    "role": "preservation",
                    "provenance": "system_derived_behavior_preservation",
                    "expected": "4space",
                    "candidate_observed": "4space",
                    "candidate_status": "preserved",
                },
            ],
            "candidate_verification_status": "rejected",
            "candidate_verification_rejection_reasons": ["primary_defect_not_closed"],
            "candidate_verification_candidate_fingerprint": "f" * 64,
        },
        "patch_safety": {"ok": True},
        "pre_probe": {"probe_result": "reproduced"},
        "candidate_fingerprint": "f" * 64,
        "rejected_target_snippet": T6_TARGET,
        "rejected_patched_snippet": _with_body(DEAD_GUARD_BODY),
        "target_file": T6_TARGET_FILE,
        "target_symbol": T6_TARGET_SYMBOL,
        "original_source": T6_TARGET,
        "preserved_task": T6_TASK,
        "revision_attempts_already_made": 0,
    }
    payload.update(overrides)
    return payload


def _revision_evidence():
    assessment = assess_candidate_revision(_revision_payload())
    assert assessment.eligible, assessment.ineligible_reasons
    return assessment.evidence


def test_the_raw_round9_response_is_still_invalid():
    """§26 — handed to the parser unchanged, it is refused exactly as before."""

    result = parse_revised_candidate(ROUND9_RAW_RESPONSE, _revision_evidence())

    assert result.accepted is False
    assert result.rejection_reason == OUTPUT_NO_PATCH_CANDIDATE
    assert result.candidate is None
    assert result.unavailable is False


@pytest.mark.parametrize(
    "alias",
    ["replacement_snippet", "replacement", "new_snippet", "diff_text", "new_code"],
)
def test_no_replacement_field_alias_is_accepted(alias):
    """§7/§8 — field names are protocol; a synonym is not mapped for the model."""

    response = json.dumps(
        {
            "patch_candidate": {
                "relative_path": T6_TARGET_FILE,
                "target_node_name": T6_TARGET_SYMBOL,
                "target_snippet": T6_TARGET,
                alias: _with_body(CORRECT_LOCAL_ONLY_BODY),
            }
        }
    )
    result = parse_revised_candidate(response, _revision_evidence())

    assert result.accepted is False
    assert result.rejection_reason == OUTPUT_NO_PATCHED_SNIPPET


def test_a_missing_wrapper_is_still_invalid():
    """§8 — a bare candidate object is not auto-wrapped."""

    bare = json.dumps(
        {
            "relative_path": T6_TARGET_FILE,
            "target_snippet": T6_TARGET,
            "patched_snippet": _with_body(CORRECT_LOCAL_ONLY_BODY),
        }
    )
    result = parse_revised_candidate(bare, _revision_evidence())

    assert result.accepted is False
    assert result.rejection_reason == OUTPUT_NO_PATCH_CANDIDATE


ALIASES = ("replacement_snippet", "replacement", "new_snippet", "diff_text", "new_code")


def _executable_strings(path: Path) -> list[str]:
    """Every string the module can actually compare against, minus docstrings.

    Prose is allowed to name the aliases — the module's docstring documents the
    Round-9 defect — but nothing the parser *evaluates* may.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_the_parser_names_no_alias_anywhere():
    """§8 — there is no alias table to grow, because there is no alias table."""

    module = ROOT / "core" / "candidate_revision.py"
    evaluated = _executable_strings(module)
    for alias in ALIASES:
        assert alias not in evaluated, alias

    # The only replacement field the parser reads is the protocol one.
    source = module.read_text(encoding="utf-8")
    assert 'candidate.get("patched_snippet")' in source
    for alias in ALIASES:
        assert f'.get("{alias}")' not in source, alias


def test_the_round9_substance_in_the_correct_envelope_parses():
    """§27 — the envelope was the whole barrier at the parser."""

    response = json.dumps(
        {
            "summary": "revised",
            "patch_candidate": {
                "relative_path": T6_TARGET_FILE,
                "target_node_kind": "function",
                "target_node_name": T6_TARGET_SYMBOL,
                "target_snippet": T6_TARGET,
                "patched_snippet": _with_body(ROUND9_SUBSTANCE_BODY),
            },
        }
    )
    result = parse_revised_candidate(response, _revision_evidence())

    assert result.accepted is True
    assert result.candidate["patched_snippet"] == _with_body(ROUND9_SUBSTANCE_BODY)
    assert result.candidate["relative_path"] == T6_TARGET_FILE
    # Still authored against the original source, never against Candidate0.
    assert result.candidate["target_snippet"] == T6_TARGET
    assert DEAD_GUARD_BODY not in result.candidate["patched_snippet"]


def test_a_revision_built_on_the_rejected_candidate_is_still_refused():
    """§18 — the rebase rule is untouched by this phase."""

    response = json.dumps(
        {
            "patch_candidate": {
                "relative_path": T6_TARGET_FILE,
                "target_snippet": _with_body(DEAD_GUARD_BODY),
                "patched_snippet": _with_body(CORRECT_LOCAL_ONLY_BODY),
            }
        }
    )
    result = parse_revised_candidate(response, _revision_evidence())

    assert result.accepted is False
    assert result.rejection_reason == OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE


# ═══════════════════════════════════════════════════════════════════════════
# §45 — the deterministic product smoke
# ═══════════════════════════════════════════════════════════════════════════


def _behavior_fact():
    facts, truncated = extract_behavioral_expectations(T6_QUERY)
    assert truncated is False
    (fact,) = facts
    return fact


@pytest.fixture(scope="module")
def t6_pre_probe():
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=T6_TARGET,
        candidate_eligible=True,
    )
    assert binding is not None
    probe_contract = build_probe_contract_from_behavior_fact(
        target=binding, behavior_fact=_behavior_fact()
    )
    assert probe_contract is not None
    receipt = execute_defect_probe(probe_contract, repo_path=ROOT)
    if receipt.probe_result != "reproduced":
        pytest.skip(f"baseline probe was {receipt.probe_result}, not reproduced")
    return probe_contract, receipt


def _t6_state(patched: str, pre_probe) -> AgentState:
    _probe_contract, receipt = pre_probe
    state = AgentState(
        interface="agent",
        mode="planner",
        user_input=T6_TASK,
        file_paths=[],
        primary_file=None,
        input_mode="terminal",
        language="python",
        task_type="bug_fix",
    )
    state.repo_path = str(ROOT)
    state.is_project_input = True
    state.patch_style = "safe_minimal"
    state.task_info = {"intent": "bug_fix", "patch_style": "safe_minimal"}
    state.live_route = {
        "selected_workflow": "defect_repair_patch",
        "preservation_passed": True,
        "behavioral_expectations": [_behavior_fact().as_dict()],
    }
    state.control_result = {
        "repo_path": str(ROOT),
        "patch_style": "safe_minimal",
        "live_route": dict(state.live_route),
        "preflight_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "defect_probe": receipt.as_dict(),
        "patch_intent": {
            "target_file": T6_TARGET_FILE,
            "relative_path": T6_TARGET_FILE,
            "target_symbol": T6_TARGET_SYMBOL,
            "target_symbol_full": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
            "source_snippet": T6_TARGET,
        },
        "entry_resolution": {
            "resolved_entry_nodes": [f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}"]
        },
        "scout": {"request_type": "bug_fix"},
    }
    state.json_block = {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "target_source_grounded": True,
        "confidence": 0.4,
        "needs_escalation": False,
        "patch_candidate": {
            "file": T6_TARGET_FILE,
            "relative_path": T6_TARGET_FILE,
            "target_node_kind": "function",
            "target_node_name": T6_TARGET_SYMBOL,
            "target_snippet": T6_TARGET,
            "patched_snippet": patched,
        },
        "issues": [],
    }
    pipeline._record_candidate_mutation_effect(state)
    patch_gates._enforce_safe_minimal(state)
    state.repository_graph = build_graph(
        [
            {"id": T6_TARGET_FILE, "type": "file"},
            {
                "id": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
                "type": "function",
                "file": T6_TARGET_FILE,
            },
        ],
        [
            {
                "source": T6_TARGET_FILE,
                "target": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
                "type": "contains",
            }
        ],
    )
    return state


def _enveloped(body: str) -> str:
    return json.dumps(
        {
            "summary": "revised",
            "patch_candidate": {
                "relative_path": T6_TARGET_FILE,
                "target_node_kind": "function",
                "target_node_name": T6_TARGET_SYMBOL,
                "target_snippet": T6_TARGET,
                "patched_snippet": _with_body(body),
            },
        }
    )


def _drive(state: AgentState, monkeypatch, response: str):
    prompts: list[str] = []

    def adapter(_state: AgentState, prompt: str) -> str:
        prompts.append(prompt)
        return response

    monkeypatch.setattr(pipeline, "_call_revision_provider", adapter)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before, "the repository moved"
    return state.json_block, prompts


def test_smoke_the_revision_request_carries_the_full_shared_contract(
    t6_pre_probe, monkeypatch
):
    """§45D — the live request, not a unit-test rendering of it."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, prompts = _drive(
        state, monkeypatch, _enveloped(CORRECT_LOCAL_ONLY_BODY)
    )

    assert len(prompts) == 1, "exactly one provider call"
    contract = control_engine.authoring_contract_for_control_result(
        state.control_result
    )
    assert contract.text in prompts[0]
    assert block["candidate_revision_attempt_count"] == 1
    assert block["candidate_revision_model_calls"] == 1

    receipt = block["candidate_revision_receipt"]
    assert receipt["revision_contract_present"] is True
    assert receipt["authoring_contract_version"] == AUTHORING_CONTRACT_VERSION
    assert receipt["authoring_contract_fingerprint"] == contract.fingerprint


def test_smoke_the_local_only_revision_is_admitted_verified_and_authorizes_nothing(
    t6_pre_probe, monkeypatch
):
    """§28/§45C — parses, is admitted, passes all five cases, grants nothing.

    Five, as this phase measured them.  Under INDENT.SEMANTICS.1's eight cases
    no candidate safe_minimal admits is known to close the matrix
    (tests/test_indent_semantics1.py), so this lifecycle proof declares the
    five-case oracle through the one shared test helper.
    """

    from _matrix_history import pin_live5_indentation_matrix

    pin_live5_indentation_matrix(monkeypatch)
    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, prompts = _drive(state, monkeypatch, _enveloped(CORRECT_LOCAL_ONLY_BODY))

    assert len(prompts) == 1
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_VERIFIED
    assert block["candidate_revision_output_rejection_reason"] == ""
    assert block["candidate_effect_status"] == "mutating"
    assert block["candidate_novelty_admitted"] is True
    assert block["behavioral_matrix_case_count"] == 5
    assert block["behavioral_matrix_status"] == MATRIX_FIXED_AND_PRESERVED
    assert set(
        case["candidate_status"] for case in block["behavioral_matrix_cases"]
    ) <= {CANDIDATE_FIXED, CANDIDATE_PRESERVED}
    assert block["candidate_verification_status"] == VERIFIED
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["auto_apply_allowed"] is False
    assert block["write_authority"] is False


def test_smoke_the_round9_substance_now_parses_and_is_then_rejected_for_lstrip(
    t6_pre_probe, monkeypatch
):
    """§12/§27 — the schema blindness is fixed; the algorithm is still refused.

    This is the phase succeeding.  Candidate1 reaches candidate normalization
    instead of dying at the parser, and PATCH.MINIMAL.LIVE.2 then rejects it for
    the novel ``lstrip`` member exactly as it always did.  Nothing here approves
    the Round-9 algorithm.
    """

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, prompts = _drive(state, monkeypatch, _enveloped(ROUND9_SUBSTANCE_BODY))

    assert len(prompts) == 1
    # It parsed: the revision was produced, not refused for its output shape.
    assert block["candidate_revision_output_rejection_reason"] == ""
    assert block["candidate_revision_present"] is True
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_REJECTED

    # And then the frozen novelty gate stopped it.
    assert block["candidate_novelty_admitted"] is False
    assert block["candidate_novelty_reason"] == REASON_NOVEL_EXTERNAL_REFERENCE
    assert block["patch_candidate"] is None
    assert block["needs_escalation"] is True
    assert block["execution_authorized"] is False


def test_smoke_the_raw_round9_envelope_still_ends_the_run(t6_pre_probe, monkeypatch):
    """§25 — the pre-LIVE.2 response shape is still an unusable revision."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, prompts = _drive(state, monkeypatch, ROUND9_RAW_RESPONSE)

    assert len(prompts) == 1, "no repair prompt and no second call"
    assert block["candidate_revision_outcome"] == "revision_output_invalid"
    assert block["candidate_revision_output_rejection_reason"] == OUTPUT_NO_PATCH_CANDIDATE
    assert block["candidate_revision_attempt_count"] == 1
    assert block["needs_escalation"] is True
    assert block["execution_authorized"] is False
    # The contract still travelled; the model simply did not follow it, and the
    # prompt is advice while the parser is the gate.
    assert control_engine.authoring_contract_for_control_result(
        state.control_result
    ).text in prompts[0]


def test_smoke_the_revision_budget_is_still_one(t6_pre_probe, monkeypatch):
    """§19 — contract parity bought no retry, no repair call and no second author."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    _block, prompts = _drive(state, monkeypatch, ROUND9_RAW_RESPONSE)
    assert len(prompts) == 1

    # Re-entering the branch finds the budget spent.
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert len(prompts) == 1
    assert state.candidate_revision.attempt_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# §39/§40/§47 — boundaries, cost and governance
# ═══════════════════════════════════════════════════════════════════════════

FIXTURE = ROOT / "tests" / "fixtures" / "patch_author_live2_contract_reversal.json"
SCRATCH = Path(__file__).resolve().parent


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_every_frozen_file_is_byte_identical():
    """§39 — the probes, the gates, the novelty rule and authority all stayed.

    Evaluated after the documented harness remediation is undone, because that
    separately requested work edited four of these files after this phase
    shipped.  Every pin is the byte-identical history LIVE.2 shipped against —
    the same digests CANDIDATE.VERIFY.LIVE.1 and DEFECT.PROBE.LIVE.5 pin — so
    this is one comparison per file, with no pin borrowed from anywhere else.
    """

    fixture = _fixture()
    assert "before_harness_remediation" in fixture["harness_remediation_note"]
    for rel, digest in fixture["files"].items():
        actual = hashlib.sha256(before_harness_remediation(rel)).hexdigest()
        assert actual == digest, rel


def test_the_change_is_a_reversible_containment_proof():
    """Every changed file's pre-phase bytes are reproducible from the shipped one.

    The remediation is undone first.  Its core/pipeline.py preimage is exactly
    this phase's post, so the pipeline chain is shipped -> LIVE.2 post ->
    LIVE.2 pre, and LIVE.2's pre is PATCH.AUTHOR.LIVE.1's post byte for byte.
    Every digest asserted here is this fixture's own.
    """

    fixture = _fixture()
    for reversal in fixture["reversals"]:
        path = reversal["path"]
        post = before_harness_remediation(path).decode("utf-8")
        assert hashlib.sha256(post.encode("utf-8")).hexdigest() == reversal["post_sha256"], path
        text = post
        for hunk in reversal["hunks"]:
            assert text.count(hunk["post"]) == 1, path
            text = text.replace(hunk["post"], hunk["pre"])
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == reversal["pre_sha256"], path

    live1 = json.loads(
        (ROOT / "tests/fixtures/patch_author_live1_frozen_boundaries.json").read_text(
            encoding="utf-8"
        )
    )["pipeline"]
    pipeline = next(r for r in fixture["reversals"] if r["path"] == "core/pipeline.py")
    assert pipeline["pre_sha256"] == live1["post_sha256"]


def test_the_containment_is_one_new_accessor_and_four_touched_definitions():
    """Nothing was removed, and nothing outside the contract path was rewritten."""

    def definitions(source: str) -> dict[str, str]:
        return {
            node.name: hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }

    expected = {
        "core/candidate_revision.py": (
            [],
            ["CandidateRevisionReceipt", "build_revision_prompt", "candidate_revision_guardrails"],
        ),
        "core/control_engine.py": (
            ["authoring_contract_for_control_result"],
            ["_patch_output_format_block", "_safe_minimal_forbidden_block", "build_control_prompt"],
        ),
        "core/pipeline.py": ([], ["_maybe_revise_rejected_candidate"]),
        "core/prompter.py": ([], []),
    }
    seen = {}
    for reversal in _fixture()["reversals"]:
        # Compare LIVE.2's own post with LIVE.2's own pre: the remediation that
        # came later is undone first, so it cannot appear as this phase's diff.
        post_text = before_harness_remediation(reversal["path"]).decode("utf-8")
        pre_text = post_text
        for hunk in reversal["hunks"]:
            pre_text = pre_text.replace(hunk["post"], hunk["pre"])
        before, after = definitions(pre_text), definitions(post_text)
        assert sorted(set(before) - set(after)) == reversal["removed_definitions"] == []
        seen[reversal["path"]] = (
            sorted(set(after) - set(before)),
            sorted(n for n in before if n in after and before[n] != after[n]),
        )
    assert seen == expected


def test_the_phase_adds_no_model_network_retrieval_or_traversal_capability():
    """§23/§39 — building the contract is prompt construction and nothing else."""

    module = ROOT / "core" / "patch_authoring_contract.py"
    # Docstrings are excluded deliberately: this module's prose says it performs
    # no traversal, indexing or embedding, and a naive substring scan would trip
    # on the very sentence that states the boundary.
    evaluated = " ".join(_executable_strings(module))
    tree = ast.parse(module.read_text(encoding="utf-8"))
    reachable = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (name := (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr if isinstance(node.func, ast.Attribute) else None
        ))
    }
    for forbidden in (
        "requests",
        "httpx",
        "urlopen",
        "subprocess",
        "walk",
        "rglob",
        "glob",
        "read_text",
        "read_bytes",
        "run_gemini_request",
        "retrieve_context",
        "build_graph",
    ):
        assert forbidden not in reachable, forbidden
        assert forbidden not in evaluated, forbidden

    registry = load_phase_registry(str(ROOT / "docs" / "roadmap" / "phase_registry.json"))
    phase = {item["phase_id"]: item for item in registry["phases"]}[PHASE]
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert phase["merge_allowed"] is False
    assert phase["human_approval_required"] is True


def test_the_registry_entry_is_present_and_honest():
    registry = load_phase_registry(str(ROOT / "docs" / "roadmap" / "phase_registry.json"))
    phase = {item["phase_id"]: item for item in registry["phases"]}[PHASE]

    assert phase["status"] == "complete"
    assert phase["track"] == "CONTROL"
    for required in (
        "PATCH.AUTHOR.LIVE.1",
        "PATCH.MINIMAL.LIVE.1",
        "PATCH.MINIMAL.LIVE.2",
        "DEFECT.PROBE.LIVE.5",
        "DEFECT.PROBE.LIVE.4",
        "CANDIDATE.VERIFY.LIVE.1",
        "DEFECT.FACT.LIVE.1",
        "PATCH.BASIS.LIVE.1",
        "CONTROL.LOCALIZE.LIVE.2",
        "RETRIEVE.LIVE.4",
    ):
        assert required in phase["prerequisites"], required
    assert "core/patch_authoring_contract.py" in phase["expected_artifacts"]
    text = json.dumps(phase).lower()
    assert "lstrip" in text, "the still-blocked member is named"
    assert "no model call" in text or "no additional provider call" in text


def test_the_real_classify_indent_is_untouched():
    """§39 — this phase fixes a prompt contract; it does not repair T6."""

    live = inspect.getsource(_classify_indent)
    assert live == T6_TARGET
    assert T6_BODY in (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    for body in (CORRECT_LOCAL_ONLY_BODY, ROUND9_SUBSTANCE_BODY, DEAD_GUARD_BODY):
        assert body not in (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert "gcd" not in live


def test_rendering_the_contract_is_negligible_next_to_a_provider_call():
    """§40 — the intended cost is prompt text, not compute."""

    started = time.perf_counter()
    for _ in range(500):
        render_patch_authoring_contract(style="safe_minimal", source_snippet=T6_TARGET)
    assert time.perf_counter() - started < 2.0


def test_the_measured_prompt_size_delta_is_the_contract_and_its_heading(monkeypatch):
    """§40 — the revision request grows by the contract, and by nothing else."""

    control_result = _t6_control_result()
    contract = control_engine.authoring_contract_for_control_result(control_result)
    evidence = _revision_evidence()
    prompt = build_revision_prompt(evidence, contract)

    heading = next(c for c in PROMPT_TEMPLATE_CONSTANTS if "PATCH CANDIDATE CONTRACT" in c)
    # Removing the contract, its heading and the blank line around them leaves a
    # request the size of LIVE.1's, give or take the reworded instruction.
    without = prompt.replace(f"{heading}\n{contract.text}\n\n", "")
    assert len(prompt) - len(without) == len(heading) + len(contract.text) + 3
    assert len(contract.text) < 4000

    # The initial draft grew by nothing at all: it already had this material.
    draft = _draft_prompt(monkeypatch, control_result)
    for section in contract.sections:
        assert section in draft
