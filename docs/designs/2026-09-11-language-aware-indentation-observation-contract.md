# INDENT.SEMANTICS.1 — Language-Aware Indentation Observation Contract

- **Phase:** `INDENT.SEMANTICS.1` (ID namespace `INDENT`, inside the existing OPS track)
- **Date:** 2026-09-11
- **Kind:** oracle / semantic contract. **Not** the production T6 fix.
- **Production files changed:** `core/indentation_observation.py` (new), `core/behavioral_matrix.py`, `core/phase_registry.py` (one namespace entry)

## 1. The measured problem

The `indentation_style` subject is the **block** indentation unit a file is
written in. Every oracle before this phase observed something else: every
physical line that starts with a space or a tab. For Python that set mixes five
different things, and only the first is the subject:

| physical leading whitespace | block evidence? |
|---|---|
| suite indentation (`INDENT`) | yes |
| continuation alignment inside brackets | no |
| multi-line string interior | no |
| comment-only rows | no |
| whitespace-only rows | no |

Measured:

```python
def f(a,
      b):
    pass
```

| reading | observation | unit | value |
|---|---|---|---|
| raw physical widths | 6, 4 | 2 | `2space` |
| tokenize structural steps | 4 | 4 | `4space` |

`core/code_dna.py` itself reads raw unit 2 from docstring interior rows (widths
2, 6, 46), while all 57 of its tokenize `INDENT` steps are 4. The unit inference
was never the fault; the **observation set** was.

## 2. Observation is not assessment

```
source text + declared input language
    -> SourceIndentationObservation   what was seen, by which observer, how strongly
    -> SourceIndentationAssessment    2space | 4space | tab | None, with its basis
```

The two are separate immutable types. The assessment keeps the observation it
read, so a structural `4space` and a heuristic `4space` compare **unequal**:
value, tier and claim strength are three dimensions, never one string.

## 3. The one observation authority — `core/indentation_observation.py`

`SourceIndentationObservation` (frozen, slotted; validates itself):

| field | meaning |
|---|---|
| `language` | normalized declared label (`python`, `go`, … or `unknown`) |
| `observation_tier` | `python_structural` \| `heuristic_physical` |
| `claim_strength` | `structural` \| `heuristic_physical` — fixed by the tier |
| `tokenizer_status` | `completed` \| `failed` \| `not_attempted` |
| `fallback_reason` | `""` \| `language_not_python` \| `language_undeclared` \| `python_tokenize_failed` |
| `structural_space_steps` | one width per pure-space `INDENT` transition |
| `structural_tab_steps` | one tab count per pure-tab transition |
| `structural_mixed_steps` | steps mixing tabs and spaces, or not extending the parent |
| `physical_space_widths` | fallback tier only — leading-space width per space-led row |
| `physical_tab_lines` | fallback tier only — tab-led row count |
| `schema_version` | `indent_semantics_1_observation_v1` |

The constructor refuses every dishonest combination: heuristic evidence with a
structural claim, a structural tier for non-Python input or failed tokenization,
physical fields on the structural tier or structural fields on the fallback
tier, a fallback reason that does not describe the declared language. No field
names a candidate, fingerprint, file or target.

`SourceIndentationAssessment`: `observation`, `value` (`2space`/`4space`/`tab`/`None`),
`basis` (closed: `structural_space_unit`, `structural_tab_unit`,
`structural_mixed_units`, `structural_unit_outside_vocabulary`,
`no_structural_indentation`, and the four `physical_*` counterparts), and
`space_unit`. A basis fixes both the tier it may read and the values it may
produce, so a physical reading cannot be relabelled structural.

## 4. Language belongs to the input

`observe_source_indentation(text, *, language)` has **no path argument**.

| declared language | observer | claim |
|---|---|---|
| `python` | stdlib `tokenize` | `structural` |
| `python`, tokenize fails | physical fallback, `python_tokenize_failed` | `heuristic_physical` |
| any other label | physical fallback, `language_not_python` | `heuristic_physical` |
| missing / `unknown` / not a label | physical fallback, `language_undeclared` | `heuristic_physical` |

The file containing `_classify_indent` is irrelevant: `core/code_dna.py` is
Python, and `_classify_indent` classifies Go, TypeScript and HTML for
`compute_dna`. Tokenizer acceptance is not evidence of Python either — HTML
tokenizes into `INDENT` events mirroring its markup, brace languages into none —
so non-Python input never reaches tokenize (a test spies on it).

## 5. The Python structural observer

- Only `INDENT`/`DEDENT` are evidence. An `INDENT` token carries the **absolute**
  prefix of its level; the step is the suffix the child prefix adds to its
  parent's, from a stack popped on every `DEDENT` — levels `0, 4, 8` are the
  steps `4, 4`; levels `0, 6, 8` are `6, 2`.
- A step of only spaces is a space step, only tabs a tab step; a step mixing
  them, or a child prefix that does not extend its parent, is counted as mixed
  and never normalized into a guessed width.
- Continuation rows, string interiors, comment-only and whitespace-only rows emit
  no `INDENT` and contribute nothing — by tokenizer semantics, not by regex.
- `TokenError`, `IndentationError`, `TabError` and `ValueError` downgrade the
  observation to the physical tier with `python_tokenize_failed`; steps seen
  before the failure are discarded.
- `ast` is deliberately not a dependency: it cannot parse four of the five
  historical fixtures (`level_N` samples), which tokenize reads.

## 6. The physical fallback and claim strength

For non-Python, undeclared and failed-Python input the observer reads
leading-space widths and leading tabs exactly as the generic raw-width
reference always did, and keeps its strict tab majority. It is always
`heuristic_physical`. Claim strength describes how trustworthy the observation
model is; it does not decide whether a fixed compatibility case is required, and
no heuristic reading is ever used to derive a structural expectation.

## 7. The reference assessment

Structural: pure tab steps → `tab`; pure space steps → their common unit, mapped
**exactly** (2 → `2space`, 4 → `4space`, anything else → `None`); tab and space
steps together, or any mixed step → `None`; no step → `None`. Physical: the same
exact mapping over widths, `tab` on a strict tab majority. This is an oracle
primitive, not `_classify_indent`.

## 8. The matrix: eight fixed cases

| # | case id | role | provenance | language | expected | reference |
|---|---|---|---|---|---|---|
| A | `indentation_style.primary.2space` | primary_defect | explicit_user_fact | python | 2space | structural 2space |
| B | `….generalize.2space.deep` | defect_generalization | subject_invariant | python | 2space | structural 2space |
| C | `….preserve.4space` | preservation | behavior_preservation | python | 4space | structural 4space |
| D | `….preserve.4space.deep` | preservation_generalization | subject_invariant | python | 4space | structural 4space |
| E | `….generalize.2space.skew` | defect_generalization | subject_invariant | python | 2space | structural 2space |
| F | `….preserve.4space.continuation` | preservation_generalization | subject_invariant | python | 4space | structural 4space |
| G | `….preserve.4space.multiline_string` | preservation_generalization | subject_invariant | python | 4space | structural 4space |
| H | `….preserve.tab.go` | preservation_generalization | behavior_preservation | go | tab | heuristic tab |

A–E keep ids, bytes, expectations, roles and provenance — pinned by
path-independent contract digests recorded before this phase changed a byte.
F, G and H are fixed constants, appended after every historical case, the same
three for every indentation fact (the mirrored `4space` fact gets seven cases).
The baseline satisfies F, G and H, so each is a real preservation oracle. H is a
compatibility case: its provenance is the nearest existing closed value for
"behavior the baseline already produces", no new role was invented, and its
reference says `heuristic_physical`.

Each case record reports `input_language`, `observation_tier`,
`claim_strength`, `fallback_reason` and `reference_assessment` — scalars only,
never the fixture text, which the case contract already holds.

## 9. Candidate execution and reference observation are independent

```
candidate:  _classify_indent(case.text)                       # unchanged, no kwargs
reference:  assess_indentation_observation(
                observe_source_indentation(case.text, language=case.input_language))
```

The language travels with the case to the reference path and stops there; every
contract's structured input is still `{"args": [text], "kwargs": {}}`.

## 10. The measured candidate battery (real sandbox, eight cases)

| candidate | A–E | F | G | H | matrix | safe_minimal |
|---|---|---|---|---|---|---|
| production baseline | A, B, E reproduced; C, D held | held | held | held | (baseline) | — |
| legacy raw-width control | pass | **regressed** 2space | **regressed** 2space | preserved | fixed_but_regressive | refused (`novel_external_reference`) |
| Round-10 any-evidence | pass | **regressed** 2space | **regressed** 2space | preserved | fixed_but_regressive | **admitted** (`width`) |
| Round-10 branch reorder (Candidate₁) | C, D regressed first | regressed | regressed | preserved | fixed_but_regressive | admitted |
| Python-only reading | pass | preserved | preserved | **regressed** None | fixed_but_regressive | refused (`novel_import`) |
| structural control (test-only) | pass | preserved | preserved | preserved | **fixed_and_preserved** | refused (`novel_import`) |
| Round 9 (absolute-width voting) | skew still reproduced | regressed | preserved | preserved | fixed_but_regressive | — |

Red-green: the any-evidence candidate is `fixed_and_preserved` on the five
historical cases and `fixed_but_regressive` on eight, with every historical
verdict identical between the two runs. The Python-only reading closes seven
cases and regresses H.

## 11. Is T6 implementable under the existing signature?

**Not shown.** The only body known to close all eight cases tokenizes *every*
input as Python — the guess this contract forbids, which reads a plain-text
outline's parenthesis as a bracket — and safe_minimal refuses it as a novel
import; the novelty budget (3 new local bindings) leaves no room for
hand-rolled bracket and string tracking. The oracle can represent the semantics;
the current candidate search space cannot express them, and this phase widens
nothing. Whether the production fix needs caller language transport, a
signature change, a wrapper or a per-language adapter is future design.

## 12. Deltas

- **Candidate verification:** none. `_matrix_verdict` already names the first
  regressed case in matrix order: F for the any-evidence candidate, C for the
  reorder. The structural control is `supporting`.
- **Revision evidence:** the existing receipt reader carries the new cases by
  id, role, provenance, expected, observed and status — and none of the new
  metadata. Round 10 replayed under eight cases differs from the recorded
  revision request by exactly three appended preserved-case lines (6,347 →
  6,897 chars); removing them rebuilds the recorded bytes. Prompt templates are
  unchanged and no fixture text reaches the author.
- **Answer coherence:** candidate identities, generation, presentation and the
  harness verdict of the Round-10 replay are Round 10's own under eight cases.
- **Answer grounding:** the new per-case fields sit inside the existing matrix
  keys and are value-identical after `ground_state_answer`.
- **Authority:** none. Passing all eight cases is verification evidence;
  execution, write, approval and review eligibility are untouched.
- **safe_minimal, targeted validation, CONTROL, retrieval, revision budget:** frozen
  code. The self-repo T6 *ordering* moved because the corpus grew (§16); the
  target stays inside the cap and the oracle stays out of it.
- **`_classify_indent`, `compute_dna`:** byte-identical; the T6 defect is still present.

## 13. Schema version: bumped, with the precedent stated

`schema_version` tags structural wire shape here. DEFECT.PROBE.LIVE.5 kept
`behavioral_matrix_live_4_v1` because it only appended a list entry; this phase
gives **every case record** five fields it never had, which is the situation
`core/evidence_verification.py` answered with `_v2`. So the receipt is now
`behavioral_matrix_live_4_v2`. Nothing is renamed or removed and every consumer
reads with `.get()`; a stored `_v1` receipt keeps saying what it said.

## 14. Phase visibility

`behavioral_matrix.discrimination_phase_ids` is now
`["DEFECT.PROBE.LIVE.4", "DEFECT.PROBE.LIVE.5", "INDENT.SEMANTICS.1"]`;
`phase_id` still names the structure's owner; there is no second subtree.

## 15. Suites that need a verified candidate declare their oracle

Under eight cases no candidate the frozen gate admits is known to close the
matrix. Suites whose subject is the lifecycle *after* verification — revision
recovery, coherence of a verified revision, PATCH.MINIMAL.LIVE.2's admitted
positive control, the public runner's verified path — declare the five-case
LIVE.5 oracle through one test-only helper, `tests/_matrix_history.py`. The
product always runs every case. Direct measurements of an earlier phase's
discrimination (LIVE.4's and LIVE.5's controls, Round 9) are pinned to the case
set they were measured on; receipt-shape facts are updated in place, as LIVE.5
updated LIVE.4. CANDIDATE.VERIFY's "verification opens" moved to the structural
control, and the raw-width candidate's new verdict is recorded beside it.

**Black-box compatibility.** Unmodified, `tests/test_harness_blackbox_revision.py`
went from 8/8 to 3/8 under eight cases: all five failures are the scenarios whose
`CORRECT` (a raw-width unit inference) must be verified. Those five now declare
the five-case oracle — an explicit, documented exception to the suite's
"only provider responses are substituted" rule — and a ninth scenario runs the
same `CORRECT` against the product's eight cases at the public boundary and
records `fixed_but_regressive` on F and G.

## 16. Retrieval on the self-repo: the oracle must not compete with T6

This repository is also the T6 task's corpus. CONTROL orders entry candidates
by repository specificity times the share of an identifier the prompt explains,
then by exact overlap. RETRIEVE.LIVE.4's real-population test (43/43 on the
fully reverted tree) caught the problem. The module's first names were
`IndentationObservation`, `IndentationAssessment` and `observe_indentation`.
As two-token exact `indentation` identifiers they explained as much of
themselves as `_classify_indent` does through its morphology bridge, and won
on exact overlap:

| population (20,952 eligible nodes) | `_classify_indent` rank | oracle in top ten |
|---|---|---|
| module with two-token names | **7**, outside the six-entry cap | ranks 4–6 |
| module removed | 4 | — |
| module with three-token names (shipped) | 4 | none |

So the three names gained a word — `SourceIndentationObservation`,
`SourceIndentationAssessment`, `observe_source_indentation` — and a fast test
uses the production matcher to pin that every matching name in the module
explains a smaller share of itself than the target does. The phase still adds
seven exact `indentation` symbols (df 11 → 18), so the prompt's incidental
`point` is now the rarer word. RETRIEVE.LIVE.4's `ROUND5_TOP_SIX` snapshot was
updated for that, the same kind of move its own history records; the target
rank moved from 2 to 4, inside the cap. No retrieval or CONTROL code changed.

## 17. Frozen boundaries and containment

`tests/fixtures/indent_semantics1_reversal.json` rebuilds both edited
production files byte for byte (17 hunks for the matrix, 1 for the registry)
and sits first in `LATER_RECEIPTS`, so every earlier pin is evaluated against
history and nothing is re-pinned. Its matrix preimage is DEFECT.PROBE.LIVE.5's
post-image. `tests/fixtures/indent_semantics1_frozen_boundaries.json` pins 40
boundary files plus the `_classify_indent` and `compute_dna` definition digests.

## 18. Performance

Measured on this machine (best of 7, CPU otherwise idle):

| operation | cost |
|---|---|
| observe + assess one matrix fixture, Python structural | 12.7–18.1 µs |
| observe + assess one matrix fixture, physical fallback | 4.5–6.1 µs |
| observe `core/code_dna.py` (12,304 chars), structural | 1.03 ms |
| assess that observation | 1.4 µs |
| observe `core/code_dna.py`, physical | 0.07 ms |
| scaling at 1× / 4× / 16× input | 83 / 94 / 90 ns per char — O(text) |
| build the matrix: 5 cases (pre-phase) → 8 cases | 0.17 ms → 0.47 ms |
| one full matrix run, same candidate: 5 cases → 8 cases | 6.30 s → 9.86 s (+3.56 s, ×1.56) |

The observation is noise. The whole added cost is three more baseline probes and
three more candidate probes — about 1.2 s per case, each a subprocess in the one
existing sandbox. No second sandbox, no second patch application.

## 19. Known limitations

- Only Python has structural semantics. Every other language keeps the weaker
  physical reading; no parser for Go, JS, TS, Rust or C++ was built.
- The physical fallback still reads continuation and string rows as indentation
  for non-Python input.
- A form feed in a Python indentation prefix is counted as a mixed step
  (conservative `None`), not normalized.
- The reference is recorded as evidence; it does not gate matrix construction.
  A fact whose width lies outside the vocabulary (e.g. `3space`) keeps its
  historical cases with a reference that reads `None`.
- `discrimination_phase_ids` names what the production builder carries; a
  test that passes an explicit case subset still sees the full list.
- No candidate admissible under the frozen safe_minimal gate is known to close
  the eight-case matrix, so T6-shaped tasks cannot currently reach `verified`.
- The self-repo T6 localization is sensitive to vocabulary. Any new short
  identifier anywhere in this repository that carries the exact token
  `indentation` competes with `_classify_indent` for the Round-5 prompt. The
  real constraint is that harness modules and product code share one
  localization corpus. Only a CONTROL decision could lift that; this phase
  kept its own names out of the way and did not touch CONTROL.
- Exactness cuts both ways. A scratch corroboration over the 876 tracked `.py`
  files (not part of the phase; the product traverses nothing) read 866 as
  structural `4space` and 10 as `None`. Nine have no block at all, and in
  `core/router.py` one real 3-space step (line 218) among 66 four-space steps
  makes the common unit 1. The raw physical reading called 72 of those files
  `2space`. Exact mapping is right for an oracle; a production classifier will
  likely need a robust unit estimate over structural steps.

## 20. Recommended next production phase

Transport the input language into production classification — `compute_dna`
already knows each file's suffix — through a language-aware classifier that
routes Python to this structural observer and everything else to the generic
reading, with `_classify_indent`'s contract decided explicitly (kept as the
generic heuristic, or given a language) rather than guessed. Re-measure the
eight-case matrix, the real-corpus preservation battery and the Round-10
candidates against it, and decide separately whether safe_minimal's novelty
budget should ever admit a stdlib import for such a fix.
