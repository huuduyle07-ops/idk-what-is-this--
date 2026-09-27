# DEFECT.FACT.LIVE.1 — Typed Behavioral Expectation Handoff

**Date:** 2026-09-08
**Track:** OPS (`DEFECT.*` ID namespace)
**Prerequisite:** CONTROL.LOCALIZE.LIVE.2
**Semantic owner:** INPUT / SemanticInterpretation — *not* CONTROL, *not* the probe

---

## 1. The failure this repairs

The live T6 run localized correctly and then could not probe.

```
parser                  OK
repository population   OK
identifier recall       OK
entry specificity       OK
_classify_indent        rank 2 / cap 6
CONTROL localization    core/code_dna.py::_classify_indent   ← correct
localization handoff    correct
probe target binding    correct
bounded probe           unavailable
```

The reconstructed reason was:

> `no deterministic typed adapter exists for the preserved task facts`

CONTROL had the right target. What it did not have was a *behavior fact*. The
live path did roughly this:

```python
derive_indentation_probe_from_preserved_task(
    raw_task=control_result["query"],   # the raw prompt
    target=localized_target,            # correct
)
```

and that adapter re-read the prompt with one literal sentence regex:

```
"<N>-space indentation is classified as <M>-space"
```

The user's actual words were semantically identical and structurally different:

> "a repository that uses 2-space indentation, the patches it writes come back
> using 4-space indentation instead"

No match. `None`. No contract. No probe.

The behavior fact was in the order the entire time. Nothing had ever typed it,
so the last component in the chain was left re-deriving meaning from prose —
and re-deriving it with a template that only accepted one sentence.

## 2. The architectural rule

> **CONTROL may CARRY behavioral facts. CONTROL must NOT INVENT behavioral facts.**

Semantic ownership now reads:

```
user input
    ↓
deterministic semantic intake        core/behavioral_expectation.py  ← extraction, once
    ↓
typed explicit behavior fact         BehavioralExpectation
    ↓
preservation                         ExplicitEvidence → SemanticInterpretation → TaskContract
    ↓                                → LiveTaskShape → LiveRouteReceipt
CONTROL carries it with the localized target
    ↓
probe request builder consumes it    build_probe_contract_from_behavior_fact
```

rather than:

```
CONTROL/probe → re-parse raw prose → derive expectation again
```

Every consumer downstream of intake reads a record. None of them reads the
user's sentence.

## 3. The typed fact

`core.behavioral_expectation.BehavioralExpectation`, frozen and slotted:

| field | meaning |
|---|---|
| `subject_kind` | what the claim is about — `indentation_style` |
| `expected_value` | what the user said the behavior **should** be |
| `observed_value` | what the user said it does **instead** |
| `relation` | how the user phrased the mismatch |
| `provenance` | `explicit_user_fact` — the only permitted value |
| `source_text` / `source_start` / `source_end` | the literal span both values were read from |
| `obligation_ordinal` | which preserved INPUT.PRESERVE.LIVE.1 obligation carries the span |
| `authoritative` | false when another explicit claim contradicts this one |

For the exact T6 order:

```
subject_kind   = indentation_style
expected_value = 2space
observed_value = 4space
relation       = instead_of
provenance     = explicit_user_fact
obligation_ordinal = 0
```

### Direction is pinned

```
repository uses 2-space indentation          → expected = 2space
patches come back using 4-space instead      → observed = 4space
```

Never the other way round. The record forbids `expected == observed`, and the
preservation gate compares the pair *ordered*, so an interpreter that swaps them
fails the gate rather than quietly inverting the claim. That inversion had
already happened once in live root-cause prose; it is now unrepresentable in the
typed transport.

## 4. Extraction: a grammar, not a template

The old adapter welded three concerns into one sentence pattern: which values
are legal, which sentence shape the user must write, and which value means what.
They are factored apart:

**One value scanner per subject kind.** Bounded and normalizing. Indentation
widths are a single digit 1–8 followed by `space`/`spaces`, optionally carrying
the subject noun. `12-space` matches nothing rather than yielding `2-space` out
of the middle of it. Word numbers ("two-space") are *not* supported, because no
existing deterministic numeric primitive backs them.

**One pairing rule.** Adjacent values, in the order written, within a bounded
gap, never straddling a sentence the user ended or a line they broke, and only
when the subject is named inside the pair or in the short bounded run of words
leading into it. A value itself may not straddle a line break either.

**One closed table of relation connectives**, applied in a fixed order:

| rule | cue | direction | relation |
|---|---|---|---|
| 1 | `instead of` / `rather than` in the gap | second value is expected | `instead_of` |
| 2 | trailing `instead` after the second value | first value is expected | `instead_of` |
| 3 | `from X to Y` (gap is only `to`, `from` leads) | first value is expected | `changes_from_to` |
| 4 | a result connective in the gap | first value is expected | `expected_vs_observed` |
| — | nothing matched | **no fact** | — |

Rule 1 before rule 2 matters: `returns Y instead of X` names the expectation
second, and reading it the other way round would build a probe that asserts the
defect.

**Why this is not regex-zoo growth.** The three pieces are orthogonal and each
is capped. A new wording costs one entry in a connective table bounded by a
five-label relation vocabulary (`equals`, `instead_of`, `changes_from_to`,
`differs_from`, `expected_vs_observed`). A new subject kind costs one value
scanner. Neither is a new sentence template, and neither can grow the number of
*meanings* the module produces. The old adapter had one template accepting one
sentence; adding T6's wording to it would have made two templates accepting two
sentences, which is the shape this phase exists to avoid. The old regex was
**not** widened — verified byte-for-byte against the pre-change baseline.

### The negatives

Silence is the correct answer for prose the grammar cannot read.

* `Explain how indentation works in this repository` → no fact, no probe.
* `2-space indentation, 4-space indentation, tabs.` → no connective, no fact.
* `The padding should be 2 spaces but becomes 4 spaces.` → no subject noun, no fact.
* `Indentation matters here. The timeout went from 2 spaces to 4 spaces.` →
  subject named too far away, no fact.
* `Indentation of 12-space became 24-space` → no legal value, no fact.
* Two incompatible claims for one subject → **all** preserved, **all** marked
  non-authoritative, `behavior_fact_ambiguous`, **no probe**. Nothing here picks
  between them. Contradictions are marked across the whole order *before* the
  bound is applied, so truncation cannot hide a conflict.

## 5. Preservation

INPUT.PRESERVE.LIVE.1 made explicit commitments survive transport. The same
invariant now runs one level down:

* the preservation gate tracks a new item kind, `behavioral_expectation`, and
  fails closed when a fact is dropped, rewritten or inverted;
* the provenance check fails an interpretation that reports a fact the user never
  stated — this is the rule that stops a model-proposed or source-derived value
  becoming a probe expectation;
* `supported_behavior_facts` drops any fact whose quoted span no longer appears
  in the preserved obligation set, so typed extraction and preserved text cannot
  silently diverge;
* `bind_obligation_ordinals` records *which* preserved obligation carries the
  span, so the link is a value on the record rather than a claim in a comment.

Serialization is transport, not re-interpretation: `restore_behavioral_expectations`
round-trips the record exactly and returns nothing at all for a payload that is
not a complete, valid fact. No field degrades to a preview string.

## 6. CONTROL carry

`attach_preflight_validation` records, additively:

```
control_result["behavior_facts"]           # exactly what the route carried
control_result["behavior_fact_transport"]  # typed_preserved_contract | legacy_untyped_transport
control_result["defect_probe_telemetry"]   # read-only diagnostics for one pass
```

WHERE and WHAT stay separate fields:

```
localized_target       core/code_dna.py::_classify_indent
behavioral_expectation expected=2space, observed=4space
```

There is deliberately no code path in CONTROL or the probe that writes an
`expected_value`, an `observed_value` or a `relation`. CONTROL may refuse a fact
it cannot use; it may not author one.

## 7. Probe contract construction

```python
build_probe_contract_from_behavior_fact(
    target=localized_target,      # WHERE
    behavior_fact=typed_fact,     # WHAT BEHAVIOR
)
```

For a supported fact: `invocation_kind = python_pure_function`,
`expected = fact.expected_value`, `expected_relation = equals`, and a bounded
nested fixture built at the user's **expected** width. Existing probe contract
semantics and the existing provenance bases
(`deterministic_task_fact_adapter` and siblings) are reused unchanged.

The claim is never checked against itself: `observed_value` reaches the
provenance reference and nothing else.

### The legacy adapter

`derive_indentation_probe_from_preserved_task` remains, with its body, its
signature and its regex byte-identical — only its docstring changed, to say what
it now is. It is reached **only** for transport that predates typed facts: a
CONTROL result whose route carries no `behavioral_expectations` field at all.
Live production reaches the typed builder, and a run that carries typed
transport never falls back to prose even when it carries no fact.

Old receipts stay readable and are reported as what they are. A legacy run's
`behavior_fact_status` is `behavior_fact_legacy_raw_adapter` — not `available`
and not `behavior_fact_unavailable` — because a run with no typed transport has
no typed fact to call present or missing. Its source is
`legacy_raw_prose_adapter` and, when the old regex does not recognise the text,
its reason is `legacy_raw_prose_adapter_unavailable`. None of it is
reinterpreted as though typed facts had existed and been found wanting.

## 8. Telemetry

The diagnostic found an observability gap: `attach_defect_probe_receipt` wrote
into `control_result` and the live payload never showed it, so every black-box
round had to reconstruct why a probe was unavailable.

`defect_probe_telemetry` is now surfaced on the live payload through the same
additive seam as `localization_handoff`. It is a **copy** of what CONTROL
already recorded: no probe is executed, no contract is rebuilt and no repository
byte is read at display time.

Truthfulness is structural rather than remembered:

* `expected` / `claimed_observed` come from the **user's** typed fact, and are
  `null` when there is none;
* `probe_expected` / `probe_observed` come from the **receipt**, and are `null`
  when nothing ran;
* a probe that never executed reports `probe_result = not_run` rather than
  borrowing the `inconclusive` verdict that belongs to a probe that did;
* when a contract could not be built, `contract_status = unavailable` and
  `unavailable_reason` names which fact was missing — no expected or probe value
  is invented to fill the gap;
* there is no confidence, no score, no source dump and no authority field.

## 9. What did not change

| frozen | status |
|---|---|
| RETRIEVE.LIVE.1/.2/.3/.4 | untouched — T6 rank still 2 / cap 6 |
| CONTROL.LOCALIZE.LIVE.2 ranking | untouched — same target, same score 22.02 |
| `localization_handoff` receipt | same four keys, byte-compatible |
| DEFECT.PROBE.LIVE.1/.2 execution | AST-pinned identical (see below) |
| PATCH.BASIS.LIVE.1 | untouched |
| OPS.VALIDATE.1/.2/.3 | untouched |
| ANSWER.GROUND.LIVE.1/.2/.3 | untouched |
| `safe_minimal` / candidate minimality | untouched |
| validator / validation execution | untouched |
| EXEC.AUTH / POLICY / APPROVAL | untouched — every authority flag still false |
| `core/code_dna.py::_classify_indent` | **not fixed** — still the live defect |
| model calls / network / traversal / index | zero delta |

CONTROL.LOCALIZE.LIVE.2 pinned `core/defect_probe.py` by whole-file digest. This
phase is authorised to change contract *construction* in that file, so that
digest was re-pinned — and the invariant it carried moved to
`tests/fixtures/defect_fact_live1_frozen_probe_execution.json`, at function
granularity, where it says the thing that actually matters: **nothing that runs
a probe changed.** Thirteen execution functions and classes are pinned by AST
digest taken from the pre-change baseline and verified identical, plus the
legacy adapter's body, signature and literal pattern.

## 10. Result

The exact T6 wording, through the real CONTROL fixture path:

```
RETRIEVE          _classify_indent rank 2 / cap 6
CONTROL target    core/code_dna.py::_classify_indent
behavior fact     expected=2space  observed=4space  instead_of  explicit_user_fact
transport         typed_preserved_contract
contract          built
invocation        python_pure_function
probe result      reproduced
probe observed    4space
probe expected    2space
```

and the short canonical phrase `2-space indentation is classified as 4-space`
produces the same typed claim — different `relation`, identical
`subject_kind` / `expected_value` / `observed_value`. That equivalence at intake
is the proof that the probe no longer depends on which sentence the user wrote.

`patch_basis` becomes `grounded_defect` through PATCH.BASIS.LIVE.1's existing,
unchanged rule for a `bounded_defect_reproduction`. That is the pre-existing
consequence of a probe that reproduces, not a new grant: `write_authority`,
`patch_application_authority`, `patch_eligibility_granted` and
`auto_patch_candidate_allowed` all remain false.

## 11. Known limitations

* One subject kind. `indentation_style` is the only value vocabulary that
  normalizes deterministically today; a typed fact of another kind would be
  preserved and reported, and would truthfully have no bounded fixture.
* No word numbers. "two-space" yields nothing, because no existing deterministic
  numeric primitive supports it and inventing one is out of scope.
* One fact per probe. Multiple compatible claims are preserved and the earliest
  is selected; multiple incompatible claims fail closed.
* Root-cause *prose* is generated downstream by a model. The typed fields are
  pinned and cannot invert, but this phase does not rewrite root-cause
  generation, so a model can still describe the direction wrongly in free text.
* Candidate minimality is untouched, so the next observed bottleneck is
  downstream of here.
