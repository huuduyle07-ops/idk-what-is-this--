# Independent implementation source review

2026-10-13 KST. **NO_CONTRACT_BLOCKER_FOUND** for the reviewed owner source
`core/synthetic_runtime_authorization_pinned_lifecycle.py`, SHA256
`235f630b6e888e55b0fae1fda7699c4a962c0f003feb0bf08e7885c91d63e3c4`.
This was source inspection only. The reviewer issued no provider, authorization
or execution lease, consumed no lease, and ran no operational test or behavior.
Machine-readable scope and observations are in [implementation_review.json](implementation_review.json).

The owner uses the exact distinct type and schema, the unchanged public pinned
validator, all fifteen public provider projection fields, and the frozen scenario
and activation policy. Valid operations authenticate the retained original
upstream under one independent lock. Copy-on-write store replacement provides
one publication point for issuance and terminal records; permanent records retain
the upstream strongly and lease identity weakly. Wrong PID rejection precedes
lock acquisition. Consumption fails closed with `PROOF_UNRESOLVED`; invalidation
does not require consumer readiness. All broad authority flags remain false.
The final public `ERROR_CODES` tuple enumerates the eleven frozen categories,
including the reserved `ACTIVATION_PRECONDITION_UNSATISFIED` category, without
inventing a consumer readiness gate or permissive branch.

The five-field one-shot key uses **upstream authorization** owner, phase, schema,
PID and authorization ID. The frozen contract document explicitly says the tuple
comes from the original pinned authorization at lines 123-125.

The independent domain frames each role as domain, NUL, role, NUL, canonical
UTF-8 JSON. `activation-policy`, `lease-evidence` and `lease-fingerprint` use
SHA256 for deterministic public projection digests. `lease-record-hmac` uses an
independent secret and HMAC-SHA256 to authenticate the immutable issuance
projection, its digests, and current state. Digests alone never authenticate a
capability; exact live identity and public original upstream validation remain
mandatory. Secret and private record signature are not exported.

One review advisory was resolved: generated IDs are now checked for exact
64-character lowercase hexadecimal shape before any issuance publication,
including collision retries. Malformed generation fails `PROOF_UNRESOLVED`.

The frozen CONTRACT suite has one stage assertion that expects this future owner
module to be absent. Its historical contract-freeze claim does not prohibit the
separately authorized 1A implementation. Preserve frozen bytes and report any
historical-view validation separately from unmodified current-tree results.
This review does not claim the frozen suite passes in the implementation tree.
