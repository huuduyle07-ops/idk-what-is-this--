# OPS.VALIDATE.3 — Bounded Targeted Repository Validation

## Outcome

OPS.VALIDATE.3 adds live deterministic regression evidence for the specific
large-repository case in which whole-repository validation was attempted but
did not finish within its existing budget.  It selects a small set of existing
repository-owned pytest checks from the operation-scoped graph, runs the exact
same immutable check set on a baseline sandbox and an exact-candidate sandbox,
and reports `passed`, `failed`, or `inconclusive`.

It does not change the full-suite fact, the independent defect-probe fact, or
execution authority.

## Three separate facts

1. `DEFECT.PROBE.LIVE.1` asks whether the claimed bounded behavior reproduces.
2. `OPS.VALIDATE.3` asks whether unchanged existing checks structurally related
   to the changed area pass before and after the candidate.
3. `OPS.VALIDATE.1/.2` asks whether the complete configured repository
   validation passed.

A targeted pass is worded as “The bounded relevant checks passed.”  It is never
worded as “repository validation passed.”  If the full suite remains
`inconclusive / validation_budget_exhausted`, that fact remains unchanged.

## Production trigger

The live adapter runs only when all of these already-established facts coexist:

- task route is `defect_repair_patch`;
- patch basis is `grounded_defect`;
- full validation is `inconclusive / validation_budget_exhausted`;
- the frozen pre-patch probe result is `reproduced` with an independently
  qualified oracle and exact target binding;
- exact candidate exists and existing patch safety passes; and
- the operation-scoped `ProgramGraph` is available.

Analysis-only, explicit-change, passing full validation, and genuine full-suite
failure flows do not trigger it.  Thus T1/T2/T3 keep normal full validation and
explicit-change continues through OPS.PATCH.2.

## Immutable request

`TargetedValidationRequest` is frozen and binds:

- canonical root-derived repository identity;
- OPS.PATCH.2 candidate fingerprint;
- normalized changed paths and localized symbols;
- selected existing checks and their graph provenance;
- selection completeness/reason and check-set fingerprint;
- a 20-second total budget;
- caps of three test files and eight test nodes; and
- `disposable_sandbox_no_copy_back` side-effect policy.

It contains no confidence and no model reasoning.

## Deterministic selection

Selection reads the already-loaded graph only.  It performs no filesystem test
discovery, repository walk, index query, graph rebuild, semantic similarity, or
model call.  The strongest non-empty tier wins:

1. bounded safe pytest selectors explicitly preserved from the user command;
2. test symbols with a `resolved_call` edge to the localized changed symbol;
3. test modules with an `imports` edge to the changed source module.

Only conservative Python pytest paths and `file::test_name` selectors are
emitted.  The runner constructs an argv list using the current Python
interpreter and `-m pytest`; arbitrary node IDs are never shell-concatenated.
Other frameworks currently return unavailable/inconclusive.

If a tier produces more than eight checks or more than three files, selection
returns `inconclusive / selection_budget_exceeded` with no partial highest-ranked
pick.  If no relation exists, the result is `inconclusive /
no_relevant_existing_checks`; zero tests can never pass.

## Baseline and candidate

The baseline runs in a disposable managed copy of the current candidate-source
state.  The candidate runs in a separate disposable managed copy.  The exact
plan is applied with OPS.PATCH.1/OPS.PATCH.2 machinery, then the same request
selectors run through the safe argv validation runner.  Its isolated
`PYTHONPYCACHEPREFIX` supplies current-source bytecode freshness.  Pytest plugin
autoload and cacheprovider are disabled; remaining generated files die with the
sandbox.  Nothing is copied to the real repository.

The comparison rules are categorical:

- baseline passed + candidate passed => targeted passed;
- baseline passed + candidate failed => targeted failed;
- baseline failed => targeted inconclusive, regardless of candidate result;
- baseline inconclusive => targeted inconclusive;
- timeout => `inconclusive / validation_budget_exhausted`;
- missing pytest/tooling => inconclusive;
- candidate apply failure => failed candidate materialization, not a fabricated
  test verdict.

There is no “failure count improved” score.

## Identity and oracle integrity

The request fingerprint must match the current plan at evaluation time.  A
refinement makes the old result stale, and the pipeline removes the entire old
targeted telemetry group without touching full-validation or probe receipts.

If the candidate changes a selected test path, targeted validation stops before
either run with `inconclusive / selected_validation_check_modified`.  Therefore
a candidate cannot rewrite its oracle and use that test as evidence.  Existing
test-path patch safety remains an independent earlier defence.

## Probe relationship

The frozen pre-patch probe result is copied as a separate telemetry fact.  It is
not merged into targeted status.  A successful probe cannot override a targeted
test failure, and a targeted pass does not assert that the probe is fixed.
OPS.VALIDATE.3 does not add post-patch probe re-execution; a later authority
policy requiring that evidence must obtain and preserve a separate post-patch
probe receipt.

## Authority

Targeted telemetry says `targeted_validation_authority_effect=none`.  The live
adapter records the result and deliberately does not branch on it for
authorization.  It cannot set `execution_authorized`, `auto_apply_allowed`,
`write_authority`, or `patch_application_authority`.  Existing AUTO_PATCH,
CTX.PATCH/CTX.APPLY, patch safety, human approval, execution receipt, full
validation, and rollback policies remain authoritative.

## Telemetry

The bounded payload exposes:

- targeted status/category/reason;
- selected/executed check identifiers and selection provenance;
- selection completeness and reason;
- baseline/candidate outcomes and executed sets;
- budget, candidate fingerprint, and check-set fingerprint;
- selection, sandbox creation, baseline, apply, candidate, cleanup, and total
  timings;
- separate pre-patch probe and full-validation facts; and
- zero authority, model, network, and traversal deltas.

No source contents or hidden reasoning are included.

## T6 dogfood expectation

Production selection must discover C.A.T.T.U.S checks for
`core/code_dna.py::_classify_indent` from the loaded graph rather than a
hardcoded filename or symbol branch.  If graph relations exceed the cap or no
relation exists, the measured result is honestly inconclusive.  The phase does
not modify `_classify_indent` and does not force a successful targeted verdict.

## Known limitations

- Python/pytest is the only live targeted framework in this phase.
- File-level imports are direct edges only; no semantic or transitive inference
  is attempted.
- Direct-call resolution is only as precise as the already-loaded graph.  An
  over-broad relation set fails closed at the cap.
- Managed sandbox copy time is measured and checked between stages; the existing
  synchronous sandbox copier itself is not pre-emptible mid-copy.
- Passing legacy tests is regression evidence, not proof that a proposed defect
  fix is semantically correct.
- No targeted-validation-based auto-apply policy is introduced.

## Frozen deltas

Zero model calls, zero generated tests, zero network calls, zero dependency
installation, zero new repository traversal, zero graph rebuild, zero retrieval
or ranking change, zero global-timeout increase, zero automatic authority
widening, and no `_classify_indent` fix.  This is a live validation capability,
not report-only.
