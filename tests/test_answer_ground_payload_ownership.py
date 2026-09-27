"""ANSWER.GROUND.LIVE.4 — structured payload non-interference.

Round-7 established that ANSWER.GROUND rewrote harness-authored control-plane
state as if the model had asserted it.  ``candidate_verification_phase_id``
reached the user as

    "CANDIDATE.VERIFY.LIVE (not established in the current evidence).1
     Repository evidence gap: ..."

— syntactically still a string, semantically destroyed.  These tests pin the
ownership boundary: grounding may rewrite model-authored answer claims and
nothing else, and every harness field is byte/value identical across the
display/persistence grounding path.
"""

from __future__ import annotations

import copy
import json
import os
from types import SimpleNamespace

import pytest

from core.answer_entity_grounding import (
    _ANSWER_SURFACE_KEYS,
    _SKIP_PAYLOAD_TEXT_KEYS,
    _SYMBOL_ASSERTION_KEYS,
    GROUNDED_EXISTING,
    UNVERIFIED_MODEL_ASSERTION,
    RepositoryEntityEvidence,
    ground_answer_for_display,
    ground_state_answer,
)


# ── fixtures ────────────────────────────────────────────────────────────────

def _evidence(
    *,
    paths: tuple[str, ...] = (),
    symbols: tuple[str, ...] = (),
) -> RepositoryEntityEvidence:
    """Evidence that puts ``candidate`` into the known-owner-name set.

    This is what made Round-7 reproducible: a repository that genuinely
    declares a symbol whose tail is ``candidate`` makes ``CANDIDATE.*`` an
    owner-shaped repository claim, so the phase id becomes classifiable.
    """

    return RepositoryEntityEvidence(
        repository_id="cattus-repo",
        display_name="C.A.T.T.U.S",
        aliases=frozenset({"C.A.T.T.U.S"}),
        existing_paths=frozenset(paths),
        source_symbols=frozenset(symbols),
        analysis_paths=frozenset(),
        execution_paths=frozenset(),
        current=True,
    )


_ROUND7_EVIDENCE = _evidence(
    paths=("main.py", "core/candidate_verification.py"),
    symbols=(
        "core/candidate_verification.py::verify_candidate",
        "core/candidate_verification.py::candidate",
    ),
)


def _frozen_boundaries() -> dict:
    path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "answer_ground_live4_frozen_boundaries.json",
    )
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _state(**overrides):
    base = dict(
        repo_path=None,
        project_tag="",
        repository_inventory=None,
        repository_graph=None,
        analysis_evidence=None,
        control_result=None,
        validation_output="",
        answer_grounding_evidence_current=True,
        user_input="why was the candidate rejected?",
        human_answer="",
        final_answer="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def round7_payload():
    """The exact Round-7 candidate-verification payload shape."""

    return {
        # -- model-authored answer surface ------------------------------------
        "summary": "The candidate was rejected by paired probe evidence.",
        "issues": [
            {
                "severity": "high",
                "type": "logic",
                "file": "main.py",
                "reason": "The reorder regressed a preserved case.",
            }
        ],
        "patch_candidate": None,
        "patch_plan": None,
        "confidence": 0.4,
        "needs_escalation": True,
        # -- harness-authored control plane ----------------------------------
        "candidate_verification_phase_id": "CANDIDATE.VERIFY.LIVE.1",
        "candidate_verification_schema_version": "candidate_verify_live_1_v1",
        "candidate_verification_status": "rejected",
        "candidate_verification_candidate_fingerprint": "sha256:ab12cd34ef56",
        "candidate_verification_probe_fingerprint": "sha256:ff00ee11dd22",
        "candidate_verification_execution_authorized": False,
        "candidate_verification_final_repository_changed": False,
        "candidate_verification_authority_effect": "none",
        "candidate_verification_timings": {"total_seconds": 1.25},
        "candidate_verification_receipt": {
            "phase_id": "CANDIDATE.VERIFY.LIVE.1",
            "schema_version": "candidate_verify_live_1_v1",
            "status": "rejected",
            "candidate_fingerprint": "sha256:ab12cd34ef56",
            "probe_fingerprint": "sha256:ff00ee11dd22",
            "provenance": "harness_authored",
            "components": {
                "paired_probe_status": "regressed",
                "sandbox_status": "applied",
            },
            "rejection_reasons": ["preservation_regressed"],
        },
        "localized_target_receipt": {
            "phase_id": "LOCALIZE.LIVE.2",
            "localized_target": "main.py::main",
            "provenance": "harness_authored",
        },
        "evidence_freshness": {"phase_id": "FRESH.LIVE.1", "binding": "current"},
        "human_review_eligible": False,
        "execution_authorized": False,
        "final_repository_changed": False,
        "write_authority": False,
        "patch_application_authority": False,
    }


def _ground(payload, evidence=_ROUND7_EVIDENCE, monkeypatch=None, state=None):
    """Run the display boundary against a fixed evidence set."""

    import core.answer_entity_grounding as module

    original = module._state_repository_evidence
    module._state_repository_evidence = lambda _state: (evidence,)
    try:
        return ground_answer_for_display(state or _state(), "", payload)
    finally:
        module._state_repository_evidence = original


# ── Round-7 regression ──────────────────────────────────────────────────────

def test_round7_candidate_verification_phase_id_survives_grounding(round7_payload):
    _, _, display, _ = _ground(round7_payload)

    assert display["candidate_verification_phase_id"] == "CANDIDATE.VERIFY.LIVE.1"


def test_round7_nested_receipt_phase_id_survives_grounding(round7_payload):
    _, _, display, _ = _ground(round7_payload)

    assert display["candidate_verification_receipt"]["phase_id"] == (
        "CANDIDATE.VERIFY.LIVE.1"
    )


def test_round7_payload_is_byte_identical_outside_the_answer_surface(round7_payload):
    before = copy.deepcopy(round7_payload)

    _, _, display, _ = _ground(round7_payload)

    for key, value in before.items():
        if key in {"summary", "issues"}:
            continue
        assert display[key] == value, f"harness field {key!r} was mutated"


def test_no_evidence_gap_prose_reaches_any_machine_field(round7_payload):
    _, _, display, _ = _ground(round7_payload)

    machine = dict(display)
    for key in ("summary", "issues", "answer_entity_grounding"):
        machine.pop(key, None)
    rendered = json.dumps(machine)

    assert "not established in the current evidence" not in rendered
    assert "Repository evidence gap" not in rendered


# ── field classes pinned individually ───────────────────────────────────────

@pytest.mark.parametrize(
    "key, value",
    [
        ("candidate_verification_phase_id", "CANDIDATE.VERIFY.LIVE.1"),
        ("candidate_verification_schema_version", "candidate_verify_live_1_v1"),
        ("candidate_verification_status", "rejected"),
        ("candidate_verification_candidate_fingerprint", "sha256:ab12cd34ef56"),
        ("candidate_verification_probe_fingerprint", "sha256:ff00ee11dd22"),
        ("candidate_verification_authority_effect", "none"),
        ("execution_eligibility_phase_id", "EXEC.POLICY.LIVE.1"),
        ("defect_closure_status", "CLOSURE.LIVE.2"),
        ("targeted_validation_status", "OPS.VALIDATE.3"),
    ],
)
def test_harness_scalar_string_is_not_rewritten(round7_payload, key, value):
    round7_payload[key] = value

    _, _, display, _ = _ground(round7_payload)

    assert display[key] == value


def test_harness_authority_booleans_are_not_rewritten(round7_payload):
    _, _, display, _ = _ground(round7_payload)

    assert display["human_review_eligible"] is False
    assert display["execution_authorized"] is False
    assert display["final_repository_changed"] is False
    assert display["write_authority"] is False
    assert display["patch_application_authority"] is False


def test_harness_provenance_value_is_not_rewritten(round7_payload):
    _, _, display, _ = _ground(round7_payload)

    assert display["candidate_verification_receipt"]["provenance"] == (
        "harness_authored"
    )
    assert display["localized_target_receipt"]["provenance"] == "harness_authored"


def test_harness_telemetry_is_not_rewritten(round7_payload):
    _, _, display, _ = _ground(round7_payload)

    assert display["candidate_verification_timings"] == {"total_seconds": 1.25}
    assert display["evidence_freshness"] == {
        "phase_id": "FRESH.LIVE.1",
        "binding": "current",
    }


def test_localized_target_receipt_is_not_rewritten(round7_payload):
    _, _, display, _ = _ground(round7_payload)

    assert display["localized_target_receipt"] == {
        "phase_id": "LOCALIZE.LIVE.2",
        "localized_target": "main.py::main",
        "provenance": "harness_authored",
    }


def test_nested_enum_and_reason_list_inside_a_receipt_are_not_rewritten(
    round7_payload,
):
    _, _, display, _ = _ground(round7_payload)

    receipt = display["candidate_verification_receipt"]
    assert receipt["components"] == {
        "paired_probe_status": "regressed",
        "sandbox_status": "applied",
    }
    assert receipt["rejection_reasons"] == ["preservation_regressed"]


# ── the safe default for unknown structure ──────────────────────────────────

def test_unknown_harness_structured_string_defaults_to_non_groundable(
    round7_payload,
):
    """A field this phase has never heard of is left alone, not guessed at."""

    round7_payload["some_future_receipt"] = {
        "phase_id": "FUTURE.LIVE.9",
        "detail": "PatchGenerator.generate ran against config/settings.py.",
    }

    _, _, display, _ = _ground(round7_payload)

    assert display["some_future_receipt"] == {
        "phase_id": "FUTURE.LIVE.9",
        "detail": "PatchGenerator.generate ran against config/settings.py.",
    }


def test_a_harness_container_shields_a_key_that_is_groundable_at_the_top(
    round7_payload,
):
    """Ownership is inherited down the subtree, not decided per leaf name.

    ``summary`` is a model-authored answer field at the top level.  The same
    spelling *inside* a harness receipt belongs to the harness.
    """

    round7_payload["candidate_verification_receipt"]["summary"] = (
        "PatchGenerator.generate was rejected."
    )

    _, _, display, _ = _ground(round7_payload)

    assert display["candidate_verification_receipt"]["summary"] == (
        "PatchGenerator.generate was rejected."
    )


# ── model-authored claims stay groundable (LIVE.1/.2/.3 protection) ─────────

def test_model_authored_symbol_field_remains_groundable():
    block = {
        "summary": "Analysis complete.",
        "symbol": "ImaginaryClass.fake_method",
        "patch_candidate": None,
        "write_authority": False,
    }

    _, _, display, receipt = _ground(block, evidence=_evidence(paths=("main.py",)))

    assert display["symbol"].startswith("ImaginaryClass.fake_method")
    assert "not established in the current evidence" in display["symbol"]
    assert receipt["unverified_symbol_count"] == 1
    assert display["write_authority"] is False


def test_model_authored_free_prose_remains_groundable():
    block = {
        "summary": "The bug is in patcher/generator.py::PatchGenerator.generate.",
        "patch_candidate": None,
    }

    _, _, display, receipt = _ground(block, evidence=_evidence(paths=("main.py",)))

    assert "The bug is in" in display["summary"]
    assert "not established in the current evidence" in display["summary"]
    assert receipt["unverified_entity_count"] == 1


def test_model_authored_nested_issue_prose_remains_groundable():
    block = {
        "summary": "Two problems.",
        "issues": [
            {"reason": "config/settings.py::ConfigurationOptions is invalid."}
        ],
        "patch_candidate": None,
    }

    _, _, display, receipt = _ground(block, evidence=_evidence(paths=("main.py",)))

    assert "is invalid" in display["issues"][0]["reason"]
    assert "not established in the current evidence" in display["issues"][0]["reason"]
    assert receipt["unverified_entity_count"] == 1


def test_model_authored_patch_candidate_fields_are_still_reached():
    block = {
        "summary": "Fixing it.",
        "patch_candidate": {
            "relative_path": "calc.py",
            "target_node_name": "add",
            "target_snippet": "def add(a, b):\n    return a - b\n",
            "patched_snippet": "def add(a, b):\n    return a + b\n",
        },
    }

    _, _, display, receipt = _ground(
        block,
        evidence=_evidence(paths=("calc.py",), symbols=("calc.py::add",)),
    )

    assert display["patch_candidate"]["relative_path"] == "calc.py"
    assert display["patch_candidate"]["target_node_name"] == "add"
    # The snippets are code bytes and are never annotated.
    assert display["patch_candidate"]["target_snippet"] == (
        "def add(a, b):\n    return a - b\n"
    )
    assert receipt["grounded_symbol_count"] == 1


def test_a_fabricated_symbol_inside_patch_candidate_is_still_downgraded():
    block = {
        "summary": "Fixing it.",
        "patch_candidate": {
            "relative_path": "calc.py",
            "target_node_name": "ImaginaryHelper.run",
        },
    }

    _, _, display, receipt = _ground(
        block,
        evidence=_evidence(paths=("calc.py",), symbols=("calc.py::add",)),
    )

    assert "not established in the current evidence" in (
        display["patch_candidate"]["target_node_name"]
    )
    assert receipt["unverified_symbol_count"] == 1


# ── the boundary itself ─────────────────────────────────────────────────────

def test_the_answer_surface_covers_every_typed_symbol_assertion_key():
    """A typed claim field the model authors must stay groundable."""

    assert _SYMBOL_ASSERTION_KEYS <= _ANSWER_SURFACE_KEYS


def test_the_answer_surface_never_overlaps_the_verbatim_text_keys():
    """Code bytes and acquired execution facts are never an answer claim."""

    assert not (_ANSWER_SURFACE_KEYS & _SKIP_PAYLOAD_TEXT_KEYS)


def test_the_answer_surface_excludes_harness_control_plane_spellings():
    forbidden = {
        "phase_id",
        "schema_version",
        "provenance",
        "status",
        "fingerprint",
        "candidate_fingerprint",
        "probe_fingerprint",
        "human_review_eligible",
        "execution_authorized",
        "final_repository_changed",
        "write_authority",
        "patch_application_authority",
        "authority_effect",
        "receipt",
        "evidence_freshness",
        "verification_status",
        "localized_target",
    }

    assert not (_ANSWER_SURFACE_KEYS & forbidden)


def test_the_answer_surface_is_disjoint_from_the_pipeline_control_plane_keys():
    """No harness key may share a spelling with a model-authored answer key.

    Ownership is inherited down the subtree, so a collision *inside* a harness
    container is already harmless.  This closes the remaining case: a
    control-plane key attached at the top level of ``json_block`` whose name
    happens to match an answer field.  If a future phase introduces one, this
    fails here rather than silently corrupting that field at display time.
    """

    from core import pipeline

    harness_keys = set()
    for group in (
        pipeline._CANDIDATE_VALIDATION_KEYS,
        pipeline._TARGETED_VALIDATION_KEYS,
        pipeline._CANDIDATE_DEFECT_PROBE_KEYS,
        pipeline._EXECUTION_ELIGIBILITY_KEYS,
        pipeline._CANDIDATE_VERIFICATION_KEYS,
        pipeline._CANDIDATE_EFFECT_KEYS,
        pipeline._CANDIDATE_NOVELTY_KEYS,
        pipeline._CANDIDATE_REVISION_KEYS,
        # ANSWER.COHERENCE.LIVE.1 — which candidate the final answer presents.
        pipeline._CANDIDATE_PRESENTATION_KEYS,
    ):
        harness_keys.update(group)

    assert harness_keys, "no control-plane keys found; the groups moved"
    assert not (harness_keys & _ANSWER_SURFACE_KEYS)


def test_grounding_a_payload_of_only_harness_fields_reports_no_action(
    round7_payload,
):
    for key in ("summary", "issues"):
        round7_payload.pop(key)

    _, _, _, receipt = _ground(round7_payload)

    assert receipt["action"] == "unchanged"
    assert receipt["asserted_entity_count"] == 0


def test_state_grounding_preserves_the_receipt_through_persistence(round7_payload):
    """The stop condition: the same bytes survive the persisted copy too."""

    state = _state(json_block=round7_payload)

    import core.answer_entity_grounding as module

    original = module._state_repository_evidence
    module._state_repository_evidence = lambda _state: (_ROUND7_EVIDENCE,)
    try:
        ground_state_answer(state)
    finally:
        module._state_repository_evidence = original

    assert state.json_block["candidate_verification_phase_id"] == (
        "CANDIDATE.VERIFY.LIVE.1"
    )
    assert state.json_block["candidate_verification_receipt"]["phase_id"] == (
        "CANDIDATE.VERIFY.LIVE.1"
    )
    # The persisted answer string is the same copy.
    assert json.loads(state.final_answer) == state.json_block
    assert json.loads(state.final_answer)["candidate_verification_receipt"] == (
        round7_payload["candidate_verification_receipt"]
    )


def test_only_the_owned_function_changed_in_the_grounding_module():
    """The finer-grained replacement for the LIVE.2 whole-file freeze.

    ``tests/fixtures/control_localize_live2_boundaries.json`` froze this whole
    file so that unrelated phases could not perturb the grounding boundary.
    ANSWER.GROUND.LIVE.4 is authorised to edit it, so that pin had to be
    re-taken — and a re-taken whole-file pin proves nothing on its own.  This
    asserts the finer fact: of the 44 top-level definitions in the module,
    exactly one is this phase's, and the other 43 are AST-identical to their
    pre-LIVE.4 values.
    """

    import ast
    import hashlib

    import core.answer_entity_grounding as module

    fixture = _frozen_boundaries()

    with open(module.__file__, encoding="utf-8") as handle:
        source = handle.read()
    digests = {
        node.name: hashlib.sha256(
            ast.dump(node, include_attributes=False).encode()
        ).hexdigest()
        for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    frozen = fixture["answer_entity_grounding_frozen_functions"]
    assert fixture["owned_function"] == "_ground_payload_value"
    assert fixture["owned_function"] not in frozen
    for name, digest in frozen.items():
        assert name in digests, f"{name} disappeared from the grounding module"
        assert digests[name] == digest, f"{name} drifted; LIVE.4 owns only the payload walk"


def test_the_collaborator_modules_are_untouched_by_this_phase():
    """LIVE.4 reuses existing boundaries; it does not edit them."""

    import hashlib

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for path, digest in _frozen_boundaries()["collaborator_files"].items():
        with open(os.path.join(root, path), "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == digest, path


def test_round7_end_to_end_through_a_real_state_and_real_evidence(tmp_path):
    """The Round-7 shape through the real seam, with nothing patched out.

    Every other test here injects evidence directly.  This one builds a real
    repository and real analysis evidence, so ``_state_repository_evidence``
    derives the symbol universe itself — including the ``candidate`` tail that
    makes ``CANDIDATE.*`` owner-shaped and thus classifiable.

    The test is deliberately non-vacuous: the same payload carries a fabricated
    model claim that MUST still be downgraded.  If grounding ever went inert,
    that assertion fails rather than the harness assertions passing for the
    wrong reason.
    """

    from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem

    repo = tmp_path / "cattus"
    repo.mkdir()
    (repo / "candidate_verification.py").write_text(
        "def candidate():\n    return None\n", encoding="utf-8"
    )

    state = _state(
        repo_path=str(repo),
        project_tag="cattus",
        analysis_evidence=AnalysisEvidence(
            items=(
                AnalysisEvidenceItem(
                    "candidate_verification.py",
                    "implementation_source",
                    "def candidate():\n    return None\n",
                ),
            )
        ),
        json_block=None,
    )

    payload = {
        "summary": "The bug is in patcher/generator.py::PatchGenerator.generate.",
        "candidate_verification_phase_id": "CANDIDATE.VERIFY.LIVE.1",
        "candidate_verification_receipt": {
            "phase_id": "CANDIDATE.VERIFY.LIVE.1",
            "candidate_fingerprint": "sha256:ab12cd34ef56",
        },
        "human_review_eligible": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", payload)

    # The gate is live: the fabricated model claim is still retracted.
    assert "not established in the current evidence" in display["summary"]
    assert receipt["unverified_entity_count"] >= 1

    # And the harness fields came through untouched.
    assert display["candidate_verification_phase_id"] == "CANDIDATE.VERIFY.LIVE.1"
    assert display["candidate_verification_receipt"] == {
        "phase_id": "CANDIDATE.VERIFY.LIVE.1",
        "candidate_fingerprint": "sha256:ab12cd34ef56",
    }
    assert display["human_review_eligible"] is False


def test_no_model_network_or_traversal_is_introduced(round7_payload):
    import core.answer_entity_grounding as module

    source = (
        os.path.join(os.path.dirname(module.__file__), "answer_entity_grounding.py")
    )
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()

    for forbidden in (
        "os.walk",
        "rglob",
        "glob(",
        "import requests",
        "import httpx",
        "import urllib",
        "import socket",
        "import subprocess",
        "core.retriever",
        "core.indexer",
        "write_authority =",
        "patch_application_authority =",
    ):
        assert forbidden not in text, forbidden
