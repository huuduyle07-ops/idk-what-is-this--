# INPUT.3 — Progressive Intake Completion & Clarification Policy

Date: 2026-08-22
Status: complete
Next: WAITER.1 — Execution Waiter workflow selection

## Decision

INPUT.1 made C.A.T.T.U.S preserve what the user said. INPUT.2 made it
understand what the user meant. Neither could answer the next question:

> Is that understood request complete enough for a future waiter to inspect — and if not, whose
> problem is it?

INPUT.3 answers it, and stops.

```text
User Prompt
    ↓
Explicit Evidence Extractor      [INPUT.1, deterministic, frozen]
    ↓
Semantic Waiter                  [INPUT.2, bounded run: at most 2 calls, frozen]
    ↓
Task Contract + semantic receipt/status
                                 [INPUT.1/2, frozen]
    ↓
Deterministic Completion Policy  [INPUT.3]
    ↓
CompletionDecision
    ↓
Goal Brief projection            [INPUT.3]
    ↓
optional local Intake Assistant  [INPUT.3, presentation only]
    ↓
[future WAITER.1 / mode router]
    ↓
[future Kitchen / execution]
```

The waiter may understand the order and may now say whether it can be taken.
It still may not enter the kitchen.

The governing invariant:

> **Local AI may improve the words. It may not change the decision.**

## Modules

| Module | Responsibility |
| --- | --- |
| `core/intake_completion.py` | `CompletionDecision`, the deterministic policy, contradiction and ambiguity detection |
| `core/goal_brief_projection.py` | `TaskContract` + decision → an editable Goal Brief-shaped view |
| `core/intake_assistant.py` | The assistant protocol, the boundary check, the always-available deterministic implementation |
| `core/local_intake_assistant.py` | Optional local-model assistant, strict parsing, opt-in Ollama transport |
| `core/input_completion.py` | Orchestration and the canonical fingerprint |

No INPUT.1 or INPUT.2 module was modified.

## Completion states

Five, and no more.

| State | Meaning |
| --- | --- |
| `ready` | Intake semantics suffice for a future execution waiter to *inspect* |
| `goal_brief_assist` | Meaning is clear; a broad task is missing operational detail |
| `ask_clarification` | The meaning itself cannot be resolved safely |
| `blocked_contradiction` | The user's own explicit commitments cannot both hold |
| `semantic_system_failure` | The interpreter or its infrastructure failed |

`READY` does **not** mean execute now, Instant Run, Commander, safe to patch,
safe to write, approved, or even necessarily future-handoff-ready. It means
the intake information appears complete. A future execution waiter may inspect
it only when the separate derived handoff predicate is also true.

## Ownership

Every non-READY state names who owns the unresolved problem:

| Owner | Raised by |
| --- | --- |
| `user_meaning_ambiguity` | `ask_clarification` |
| `operational_detail_missing` | `goal_brief_assist` |
| `explicit_constraint_conflict` | `blocked_contradiction` |
| `semantic_system_failure` | `semantic_system_failure` |

The mapping is one-to-one and checked in `__post_init__`, so a decision cannot
be assembled that blames the wrong party.

## The decision schema

```python
CompletionDecision:
    state
    owner                       # None only for READY
    reasons[]                   # bounded reason codes
    ambiguities[]               # ClarificationNeed
    missing_requirements[]      # MissingRequirement (field, reason, severity)
    contradiction_reasons[]
    semantic_status
    preservation_status
    contract_present
    semantic_receipt             # existing INPUT.2 evidence, never model-written

    semantic_evidence_status    # derived: valid, missing, or invalid receipt
    handoff_blockers[]           # derived, bounded reasons
    ready_for_future_handoff    # derived; see formula below
    required_before_handoff     # derived: required-severity fields
    optional_improvements       # derived: suggested-severity fields
```

`ready_for_future_handoff` is a **property**, not a field. There is no way to
set it independently of the policy — not by a local assistant or a serializer
round-trip. It is deliberately not called `routing_allowed`: that name already
belongs to INPUT.1's gate and means something stronger.

It is true only when all four prerequisite facts hold:

```text
state == READY
and contract_present
and preservation_status == passed
and semantic receipt is valid
```

A valid receipt is the existing INPUT.2 `SemanticWaiterReceipt` for exactly
`semantic_interpretation_ok` or `semantic_interpretation_repaired`, agrees with
the decision status, has structured output marked valid, is not a fallback, and
matches INPUT.2's bounded success-receipt shape: a positive first-attempt run
for `ok`, or a positive two-attempt preservation-repair run for `repaired`.
`semantic_interpretation_not_run`, failed/unavailable/invalid statuses,
deterministic fallback, unknown statuses, missing receipts, and receipt/status
mismatches are never handoff evidence. Model confidence has no vote.

Invariants enforced at construction:

- READY carries no owner, no ambiguity, no required field, no contradiction.
- `ask_clarification` needs at least one clarification need.
- `blocked_contradiction` needs at least one contradiction reason.
- `goal_brief_assist` needs at least one field that actually blocks.
- Every non-READY state states at least one reason.

## Precedence

```text
1. semantic / system failure           -> SEMANTIC_SYSTEM_FAILURE
2. explicit conflict in the user's      -> BLOCKED_CONTRADICTION
   own literal commitments              /  ASK_CLARIFICATION
3. preservation failure                 -> SEMANTIC_SYSTEM_FAILURE
4. unresolved meaning ambiguity         -> ASK_CLARIFICATION
5. operational incompleteness           -> GOAL_BRIEF_ASSIST
6. otherwise                            -> READY
```

No LLM confidence threshold participates. "The task sounds hard" is not a
reason for anything.

### Why step 2 sits above step 3

The suggested precedence put preservation above contradiction. One case makes
that order dishonest.

A user who writes *"Give me the result in JSON. Return it in markdown only."*
has stated two incompatible outputs. INPUT.1's contract carries exactly **one**
`requested_output`, so this order cannot survive the preservation gate by
construction. Under strict precedence the answer would be "my semantic
interpreter failed" — blaming the system for the user's words, and leaving the
user with nothing to fix.

So step 2 reaches over step 3, but only through a keyhole: the carve-out
applies **only** when every missing preservation item is of kind
`requested_output`. A preservation failure with any wider footprint — one lost
subject, one dropped rubric value — is a system failure and is reported as one.
`tests/test_intake_completion.py` pins both halves.

### The benign half of the same limit

*"as a table in markdown"* names two shapes that **compose** into one answer.
The gate still reports the second cue as lost, but nothing the user said
actually disappeared. That case continues through the policy carrying the
reason code `output_format_representation_limit`, and `preservation_status`
still reads `failed` so the situation is visible rather than swallowed.

This is a frozen INPUT.1 representation limit, recorded rather than patched
around. It may still classify as `READY` for intake presentation, but because
its preservation status remains `failed`, it is always non-handoff-ready.

## READY criteria and handoff eligibility

A request classifies as READY when all of these hold:

- the semantic status can continue the completion policy (`ok`, `repaired`, or
  no semantic run for a standalone preview);
- the preservation gate passed, or failed only on the frozen composable-output
  representation limit;
- no explicit contradiction is detectable from literal evidence;
- no clarification need exists;
- no *required* operational detail is missing.

That completion state is necessary but not sufficient for future handoff. The
strict derived predicate above additionally requires an actual contract, a
passed preservation gate, and a valid accepted INPUT.2 receipt. Thus a
standalone preview may be READY with `semantic_receipt_missing`, and the
Markdown-table representation limit may be READY with `preservation_failed`;
both remain useful to inspect but are non-handoff-ready.

When a decision is READY, **nothing is asked and nothing is volunteered**.
`optional_improvements` is empty, every absent brief field reads
`not_collected`, and the deterministic assistant produces zero questions. A
complete request is not an invitation to interview the user.

## GOAL_BRIEF_ASSIST criteria

Both conditions must hold:

1. **Operational task type** — `implementation`, `debugging`, or `planning`.
2. **A breadth signal** on the contract's execution requirements — `multi_stage`,
   `repository_inspection_required`, or `local_repository_required`.

Then assistance is offered if either:

- `scope` is unknown (no explicit file path and no explicit `only`-style
  restriction), or
- the interpreter reported `missing_information`.

### Complexity is not incompleteness

This is the regression the gate exists to prevent:

| Request | State |
| --- | --- |
| "Explain what DeepSeek Harness is." | READY |
| "Compare these two pasted functions for readability." | READY |
| "Compare these two functions" *flagged multi-stage* | READY |
| "Fix the typo 'teh' to 'the' in README.md." | READY |
| "Migrate the storage backend to PostgreSQL." | GOAL_BRIEF_ASSIST |
| Same migration, with file, constraint and scope supplied | READY |

A comparative analysis is never broad-operational however hard it is. A
single-file typo fix is operational but carries its own scope.

The soft fields offered while assisting are `constraints`, `validation` and
`stop_conditions`. **`why` and `desired_output` are deliberately excluded** —
they are the two fields that turn structured assistance into the forbidden
interview, and neither changes whether broad work can be planned safely.

INPUT.3 may say *more operational detail would help*. It may not say *route to
Commander*.

## ASK_CLARIFICATION criteria

Clarification needs come from three deterministic sources:

| Kind | Source |
| --- | --- |
| `reported_ambiguity` | The interpreter's own `ambiguities` |
| `dangling_subject_reference` | A relationship over a subject the contract never names |
| `conflicting_output_formats` | Incompatible explicit formats with no exclusivity marker |

Bounded at four, one question per independent need.

### What INPUT.3 deliberately does not do

**It never re-reads the raw prompt.** Deciding whether "it" has a referent is a
*meaning* question, and meaning belongs to the Semantic Waiter — INPUT.2's eval
matrix already requires case F to report exactly that ambiguity. INPUT.3
honours the report instead of second-guessing it.

The honest consequence: with **no** semantic model configured, "Replace it with
the other one." is READY, because INPUT.1's literal extractor genuinely cannot
distinguish it from "Compare these two pasted functions for readability." —
both produce an empty-evidence, zero-subject contract. A pronoun regex would fix
the English case and break the Vietnamese one, which is exactly the
language-specific policy the phase is supposed to avoid.

A model can therefore make intake *more* cautious and never less: it can raise
a question, never skip one.

## SEMANTIC_SYSTEM_FAILURE criteria

Any of:

- `semantic_interpretation_failed`
- `semantic_output_invalid`
- `semantic_model_unavailable`
- `semantic_deterministic_fallback`
- an unrecognised status (fail-closed)
- a semantic run that produced no contract at all
- a preservation failure with a footprint wider than composable output formats

`semantic_deterministic_fallback` counts because INPUT.2 records it as a
*substitution for a model failure*, not as understanding.

The wording is first-person and never accusatory:

> I could not reliably interpret this request because the semantic interpreter
> failed. This is not a problem with how you wrote it.

Tests assert that the words "unclear", "clarify" and "rephrase" never appear in
a system-failure summary, and that the state is never `ask_clarification`.

Recovery — retry, deterministic interpretation, operator checks provider — is
left to the operator. INPUT.3 performs no provider escalation.

## Contradiction detection

Implemented, conservatively.

It reads **only** INPUT.1 explicit evidence. No model participates, and there
is no theorem-proving.

**Rule 1 — opposing polarity over an identical object.** Strip the polarity
marker from an explicit `requirement` and an explicit `prohibition`; if the
residual token tuples are *exactly* equal, they contradict.

```text
"You must modify the tests"      -> (you, modify, the, tests)   requirement
"You must not modify the tests"  -> (you, modify, the, tests)   prohibition
```

**Rule 2 — incompatible explicit output formats pinned by an explicit
restriction.** `{json, yaml, csv}` are serializations that decide what the
answer *is*; `{table, markdown, bullet_list, report, prose, diagram}` are
presentation shapes that compose. Two serializations, or a serialization plus a
presentation shape, conflict — but only block when an explicit `restriction`
whose own text contains the user's own output cue pins one of them. Without
that marker the conflict is preserved as **ambiguity**, not invented as
contradiction.

Known limit: frozen INPUT.1 only extracts marker-bearing constraints, so
*"Modify the tests but do not modify any tests."* is one clause and is not
detected. *"You must modify the tests. You must not modify the tests."* is.

## Goal Brief projection

Seven fields: `what`, `why`, `scope`, `constraints`, `stop_conditions`,
`validation`, `desired_output`.

Each field has a status — `present`, `needed_before_handoff`,
`suggested_for_completion`, `not_collected` — and each *value* carries the
provenance the contract gave it plus its source (`raw_request`,
`explicit_evidence`, `task_contract`).

```text
what:
  value: <the user's prompt, verbatim>   source: raw_request   provenance: explicit
scope:
  values: ["storage/db.py"]              source: explicit_evidence  provenance: explicit
validation:
  values: []                             status: suggested_for_completion
```

`what` is the user's own words rather than a tidy paraphrase. A short summary
would read better and would also be invented text; the friendly version is the
optional assistant's job and stays labelled as assistance.

`why`, `stop_conditions` and `validation` have no source in the contract and
are therefore never filled in — only offered.

`goal_brief_offered` is true only in `goal_brief_assist`. Every serialization
also carries `goal_brief_required: false`. **A Goal Brief is never mandatory.**

## The Intake Assistant boundary

```python
IntakeAssistant.assist(contract, decision, projection) -> IntakeAssistance
```

The decision and the projection are finished **before** the assistant is
called, are passed in read-only, and are the same objects returned in the
outcome. A test asserts object identity.

`IntakeAssistance` carries only: `assistant_name`, `summary`, `questions`,
`field_suggestions`, `generated_by_model`, `status`.

There is **no** state, owner, readiness, severity or resolution field. Turning
`ask_clarification` into `ready` is impossible through the API, not merely
forbidden by instruction.

Four further defences:

1. **Forbidden keys** — a response containing `state`, `owner`, `ready`,
   `ready_for_future_handoff`, `resolved`, `routing_allowed`, `mode`,
   `provider`, `model`, `preservation`, `authority` (and more) fails closed.
2. **Severity is not the model's** — question `optional` flags come from the
   decision, and `optional` in the response is an unsupported key.
3. **Provenance is not the model's** — suggestions are always
   `generated_assistance`; `FieldSuggestion` *cannot be constructed* with
   provenance `explicit`.
4. **`enforce_assistance_boundary`** — refuses an invented question anchor, a
   severity disagreement, a duplicate need, or a suggestion over a field the
   contract already fills.

Every failure — transport, malformed JSON, authority claim, boundary breach —
returns deterministic assistance tagged with which failure it was:
`intake_assistant_unavailable`, `intake_assistance_invalid`,
`intake_assistance_rejected`.

### Suggestion provenance

> User: "Migrate storage."
> Model: "Preserve backward compatibility."

That stays a **suggestion**. It serializes with `canonical: false`, lives on
the assistance record rather than on the projection, and never enters the Task
Contract.

## Zero-model equivalence

The required regression test. For each decision state, the same contract is run
twice — deterministic-only, and with a scripted local assistant that rewrites
every question — and `canonical_intake_fingerprint` must match exactly:

```text
state · owner · ready_for_future_handoff · reasons · ambiguities
missing_requirements · required_before_handoff · optional_improvements
contradiction_reasons · semantic_status · semantic_evidence_status
preservation_status · contract_present · handoff_blockers
goal_brief_offered · goal_brief canonical values · authority
```

Only wording may differ. Separate tests confirm the wording *does* differ, so
the equivalence is not passing because the assistant did nothing.

Without a model:

```text
ASK_CLARIFICATION
  - Clarify: 'it' has no resolvable referent in the supplied context
```

With one:

```text
ASK_CLARIFICATION
  - When you say 'it', which component do you mean?
```

Same state. Same owner. Same needs. Better sentence.

## The local assistant is local, small, and single

One configured model, `INTAKE_ASSISTANT_MODEL`, default `qwen3.5:4b`, over the
existing Ollama transport.

**No cloud path exists in INPUT.3 at all.** No Gemini client, no credential
read, no provider ranking, no difficulty-based escalation, no local-to-cloud
failover, no retry against a different model. A test asserts the module source
contains no cloud provider token and that the builder has no `provider`
parameter. If the local model is unavailable, deterministic wording is used —
nothing is retried somewhere more expensive.

### The prompt is deliberately tiny

It carries the completion state, the owner, the open needs with their ids, a
compact task summary capped at 600 characters, the explicit constraints, and
the contradiction reasons.

It carries **no** repository map, source file, project index, graph, benchmark
report, lesson, Dream artifact, or run history.

Measured: **728 characters** on the ambiguity case, **1,187** on the migration
case. That is why the context window default is **4096** rather than INPUT.2's
16384 — this is phrasing, not interpretation, and a small window keeps a laptop
model fast and cool. A 4096-vs-8192 comparison on the migration prompt produced
responses of 881 and 878 characters respectively, so nothing was being
truncated and the wider window bought nothing.

### Need ids are short because a 4B model has to copy them

The first live run surfaced a real defect. The anchor ids were originally
`ambiguity:reported_ambiguity_1` and `missing:scope_1`; `qwen3.5:4b` returned
an otherwise perfect response that had silently dropped the `ambiguity:`
prefix, and the boundary correctly rejected the whole thing.

The boundary was right and the id format was wrong. Anchors are now
`ambiguity_1` and `missing_1` — numbered by position in the decision rather
than per kind, so they stay unique — and a `CompletionDecision` refuses to be
built with two needs sharing an anchor. After the change the same model
returned usable questions on both cases.

An opt-in live smoke (`RUN_LIVE_INTAKE_ASSISTANT_TESTS=1`) records latency,
prompt size and availability for two bounded phrasing tasks, and asserts the
canonical fingerprint survived. It is skipped by default and is in no
validation command.

### Measured, for honesty rather than as a benchmark

`qwen3.5:4b`, local, one smoke run per case, 45–85s per call on this laptop:

| Case | Prompt | Status | Result |
| --- | --- | --- | --- |
| Ambiguity | 728 chars | `intake_assistant_ok` | "Which item are you referring to when you say 'it'?" |
| Goal brief | 1,187 chars | mixed across runs | 4 natural questions when ok; deterministic wording when not |

A 4B reasoning model does not answer identically every time: across the runs
performed, some calls produced clean structured output and some produced
something the strict parser refused. **In every case the canonical decision was
byte-identical to the zero-model run.** That is the design working, not the
design failing — the model is allowed to be unreliable precisely because it has
no authority.

## Authority

Every decision, projection, assistance record and outcome serializes:

```text
routing_authority · execution_authority · repository_read_authority
repository_write_authority · patch_authority · validation_authority
benchmark_authority · worker_launch_authority · provider_selection_authority
model_escalation_authority · dream_authority · project_evolution_authority
mode_selection_authority                                        → all false
human_approval_required                                          → true
```

No completion state changes any of them. READY grants nothing. The contract's
own `routing_allowed` is read and never written.

## Registry mismatch, stated plainly

The ROAD.1 schema hard-errors on `network_allowed=true`. INPUT.3 registers both
`network_allowed` and `model_calls_allowed` as false, which is true of the
phase: the implementation, the default behavior, the test suite and every
validation command perform zero model and zero network calls.

What the schema still cannot express is a phase that *ships an opt-in local
capability it never exercises*. The gap is recorded in the phase notes. It is
smaller than INPUT.2's, because there is no cloud spend on the other side of
the opt-in — only a local model an operator has already installed.

No registry safety rule was weakened.

## Not wired

Nothing calls `complete_intake` in a live path. Chat, Instant Run, Mixed Mode,
Commander, Goal Brief submission and execution, Project Evolution, Dream,
CTX.SELECT, the indexer, the graph, patching, validation, benchmarks, lessons,
the model Driver and provider routing are untouched.

## Next

WAITER.1 should take a `CompletionDecision` whose
`ready_for_future_handoff` is true and decide *which workflow* handles it. It
should consume that as an input signal, never as permission, and should
re-derive its own authority — a complete order still has to be authorized
before it is cooked.
