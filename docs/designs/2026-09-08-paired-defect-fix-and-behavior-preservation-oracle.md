# DEFECT.PROBE.LIVE.3 — Paired Defect-Fix & Behavior-Preservation Oracle

*2026-09-08 · track OPS · automation LOCAL_1_PREPARE · risk medium*

## The measurement

T6 is a defect-repair order: `2-space indentation is classified as 4-space`.
Everything upstream of the oracle already works, and this phase changed none of
it.

| Stage | State entering this phase |
| --- | --- |
| CONTROL.LOCALIZE.LIVE.2 | `core/code_dna.py::_classify_indent` |
| DEFECT.FACT.LIVE.1 | `BehavioralExpectation(indentation_style, expected=2space, observed=4space, explicit_user_fact)` |
| DEFECT.PROBE.LIVE.1 | fixture width 2, expected `2space`, observed `4space` → `reproduced` |
| PATCH.BASIS.LIVE.1 | `grounded_defect` |

The model authored this candidate:

```python
elif line.startswith("  "):
    counts["2space"] += 1
elif line.startswith("    "):
    counts["4space"] += 1
```

It is minimal, it touches one function, and `safe_minimal` correctly accepts its
shape. What it does is reverse the prefix overlap rather than resolve it, and
the consequence is measurable at both widths:

| `_nested_indentation_fixture(width)` | baseline | branch-reorder candidate |
| --- | --- | --- |
| width 2 (the user's `expected_value`) | `4space` — wrong | `2space` — **correct** |
| width 4 (the user's `observed_value`) | `4space` — correct | `2space` — **broken** |

DEFECT.PROBE.LIVE.2 asks only the first row's question, so it reported
`defect_closure_status = "fixed"`, and `EXEC.POLICY.LIVE.1` read that status and
reached `human_review_eligible = True`. Both were behaving exactly as specified.
The defect was that one expected-value probe cannot distinguish *repairing* a
collision from *reversing* it.

## What changed

Only the oracle. The same immutable contract runs through the same static
worker in the same managed sandbox; no probe execution primitive, candidate
author, ranking coefficient, retrieval path or authority setter was touched.

### 1. A subject adapter that yields preservation counter-cases

`core/paired_defect_probe.py` maps a behavior subject to zero or more
deterministic counter-cases:

```
behavior subject → optional deterministic preservation cases
```

`indentation_style` is the only production subject a typed behavioral
expectation currently carries, so it is the only entry in the table. Its
counter-case is the collision partner the fact already exposes: the user's
`observed_value` probed at *its own* width, expecting itself.

```
primary case:        _nested_indentation_fixture(2) → expect "2space"
preservation case:   _nested_indentation_fixture(4) → expect "4space"
```

`_nested_indentation_fixture` is reused exactly — §2 of the order, and the
function is digest-pinned by DEFECT.FACT.LIVE.1. There is no second indentation
fixture generator, and the module asserts as much about its own source.

Every other subject returns nothing. An empty result is the truthful answer for
a subject with no adapter, for a fact whose values this phase cannot read, and
for legacy transport that carries no typed fact at all. It is never an
approximation, and nothing generalises a counter-case for a subject that has not
been designed one.

### 2. A baseline precondition, so a counter-case is only ever an oracle

A counter-case the unpatched repository already fails proves nothing about a
candidate. Each preservation contract therefore runs read-only against the real
repository first, at `pre_patch` stage, and only a `not_reproduced` baseline is
promoted to an oracle. A baseline that fails, or that reaches no verdict, yields
an explicit `unavailable` case with a reason — never a manufactured regression.

### 3. Separate representation, then a closed pair

```
primary_case:        expected · baseline_observed · candidate_observed · status
preservation_cases:  case_id · expected · baseline_observed ·
                     candidate_observed · status · provenance
paired_status:       the closed assessment over both
```

The paired vocabulary reuses DEFECT.PROBE.LIVE.2's where it can and splits
`fixed` where it must:

| `paired_status` | meaning |
| --- | --- |
| `fixed_and_preserved` | primary closed, every available counter-case held |
| `fixed` | primary closed, no preservation oracle available (pre-existing meaning) |
| `fixed_but_regressive` | primary closed, a counter-case the baseline satisfied broke |
| `still_reproduced` · `changed_but_unresolved` · `inconclusive` · `invalid_comparison` · `unavailable` | unchanged |

Only a fixed primary can be qualified by preservation. A primary that did not
close is already answered by the existing vocabulary, and a preservation
observation may not make it better or worse than it is.

### 4. Provenance stays separated

The primary expectation is `explicit_user_fact`, unchanged. The preservation
expectation is `system_derived_behavior_preservation`, and
`PreservationCaseResult` raises if anything tries to give it user provenance.
The contract's own `provenance_reference` says in words that its expected value
is the behavior the unpatched code already produces and *not* a user
requirement, naming the user's actual requirement so the two can never be read
as one claim.

## Downstream compatibility

`defect_closure_status` is the field every existing consumer reads, and it is
compared against the literal `"fixed"` in `core/execution_eligibility_policy.py`
and `core/check_oracle_assessment.py`. Rather than rewrite those readers, this
phase makes the field truthful:

* `fixed_and_preserved` → `fixed`, so a correct candidate loses nothing it had;
* no preservation oracle → the primary status, byte-for-byte what T1/T2/T3 and
  every unsupported subject recorded before this phase existed;
* `fixed_but_regressive` → `fixed_but_regressive`, which no reader will ever
  mistake for a closure.

That leaves `core/execution_eligibility_policy.py` byte-identical: the
regressive status falls through its existing `else` branch to
`BLOCK_POST_PROBE_NOT_FIXED / INELIGIBLE`. VALIDATE.ORACLE gained exactly one
branch — a description that names the regression instead of restating the
targeted-check story — and nothing else.

Patch basis is untouched (§10). The pre-patch reproduction is a fact about the
repository, not about the candidate, so `grounded_defect` survives a regressive
candidate; what the candidate loses is closure readiness, which was never
authority to begin with.

## Boundaries

`core/candidate_defect_probe.py` gained two things and nothing else: an optional
`preservation_probes` parameter that runs already-built contracts against the
*same* sandbox bytes the primary post-probe saw — one sandbox, one apply, so the
two halves of a pair can never describe different candidates — and the
`fixed_but_regressive` status. With no preservation probes supplied it behaves
exactly as it did before, and one test keeps proving it by measuring the
original defect against the unchanged single-case function and watching it
still answer `fixed`.

`tests/fixtures/defect_probe_live3_frozen_boundaries.json` pins, by whole-file
digest, everything this phase was forbidden to change: the probe execution
engine and its worker, `BehavioralExpectation` extraction, the production
`_classify_indent` this phase measures but does not repair, every authority and
eligibility surface, OPS.VALIDATE.3, patch basis and safety, CONTROL ranking and
RETRIEVE recall, and the sandbox/apply primitives. It also pins, by AST digest,
the DEFECT.PROBE.LIVE.2 comparison-integrity rules — what makes a comparison
valid, what makes it stale, and how the managed sandbox is disposed of — which
is the finer-grained invariant that CONTROL.LOCALIZE.LIVE.2's now re-pinned
whole-file digest for `core/candidate_defect_probe.py` used to carry.

## Stop condition

The exact T6 branch-reorder candidate now measures as:

```
primary:       expected 2space · baseline 4space · candidate 2space · fixed
preservation:  expected 4space · baseline 4space · candidate 2space · regressed
paired:        fixed_but_regressive
closure:       fixed_but_regressive   (never "fixed")
eligibility:   human_review_eligible = False
```

and the width-distinguishing positive control measures as
`fixed_and_preserved`, so the oracle opens as well as it closes. No-auto-patch
candidate verification is explicitly *not* begun here.
