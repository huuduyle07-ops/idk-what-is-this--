# EXEC.POLICY.LIVE.1 — Evidence-Bounded Large-Repository Execution Eligibility

## Decision boundary

This phase answers one question: given the immutable facts already produced by
the live execution pipeline, which named execution-policy profiles do those
facts satisfy?

It does not answer whether a patch may be written. Evidence facts, policy
eligibility, and execution authorization remain separate:

```text
evidence receipts -> deterministic eligibility assessment -> human review
                                                         != execution authority
```

`eligible` never sets `execution_authorized`, `auto_apply_allowed`,
`write_authority`, `patch_application_authority`, `patch_applied`, or human
approval. EXEC.AUTH remains authoritative for execution.

## Profiles

The profile vocabulary is closed:

- `full_validation_required`: eligible only when the existing required
  repository validation outcome is `passed`. Failed, inconclusive, unavailable,
  or missing validation does not satisfy it.
- `bounded_evidence_human_review`: human-review-only eligibility for a
  grounded defect candidate supported by a conservative bounded evidence
  matrix. No bounded auto-apply profile exists.

The status vocabulary is `eligible`, `ineligible`, `insufficient_evidence`, and
`inconsistent_input`. Historical payloads without an assessment read as
`legacy_unassessed`, never eligible.

## Bounded evidence policy

The bounded human-review profile requires all of these facts:

- the route is defect repair;
- patch basis is `grounded_defect` and exact source/target grounding exists;
- the existing patch-safety verdict passed and is bound to the exact candidate;
- the independently grounded pre-patch probe reproduced on current source;
- the same immutable probe is fixed by the exact candidate in a managed
  sandbox, candidate application succeeded, and cleanup was confirmed;
- candidate, probe, selected-check-set, source, and available repository
  identities are current and consistent;
- targeted evidence is selected, complete, valid, and has a passed baseline;
- there is no candidate-regression-oracle failure or unresolved failed check;
- human approval remains required for execution; and
- full validation either passed or is inconclusive specifically because
  `validation_budget_exhausted`.

The timeout case is recorded as the accepted limitation
`full_validation_budget_exhausted`. The full-validation receipt remains
`inconclusive`; the repository is not called validated.

## Failed targeted checks

A targeted failure remains a failure. It can coexist with bounded human-review
eligibility only when every failed relevant selected check has a current
assessment bound to the same candidate, probe, and check set, and every such
failure is `defect_preservation_oracle`. The policy records
`accepted_evidence_conflicts=[defect_preservation_oracle]`; it does not relabel
any check as passing.

A failed `candidate_regression_oracle` blocks eligibility. A failed
`conflict_unresolved`, `insufficient_basis`, unrelated/possibly-regressive
check, missing assessment, or unresolved per-check execution result is
insufficient evidence and cannot be ignored. Candidate-modified or otherwise
tampered selected checks are a hard invalid block.

## Full-suite and safety behavior

A completed meaningful full-suite failure blocks the bounded profile. Targeted
evidence and a fixed probe cannot override it. Inconclusive categories other
than `validation_budget_exhausted` are not accepted. Patch safety is a hard gate
for both profiles and cannot be overridden by stronger probe or test evidence.

Model-only probe input or expectation provenance is invalid. Candidate, probe,
check-set, source, or explicit repository-identity disagreement produces stale
or inconsistent input rather than combining receipts from different states.

## Pure implementation and live integration

`core.execution_eligibility_policy.evaluate_execution_eligibility` is a pure
stdlib reducer over mappings. It imports no filesystem, process, network,
provider, graph, validation, or retrieval machinery. The same evidence produces
the same assessments and deterministic assessment fingerprints. Pipeline code
only assembles receipts already in memory, binds the already-computed patch
safety result to the current candidate, times the pure call, and attaches its
telemetry.

The live adapter runs at the existing grounded-defect, non-authorizing human
review handoff after EXEC.AUTH has already recorded
`execution_authorized=false` and
`human_approval_required_for_execution=true`. No authorization branch consumes
`human_review_eligible`.

T1/T2/T3 conclusive full-validation flows do not enter this bounded handoff. T4
explicit change remains OPS.PATCH.2 plus human approval. T5 analysis and
no-patch-basis/no-candidate states do not invent a policy assessment.

## T6 acceptance

For the exact sandbox-only `_classify_indent` candidate:

- full validation remains `inconclusive / validation_budget_exhausted`;
- the pre-probe reproduces `4space` against independently expected `2space`;
- the same post-candidate probe observes `2space / fixed`;
- targeted baseline passes and candidate targeted validation fails;
- both failed checks remain failed and are classified
  `defect_preservation_oracle`;
- `full_validation_required` is ineligible;
- `bounded_evidence_human_review` is eligible; and
- execution remains unauthorized, auto apply remains false, no patch is
  applied, and the real `core/code_dna.py` stays byte-identical and intentionally
  broken.

The evaluator adds zero model calls, network calls, filesystem or graph
traversals, validation executions, retrieval operations, and authority.
