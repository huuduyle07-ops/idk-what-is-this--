"""PATCH.AUTHOR.LIVE.2 — the one authoritative patch-authoring contract.

Round 9 measured the asymmetry this module removes.  The initial patch author
was shown the candidate wire shape, the exact field names, the operation
shapes, the output-only rule and the ``safe_minimal`` identifier constraints.
The verification-guided revision author — a *stateless* call to the same model
— was shown none of them and told only to "return the normal patch-candidate
JSON schema".  It returned::

    {"target_snippet": "...", "replacement_snippet": "..."}

which the parser correctly refused as ``revision_output_carried_no_patch_
candidate``.  The implementation substance inside that envelope had already
improved; the envelope threw it away.

So this module owns exactly one thing: **how a model is told to construct a
patch candidate**.  Both authoring calls render their contract from here, which
is why there is no second place to change a field name.  It owns nothing else:

* what payloads are *accepted* stays with the candidate parser/normalizer,
  which this phase does not touch and does not soften;
* which candidate *language* is eligible stays with ``PATCH.MINIMAL``, whose
  deterministic gate remains authoritative no matter what a prompt said;
* whether a candidate is *correct* stays with ``DEFECT.PROBE``.

Prompt text is advice to a model.  None of it is a gate, and a revision that
ignores every sentence here is rejected by exactly the same deterministic
machinery as before.

Everything below is a fixed literal or a pure function of ``(style,
source_snippet)``: no timestamps, no set iteration order, no model-generated
text, no repository access, no retrieval.  The same inputs render the same
bytes, which is what ``authoring_contract_fingerprint`` certifies.

Stdlib only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from dataclasses import replace


PHASE_ID = "PATCH.AUTHOR.LIVE.2"

#: §5 — the version of the *contract material*, not of a candidate and not of a
#: receipt schema.  It moves when the material below moves.
AUTHORING_CONTRACT_VERSION = "patch_authoring_contract_v3"


# ══════════════════════════════════════════════════════════════════════════════
# §6/§7 — the response envelope
# ══════════════════════════════════════════════════════════════════════════════
#
# Moved here verbatim from ``core.prompter``, which now imports it back so its
# public name is unchanged.  It is the outer JSON object every patch-authoring
# call is asked to return, and ``patch_candidate`` is the key the runtime reads.

PATCH_RESPONSE_SCHEMA = """
Return JSON:
{
  "summary": "...",
  "issues": [...],
  "patch_candidate": null | {...},
  "patch_plan": null | [
    {"op": "create_file", "relative_path": "...", "content": "..."},
    {"op": "replace_snippet", "relative_path": "...", "target_snippet": "...", "patched_snippet": "..."}
  ],
  "confidence": 0.0,
  "needs_escalation": false,
  "escalation_reason": "none|semantic_intent_required|missing_context|insufficient_evidence|unsupported_scope|author_output_invalid|other_bounded_reason"
}

Select exactly one escalation_reason from the listed values. When
needs_escalation=false, use "none". When needs_escalation=true, use one
non-none reason and set patch_candidate=null and patch_plan=null. If source
and evidence permit materially different observable behaviors without an
authoritative user/task choice, use "semantic_intent_required" and report a
source-grounded semantic_gap as instructed by the semantic intent handoff.
Never return a candidate alongside an unresolved escalation.
"""


def safe_minimal_forbidden_block(source_snippet: str) -> str:
    """Describe the existing gate's candidate language, without a second scan."""
    if not source_snippet:
        return ""
    return """
SAFE_MINIMAL — HARD CONSTRAINTS:
Candidate references must come from authoritative baseline bindings shown in
AUTHORITATIVE AUTHORING SCOPE, permitted bounded candidate-local bindings, or
the gate's existing source-snippet, language-keyword and supported-builtin classes.
Baseline locals remain subject to initialization and lexical shadowing; their
presence does not prove a value at an arbitrary point in the function.
A proven repository-local immutable result may expose its declared read-only
data fields. This permission is limited to proven reads in bounded straight-line
return expressions, directly or through a single unaliased local assignment
before use. It grants no new method, property, chained member, field call, write,
delete, module-namespace or dynamic access permission.
Candidate-local novelty remains bounded by PATCH.MINIMAL; it does not permit
new external capabilities. Deterministic PATCH.MINIMAL remains final authority.

FORBIDDEN in patched_snippet:
- Unproven new external references or member capabilities.
- New imports, new helper functions, new type declarations.
- Behavioural redesign — only fix the literal bug.

If a correct fix would require any of the above:
  set patch_candidate=null, confidence<=0.3, needs_escalation=true,
  and explain in `summary` what is missing from context.
""".strip()


def patch_output_format_block(style: str) -> str:
    """Tell the AI when to use patch_candidate vs patch_plan.

    - safe_minimal: patch_candidate only — single-file edit, never create files.
    - balanced:     patch_candidate by default; patch_plan ALLOWED for feature work.
    - vibe:         patch_plan freely, but every path must stay inside the repo.

    Mirrors the split between the executor's snippet-replace path and the
    multi-file plan path. Putting this in the prompt prevents the AI from
    quietly cramming a multi-file change into a single patch_candidate.
    """
    common_shapes = """\
patch_candidate (single-file existing-code fix):
{
  "patch_candidate": {
    "file": "...",
    "relative_path": "...",
    "target_node_name": "...",
    "target_node_kind": "function|class",
    "target_snippet": "...",
    "patched_snippet": "..."
  }
}

patch_plan (multi-file or new-file work):
{
  "patch_plan": [
    {"op": "create_file",     "relative_path": "src/aml.rs", "content": "..."},
    {"op": "replace_snippet", "relative_path": "src/main.rs",
     "target_snippet": "mod agent;",
     "patched_snippet": "mod agent;\\nmod aml;"}
  ]
}

Rules:
- Output EITHER patch_candidate OR patch_plan, never both.
- Use patch_candidate only when editing one existing file.
- Use patch_plan when creating files, editing multiple files, or changing APIs across files.
- Every relative_path MUST stay inside the repo (no absolute paths, no '..').
- Every patch_candidate.target_snippet must be an exact quote from the target file.
- If it is not found, reject/demote the candidate before final result.
"""

    if style == "safe_minimal":
        return (
            "[PATCH OUTPUT FORMAT — safe_minimal]\n"
            "Use patch_candidate ONLY. Do NOT emit patch_plan. Do NOT create files.\n"
            "If the fix would require new files or multi-file changes, set\n"
            "patch_candidate=null and needs_escalation=true.\n\n"
            + common_shapes
            + "\nsafe_minimal-specific: patch_plan is FORBIDDEN. Single existing file or escalate."
        )

    if style == "balanced":
        return (
            "[PATCH OUTPUT FORMAT — balanced]\n"
            "Prefer patch_candidate. Use patch_plan ONLY when feature work genuinely\n"
            "requires touching multiple files or creating a new file. Justify in `summary`.\n\n"
            + common_shapes
            + "\nbalanced-specific: patch_plan allowed but every op must reference an existing\n"
              "module/API or be clearly justified. Bias toward smaller patch_candidate when possible."
        )

    # vibe
    return (
        "[PATCH OUTPUT FORMAT — vibe]\n"
        "Use whichever shape best fits the change. patch_plan is encouraged for feature work,\n"
        "refactors across files, or anything that needs new helpers. List every assumption in `summary`.\n\n"
        + common_shapes
        + "\nvibe-specific: patch_plan freely usable, but every relative_path MUST stay inside\n"
          "the repo. Auto-apply is disabled — the user will review your plan."
    )

# ══════════════════════════════════════════════════════════════════════════════
# §9 — candidate-language constraints, per style
# ══════════════════════════════════════════════════════════════════════════════
#
# The safe_minimal rule describes the frozen policy; baseline names and static
# field capabilities are projected separately by CandidateAuthoringContext.
# This contract and its version remain shared by both authoring calls.

BALANCED_CANDIDATE_LANGUAGE = (
    "BALANCED: design-level fixes allowed, but every identifier in patched_snippet "
    "must be either in source_snippet OR a clearly-existing API shown in RELATED CONTEXT. "
    "If you need a new field/method on a user-defined type, set needs_escalation=true."
)

VIBE_CANDIDATE_LANGUAGE = (
    "VIBE: creative fixes allowed. You MAY introduce new helpers/fields, but mark each "
    "assumption explicitly in summary. auto_apply will be disabled — produce a reviewable patch."
)


def candidate_language_block(style: str, source_snippet: str) -> str:
    """The lexical/structural constraints the author is asked to respect.

    Dispatch is by the same normalized style the patch policy already resolved,
    and the branches are the ones ``build_control_prompt`` used inline before
    this phase — the same order, the same fallback to ``vibe``.
    """

    if style == "safe_minimal":
        return safe_minimal_forbidden_block(source_snippet)
    if style == "balanced":
        return BALANCED_CANDIDATE_LANGUAGE
    return VIBE_CANDIDATE_LANGUAGE


# ══════════════════════════════════════════════════════════════════════════════
# §1/§4/§5 — the contract itself
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class PatchAuthoringContract:
    """One rendering of the authoring contract, and its identity.

    ``sections`` are the authoritative material.  Every one of them appears
    byte-for-byte in *both* the initial-draft prompt and the revision prompt;
    the framing around them is call-specific and deliberately differs, because
    the two calls carry different evidence and are not the same request.

    ``text`` is the canonical concatenation — what a call embeds when it needs
    the whole contract in one place, and what the fingerprint is taken over.
    """

    style: str
    output_format_block: str
    candidate_language_block: str
    response_schema_block: str
    version: str = AUTHORING_CONTRACT_VERSION
    phase_id: str = PHASE_ID

    @property
    def sections(self) -> tuple[str, ...]:
        return (
            self.output_format_block,
            self.candidate_language_block,
            self.response_schema_block,
        )

    @property
    def text(self) -> str:
        """Deterministic: fixed order, no separator when a section is empty."""

        return "\n\n".join(part for part in self.sections if part.strip())

    @property
    def fingerprint(self) -> str:
        """§5 — identifies PROMPT CONTRACT content, never candidate bytes.

        Deliberately *not* the candidate fingerprint primitive: this answers
        "were both authors held to the same contract", which is a question about
        the request, not about the patch that came back.
        """

        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def as_telemetry(self) -> dict[str, object]:
        """§33 — three bounded facts.  The contract text itself is not stored."""

        return {
            "authoring_contract_version": self.version,
            "authoring_contract_fingerprint": self.fingerprint,
            "authoring_contract_style": self.style,
        }


def render_patch_authoring_contract(
    *, style: str, source_snippet: str
) -> PatchAuthoringContract:
    """§1/§21 — the single authoritative rendering, used by both authors.

    Pure prompt construction over state the caller already holds: no retrieval,
    no graph work, no repository traversal, no embedding, no indexing and no
    model call.  ``source_snippet`` is the bounded source the author was already
    given, never a fresh read.
    """

    return PatchAuthoringContract(
        style=style,
        output_format_block=patch_output_format_block(style),
        candidate_language_block=candidate_language_block(style, source_snippet),
        response_schema_block=PATCH_RESPONSE_SCHEMA,
    )


def patch_authoring_contract_guardrails() -> dict[str, object]:
    """The boundaries this phase asserts about itself."""

    return {
        "authoring_contract_version": AUTHORING_CONTRACT_VERSION,
        "initial_draft_and_revision_share_one_contract": True,
        "contract_rendering_is_deterministic": True,
        "contract_performs_retrieval": False,
        "contract_traverses_the_repository": False,
        "contract_makes_model_calls": False,
        "contract_makes_network_calls": False,
        "contract_loosens_the_candidate_parser": False,
        "contract_aliases_replacement_snippet": False,
        "contract_repairs_provider_output": False,
        "contract_replaces_safe_minimal": False,
        "contract_grants_execution_authority": False,
        "contract_contains_task_specific_solution_advice": False,
    }


MEASURED_REPAIR_AUTHORING_RULES = """[MEASURED REPAIR-SET AUTHORING CONTRACT]
You may draft changes inside exactly the measured repair members in
AUTHORITATIVE AUTHORING SCOPE. The primary target remains separate and unchanged.
Account for all associated compiler diagnostics; you need not edit every member.
Member-local bindings belong only to their named member. Proven file imports
retain their existing read capabilities; no import modification is authorized.
Visible context and the source between members are read-only.
Use the existing single-file patch_candidate shape. Keep target_node_name equal
to the primary symbol; it identifies the semantic target, not the replacement span.
CANONICAL REPLACEMENT ENVELOPE: replacement_envelope.original_snippet is the exact
provided baseline interval, separate from primary_target.source_snippet, member
snippets and whole-file read-only context. For edits spanning multiple measured
members, copy that entire original_snippet verbatim into target_snippet and put
its replacement in patched_snippet. Both fields must describe the SAME interval.
Never quote only the primary member while supplying other members in the
replacement: their original definitions would remain outside the replaced span.
An existing exact unique sub-envelope is allowed only when the replacement is
self-consistent for precisely that interval; do not insert copies of members
outside it. The canonical envelope is the maximum allowed original interval.
Preserve every byte outside the measured members in patched_snippet, including
intervening definitions, comments, annotations, blank lines and whitespace.
Members inside the envelope may remain unchanged; not every member must differ.
Malformed spans are rejected, never silently expanded or rewritten.
No new definitions, files, imports or extra targets may be proposed.
The measured set is permitted for drafting even when it contains several methods.
Draft permission does not certify safety, minimality or completeness.
Existing PATCH.MINIMAL (including its one-function limit), verification and human
approval remain downstream authorities and may reject this draft.
write_authority=false; execution_authorized=false; auto_apply=false.
""".strip()


def for_measured_repair_scope(contract: PatchAuthoringContract) -> PatchAuthoringContract:
    """Called only after admission of a complete multi-member BASIS scope."""
    return replace(
        contract, version="patch_authoring_contract_v4_replacement_envelope",
        phase_id="PATCH.AUTHOR.SPAN.1",
        candidate_language_block=contract.candidate_language_block + "\n\n" + MEASURED_REPAIR_AUTHORING_RULES,
    )
