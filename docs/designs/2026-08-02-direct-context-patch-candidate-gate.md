# CTX.PATCH.1 — Direct Context Patch Candidate Gate

Date: 2026-08-02
Status: complete
Next: CTX.APPLY.0 — Direct Context Patch Safety Attachment Contract

## Decision

CTX.PATCH.1 is a pure, fail-closed evidence gate between bounded direct file
context and the existing patch-safety/human-approval path. It answers which
already-read repository files are sufficiently understood to be considered
modification candidates. It does not decide which files may be written.

The hard authority relationship is:

```text
direct read receipt
→ fresh identity decision
→ patchability evaluation
→ bounded proposed patch set
≠ write authority
```

Every result and every selected file retains:

```python
{
    "write_authority": False,
    "patch_application_authority": False,
    "human_approval_required": True,
    "patch_safety_bypassed": False,
}
```

## Inputs and trust boundary

The gate consumes only:

- one supplied immutable `RepositoryInventory`;
- one completed task/operation-scoped `DirectFileContext` or its serialized
  contract;
- CTX.SELECT actionability records;
- deterministic patchability evidence and risk records;
- file capabilities established by the existing capability policy;
- bounded change intentions and validation mappings; and
- current file identities acquired by a caller through targeted identity
  checks.

The gate recomputes the supplied inventory identity without traversal and
requires it to match the direct context and every successful receipt. Receipt
task id, operation id, inventory identity, path, success state, and relevant
line coverage must all agree. Current identities are compared through the
existing pure `verify_direct_read_receipt` helper.

CTX.PATCH.1 never acquires current identities by enumerating the repository.
The `current_file_identities` mapping is the explicit bounded seam: a missing
mapping value is `unverifiable`, while an explicitly supplied `None` means the
target was deleted.

## Score separation

`actionability_score` remains the CTX.SELECT answer to “how relevant is this
file to the task?” `patchability_score` separately answers “how suitable is a
bounded, testable modification to this specific file given current direct-read
evidence?” Actionability is carried into output but contributes zero to
patchability.

Patchability is an explainable integer from 0 through 100. Canonical positive
dimensions are:

- direct-read target confirmation;
- diagnosis confidence;
- change locality;
- symbol or branch specificity;
- validation coverage;
- reversibility;
- a matching test, linter, or type-check path;
- authoritative source confidence;
- direct symbol/reference confirmation;
- localized defect evidence; and
- a bounded manual-verification plan.

Canonical risks include blast radius, dependency centrality, shared public API,
raw-text-only understanding, ambiguous ownership, validation gap, generated or
derived semantics, configuration security, cross-language impact, and partial
read evidence.

Weights are constants. Caller-supplied weights cannot alter them. Unknown
evidence kinds—including CTX.SELECT filename and lexical relevance evidence—are
reported but add zero. Stable evidence ids deduplicate one fact projected
through CTX.SELECT, CTX.SEARCH, and CTX.READ. Each semantic dimension is capped
at one contribution, so repeated matches cannot inflate the score.

Bands are:

```text
80–100  primary_patch_candidate
65–79   patch_candidate_with_review
40–64   inspect_or_supporting_context
1–39    insufficient_patch_evidence
0       blocked_or_forbidden
```

Capability and security states override bands. A generated file can retain an
informative high score while still becoming only `generated_source_redirect`.
Forbidden, outside-scope, opaque, or sensitive capability states hard-zero the
gate score and can never enter the proposed set.

## Freshness and range coverage

Stable receipt outcomes and actions are:

```text
fresh        → candidate may be evaluated
changed      → reread_required
deleted      → candidate_removed
replaced     → security_blocked
unverifiable → human_review_or_reread_required
```

Only `fresh` may be selected. A complete, non-truncated full-file receipt covers
a bounded intention. A range-based or partial receipt qualifies only when its
returned ranges fully contain every proposed target range; partial evidence
also incurs a review penalty. No stale content is silently reused.

## Candidate states

The stable file states are:

```text
eligible
eligible_with_review
insufficient_evidence
reread_required
validation_gap
read_only_context
generated_source_redirect
sensitive_blocked
high_blast_radius_review
outside_scope
forbidden
```

Filename or grep evidence alone is insufficient. At least one direct-read
target, direct symbol/reference, localized defect, or authoritative source
confirmation is mandatory. A nonblank bounded change intention is also
required for selection.

`eligible` requires fresh scope-matched evidence, complete target coverage,
editable capability, low known blast radius, a mapped validation path, no
review-only limitation, and a score of at least 80. Unsupported safe text may
be `eligible_with_review`, with `parser_support=unsupported`,
`understanding_confidence=raw_text_only`, `AST_claimed=false`, and
`dependency_completeness_claimed=false`.

Unknown blast radius is never treated as low. High and critical blast radius
use `high_blast_radius_review`. A validation gap is explicit, penalized, and
uses `validation_gap`; sufficiently strong remaining evidence may still place
it in a proposed set that requires review.

## Sensitive, generated, and configuration policy

- `editable` may qualify.
- `editable_with_review` always requires review.
- `read_only` remains supporting context.
- `generated_do_not_edit` becomes `generated_source_redirect`; a known
  authoritative source is returned as `redirect_to`.
- `sensitive_requires_approval` becomes `sensitive_blocked`, even if a prior
  human-approved read receipt is supplied.
- `outside_scope`, `opaque`, and `forbidden` never qualify.
- `.env.example`, `.env.sample`, and `.env.template` may qualify with direct
  authoritative evidence and review.
- `.env` remains sensitive-blocked, and private material remains forbidden.

## Bounded change and validation planning

A change intention contains only:

- a summary;
- at most eight target ranges;
- an expected behavior change; and
- at most sixteen preservation constraints.

Diff, patch, command, and filesystem-write fields are rejected. The intention
is planning evidence only and never claims correctness.

Up to sixteen per-file validation mappings may be considered. They identify
pytest, compile, linter, type-check, known-command, or bounded manual paths and
are never executed. Unknown validation becomes `validation_status=gap`.

Test files may be identified as validation or potential patch candidates, but
they always carry `test_modification_requires_separate_policy=true`, no write
authority, and no patch authority. CTX.PATCH.1 does not define test-authoring,
test weakening, or RED→GREEN authority.

## Minimal proposed patch set

`build_proposed_patch_set` enforces:

```text
maximum source files      4
maximum validation files  4
maximum total files       8
```

The planner selects one primary implementation target, explicitly required
adjacent implementation files, and corresponding eligible test candidates.
Other read or eligible-but-unneeded files remain supporting context. Required
dependencies are resolved only from supplied evaluated candidates.

Equally plausible unrelated strategies produce
`human_file_selection_required`; the planner does not choose by path spelling.
If a coherent required set exceeds a limit, it also requires human selection
instead of silently truncating the set. Stable patch-set outcomes are `ready`,
`ready_with_review`, `insufficient_evidence`, `reread_required`,
`human_file_selection_required`, and `blocked`.

The invariant is checked before return:

```text
files_read ⊇ proposed implementation and validation candidates
```

## Independence and side effects

For one CTX.PATCH.1 execution:

```text
repository traversals          0
production content reads       0
filesystem writes              0
patches generated              0
patches applied                0
validation commands executed   0
database operations            0
model or API calls              0
```

No canonical index, manifest, vector database, embedding provider, database,
activation graph, parser, model, API, or patch engine is required. Availability
flags for those systems are accepted only to make this independence explicit
and are discarded.

## Implementation

- `core/file_patchability.py` — canonical score evidence, penalties, bands,
  deduplication, and score authority invariants.
- `core/direct_patch_candidate_gate.py` — inventory, receipt, scope, freshness,
  capability, range, intention, validation, and candidate-state gate.
- `core/proposed_patch_set.py` — deterministic minimal coherent set planner and
  hard limits.
- `tests/test_file_patchability.py`
- `tests/test_direct_patch_candidate_gate.py`
- `tests/test_proposed_patch_set.py`

## Future attachment

The recommended next phase is `CTX.APPLY.0 — Direct Context Patch Safety
Attachment Contract`. It should attach fresh CTX.PATCH candidates to the
existing patch-safety and human-approval mechanism. It must not create an
independent write path, infer write authority from a candidate score, or weaken
the existing patch-application boundary.
