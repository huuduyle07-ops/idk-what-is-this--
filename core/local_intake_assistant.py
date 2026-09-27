"""INPUT.3 — optional local-model Intake Assistant.

The deterministic policy has already decided.  This module exists only so the
resulting conversation can sound like a person wrote it:

    CompletionDecision (frozen)
        -> tiny local prompt
        -> friendlier questions, summary, candidate wording

What the model may not do is enforced twice over.  Structurally, the response
schema has no field for a state, an owner, a readiness flag, a severity or a
resolution, so those claims have nowhere to land.  Procedurally, every parsed
response is passed through
:func:`~core.intake_assistant.enforce_assistance_boundary`, and any failure —
transport, malformed JSON, authority-claiming key, invented question anchor —
falls back to the deterministic assistant with the failure recorded.

    Local AI may improve the words.  It may not change the decision.

Local only.  INPUT.3 ships no cloud provider, no provider ranking, no
difficulty-based escalation and no local-to-cloud failover.  If the configured
local model is unavailable, deterministic assistance is used; nothing is
retried somewhere more expensive.

Why this is a much easier job than INPUT.2: the prompt carries the completion
state, the open needs and a compact task summary, and nothing else.  No
repository map, source file, project index, graph, benchmark, lesson, Dream
artifact or run history is ever sent, so the context stays small enough for a
4B-class model on a laptop.

The module is inert on import: the transport is imported lazily inside
:meth:`LocalIntakeAssistantClient.complete`.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any, Protocol, runtime_checkable

from core.goal_brief_projection import GoalBriefProjection
from core.intake_completion import CompletionDecision, MAX_DETAIL_CHARS
from core.intake_assistant import (
    ASSISTANCE_GENERATED,
    ASSISTANCE_STATUS_INVALID,
    ASSISTANCE_STATUS_OK,
    ASSISTANCE_STATUS_REJECTED,
    ASSISTANCE_STATUS_UNAVAILABLE,
    MAX_ASSISTANCE_QUESTIONS,
    MAX_FIELD_SUGGESTIONS,
    MAX_QUESTION_CHARS,
    MAX_SUGGESTION_CHARS,
    MAX_SUMMARY_CHARS,
    AssistanceQuestion,
    DeterministicIntakeAssistant,
    FieldSuggestion,
    IntakeAssistance,
    IntakeAssistanceRejected,
    enforce_assistance_boundary,
)
from core.json_utils import extract_json_block
from core.task_contract import TaskContract


PHASE_ID = "INPUT.3"
LOCAL_ASSISTANT_NAME = "local_model_intake_assistant"
INTAKE_ASSISTANCE_RESPONSE_SCHEMA_VERSION = "input_3_intake_assistance_response_v1"

# ── Operator configuration ────────────────────────────────────────────────────
INTAKE_ASSISTANT_MODEL_ENV = "INTAKE_ASSISTANT_MODEL"
INTAKE_ASSISTANT_HOST_ENV = "INTAKE_ASSISTANT_HOST"
INTAKE_ASSISTANT_TIMEOUT_ENV = "INTAKE_ASSISTANT_TIMEOUT_SECONDS"
INTAKE_ASSISTANT_NUM_CTX_ENV = "INTAKE_ASSISTANT_NUM_CTX"

#: The manual local contingency model.  One configured model, no ranking.
DEFAULT_INTAKE_ASSISTANT_MODEL = "qwen3.5:4b"
DEFAULT_INTAKE_ASSISTANT_TIMEOUT = 60

#: Deliberately far below INPUT.2's 16k window.  This job is phrasing, not
#: interpretation: the prompt is a few hundred tokens and the answer is a
#: handful of sentences, so a small window keeps a laptop model fast and cool.
DEFAULT_INTAKE_ASSISTANT_NUM_CTX = 4_096

#: Opt-in switch for the live local smoke.  The default suite never sets it.
LIVE_SMOKE_ENV_VAR = "RUN_LIVE_INTAKE_ASSISTANT_TESTS"

#: How much of the raw request is shown to the assistant.  The full text is
#: already preserved on the contract; the assistant only needs enough to write
#: a natural sentence.
MAX_ASSISTANT_PROMPT_CHARS = 600
MAX_ASSISTANT_LIST_ITEMS = 8

_AGENT_ERROR_PREFIX = "AGENT_ERROR:"

#: Response keys that would claim authority the assistant does not hold.  Their
#: mere presence fails the response closed.
FORBIDDEN_RESPONSE_KEYS: tuple[str, ...] = (
    "state",
    "owner",
    "ready",
    "ready_for_future_handoff",
    "handoff_blockers",
    "contract_present",
    "resolved",
    "resolution",
    "decision",
    "completion_state",
    "routing_allowed",
    "execution_allowed",
    "apply_allowed",
    "mode",
    "execution_mode",
    "provider",
    "model",
    "preservation",
    "preservation_status",
    "semantic_status",
    "semantic_evidence_status",
    "semantic_evidence_valid",
    "ambiguities",
    "missing_requirements",
    "required_before_handoff",
    "optional_improvements",
    "contradiction_reasons",
    "authority",
    "guardrails",
    "human_approval",
    "human_approval_required",
)

ALLOWED_RESPONSE_KEYS: tuple[str, ...] = ("summary", "questions", "field_suggestions")
#: Severity and provenance are policy facts, so the model may not send them.
ALLOWED_QUESTION_KEYS: tuple[str, ...] = ("need_id", "text")
ALLOWED_SUGGESTION_KEYS: tuple[str, ...] = ("field", "suggested_value")


INTAKE_ASSISTANT_SYSTEM_INSTRUCTION = """You are the Intake Assistant.

A deterministic policy has already decided whether this request is complete.
That decision is final and is not yours to make.

Your only job is wording:
  - write one short, natural question for each open need you are given
  - write one short sentence summarizing what was understood
  - optionally suggest candidate wording for a named missing field

You do not decide whether the request is ready.
You do not resolve an ambiguity by guessing what the user meant.
You do not invent facts, entities, file names, or requirements.
You do not choose modes, providers, models, or tools.
You do not solve or execute the task.

A suggestion is a suggestion. Never present one as something the user said.

Return exactly one JSON object and nothing else."""


class IntakeAssistantTransportError(RuntimeError):
    """The configured local assistant model could not be reached."""


class IntakeAssistanceInvalid(Exception):
    """The assistant's response was not a valid, non-authority structure."""


@runtime_checkable
class IntakeAssistantClient(Protocol):
    """One configured local model, one completion, raw text back."""

    @property
    def model_id(self) -> str:
        ...

    def complete(self, system_instruction: str, user_message: str) -> str:
        ...


# ── Request ───────────────────────────────────────────────────────────────────

def _bullets(values: tuple[str, ...]) -> str:
    if not values:
        return "  (none)"
    return "\n".join(f"  - {value}" for value in values[:MAX_ASSISTANT_LIST_ITEMS])


def build_intake_assistance_request(
    contract: TaskContract,
    decision: CompletionDecision,
    projection: GoalBriefProjection,
) -> str:
    """Build the whole prompt the local assistant sees.

    Everything outside this function's output is invisible to the model: no
    repository map, no source, no index, no graph, no benchmarks, no lessons,
    no Dream artifacts, no run history.
    """
    del projection  # canonical values are never restated back to the model

    request_text = " ".join(contract.raw_request.text.split())[:MAX_ASSISTANT_PROMPT_CHARS]

    needs: list[str] = []
    for need in decision.ambiguities:
        needs.append(f"{need.need_id} | unresolved meaning | {need.detail}")
    for item in decision.missing_requirements:
        severity = "needed" if item.required else "optional"
        needs.append(f"{item.need_id} | missing {item.field} ({severity}) | {item.reason}")

    constraints = tuple(
        f"({item.kind}) {item.text}"[:MAX_DETAIL_CHARS] for item in contract.constraints
    )

    return "\n".join(
        [
            "INTAKE STATE",
            f"  state: {decision.state}",
            f"  owner: {decision.owner or 'none'}",
            "",
            "REQUEST",
            f"  task type: {contract.task.type}",
            f"  subjects: {', '.join(contract.subject_values()) or '(none named)'}",
            f"  text: {request_text or '(empty)'}",
            "",
            "EXPLICIT CONSTRAINTS",
            _bullets(constraints),
            "",
            "OPEN NEEDS (write one question for each, keep the need_id exactly)",
            _bullets(tuple(needs)),
            "",
            "CONTRADICTIONS",
            _bullets(decision.contradiction_reasons),
            "",
            "RESPOND WITH ONE JSON OBJECT",
            '  {"summary": "one short sentence",',
            '   "questions": [{"need_id": "<exact id above>", "text": "<one question>"}],',
            '   "field_suggestions": [{"field": "<named missing field>", '
            '"suggested_value": "<candidate wording>"}]}',
            "",
            "Use only the need_ids listed above. Suggest nothing for a field that was "
            "not listed. Write in the same language as the request text.",
        ]
    )


# ── Response parsing ──────────────────────────────────────────────────────────

def _invalid(reason: str) -> IntakeAssistanceInvalid:
    return IntakeAssistanceInvalid(reason)


def _text(raw: Any, label: str, limit: int) -> str:
    if not isinstance(raw, str):
        raise _invalid(f"{label} must be a string")
    value = " ".join(raw.split())
    if not value:
        raise _invalid(f"{label} must not be empty")
    return value[:limit]


def _mapping(raw: Any, label: str, allowed: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _invalid(f"{label} must be an object")
    unknown = sorted(set(raw) - set(allowed))
    if unknown:
        raise _invalid(f"{label} carries unsupported keys: {', '.join(unknown)}")
    return raw


def parse_intake_assistance_response(
    text: str,
    decision: CompletionDecision,
    *,
    assistant_name: str = LOCAL_ASSISTANT_NAME,
) -> IntakeAssistance:
    """Parse one assistant response, strictly and fail-closed.

    Severity and provenance are taken from the deterministic decision rather
    than from the response, so a model cannot downgrade a needed field into an
    optional one or label its own guess as something the user said.
    """
    if not isinstance(text, str) or not text.strip():
        raise _invalid("the assistant returned an empty response")

    payload: Any
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        payload = extract_json_block(text)
    if not isinstance(payload, dict):
        raise _invalid("the assistant response must be a single JSON object")

    claimed = sorted(set(payload) & set(FORBIDDEN_RESPONSE_KEYS))
    if claimed:
        raise _invalid(
            f"the assistant tried to claim authority it does not have: {', '.join(claimed)}"
        )
    payload = _mapping(payload, "the assistant response", ALLOWED_RESPONSE_KEYS)

    summary = ""
    if payload.get("summary") is not None:
        summary = _text(payload["summary"], "summary", MAX_SUMMARY_CHARS)

    optional_by_need = {
        **{need.need_id: False for need in decision.ambiguities},
        **{item.need_id: not item.required for item in decision.missing_requirements},
    }

    raw_questions = payload.get("questions") or []
    if not isinstance(raw_questions, list):
        raise _invalid("questions must be a list")
    if len(raw_questions) > MAX_ASSISTANCE_QUESTIONS:
        raise _invalid("the assistant returned more questions than there are needs")

    questions: list[AssistanceQuestion] = []
    for entry in raw_questions:
        item = _mapping(entry, "a question", ALLOWED_QUESTION_KEYS)
        need_id = _text(item.get("need_id"), "question need_id", MAX_QUESTION_CHARS)
        if need_id not in optional_by_need:
            raise _invalid(f"question is anchored to unknown need {need_id!r}")
        questions.append(
            AssistanceQuestion(
                need_id=need_id,
                text=_text(item.get("text"), "question text", MAX_QUESTION_CHARS),
                provenance=ASSISTANCE_GENERATED,
                optional=optional_by_need[need_id],
            )
        )

    raw_suggestions = payload.get("field_suggestions") or []
    if not isinstance(raw_suggestions, list):
        raise _invalid("field_suggestions must be a list")
    if len(raw_suggestions) > MAX_FIELD_SUGGESTIONS:
        raise _invalid("the assistant returned more suggestions than the bound allows")

    suggestions: list[FieldSuggestion] = []
    for entry in raw_suggestions:
        item = _mapping(entry, "a field suggestion", ALLOWED_SUGGESTION_KEYS)
        try:
            suggestions.append(
                FieldSuggestion(
                    field=_text(item.get("field"), "suggestion field", 64),
                    suggested_value=_text(
                        item.get("suggested_value"), "suggested value", MAX_SUGGESTION_CHARS
                    ),
                    provenance=ASSISTANCE_GENERATED,
                )
            )
        except ValueError as error:
            raise _invalid(str(error)) from error

    return IntakeAssistance(
        assistant_name=assistant_name,
        summary=summary,
        questions=tuple(questions),
        field_suggestions=tuple(suggestions),
        generated_by_model=True,
        status=ASSISTANCE_STATUS_OK,
    )


# ── Assistant ─────────────────────────────────────────────────────────────────

def deterministic_assistance(
    contract: TaskContract,
    decision: CompletionDecision,
    projection: GoalBriefProjection,
    *,
    status: str,
) -> IntakeAssistance:
    """Deterministic assistance, tagged with why the model was not used."""
    baseline = DeterministicIntakeAssistant().assist(contract, decision, projection)
    return dataclasses.replace(baseline, status=status)


class LocalModelIntakeAssistant:
    """Phrasing help from one configured local model, or nothing at all.

    Every failure path lands on the deterministic assistant.  A missing model
    degrades the wording and never the decision, which is what makes the local
    model genuinely optional rather than quietly required.
    """

    def __init__(
        self,
        client: IntakeAssistantClient,
        *,
        name: str = LOCAL_ASSISTANT_NAME,
    ) -> None:
        self._client = client
        self._name = name
        self._call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_id(self) -> str:
        return getattr(self._client, "model_id", "")

    @property
    def call_count(self) -> int:
        return self._call_count

    def assist(
        self,
        contract: TaskContract,
        decision: CompletionDecision,
        projection: GoalBriefProjection,
    ) -> IntakeAssistance:
        """Return model-written wording, or the deterministic baseline."""
        request = build_intake_assistance_request(contract, decision, projection)

        self._call_count += 1
        try:
            raw = self._client.complete(INTAKE_ASSISTANT_SYSTEM_INSTRUCTION, request)
        except Exception:  # transport, provider, timeout — all the same to us
            return deterministic_assistance(
                contract, decision, projection, status=ASSISTANCE_STATUS_UNAVAILABLE
            )

        try:
            assistance = parse_intake_assistance_response(
                raw, decision, assistant_name=self._name
            )
        except (IntakeAssistanceInvalid, ValueError):
            return deterministic_assistance(
                contract, decision, projection, status=ASSISTANCE_STATUS_INVALID
            )

        try:
            return enforce_assistance_boundary(decision, projection, assistance)
        except IntakeAssistanceRejected:
            return deterministic_assistance(
                contract, decision, projection, status=ASSISTANCE_STATUS_REJECTED
            )


class ScriptedIntakeAssistantClient:
    """Test double replaying fixed responses, with no transport at all."""

    def __init__(self, responses: list[str], *, model_id: str = "scripted-intake") -> None:
        self._responses = list(responses)
        self._model_id = model_id
        self.requests: list[str] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    def complete(self, system_instruction: str, user_message: str) -> str:
        self.requests.append(user_message)
        del system_instruction
        if not self._responses:
            raise IntakeAssistantTransportError("the scripted client ran out of responses")
        return self._responses.pop(0)


# ── Opt-in local transport ────────────────────────────────────────────────────

def _positive_int(raw: str, default: int) -> int:
    text = (raw or "").strip()
    if not text:
        return default
    try:
        return max(1, int(text))
    except ValueError:
        return default


def resolve_intake_assistant_model_id(env: dict[str, str] | None = None) -> str:
    """Return the configured local assistant model id.

    Configuration only: this never compares, ranks, or selects between models.
    """
    source = os.environ if env is None else env
    configured = (source.get(INTAKE_ASSISTANT_MODEL_ENV) or "").strip()
    return configured or DEFAULT_INTAKE_ASSISTANT_MODEL


def resolve_intake_assistant_num_ctx(env: dict[str, str] | None = None) -> int:
    """Return the configured context window for the assistance call."""
    source = os.environ if env is None else env
    return _positive_int(
        source.get(INTAKE_ASSISTANT_NUM_CTX_ENV, ""), DEFAULT_INTAKE_ASSISTANT_NUM_CTX
    )


class LocalIntakeAssistantClient:
    """One local model over the existing Ollama transport, one completion.

    Inert until :meth:`complete` runs, so importing this module and building an
    assistant stay offline.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        num_ctx: int | None = None,
    ) -> None:
        self._model = (model or "").strip() or resolve_intake_assistant_model_id()
        self._base_url = base_url or os.environ.get(INTAKE_ASSISTANT_HOST_ENV) or None
        self._timeout = (
            timeout
            if timeout is not None
            else _positive_int(
                os.environ.get(INTAKE_ASSISTANT_TIMEOUT_ENV, ""),
                DEFAULT_INTAKE_ASSISTANT_TIMEOUT,
            )
        )
        self._num_ctx = num_ctx if num_ctx is not None else resolve_intake_assistant_num_ctx()

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def num_ctx(self) -> int:
        return self._num_ctx

    def complete(self, system_instruction: str, user_message: str) -> str:
        """Run one completion against the single configured local model."""
        # Imported here so importing this module and building an assistant stay
        # completely offline.
        from agents.ollama_client import OllamaClient

        client = OllamaClient(
            model=self._model,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        answer = client.generate(
            user_message,
            system_prompt=system_instruction,
            options={"num_ctx": self._num_ctx},
        )
        if isinstance(answer, str) and answer.startswith(_AGENT_ERROR_PREFIX):
            raise IntakeAssistantTransportError(answer)
        return answer


def build_live_intake_assistant(
    *,
    model: str | None = None,
    base_url: str | None = None,
    timeout: int | None = None,
    num_ctx: int | None = None,
) -> LocalModelIntakeAssistant:
    """Build the opt-in local Intake Assistant.

    One configured local model.  No provider choice, no cloud, no escalation
    and no failover: if this model is unavailable the assistant degrades to
    deterministic wording rather than looking somewhere more expensive.

    Constructing it contacts nothing.
    """
    return LocalModelIntakeAssistant(
        LocalIntakeAssistantClient(
            model=model, base_url=base_url, timeout=timeout, num_ctx=num_ctx
        )
    )
