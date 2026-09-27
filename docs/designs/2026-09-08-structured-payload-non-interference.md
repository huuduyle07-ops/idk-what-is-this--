# ANSWER.GROUND.LIVE.4 — Structured Payload Non-Interference

**Date:** 2026-09-08
**Track:** CHECK
**Status:** complete
**Prerequisites:** ANSWER.GROUND.LIVE.1, ANSWER.GROUND.LIVE.2, ANSWER.GROUND.LIVE.3,
CANDIDATE.VERIFY.LIVE.1

## The proven defect

Round-7 showed ANSWER.GROUND rewriting machine-authored control-plane telemetry
as if the model had asserted it. The candidate-verification phase id

```
"CANDIDATE.VERIFY.LIVE.1"
```

reached the display and persistence surfaces as

```
"CANDIDATE.VERIFY.LIVE (not established in the current evidence).1

Repository evidence gap: the model named \"CANDIDATE.VERIFY.LIVE\", but the
reference is not established in the current evidence for C.A.T.T.U.S, ..."
```

The payload stayed syntactically valid JSON. Its machine semantics were
destroyed: any reader comparing `candidate_verification_phase_id` against
`CANDIDATE.VERIFY.LIVE.1`, or matching a receipt's `phase_id`, now sees a
mismatch, and a user-facing evidence-gap paragraph sits inside a field no user
ever reads.

### Reproduction

The defect needs one condition beyond the payload shape: the subject repository
must genuinely declare a symbol whose tail is `candidate`, which puts
`candidate` into `SymbolMembership._known_names`. `is_repository_claim` then
accepts `CANDIDATE.*` as an owner-shaped repository claim — so the phase id
becomes classifiable, resolves to nothing, and is downgraded. On a
self-analysis of C.A.T.T.U.S (`core/candidate_verification.py`) that condition
holds. This is why the defect is intermittent by repository rather than
constant, and why it was not caught by fixtures with sparse evidence.

The span the annotation lands on is `CANDIDATE.VERIFY.LIVE` — the symbol
grammar stops before `.1`, because a segment beginning with a digit is not a
member name. That is exactly the corruption Round-7 reported.

## Root cause

`core/answer_entity_grounding.py::_ground_payload_value` walked the entire
`json_block` and grounded **every string at every depth**, skipping only those
whose immediate key appeared in the `_SKIP_PAYLOAD_TEXT_KEYS` blacklist.

The default was inverted: *rewrite unless blacklisted*.

That default cannot hold. `json_block` is not the model's answer — it is the
model's answer plus every control-plane fact the harness attaches to it after
the model has finished. `core/pipeline.py` alone names over a hundred such
keys (`_CANDIDATE_VERIFICATION_KEYS`, `_EXECUTION_ELIGIBILITY_KEYS`,
`_TARGETED_VALIDATION_KEYS`, `_CANDIDATE_VALIDATION_KEYS`,
`_CANDIDATE_DEFECT_PROBE_KEYS`), and every new phase adds more. A blacklist
of key names is a list that is always one phase out of date, and it fails
*open* — the failure mode is silent corruption of the field nobody thought to
add.

This is a boundary violation, not a grammar bug. ANSWER.GROUND owns
model-authored repository specificity. It does not own harness-authored
control-plane state.

## The fix: ownership, not spelling

The default is inverted back. `_ground_payload_value` descends into and
rewrites a field only when that field is on an explicit **model-authored answer
surface**; everything else is returned by identity.

```python
_ANSWER_SURFACE_KEYS = (
    _ANSWER_PROSE_KEYS | _SYMBOL_ASSERTION_KEYS | frozenset(_PATH_CONTEXT_KEYS)
)
```

* `_ANSWER_PROSE_KEYS` — free-text and list fields the model is asked to write,
  taken from the response schemas in `core/prompter.py` (`REVIEWER_SCHEMA`,
  `PLANNER_SCHEMA`, `PATCH_RESPONSE_SCHEMA`, the per-step schema) and from the
  reviewer block `patching/patch_gates.py::reject_schema_drift` synthesises.
* `_SYMBOL_ASSERTION_KEYS` — unchanged from LIVE.2. A typed symbol claim is
  still validated as a claim, so a model-authored
  `symbol = "ImaginaryClass.fake_method"` is still downgraded. The distinction
  is ownership, not `str` versus `dict`.
* `_PATH_CONTEXT_KEYS` — unchanged from LIVE.2, and still read from the whole
  mapping for sibling path context. Reading a field is not rewriting it.

Enum and scalar fields the model also authors — `severity`, `type`, `op`,
`status`, `target_node_kind`, `action`, `confidence`, `needs_escalation`,
`blocked`, `id` — are deliberately **absent**. They are machine vocabulary; a
truthfulness gate has nothing to say about them, and the safe default applies.

### Ownership is inherited down the subtree

The key is checked at every level, not only at the root. A harness receipt that
happens to contain a `summary` keeps it verbatim, because once a field belongs
to the harness, everything beneath it does too. This is what makes the boundary
robust against key-name collisions between the answer schema and future receipt
schemas — without it, the fix would be another list that goes stale.

### Reusing the existing boundary

`core/localization_handoff.py::_display_payload` already annotates *this same
payload* and already recurses only into a declared list of model-authored
answer keys, with the comment "Execution receipts, patch bytes and
entity-grounding facts remain exact." ANSWER.GROUND did the opposite on the
same object. This phase makes the two seams agree; it does not invent a new
concept, and `core/localization_handoff.py` is not edited.

`_SKIP_PAYLOAD_TEXT_KEYS` is now structurally redundant — `content`,
`target_snippet`, `patched_snippet`, `source_snippet`, `output`, `diff`,
`traceback` and the rest are simply not on the answer surface. It is retained
as a second gate, and a test asserts the two sets stay disjoint, so a future
edit that puts code bytes on the answer surface is caught rather than shipped.

## Byte preservation

`tests/test_answer_ground_payload_ownership.py` pins value identity across the
display and persistence path for phase ids (top-level and nested in a receipt),
schema versions, candidate and probe fingerprints, the localized target
receipt, the candidate verification receipt, verification status, provenance,
`human_review_eligible`, `execution_authorized`, `final_repository_changed`,
`write_authority`, `patch_application_authority`, telemetry mappings, nested
enum components and rejection-reason lists.

The Round-7 payload shape is replayed whole: every key outside `summary` and
`issues` must compare equal to its input, and no machine field may contain
`"not established in the current evidence"` or `"Repository evidence gap"`.

## LIVE.1 / .2 / .3 remain true

All 89 existing tests in `tests/test_answer_entity_grounding.py`,
`tests/test_answer_symbol_grounding.py` and
`tests/test_answer_grounding_nondestructive.py` pass unchanged. Entity-span-only
remediation, no sentence deletion, the honest "not established in the current
evidence" reading, the path-boundary fixes and multi-root semantics are
untouched — this phase changes *which fields are offered to* the grounding
pass, never what the pass does with a field it is given.

The free-text/entity classification of `CANDIDATE.VERIFY.LIVE` in model prose
is deliberately **unchanged**. If a model writes that string into a `summary`,
it is a model-authored claim and LIVE.1/.2/.3 semantics apply. The `elif` /
`startswith` free-text classification question stays on its own backlog, as
scoped.

## Frozen boundaries

`core/answer_entity_grounding.py` was pinned by whole-file digest in
`tests/fixtures/control_localize_live2_boundaries.json`. This phase is
authorised to edit it, so that pin was re-taken — and a re-taken whole-file pin
proves nothing on its own.

`tests/fixtures/answer_ground_live4_frozen_boundaries.json` replaces it with a
finer-grained invariant, generated from a **reconstructed pre-change file whose
sha256 was verified equal to the old pin**: of the module's 44 top-level
definitions, exactly one — `_ground_payload_value` — is this phase's, and the
other 43 are pinned at their pre-LIVE.4 AST digests. Nothing was added or
removed. The fixture also pins `core/repository_symbol_membership.py`,
`core/localization_handoff.py` and `core/candidate_verification.py` by whole-file
digest: this phase reuses those boundaries and does not edit them.

## No new capabilities

No model call, no network call, no repository traversal, no retrieval, no
indexing, no authority change, no validation change, no candidate change. The
diff removes work rather than adding it — the payload walk now visits strictly
fewer nodes than before. `authority_effect` and `retrieval_effect` remain
`"none"` in the receipt.

## Stop condition

ANSWER.GROUND can no longer alter harness-authored structured state, while
retaining grounding over explicitly model-authored answer claims. The Round-7
candidate-verification phase id and receipt are byte/value identical through the
display and persistence grounding path.
