# Depth-Variant Behavioral Discrimination Matrix

**Phase:** DEFECT.PROBE.LIVE.4
**Date:** 2026-09-09
**Track:** OPS
**Prerequisites:** DEFECT.PROBE.LIVE.1/.2/.3, DEFECT.FACT.LIVE.1,
CANDIDATE.VERIFY.LIVE.1, PATCH.MINIMAL.LIVE.1, PATCH.BASIS.LIVE.1,
VALIDATE.ORACLE.LIVE.1, OPS.VALIDATE.3, CONTROL.LOCALIZE.LIVE.2

---

## 1. The measured problem

DEFECT.PROBE.LIVE.3 asks a candidate two questions, both derived from the same
typed behavioral fact:

| case | indentation unit | expected |
| --- | --- | --- |
| primary defect | 2 spaces | `2space` |
| preservation | 4 spaces | `4space` |

That pair is enough to reject the Round-7 branch-reorder candidate, which makes
the 2-space fixture classify correctly by making the 4-space fixture classify
incorrectly. It is not enough for a candidate measured in Round 8:

```
ordinary nested 2-space                  expected 2space   candidate 2space   PASS
ordinary nested 4-space                  expected 4space   candidate 4space   PASS
2-space, indentation only at depth >= 3  expected 2space   candidate None     FAIL
4-space, indentation only at depth >= 2  expected 4space   candidate None     FAIL
```

`fixed_and_preserved` under the two-point oracle was therefore not sufficiently
discriminating for the existing production subject `indentation_style`. This is
a **measured verifier gap**, not a hypothetical one.

The reason is a category error in the oracle, not in the probe. For
`indentation_style`, classification refers to the **base indentation unit**, not
to the absolute number of leading spaces on any one observed line. A unit of
2 spaces covers depths 2, 4, 6, 8; a unit of 4 covers 4, 8, 12, 16. A repository
does not stop being 2-space because its acquired sample contains no line indented
by exactly two spaces. Both LIVE.3 cases happen to put a line at exactly one
indentation unit in front of the classifier, so a candidate that recognises the
*width* 2 and the *width* 4 — and nothing else — satisfies both.

## 2. What this phase changes

The oracle, and only the oracle. Probe execution, candidate authoring, sandbox
creation, `safe_minimal`, targeted-validation budgets, retrieval, control
ranking and every authority boundary are untouched. The same immutable
`DefectProbeContract` runs through the same static worker in the same single
managed sandbox; the matrix changes **which bounded inputs are probed**, not how
a probe runs.

A new pure module `core/behavioral_matrix.py` builds one bounded deterministic
four-case matrix for the one production subject a typed behavioral expectation
currently carries, runs it, and reduces it.

## 3. The matrix

For the exact live T6 fact (`expected_value=2space`,
`claimed_observed_value=4space`):

| case id | role | provenance | fixture | expected |
| --- | --- | --- | --- | --- |
| `indentation_style.primary.2space` | `primary_defect` | `explicit_user_fact` | 2-space, depths `(0,1,2,3,3,2,1)` | `2space` |
| `indentation_style.generalize.2space.deep` | `defect_generalization` | `system_derived_subject_invariant` | 2-space, depths `(0,3,4,4,3)` | `2space` |
| `indentation_style.preserve.4space` | `preservation` | `system_derived_behavior_preservation` | 4-space, depths `(0,1,2,3,3,2,1)` | `4space` |
| `indentation_style.preserve.4space.deep` | `preservation_generalization` | `system_derived_subject_invariant` | 4-space, depths `(0,2,3,3,2)` | `4space` |

Four cases. No random values, no Hypothesis, no generated depth search, no
combinatorial exploration, no coverage padding.

**Provenance is not laundered.** Only the primary case carries the user's own
provenance, and `BehavioralMatrixCase.__post_init__` refuses to construct a
derived case that claims it. The original preservation case keeps LIVE.3's own
`system_derived_behavior_preservation`, so a legacy reader sees exactly the
label it always saw.

## 4. Fixtures

Cases A and C are built by the frozen constructors that built them before —
`build_probe_contract_from_behavior_fact` and
`paired_defect_probe.build_preservation_cases` — so their bytes cannot drift.

Cases B and D need a depth-selectable sample, which
`core.defect_probe._nested_indentation_fixture(width)` cannot express and which
is AST-pinned by `tests/fixtures/defect_fact_live1_frozen_probe_execution.json`.
Rather than edit a frozen generator or hand-write program strings, the new module
carries one primitive that takes both dimensions:

```python
indentation_depth_fixture(width, depths=(0, 1, 2, 3, 3, 2, 1)) -> str
```

`indentation_depth_fixture(w)` reproduces `_nested_indentation_fixture(w)`
byte-for-byte at every width the value grammar accepts (1–8), which the test
suite pins. It is the same construction with the depth sequence made explicit,
not a second fixture idea.

**Depth selection is derived, not chosen.** `depth_only_depths(unit, collisions)`
returns the shallowest depth pair whose widths land on neither of the two widths
the typed fact names, bounded at `MAX_DEPTH_ONLY_START = 4`:

* unit 2, collisions `{2, 4}`: depth 2 → 4 spaces, which is the 4-space unit, so
  the pair starts at depth 3 → widths `{6, 8}`;
* unit 4, collisions `{2, 4}`: depth 2 → 8 spaces, which is neither → widths
  `{8, 12}`.

That lands exactly on the depths Round 8 measured, and the shape keeps the
ordinary fixture's rise-and-fall so the two families differ in nothing but which
nesting levels appear.

**Depth-only means depth-only**, pinned structurally: each deep fixture is
asserted to contain no line at one indentation unit *and* no line at the
collision partner's unit, to have every width divisible by its unit, and to
contain at least two distinct depths so the unit is recoverable at all.

## 5. Reduction

Per-case vocabulary is split by role, and the dataclass refuses a verdict from
the wrong family:

* defect cases (`primary_defect`, `defect_generalization`) → `fixed`,
  `still_reproduced`, `changed_but_unresolved`, `inconclusive`, `unavailable`;
* preservation cases → `preserved`, `regressed`, `inconclusive`, `unavailable`.

A preservation case keeps LIVE.3's precondition: it is an oracle only where the
baseline already satisfies it. Where the baseline already fails, the case is
reported `unavailable` with `baseline_did_not_satisfy_the_case` and its candidate
probe is not consulted at all — a regression is never manufactured from
behavior that was already wrong.

A defect-generalization case may fail on the baseline. That is valid and
expected: it establishes that the bounded subject invariant exposes the same
behavior family, and it creates no second user claim.

`reduce_behavioral_matrix` closes the matrix in one fixed, fail-closed order:

1. any preservation case the baseline satisfied and the candidate broke →
   `fixed_but_regressive`;
2. no cases at all → `unavailable`;
3. any required case with no verdict → `inconclusive`;
4. no defect case closed, each still producing its baseline value →
   `still_reproduced`;
5. no defect case closed, at least one changed without closing →
   `unresolved_matrix_failure`;
6. some defect cases closed and at least one not → `partially_fixed`;
7. every defect case closed and every available preservation case held →
   `fixed_and_preserved`.

`partially_fixed` exists so a candidate that satisfies the user's own claim and
fails its own subject's invariant cannot be rounded up to `fixed`. One passing
case never speaks for another.

## 6. Compatibility

`evaluate_behavioral_closure` is the single entry point the pipeline calls.

* **Subject with no matrix** → it delegates to
  `evaluate_paired_defect_closure` and returns a DEFECT.PROBE.LIVE.3 receipt.
  Every task outside the one supported subject keeps exactly the behavior it
  had. `core/paired_defect_probe.py` is byte-identical.
* **Subject with a matrix** → the matrix is authoritative. The receipt still
  carries a real LIVE.3 half covering exactly the cases LIVE.3 ran — the primary
  case and the one ordinary preservation counter-case, resolved by LIVE.3's own
  rules — so a pre-LIVE.4 reader sees what it expects and no historical receipt
  is reinterpreted as though depth-variant cases had executed.

`paired_status` and `defect_closure_status` are then **narrowed** to the matrix's
verdict wherever the matrix is stricter, never widened. `fixed` is reachable only
from `fixed_and_preserved`. A reader written before this phase cannot be told a
candidate closed when the matrix says the subject invariant did not.

CANDIDATE.VERIFY.LIVE.1 consumes the matrix reduction where matrix evidence is
bound to the exact candidate and probe, via a new `_matrix_verdict` reading
`behavioral_matrix`. A new closed rejection reason,
`subject_invariant_not_closed`, distinguishes "the primary claim closed and a
derived case did not" from "the primary defect is still open". A receipt with no
matrix takes the legacy path and records
`no_behavioral_matrix_for_subject` as an accepted limitation.

## 7. Cost

One sandbox. Every case runs against the same applied candidate bytes in the
single managed sandbox DEFECT.PROBE.LIVE.2 creates, through
`evaluate_candidate_defect_closure`'s existing `preservation_probes` channel.
The primary case's baseline and candidate observations are read off the closure
receipt rather than re-executed, so the added cost is three companion baseline
probes and three companion candidate probes — `O(fixed case count)` — and no
second patch application.

Timings are reported by stage: `matrix_construction_sec`, `matrix_baseline_sec`,
`matrix_candidate_probe_sec`, `matrix_reduction_sec`, `matrix_total_sec`.
Measured on the live T6 target: construction and reduction under a millisecond,
matrix total ≈ 4.2–5.3 s against ≈ 2.4 s for the LIVE.3 pair.

## 8. Measured acceptance

Replayed against the exact current T6 target and contract, read-only, with the
real `core/code_dna.py` asserted byte-identical throughout:

| candidate | pre-LIVE.4 | post-LIVE.4 | verification |
| --- | --- | --- | --- |
| exact no-op | rejected by PATCH.MINIMAL.LIVE.1 | unchanged — matrix never entered | rejected, 0.00 s |
| inverted branch reorder | `fixed_but_regressive` | `fixed_but_regressive` | rejected |
| **Round-8 ceiling** | **`fixed_and_preserved` / `fixed`** | **`fixed_but_regressive`** | **rejected** |
| unit-inferring control | `fixed_and_preserved` | `fixed_and_preserved` | verified |

Per-case for the Round-8 ceiling candidate:

```
indentation_style.primary.2space          baseline=reproduced  candidate=fixed                  observed='2space'
indentation_style.generalize.2space.deep  baseline=reproduced  candidate=changed_but_unresolved observed=None
indentation_style.preserve.4space         baseline=satisfied   candidate=preserved              observed='4space'
indentation_style.preserve.4space.deep    baseline=satisfied   candidate=regressed              observed=None
```

The ordinary cases still pass; both depth variants fail; the matrix refuses
closure. That difference is the whole phase.

`execution_authorized=false` and `final_repository_changed=false` for every
candidate including the verified one — matrix success is verification evidence
and grants nothing.

The tests measure the depth-variant half rather than merely running: with
`build_behavioral_matrix` degraded to LIVE.3's two cases, **25 of 73 fail**;
restored (byte-identical, sha256 verified), all 73 pass.

## 9. What this phase does not do

`_classify_indent` is **not** repaired. The positive control is test-only, is
never applied to production, and is not made available to any model. Round 8
also established that a genuinely correct implementation is likely not
expressible under the current lexical novelty restrictions; that is
PATCH.MINIMAL.LIVE.2's problem and is deliberately not begun here. The verifier
had to be able to reject the measured oracle-overfitting candidate first.

`safe_minimal`, the OPS.VALIDATE.3 targeted-validation budgets (3 files, 8
checks, selector, commands), `BehavioralExpectation` extraction, RETRIEVE,
CONTROL, and the EXEC.AUTH/POLICY/APPROVAL boundaries are untouched and pinned
by whole-file digest in
`tests/fixtures/defect_probe_live4_frozen_boundaries.json`. No model call, no
network call, no repository traversal is added.

## 10. A consequence worth naming

CANDIDATE.VERIFY.LIVE.1's positive control was the smallest-observed-width
candidate, which closed LIVE.3's two-point oracle. Under the matrix it is
`partially_fixed`: it is correct for both ordinary widths and for the deep
4-space sample, and it still cannot classify a 2-space sample whose shallowest
line is six spaces wide. The invariant it carried — "verification opens" — has
moved to a candidate that answers every bounded case, and the old candidate is
kept as `T6_SUBJECT_INVARIANT_OPEN_PATCHED` with a test recording exactly what
became of it. Widening an oracle is supposed to invalidate the controls that
only satisfied the narrow one; the honest response is to re-home the invariant,
not to delete the test.

## 11. Files

**Added**

* `core/behavioral_matrix.py`
* `tests/test_defect_probe_matrix_live.py`
* `tests/fixtures/defect_probe_live4_frozen_boundaries.json`
* `docs/designs/2026-09-09-depth-variant-behavioral-discrimination-matrix.md`

**Changed**

* `core/pipeline.py` — calls `evaluate_behavioral_closure`; records the matrix
  telemetry keys with the candidate they describe
* `core/candidate_verification.py` — `_matrix_verdict`, consumed ahead of the
  legacy paired reading (1 of 22 top-level definitions changed, 1 added, 0
  removed)
* `tests/test_candidate_verification.py` — positive control re-homed
* `tests/test_patch_minimal_live.py` — producer map names the LIVE.4 entry point
* `tests/fixtures/answer_ground_live4_frozen_boundaries.json` — re-pinned
* `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`,
  `tests/test_phase_picker.py`
