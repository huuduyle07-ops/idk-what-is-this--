# CTX.APPLY.0 — Direct Context Patch Safety Attachment

Status: complete  
Date: 2026-08-14  
Next phase: `CTX.APPLY.1 — Human-Confirmed Direct Context Patch Handoff`

## Decision

CTX.APPLY.0 is an in-memory, fail-closed adapter from a typed `CTX.PATCH.1`
result to the existing `core.patch_safety.evaluate_patch_safety` boundary. It
does not create a patch, modify a file, execute validation, create an approval
record, or wire an independent direct-context apply route.

The adapter accepts only the typed `DirectPatchCandidateGateResult`, original
immutable `DirectReadReceipt` objects, a supplied immutable
`RepositoryInventory`, typed `FileCapability` records, and supplied targeted
current identities. A bare or serialized `ProposedPatchSet` is intentionally
not sufficient: it cannot prove task, operation, repository, or receipt
provenance.

## Binding and freshness

Every attachment is bound to:

- task ID and operation ID;
- canonical repository root and repository ID derived from that root;
- inventory identity;
- deterministic proposed patch-set identity;
- exact canonical implementation path;
- original receipt and file-identity fingerprints;
- bounded target ranges and a fingerprint of the bounded change intention;
- candidate state, capability, and validation metadata.

The adapter rejects aliases, traversal, absolute paths, case collisions,
duplicate candidates/receipts, paths absent from the supplied inventory, and
capability records that do not exactly match the candidate path. It rechecks
each supplied current identity through the existing `fresh`, `changed`,
`deleted`, `replaced`, and `unverifiable` receipt decision. Only `fresh` is
attachable. It never rereads or stats a repository file itself.

`changed` yields `reread_required`; `deleted` removes that candidate;
`replaced` is security-blocked; and `unverifiable` is attachment-blocked. The
review artifact declares that the same checks must be repeated immediately
before later generation or application, so an attachment cannot outlive a file
change.

## Path-set and safety boundary

The only potential implementation targets are the typed
`proposed_patch_set.implementation_candidates`. Supporting context,
`required_paths`, and validation candidates are never promoted. Validation
files can appear only as non-writable fresh validation evidence; the approved
test-modification target remains `None`.

Mapped validation candidates on an implementation target are retained as a
bounded, non-executable validation plan. A canonical repository-relative test
path may be named as validation-only; a command-like target is represented
only by a fingerprint. Neither form is a writable target.

The adapter calls the established path safety gate for the declared
implementation target set. An optional injected policy may narrow that set,
but cannot widen it because the established gate always runs first. Existing
web, CLI, executor, lifecycle, and auto-patch chokepoints remain unchanged;
they are still the only future application authority.

Generated, vendor, sensitive, read-only, out-of-scope, forbidden, and
symlink-escaped capabilities do not attach. A generated redirect does not
implicitly add its source: that source needs its own read receipt and CTX.PATCH
proposal.

## Review decisions

Stable attachment outcomes are `attached`, `attached_with_review`,
`partially_attached`, `reread_required`, `human_file_selection_required`,
`policy_blocked`, `security_blocked`, and `invalid_evidence`.

CTX.PATCH.1's existing `validation_gap` and `high_blast_radius_review` states
remain visible and can only produce `attached_with_review`; they are never
silently upgraded to `eligible`. An absent coherent source set is surfaced as
`human_file_selection_required` with the bounded reason
`additional_context_required`, rather than triggering another search or read.

## Human approval and authority

The resulting `PatchSafetyAttachment` provides an exact-file,
task/repository-bound `human_review_request`. Its review options are approval
of the exact set, approval with file removals, rejection, reread, or more
context. Generic repository-wide approval is explicitly insufficient.

The current human-token work is contract/dry-run only, so CTX.APPLY.0 neither
issues nor consumes a token and does not claim runtime enforcement exists.
Every artifact and candidate has:

```text
write_authority = false
patch_generation_authority = false
patch_application_authority = false
human_approval_required = true
```

`eligible_for_patch_safety_review` is the only positive state an attached
implementation target receives. It is not write permission.

## Serialization and independence

The review serialization uses a strict allowlist: paths, bounded ranges,
redacted change-intention descriptors and fingerprints, states, risk/review
points, and reason codes. It omits direct file content, raw change-intention
text, raw read results, patchability evidence detail, raw validation commands,
diffs, patches, and full receipts.

The adapter performs zero repository traversals, production-content reads,
filesystem writes, patch generations, patch applications, validation commands,
indexing, database, graph, model, or API operations. Its only dynamic evidence
operation is comparison of caller-supplied targeted current identities.
