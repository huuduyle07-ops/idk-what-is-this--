# WAITER.LIVE.1 — Live Task-Shape Routing & Change-Need Separation

**Track:** WAITER · **Prerequisite:** CONTROL.SAFETY.LIVE.1 · **Status:** live production routing change (not report-only)

## 1. The failure this phase exists for

Two black-box field tests, one cause.

**Case A — analysis.** The user asked:

> Compare deepseek-harness and C.A.T.T.U.S architecture.

No code change was requested. The live runtime nevertheless indexed for roughly
twenty-six minutes, ran graph localization, formed a CONTROL patch hypothesis,
ranked an unrelated test file first, demanded an exact `source_snippet`, and
finished on the patch-oriented fallback prompt whose summary reads *"Cannot
safely generate patch because CONTROL did not provide an exact source
snippet."* The final answer echoed the user's own task back at them. Nobody had
asked for a patch, so the refusal to write one was not an answer to anything.

**Case B — explicit change.** The user asked:

> Add task priority support.

There is no pre-existing defect here, and there is not supposed to be. The
model produced a correct five-operation multi-file plan. After
CONTROL.SAFETY.LIVE.1 — correctly — a change with no failing-validation
evidence cannot use the defect-grounded CONTROL path to gain patch eligibility,
so `enforce_control_grounding_on_payload` nulled the plan. CONTROL.SAFETY.LIVE.1
is not wrong; the runtime simply had no other way to say *why* a change was
needed.

Both cases share one root cause: **production had no place to say what kind of
order it was holding before it started looking for something to patch.**

## 2. What changed

A deterministic task-shape gate now sits in front of CONTROL, at every real
entry point:

```
resolved user task
    ↓
LiveTaskShape                        core/live_task_shape.py
    ↓
LiveRouteReceipt                     core/live_task_routing.py
    ↓
┌── ANALYSIS_ONLY ────────► analysis_answer
│      bounded document evidence, user-readable answer
│      no index · no preflight · no CONTROL · no snippet · no write
│
├── DEFECT_REPAIR ────────► defect_repair_patch
│      index → preflight → OPS.VALIDATE.1 → CONTROL localization
│      → defect grounding → exact source → patch safety → apply → validate
│      (unchanged)
│
├── EXPLICIT_CHANGE ──────► explicit_change_patch
│      index → CONTROL context acquisition → change-oriented planning
│      change_need_source = explicit_user_request
│      exact verbatim source quotes, patch safety, CTX and authorization
│      all still required
│
└── NEEDS_CLARIFICATION ──► clarification
       read-only; states every obligation and asks. Never a write workflow.
```

The gate runs **before** `index_repository`, **before** `run_preflight_validation`
and **before** `run_control_structured`. That ordering is the fix for Case A's
twenty-six minutes: nothing that depends on the task being a patch task happens
until the runtime knows whether it is one.

## 3. Reuse, and the one mismatch

WAITER.1 already contained the routing architecture. It was never wired. This
phase wires it and reuses, unchanged:

| Reused | From |
| --- | --- |
| Literal explicit-evidence extraction | `core.explicit_evidence` (INPUT.1) |
| Deterministic semantic interpreter | `core.semantic_waiter.ExplicitEvidenceInterpreter` (INPUT.1) |
| Requirement-preservation gate | `core.requirement_preservation` (INPUT.1) |
| Lossless Task Contract assembly | `core.input_understanding.understand_request` (INPUT.1) |
| Task Shape derivation | `core.task_shape.derive_task_shape` (WAITER.1) |
| Capability Requirement derivation | `core.capability_requirements` (WAITER.1) |
| Deterministic workflow rule table | `core.execution_waiter.select_workflow` (WAITER.1) |
| Authority / guardrail blocks | `core.waiter_receipt` (WAITER.1) |

**The one proven integration incompatibility.**
`core.execution_waiter.route_execution_workflow` consumes an INPUT.3
`CompletionDecision`, and `core.waiter_receipt.check_handoff_eligibility`
rejects any decision whose INPUT.2 semantic receipt does not attest to
`model_call_count >= 1`. INPUT.2's model-backed Semantic Waiter is not wired
into the live runtime, so the frozen entry point cannot be reached from
production without adding exactly the model call this phase forbids
(§33: zero additional model calls for routing).

The adapter around that mismatch is deliberately minimal:

* the handoff gate is replaced by INPUT.1's own fail-closed preservation
  verdict — a contract whose explicit commitments did not survive routes to
  `needs_clarification`, never to a patch route;
* `LiveTaskFieldsInterpreter` wraps — does not replace —
  `ExplicitEvidenceInterpreter`, overriding exactly two fields the frozen
  deterministic interpreter cannot derive:
  * `task` (it has no rule that yields `implementation` or `debugging`, because
    INPUT.2's model was meant to supply those), derived from literal marker
    words;
  * `execution_requirements` (its rule reads "a repository is involved" off file
    paths in the prose; live, production already *knows* whether a repository is
    attached).

Everything else — subjects, relationships, framework, constraints, requested
output, preservation — is INPUT.1's, unaltered. The adapter is labelled
`live compatibility adapter` in code and in every serialised receipt. It is not
an authoritative semantic replacement and it is not a second semantic system.

## 4. Task-shape vocabulary

Four shapes. Each changes what production may do next; a fifth that did not
would be description rather than routing.

| Shape | `change_requested` | `defect_claim_present` | `change_need_source` |
| --- | --- | --- | --- |
| `analysis_only` | false | false | `none` |
| `defect_repair` | true | true | `unresolved` → `grounded_defect` only via OPS.VALIDATE.1 |
| `explicit_change` | true | false | `explicit_user_request` |
| `needs_clarification` | false | false | `unresolved` |

Classification precedence, fixed and deterministic:

0. empty request → `needs_clarification`
1. an analysis obligation and a change obligation in **separate ordered
   clauses** → `needs_clarification` (§31 mixed request)
2. a defect claim or a repair imperative → `defect_repair`
3. an explicit change request → `explicit_change`
4. an analysis marker, or an answer task type INPUT.1 already read off the
   words → `analysis_only`
5. anything else → `needs_clarification`

Rule 2 sits above rule 3 because "fix this bug" asks for both, and the defect
route is the one that demands evidence before it patches. Rule 5 is the
fail-closed default: an order nobody can read is never a patch target.

Two details earn their complexity:

* **Change verbs are refused in call position.** `add(2, 2) returns 0` names a
  function; reading its `add` as a feature request would send the calc.py defect
  down the wrong road. The pattern is `\badd\b(?!\s*\()`.
* **`conversation` is not an answer type here.** INPUT.1 reports `conversation`
  when a request carries *no explicit evidence at all* — which is exactly the
  ambiguous case. "Improve the agent." names no subject, no defect and no
  change; treating its emptiness as "an analysis was requested" would answer a
  question nobody asked. It falls through to `needs_clarification` (§30).

## 5. Change need versus defect establishment versus write authority

Three separate facts that the old runtime collapsed into one:

```
change_requested        "the user wants something changed"
defect_established      "executed failure evidence proves something is broken"
write_authority         "this process may modify the repository"
```

* A feature: `change_requested=true`, `defect_established=false`,
  `write_authority=false`. Valid, and now representable.
* An analysis question: `change_requested=false`, `defect_established=false`,
  `write_authority=false`.
* A real bug, after grounding: `change_requested=true`,
  `defect_established=true`, `write_authority=false` until the existing
  authorization gates say otherwise.

`change_need_source` names *why* a change is needed and never *whether* one may
be written. It has four values and no confidence: `none`,
`explicit_user_request`, `grounded_defect`, `unresolved`.
`LiveTaskShape.__post_init__` refuses to construct a shape whose
`change_need_source` is `grounded_defect`: only CONTROL.SAFETY.LIVE.1, from
OPS.VALIDATE.1 facts bound to exact source, may set that.

`LiveRouteReceipt.write_authority` and `.patch_application_authority` are
read-only properties that return `False` unconditionally — not defaults a caller
can override.

## 6. What the explicit-change path changed in CONTROL, and what it did not

`refresh_control_safety` now records `change_need_source` on
`patch_candidate_state` and `patch_intent`, derived from the attached route and
the defect-grounding result. It is `grounded_defect` when — and only when —
`defect_established` is true.

`enforce_control_grounding_on_payload` gains a second legitimate reason for a
payload to survive, alongside the defect one:

| | defect route | explicit-change route |
| --- | --- | --- |
| Why a change is needed | executed validation failure bound to a ranked file | the user asked, in their own words |
| Target binding | must include CONTROL's grounded file | every operation must target a file whose source this run actually acquired |
| Source grounding | CONTROL exact `source_snippet` | verbatim quote from acquired source, checked against the file on disk |
| Quote grounding, patch safety, CTX.PATCH/CTX.APPLY, forbidden paths, byte fidelity, validation | unchanged | unchanged |
| `AUTO_PATCH_ENABLED` | monotonic | monotonic |
| Auto-apply | requires `defect_grounded` | **still** requires `defect_grounded`, so a feature never auto-applies |
| Human approval | unchanged | unchanged |

The explicit-change path supplies a different legitimate reason for **why** a
change is needed. It does not weaken **how** one may be executed. In particular
`build_patch_policy(defect_grounded=…)` is untouched: `auto_apply_allowed`
still requires a grounded defect, so an explicit feature request produces a
reviewable plan and never an automatic write.

Multi-file plans are permitted for the explicit-change route (§24) within the
existing operation and file budgets, because a feature that genuinely spans
model, store and CLI must not be flattened into "find one suspicious symbol".

## 7. The analysis path

* **Never enters patch localization.** `route_allows_patch_localization` returns
  `False` for an absent route as well as an analysis route, so a code path that
  forgets to look fails closed rather than carrying on as before.
* **Never requires a replacement snippet.** `source_grounding = none`.
* **Never runs validation to answer a question.** Preflight is skipped.
* **Never indexes to classify.** `repository_indexing_allowed = False`.
* **Never gains write authority.** `write_authority` and
  `patch_application_authority` are false, and `maybe_run_auto_patch` and the
  patch post-processing battery are both skipped on a read-only route.

Evidence comes from `core/analysis_evidence.py`: a fixed priority order over
the repository inventory production had *already* built — files the user named,
the documents a repository writes about itself, paths naming a requested
subject, architecture documents, package manifests, canonical entry points —
capped at 12 files / 6 000 chars each / 60 000 chars total. No ranking model, no
embedding, no scoring, no graph, no traversal beyond that inventory.

This is explicitly **not** a retrieval redesign (§13, §46). Choosing *better*
documents for a large repository remains a known separate problem. The invariant
delivered here is narrower and is the one that was broken: an analysis question
no longer becomes a patch-target search.

The answer prompt is natural language, carries the acquired excerpts, lists the
files read, lists the evidence gaps, and instructs the model to declare a gap
rather than fill it. It contains no patch schema and no instruction to return
`patch_candidate=null`.

## 8. Ordered obligations

`split_obligations` splits only at sequencing the user wrote themselves
(`then`, `next`, `finally`, `after that`, `;`, newline), preserving order and
rewording nothing. The obligations ride on the route receipt and into every
answer prompt, so "compare X, then recommend Y" cannot be silently reordered and
"change A but do not touch B" keeps its prohibition — which INPUT.1's constraint
extraction had already preserved on the contract.

A mixed request — an analysis obligation and a change obligation in separate
clauses — routes to `needs_clarification` with both halves stated, rather than
having either half dropped. Commander decomposition is out of scope here.

## 9. Boundaries held

* **No model call** is added anywhere in routing. Routing is literal marker
  matching plus INPUT.1 extraction. The embedding-backed
  `core.router.classify_task` is *not* consulted for task shape.
* **No network call** is added.
* **No indexing or graph traversal** is added; the analysis route *removes*
  both, and routing itself reads no files.
* **CONTROL.SAFETY.LIVE.1 is not weakened.** Localization rank still cannot
  mint defect certainty, suppress escalation, create auto-patch permission or
  grant write authority. `defect_established` still requires an executed
  OPS.VALIDATE.1 failure bound to a ranked file.
* **OPS.VALIDATE.1 semantics are unchanged.** Passing, failing and inconclusive
  keep their meanings; inconclusive still establishes nothing.
* **OPS.PATCH.1, patch safety, CTX.PATCH and CTX.APPLY are untouched.**
* WORKER.DECL.2B remains parked; CHECK.2 / CHECK.3 / CHECK.LIVE.2A are not
  wired; `code_dna` indentation, Phantom Limb and the CLI DB/session fallback
  are out of scope and recorded as follow-ups.

## 10. Known limitations

1. **Retrieval quality is untouched.** A defect repair on a very large
   repository may still rank a poor candidate. CONTROL.SAFETY.LIVE.1 makes that
   safe; future retrieval work will make it useful. The two must not be
   conflated.
2. **Marker vocabulary is literal.** A change request phrased entirely without
   a change verb ("the CLI should really have a `--json` flag") reads as
   `needs_clarification` rather than `explicit_change`. Failing to
   `needs_clarification` is the intended direction.
3. **`web/app.py` `mode="control"`** is a direct request to run CONTROL as an
   inspection tool, not a user task, so it is deliberately not routed. It is
   recorded here rather than silently exempted.
4. **The recorded `waiter_workflow`** (WAITER.1's own recommendation over the
   same shape) can read `instant_run` for a `needs_clarification` order, because
   WAITER.1's rule 3 fires on a repository-read requirement before its
   known-family check. It is observability only and selects nothing.
5. **Scout is skipped on the analysis route**, removing one existing model call
   from that path. That is a reduction, never an addition.

## 11. Follow-ups recorded, not done here

* Retrieval / large-graph ranking quality for the defect route.
* `code_dna` indentation detection.
* Phantom Limb accuracy.
* CLI validation-directive UX and the DB-disabled `create_session` fallback.
* Commander decomposition for genuinely mixed multi-part orders.
