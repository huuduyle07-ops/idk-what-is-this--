"""EVIDENCE.1 — optional model-backed evidence analyzer.

One call in, one bounded :class:`~core.evidence_verification.EvidenceVerificationProposal`
out.  The adapter implements the :class:`~core.evidence_analyzer.EvidenceAnalyzer`
protocol; the protocol and the deterministic gate are unchanged by its presence.

Trust boundary
--------------

The model is an analyzer, not an authority — the pattern INPUT.2 already
validated.  It never produces the contractual outcome: it returns an
interpretation of bytes that the deterministic gate then re-derives against the
proposition, the receipt and the payload.  Response keys that would claim
authority — promotion, verification status, authority flags, routing, provider,
model, further acquisition, web search — are rejected outright, and so is any
numeric confidence, because a number is exactly how an unverified reading gets
laundered into a verified one.

Parsing is strict.  A malformed or authority-claiming response fails closed with
:class:`~core.evidence_analyzer.EvidenceAnalysisRejected`; there is no
best-effort reconstruction from prose.  Ordering inside enum lists is the single
normalization performed, because order carries no meaning in this schema — no
value is ever invented, dropped, deduplicated or substituted to make a response
parse.

Disclosure boundary
-------------------

Acquired source content is repository content.  Sending it to a cloud model is a
disclosure decision a human makes in configuration, never a side effect of
running a verification.  A client that declares itself cloud-hosted — or that
declines to declare its locality at all — is refused unless the operator
explicitly configured :data:`SOURCE_DISCLOSURE_CLOUD_APPROVED`, and a request
carrying ``local_analysis_only`` refuses a cloud client regardless.  That INPUT.2
happens to use a hosted model for intake semantics grants nothing here: intake
text and repository bytes are different material.

Provider boundary
-----------------

There is no provider framework.  One configured client, one call, one answer.
No model list, no cheap-then-strong escalation, no failover, no retry on a
disappointing relation.  Selecting a provider is a configuration act performed
before verification starts.

EVIDENCE.1 ships no live transport at all: this module defines the protocol and
a scripted client, so the entire test matrix runs offline with no network and no
model.  Any real client is supplied by a caller that implements
:class:`EvidenceModelClient`.

The module is pure and transport-free: it never opens a socket.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from core.evidence_analyzer import (
    EvidenceAnalysisError,
    EvidenceAnalysisRejected,
    EvidenceAnalyzerUnavailable,
)
from core.evidence_verification import (
    ANALYSIS_REASONS,
    CONSTRAINT_LOCAL_ANALYSIS_ONLY,
    MAX_ANALYSIS_REASONS,
    MAX_EVIDENCE_SPANS,
    PROPOSAL_SCHEMA_VERSION,
    RELATIONS,
    ROLE_STATUSES,
    SPAN_PURPOSES,
    BoundedPayloadView,
    EvidenceSpan,
    EvidenceVerificationProposal,
    EvidenceVerificationRequest,
    RoleAssessment,
)
from core.evidence_requirements import EVIDENCE_ROLES
from core.json_utils import extract_json_block


PHASE_ID = "EVIDENCE.1"
ADAPTER_NAME = "evidence_analyzer_model_adapter"
ANALYSIS_RESPONSE_SCHEMA_VERSION = "evidence_1_analysis_response_v1"

# ── Disclosure policy ─────────────────────────────────────────────────────────
LOCALITY_LOCAL = "local"
LOCALITY_CLOUD = "cloud"
LOCALITIES: tuple[str, ...] = (LOCALITY_LOCAL, LOCALITY_CLOUD)

#: The default.  Acquired repository bytes stay on the machine that acquired them.
SOURCE_DISCLOSURE_LOCAL_ONLY = "local_only"
#: An explicit operator decision, recorded in configuration before a run starts.
SOURCE_DISCLOSURE_CLOUD_APPROVED = "cloud_disclosure_approved"

SOURCE_DISCLOSURE_POLICIES: tuple[str, ...] = (
    SOURCE_DISCLOSURE_LOCAL_ONLY,
    SOURCE_DISCLOSURE_CLOUD_APPROVED,
)

#: How much of the acquired payload may be rendered into one analysis request.
MAX_ANALYZER_PROMPT_BYTES = 24_000
#: How many defects a single repair brief may carry.
MAX_REPAIR_DEFECTS = 8


class SourceDisclosureRefused(EvidenceAnalysisError):
    """Acquired source content would have been disclosed without approval."""


@runtime_checkable
class EvidenceModelClient(Protocol):
    """The narrowest possible transport: one configured model, raw text back.

    ``locality`` is not decoration.  The adapter refuses a client that declares
    ``cloud`` without approval, and treats a client that declares nothing as
    cloud, so an under-specified client fails closed rather than open.
    """

    @property
    def model_id(self) -> str:
        ...

    @property
    def locality(self) -> str:
        ...

    def complete(self, system_instruction: str, user_message: str) -> str:
        ...


# ── Response schema ───────────────────────────────────────────────────────────

ALLOWED_RESPONSE_KEYS: tuple[str, ...] = (
    "schema_version",
    "proposition_id",
    "proposition_sha256",
    "source_identifier",
    "source_content_sha256",
    "relation",
    "role_assessments",
    "evidence_spans",
    "reasons",
)

#: Keys whose mere presence fails the response closed.  Each names an authority
#: the analyzer does not have or a number this phase refuses to carry.
FORBIDDEN_RESPONSE_KEYS: tuple[str, ...] = (
    "acquire_more",
    "authority",
    "authority_status",
    "chain_of_thought",
    "claim",
    "claim_true",
    "claim_verified",
    "confidence",
    "evidence_promoted",
    "execution",
    "files_to_read",
    "guardrails",
    "human_approval",
    "human_approval_required",
    "likelihood",
    "model",
    "next_action",
    "patch_authority",
    "probability",
    "promotion",
    "promotion_status",
    "propose_proposition",
    "provider",
    "read_authority",
    "read_more_files",
    "reasoning",
    "routing",
    "score",
    "search_repository",
    "search_web",
    "support_score",
    "thinking",
    "tool_calls",
    "tools",
    "verification_status",
    "verified",
    "verified_evidence",
    "write_authority",
)

ALLOWED_ROLE_KEYS: tuple[str, ...] = ("role", "status", "span_indexes", "reasons")
ALLOWED_SPAN_KEYS: tuple[str, ...] = (
    "start_byte",
    "end_byte",
    "span_sha256",
    "purpose",
    "source_content_sha256",
    "quoted_text",
)


EVIDENCE_ANALYZER_SYSTEM_INSTRUCTION = """You are an Evidence Analyzer.

You are given ONE proposition and the exact bytes of ONE already-acquired source
file. Report only what those bytes establish about that exact proposition.

You MUST NOT:
- restate, reword, narrow, widen or replace the proposition
- assess any role other than the expected roles listed in the request
- name any source other than the one supplied
- ask for another file, a directory listing, a repository search or a web search
- claim that anything is verified, promoted, authoritative or approved
- report a confidence, probability, score or likelihood
- explain your reasoning in prose

Relation vocabulary, and nothing else:
- "supports": the bytes contain evidence for this exact proposition
- "contradicts": the bytes contain evidence incompatible with it
- "insufficient": the bytes are about this subject but do not establish it
- "unrelated": the bytes have no bearing on it

A file that simply never mentions the subject is "unrelated" or "insufficient".
It is NOT "contradicts": omission is not counter-evidence.

Absence of something in ONE file never establishes that it is absent from the
whole system.

Every "supports" and every "contradicts" must cite at least one byte span you
actually read, given as byte offsets into the supplied content.

Reply with exactly one JSON object and no other text."""


def _relation_line(values: tuple[str, ...]) -> str:
    return ", ".join(f'"{item}"' for item in values)


def _schema_section() -> str:
    return (
        "Reply with exactly this JSON object:\n"
        "{\n"
        f'  "schema_version": "{PROPOSAL_SCHEMA_VERSION}",\n'
        '  "proposition_id": "<copied verbatim from the request>",\n'
        '  "proposition_sha256": "<copied verbatim from the request>",\n'
        '  "source_identifier": "<copied verbatim from the request>",\n'
        '  "source_content_sha256": "<copied verbatim from the request>",\n'
        f"  \"relation\": one of {_relation_line(RELATIONS)},\n"
        '  "role_assessments": [\n'
        '    {"role": "<one expected role>", "status": '
        f"one of {_relation_line(ROLE_STATUSES)}, "
        '"span_indexes": [<indexes into evidence_spans>], '
        '"reasons": ["<reason code>"]}\n'
        "  ],\n"
        '  "evidence_spans": [\n'
        '    {"start_byte": <int>, "end_byte": <int>, "span_sha256": '
        '"<sha256 of those exact bytes>", "purpose": '
        f"one of {_relation_line(SPAN_PURPOSES)}, "
        '"source_content_sha256": "<copied verbatim>"}\n'
        "  ],\n"
        '  "reasons": ["<reason code>"]\n'
        "}\n\n"
        f"Reason codes, and nothing else: {_relation_line(ANALYSIS_REASONS)}.\n"
        f"At most {MAX_EVIDENCE_SPANS} spans and {MAX_ANALYSIS_REASONS} reasons.\n"
        "Cite whole lines: each line below is labelled with its exact byte range."
    )


def render_payload_window(view: BoundedPayloadView) -> tuple[str, bool]:
    """Render the acquired bytes with per-line byte ranges.

    Every line is labelled with the exact half-open byte range it occupies, so a
    citation can be copied rather than counted.  A miscounted range is not a
    disaster either: its digest will not match and the gate refuses it.
    """
    content = view.content
    truncated = len(content) > MAX_ANALYZER_PROMPT_BYTES
    window = content[:MAX_ANALYZER_PROMPT_BYTES]
    lines: list[str] = []
    start = 0
    while start < len(window):
        newline = window.find(b"\n", start)
        end = len(window) if newline < 0 else newline + 1
        text = window[start:end].decode("utf-8", errors="replace").rstrip("\n")
        lines.append(f"[{start},{end}] {text}")
        start = end
    if not lines:
        lines.append("[0,0] <empty source>")
    return "\n".join(lines), truncated


def build_analysis_request(
    request: EvidenceVerificationRequest,
    view: BoundedPayloadView,
) -> str:
    """The whole prompt: one proposition, one source, nothing else.

    No project map, index, graph, lesson store, benchmark report, sibling file or
    run history travels with it.  This is one source against one claim.
    """
    window, truncated = render_payload_window(view)
    expected = ", ".join(view.expected_roles) or "<none>"
    constraints = ", ".join(request.verification_constraints) or "<none>"
    return (
        "PROPOSITION\n"
        f"  proposition_id: {request.proposition.proposition_id}\n"
        f"  proposition_sha256: {request.proposition.proposition_sha256}\n"
        f"  proposition_type: {request.proposition.proposition_type}\n"
        f"  proposition_scope: {request.proposition.scope}\n"
        f"  text: {request.proposition.text}\n\n"
        "SOURCE\n"
        f"  source_identifier: {view.candidate_identifier}\n"
        f"  source_content_sha256: {view.content_sha256}\n"
        f"  byte_count: {view.byte_count}\n"
        f"  expected_roles: {expected}\n"
        f"  rendered_window_truncated: {str(truncated).lower()}\n\n"
        "VERIFICATION CONSTRAINTS\n"
        f"  {constraints}\n\n"
        "SOURCE CONTENT (byte ranges are exact)\n"
        f"{window}\n\n"
        f"{_schema_section()}\n"
    )


def build_repair_request(
    request: EvidenceVerificationRequest,
    view: BoundedPayloadView,
    defects: tuple[str, ...],
) -> str:
    """One repair brief: the exact structural defects, and nothing else.

    Not "try harder" and not "reconsider your conclusion" — the analyzer is told
    what was structurally wrong and is asked for the same analysis in a valid
    shape.  There is no second repair.
    """
    listed = "\n".join(f"  - {item}" for item in defects[:MAX_REPAIR_DEFECTS])
    return (
        "Your previous answer was rejected for structural reasons only.\n"
        "Do not change your findings to make them acceptable; restate the same\n"
        "analysis in a valid shape.\n\n"
        "DEFECTS\n"
        f"{listed}\n\n"
        f"{build_analysis_request(request, view)}"
    )


# ── Strict parsing ────────────────────────────────────────────────────────────

def _rejected(reason: str) -> EvidenceAnalysisRejected:
    return EvidenceAnalysisRejected(reason)


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _rejected(f"{label} must be a JSON object")
    return value


def _require_list(value: Any, label: str, limit: int) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _rejected(f"{label} must be a JSON array")
    if len(value) > limit:
        raise _rejected(f"{label} exceeds its finite bound")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _rejected(f"{label} must be a non-empty string")
    return value


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _rejected(f"{label} must be an integer")
    return value


def _canonical_enum_tuple(
    values: list[Any],
    vocabulary: tuple[str, ...],
    label: str,
) -> tuple[str, ...]:
    """Normalize order, never membership.

    Order carries no meaning in this schema, so sorting is not a repair.  An
    unknown or duplicated value is a different matter and fails closed.
    """
    seen: set[str] = set()
    for item in values:
        text = _require_str(item, f"{label} entry")
        if text not in vocabulary:
            raise _rejected(f"unsupported {label}: {text!r}")
        if text in seen:
            raise _rejected(f"{label} {text!r} was stated more than once")
        seen.add(text)
    return tuple(item for item in vocabulary if item in seen)


def _reject_forbidden_keys(payload: dict[str, Any], label: str) -> None:
    for key in payload:
        if key in FORBIDDEN_RESPONSE_KEYS:
            raise _rejected(
                f"{label} carries {key!r}, which would claim authority the analyzer "
                "does not have"
            )


def _parse_role_assessment(raw: Any) -> RoleAssessment:
    payload = _require_mapping(raw, "role assessment")
    _reject_forbidden_keys(payload, "a role assessment")
    unknown = set(payload) - set(ALLOWED_ROLE_KEYS)
    if unknown:
        raise _rejected(
            f"role assessment carries unsupported keys: {sorted(unknown)}"
        )
    role = _require_str(payload.get("role"), "role")
    if role not in EVIDENCE_ROLES:
        raise _rejected(f"unsupported evidence role: {role!r}")
    status = _require_str(payload.get("status"), "role status")
    if status not in ROLE_STATUSES:
        raise _rejected(f"unsupported role status: {status!r}")
    indexes = _require_list(payload.get("span_indexes"), "span_indexes", MAX_EVIDENCE_SPANS)
    seen_indexes: set[int] = set()
    for item in indexes:
        index = _require_int(item, "span index")
        if index < 0:
            raise _rejected("a span index may not be negative")
        if index in seen_indexes:
            raise _rejected(f"span index {index} was cited more than once")
        seen_indexes.add(index)
    parsed_indexes = tuple(sorted(seen_indexes))
    reasons = _canonical_enum_tuple(
        _require_list(payload.get("reasons"), "role reasons", MAX_ANALYSIS_REASONS),
        ANALYSIS_REASONS,
        "role reason",
    )
    try:
        return RoleAssessment(
            role=role,
            status=status,
            span_indexes=parsed_indexes,
            reasons=reasons,
        )
    except (TypeError, ValueError) as error:
        raise _rejected(f"invalid role assessment: {error}") from error


def _parse_span(raw: Any) -> EvidenceSpan:
    payload = _require_mapping(raw, "evidence span")
    _reject_forbidden_keys(payload, "an evidence span")
    unknown = set(payload) - set(ALLOWED_SPAN_KEYS)
    if unknown:
        raise _rejected(f"evidence span carries unsupported keys: {sorted(unknown)}")
    purpose = _require_str(payload.get("purpose"), "span purpose")
    if purpose not in SPAN_PURPOSES:
        raise _rejected(f"unsupported span purpose: {purpose!r}")
    quoted = payload.get("quoted_text")
    if quoted is not None and not isinstance(quoted, str):
        raise _rejected("quoted_text must be a string when present")
    try:
        return EvidenceSpan(
            start_byte=_require_int(payload.get("start_byte"), "span start_byte"),
            end_byte=_require_int(payload.get("end_byte"), "span end_byte"),
            span_sha256=_require_str(payload.get("span_sha256"), "span digest"),
            purpose=purpose,
            source_content_sha256=_require_str(
                payload.get("source_content_sha256"),
                "span source content digest",
            ),
            quoted_text=quoted,
        )
    except (TypeError, ValueError) as error:
        raise _rejected(f"invalid evidence span: {error}") from error


def parse_analysis_response(text: str) -> EvidenceVerificationProposal:
    """Turn one model response into a structurally valid proposal, or refuse.

    Structural only.  Whether the proposal names the *right* proposition and the
    *right* source is re-derived by the deterministic gate against records this
    parser never sees, so there is exactly one place that owns binding.
    """
    if not isinstance(text, str) or not text.strip():
        raise EvidenceAnalyzerUnavailable("the analyzer returned an empty response")
    payload = extract_json_block(text)
    if payload is None:
        raise _rejected("the analyzer response contained no JSON object")
    payload = _require_mapping(payload, "the analyzer response")
    _reject_forbidden_keys(payload, "the analyzer response")
    unknown = set(payload) - set(ALLOWED_RESPONSE_KEYS)
    if unknown:
        raise _rejected(f"the analyzer response carries unsupported keys: {sorted(unknown)}")

    schema_version = payload.get("schema_version", PROPOSAL_SCHEMA_VERSION)
    if schema_version != PROPOSAL_SCHEMA_VERSION:
        raise _rejected(f"unsupported analysis response schema: {schema_version!r}")

    relation = _require_str(payload.get("relation"), "relation")
    if relation not in RELATIONS:
        raise _rejected(f"unsupported proposition relation: {relation!r}")

    spans = tuple(
        _parse_span(item)
        for item in _require_list(
            payload.get("evidence_spans"), "evidence_spans", MAX_EVIDENCE_SPANS
        )
    )
    assessments = tuple(
        _parse_role_assessment(item)
        for item in _require_list(
            payload.get("role_assessments"), "role_assessments", len(EVIDENCE_ROLES)
        )
    )
    assessments = tuple(
        sorted(assessments, key=lambda item: EVIDENCE_ROLES.index(item.role))
    )
    reasons = _canonical_enum_tuple(
        _require_list(payload.get("reasons"), "reasons", MAX_ANALYSIS_REASONS),
        ANALYSIS_REASONS,
        "analysis reason",
    )

    try:
        return EvidenceVerificationProposal(
            proposition_id=_require_str(payload.get("proposition_id"), "proposition_id"),
            proposition_sha256=_require_str(
                payload.get("proposition_sha256"), "proposition_sha256"
            ),
            source_identifier=_require_str(
                payload.get("source_identifier"), "source_identifier"
            ),
            source_content_sha256=_require_str(
                payload.get("source_content_sha256"), "source_content_sha256"
            ),
            relation=relation,
            role_assessments=assessments,
            evidence_spans=spans,
            reasons=reasons,
        )
    except (TypeError, ValueError) as error:
        raise _rejected(f"invalid analysis proposal: {error}") from error


# ── The adapter ───────────────────────────────────────────────────────────────

class EvidenceAnalyzerModelAdapter:
    """A model-backed evidence analyzer.

    Holds one configured client and calls it once.  It never selects, retries,
    falls back to, or escalates to another model, and it never decides anything
    contractual: its output goes to the deterministic gate exactly like a
    scripted analyzer's would.
    """

    def __init__(
        self,
        client: EvidenceModelClient,
        *,
        source_disclosure: str = SOURCE_DISCLOSURE_LOCAL_ONLY,
        name: str = ADAPTER_NAME,
    ) -> None:
        if source_disclosure not in SOURCE_DISCLOSURE_POLICIES:
            raise ValueError(f"unsupported source disclosure policy: {source_disclosure!r}")
        locality = getattr(client, "locality", None)
        if locality not in LOCALITIES:
            raise SourceDisclosureRefused(
                "an evidence analyzer client must declare locality as "
                f"{LOCALITY_LOCAL!r} or {LOCALITY_CLOUD!r}; an undeclared client is "
                "treated as cloud and refused"
            )
        if locality == LOCALITY_CLOUD and source_disclosure != SOURCE_DISCLOSURE_CLOUD_APPROVED:
            raise SourceDisclosureRefused(
                "sending acquired repository content to a cloud model requires an "
                "explicit cloud_disclosure_approved configuration"
            )
        self._client = client
        self._source_disclosure = source_disclosure
        self._locality = locality
        self._name = name
        self._call_count = 0
        self._last_proposal: EvidenceVerificationProposal | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_id(self) -> str:
        return str(getattr(self._client, "model_id", "unknown"))

    @property
    def locality(self) -> str:
        return self._locality

    @property
    def source_disclosure(self) -> str:
        return self._source_disclosure

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def last_proposal(self) -> EvidenceVerificationProposal | None:
        return self._last_proposal

    def _guard_disclosure(self, request: EvidenceVerificationRequest) -> None:
        if (
            CONSTRAINT_LOCAL_ANALYSIS_ONLY in request.verification_constraints
            and self._locality != LOCALITY_LOCAL
        ):
            raise SourceDisclosureRefused(
                "this verification request requires local_analysis_only and the "
                "configured analyzer is not local"
            )

    def _complete(self, user_message: str) -> str:
        self._call_count += 1
        try:
            response = self._client.complete(
                EVIDENCE_ANALYZER_SYSTEM_INSTRUCTION, user_message
            )
        except EvidenceAnalysisError:
            raise
        except Exception as error:  # transport, auth, timeout, quota, ...
            raise EvidenceAnalyzerUnavailable(
                f"the configured evidence analyzer could not be reached: {error}"
            ) from error
        if not isinstance(response, str) or not response.strip():
            raise EvidenceAnalyzerUnavailable(
                "the configured evidence analyzer returned an empty response"
            )
        return response

    def analyze(
        self,
        request: EvidenceVerificationRequest,
        view: BoundedPayloadView,
    ) -> EvidenceVerificationProposal:
        self._guard_disclosure(request)
        proposal = parse_analysis_response(
            self._complete(build_analysis_request(request, view))
        )
        self._last_proposal = proposal
        return proposal

    def repair(
        self,
        request: EvidenceVerificationRequest,
        view: BoundedPayloadView,
        defects: tuple[str, ...],
    ) -> EvidenceVerificationProposal:
        """One bounded repair, driven by the gate's own defect list."""
        self._guard_disclosure(request)
        proposal = parse_analysis_response(
            self._complete(build_repair_request(request, view, defects))
        )
        self._last_proposal = proposal
        return proposal


class ScriptedEvidenceModelClient:
    """Deterministic offline client replaying canned responses in order."""

    def __init__(
        self,
        responses: list[str],
        *,
        model_id: str = "scripted-evidence-model",
        locality: str = LOCALITY_LOCAL,
    ) -> None:
        if locality not in LOCALITIES:
            raise ValueError(f"unsupported locality: {locality!r}")
        self._responses = list(responses)
        self._model_id = model_id
        self._locality = locality
        self._calls: list[tuple[str, str]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def locality(self) -> str:
        return self._locality

    @property
    def calls(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._calls)

    def complete(self, system_instruction: str, user_message: str) -> str:
        if not self._responses:
            raise EvidenceAnalyzerUnavailable(
                "the scripted evidence model client ran out of responses"
            )
        self._calls.append((system_instruction, user_message))
        return self._responses.pop(0)


def render_proposal_response(proposal: EvidenceVerificationProposal) -> str:
    """Serialize a proposal the way a well-behaved model would answer.

    Used by offline fixtures so the parser is exercised against the exact shape
    the system instruction asks for.
    """
    if not isinstance(proposal, EvidenceVerificationProposal):
        raise TypeError("render_proposal_response requires an EvidenceVerificationProposal")
    payload: dict[str, Any] = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "proposition_id": proposal.proposition_id,
        "proposition_sha256": proposal.proposition_sha256,
        "source_identifier": proposal.source_identifier,
        "source_content_sha256": proposal.source_content_sha256,
        "relation": proposal.relation,
        "role_assessments": [
            {
                "role": item.role,
                "status": item.status,
                "span_indexes": list(item.span_indexes),
                "reasons": list(item.reasons),
            }
            for item in proposal.role_assessments
        ],
        "evidence_spans": [
            {
                "start_byte": item.start_byte,
                "end_byte": item.end_byte,
                "span_sha256": item.span_sha256,
                "purpose": item.purpose,
                "source_content_sha256": item.source_content_sha256,
            }
            for item in proposal.evidence_spans
        ],
        "reasons": list(proposal.reasons),
    }
    return json.dumps(payload, ensure_ascii=False)


__all__ = [
    "ADAPTER_NAME",
    "ALLOWED_RESPONSE_KEYS",
    "ANALYSIS_RESPONSE_SCHEMA_VERSION",
    "EVIDENCE_ANALYZER_SYSTEM_INSTRUCTION",
    "FORBIDDEN_RESPONSE_KEYS",
    "LOCALITIES",
    "LOCALITY_CLOUD",
    "LOCALITY_LOCAL",
    "MAX_ANALYZER_PROMPT_BYTES",
    "PHASE_ID",
    "SOURCE_DISCLOSURE_CLOUD_APPROVED",
    "SOURCE_DISCLOSURE_LOCAL_ONLY",
    "SOURCE_DISCLOSURE_POLICIES",
    "EvidenceAnalyzerModelAdapter",
    "EvidenceModelClient",
    "ScriptedEvidenceModelClient",
    "SourceDisclosureRefused",
    "build_analysis_request",
    "build_repair_request",
    "parse_analysis_response",
    "render_payload_window",
    "render_proposal_response",
]
