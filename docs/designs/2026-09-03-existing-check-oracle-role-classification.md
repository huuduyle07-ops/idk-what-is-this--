# VALIDATE.ORACLE.LIVE.1 — Existing Check Role & Candidate-Oracle Conflict Classification

Status: complete  
Track: OPS  
Prerequisite: `DEFECT.PROBE.LIVE.2`

## Outcome

C.A.T.T.U.S now preserves two independent facts for every bounded selected
check: its real execution outcome and its semantic role relative to the
independently grounded desired behavior. A failed check remains failed. The
role is additive and cannot pass, ignore, select, generate, authorize, apply,
or approve anything.

The bounded role vocabulary is:

- `candidate_regression_oracle`
- `defect_preservation_oracle`
- `compatible_but_nonexclusive`
- `unrelated`
- `conflict_unresolved`
- `insufficient_basis`

There are no confidence scores.

## Deterministic relation boundary

The classifier receives the immutable `DefectProbeContract` and exactly the
`TargetedCheck` set already selected by `OPS.VALIDATE.3`. It reads only those
named Python files and accepts only direct pytest assertions of these forms:

```python
assert function(literal_args) == literal
assert function(literal_args) != literal
assert function(literal_args)
assert not function(literal_args)
```

Local literal bindings are allowed. Nested calls, computed expectations,
fixtures that cannot be reduced to literals, and complex assertions are
`conflict_unresolved`. A different bounded input or no assertion for the probe
target is `unrelated`. There is no model interpretation and no general Python
theorem prover.

Exact literal probe inputs compare directly. The existing typed indentation
task-fact adapter additionally permits an exact nonblank leading-space shape
comparison. That rule is enabled by typed input provenance, has no target or
test-name branch, and lets differently named but structurally identical nested
two-space fixtures describe the same bounded input relation.

## Independence and identity

Desired behavior is accepted only when the probe already carries an allowed
independent probe, input, and expectation basis. Model-only expectation is
`insufficient_basis`. An existing test cannot serve both as the probe's desired
behavior source and as an independent comparator. A candidate-modified or
candidate-generated selected check remains invalid and is never rehabilitated.

Each `CheckOracleAssessment` binds:

- exact check id and path;
- check-source SHA-256 and a check fingerprint;
- immutable probe fingerprint;
- optional candidate fingerprint for execution traceability;
- factual check execution outcome;
- oracle role, explicit role basis, and assessment status.

A changed probe fingerprint or changed selected source makes the prior
assessment stale. Role semantics are not otherwise candidate-specific.

## Execution facts

Candidate check outcomes come only from the existing targeted validation
receipt. An overall pass proves every executed selected check passed. For a
failed multi-check execution, a check is marked failed only when pytest's
bounded failure summary names its exact selector; otherwise the individual
outcome is `outcome_unresolved`. Semantic conflict never manufactures an
execution failure.

The emitted evidence matrix keeps these facts side by side:

```text
full validation:       inconclusive / budget exhausted
pre-patch probe:       reproduced
post-patch probe:      fixed
targeted validation:   failed
selected check role:   defect_preservation_oracle
```

This is a truthful evidence conflict, not `inconsistent_input`.

## T6

The two selected `_classify_indent` checks are parsed from their actual source.
Both call the same target over the same typed nested two-space input shape and
assert `4space` (one also rejects `2space`), while the independently preserved
probe expects `2space`. Both checks therefore remain `failed` and receive the
additive role `defect_preservation_oracle`. Their names are never inspected for
semantic hints. The production `_classify_indent` source and the tests remain
unchanged.

## Frozen boundaries

`OPS.VALIDATE.3` still owns selection and execution. Full validation, the
pre/post probe, targeted validation, patch basis, patch safety, execution
authority, human approval, retrieval, ranking, graph construction, global
timeouts, and answer grounding are unchanged. The classifier performs zero
model calls, network calls, repository traversals, test generation, validation
executions, or real-repository mutations.
