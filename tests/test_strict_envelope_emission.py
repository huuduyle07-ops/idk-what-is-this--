"""WORKER.DECL.2A.1 — strict envelope emission adoption experiment.

WORKER.DECL.2A proved the channel and measured that nothing uses it.  This
phase changes the request behind an opt-in flag and measures again, and the
whole value of the number depends on four things staying true while it is
gathered:

    the legacy extractor still decides which patch runs,
    a strict rejection cannot fail the run,
    no model call is added, and
    the frozen parser is not loosened to make the number look better.

Every test here is about one of those, or about the delta being exactly the
output-format request and nothing else.  No model is called anywhere in this
file: a "worker response" is a fixture string, and every provider is a fake
that counts what it was asked for.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import core.run_lifecycle as run_lifecycle
import core.sleeping_consultant as sleeping_consultant
import scripts.run_patch_proposal_queue as queue
import scripts.strict_envelope_emission_baseline as baseline
from agents.model_stats import ModelStatsScope, record_model_call
from core.json_utils import extract_json_block
from core.strict_envelope_emission import (
    AGREEMENT_NOT_MEASURED,
    EMISSION_ARTIFACT_NAME,
    ENVIRONMENT_FLAG,
    LEGACY_STATUS_NO_PLAN,
    LEGACY_STATUS_NOT_MEASURED,
    LEGACY_STATUS_PLAN_AVAILABLE,
    PROVIDER_GOOGLE,
    PROVIDER_OLLAMA_HTTP,
    PROVIDER_UNKNOWN,
    STRATEGY_LEGACY_PROMPT,
    STRATEGY_PROVIDER_NATIVE_JSON,
    STRATEGY_STRICT_PROMPT,
    STRICT_ENVELOPE_PROMPT_BLOCK,
    STRICT_STATUS_NOT_MEASURED,
    STRICT_TRANSPORT_RULES,
    TRANSPORT_STRATEGIES,
    StrictEmissionDirective,
    StrictEnvelopeEmissionObservation,
    apply_strict_emission_to_prompt,
    is_strict_envelope_emission_enabled,
    load_strict_envelope_emission_observation,
    observe_strict_envelope_emission,
    patch_plan_is_the_declared_shape,
    requested_transport_strategy,
    safe_observe_strict_envelope_emission,
    strict_emission_client_kwargs,
    strict_emission_directive,
    strict_envelope_emission_guardrails,
    summarize_strict_envelope_emission_observations,
)
from core.worker_patch_envelope import (
    AGREEMENT_AGREED,
    AGREEMENT_MISMATCH,
    AGREEMENT_NOT_COMPARABLE,
    PROVENANCE_LEGACY,
    PROVENANCE_STRICT,
    STATUS_SURROUNDING_PROSE_REJECTED,
    STATUS_UNKNOWN_FIELD,
    STATUS_VALID,
    WORKER_PATCH_ENVELOPE_SCHEMA_VERSION,
    compare_strict_and_legacy,
)


# -- Fixtures -----------------------------------------------------------------

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


def _envelope_text(plan, **extra) -> str:
    return json.dumps(
        {
            "schema_version": WORKER_PATCH_ENVELOPE_SCHEMA_VERSION,
            "patch_plan": plan,
            **extra,
        },
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


def _fenced(plan) -> str:
    return (
        "Sure! Here is the patch:\n"
        "```json\n" + _envelope_text(plan) + "\n```\n"
        "Let me know if you'd like me to adjust anything."
    )


def _record(response_text: str, legacy_payload=None):
    if legacy_payload is None:
        legacy_payload = extract_json_block(response_text)
    return compare_strict_and_legacy(response_text, legacy_payload)


@pytest.fixture(autouse=True)
def _experiment_off_by_default(monkeypatch):
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)


@pytest.fixture(autouse=True)
def _quiet_brain_stamp(monkeypatch):
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


def _live_gemini_module():
    """The module object the code under test will actually resolve.

    `_generate_patch_payload` imports `run_gemini_request_2` inside the function,
    so it reads whatever `sys.modules["agents.gemini_client"]` holds at call
    time. Resolving the module the same way is what keeps the patch and the code
    under test pointed at one object, whatever an earlier suite left behind.

    This mattered concretely: `test_seed_lessons_from_proposals.py` used to
    raw-pop that entry without restoring it, after which a later
    `from agents.gemini_client import ...` built a *fresh* module object and a
    patch applied to the one captured at collection time was invisible — these
    tests passed standalone and failed only in a full-suite run. That leak is
    fixed (it now uses `monkeypatch.delitem`), but resolving through
    `sys.modules` remains the honest thing for the test to do.
    """
    import importlib

    return importlib.import_module("agents.gemini_client")


def _emission_artifact(result: dict) -> dict | None:
    path = Path(result["replay_dir"]) / EMISSION_ARTIFACT_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _enrolled(**kwargs) -> StrictEmissionDirective:
    return strict_emission_directive(
        PROVIDER_GOOGLE, patch_plan_is_declared_shape=True, **kwargs
    )


# -- S3 the flag --------------------------------------------------------------

@pytest.mark.parametrize(
    "raw", ["", "0", "off", "false", "no", "none", "legacy", "legacy_prompt"]
)
def test_the_experiment_is_off_unless_explicitly_enabled(raw):
    assert requested_transport_strategy(raw) == STRATEGY_LEGACY_PROMPT
    assert is_strict_envelope_emission_enabled(raw) is False


def test_an_unset_flag_is_off(monkeypatch):
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    assert is_strict_envelope_emission_enabled() is False
    monkeypatch.setenv(ENVIRONMENT_FLAG, "strict_prompt")
    assert is_strict_envelope_emission_enabled() is True


@pytest.mark.parametrize("raw", ["1", "on", "true", "yes", "prompt", "strict_prompt"])
def test_a_bare_truthy_flag_selects_the_narrower_prompt_only_arm(raw):
    assert requested_transport_strategy(raw) == STRATEGY_STRICT_PROMPT


@pytest.mark.parametrize("raw", ["native", "native_json", "provider_native_json"])
def test_the_native_value_selects_the_provider_native_arm(raw):
    assert requested_transport_strategy(raw) == STRATEGY_PROVIDER_NATIVE_JSON


def test_an_unrecognised_value_never_enrols_a_run():
    """A typo must not silently put a production run into an experiment."""
    for raw in ("strict", "STRICT_PROMPTT", "json", "schema", "yes please"):
        assert requested_transport_strategy(raw) == STRATEGY_LEGACY_PROMPT


# -- S5/S22/S23 the prompt-only delta ----------------------------------------

def test_the_flag_off_prompt_is_the_very_same_object():
    """S23: off is not 'a smaller change', it is no change at all."""
    prompt = "EXISTING PATCH PROMPT"
    directive = _enrolled(value=None)

    assert directive.strategy == STRATEGY_LEGACY_PROMPT
    assert apply_strict_emission_to_prompt(prompt, directive) is prompt
    assert apply_strict_emission_to_prompt(prompt, None) is prompt
    assert strict_emission_client_kwargs(directive) == {}
    assert strict_emission_client_kwargs(None) == {}


def test_the_strict_block_is_appended_and_changes_nothing_before_it():
    prompt = "[PATCH OUTPUT FORMAT - vibe]\nrules...\nEvery relative_path MUST stay inside the repo."
    result = apply_strict_emission_to_prompt(prompt, _enrolled(value="strict_prompt"))

    assert result.startswith(prompt)
    assert result != prompt
    # Nothing that was in the prompt was removed, reordered or rewritten.
    assert result[len(prompt):].lstrip().startswith("[STRICT PATCH ENVELOPE")


def test_the_strict_block_asks_for_one_object_and_nothing_else():
    block = STRICT_ENVELOPE_PROMPT_BLOCK
    for rule in STRICT_TRANSPORT_RULES:
        assert rule in block
    assert WORKER_PATCH_ENVELOPE_SCHEMA_VERSION in block
    assert '"patch_plan"' in block
    assert "No other top-level key is allowed." in block


def test_the_strict_block_adds_no_reasoning_planning_or_selection_instruction():
    """S5: the experimental variable is the output format, and only that."""
    lowered = STRICT_ENVELOPE_PROMPT_BLOCK.lower()
    for forbidden in (
        "think step",
        "reason",
        "chain of thought",
        "plan first",
        "confidence",
        "prefer",
        "choose the best",
        "temperature",
        "model",
    ):
        assert forbidden not in lowered, forbidden


def test_the_strict_block_reuses_the_repositorys_own_strict_output_wording():
    """S6: one convention, not a second one invented here."""
    from core import prompter

    scout = prompter.SCOUT_PROMPT.replace("{{", "{").replace("}}", "}")
    for rule in STRICT_TRANSPORT_RULES:
        assert rule in scout, rule


def test_the_strict_block_carries_no_scout_semantics():
    """S6: reuse the transport language, not the scout contract."""
    lowered = STRICT_ENVELOPE_PROMPT_BLOCK.lower()
    for scout_only in (
        "likely_files",
        "likely_symbols",
        "target_concepts",
        "request_type",
        "repo scout",
        "inventory",
    ):
        assert scout_only not in lowered, scout_only


def test_the_strict_block_asks_for_no_change_intent():
    """S37: WORKER.DECL.2B owns intent; this channel must not pre-empt it."""
    lowered = STRICT_ENVELOPE_PROMPT_BLOCK.lower()
    for later_phase_field in (
        "change_intent",
        "declared_changes",
        "pre_execution",
        "worker_declaration",
    ):
        assert later_phase_field not in lowered, later_phase_field


# -- S4 eligibility: patch semantics stay fixed -------------------------------

@pytest.mark.parametrize(
    "style", ["safe_minimal", "balanced", "", None, "unknown", 7, {"style": "vibe"}]
)
def test_a_style_that_does_not_already_declare_a_plan_is_never_enrolled(style):
    assert patch_plan_is_the_declared_shape(style) is False
    directive = strict_emission_directive(
        PROVIDER_GOOGLE,
        patch_plan_is_declared_shape=patch_plan_is_the_declared_shape(style),
        value="provider_native_json",
    )
    assert directive.strategy == STRATEGY_LEGACY_PROMPT
    assert directive.prompt_suffix == ""
    assert directive.response_mime_type is None


@pytest.mark.parametrize("style", ["vibe", "VIBE", "  vibe  "])
def test_a_style_that_already_declares_a_plan_is_enrolled(style):
    assert patch_plan_is_the_declared_shape(style) is True


def test_an_unknown_provider_family_stays_on_the_legacy_request():
    directive = strict_emission_directive(
        "some-new-vendor", patch_plan_is_declared_shape=True, value="strict_prompt"
    )
    assert directive.strategy == STRATEGY_LEGACY_PROMPT
    assert directive.provider_family == PROVIDER_UNKNOWN


def test_a_legacy_directive_can_never_smuggle_a_delta():
    with pytest.raises(ValueError):
        StrictEmissionDirective(
            strategy=STRATEGY_LEGACY_PROMPT,
            provider_family=PROVIDER_GOOGLE,
            prompt_suffix="do something",
        )
    with pytest.raises(ValueError):
        StrictEmissionDirective(
            strategy=STRATEGY_STRICT_PROMPT,
            provider_family=PROVIDER_GOOGLE,
            response_mime_type="application/json",
        )


# -- S7/S8/S29/S30 provider-native transport ----------------------------------

def test_a_provider_with_a_native_json_mode_gets_exactly_one_transport_argument():
    directive = _enrolled(value="provider_native_json")

    assert directive.strategy == STRATEGY_PROVIDER_NATIVE_JSON
    assert strict_emission_client_kwargs(directive) == {
        "response_mime_type": "application/json"
    }
    # The native arm still carries the same strict prompt: no provider is given
    # weaker envelope semantics than another.
    assert directive.prompt_suffix == STRICT_ENVELOPE_PROMPT_BLOCK


def test_a_provider_without_a_native_mode_keeps_the_prompt_only_arm():
    """S30: cross-provider compatibility, not a silent drop to legacy."""
    directive = strict_emission_directive(
        PROVIDER_OLLAMA_HTTP,
        patch_plan_is_declared_shape=True,
        value="provider_native_json",
    )
    assert directive.strategy == STRATEGY_STRICT_PROMPT
    assert directive.prompt_suffix == STRICT_ENVELOPE_PROMPT_BLOCK
    assert strict_emission_client_kwargs(directive) == {}


def test_every_arm_is_judged_by_the_same_frozen_parser():
    """S8: transport differs per provider; envelope semantics never do."""
    fenced = _fenced([EDIT_MAIN])
    for family in (PROVIDER_GOOGLE, PROVIDER_OLLAMA_HTTP):
        directive = strict_emission_directive(
            family, patch_plan_is_declared_shape=True, value="provider_native_json"
        )
        observation = observe_strict_envelope_emission(directive, _record(fenced))
        assert observation.strict_status == STATUS_SURROUNDING_PROSE_REJECTED


# -- S29/S35 the provider adapter ---------------------------------------------

class _FakeGeminiClient:
    """Counts requests and records the config each one carried."""

    def __init__(self, *_args, **_kwargs):
        self.models = self
        _FakeGeminiClient.calls = getattr(_FakeGeminiClient, "calls", [])

    def generate_content(self, *, model, contents, config):
        _FakeGeminiClient.calls.append({"model": model, "config": config})
        return type("R", (), {"text": '{"patch_plan": []}'})()


@pytest.fixture
def gemini(monkeypatch):
    """The provider adapter, resolved the way an importer would resolve it."""
    return _live_gemini_module()


@pytest.fixture
def fake_gemini(monkeypatch, gemini):
    _FakeGeminiClient.calls = []
    monkeypatch.setattr(gemini, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(gemini.genai, "Client", _FakeGeminiClient)
    return _FakeGeminiClient


def test_the_gemini_request_is_unchanged_when_no_media_type_is_asked_for(
    fake_gemini, gemini
):
    """S23/S24: with the experiment off the config is exactly today's."""
    gemini.run_gemini_request_2("prompt")

    assert len(fake_gemini.calls) == 1
    config = fake_gemini.calls[0]["config"]
    assert config.temperature == 0.0
    assert getattr(config, "response_mime_type", None) is None


def test_the_gemini_request_carries_the_media_type_when_asked(fake_gemini, gemini):
    """S29: the structured-output argument, on the same single request."""
    gemini.run_gemini_request_2(
        "prompt", **strict_emission_client_kwargs(_enrolled(value="native"))
    )

    assert len(fake_gemini.calls) == 1
    config = fake_gemini.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.temperature == 0.0


def test_the_native_transport_argument_adds_no_network_request(fake_gemini, gemini):
    """S35: an existing request is altered; none is added."""
    gemini.run_gemini_request_2("prompt")
    off_requests = len(fake_gemini.calls)

    fake_gemini.calls = []
    gemini.run_gemini_request_2(
        "prompt", **strict_emission_client_kwargs(_enrolled(value="native"))
    )
    assert len(fake_gemini.calls) == off_requests == 1


def test_the_model_identity_and_temperature_are_untouched_by_the_experiment(
    fake_gemini, gemini
):
    """S24: only the output-format delta, never the model or its sampling."""
    gemini.run_gemini_request_2("prompt")
    off = fake_gemini.calls[0]

    fake_gemini.calls = []
    gemini.run_gemini_request_2(
        "prompt", **strict_emission_client_kwargs(_enrolled(value="native"))
    )
    on = fake_gemini.calls[0]

    assert on["model"] == off["model"]
    assert on["config"].temperature == off["config"].temperature == 0.0


# -- S12/S25-S28 one response, two parsers, under the experiment --------------

def test_a_pure_envelope_response_is_valid_and_legacy_still_leads():
    """S25: strict valid, legacy recorded, agreement checked, nothing switched."""
    response = _envelope_text([EDIT_MAIN])
    record = _record(response)
    observation = observe_strict_envelope_emission(_enrolled(value="native"), record)

    assert observation.strict_status == STATUS_VALID
    assert observation.legacy_status == LEGACY_STATUS_PLAN_AVAILABLE
    assert observation.agreement_status == AGREEMENT_AGREED
    assert observation.envelope_fingerprint
    assert observation.authoritative_effect is False


def test_a_fenced_response_despite_the_strict_request_is_rejected(monkeypatch):
    """S26: useful adoption data, not a defect and not a repair trigger."""
    response = _fenced([EDIT_MAIN])
    record = _record(response)
    observation = observe_strict_envelope_emission(
        _enrolled(value="strict_prompt"), record
    )

    assert observation.strict_status == STATUS_SURROUNDING_PROSE_REJECTED
    assert observation.legacy_status == LEGACY_STATUS_PLAN_AVAILABLE
    assert record.provenance == PROVENANCE_LEGACY


def test_prose_around_the_object_despite_the_strict_request_is_rejected():
    """S27: same outcome, no second call, legacy result preserved."""
    response = (
        "I looked at the file and here is what I would change:\n"
        + _envelope_text([EDIT_MAIN])
        + "\nHope that helps."
    )
    observation = observe_strict_envelope_emission(
        _enrolled(value="strict_prompt"), _record(response)
    )
    assert observation.strict_status == STATUS_SURROUNDING_PROSE_REJECTED
    assert observation.legacy_status == LEGACY_STATUS_PLAN_AVAILABLE


def test_an_extra_authority_shaped_field_is_still_unknown_field():
    """S28/S39: the parser is not loosened to raise the adoption number."""
    response = _envelope_text([EDIT_MAIN], write_authority=True)
    observation = observe_strict_envelope_emission(
        _enrolled(value="native"), _record(response)
    )
    assert observation.strict_status == STATUS_UNKNOWN_FIELD
    assert observation.envelope_fingerprint is None


def test_an_extra_change_intent_field_is_still_unknown_field():
    """S37: WORKER.DECL.2B's field must keep failing until 2B adds it."""
    response = _envelope_text([EDIT_MAIN], change_intent={"summary": "x"})
    observation = observe_strict_envelope_emission(
        _enrolled(value="native"), _record(response)
    )
    assert observation.strict_status == STATUS_UNKNOWN_FIELD


# -- S13/S14/S15 agreement, and never a winner --------------------------------

def test_a_strict_legacy_mismatch_is_recorded_and_not_resolved():
    strict_plan = [{**EDIT_MAIN, "patched_snippet": "VALUE = 99\n"}]
    record = compare_strict_and_legacy(
        _envelope_text(strict_plan), _legacy_response([EDIT_MAIN])
    )
    observation = observe_strict_envelope_emission(_enrolled(value="native"), record)

    assert observation.agreement_status == AGREEMENT_MISMATCH
    assert observation.authoritative_effect is False
    # Nothing in the observation names a winner.
    serialized = json.dumps(observation.as_dict())
    for verdict_word in ("winner", "preferred", "selected", "chosen", "override"):
        assert verdict_word not in serialized


def test_an_invalid_strict_beside_a_valid_legacy_is_the_expected_case():
    """S14: the authoritative patch proceeds; the rejection is only recorded."""
    observation = observe_strict_envelope_emission(
        _enrolled(value="strict_prompt"), _record(_fenced([EDIT_MAIN]))
    )
    assert observation.strict_status == STATUS_SURROUNDING_PROSE_REJECTED
    assert observation.legacy_status == LEGACY_STATUS_PLAN_AVAILABLE


def test_a_valid_strict_beside_an_absent_legacy_plan_switches_no_authority():
    """S15: representable, recorded, and never opportunistically promoted."""
    response = _envelope_text([EDIT_MAIN])
    record = compare_strict_and_legacy(response, {"patch_candidate": {"file": "a.py"}})
    observation = observe_strict_envelope_emission(_enrolled(value="native"), record)

    assert record.provenance == PROVENANCE_STRICT
    assert observation.strict_status == STATUS_VALID
    assert observation.legacy_status == LEGACY_STATUS_NO_PLAN
    assert observation.agreement_status == AGREEMENT_NOT_COMPARABLE
    assert observation.authoritative_effect is False


# -- S16/S18 the observation --------------------------------------------------

def test_the_observation_records_transport_and_statuses_only():
    observation = observe_strict_envelope_emission(
        _enrolled(value="native"), _record(_envelope_text([EDIT_MAIN]))
    )
    record = observation.as_dict()

    assert record["provider_family"] == PROVIDER_GOOGLE
    assert record["transport_strategy"] == STRATEGY_PROVIDER_NATIVE_JSON
    assert record["strict_status"] == STATUS_VALID
    assert record["legacy_status"] == LEGACY_STATUS_PLAN_AVAILABLE
    assert record["agreement_status"] == AGREEMENT_AGREED
    assert record["authoritative_effect"] is False
    for absent in ("confidence", "score", "trust", "quality", "verdict", "correct"):
        assert absent not in json.dumps(record).lower().replace(
            "authoritative_effect", ""
        ), absent


def test_the_observation_carries_no_raw_response_prompt_or_snippet():
    """S18: no second unrestricted raw-response artifact."""
    secret = "AWS_SECRET_ACCESS_KEY = 'hunter2'\n"
    response = (
        "Here is the change I propose.\n"
        + _envelope_text(
            [{"op": "create_file", "relative_path": "keys.py", "content": secret}]
        )
        + "\nBe careful with it."
    )
    observation = observe_strict_envelope_emission(
        _enrolled(value="native"), _record(response)
    )
    serialized = json.dumps(observation.as_dict())

    assert secret not in serialized
    assert "hunter2" not in serialized
    assert "Be careful with it" not in serialized
    assert "keys.py" not in serialized
    assert STRICT_ENVELOPE_PROMPT_BLOCK not in serialized


def test_a_run_without_a_compatibility_record_is_reported_as_not_measured():
    observation = observe_strict_envelope_emission(_enrolled(value="native"), None)

    assert observation.strict_status == STRICT_STATUS_NOT_MEASURED
    assert observation.legacy_status == LEGACY_STATUS_NOT_MEASURED
    assert observation.agreement_status == AGREEMENT_NOT_MEASURED
    assert observation.envelope_fingerprint is None


def test_a_raw_mapping_is_never_laundered_into_a_measurement():
    observation = observe_strict_envelope_emission(
        _enrolled(value="native"), {"strict_status": "valid", "legacy_available": True}
    )
    assert observation.strict_status == STRICT_STATUS_NOT_MEASURED


def test_only_a_valid_strict_parse_may_carry_a_fingerprint():
    with pytest.raises(ValueError):
        StrictEnvelopeEmissionObservation(
            provider_family=PROVIDER_GOOGLE,
            transport_strategy=STRATEGY_STRICT_PROMPT,
            strict_status=STATUS_SURROUNDING_PROSE_REJECTED,
            legacy_status=LEGACY_STATUS_PLAN_AVAILABLE,
            agreement_status=AGREEMENT_NOT_COMPARABLE,
            envelope_fingerprint="deadbeef",
        )


def test_an_observation_failure_can_never_interrupt_the_run_it_observes():
    class Exploding:
        @property
        def strategy(self):
            raise RuntimeError("boom")

        provider_family = PROVIDER_GOOGLE

    assert safe_observe_strict_envelope_emission(Exploding(), None) is None


def test_the_observation_cannot_be_given_an_authoritative_effect():
    observation = observe_strict_envelope_emission(
        _enrolled(value="native"), _record(_envelope_text([EDIT_MAIN]))
    )
    with pytest.raises(AttributeError):
        observation.authoritative_effect = True  # type: ignore[misc]


# -- S17 the vocabulary -------------------------------------------------------

def test_the_transport_vocabulary_is_small_and_only_what_is_implemented():
    assert TRANSPORT_STRATEGIES == (
        STRATEGY_LEGACY_PROMPT,
        STRATEGY_STRICT_PROMPT,
        STRATEGY_PROVIDER_NATIVE_JSON,
    )
    # provider_native_schema is described by S17 but not implemented here, so it
    # is not in the vocabulary: a label must mean a code path that exists.
    assert "provider_native_schema" not in TRANSPORT_STRATEGIES


def test_every_requestable_strategy_is_reachable_and_nothing_else_is():
    """The advertised arms are exactly the ones the flag can select."""
    from core.strict_envelope_emission import REQUESTABLE_STRATEGIES

    reachable = {
        requested_transport_strategy(raw)
        for raw in (
            "",
            "0",
            "off",
            "typo",
            "1",
            "on",
            "prompt",
            "strict_prompt",
            "native",
            "native_json",
            "provider_native_json",
        )
    }
    assert reachable == {STRATEGY_LEGACY_PROMPT, *REQUESTABLE_STRATEGIES}
    assert STRATEGY_LEGACY_PROMPT not in REQUESTABLE_STRATEGIES
    assert set(REQUESTABLE_STRATEGIES) < set(TRANSPORT_STRATEGIES)


def test_provider_native_json_is_not_labelled_stronger_evidence():
    """S17: transport provenance carries no epistemic rank."""
    fenced = _fenced([EDIT_MAIN])
    native = observe_strict_envelope_emission(_enrolled(value="native"), _record(fenced))
    prompted = observe_strict_envelope_emission(
        _enrolled(value="strict_prompt"), _record(fenced)
    )
    assert native.strict_status == prompted.strict_status
    assert native.as_dict()["authoritative_effect"] is False

    guardrails = strict_envelope_emission_guardrails()
    assert guardrails["strict_parser_weakened"] is False
    assert guardrails["patch_authority_changed"] is False


# -- S19/S20 dogfood ----------------------------------------------------------

def _observation(strategy, family, record):
    return observe_strict_envelope_emission(
        StrictEmissionDirective(
            strategy=strategy,
            provider_family=family,
            prompt_suffix=(
                "" if strategy == STRATEGY_LEGACY_PROMPT else STRICT_ENVELOPE_PROMPT_BLOCK
            ),
        ),
        record,
    ).as_dict()


def test_the_summary_counts_by_provider_and_transport_strategy():
    records = [
        _observation(STRATEGY_STRICT_PROMPT, PROVIDER_GOOGLE, _record(_envelope_text([EDIT_MAIN]))),
        _observation(STRATEGY_STRICT_PROMPT, PROVIDER_GOOGLE, _record(_fenced([EDIT_MAIN]))),
        _observation(STRATEGY_LEGACY_PROMPT, PROVIDER_GOOGLE, _record(_fenced([EDIT_MAIN]))),
        _observation(
            STRATEGY_STRICT_PROMPT,
            PROVIDER_OLLAMA_HTTP,
            _record("no json at all here"),
        ),
    ]
    summary = summarize_strict_envelope_emission_observations(records)

    assert summary["records"] == 4
    assert summary["strict_valid"] == 1
    assert summary["legacy_only"] == 2
    assert summary["invalid_both"] == 1
    assert summary["strict_status_by_transport_strategy"][STRATEGY_STRICT_PROMPT] == {
        STATUS_SURROUNDING_PROSE_REJECTED: 2,
        STATUS_VALID: 1,
    }
    assert summary["strict_status_by_provider_family"][PROVIDER_OLLAMA_HTTP] == {
        STATUS_SURROUNDING_PROSE_REJECTED: 1
    }
    assert summary["legacy_status_counts"][LEGACY_STATUS_PLAN_AVAILABLE] == 3


def test_the_summary_counts_semantic_mismatches_without_resolving_them():
    mismatch = compare_strict_and_legacy(
        _envelope_text([{**EDIT_MAIN, "patched_snippet": "VALUE = 99\n"}]),
        _legacy_response([EDIT_MAIN]),
    )
    summary = summarize_strict_envelope_emission_observations(
        [_observation(STRATEGY_STRICT_PROMPT, PROVIDER_GOOGLE, mismatch)]
    )
    assert summary["semantic_mismatch"] == 1
    assert summary["authoritative_effect"] is False


def _tokens(value, seen=None):
    """Every key name in a nested summary, split into words."""
    words: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            words.extend(str(key).lower().split("_"))
            words.extend(_tokens(nested))
    elif isinstance(value, list):
        for nested in value:
            words.extend(_tokens(nested))
    return words


def test_the_summary_states_no_threshold_rate_or_verdict():
    """S20: we do not yet have data supporting a pass bar, so there is none."""
    summary = summarize_strict_envelope_emission_observations(
        [_observation(STRATEGY_STRICT_PROMPT, PROVIDER_GOOGLE, _record(_fenced([EDIT_MAIN])))]
    )
    words = set(_tokens(summary))
    for banned in (
        "threshold",
        "rate",
        "percent",
        "percentage",
        "ratio",
        "pass",
        "passed",
        "fail",
        "failed",
        "confidence",
        "score",
        "verdict",
        "ready",
        "adequate",
        "sufficient",
    ):
        assert banned not in words, banned
    assert strict_envelope_emission_guardrails()["adoption_threshold_enforced"] is False


def test_an_older_bundle_without_the_observation_stays_readable():
    empty = load_strict_envelope_emission_observation(None)
    assert empty["transport_strategy"] is None
    assert empty["authoritative_effect"] is False
    assert summarize_strict_envelope_emission_observations([])["records"] == 0


def test_a_persisted_observation_cannot_claim_an_authoritative_effect():
    loaded = load_strict_envelope_emission_observation(
        {
            "transport_strategy": STRATEGY_PROVIDER_NATIVE_JSON,
            "strict_status": STATUS_VALID,
            "authoritative_effect": True,
            "write_authority": True,
        }
    )
    assert loaded["authoritative_effect"] is False


# -- S21 the recorded baseline ------------------------------------------------

def test_the_baseline_classifies_recorded_responses_without_a_model_call(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "model_raw_response.txt").write_text(
        _envelope_text([EDIT_MAIN]), encoding="utf-8"
    )
    (tmp_path / "b" / "raw_model_response.txt").write_text(
        _fenced([EDIT_MAIN]), encoding="utf-8"
    )
    (tmp_path / "b" / "raw_model_attempt1.txt").write_text(
        "I cannot patch this safely.", encoding="utf-8"
    )

    report = baseline.summarize_recorded_baseline(tmp_path)

    assert report["responses_scanned"] == 3
    assert report["strict_valid"] == 1
    assert report["legacy_only"] == 1
    assert report["invalid_both"] == 1
    assert report["response_shape_counts"] == {
        baseline.SHAPE_FENCED_JSON: 1,
        baseline.SHAPE_NO_JSON_FOUND: 1,
        baseline.SHAPE_PURE_JSON_OBJECT: 1,
    }
    assert report["model_calls_performed"] == 0
    assert report["network_calls_performed"] == 0
    assert report["transport_strategy"] == STRATEGY_LEGACY_PROMPT


def test_the_baseline_shape_label_never_overrides_a_strict_status(tmp_path):
    """The legacy reader explains a rejection; it cannot undo one."""
    prose = "Here you go: " + _envelope_text([EDIT_MAIN])
    record = baseline.classify_recorded_response(prose)

    assert record["response_shape"] == baseline.SHAPE_PROSE_WRAPPED_JSON
    assert record["strict_status"] == STATUS_SURROUNDING_PROSE_REJECTED
    assert record["strict_valid"] is False
    assert record["legacy_plan_available"] is True


def test_the_baseline_reports_what_a_limit_dropped(tmp_path):
    """No silent caps: a bounded scan says how much it did not read."""
    for index in range(4):
        item = tmp_path / f"item{index}"
        item.mkdir()
        (item / "model_raw_response.txt").write_text(
            _envelope_text([EDIT_MAIN]), encoding="utf-8"
        )

    report = baseline.summarize_recorded_baseline(tmp_path, limit=2)
    assert report["responses_scanned"] == 2
    assert report["responses_dropped_by_limit"] == 1


# -- S31/S10/S11 the live queue site ------------------------------------------

class _CountingModel:
    """Stands in for the one patch-generation call the run already makes.

    It records into `ModelStatsScope` exactly as the real client does, so the
    S31 model-call count has two independent witnesses: this object's own call
    log, and the repository's own model-call recorder.
    """

    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def __call__(self, *, prompt, repo_path=None, **kwargs):
        self.calls.append({"prompt": prompt, "kwargs": dict(kwargs)})
        record_model_call(
            "gemma-4-31b-it", success=True, role="reviewer", provider="google"
        )
        return self.response


@pytest.fixture
def queue_case(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "_file_context", lambda temp_repo, case: "")
    repo = tmp_path / "case-repo"
    repo.mkdir()
    return repo, {"name": "case", "language": "python", "prompt": "fix it"}


def _run_queue_generation(monkeypatch, queue_case, response, *, flag):
    from core.strict_envelope_emission import strict_emission_directive as directive_for

    repo, case = queue_case
    model = _CountingModel(response)
    monkeypatch.setattr(_live_gemini_module(), "run_gemini_request_2", model)
    if flag is None:
        monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    else:
        monkeypatch.setenv(ENVIRONMENT_FLAG, flag)

    emission = directive_for(PROVIDER_GOOGLE, patch_plan_is_declared_shape=True)
    with ModelStatsScope() as stats:
        payload, raw = queue._generate_patch_payload(
            temp_repo=repo, item={"title": "t"}, case=case, emission=emission
        )
    return model, payload, raw, emission, stats


def test_the_queue_site_asks_for_nothing_extra_with_the_flag_off(
    monkeypatch, queue_case
):
    """S23: the flag-off request is the exact request this site always made."""
    model, payload, _raw, emission, _stats = _run_queue_generation(
        monkeypatch, queue_case, _fenced([EDIT_MAIN]), flag=None
    )

    assert len(model.calls) == 1
    assert model.calls[0]["kwargs"] == {}
    assert "STRICT PATCH ENVELOPE" not in model.calls[0]["prompt"]
    assert emission.strategy == STRATEGY_LEGACY_PROMPT
    assert payload["patch_plan"] == [EDIT_MAIN]


def test_the_queue_site_asks_for_the_envelope_with_the_flag_on(
    monkeypatch, queue_case
):
    model, _payload, _raw, emission, _stats = _run_queue_generation(
        monkeypatch, queue_case, _envelope_text([EDIT_MAIN]), flag="strict_prompt"
    )

    assert len(model.calls) == 1
    assert model.calls[0]["kwargs"] == {}
    prompt = model.calls[0]["prompt"]
    assert prompt.endswith(STRICT_ENVELOPE_PROMPT_BLOCK)
    # The site's own patch contract still reaches the model, ahead of the block.
    assert "Return ONLY valid JSON in this shape" in prompt
    assert "Do not touch forbidden_changed_files." in prompt
    assert emission.strategy == STRATEGY_STRICT_PROMPT


def test_the_queue_site_native_arm_adds_one_transport_argument(
    monkeypatch, queue_case
):
    model, _payload, _raw, emission, _stats = _run_queue_generation(
        monkeypatch, queue_case, _envelope_text([EDIT_MAIN]), flag="provider_native_json"
    )

    assert len(model.calls) == 1
    assert model.calls[0]["kwargs"] == {"response_mime_type": "application/json"}
    assert emission.strategy == STRATEGY_PROVIDER_NATIVE_JSON


@pytest.mark.parametrize(
    "flag", [None, "strict_prompt", "provider_native_json"]
)
def test_the_queue_site_makes_exactly_one_model_call_either_way(
    monkeypatch, queue_case, flag
):
    """S10/S31: model_call_delta = 0, counted two independent ways."""
    model, _payload, _raw, _emission, stats = _run_queue_generation(
        monkeypatch, queue_case, _fenced([EDIT_MAIN]), flag=flag
    )
    assert len(model.calls) == 1
    # The repository's own model-call recorder saw the same single attempt.
    assert len(stats) == 1
    assert stats[0]["role"] == "reviewer"


def test_a_strict_rejection_triggers_no_second_call_and_no_repair(
    monkeypatch, queue_case
):
    """S10/S11/S26: a rejected envelope is measured, never re-requested."""
    model, payload, raw, emission, _stats = _run_queue_generation(
        monkeypatch, queue_case, _fenced([EDIT_MAIN]), flag="provider_native_json"
    )
    observation = observe_strict_envelope_emission(emission, _record(raw, payload))

    assert observation.strict_status == STATUS_SURROUNDING_PROSE_REJECTED
    assert len(model.calls) == 1
    # And the authoritative payload is exactly what the legacy extractor made.
    assert payload["patch_plan"] == [EDIT_MAIN]


def test_the_same_response_feeds_the_same_legacy_payload_either_way(
    monkeypatch, queue_case
):
    """S33: identical response fixtures, identical authoritative payload."""
    response = _fenced([EDIT_MAIN, CREATE_EXTRA])
    _m1, off_payload, off_raw, _e1, _s1 = _run_queue_generation(
        monkeypatch, queue_case, response, flag=None
    )
    _m2, on_payload, on_raw, _e2, _s2 = _run_queue_generation(
        monkeypatch, queue_case, response, flag="provider_native_json"
    )

    assert off_payload == on_payload
    assert off_raw == on_raw
    assert off_payload["patch_plan"] == [EDIT_MAIN, CREATE_EXTRA]


def _draft_state():
    from core.agent_state import AgentState

    return AgentState(
        interface="agent",
        mode="reviewer",
        user_input="fix it",
        file_paths=[],
        primary_file=None,
        input_mode="project",
        language="python",
        task_type="bug_fix",
    )


def test_a_review_round_drops_the_drafts_transport_label(monkeypatch):
    """The refine call was never enrolled, so its response is not credited to one.

    `finalize_answer` measures whatever answer survived review. When a refine
    round replaces the draft, labelling that response `strict_prompt` would
    attribute it to a request that was never made.
    """
    import core.pipeline as pipeline

    monkeypatch.setenv(ENVIRONMENT_FLAG, "provider_native_json")
    state = _draft_state()
    state.strict_envelope_transport = _enrolled(value="native")
    assert state.strict_envelope_transport.applies is True

    monkeypatch.setattr(pipeline, "build_deepseek_review", lambda *a, **k: "review")
    monkeypatch.setattr(pipeline, "run_deepseek_review", lambda prompt: "critique")
    monkeypatch.setattr(pipeline, "build_refine_prompt", lambda *a, **k: "refine")
    monkeypatch.setattr(
        pipeline, "run_gemini_request", lambda prompt, files=None, **kw: "refined"
    )

    assert pipeline._run_one_review_round(state, "draft") == "refined"
    assert state.strict_envelope_transport is None

    observation = safe_observe_strict_envelope_emission(
        state.strict_envelope_transport, _record(_fenced([EDIT_MAIN]))
    )
    assert observation.transport_strategy == STRATEGY_LEGACY_PROMPT
    assert observation.provider_family == PROVIDER_UNKNOWN


def test_a_failed_review_round_keeps_the_drafts_transport_label(monkeypatch):
    """A refine that errors is discarded, so the draft's response is still measured."""
    import core.pipeline as pipeline

    monkeypatch.setenv(ENVIRONMENT_FLAG, "strict_prompt")
    state = _draft_state()
    state.strict_envelope_transport = _enrolled(value="strict_prompt")

    monkeypatch.setattr(pipeline, "build_deepseek_review", lambda *a, **k: "review")
    monkeypatch.setattr(pipeline, "run_deepseek_review", lambda prompt: "critique")
    monkeypatch.setattr(pipeline, "build_refine_prompt", lambda *a, **k: "refine")
    monkeypatch.setattr(
        pipeline,
        "run_gemini_request",
        lambda prompt, files=None, **kw: "AGENT_ERROR: nope",
    )

    assert pipeline._run_one_review_round(state, "draft") is None
    assert state.strict_envelope_transport.strategy == STRATEGY_STRICT_PROMPT


def test_the_dream_site_is_not_enrolled_and_records_the_legacy_arm(monkeypatch):
    """The dream prompt resolves to safe_minimal, where a plan is forbidden.

    Enrolling it would override a safety instruction, so it stays on the legacy
    request and contributes the experiment's control arm.
    """
    monkeypatch.setenv(ENVIRONMENT_FLAG, "provider_native_json")
    source = Path(sleeping_consultant.__file__).read_text(encoding="utf-8")
    assert "patch_plan_is_declared_shape=False" in source

    captured = {}

    def fake_model(*, prompt, repo_path=None, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = dict(kwargs)
        return _fenced([EDIT_MAIN])

    monkeypatch.setattr(sleeping_consultant, "run_gemini_request_2", fake_model)
    monkeypatch.setattr(
        sleeping_consultant, "run_control_structured", lambda query, repo_path: {}
    )
    monkeypatch.setattr(
        sleeping_consultant,
        "maybe_enrich_with_scout",
        lambda query, repo_path, control_result, force=False: control_result,
    )
    monkeypatch.setattr(
        sleeping_consultant,
        "inspect_repo_inventory",
        lambda repo_path: {"primary_language": "python"},
    )
    monkeypatch.setattr(
        sleeping_consultant,
        "hydrate_control_source_from_scout",
        lambda **kwargs: kwargs["control_result"],
    )

    emission = strict_emission_directive(
        PROVIDER_GOOGLE, patch_plan_is_declared_shape=False
    )
    sleeping_consultant._generate_patch_plan(".", {"kind": "bug"}, emission=emission)

    assert emission.strategy == STRATEGY_LEGACY_PROMPT
    assert captured["kwargs"] == {}
    assert "STRICT PATCH ENVELOPE" not in captured["prompt"]


# -- S23/S32/S33/S34 the lifecycle sink ---------------------------------------

def _run(repo: Path, plan, **kwargs) -> dict:
    return run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), plan, source="worker-decl-2a1", **kwargs
    )


def _observation_for(response: str, *, value: str) -> StrictEnvelopeEmissionObservation:
    return observe_strict_envelope_emission(_enrolled(value=value), _record(response))


def test_an_enabled_experiment_persists_the_observation_into_the_bundle(
    repo, monkeypatch
):
    monkeypatch.setenv(ENVIRONMENT_FLAG, "provider_native_json")
    result = _run(
        repo,
        [EDIT_MAIN],
        strict_envelope_emission=_observation_for(
            _envelope_text([EDIT_MAIN]), value="native"
        ),
    )

    assert result["success"] is True
    persisted = _emission_artifact(result)
    assert persisted is not None
    assert persisted["transport_strategy"] == STRATEGY_PROVIDER_NATIVE_JSON
    assert persisted["provider_family"] == PROVIDER_GOOGLE
    assert persisted["strict_status"] == STATUS_VALID
    assert persisted["authoritative_effect"] is False
    assert "VALUE = " not in json.dumps(persisted)


def test_an_unenrolled_site_still_records_the_control_arm(repo, monkeypatch):
    """S19: `legacy_prompt` rows are the baseline the experimental arms are read against."""
    monkeypatch.setenv(ENVIRONMENT_FLAG, "provider_native_json")
    directive = strict_emission_directive(
        PROVIDER_GOOGLE, patch_plan_is_declared_shape=False
    )
    assert directive.strategy == STRATEGY_LEGACY_PROMPT

    result = _run(
        repo,
        [EDIT_MAIN],
        strict_envelope_emission=observe_strict_envelope_emission(
            directive, _record(_fenced([EDIT_MAIN]))
        ),
    )

    persisted = _emission_artifact(result)
    assert persisted is not None
    assert persisted["transport_strategy"] == STRATEGY_LEGACY_PROMPT
    # The provider is still named, so the control arm is comparable per family.
    assert persisted["provider_family"] == PROVIDER_GOOGLE
    assert persisted["strict_status"] == STATUS_SURROUNDING_PROSE_REJECTED
    assert persisted["authoritative_effect"] is False


def test_a_disabled_experiment_writes_no_emission_artifact(repo, monkeypatch):
    """S23: flag off leaves the bundle exactly as it was."""
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    result = _run(
        repo,
        [EDIT_MAIN],
        strict_envelope_emission=_observation_for(
            _envelope_text([EDIT_MAIN]), value="native"
        ),
    )
    assert result["success"] is True
    assert _emission_artifact(result) is None


def test_a_malformed_supplied_observation_is_ignored_not_persisted(repo, monkeypatch):
    monkeypatch.setenv(ENVIRONMENT_FLAG, "strict_prompt")
    result = _run(
        repo,
        [EDIT_MAIN],
        strict_envelope_emission={
            "transport_strategy": "provider_native_json",
            "write_authority": True,
        },
    )
    assert result["success"] is True
    assert _emission_artifact(result) is None


def test_an_unsupplied_observation_leaves_the_bundle_as_it_was(repo, monkeypatch):
    monkeypatch.setenv(ENVIRONMENT_FLAG, "strict_prompt")
    assert _emission_artifact(_run(repo, [EDIT_MAIN])) is None


def test_the_applied_patch_is_identical_with_the_experiment_on(
    repo, tmp_path, monkeypatch
):
    """S33: same response fixture, same applied plan, order and result keys."""
    other = tmp_path / "other"
    other.mkdir()
    (other / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    plan = [EDIT_MAIN, CREATE_EXTRA]

    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    unobserved = _run(other, plan)

    monkeypatch.setenv(ENVIRONMENT_FLAG, "provider_native_json")
    observed = _run(
        repo,
        plan,
        strict_envelope_emission=_observation_for(_envelope_text(plan), value="native"),
    )

    assert observed["success"] == unobserved["success"] is True
    assert observed["applied_ops"] == unobserved["applied_ops"]
    assert observed["diffs"] == unobserved["diffs"]
    assert observed["rollback_performed"] == unobserved["rollback_performed"]
    assert set(observed) == set(unobserved)
    for path in (repo, other):
        assert (path / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"
        assert (path / "extra.py").read_text(encoding="utf-8") == "EXTRA = True\n"


def test_a_strict_rejection_does_not_fail_the_run(repo, monkeypatch):
    """The stop condition, stated as a test: rejection is data, not a verdict."""
    monkeypatch.setenv(ENVIRONMENT_FLAG, "strict_prompt")
    observation = _observation_for(_fenced([EDIT_MAIN]), value="strict_prompt")
    assert observation.strict_status == STATUS_SURROUNDING_PROSE_REJECTED

    result = _run(repo, [EDIT_MAIN], strict_envelope_emission=observation)

    assert result["success"] is True
    assert (repo / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_the_experiment_asks_the_apply_engine_for_the_same_validation(
    repo, tmp_path, monkeypatch
):
    """S32: validation delta is zero -- the same request, executed the same way."""
    seen: list[dict] = []
    real_apply = run_lifecycle.apply_patch_plan

    def recording_apply(*args, **kwargs):
        seen.append(
            {
                "validation_command": kwargs.get("validation_command"),
                "plan": kwargs.get("plan") or (args[1] if len(args) > 1 else None),
            }
        )
        return real_apply(*args, **kwargs)

    monkeypatch.setattr(run_lifecycle, "apply_patch_plan", recording_apply)

    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    off = _run(repo, [EDIT_MAIN])

    other = tmp_path / "second"
    other.mkdir()
    (other / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setenv(ENVIRONMENT_FLAG, "provider_native_json")
    on = _run(
        other,
        [EDIT_MAIN],
        strict_envelope_emission=_observation_for(
            _envelope_text([EDIT_MAIN]), value="native"
        ),
    )

    assert len(seen) == 2
    assert seen[0]["validation_command"] == seen[1]["validation_command"]
    assert seen[0]["plan"] == seen[1]["plan"] == [EDIT_MAIN]
    assert on.get("validation_ok") == off.get("validation_ok")
    assert on.get("validation_mode") == off.get("validation_mode")


# -- S38/S39 no checker, no authority -----------------------------------------

def test_the_experiment_promotes_no_checker():
    guardrails = strict_envelope_emission_guardrails()
    assert guardrails["checker_promoted"] is False
    assert guardrails["change_intent_declared"] is False
    assert guardrails["run_failed_by_strict_rejection"] is False
    assert guardrails["repair_call_added"] is False
    assert guardrails["model_call_added"] is False


def test_provider_native_json_creates_no_authority():
    """S39: a transport mode is not a permission."""
    response = _envelope_text(
        [EDIT_MAIN],
        write_authority=True,
        human_approved=True,
        validation_passed=True,
    )
    observation = observe_strict_envelope_emission(
        _enrolled(value="native"), _record(response)
    )
    assert observation.strict_status == STATUS_UNKNOWN_FIELD

    serialized = json.dumps(observation.as_dict())
    for authority_word in ("write_authority", "human_approved", "merge_allowed"):
        assert f'"{authority_word}": true' not in serialized
