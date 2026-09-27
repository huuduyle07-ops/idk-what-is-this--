"""WORKER.DECL.2A — strict structured patch response envelope.

The point of these tests is the difference between two sentences:

    "a JSON object appeared somewhere in the answer"
    "the answer is exactly one JSON object"

The legacy extractor accepts the first.  The strict envelope accepts only the
second, and this suite pins every way the two diverge — fenced blocks, prose
preambles, trailing text, a second object, unknown fields, authority-shaped
fields, and every bound — while proving the run that was measured applied
exactly the patch it would have applied anyway.

Live tests drive the real apply engine over a real temporary repository.  No
model is called anywhere in this file: the "worker response" is a fixture
string, read once by both parsers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

import core.run_lifecycle as run_lifecycle
from core.json_utils import extract_json_block
from core.post_run_reconciliation import MAX_DECLARED_CHANGES
from core.worker_patch_envelope import (
    AGREEMENT_AGREED,
    AGREEMENT_MISMATCH,
    AGREEMENT_NOT_COMPARABLE,
    ENVELOPE_ARTIFACT_NAME,
    ENVIRONMENT_FLAG,
    MAX_ENVELOPE_OPERATIONS,
    MAX_ENVELOPE_RESPONSE_CHARS,
    MAX_OPERATION_PAYLOAD_CHARS,
    PROVENANCE_LEGACY,
    PROVENANCE_NONE,
    PROVENANCE_STRICT,
    STATUS_BOUND_EXCEEDED,
    STATUS_INVALID_JSON,
    STATUS_NON_OBJECT,
    STATUS_SCHEMA_INVALID,
    STATUS_SURROUNDING_PROSE_REJECTED,
    STATUS_UNKNOWN_FIELD,
    STATUS_UNSUPPORTED_SCHEMA_VERSION,
    STATUS_VALID,
    WORKER_PATCH_ENVELOPE_SCHEMA_VERSION,
    WorkerPatchEnvelope,
    canonical_patch_plan_identity,
    compare_strict_and_legacy,
    is_strict_worker_patch_envelope_shadow_enabled,
    load_worker_patch_envelope_record,
    parse_strict_worker_patch_envelope,
    safe_compare_strict_and_legacy,
    summarize_worker_patch_envelope_records,
    worker_patch_envelope_fingerprint,
    worker_patch_envelope_guardrails,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

EDIT_MAIN = {
    "op": "replace_snippet",
    "relative_path": "main.py",
    "target_snippet": "VALUE = 1\n",
    "patched_snippet": "VALUE = 2\n",
}
CREATE_EXTRA = {
    "op": "create_file",
    "relative_path": "extra.py",
    "content": "EXTRA = True\n",
}


def _envelope_text(plan, *, schema_version=WORKER_PATCH_ENVELOPE_SCHEMA_VERSION, **extra):
    return json.dumps(
        {"schema_version": schema_version, "patch_plan": plan, **extra},
        ensure_ascii=False,
    )


def _legacy_response(plan) -> dict:
    """A payload shaped like what the existing prompt contract asks for."""
    return {
        "summary": "a change",
        "issues": [],
        "patch_candidate": None,
        "patch_plan": plan,
        "confidence": 0.9,
        "needs_escalation": False,
    }


@pytest.fixture(autouse=True)
def _quiet_brain_stamp(monkeypatch):
    """The brain stamp shells out to git; it is irrelevant to this phase."""
    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo: {"brain_stamp_id": "stamp", "schema_version": 2},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    return project


def _artifact(result: dict) -> dict | None:
    path = Path(result["replay_dir"]) / ENVELOPE_ARTIFACT_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── The flag ──────────────────────────────────────────────────────────────────

def test_the_envelope_shadow_is_disabled_unless_explicitly_enabled(monkeypatch):
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    assert is_strict_worker_patch_envelope_shadow_enabled() is False
    for value in ("", "0", "false", "no", "off", "maybe"):
        monkeypatch.setenv(ENVIRONMENT_FLAG, value)
        assert is_strict_worker_patch_envelope_shadow_enabled() is False
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(ENVIRONMENT_FLAG, value)
        assert is_strict_worker_patch_envelope_shadow_enabled() is True


# ── §30 pure JSON ─────────────────────────────────────────────────────────────

def test_a_pure_json_object_response_is_a_valid_envelope():
    parse = parse_strict_worker_patch_envelope(_envelope_text([EDIT_MAIN]))

    assert parse.status == STATUS_VALID
    assert parse.is_valid is True
    assert parse.envelope is not None
    assert parse.envelope.schema_version == WORKER_PATCH_ENVELOPE_SCHEMA_VERSION
    # The existing operation reaches the existing executor unchanged.
    assert parse.envelope.patch_plan_operations() == [EDIT_MAIN]


def test_surrounding_whitespace_alone_does_not_make_a_response_prose():
    parse = parse_strict_worker_patch_envelope(
        "\n\t  " + _envelope_text([EDIT_MAIN]) + "  \n\n"
    )
    assert parse.status == STATUS_VALID


# ── §31/§32/§33 the whole point ───────────────────────────────────────────────

def test_a_markdown_fenced_response_is_rejected_while_legacy_still_reads_it():
    """The expected divergence, not a bug: the fence is prose around an object."""
    inner = _envelope_text([EDIT_MAIN])
    response = "```json\n" + inner + "\n```"

    assert parse_strict_worker_patch_envelope(response).status == (
        STATUS_SURROUNDING_PROSE_REJECTED
    )
    # And the legacy extractor happily recovers it, which is why the two
    # channels must be measured separately rather than conflated.
    assert extract_json_block(response) is not None


def test_prose_around_the_object_is_rejected_even_though_legacy_extracts_it():
    response = "Sure! Here is the patch:\n" + _envelope_text([EDIT_MAIN])

    assert parse_strict_worker_patch_envelope(response).status == (
        STATUS_SURROUNDING_PROSE_REJECTED
    )
    assert extract_json_block(response) is not None


def test_trailing_commentary_after_a_complete_object_is_rejected():
    response = _envelope_text([EDIT_MAIN]) + "\nHope that helps!"
    assert parse_strict_worker_patch_envelope(response).status == (
        STATUS_SURROUNDING_PROSE_REJECTED
    )


def test_two_objects_never_become_the_first_one():
    """No 'take the first one' — the whole response must be one object."""
    first = _envelope_text([EDIT_MAIN])
    second = _envelope_text([CREATE_EXTRA])
    parse = parse_strict_worker_patch_envelope(first + "\n" + second)

    assert parse.status == STATUS_SURROUNDING_PROSE_REJECTED
    assert parse.envelope is None
    # The legacy extractor does take the first one; that is the divergence.
    assert extract_json_block(first + "\n" + second) is not None


def test_a_prose_only_response_is_rejected_without_being_searched():
    parse = parse_strict_worker_patch_envelope("I could not produce a patch.")
    assert parse.status == STATUS_SURROUNDING_PROSE_REJECTED
    assert parse.envelope is None


def test_malformed_json_is_named_separately_from_prose():
    assert parse_strict_worker_patch_envelope("{not json").status == (
        STATUS_INVALID_JSON
    )
    assert parse_strict_worker_patch_envelope("").status == STATUS_INVALID_JSON
    assert parse_strict_worker_patch_envelope(None).status == STATUS_INVALID_JSON


def test_a_json_value_that_is_not_an_object_is_not_an_envelope():
    assert parse_strict_worker_patch_envelope("[1, 2]").status == STATUS_NON_OBJECT
    assert parse_strict_worker_patch_envelope('"a string"').status == (
        STATUS_NON_OBJECT
    )


# ── §8/§9/§34 unknown and authority-shaped fields ─────────────────────────────

def test_an_authority_shaped_field_is_rejected_by_name():
    """An envelope may not smuggle a decision it has no standing to make."""
    for key in (
        "write_authority",
        "write_allowed",
        "reviewer_approved",
        "human_approved",
        "merge_allowed",
        "secret_authority",
    ):
        parse = parse_strict_worker_patch_envelope(
            _envelope_text([EDIT_MAIN], **{key: True})
        )
        assert parse.status == STATUS_UNKNOWN_FIELD, key
        assert parse.envelope is None
        assert key in parse.unknown_keys


def test_an_unknown_top_level_field_is_rejected_not_ignored():
    parse = parse_strict_worker_patch_envelope(
        _envelope_text([EDIT_MAIN], confidence=0.9)
    )
    assert parse.status == STATUS_UNKNOWN_FIELD
    assert parse.unknown_keys == ("confidence",)


def test_a_declaration_field_is_not_yet_part_of_the_contract():
    """WORKER.DECL.2B owns change intent; 2A must not quietly accept it early."""
    parse = parse_strict_worker_patch_envelope(
        _envelope_text([EDIT_MAIN], declared_changes=[{"path": "main.py"}])
    )
    assert parse.status == STATUS_UNKNOWN_FIELD
    assert parse.unknown_keys == ("declared_changes",)


def test_an_unknown_operation_field_is_rejected():
    operation = {**EDIT_MAIN, "reviewer_approved": True}
    assert parse_strict_worker_patch_envelope(
        _envelope_text([operation])
    ).status == STATUS_UNKNOWN_FIELD

    operation = {**EDIT_MAIN, "rationale": "because"}
    assert parse_strict_worker_patch_envelope(
        _envelope_text([operation])
    ).status == STATUS_UNKNOWN_FIELD


def test_a_missing_required_field_is_schema_invalid():
    assert parse_strict_worker_patch_envelope(
        json.dumps({"patch_plan": [EDIT_MAIN]})
    ).status == STATUS_SCHEMA_INVALID
    assert parse_strict_worker_patch_envelope(
        json.dumps({"schema_version": WORKER_PATCH_ENVELOPE_SCHEMA_VERSION})
    ).status == STATUS_SCHEMA_INVALID


def test_an_unsupported_schema_version_is_named_as_such():
    assert parse_strict_worker_patch_envelope(
        _envelope_text([EDIT_MAIN], schema_version="something_else_v9")
    ).status == STATUS_UNSUPPORTED_SCHEMA_VERSION


# ── §7 the existing patch-plan contract, unchanged ────────────────────────────

def test_an_operation_the_executor_does_not_define_is_invalid_here_too():
    for operation in (
        {"op": "delete_file", "relative_path": "main.py"},
        {"op": "", "relative_path": "main.py"},
        {"relative_path": "main.py", "content": "x"},
    ):
        assert parse_strict_worker_patch_envelope(
            _envelope_text([operation])
        ).status == STATUS_SCHEMA_INVALID, operation


def test_a_required_operation_payload_must_be_a_string():
    assert parse_strict_worker_patch_envelope(
        _envelope_text([{**EDIT_MAIN, "patched_snippet": 7}])
    ).status == STATUS_SCHEMA_INVALID
    assert parse_strict_worker_patch_envelope(
        _envelope_text([{"op": "create_file", "relative_path": "a.py", "content": None}])
    ).status == STATUS_SCHEMA_INVALID


def test_a_path_is_accepted_as_written_or_not_at_all():
    """Strict means strict: this channel never repairs a path spelling."""
    for path in (
        "/etc/passwd",
        "../outside.py",
        "sub\\windows.py",
        "./main.py",
        "",
    ):
        assert parse_strict_worker_patch_envelope(
            _envelope_text([{**EDIT_MAIN, "relative_path": path}])
        ).status in {STATUS_SCHEMA_INVALID, STATUS_BOUND_EXCEEDED}, path


def test_an_over_long_path_is_rejected():
    assert parse_strict_worker_patch_envelope(
        _envelope_text([{**EDIT_MAIN, "relative_path": "a" * 2000 + ".py"}])
    ).status == STATUS_BOUND_EXCEEDED


# ── §10/§11/§35 bounds, and never truncation ──────────────────────────────────

def test_an_oversized_operation_list_is_rejected_whole():
    plan = [
        {**EDIT_MAIN, "relative_path": f"file{index}.py"}
        for index in range(MAX_ENVELOPE_OPERATIONS + 1)
    ]
    parse = parse_strict_worker_patch_envelope(_envelope_text(plan))

    assert parse.status == STATUS_BOUND_EXCEEDED
    # No partial envelope: trimming the tail would silently change the patch.
    assert parse.envelope is None


def test_an_operation_list_exactly_at_the_bound_is_accepted():
    plan = [
        {**EDIT_MAIN, "relative_path": f"file{index}.py"}
        for index in range(MAX_ENVELOPE_OPERATIONS)
    ]
    assert parse_strict_worker_patch_envelope(_envelope_text(plan)).status == (
        STATUS_VALID
    )


def test_an_oversized_operation_payload_is_rejected_whole():
    for key in ("target_snippet", "patched_snippet"):
        parse = parse_strict_worker_patch_envelope(
            _envelope_text([{**EDIT_MAIN, key: "x" * (MAX_OPERATION_PAYLOAD_CHARS + 1)}])
        )
        assert parse.status == STATUS_BOUND_EXCEEDED, key
        assert parse.envelope is None

    parse = parse_strict_worker_patch_envelope(
        _envelope_text(
            [{**CREATE_EXTRA, "content": "x" * (MAX_OPERATION_PAYLOAD_CHARS + 1)}]
        )
    )
    assert parse.status == STATUS_BOUND_EXCEEDED


def test_an_oversized_response_is_rejected_before_it_is_decoded():
    parse = parse_strict_worker_patch_envelope("{" + " " * MAX_ENVELOPE_RESPONSE_CHARS)
    assert parse.status == STATUS_BOUND_EXCEEDED


def test_the_operation_bound_matches_the_downstream_declared_change_bound():
    """Kept equal on purpose, pinned by a test instead of by an import.

    A plan with more operations than CHECK.1 can represent as declared changes
    is already unrepresentable downstream, so accepting one here would only
    defer the rejection.  The worker protocol stays free of a checker import.
    """
    assert MAX_ENVELOPE_OPERATIONS == MAX_DECLARED_CHANGES


# ── §17/§26/§36 semantic identity ─────────────────────────────────────────────

def test_key_order_and_whitespace_do_not_change_the_fingerprint():
    compact = json.dumps(
        {"schema_version": WORKER_PATCH_ENVELOPE_SCHEMA_VERSION, "patch_plan": [EDIT_MAIN]},
        separators=(",", ":"),
    )
    reordered_operation = {
        "patched_snippet": EDIT_MAIN["patched_snippet"],
        "target_snippet": EDIT_MAIN["target_snippet"],
        "relative_path": EDIT_MAIN["relative_path"],
        "op": EDIT_MAIN["op"],
    }
    spacious = json.dumps(
        {"patch_plan": [reordered_operation], "schema_version": WORKER_PATCH_ENVELOPE_SCHEMA_VERSION},
        indent=4,
    )

    first = parse_strict_worker_patch_envelope(compact).envelope
    second = parse_strict_worker_patch_envelope(spacious).envelope
    assert worker_patch_envelope_fingerprint(first) == (
        worker_patch_envelope_fingerprint(second)
    )


def test_the_existing_path_alias_resolves_to_one_identity():
    """``relative_path`` and ``file`` name the same target to the executor."""
    aliased = {key: value for key, value in EDIT_MAIN.items() if key != "relative_path"}
    aliased["file"] = EDIT_MAIN["relative_path"]

    canonical = parse_strict_worker_patch_envelope(_envelope_text([EDIT_MAIN])).envelope
    alias = parse_strict_worker_patch_envelope(_envelope_text([aliased])).envelope
    assert canonical.patch_plan_identity == alias.patch_plan_identity


def test_relative_path_wins_over_the_alias_exactly_as_the_executor_reads_it():
    both = {**EDIT_MAIN, "file": "somewhere_else.py"}
    canonical = parse_strict_worker_patch_envelope(_envelope_text([EDIT_MAIN])).envelope
    shadowed = parse_strict_worker_patch_envelope(_envelope_text([both])).envelope
    assert canonical.patch_plan_identity == shadowed.patch_plan_identity


def test_operation_order_changes_the_identity():
    """The executor applies operations in order, so order is semantic."""
    forward = parse_strict_worker_patch_envelope(
        _envelope_text([EDIT_MAIN, CREATE_EXTRA])
    ).envelope
    backward = parse_strict_worker_patch_envelope(
        _envelope_text([CREATE_EXTRA, EDIT_MAIN])
    ).envelope
    assert forward.patch_plan_identity != backward.patch_plan_identity


def test_a_changed_payload_changes_the_identity():
    changed = {**EDIT_MAIN, "patched_snippet": "VALUE = 3\n"}
    first = parse_strict_worker_patch_envelope(_envelope_text([EDIT_MAIN])).envelope
    second = parse_strict_worker_patch_envelope(_envelope_text([changed])).envelope
    assert first.patch_plan_identity != second.patch_plan_identity


def test_the_fingerprint_carries_no_clock_or_response_identifier():
    envelope = parse_strict_worker_patch_envelope(_envelope_text([EDIT_MAIN])).envelope
    assert worker_patch_envelope_fingerprint(envelope) == (
        worker_patch_envelope_fingerprint(envelope)
    )
    rebuilt = WorkerPatchEnvelope(
        schema_version=WORKER_PATCH_ENVELOPE_SCHEMA_VERSION,
        patch_plan=(dict(EDIT_MAIN),),
    )
    assert worker_patch_envelope_fingerprint(rebuilt) == (
        worker_patch_envelope_fingerprint(envelope)
    )


def test_a_value_that_is_not_a_plan_has_no_plan_identity():
    assert canonical_patch_plan_identity(None) is None
    assert canonical_patch_plan_identity("main.py") is None
    assert canonical_patch_plan_identity([]) is not None


# ── §14/§16/§37 one response, two parsers ─────────────────────────────────────

def test_strict_and_legacy_agreement_is_measured_semantically():
    """Both channels read the same response; agreement is by plan identity."""
    response = _envelope_text([EDIT_MAIN])
    legacy = _legacy_response([dict(reversed(list(EDIT_MAIN.items())))])

    record = compare_strict_and_legacy(response, legacy)

    assert record.strict_status == STATUS_VALID
    assert record.strict_available is True
    assert record.legacy_available is True
    assert record.provenance == PROVENANCE_STRICT
    # Key order differs between the two payloads; the semantics do not.
    assert record.semantic_agreement == AGREEMENT_AGREED
    assert record.strict_patch_plan_identity == record.legacy_patch_plan_identity


def test_a_deliberate_divergence_is_recorded_rather_than_resolved():
    response = _envelope_text([EDIT_MAIN])
    legacy = _legacy_response([{**EDIT_MAIN, "patched_snippet": "VALUE = 99\n"}])

    record = compare_strict_and_legacy(response, legacy)

    assert record.semantic_agreement == AGREEMENT_MISMATCH
    assert record.strict_patch_plan_identity != record.legacy_patch_plan_identity
    # Recording a mismatch is the whole action.  Nothing here picks a plan.
    assert record.authoritative_effect is False


def test_legacy_extracted_json_is_never_labelled_strict():
    response = "```json\n" + _envelope_text([EDIT_MAIN]) + "\n```"
    record = compare_strict_and_legacy(response, _legacy_response([EDIT_MAIN]))

    assert record.strict_available is False
    assert record.legacy_available is True
    assert record.provenance == PROVENANCE_LEGACY
    assert record.semantic_agreement == AGREEMENT_NOT_COMPARABLE
    assert record.envelope_fingerprint is None


def test_a_response_carrying_no_plan_at_all_is_no_patch_payload():
    record = compare_strict_and_legacy("I found nothing to patch.", {"summary": "none"})

    assert record.provenance == PROVENANCE_NONE
    assert record.strict_available is False
    assert record.legacy_available is False


def test_a_patch_candidate_only_payload_carries_no_plan_for_this_measurement():
    """Converting a candidate into a plan is the legacy path's own business."""
    legacy = {"summary": "s", "patch_candidate": {"relative_path": "main.py"}}
    record = compare_strict_and_legacy("prose", legacy)
    assert record.legacy_available is False
    assert record.provenance == PROVENANCE_NONE


def test_the_comparison_is_a_pure_function_of_the_response_it_was_given():
    response = _envelope_text([EDIT_MAIN])
    legacy = _legacy_response([EDIT_MAIN])
    first = compare_strict_and_legacy(response, legacy)
    second = compare_strict_and_legacy(response, legacy)
    assert first.as_dict() == second.as_dict()


def test_a_measurement_failure_can_never_interrupt_the_run_it_measures():
    class HostileMapping(Mapping):
        def __getitem__(self, key):
            raise RuntimeError("boom")

        def __iter__(self):
            raise RuntimeError("boom")

        def __len__(self):
            raise RuntimeError("boom")

    hostile = HostileMapping()
    # The measurement itself genuinely fails on this input...
    with pytest.raises(RuntimeError):
        compare_strict_and_legacy(_envelope_text([EDIT_MAIN]), hostile)
    # ...and the guarded entry point the wiring actually calls absorbs it.
    assert safe_compare_strict_and_legacy(_envelope_text([EDIT_MAIN]), hostile) is None
    # A merely unusual value is still measured rather than swallowed.
    assert safe_compare_strict_and_legacy(object(), None) is not None


def test_the_record_grants_no_authority():
    record = compare_strict_and_legacy(
        _envelope_text([EDIT_MAIN]), _legacy_response([EDIT_MAIN])
    )
    payload = record.as_dict()

    assert payload["authoritative_effect"] is False
    guardrails = payload["guardrails"]
    for declined in (
        "prose_parsed",
        "fenced_block_extracted",
        "balanced_brace_scanned",
        "first_object_selected",
        "regular_expression_used",
        "markdown_repaired",
        "output_truncated",
        "model_called",
        "model_repair_requested",
        "provider_sdk_imported",
        "network_call_performed",
        "repository_traversed",
        "validation_executed",
        "patch_applied",
        "patch_semantics_changed",
        "patch_selection_changed",
        "authoritative_effect",
    ):
        assert guardrails[declined] is False, declined
    assert guardrails["strict_one_object_protocol"] is True
    assert guardrails["human_approval_required"] is True


# ── §27 the record is identity, not payload ───────────────────────────────────

def test_the_record_carries_no_snippet_file_body_or_raw_response():
    response = (
        "Here is the patch:\n"
        + _envelope_text([{**CREATE_EXTRA, "content": "SECRET_TOKEN = 'abc'\n"}])
    )
    legacy = _legacy_response([{**CREATE_EXTRA, "content": "SECRET_TOKEN = 'abc'\n"}])
    rendered = json.dumps(compare_strict_and_legacy(response, legacy).as_dict())

    assert "SECRET_TOKEN" not in rendered
    assert "Here is the patch" not in rendered
    assert "VALUE = " not in rendered


def test_an_envelope_record_reports_identity_and_a_count_not_operations():
    envelope = parse_strict_worker_patch_envelope(
        _envelope_text([EDIT_MAIN, CREATE_EXTRA])
    ).envelope
    payload = envelope.as_dict()

    assert payload["operation_count"] == 2
    assert set(payload) == {
        "schema_version",
        "phase_id",
        "operation_count",
        "patch_plan_identity",
        "envelope_fingerprint",
    }
    assert "EXTRA = True" not in json.dumps(payload)


# ── §38 dogfood ───────────────────────────────────────────────────────────────

def test_the_dogfood_summary_counts_adoption_without_deciding_correctness():
    plan = [EDIT_MAIN]
    strict = compare_strict_and_legacy(_envelope_text(plan), _legacy_response(plan))
    fenced = compare_strict_and_legacy(
        "```json\n" + _envelope_text(plan) + "\n```", _legacy_response(plan)
    )
    nothing = compare_strict_and_legacy("no patch", {"summary": "s"})
    mismatch = compare_strict_and_legacy(
        _envelope_text(plan),
        _legacy_response([{**EDIT_MAIN, "patched_snippet": "VALUE = 99\n"}]),
    )

    summary = summarize_worker_patch_envelope_records(
        [record.as_dict() for record in (strict, fenced, nothing, mismatch)]
    )

    assert summary["records"] == 4
    assert summary["strict_valid_responses"] == 2
    assert summary["legacy_only_responses"] == 1
    assert summary["invalid_both_responses"] == 1
    assert summary["strict_legacy_mismatches"] == 1
    assert summary["strict_status_counts"][STATUS_VALID] == 2
    assert summary["strict_status_counts"][STATUS_SURROUNDING_PROSE_REJECTED] == 2
    assert summary["provenance_counts"][PROVENANCE_STRICT] == 2
    assert summary["provenance_counts"][PROVENANCE_LEGACY] == 1
    assert summary["provenance_counts"][PROVENANCE_NONE] == 1
    # Instrumentation only: no score, no confidence, no verdict.
    assert summary["authoritative_effect"] is False
    rendered = json.dumps(summary)
    for forbidden in ("confidence", "score", "trust", "quality", "verdict"):
        assert forbidden not in rendered


def test_an_older_bundle_without_the_record_stays_readable():
    record = load_worker_patch_envelope_record(None)
    assert record["strict_status"] is None
    assert record["provenance"] is None
    assert record["strict_available"] is False
    assert record["authoritative_effect"] is False

    summary = summarize_worker_patch_envelope_records([])
    assert summary["records"] == 0
    assert summary["strict_valid_responses"] == 0


def test_a_persisted_record_cannot_claim_an_authoritative_effect():
    forged = compare_strict_and_legacy(
        _envelope_text([EDIT_MAIN]), _legacy_response([EDIT_MAIN])
    ).as_dict()
    forged["authoritative_effect"] = True
    assert load_worker_patch_envelope_record(forged)["authoritative_effect"] is False


# ── §2/§22/§28/§29 the live wiring ────────────────────────────────────────────

def _run(repo: Path, plan, **kwargs) -> dict:
    return run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), plan, source="worker-decl-2a", **kwargs
    )


def test_an_enabled_shadow_persists_a_bounded_record_into_the_replay_bundle(
    repo, monkeypatch
):
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    response = _envelope_text([EDIT_MAIN])
    legacy = extract_json_block(response)
    record = compare_strict_and_legacy(response, legacy)

    result = _run(repo, [EDIT_MAIN], worker_patch_response=record)

    assert result["success"] is True
    persisted = _artifact(result)
    assert persisted is not None
    assert persisted["strict_status"] == STATUS_VALID
    assert persisted["provenance"] == PROVENANCE_STRICT
    assert persisted["authoritative_effect"] is False
    assert persisted["envelope_fingerprint"]
    assert "VALUE = " not in json.dumps(persisted)


def test_a_disabled_shadow_writes_no_envelope_artifact(repo, monkeypatch):
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    record = compare_strict_and_legacy(
        _envelope_text([EDIT_MAIN]), _legacy_response([EDIT_MAIN])
    )

    result = _run(repo, [EDIT_MAIN], worker_patch_response=record)

    assert result["success"] is True
    assert _artifact(result) is None


def test_an_unsupplied_record_leaves_the_bundle_exactly_as_it_was(repo, monkeypatch):
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    result = _run(repo, [EDIT_MAIN])
    assert _artifact(result) is None


def test_a_malformed_supplied_record_is_ignored_not_persisted(repo, monkeypatch):
    """Only a typed record is written; a raw mapping is not laundered into one."""
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    result = _run(
        repo,
        [EDIT_MAIN],
        worker_patch_response={"strict_status": "valid", "write_authority": True},
    )
    assert result["success"] is True
    assert _artifact(result) is None


def test_the_run_and_the_applied_patch_are_identical_with_the_flag_on(
    repo, tmp_path, monkeypatch
):
    """§22: measuring the response may not move the patch, the order or the result."""
    other = tmp_path / "other"
    other.mkdir()
    (other / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    plan = [EDIT_MAIN, CREATE_EXTRA]

    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    unobserved = _run(other, plan)

    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    observed = _run(
        repo,
        plan,
        worker_patch_response=compare_strict_and_legacy(
            _envelope_text(plan), _legacy_response(plan)
        ),
    )

    assert observed["success"] == unobserved["success"] is True
    assert observed["applied_ops"] == unobserved["applied_ops"]
    assert observed["diffs"] == unobserved["diffs"]
    assert observed["rollback_performed"] == unobserved["rollback_performed"]
    # The additive artifact is the only difference the flag makes to the run.
    assert set(observed) == set(unobserved)
    for path in (repo, other):
        assert (path / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"
        assert (path / "extra.py").read_text(encoding="utf-8") == "EXTRA = True\n"


def test_a_strict_legacy_mismatch_still_applies_the_caller_supplied_plan(
    repo, monkeypatch
):
    """§16: a recorded disagreement never selects a different patch."""
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    applied_plan = [EDIT_MAIN]
    record = compare_strict_and_legacy(
        _envelope_text([{**EDIT_MAIN, "patched_snippet": "VALUE = 99\n"}]),
        _legacy_response(applied_plan),
    )
    assert record.semantic_agreement == AGREEMENT_MISMATCH

    result = _run(repo, applied_plan, worker_patch_response=record)

    assert result["success"] is True
    # The plan the caller passed is the plan that ran — not the strict one.
    assert (repo / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    assert _artifact(result)["semantic_agreement"] == AGREEMENT_MISMATCH


def test_the_envelope_hands_the_existing_executor_its_own_operations(
    repo, monkeypatch
):
    """§7: the envelope wraps the existing payload; it does not restate it."""
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    envelope = parse_strict_worker_patch_envelope(
        _envelope_text([EDIT_MAIN, CREATE_EXTRA])
    ).envelope
    operations = envelope.patch_plan_operations()

    assert operations == [EDIT_MAIN, CREATE_EXTRA]
    result = _run(repo, operations)

    assert result["success"] is True
    assert (repo / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    assert (repo / "extra.py").read_text(encoding="utf-8") == "EXTRA = True\n"
