"""INPUT.2 — Semantic Waiter model adapter.

One model call in, one :class:`~core.semantic_waiter.SemanticInterpretation`
out.  The adapter implements the frozen INPUT.1 ``SemanticInterpreter``
protocol; the protocol itself is unchanged.

Trust boundary
--------------

The model is an interpreter, not an authority.  It never produces the
authoritative Task Contract: it returns an intermediate semantic structure that
the existing deterministic INPUT.1 path converts and then gates.  Response keys
that would claim authority — routing, preservation status, execution mode,
provider, write/apply authority, human approval — are rejected outright.

Parsing is strict.  A malformed or authority-claiming response fails closed with
:class:`SemanticOutputInvalid`; there is no best-effort conversion from prose.

Cost boundary
-------------

The request carries the raw prompt and the deterministic explicit evidence, and
nothing else.  No project map, repository index, graph, lessons, benchmark
report, source file, test, or run history is ever sent.  This is intake
semantics, not repository reasoning.

This module is pure and transport-free: it never opens a socket.  The caller
supplies a :class:`SemanticModelClient`; see ``core.semantic_waiter_client`` for
the opt-in live one.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Protocol, runtime_checkable

from core.explicit_evidence import (
    CONSTRAINT_KINDS,
    FRAMEWORK_TYPES,
    OUTPUT_FORMATS,
    ExplicitEvidence,
)
from core.json_utils import extract_json_block
from core.semantic_waiter import SemanticInterpretation
from core.task_contract import (
    MAX_AMBIGUITIES,
    MAX_CONSTRAINTS,
    MAX_FRAMEWORK_VALUES,
    MAX_MISSING_INFORMATION,
    MAX_NOTES,
    MAX_RELATIONSHIPS,
    MAX_SUBJECTS,
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    PROVENANCES,
    RELATIONSHIP_TYPES,
    TASK_TYPES,
    Constraint,
    ExecutionRequirements,
    PreservationReport,
    Relationship,
    RequestedOutput,
    Subject,
    TaskClassification,
    UserSuppliedFramework,
)


PHASE_ID = "INPUT.2"
ADAPTER_NAME = "semantic_waiter_model_adapter"
SEMANTIC_RESPONSE_SCHEMA_VERSION = "input_2_semantic_response_v1"

#: Hard ceiling on how much raw prompt text is sent to the semantic model.
#: INPUT.1 keeps the untruncated original; the model only needs enough to read
#: the intent, and the explicit evidence travels separately and in full.
MAX_SEMANTIC_PROMPT_CHARS = 8_000
#: Ceiling on each evidence list rendered into the request.
MAX_REQUEST_EVIDENCE_ITEMS = 32

#: Top-level response keys the adapter accepts.
ALLOWED_RESPONSE_KEYS: tuple[str, ...] = (
    "task",
    "subjects",
    "relationships",
    "user_supplied_framework",
    "requested_output",
    "constraints",
    "ambiguities",
    "missing_information",
    "execution_requirements",
    "notes",
)

#: Top-level response keys that would claim authority the waiter does not have.
#: Their mere presence fails the response closed.
FORBIDDEN_RESPONSE_KEYS: tuple[str, ...] = (
    "routing_allowed",
    "preservation",
    "preservation_status",
    "mode",
    "execution_mode",
    "model",
    "provider",
    "read_authority",
    "write_authority",
    "apply_authority",
    "patch_authority",
    "human_approval",
    "human_approval_required",
    "guardrails",
)

SEMANTIC_WAITER_SYSTEM_INSTRUCTION = """You are the Semantic Waiter.

You only interpret the user's requested task.

You do not solve the task.
You do not inspect repositories.
You do not choose execution modes.
You do not recommend patches.
You do not call tools.
You do not choose downstream models.
You do not execute anything.

Return only the requested semantic structure, as a single JSON object and
nothing else.

Preserve explicitly supplied subjects, relationships, frameworks, rubric
values, constraints, and requested output requirements. When the request lists
EXPLICIT EVIDENCE, copy those literal strings into your answer character for
character; do not paraphrase, shorten, reorder, or merge them.

Distinguish what the user explicitly said from what you inferred:
  provenance "explicit" means the user literally supplied this text and it
  appears in the EXPLICIT EVIDENCE section;
  provenance "inferred" means you concluded it.
Never mark something explicit that is not in the EXPLICIT EVIDENCE section —
mark it inferred instead. An inferred value honestly labelled is always
better than a false explicit one.

Do not invent subjects, comparisons, rubrics, constraints, or requirements the
user did not ask for. If the request is ambiguous, say so in "ambiguities"
rather than guessing.

Never emit routing_allowed, preservation, mode, provider, model, any authority
field, or any human-approval decision."""


class SemanticWaiterError(Exception):
    """Base class for semantic interpretation failures."""


class SemanticModelUnavailable(SemanticWaiterError):
    """The configured semantic model could not be reached or produced nothing."""


class SemanticOutputInvalid(SemanticWaiterError):
    """The model's response was not a valid, non-authority semantic structure."""


@runtime_checkable
class SemanticModelClient(Protocol):
    """The narrow transport seam: text in, text out, one configured model.

    INPUT.2 deliberately keeps this smaller than a provider framework. The
    client does not choose a model, retry, fall back, or escalate — those are
    configuration and routing concerns, not semantic ones.
    """

    @property
    def model_id(self) -> str:
        """Identifier of the single configured model, for telemetry."""
        ...

    def complete(self, system_instruction: str, user_message: str) -> str:
        """Return the model's raw text response."""
        ...


# ── request building ──────────────────────────────────────────────────────────

def _bullets(values: Any, limit: int = MAX_REQUEST_EVIDENCE_ITEMS) -> str:
    items = list(values)[:limit]
    if not items:
        return "  (none)"
    return "\n".join(f"  - {item}" for item in items)


def _evidence_section(evidence: ExplicitEvidence) -> str:
    lines = [
        "EXPLICIT EVIDENCE (literal strings the user supplied; copy verbatim):",
        "named entities:",
        _bullets(evidence.named_entities),
        "comparison subjects:",
        _bullets(evidence.comparison_subjects()),
        "quoted terms:",
        _bullets(evidence.quoted_terms),
        "file paths:",
        _bullets(evidence.file_paths),
        "urls:",
        _bullets(evidence.urls),
        "list items:",
        _bullets(evidence.list_items),
    ]

    if evidence.framework is not None:
        lines.append(
            f"user-supplied {evidence.framework.type} values "
            f"({'ordered' if evidence.framework.ordered else 'unordered'}):"
        )
        lines.append(_bullets(evidence.framework.values))
    else:
        lines.append("user-supplied evaluation framework:")
        lines.append("  (none — do not invent one)")

    lines.append("constraints (kind :: exact text):")
    lines.append(
        _bullets(f"{item.kind} :: {item.text}" for item in evidence.constraints)
    )
    lines.append("requested output formats:")
    lines.append(_bullets(item.format for item in evidence.requested_outputs))
    return "\n".join(lines)


def _schema_section() -> str:
    return (
        "Respond with exactly one JSON object using these keys "
        f"({', '.join(ALLOWED_RESPONSE_KEYS)}):\n"
        '{\n'
        '  "task": {"type": "<one of: ' + " | ".join(TASK_TYPES) + '>", "confidence": 0.0},\n'
        '  "subjects": [{"value": "...", "provenance": "explicit|inferred", '
        '"confidence": 0.0, "role": "..."}],\n'
        '  "relationships": [{"type": "<one of: ' + " | ".join(RELATIONSHIP_TYPES) + '>", '
        '"subjects": ["...", "..."], "provenance": "explicit|inferred"}],\n'
        '  "user_supplied_framework": {"type": "<one of: ' + " | ".join(FRAMEWORK_TYPES) + '>", '
        '"values": ["..."], "provenance": "explicit|inferred", "ordered": true} or null,\n'
        '  "requested_output": {"format": "<one of: ' + " | ".join(OUTPUT_FORMATS) + '>", '
        '"provenance": "explicit|inferred"} or null,\n'
        '  "constraints": [{"kind": "<one of: ' + " | ".join(CONSTRAINT_KINDS) + '>", '
        '"text": "...", "provenance": "explicit|inferred"}],\n'
        '  "ambiguities": ["..."],\n'
        '  "missing_information": ["..."],\n'
        '  "execution_requirements": {"multi_stage": false, '
        '"external_information_required": false, '
        '"repository_inspection_required": false, "local_repository_required": false}\n'
        "}\n"
        "Omit no key. Use null or [] where nothing applies. Add no other key."
    )


def _prompt_section(raw_prompt: str) -> str:
    text = raw_prompt
    suffix = ""
    if len(text) > MAX_SEMANTIC_PROMPT_CHARS:
        text = text[:MAX_SEMANTIC_PROMPT_CHARS]
        suffix = "\n[prompt truncated for the semantic pass; explicit evidence is complete]"
    return f"USER REQUEST (verbatim):\n{text}{suffix}"


def prompt_was_truncated(raw_prompt: str) -> bool:
    """Whether the semantic pass saw less than the full prompt."""
    return len(raw_prompt) > MAX_SEMANTIC_PROMPT_CHARS


def build_interpretation_request(raw_prompt: str, evidence: ExplicitEvidence) -> str:
    """Build the first-attempt user message.

    Carries the prompt and the explicit evidence only — never repository
    context of any kind.
    """
    return "\n\n".join(
        (
            _prompt_section(raw_prompt),
            _evidence_section(evidence),
            _schema_section(),
        )
    )


def build_repair_request(
    raw_prompt: str,
    evidence: ExplicitEvidence,
    preservation: PreservationReport,
) -> str:
    """Build the single repair message from deterministic preservation evidence.

    The feedback is specific and bounded: what was lost, what must remain, and
    the same do-not-solve boundary. It is never a vague "try again".
    """
    missing = "\n".join(
        f"  - {item.kind}: {item.value}" for item in preservation.missing_items
    ) or "  (none)"
    reasons = "\n".join(f"  - {reason}" for reason in preservation.reasons) or "  (none)"

    lines = [
        "Your previous interpretation failed deterministic preservation checking.",
        "",
        "Missing or altered items:",
        missing,
        "",
        "Reasons:",
        reasons,
        "",
        "Explicit items that must remain represented, verbatim:",
        _bullets(evidence.comparison_subjects() or evidence.named_entities),
    ]

    if evidence.framework is not None:
        lines += [
            "",
            f"{evidence.framework.type} values that must remain represented, "
            "in this exact order:",
            _bullets(evidence.framework.values),
        ]

    if evidence.constraints:
        lines += [
            "",
            "Constraints that must remain represented with their exact text:",
            _bullets(f"{item.kind} :: {item.text}" for item in evidence.constraints),
        ]

    if evidence.requested_outputs:
        lines += [
            "",
            "Requested output formats that must remain represented:",
            _bullets(item.format for item in evidence.requested_outputs),
        ]

    lines += [
        "",
        "Mark an item explicit only if it appears above. Otherwise mark it inferred.",
        "Do not solve the user task. Return a corrected SemanticInterpretation only.",
        "",
        _prompt_section(raw_prompt),
        "",
        _schema_section(),
    ]
    return "\n".join(lines)


# ── strict response parsing ───────────────────────────────────────────────────

def _invalid(reason: str) -> SemanticOutputInvalid:
    return SemanticOutputInvalid(reason)


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _invalid(f"{label} must be a JSON object")
    return value


def _require_list(value: Any, label: str, limit: int) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _invalid(f"{label} must be a JSON array")
    if len(value) > limit:
        raise _invalid(f"{label} exceeds the bound of {limit}")
    return value


def _string_list(value: Any, label: str, limit: int) -> tuple[str, ...]:
    items = _require_list(value, label, limit)
    out: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise _invalid(f"{label} entries must be non-empty strings")
        out.append(item.strip())
    return tuple(out)


def _provenance(raw: Any, label: str) -> str:
    if raw is None:
        return PROVENANCE_INFERRED
    if raw not in PROVENANCES:
        raise _invalid(f"{label}: unsupported provenance {raw!r}")
    return str(raw)


def _confidence(raw: Any, provenance: str, label: str) -> float | None:
    # An explicit value is a quotation, not a probability. INPUT.1 rejects a
    # confidence there, so drop the model's number rather than fail the whole
    # response over a formatting habit; nothing is weakened, a false
    # probabilistic claim is simply removed.
    if provenance == PROVENANCE_EXPLICIT:
        return None
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise _invalid(f"{label}: confidence must be a number")
    value = float(raw)
    if not 0.0 <= value <= 1.0:
        raise _invalid(f"{label}: confidence must fall within 0.0 through 1.0")
    return value


def _text(raw: Any, label: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise _invalid(f"{label} must be a non-empty string")
    return raw.strip()


def _parse_task(raw: Any) -> TaskClassification:
    payload = _require_mapping(raw, "task")
    task_type = payload.get("type")
    if task_type not in TASK_TYPES:
        raise _invalid(f"task.type {task_type!r} is not a supported task type")
    # A task classification is never a user quotation; it is always the
    # interpreter's conclusion, whatever the model claims.
    return TaskClassification(
        type=str(task_type),
        provenance=PROVENANCE_INFERRED,
        confidence=_confidence(payload.get("confidence"), PROVENANCE_INFERRED, "task"),
    )


def _parse_subjects(raw: Any) -> tuple[Subject, ...]:
    out: list[Subject] = []
    for index, item in enumerate(_require_list(raw, "subjects", MAX_SUBJECTS)):
        payload = _require_mapping(item, f"subjects[{index}]")
        provenance = _provenance(payload.get("provenance"), f"subjects[{index}]")
        role = payload.get("role")
        out.append(
            Subject(
                value=_text(payload.get("value"), f"subjects[{index}].value"),
                provenance=provenance,
                confidence=_confidence(
                    payload.get("confidence"), provenance, f"subjects[{index}]"
                ),
                role=str(role) if isinstance(role, str) and role.strip() else None,
            )
        )
    return tuple(out)


def _parse_relationships(raw: Any) -> tuple[Relationship, ...]:
    out: list[Relationship] = []
    for index, item in enumerate(_require_list(raw, "relationships", MAX_RELATIONSHIPS)):
        payload = _require_mapping(item, f"relationships[{index}]")
        rel_type = payload.get("type")
        if rel_type not in RELATIONSHIP_TYPES:
            raise _invalid(f"relationships[{index}].type {rel_type!r} is not supported")
        subjects = _string_list(
            payload.get("subjects"), f"relationships[{index}].subjects", MAX_SUBJECTS
        )
        provenance = _provenance(payload.get("provenance"), f"relationships[{index}]")
        try:
            out.append(
                Relationship(
                    type=str(rel_type),
                    subjects=subjects,
                    provenance=provenance,
                    confidence=_confidence(
                        payload.get("confidence"), provenance, f"relationships[{index}]"
                    ),
                )
            )
        except ValueError as error:
            raise _invalid(f"relationships[{index}]: {error}") from error
    return tuple(out)


def _parse_framework(raw: Any) -> UserSuppliedFramework | None:
    if raw is None:
        return None
    payload = _require_mapping(raw, "user_supplied_framework")
    framework_type = payload.get("type")
    if framework_type not in FRAMEWORK_TYPES:
        raise _invalid(f"user_supplied_framework.type {framework_type!r} is not supported")
    values = _string_list(
        payload.get("values"), "user_supplied_framework.values", MAX_FRAMEWORK_VALUES
    )
    if not values:
        return None
    ordered = payload.get("ordered")
    return UserSuppliedFramework(
        type=str(framework_type),
        values=values,
        provenance=_provenance(payload.get("provenance"), "user_supplied_framework"),
        ordered=True if ordered is None else bool(ordered),
    )


def _parse_requested_output(raw: Any) -> RequestedOutput | None:
    if raw is None:
        return None
    payload = _require_mapping(raw, "requested_output")
    fmt = payload.get("format")
    if fmt is None:
        return None
    if fmt not in OUTPUT_FORMATS:
        raise _invalid(f"requested_output.format {fmt!r} is not supported")
    provenance = _provenance(payload.get("provenance"), "requested_output")
    return RequestedOutput(
        format=str(fmt),
        provenance=provenance,
        confidence=_confidence(payload.get("confidence"), provenance, "requested_output"),
    )


def _parse_constraints(raw: Any) -> tuple[Constraint, ...]:
    out: list[Constraint] = []
    for index, item in enumerate(_require_list(raw, "constraints", MAX_CONSTRAINTS)):
        payload = _require_mapping(item, f"constraints[{index}]")
        kind = payload.get("kind")
        if kind not in CONSTRAINT_KINDS:
            raise _invalid(f"constraints[{index}].kind {kind!r} is not supported")
        provenance = _provenance(payload.get("provenance"), f"constraints[{index}]")
        out.append(
            Constraint(
                kind=str(kind),
                text=_text(payload.get("text"), f"constraints[{index}].text"),
                provenance=provenance,
                confidence=_confidence(
                    payload.get("confidence"), provenance, f"constraints[{index}]"
                ),
            )
        )
    return tuple(out)


def _parse_execution_requirements(raw: Any) -> ExecutionRequirements:
    if raw is None:
        return ExecutionRequirements()
    payload = _require_mapping(raw, "execution_requirements")
    # Execution requirements are always the interpreter's own conclusion.
    return ExecutionRequirements(
        multi_stage=bool(payload.get("multi_stage", False)),
        external_information_required=bool(
            payload.get("external_information_required", False)
        ),
        repository_inspection_required=bool(
            payload.get("repository_inspection_required", False)
        ),
        local_repository_required=bool(payload.get("local_repository_required", False)),
        provenance=PROVENANCE_INFERRED,
        confidence=_confidence(
            payload.get("confidence"), PROVENANCE_INFERRED, "execution_requirements"
        ),
    )


def parse_semantic_response(text: str) -> SemanticInterpretation:
    """Parse a model response strictly, or fail closed.

    Accepts a bare JSON object or one fenced in a ```json block. Rejects prose,
    unknown keys, unsupported vocabulary values, out-of-range confidences,
    over-bound collections, and any key that would claim authority.
    """
    if not isinstance(text, str) or not text.strip():
        raise _invalid("the semantic model returned an empty response")

    payload: Any
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        payload = extract_json_block(text)

    if not isinstance(payload, dict):
        raise _invalid("the semantic response was not a single JSON object")

    claimed = [key for key in FORBIDDEN_RESPONSE_KEYS if key in payload]
    if claimed:
        raise _invalid(
            "the semantic response claimed authority it does not have: "
            + ", ".join(sorted(claimed))
        )

    unknown = sorted(set(payload) - set(ALLOWED_RESPONSE_KEYS))
    if unknown:
        raise _invalid("the semantic response contained unknown keys: " + ", ".join(unknown))

    if "task" not in payload:
        raise _invalid("the semantic response is missing the required 'task' key")

    try:
        return SemanticInterpretation(
            task=_parse_task(payload.get("task")),
            subjects=_parse_subjects(payload.get("subjects")),
            relationships=_parse_relationships(payload.get("relationships")),
            framework=_parse_framework(payload.get("user_supplied_framework")),
            requested_output=_parse_requested_output(payload.get("requested_output")),
            constraints=_parse_constraints(payload.get("constraints")),
            ambiguities=_string_list(payload.get("ambiguities"), "ambiguities", MAX_AMBIGUITIES),
            missing_information=_string_list(
                payload.get("missing_information"), "missing_information", MAX_MISSING_INFORMATION
            ),
            execution_requirements=_parse_execution_requirements(
                payload.get("execution_requirements")
            ),
            notes=_string_list(payload.get("notes"), "notes", MAX_NOTES),
        )
    except SemanticOutputInvalid:
        raise
    except (ValueError, TypeError) as error:
        raise _invalid(f"the semantic response violated a contract rule: {error}") from error


# ── the adapter ───────────────────────────────────────────────────────────────

class SemanticWaiterModelAdapter:
    """A model-backed Semantic Waiter.

    Implements the frozen INPUT.1 ``SemanticInterpreter`` protocol. Holds one
    configured client; never selects, retries, falls back to, or escalates to
    another model.
    """

    def __init__(self, client: SemanticModelClient, *, name: str = ADAPTER_NAME) -> None:
        self._client = client
        self._name = name
        self._call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_id(self) -> str:
        return str(getattr(self._client, "model_id", "unknown"))

    @property
    def call_count(self) -> int:
        return self._call_count

    def _complete(self, user_message: str) -> str:
        self._call_count += 1
        try:
            response = self._client.complete(
                SEMANTIC_WAITER_SYSTEM_INSTRUCTION, user_message
            )
        except SemanticWaiterError:
            raise
        except Exception as error:  # transport, auth, timeout, quota, ...
            raise SemanticModelUnavailable(
                f"the configured semantic model could not be reached: {error}"
            ) from error
        if not isinstance(response, str) or not response.strip():
            raise SemanticModelUnavailable(
                "the configured semantic model returned an empty response"
            )
        return response

    def interpret(
        self,
        raw_prompt: str,
        explicit_evidence: ExplicitEvidence,
    ) -> SemanticInterpretation:
        """First attempt: read the order and report what it means."""
        interpretation = parse_semantic_response(
            self._complete(build_interpretation_request(raw_prompt, explicit_evidence))
        )
        # OOP.INTENT.DESIGN.1: these typed literals belong to intake, so model
        # JSON cannot author or rewrite them.  Transport them beside its result
        # without changing the model schema, prompt, or number of calls.
        return replace(interpretation, design_evidence=explicit_evidence.design_evidence)

    def repair(
        self,
        raw_prompt: str,
        explicit_evidence: ExplicitEvidence,
        preservation: PreservationReport,
    ) -> SemanticInterpretation:
        """Single bounded repair attempt driven by deterministic gate evidence.

        Not part of the INPUT.1 protocol — the runner calls it directly, and
        only once.
        """
        interpretation = parse_semantic_response(
            self._complete(build_repair_request(raw_prompt, explicit_evidence, preservation))
        )
        return replace(interpretation, design_evidence=explicit_evidence.design_evidence)


class ScriptedSemanticModelClient:
    """Deterministic test client replaying canned responses in order.

    Lets the whole adapter, repair loop, and eval matrix run with no network.
    """

    def __init__(self, responses: list[str], *, model_id: str = "scripted-semantic-model") -> None:
        self._responses = list(responses)
        self._model_id = model_id
        self._calls: list[tuple[str, str]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def calls(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._calls)

    def complete(self, system_instruction: str, user_message: str) -> str:
        if not self._responses:
            raise SemanticModelUnavailable("the scripted semantic client ran out of responses")
        self._calls.append((system_instruction, user_message))
        return self._responses.pop(0)
