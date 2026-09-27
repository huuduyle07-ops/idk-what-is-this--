# DEFECT.PROBE.LIVE.2 — Immutable Pre/Post Candidate Reproduction Closure

## Outcome

C.A.T.T.U.S can evaluate an exact final defect-repair candidate against the
same independent behavioral probe that reproduced the pre-patch symptom.  The
candidate is applied only to a managed disposable sandbox; the real repository
is never a candidate target and nothing is copied back.

The live evidence chain is:

```text
immutable typed probe P -> current source -> reproduced observation
exact safe candidate C  -> managed sandbox -> real patch-plan apply
same P and same oracle  -> current sandbox source -> post observation
```

The closure receipt is candidate evidence, not repository validation and not
execution authority.

## Immutable probe identity

`DefectProbeContract.fingerprint` is SHA-256 over canonical JSON containing the
semantically significant typed fields:

- exact repository/file/symbol target and localized pre-patch source binding;
- invocation kind and structured JSON input;
- expected relation and expected JSON result;
- probe, input and expectation provenance, reference and bound source paths;
- timeout, read-only/no-network side-effect policy, test selector and schema.

Timestamps and run IDs are absent.  The post run receives the original contract
object; it does not derive a candidate-specific input or expectation.  The
sandbox execution location is recognized as a copy of the original repository
without rebinding the target or changing the fingerprint.

## Candidate identity and ordering

The receipt uses `OPS.PATCH.2`'s canonical patch-plan fingerprint.  A caller may
also supply the already-bound expected fingerprint; a mismatch stops before
sandbox creation.  Stored evidence is current only while that fingerprint still
matches the final candidate.  Pipeline refinement removes the entire stale
candidate-probe telemetry group.

Existing gates run first:

```text
patch basis -> target/source grounding -> patch safety -> candidate probe
```

`patch_safety.ok` must be exactly true.  A denial is not materialized merely to
learn how it behaves.  The sandbox uses the existing managed copier and marker-
guarded cleanup, while `patching.patch_plan_executor.apply_patch_plan` supplies
the real OPS.PATCH.1 byte semantics.  No alternate apply helper exists.

## Oracle integrity

Explicit user requirements and deterministic preserved task facts live outside
candidate-controlled repository bytes.  Repository contracts and existing-test
expectations require immutable source-artifact bindings.  If the candidate
touches a bound oracle artifact, comparison is `invalid_comparison` before any
candidate bytes are written.

Model-authored input or expectation remains disallowed by
`DEFECT.PROBE.LIVE.1`.  Even a candidate that changes `add(2, 2)` to return a
model-invented expected value of `5` cannot produce legitimate fixed evidence.

## Result vocabulary

The closure vocabulary is categorical and contains no confidence:

| Status | Meaning |
|---|---|
| `fixed` | Pre reproduced, the immutable post probe observed its independent expectation. |
| `still_reproduced` | The exact same wrong observation remains. |
| `changed_but_unresolved` | The observation changed but is still not expected. |
| `inconclusive` | Timeout, worker/import/tool failure, freshness failure, or cleanup uncertainty prevented a verdict. |
| `invalid_comparison` | Probe/oracle/candidate identity or provenance was not comparable. |
| `unavailable` | No safe materializable candidate/sandbox evaluation was available. |

Telemetry exposes the probe and candidate fingerprints, both probe results and
observations, expectation basis, closure status, `sandbox_only=true`, apply and
cleanup facts, and separate sandbox-create/apply/probe/cleanup/total timings.

## Independent validation and authority facts

The live adapter writes only candidate-probe telemetry.  It does not read or
rewrite:

- full repository validation;
- OPS.VALIDATE.3 targeted baseline/candidate validation;
- the DEFECT.PROBE.LIVE.1 pre-patch receipt;
- PATCH.BASIS;
- execution authorization or human approval.

Consequently this is a valid representable state:

```text
pre probe             reproduced
post probe            expected behavior observed
defect closure        fixed
targeted baseline     passed
targeted candidate    failed
full validation       inconclusive / validation_budget_exhausted
execution authorized  false
```

Neither the targeted failure nor the fixed probe overwrites the other.  No
targeted-validation-based auto-apply policy is introduced.

## T6 dogfood

The test fixture builds a normal deterministic patch plan for
`core/code_dna.py::_classify_indent`.  Current real source observes `4space` for
the existing nested two-space fixture.  The same probe observes `2space` after
the plan is applied in a sandbox, so closure is `fixed`.

The two structurally selected defect-preservation tests run separately against
the same candidate.  They pass on baseline and fail on the fixed candidate, as
expected from their current role.  Their names are not special-cased in
production.  The real `core/code_dna.py` remains broken and byte-identical.

## Frozen deltas

No generated tests, model calls, network calls, dependency installation,
retrieval change, graph traversal, test-selection change, validation-score
aggregation, global-timeout change, authority widening, stash, reset or clean.
Analysis-only, feature/explicit-change and ordinary meaningful T1/T2/T3
validation flows remain unchanged.
