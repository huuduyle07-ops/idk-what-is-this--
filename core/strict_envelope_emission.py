"""WORKER.DECL.2A.1 — strict envelope emission adoption experiment.

WORKER.DECL.2A built the channel: a frozen parser that accepts a worker patch
response only when the entire non-whitespace text decodes as exactly one JSON
object whose keys are an allow-list.  It then wired that parser in shadow at the
real patch-producing sites and measured what current providers actually emit.

The answer was ``surrounding_prose_rejected``, because nothing had asked them
for anything else.  The request was never changed; only the reader was added.

This module changes the request, and nothing else.  Behind one opt-in flag it
can ask an **already-happening** patch-generation call to return exactly one
bounded JSON object in the frozen envelope's shape, optionally using a
provider's own JSON transport argument on that same request, and it records
which strategy was used beside the strict/legacy statuses WORKER.DECL.2A
already produces.

What it deliberately does **not** do
------------------------------------

It adds no model call.  There is no formatting turn, no repair turn, no
verifier turn and no retry triggered by a strict rejection.  The directive this
module returns is consumed by a call the run was going to make anyway; the
boundary suite asserts this module reaches no provider, no network and no
subprocess.

It repairs nothing.  A response that ignores the request is measured as having
ignored it.  Fixing emission is the experiment; weakening the parser or
patching up its input would destroy the number the experiment exists to
produce.

It weakens no parser.  WORKER.DECL.2A's parser is imported and used exactly as
frozen — this module defines no parse status of its own, accepts no fence,
strips no prose, and never sees a response body.

It moves no authority.  The legacy extractor remains the authoritative source
of every applied patch plan, exactly as in WORKER.DECL.2A.  A strict rejection
cannot fail a run, cannot select a plan, and cannot reach the executor.  The
observation forces ``authoritative_effect`` to ``False`` structurally.

It changes no patch semantics.  The strict block is appended only where the
site's existing contract already declares a ``patch_plan`` as the shape being
asked for; where the existing policy prefers ``patch_candidate`` or forbids
``patch_plan`` outright, the site stays on ``legacy_prompt`` and says so.

It adds no ``change_intent``.  WORKER.DECL.2B owns that, and the frozen parser
must keep rejecting it as ``unknown_field`` until then.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.worker_patch_envelope import (
    AGREEMENT_MISMATCH,
    AGREEMENT_VALUES,
    PARSE_STATUSES,
    STATUS_VALID,
    WORKER_PATCH_ENVELOPE_SCHEMA_VERSION,
    WorkerPatchResponseCompatibility,
)


PHASE_ID = "WORKER.DECL.2A.1"
PRODUCER_KIND = "strict_envelope_emission_observation"

#: Version of the observation record persisted beside a run.
EMISSION_OBSERVATION_SCHEMA_VERSION = "worker_decl_2a1_emission_observation_v1"

#: Additive replay-bundle artifact.  A bundle written before this phase simply
#: does not carry the file.
EMISSION_ARTIFACT_NAME = "strict_envelope_emission.json"

#: Opt-in experimental flag.  Unset, empty or any off-like value means the
#: request is exactly the request WORKER.DECL.2A measured.
ENVIRONMENT_FLAG = "STRICT_WORKER_PATCH_ENVELOPE_EMISSION"


# -- Transport strategy vocabulary (S17) --------------------------------------
#
# Transport provenance, not epistemic strength.  ``provider_native_json`` is not
# better evidence than ``strict_prompt``; it only says how the same one-object
# request was expressed on the wire.

STRATEGY_LEGACY_PROMPT = "legacy_prompt"
STRATEGY_STRICT_PROMPT = "strict_prompt"
STRATEGY_PROVIDER_NATIVE_JSON = "provider_native_json"

TRANSPORT_STRATEGIES: tuple[str, ...] = (
    STRATEGY_LEGACY_PROMPT,
    STRATEGY_STRICT_PROMPT,
    STRATEGY_PROVIDER_NATIVE_JSON,
)

#: Strategies a caller may ask for.  ``legacy_prompt`` is the absence of the
#: experiment rather than an arm of it.
REQUESTABLE_STRATEGIES: tuple[str, ...] = (
    STRATEGY_STRICT_PROMPT,
    STRATEGY_PROVIDER_NATIVE_JSON,
)


# -- Provider families --------------------------------------------------------

PROVIDER_GOOGLE = "google"
PROVIDER_OLLAMA_HTTP = "ollama_http"
PROVIDER_OLLAMA_CHAT = "ollama_chat"
PROVIDER_UNKNOWN = "unknown"

PROVIDER_FAMILIES: tuple[str, ...] = (
    PROVIDER_GOOGLE,
    PROVIDER_OLLAMA_HTTP,
    PROVIDER_OLLAMA_CHAT,
    PROVIDER_UNKNOWN,
)

#: The response media type a provider family is asked for when
#: ``provider_native_json`` is requested *and* implemented for it.  A family
#: absent from this table keeps the prompt-only arm (S30): it is never dropped
#: back to ``legacy_prompt`` merely for lacking a native mode, and it is never
#: given weaker envelope semantics (S8) -- the same frozen parser judges it.
PROVIDER_NATIVE_JSON_MEDIA_TYPE: dict[str, str] = {
    PROVIDER_GOOGLE: "application/json",
}


# -- Legacy channel status vocabulary -----------------------------------------
#
# Derived from WORKER.DECL.2A's frozen record.  The legacy extractor is neither
# re-run nor re-implemented here; these are names for the one bit that record
# already carries.

LEGACY_STATUS_PLAN_AVAILABLE = "legacy_plan_available"
LEGACY_STATUS_NO_PLAN = "legacy_no_plan"
LEGACY_STATUS_NOT_MEASURED = "legacy_not_measured"

LEGACY_STATUSES: tuple[str, ...] = (
    LEGACY_STATUS_PLAN_AVAILABLE,
    LEGACY_STATUS_NO_PLAN,
    LEGACY_STATUS_NOT_MEASURED,
)

#: Recorded when the run produced no WORKER.DECL.2A compatibility record at all.
STRICT_STATUS_NOT_MEASURED = "not_measured"
AGREEMENT_NOT_MEASURED = "not_measured"


# -- Patch-shape eligibility (S4: patch semantics stay fixed) -----------------
#
# The strict envelope carries a ``patch_plan`` and nothing else.  Appending it
# to a prompt whose existing policy prefers ``patch_candidate`` -- or forbids
# ``patch_plan`` outright, as ``safe_minimal`` does -- would override a patch
# rule and a safety instruction, which is exactly what S4 keeps fixed.  So the
# experiment enrols a site only where a plan is already the declared shape.

#: Patch styles under which the existing policy already treats ``patch_plan`` as
#: the shape to produce.  ``safe_minimal`` forbids it; ``balanced`` prefers
#: ``patch_candidate`` and permits a plan only as a justified exception.
PATCH_PLAN_DECLARED_STYLES: frozenset[str] = frozenset({"vibe"})


def patch_plan_is_the_declared_shape(patch_style: Any) -> bool:
    """Does the existing patch policy already ask this site for a plan?

    Conservative by construction: an unknown, missing or unparseable style is
    not eligible, because this experiment may not be the thing that decides a
    patch is allowed to be multi-file.
    """
    if not isinstance(patch_style, str):
        return False
    return patch_style.strip().lower() in PATCH_PLAN_DECLARED_STYLES


# -- The output-format request (S5, S6) ---------------------------------------
#
# S6: reuse the repository's own strict-output wording rather than inventing a
# second convention.  These five rules are ``SCOUT_PROMPT``'s "OUTPUT FORMAT --
# STRICT" lines verbatim (a test pins them against ``core/prompter.py``), and
# only the transport language is reused: no scout semantics, no scout schema and
# no reasoning or planning instruction travels with them.

STRICT_TRANSPORT_RULES: tuple[str, ...] = (
    "- Return ONLY valid JSON.",
    "- Do NOT use Markdown.",
    "- Do NOT wrap the JSON in ```json or ``` fences.",
    "- Do NOT include any explanation, preface, or trailing text before or after the JSON.",
    "- The first character of your response MUST be `{` and the last character MUST be `}`.",
)

STRICT_ENVELOPE_PROMPT_BLOCK = "\n".join(
    (
        "",
        "[STRICT PATCH ENVELOPE - OUTPUT TRANSPORT ONLY]",
        "This section changes only the format your answer is transported in.",
        "The patch itself is unchanged: the same operations, the same paths, the",
        "same verbatim snippets, and every patch rule stated above still applies.",
        "",
        "OUTPUT FORMAT - STRICT:",
        *STRICT_TRANSPORT_RULES,
        "",
        "Return exactly one JSON object with exactly these two keys:",
        "{",
        '  "schema_version": "' + WORKER_PATCH_ENVELOPE_SCHEMA_VERSION + '",',
        '  "patch_plan": [',
        '    {"op": "create_file",     "relative_path": "...", "content": "..."},',
        '    {"op": "replace_snippet", "relative_path": "...",',
        '     "target_snippet": "...", "patched_snippet": "..."}',
        "  ]",
        "}",
        "",
        "- No other top-level key is allowed.",
        "- Do not add any field describing permission, approval, review,",
        "  validation, merge or authority; such a field is rejected by name.",
        "",
    )
)


# -- The directive a call site consumes ---------------------------------------

@dataclass(frozen=True, slots=True)
class StrictEmissionDirective:
    """How one already-scheduled patch-generation call should be expressed.

    Plain data on purpose.  It names a media type as a string and carries a
    prompt suffix as text; it holds no client, no config object and no provider
    type, so nothing here can import or reach a provider SDK.
    """

    strategy: str
    provider_family: str
    prompt_suffix: str = ""
    response_mime_type: str | None = None

    def __post_init__(self) -> None:
        if self.strategy not in TRANSPORT_STRATEGIES:
            raise ValueError(f"unsupported transport strategy: {self.strategy!r}")
        if self.provider_family not in PROVIDER_FAMILIES:
            raise ValueError(f"unsupported provider family: {self.provider_family!r}")
        if self.strategy == STRATEGY_LEGACY_PROMPT and (
            self.prompt_suffix or self.response_mime_type
        ):
            raise ValueError("legacy_prompt must request no delta at all")
        if self.response_mime_type is not None and (
            self.strategy != STRATEGY_PROVIDER_NATIVE_JSON
        ):
            raise ValueError(
                "only provider_native_json may carry a transport media type"
            )

    @property
    def applies(self) -> bool:
        """Is this call being asked for anything the run would not ask anyway?"""
        return self.strategy != STRATEGY_LEGACY_PROMPT

    @property
    def authoritative_effect(self) -> bool:
        """The request format never decides which patch a run applies."""
        return False


#: The one directive that asks for nothing.  Every off path returns exactly it.
LEGACY_EMISSION_DIRECTIVE = StrictEmissionDirective(
    strategy=STRATEGY_LEGACY_PROMPT,
    provider_family=PROVIDER_UNKNOWN,
)


def _legacy_directive(provider_family: str) -> StrictEmissionDirective:
    if provider_family == PROVIDER_UNKNOWN:
        return LEGACY_EMISSION_DIRECTIVE
    return StrictEmissionDirective(
        strategy=STRATEGY_LEGACY_PROMPT,
        provider_family=provider_family,
    )


# -- Flag resolution ----------------------------------------------------------

#: There is no off-list: anything that is not an arm is off.  ``""``, ``"0"``,
#: ``"off"``, ``"legacy_prompt"`` and a typo all mean the same thing, which is
#: the only safe default for a flag that enrols production runs.
_PROMPT_ALIASES = frozenset({"1", "on", "true", "yes", "prompt", STRATEGY_STRICT_PROMPT})
_NATIVE_ALIASES = frozenset({"native", "native_json", STRATEGY_PROVIDER_NATIVE_JSON})


def requested_transport_strategy(value: str | None = None) -> str:
    """Which arm the operator asked for, defaulting to no experiment at all.

    An unrecognised value resolves to ``legacy_prompt`` rather than raising or
    guessing: a typo must never silently enrol a production run in an
    experiment, and a bare truthy value gets the narrower prompt-only arm.
    """
    raw = os.environ.get(ENVIRONMENT_FLAG, "") if value is None else value
    normalized = str(raw or "").strip().lower()
    if normalized in _NATIVE_ALIASES:
        return STRATEGY_PROVIDER_NATIVE_JSON
    if normalized in _PROMPT_ALIASES:
        return STRATEGY_STRICT_PROMPT
    return STRATEGY_LEGACY_PROMPT


def is_strict_envelope_emission_enabled(value: str | None = None) -> bool:
    """Default off.  Off means the request is byte-identical to today's."""
    return requested_transport_strategy(value) != STRATEGY_LEGACY_PROMPT


def strict_emission_directive(
    provider_family: str,
    *,
    patch_plan_is_declared_shape: bool,
    value: str | None = None,
) -> StrictEmissionDirective:
    """Resolve what, if anything, this one call is asked to change.

    Three independent conditions must all hold before any delta exists: the
    operator opted in, the call reaches a provider family this phase knows how
    to address, and the site's existing patch contract already declares a plan
    as the shape being requested.  Any of them failing yields the do-nothing
    directive, which is recorded honestly as ``legacy_prompt``.
    """
    if provider_family not in PROVIDER_FAMILIES:
        provider_family = PROVIDER_UNKNOWN

    requested = requested_transport_strategy(value)
    if requested == STRATEGY_LEGACY_PROMPT:
        return _legacy_directive(provider_family)
    if not patch_plan_is_declared_shape:
        return _legacy_directive(provider_family)
    if provider_family == PROVIDER_UNKNOWN:
        return _legacy_directive(provider_family)

    media_type = PROVIDER_NATIVE_JSON_MEDIA_TYPE.get(provider_family)
    if requested == STRATEGY_PROVIDER_NATIVE_JSON and media_type:
        return StrictEmissionDirective(
            strategy=STRATEGY_PROVIDER_NATIVE_JSON,
            provider_family=provider_family,
            prompt_suffix=STRICT_ENVELOPE_PROMPT_BLOCK,
            response_mime_type=media_type,
        )

    # S30: a family with no native mode keeps the prompt-only arm rather than
    # losing the experiment, and the same frozen parser still judges it.
    return StrictEmissionDirective(
        strategy=STRATEGY_STRICT_PROMPT,
        provider_family=provider_family,
        prompt_suffix=STRICT_ENVELOPE_PROMPT_BLOCK,
    )


def apply_strict_emission_to_prompt(
    prompt: str,
    directive: StrictEmissionDirective | None,
) -> str:
    """Append the transport block, or hand back the very same prompt object.

    Nothing already in ``prompt`` is read, rewritten, reordered or removed: the
    existing patch contract, its policy rules and its safety instructions reach
    the model exactly as they do today, with the transport block after them.
    """
    if directive is None or not directive.applies or not directive.prompt_suffix:
        return prompt
    return prompt + "\n" + directive.prompt_suffix


def strict_emission_client_kwargs(
    directive: StrictEmissionDirective | None,
) -> dict[str, str]:
    """Provider transport keywords for this one call -- usually none at all.

    S23 asks for *exact* old provider arguments with the experiment off, so the
    off path returns an empty mapping and the call site spreads nothing: the
    invocation is argument-identical to the one this repository has always
    made, rather than merely carrying a new argument set to ``None``.

    S35: this only ever alters an existing request.  There is no second request
    to add a keyword to, and nothing here performs one.
    """
    if directive is None or not directive.applies or not directive.response_mime_type:
        return {}
    return {"response_mime_type": directive.response_mime_type}


# -- The observation (S16) ----------------------------------------------------

@dataclass(frozen=True, slots=True)
class StrictEnvelopeEmissionObservation:
    """How one experimental request was expressed, and how it was read.

    Statuses, provenance and a fingerprint -- never a response body, never a
    snippet, never a prompt.  It carries no confidence, no score, no rate and no
    correctness claim, and it decides nothing: the legacy payload the run
    already produced stays the applied patch whatever this says.
    """

    provider_family: str
    transport_strategy: str
    strict_status: str
    legacy_status: str
    agreement_status: str
    envelope_fingerprint: str | None = None
    schema_version: str = EMISSION_OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.provider_family not in PROVIDER_FAMILIES:
            raise ValueError(f"unsupported provider family: {self.provider_family!r}")
        if self.transport_strategy not in TRANSPORT_STRATEGIES:
            raise ValueError(
                f"unsupported transport strategy: {self.transport_strategy!r}"
            )
        if self.strict_status not in PARSE_STATUSES + (STRICT_STATUS_NOT_MEASURED,):
            raise ValueError(f"unsupported strict status: {self.strict_status!r}")
        if self.legacy_status not in LEGACY_STATUSES:
            raise ValueError(f"unsupported legacy status: {self.legacy_status!r}")
        if self.agreement_status not in AGREEMENT_VALUES + (AGREEMENT_NOT_MEASURED,):
            raise ValueError(f"unsupported agreement: {self.agreement_status!r}")
        if self.envelope_fingerprint is not None and self.strict_status != STATUS_VALID:
            raise ValueError(
                "only a valid strict parse may carry an envelope fingerprint"
            )

    @property
    def authoritative_effect(self) -> bool:
        """Structural, not a stored field: the experiment applies no patch."""
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_kind": PRODUCER_KIND,
            "phase_id": PHASE_ID,
            "provider_family": self.provider_family,
            "transport_strategy": self.transport_strategy,
            "strict_status": self.strict_status,
            "legacy_status": self.legacy_status,
            "agreement_status": self.agreement_status,
            "envelope_fingerprint": self.envelope_fingerprint,
            "authoritative_effect": self.authoritative_effect,
            "guardrails": strict_envelope_emission_guardrails(),
        }


def observe_strict_envelope_emission(
    directive: StrictEmissionDirective | None,
    compatibility: Any = None,
) -> StrictEnvelopeEmissionObservation:
    """Label an already-computed strict/legacy measurement with its transport.

    Nothing is parsed here.  ``compatibility`` is WORKER.DECL.2A's frozen record
    for the response the run already has; this only says which request produced
    it.  A run with no such record is reported as ``not_measured`` rather than
    assumed to have conformed.
    """
    strategy = (
        directive.strategy if directive is not None else STRATEGY_LEGACY_PROMPT
    )
    family = (
        directive.provider_family if directive is not None else PROVIDER_UNKNOWN
    )

    if not isinstance(compatibility, WorkerPatchResponseCompatibility):
        return StrictEnvelopeEmissionObservation(
            provider_family=family,
            transport_strategy=strategy,
            strict_status=STRICT_STATUS_NOT_MEASURED,
            legacy_status=LEGACY_STATUS_NOT_MEASURED,
            agreement_status=AGREEMENT_NOT_MEASURED,
        )

    return StrictEnvelopeEmissionObservation(
        provider_family=family,
        transport_strategy=strategy,
        strict_status=compatibility.strict_status,
        legacy_status=(
            LEGACY_STATUS_PLAN_AVAILABLE
            if compatibility.legacy_available
            else LEGACY_STATUS_NO_PLAN
        ),
        agreement_status=compatibility.semantic_agreement,
        envelope_fingerprint=compatibility.envelope_fingerprint,
    )


def safe_observe_strict_envelope_emission(
    directive: StrictEmissionDirective | None,
    compatibility: Any = None,
) -> StrictEnvelopeEmissionObservation | None:
    """Observe without ever being able to interrupt the run being observed."""
    try:
        return observe_strict_envelope_emission(directive, compatibility)
    except Exception:  # noqa: BLE001 - measurement failure is isolated
        return None


# -- Persistence and offline summary (S19, S20) -------------------------------

def load_strict_envelope_emission_observation(payload: Any) -> dict[str, Any]:
    """Read one persisted observation, defaulting anything an older bundle lacks."""
    if not isinstance(payload, Mapping):
        return {
            "schema_version": EMISSION_OBSERVATION_SCHEMA_VERSION,
            "record_kind": PRODUCER_KIND,
            "phase_id": PHASE_ID,
            "provider_family": None,
            "transport_strategy": None,
            "strict_status": None,
            "legacy_status": None,
            "agreement_status": None,
            "envelope_fingerprint": None,
            "authoritative_effect": False,
        }
    record = dict(payload)
    record.setdefault("schema_version", EMISSION_OBSERVATION_SCHEMA_VERSION)
    record.setdefault("record_kind", PRODUCER_KIND)
    record.setdefault("phase_id", PHASE_ID)
    for key in (
        "provider_family",
        "transport_strategy",
        "strict_status",
        "legacy_status",
        "agreement_status",
        "envelope_fingerprint",
    ):
        record.setdefault(key, None)
    record["authoritative_effect"] = False
    return record


def summarize_strict_envelope_emission_observations(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Count how the experiment went, per provider and per transport strategy.

    S20: there is no pass threshold here, and there is no rate.  Counts only --
    a human reads the distribution and decides whether adoption is good enough
    for WORKER.DECL.2B.  Nothing in this summary carries a confidence, a score
    or a verdict, and no branch anywhere reads it.
    """
    by_strategy: dict[str, dict[str, int]] = {}
    by_provider: dict[str, dict[str, int]] = {}
    by_strict_status: dict[str, int] = {}
    by_legacy_status: dict[str, int] = {}
    by_agreement: dict[str, int] = {}

    strict_valid = 0
    legacy_only = 0
    invalid_both = 0
    mismatches = 0

    def _bump(bucket: dict[str, dict[str, int]], key: Any, status: Any) -> None:
        if not isinstance(key, str) or not isinstance(status, str):
            return
        bucket.setdefault(key, {})
        bucket[key][status] = bucket[key].get(status, 0) + 1

    for raw in records:
        record = load_strict_envelope_emission_observation(raw)
        strict_status = record.get("strict_status")
        legacy_status = record.get("legacy_status")
        agreement = record.get("agreement_status")

        if isinstance(strict_status, str):
            by_strict_status[strict_status] = by_strict_status.get(strict_status, 0) + 1
        if isinstance(legacy_status, str):
            by_legacy_status[legacy_status] = by_legacy_status.get(legacy_status, 0) + 1
        if isinstance(agreement, str):
            by_agreement[agreement] = by_agreement.get(agreement, 0) + 1

        _bump(by_strategy, record.get("transport_strategy"), strict_status)
        _bump(by_provider, record.get("provider_family"), strict_status)

        if strict_status == STATUS_VALID:
            strict_valid += 1
        elif legacy_status == LEGACY_STATUS_PLAN_AVAILABLE:
            legacy_only += 1
        else:
            invalid_both += 1

        if agreement == AGREEMENT_MISMATCH:
            mismatches += 1

    return {
        "schema_version": EMISSION_OBSERVATION_SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "records": len(records),
        "strict_valid": strict_valid,
        "legacy_only": legacy_only,
        "invalid_both": invalid_both,
        "semantic_mismatch": mismatches,
        "strict_status_counts": dict(sorted(by_strict_status.items())),
        "legacy_status_counts": dict(sorted(by_legacy_status.items())),
        "agreement_counts": dict(sorted(by_agreement.items())),
        "strict_status_by_transport_strategy": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_strategy.items())
        },
        "strict_status_by_provider_family": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_provider.items())
        },
        "authoritative_effect": False,
    }


def strict_envelope_emission_guardrails() -> dict[str, bool]:
    """Every power this experiment declines."""
    return {
        "output_format_requested": True,
        "strict_parser_weakened": False,
        "prose_accepted": False,
        "fenced_block_accepted": False,
        "model_call_added": False,
        "repair_call_added": False,
        "formatting_call_added": False,
        "retry_on_strict_rejection": False,
        "network_call_added": False,
        "provider_sdk_imported": False,
        "strict_plan_applied": False,
        "patch_authority_changed": False,
        "patch_semantics_changed": False,
        "patch_schema_changed": False,
        "run_failed_by_strict_rejection": False,
        "validation_executed": False,
        "repository_traversed": False,
        "checker_promoted": False,
        "change_intent_declared": False,
        "adoption_threshold_enforced": False,
        "authoritative_effect": False,
        "human_approval_required": True,
    }


__all__ = [
    "PHASE_ID",
    "PRODUCER_KIND",
    "EMISSION_OBSERVATION_SCHEMA_VERSION",
    "EMISSION_ARTIFACT_NAME",
    "ENVIRONMENT_FLAG",
    "TRANSPORT_STRATEGIES",
    "REQUESTABLE_STRATEGIES",
    "STRATEGY_LEGACY_PROMPT",
    "STRATEGY_STRICT_PROMPT",
    "STRATEGY_PROVIDER_NATIVE_JSON",
    "PROVIDER_FAMILIES",
    "PROVIDER_GOOGLE",
    "PROVIDER_OLLAMA_HTTP",
    "PROVIDER_OLLAMA_CHAT",
    "PROVIDER_UNKNOWN",
    "PROVIDER_NATIVE_JSON_MEDIA_TYPE",
    "LEGACY_STATUSES",
    "LEGACY_STATUS_PLAN_AVAILABLE",
    "LEGACY_STATUS_NO_PLAN",
    "LEGACY_STATUS_NOT_MEASURED",
    "STRICT_STATUS_NOT_MEASURED",
    "AGREEMENT_NOT_MEASURED",
    "PATCH_PLAN_DECLARED_STYLES",
    "patch_plan_is_the_declared_shape",
    "STRICT_TRANSPORT_RULES",
    "STRICT_ENVELOPE_PROMPT_BLOCK",
    "StrictEmissionDirective",
    "LEGACY_EMISSION_DIRECTIVE",
    "requested_transport_strategy",
    "is_strict_envelope_emission_enabled",
    "strict_emission_directive",
    "apply_strict_emission_to_prompt",
    "strict_emission_client_kwargs",
    "StrictEnvelopeEmissionObservation",
    "observe_strict_envelope_emission",
    "safe_observe_strict_envelope_emission",
    "load_strict_envelope_emission_observation",
    "summarize_strict_envelope_emission_observations",
    "strict_envelope_emission_guardrails",
]
