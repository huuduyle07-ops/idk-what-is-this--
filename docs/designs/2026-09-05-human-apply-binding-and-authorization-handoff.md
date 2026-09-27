# EXEC.APPROVAL.LIVE.1 — Human Apply Binding, Freshness Revalidation & Authorization Handoff

## Decision boundary

This phase answers one question: does one explicit human Apply action carry
execution authority for the exact candidate that human was shown?

It is an authority boundary, not an evidence producer. Eligibility, approval,
authorization, execution and persistence remain five separate facts, and no
later fact may be inferred from an earlier one:

```text
human_review_eligible -> human_approval_received -> execution_authorized
                      -> execution_attempted     -> patch_applied
```

`human_review_eligible=true` with `human_approval_received=false` is always
`execution_authorized=false`. `human_approval_received=true` is not yet
authorization: candidate, eligibility receipt, repository identity, bounded
source state and the existing patch-safety verdict are revalidated first.

## Review receipt

`HumanApplyReviewReceipt` freezes the exact state presented for review at the
moment the candidate becomes stable — immediately after the existing patch
safety handoff, and after OPS.PATCH.2 sandbox validation or EXEC.POLICY.LIVE.1
eligibility has recorded its result. It carries:

- `candidate_fingerprint` (the existing OPS.PATCH.2 patch-plan fingerprint);
- `eligibility_receipt_fingerprint` (the EXEC.POLICY.LIVE.1 assessment identity);
- `policy_profile`;
- `repository_identity` (the existing canonical repository id);
- `source_state` and `source_state_fingerprint` over bounded known paths;
- `patch_safety_binding`, binding the existing safety verdict to this candidate,
  repository and path set;
- `probe_fingerprint` and `targeted_validation_fingerprint` where the receipt
  depends on them.

The receipt is content-addressed and self-verifying: parsing recomputes its
fingerprint and its source-state fingerprint and refuses a mismatch. Freezing a
receipt cannot change eligibility; a receipt that cannot be frozen simply leaves
the later Apply with nothing to authorize, and Apply then fails closed.

## Profiles

Two manual review profiles share this one Apply boundary and differ only in
evidence prerequisites:

- `bounded_evidence_human_review` — the T6-like large-repository defect route.
  A receipt is issued only when the EXEC.POLICY.LIVE.1 assessment for that
  profile is `eligible`, its recorded fingerprint recomputes, and it is bound to
  the same candidate. Ineligible, insufficient, inconsistent and legacy
  unassessed states are never frozen for review and never authorized.
- `explicit_change_manual_review` — the existing T4 route. It requires no defect
  probe, targeted validation or eligibility receipt; its prerequisite is the
  established explicit-change basis plus the existing patch-safety verdict.

No `bounded_auto_apply` profile exists. `full_validation_required` behavior is
unchanged.

## Explicit action

Approval is only the existing human-triggered action: the browser Apply /
Review & Apply POST, or an explicit CLI confirmation. `human_action_kind` is a
closed vocabulary. Opening a candidate, reading a diff, continuing a
conversation, model recommendation, confidence and `human_review_eligible=true`
are not approval, and a displayed sentence carries no authority.

## Freshness revalidation

At the Apply boundary the existing primitives are re-read, never regenerated:

- the canonical repository identity must equal the reviewed one;
- the reviewed known paths are re-digested with the CHECK.LIVE path observer and
  must equal the reviewed source state;
- the eligibility assessment must still recompute to the reviewed fingerprint
  and still be bound to the same candidate, probe and check set;
- the recomputed patch-safety binding must equal the reviewed one and the
  existing verdict must still pass.

Only the reviewed known paths are read, so an unrelated file change that bounded
freshness can prove irrelevant does not invalidate the candidate. Where the
bounded state cannot be established — an unreadable or oversized reviewed path —
the result is `incomplete` and denial, never an optimistic pass. No model call,
network call, retrieval, probe, targeted test, full validation or repository
traversal happens here.

## Authorization receipt

`HumanApplyAuthorization` is the typed, immutable, pre-mutation product of the
boundary. It carries candidate and approved-candidate fingerprints, eligibility
receipt and approved receipt fingerprints, policy profile, human action kind,
`human_approval_received`, `freshness_status`, `patch_safety_binding`,
source-state fingerprint, repository identity, `authorization_status`,
`denial_reason`, `authority_source` and measured timings. It carries no
confidence and no prose authority.

Its invariants are enforced in construction: an authorized receipt requires
explicit approval, `current` freshness, no denial reason and
`authority_source=manual_apply_action`; a denied receipt requires a reason from
the closed vocabulary and no authority source.

The denial vocabulary is `not_human_review_eligible`, `approval_missing`,
`candidate_mismatch`, `eligibility_receipt_stale`, `source_state_stale`,
`patch_safety_mismatch`, `repository_identity_mismatch`,
`policy_profile_mismatch` and `inconsistent_input`. The same names were added to
the EXEC.AUTH denial vocabulary so a denied Apply reports one reason everywhere.

## Authorization precedes mutation

The existing `/apply_patch` and `/apply_patch_plan` routes evaluate the existing
patch-safety gate, then call `authorize_human_apply`, and return the denial
response before any backup, executor or lifecycle call when it is not
authorized. On the authorized path the plan route hands the receipt to
`run_patch_plan_with_artifacts`, which persists `human_apply_authorization.json`
into the replay bundle before the safety chokepoint and the executor. Nothing
records approval retroactively after a mutation.

## Execution, validation and rollback

Authorized execution enters the existing executor and lifecycle unchanged.
OPS.PATCH.1 remains authoritative for bytes and rollback, and the existing
apply-time validation policy is untouched: human approval authorizes the
attempt, not persistence. A rollback reports `execution_authorized=true`,
`execution_attempted=true`, mutation observed, `rollback_performed=true`,
`patch_applied=false` and `final_repository_changed=false`, and says so in
words.

## Hard non-overrides

Human approval does not override patch safety, policy ineligibility or stale
evidence. There is no "the human accepted the risk" path in this phase. An
approval is bound to one candidate and one evidence state; nothing authorizes
future patches from the same run.

## Persistence and follow-up

The approved candidate, the eligibility receipt used, the authorization result,
any denial reason and the final execution outcome are written into the patch
payload, the web session history and the replay bundle. History and follow-up
surfaces read the EXEC.AUTH final outcome, so no surface says "applied" merely
because Apply was pressed. Only fingerprints and closed vocabularies are stored;
no source contents or secrets are added.

## Compatibility

Old manual Apply artifacts without the new receipt keep their established
semantics: an explicit-change payload posted to the pre-existing Apply routes
still applies under legacy manual policy, marked `legacy_compatibility`. A
historical `grounded_defect` payload without a bounded receipt is not
reinterpreted as an evidence-bounded approved run; it is denied
`eligibility_receipt_stale`.

T1/T2/T3 automatic execution is untouched. The manual review receipt is created
only inside the no-authority patch-safety handoff, which the auto-apply branches
never reach, so no automatic run acquires, needs or emits one. Analysis and
clarification routes have no candidate, so Apply there is `inconsistent_input`.

## T6 acceptance

Against an isolated copy of the real, still-broken `core/code_dna.py`:

- before the click the bounded profile is eligible, `human_review_eligible` is
  true, `execution_authorized` is false and nothing is applied;
- the existing explicit Apply action binds to the exact candidate, freshness
  revalidates as `current`, authority is `manual_apply_action`, authorization is
  created before mutation, and the candidate is applied through the normal
  executor with the existing validation policy;
- editing the reviewed target first yields approval received, freshness stale,
  no authorization and no mutation;
- approving C1 and submitting a refined C2 is `candidate_mismatch`;
- a safety-blocked target is `patch_safety_mismatch`;
- a candidate the regression oracle made ineligible is
  `not_human_review_eligible`, and an ineligible candidate is never frozen for
  review at all;
- a T4 explicit-change candidate applies through the same boundary with no
  defect evidence; and
- an authorized attempt whose execution validation fails rolls back byte-exactly
  while the approval receipt stays truthful.

The real `core/code_dna.py` is byte-identical before and after the whole matrix
and remains intentionally broken.

The boundary adds zero model calls, network calls, repository traversals,
validation executions and evidence producers, and no bounded auto-apply.
