# INPUT.PRESERVE.LIVE.1 — Lossless Long-Obligation Transport

**Track:** INPUT · **Status:** complete · **Date:** 2026-09-06
**Prerequisites (frozen):** INPUT.1, INPUT.2, INPUT.3, WAITER.LIVE.1, ANALYSIS.EVIDENCE.LIVE.1

---

## 1. The defect

A live T5 black-box run exposed a violation of the already-frozen INPUT.1
preservation contract. The user request named six explicit comparison
dimensions:

```
Compare this repository (deepseek-harness, the DeepSeek AI agent harness)
against C.A.T.T.U.S, the Python agent harness located at ../C.A.T.T.U.S.
Focus on: (1) how each one structures its agent loop and extension model,
(2) how each handles tool/plugin registration and lifecycle, (3) how each
handles repository context and retrieval for coding tasks. Then recommend
the three highest-value architectural ideas C.A.T.T.U.S should adopt from
deepseek-harness, with concrete justification grounded in files you actually
read.
```

WAITER.LIVE.1 split it correctly at the sequencing the user wrote (`Then`),
producing two clauses of 352 and 165 characters. It then capped each clause at
240 characters. What reached downstream was:

```
... Focus on: (1) how each one structures its agent loop and extension
model, (2) how each handle
```

`tool`, `plugin`, `lifecycle`, `context` and `retrieval` — five explicit
commitments — never arrived. ANALYSIS.EVIDENCE.LIVE.1 was using the obligations
it received exactly as designed; the obligations it received were incomplete.

The cut landed **mid-word**. That is the signature of blind character slicing
being used as semantic storage, and it has a second consequence nobody had
measured: the fragment `handle` — a word the user never typed — entered
`subject_tokens` and travelled into path matching as though it were a
user-supplied term. The old transport did not merely lose commitments; it
**invented** one.

## 2. The exact truncation point

```
raw user input (525 chars)
  └─ derive_live_task_shape()                        core/live_task_shape.py
       ├─ understand_request() → TaskContract        core/input_understanding.py
       │    ├─ extract_explicit_evidence()           MAX_SCAN_CHARS = 100_000  ✅ lossless
       │    ├─ LiveTaskFieldsInterpreter.interpret()
       │    │    └─ classify_live_shape()
       │    │         └─ split_obligations()
       │    │              └─ clause[:MAX_OBLIGATION_CHARS]   ★ 240  ← THE BUG
       │    └─ check_requirement_preservation()      ← never saw obligations at all
       └─ LiveTaskShape(obligations=<truncated>)
  └─ route_live_task() → LiveRouteReceipt.obligations
  └─ state.live_route["obligations"]
       ├─ core/pipeline.py:197 → collect_analysis_evidence(obligations=…)
       ├─ core/pipeline.py:225 → build_analysis_answer_prompt(obligations=…)
       └─ core/control_engine.py:2292
```

`core/live_task_shape.py:353`, `MAX_OBLIGATION_CHARS = 240`. One line.

### Why it violated INPUT.1

INPUT.1's contract states that a value marked `explicit` was literally supplied
by the user, and that the request is preserved rather than summarised. The
obligations tuple was presented as preserved user commitments — `core/pipeline.py`
literally comments *"the preserved obligations decide the evidence profile"* —
while being a character-truncated prefix.

Worse, it produced the permanent regression §8 of the phase brief forbids:

- the Preservation Gate compares `ExplicitEvidence` against
  `SemanticInterpretation`, neither of which carries obligations;
- so the gate reported `passed`;
- while downstream received a clause missing five explicit dimensions.

**Gate says preserved, downstream receives fewer.**

## 3. The fix

`core/obligation_preservation.py` — INPUT.PRESERVE.LIVE.1 — becomes the single
authoritative producer of obligations.

### 3.1 Bounded, not unbounded

Lossless does not mean unbounded. The bound moves from *characters of a
commitment* to *whole spans the user wrote*:

| Bound | Value | What it bounds |
|---|---|---|
| `MAX_ACCEPTED_TASK_CHARS` | `100_000` (= INPUT.1's `MAX_SCAN_CHARS`) | request size at intake |
| `MAX_OBLIGATION_CLAUSES` | 32 | user-written ordered clauses |
| `MAX_OBLIGATION_UNITS` | 32 | authoritative units |
| `MAX_OBLIGATION_UNIT_CHARS` | 480 | one unit — a clause past it is **sub-divided**, never cut |
| `MAX_TOTAL_OBLIGATION_CHARS` | 6_000 | the whole set's prompt-payload budget |
| `OBLIGATION_PREVIEW_CHARS` | 240 | **display only** |

The accepted-input bound is *reused* from the frozen extractor rather than
re-declared, so intake and extraction cannot disagree about what "too large"
means. Every bound that can still bite reports an explicit `overflow_status`;
none of them shortens a span quietly.

### 3.2 Sub-division at boundaries the user wrote

A clause longer than one unit is divided, in a fixed precedence, at boundaries
that appear literally in the request — enumerations (`(1)`, `2.`), sentence
ends, then comma-plus-conjunction. Only an unbroken wall of prose reaches the
word-boundary wrap, and even that never splits inside a word. Nothing is
reworded, reordered, summarised or dropped.

### 3.3 Storage is not display

- `ObligationSet.values` — authoritative, never abbreviated, what downstream reads.
- `ObligationSet.preview` — 240 characters with an ellipsis, for a UI field or
  a log line.

The old 240 survives, in the one place a cap is honest.

### 3.4 One set, not two

The structural core of the fix. `classify_live_shape` derives the
`ObligationSet` **once**; `LiveTaskShape.obligations`, `LiveRouteReceipt.obligations`
and the preservation verdict all read that same object. `LiveTaskShape.__post_init__`
raises if the tuple it carries differs from the set the gate inspected, and
raises again if preservation is reported as passed while the set reports
`authoritative_truncated`.

"Gate passed, downstream received fewer" is not a bug that has to be tested
for. It is unrepresentable.

`derive_live_task_shape` folds the set into the fail-closed verdict INPUT.1
already had: an order whose obligations did not all reach the contract is
exactly as unroutable as one whose subjects did not.

### 3.5 Routing reads clauses, not units

Mixed-obligation detection reads the set's **clauses** — the user's own
sequencing — never its units. A long clause that INPUT.PRESERVE sub-divides for
transport is still one order, so sub-division cannot manufacture a
`needs_clarification` route. Measured across 180 adversarial head×tail×padding
combinations (120 of which the old cap truncated): **zero verdict flips**.

## 4. Measured results

### T5, before and after

| | before | after |
|---|---|---|
| unit 1 | 240 chars, ends `…how each handle` | 352 chars, complete |
| unit 2 | 165 chars | 165 chars (unchanged) |
| `tool` `plugin` `lifecycle` `context` `retrieval` | absent | present |
| `subject_tokens` | contains fabricated `handle` | contains real `handles`, `tool` |
| evidence profile | `architecture_implementation` | `architecture_implementation` |
| route | `analysis_only / analysis_answer` | unchanged |

### Across the fixture matrix

- Explicit commitments lost by the old transport: **12**
- Explicit commitments lost by the new transport: **0**
- Route deltas: **0 / 12** cases, **0 / 180** adversarial cases

### Size

| measurement | before | after | delta |
|---|---|---|---|
| serialized Task Contract | 25,008 | 25,008 | **0 %** — the contract never carried obligations |
| T5 model-prompt obligations block | 405 | 517 | **+112 chars** — the recovered commitments themselves |
| serialized route receipt (telemetry) | 26,529 | 30,849 | +16.3 %, all of it the counts-and-flags receipt |

The route receipt is a routing/telemetry record: `render_live_route_json` has no
production caller, and no path serializes it into a model prompt. The only
prompt growth is the obligations block, and it is the user's own words.

The receipt carries counts and flags, never a second copy of the request. At
the route level it also drops `preview`, because `obligations` sits two keys
above it — repeating an abbreviation of a list already printed there would be
this phase's own defect running backwards. The bounds a receipt was produced
under are identified by `schema_version` rather than copied into every record.

Late commitments that previously vanished and now survive:

| fixture | lost before | lost after |
|---|---|---|
| T5 | `tool`, `plugin`, `lifecycle`, `context`, `retrieval` | — |
| late constraint | `do not modify files` | — |
| late output format | `exactly three recommendations` | — |
| late no-write | `do not write` | — |
| late subject/relationship/rubric | `validation pipeline`, `latency`, `memory footprint`, `failure isolation` | — |

## 5. What this phase is not

- **No model call.** The module is stdlib-only; the only project import is a
  bound constant.
- **No network call.**
- **No repository traversal**, no index, no graph.
- **No routing retune.** WAITER's marker vocabulary, precedence and workflow
  table are untouched.
- **No analysis-ranking change.** ANALYSIS.EVIDENCE.LIVE.1's role allocation,
  its 12-token budget and its 12-file / 60,000-character caps are untouched.
  It simply receives what the user wrote.
- **No multi-root support.** Not begun here.
- **No summariser.** A model summary standing in for user commitments is
  exactly the lossy semantics this phase removes.

## 6. Historical artifacts

`ObligationSet.from_historical()` restores an obligation list stored by an
earlier run. Old artifacts hold whatever the 240-character transport left
behind; their completeness cannot be established after the fact, so a restored
set reports `overflow_status = historical_representation_unknown` and
`authoritative_truncated = True`. Old runs stay readable and are never
reinterpreted as having been preserved.

## 7. Known limitations

- **Sub-division is structural, not semantic.** A 480-character clause with no
  enumeration, sentence end or conjunction is wrapped at a word boundary into
  consecutive units. Nothing is lost, but the split point is arbitrary prose
  rather than a commitment boundary. `ObligationUnit.continued` marks it.
- **The 12-token budget downstream is unchanged.** All five recovered T5 terms
  now reach ANALYSIS.EVIDENCE; `tool` wins a token slot and `plugin`,
  `lifecycle`, `context`, `retrieval` do not, because `MAX_SUBJECT_TOKENS` is
  12 and subjects are spent first. Widening it is ANALYSIS.EVIDENCE's decision,
  deliberately not taken here to pass T5.
- **Dedup is exact-match only.** Two clauses differing by a single character
  are two obligations.
- **Multi-root remains refused.** The C.A.T.T.U.S side of the T5 comparison is
  still unavailable, and the answer still says so.
