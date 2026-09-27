# DEFECT.PROBE.LIVE.5 — Distribution-Skew Indentation Unit Discrimination

**Date:** 2026-09-10
**Track:** OPS (phase-id namespace `DEFECT.*`, no new track, no schema dimension)
**Status:** complete
**Prerequisites:** DEFECT.PROBE.LIVE.1–.4, DEFECT.FACT.LIVE.1, PATCH.MINIMAL.LIVE.1/.2,
PATCH.AUTHOR.LIVE.1, CANDIDATE.VERIFY.LIVE.1, PATCH.BASIS.LIVE.1,
CONTROL.LOCALIZE.LIVE.2, OPS.VALIDATE.3

---

## 1. The measured ceiling

DEFECT.PROBE.LIVE.4 asks a candidate four bounded questions about one typed
indentation fact. Round 9 authored a revised candidate that answers all four and
still does not infer the base indentation unit. Its substance, reconstructed from
the captured provider response:

```python
for line in text.splitlines():
    stripped = line.lstrip('\n\r')
    if not stripped or stripped[0] not in " \t":
        continue
    indent = len(stripped) - len(stripped.lstrip(" \t"))
    if "\t" in stripped[:indent]:
        counts["tab"] += 1
    elif indent % 4 == 0:
        counts["4space"] += 1
    elif indent % 2 == 0:
        counts["2space"] += 1
```

It stops testing prefixes in an order and measures the real leading width — which
is why it clears the Round-8 ceiling — and then **votes on the absolute width**.
It is therefore correct exactly when the right width family happens to hold a
majority, and every LIVE.4 fixture gave it one.

The deterministic diagnostic found the smallest shape where it does not: one line
at one indentation unit and two at two.

| | widths | true unit | baseline | Round-9 Candidate₁ | unit-inferring control | expected |
|---|---|---|---|---|---|---|
| skew | `[2, 4, 4]` | 2 | `4space` | `4space` | `2space` | **`2space`** |
| mirror | `[4, 8, 8]` | 4 | `4space` | `4space` | `4space` | `4space` |

Absolute-width votes on the skew shape are `4space` two to `2space` one. So the
measured ceiling is:

```
base indentation unit  !=  most frequent classified absolute indentation width
```

That is a measurement, not a hypothesis. The mirror discriminates nothing — every
candidate answers it — which is why it is a regression control here and never a
required production case (§6 of the phase brief).

## 2. What changed

One production file, one appended case.

| File | Change |
|---|---|
| `core/behavioral_matrix.py` | 3 definitions added, 0 removed, 3 changed |
| `tests/test_defect_probe_matrix_live5.py` | new, 44 tests |
| `tests/fixtures/defect_probe_live5_frozen_boundaries.json` | new: 33 pinned files + the reversal proof |
| `tests/fixtures/patch_author_live1_frozen_boundaries.json` | re-pin + the pre-LIVE.5 digest it replaced |
| `tests/test_defect_probe_matrix_live.py` | 11 counter updates, no semantic change |
| `tests/test_candidate_revision_live.py` | counter updates, no semantic change |
| `tests/test_phase_registry.py`, `tests/test_phase_picker.py` | registry counters |
| `docs/roadmap/phase_registry.json` | one appended entry |

Added: `indentation_skew_fixture`, `skew_consistent_units`, `_skew_contract`.
Changed: `_indentation_matrix_cases` (the appended case),
`BehavioralMatrixReceipt` (one additive telemetry field),
`behavioral_matrix_guardrails` (three new flags).

`core/defect_probe.py`, the defect probe worker, sandbox execution semantics,
`core/pipeline.py`, `core/candidate_verification.py`, `core/candidate_revision.py`,
`safe_minimal`, targeted validation, CONTROL, RETRIEVE, every authority module and
`_classify_indent` are byte-identical and pinned.

## 3. The five-case matrix

| | case id | role | provenance | expected |
|---|---|---|---|---|
| A | `indentation_style.primary.2space` | `primary_defect` | `explicit_user_fact` | `2space` |
| B | `indentation_style.generalize.2space.deep` | `defect_generalization` | `system_derived_subject_invariant` | `2space` |
| C | `indentation_style.preserve.4space` | `preservation` | `system_derived_behavior_preservation` | `4space` |
| D | `indentation_style.preserve.4space.deep` | `preservation_generalization` | `system_derived_subject_invariant` | `4space` |
| **E** | **`indentation_style.generalize.2space.skew`** | **`defect_generalization`** | **`system_derived_subject_invariant`** | **`2space`** |

Exactly five. A–D keep their identifiers, their contracts, their fixture bytes and
their positions; E is **appended**, never inserted, so no historical case is
renamed and no stored LIVE.4 receipt is reinterpreted. No new role vocabulary was
invented for frequency skew — `defect_generalization` already says what this is:
a system-derived generalization of the defect behavior, not a second user claim.

No ratio ladder reached production. No 1:3 or 1:4 variant. The diagnostic
established that 1:2 is sufficient, and `SKEW_DEPTHS` is one fixed tuple.

## 4. The fixture, and why it is real source

```python
def level_0():
  if level_1:
    level_2 = 2
    level_3 = 3
```

Built by `indentation_skew_fixture(2)`, which reuses the frozen generator's
`width * depth` arithmetic and makes the line bodies structural: a line whose
successor sits deeper opens a block, every other line is a statement. The same
generator at width 4 produces the mirror. Nothing is stored as a detached integer
width vector.

Pinned structurally by test:

- `ast.parse` succeeds, and the tree is a `FunctionDef` → `If` → two `Assign`
  nodes at `col_offset` 4
- positive widths `== [2, 4, 4]`; `min == 2`; `2 in widths`
- `count(4) > count(2)`
- every width divisible by 2
- max depth `<= 2`; exactly 3 indented sample lines
- depth distribution `{1: 1 line, 2: 2 lines}`
- nesting changes by at most one level per adjacent structural step
- deterministic bytes, asserted literally

## 5. Why `2space` is unambiguous — from the source, not from convention

A base indentation unit must divide every indentation width in a sample.
`skew_consistent_units(w)` returns the members of the subject's own classification
vocabulary (`SUBJECT_SPACE_UNITS == (2, 4)`, the space values `_classify_indent`
can return) that divide `w`:

| claimed width | fixture widths | consistent vocabulary units | verdict |
|---|---|---|---|
| 2 | `{2, 4}` | `(2,)` | unambiguous → required case |
| 4 | `{4, 8}` | `(2, 4)` | ambiguous → **case omitted** |

A four-space line is equally consistent with a two-space style indented twice, so
the mirror direction is genuinely undecidable from the bounded source. The adapter
**omits** the case there rather than deciding it by preference. That is the
derivation §5 of the brief asked for, expressed as code rather than as prose, and
it is why §6's "do not add the mirror" is obeyed for a reason rather than for
symmetry.

No style guide, PEP 8, internet knowledge, repository convention or user
preference is consulted anywhere in the phase.

## 6. Results

### The primary red/green proof

Same candidate bytes, same contract, same repository, same one sandbox:

| | cases | matrix status | closure_ready |
|---|---|---|---|
| PRE-LIVE.5 (four cases) | 4 | `fixed_and_preserved` | `True` |
| POST-LIVE.5 (five cases) | 5 | `partially_fixed` | `False` |

The four LIVE.4 verdicts are asserted **equal** across the two runs, so the
difference is the fifth case and nothing else.

### Round-9 Candidate₁, case by case

| case | expected | observed | status |
|---|---|---|---|
| A primary 2space | `2space` | `2space` | `fixed` |
| B deep 2space | `2space` | `2space` | `fixed` |
| C ordinary 4space | `4space` | `4space` | `preserved` |
| D deep 4space | `4space` | `4space` | `preserved` |
| **E skew** | **`2space`** | **`4space`** | **`still_reproduced`** |

Matrix: **`partially_fixed`** — some required defect cases closed and one did not.
Not `fixed_and_preserved`, and deliberately not `fixed_but_regressive`: nothing
regressed. The status is `still_reproduced` rather than `changed_but_unresolved`
because the baseline returned `4space` for this shape too, which is the existing
closed vocabulary's term for "the exact same wrong bounded behavior remains".

`CANDIDATE.VERIFY.LIVE.1` rejects it for `subject_invariant_not_closed`, through
the integration LIVE.4 already built. There is no Round-9 branch anywhere.

### Five candidates, five distinct rejections

| candidate | earliest rejection | matrix status |
|---|---|---|
| exact no-op | mutation effect, before any matrix work | none (matrix never built) |
| inverted reorder | preservation regression (case C) | `fixed_but_regressive` |
| Round-8 ceiling | depth generalization (cases B, D) | `fixed_but_regressive` |
| Round-9 absolute-width voting | **distribution skew (case E)** | `partially_fixed` |
| unit-inferring control | — verified | `fixed_and_preserved` |

The two `fixed_but_regressive` candidates regress *different* cases (C vs D),
which a test asserts, so the diagnostic separation is preserved rather than
assumed.

## 7. Cost

| | four cases | five cases |
|---|---|---|
| candidate sandboxes | 1 | 1 |
| companion baseline probes | 3 | 4 |
| companion candidate probes | 3 | 4 |
| primary baseline | reused, never re-probed | reused, never re-probed |

Delta: one baseline probe, one candidate probe. `O(5 fixed cases)`; no unbounded
search. All five cases bind to the same candidate fingerprint, the same target
binding and the same original-source digest — no new fingerprint primitive.

## 8. The oracle is not solution-aware

`core/behavioral_matrix.py` references no `ast`, `inspect`, `compile`, `exec`,
`eval` or `tokenize`, and contains none of the words `gcd`, `lstrip`, `histogram`,
`divisor`, `modulo` or `most_common`. A test runs a deliberately odd
implementation — a `while` loop counting columns, then a hand-rolled
smallest-then-divisibility check — and it passes on behavior alone.

The revision request may learn *"this candidate returned `4space` for this
required case"*. It may not learn *"use GCD"*, *"measure the minimum width"* or
*"don't vote by frequency"*. PATCH.AUTHOR.LIVE.1's authoring logic is unchanged;
the new failing case simply appears in `CandidateRevisionEvidence.failed_cases`
through the mechanism that already existed.

## 9. Schema version: inspected, then deliberately not bumped

`schema_version` in this repository tags **structural wire shape**. The precedent
that settles it is `core/content_acquisition.py`, where
`SourceReceipt.__post_init__` *refuses to construct* when `schema_version` does
not match. Nothing validates or branches on `behavioral_matrix_live_4_v1`: every
consumer (`core/candidate_verification.py`, `core/candidate_revision.py`) reads the
block with `.get()`.

This phase removes no field and changes no field's type. It adds one entry to a
list that was always variable-length, plus one additive key. So the version stays,
and a stored LIVE.4 receipt keeps saying exactly what it said: four cases, no skew
case, no claim that LIVE.5 ran.

Phase visibility is carried by data instead, inside the one canonical
`behavioral_matrix` structure:

```json
"discrimination_phase_ids": ["DEFECT.PROBE.LIVE.4", "DEFECT.PROBE.LIVE.5"],
"case_count": 5
```

`PHASE_ID` still names the phase that owns the structure. No duplicate telemetry
subtree, no second LIVE.5-specific receipt. ANSWER.GROUND.LIVE.4 leaves all of it
byte/value-identical — the new keys live in `_CANDIDATE_DEFECT_PROBE_KEYS`, which
is disjoint from `_ANSWER_SURFACE_KEYS`.

## 10. Containment, proved rather than claimed

`core/behavioral_matrix.py` is pinned by
`tests/fixtures/patch_author_live1_frozen_boundaries.json`. This phase is
authorised to change it, so the re-pin is a **proof**:
`defect_probe_live5_frozen_boundaries.json` ships nine reversal hunks built with
`difflib.SequenceMatcher(...).get_grouped_opcodes(3)`. A test applies them to the
shipped file, asserts each `post` is unique, and asserts the reconstructed file's
sha256 equals `e054ce75…` — the exact digest PATCH.AUTHOR.LIVE.1 pinned before this
phase existed, which that fixture now also records as
`behavioral_matrix_pre_live5_sha256`.

From that reconstruction: 18 → 21 top-level definitions, 3 added, 0 removed,
3 changed, each named above.

## 11. Authority

Unchanged. No matrix status sets `human_review_eligible`, `approval_ready`,
`execution_authorized` or `write_authority`. The product smoke drives the real
`maybe_run_auto_patch` branch with `AUTO_PATCH_ENABLED=False` and ends with the
unit-inferring control `verified` **and** `execution_authorized=false`,
`auto_apply_allowed=false`, `write_authority=false`,
`final_repository_changed=false`, with `core/code_dna.py` byte-identical on disk.

Passing all five cases authorizes nothing by itself. Existing verification and
execution policy remain authoritative.

## 12. Known limitations

1. **One subject, one more shape of it.** `indentation_style` is still the only
   production subject with a matrix, so this discrimination generalizes to no
   other defect family yet. A subject without an adapter keeps
   DEFECT.PROBE.LIVE.3's paired semantics exactly.
2. **The skew case is one-directional by construction.** A fact claiming the
   larger width (`4-space` misclassified as `2-space`) gets four cases rather than
   five, because `[4, 8, 8]` admits both vocabulary units. Deciding it would
   require something outside the bounded source. Widening the classification
   vocabulary is what would change this.
3. **The revision schema bug is still open.** Round 9 also established that the
   revision prompt does not include the normal patch candidate output contract, so
   Candidate₁ came back in a malformed envelope. This phase reconstructs the
   candidate's *substance* to measure it and leaves the envelope alone. Next
   planned phase: **PATCH.AUTHOR.LIVE.2 — Self-Contained Authoring Contract
   Parity.** The two issues are kept separate deliberately, and a test asserts
   `core/candidate_revision.py` is byte-identical.

## 13. Not done here

No web search, documentation search, RAG expansion, model call, external API or
network. No fuzzing or property testing. No randomized or generated case. No
repository traversal. No change to `safe_minimal`'s builtin/member policy, local
novelty caps or identifier classification — `lstrip` is still not allowed, and the
known unit-inferring local-only candidate remains sufficient to prove the task is
expressible. No change to targeted validation's 3-file cap, 8-node/check cap,
selector, commands or timeout/budget. No second candidate sandbox.
`_classify_indent` is not fixed.
