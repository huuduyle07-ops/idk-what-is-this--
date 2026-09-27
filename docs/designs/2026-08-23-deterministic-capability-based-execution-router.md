# WAITER.1 — Deterministic Capability-Based Execution Router

Date: 2026-08-23
Status: complete
Next: WAITER.2 — how the selected workflow acquires its evidence

## Decision

INPUT.1 preserved what the user said. INPUT.2 understood what they meant.
INPUT.3 decided whether that understood order was complete. WAITER.1 answers
the next question, and stops:

> Which execution workflow has the capabilities required by this valid order?

It does not answer *how the workflow should execute it*.

```text
User Prompt
    ↓
INPUT.1  Preserve                 [frozen]
    ↓
INPUT.2  Understand               [frozen]
    ↓
INPUT.3  Complete?                [frozen]
    ↓
TaskContract + CompletionDecision + semantic receipt
    ↓
Handoff Eligibility Gate          [WAITER.1]
    ↓
Task Shape                        [WAITER.1]
    ↓
Capability Requirements           [WAITER.1]
    ↓
Deterministic Workflow Policy     [WAITER.1]
    ↓
WaiterDecision
    ↓
STOP
```

The Semantic Waiter understands what the customer ordered. The Execution
Waiter decides which kitchen has the equipment to cook it — and then stops at
the kitchen door.

## The failure this phase exists to fix

A real request:

> Analyze DeepSeek Harness against C.A.T.T.U.S using this five-way matrix…

went to **Instant Run**. It carried a comparison, an architecture analysis,
repository evidence needs, a user-supplied rubric, and multi-stage
investigation. Every one of those was visible; none of them was consulted.

The bug was not a mis-tuned threshold. It was a **missing stage**. The old
routers went straight from words to a mode:

```text
prose  →  keyword signals  →  mode
```

Nothing in between ever asked *what the order would require*. WAITER.1 inserts
that layer:

```text
structured facts  →  task shape  →  capability requirements  →  workflow
```

Once the question is asked, "compare A and B from what I pasted" and "compare
A and B by inspecting both repositories" stop looking alike. They share a task
family and an analysis shape, and they differ in **evidence scope** — and it is
the evidence scope that needs a workflow able to reconnoitre.

> The noun "compare" never decides a route.

## Modules

| Module | Responsibility |
| --- | --- |
| `core/task_shape.py` | `TaskShape`, `ProjectEvolutionRequest`, deterministic shape derivation |
| `core/capability_requirements.py` | `CapabilityRequirements`, bounded provenance vocabulary, derivation |
| `core/execution_waiter.py` | `WaiterDecision`, the rule table, `route_execution_workflow`, canonical fingerprint |
| `core/waiter_receipt.py` | The hard entry gate, source fingerprints, the authority block |

No INPUT.1, INPUT.2 or INPUT.3 module was modified. WAITER.1 is built entirely
on their public contracts.

## The hard entry gate

Routing requires INPUT.3's derived `ready_for_future_handoff`. WAITER.1
re-derives it rather than trusting a flag, and adds two integrity checks of its
own.

| Blocker | Source |
| --- | --- |
| `completion_not_ready` | INPUT.3 |
| `contract_missing` | INPUT.3 |
| `preservation_failed` | INPUT.3 / INPUT.1 |
| `semantic_receipt_missing` | INPUT.3 |
| `semantic_receipt_invalid` | INPUT.3 |
| `contract_decision_mismatch` | WAITER.1 — the contract and decision do not describe one run |
| `contract_routing_not_allowed` | WAITER.1 — INPUT.1's own fail-closed flag is false |

Any blocker produces `status=not_handoff_ready` with **no workflow, no shape
and no capabilities**. A blocked order is not described at all: WAITER.1 does
not reinterpret it to rescue it, and it does not ask a model.

`READY` alone is not enough. A standalone INPUT.3 preview with no semantic
receipt is READY and is not routable.

## Task Shape

Six fields, all bounded, all derived from structured facts.

| Field | Vocabulary |
| --- | --- |
| `task_family` | `conversational`, `explanatory`, `analysis`, `comparative_analysis`, `research`, `implementation`, `debugging`, `review`, `planning`, `project_evolution`, `unknown` |
| `interaction_shape` | `single_stage`, `multi_stage` |
| `evidence_scope` | `none`, `direct_context`, `bounded_repository`, `broad_repository`, `external_information`, `mixed_sources` |
| `change_shape` | `no_change`, `bounded_change`, `broad_change` |
| `analysis_shape` | `simple`, `synthesis`, `comparative`, `investigative` |
| `horizon` | `immediate`, `bounded_multi_stage`, `long_running` |

Plus three derived booleans that make the routing predicates legible:
`comparison_present`, `broad_repository_scope`, `explicit_project_evolution`.

Every family except `project_evolution` is a direct mapping of a frozen
`TaskContract` task type — not a second taxonomy laid over INPUT.1's.

### Where breadth comes from

```text
repository_required = repository_inspection_required or local_repository_required

broad_repository_scope = repository_required and (
      multi_stage                       # coordination is already required
   or family in ANALYSIS_FAMILIES       # the repository IS the evidence to survey
   or verified project-evolution declaration
)
```

`ANALYSIS_FAMILIES` is `analysis`, `comparative_analysis`, `research`,
`review` — families whose deliverable *is* the analysis. When such a task needs
the repository, the code must be surveyed before anything can be said about it.

An `implementation` or `debugging` task that names its target and needs one
stage stays bounded. This is what keeps "fix this typo in README.md" and "run
the tests for this module" out of Commander while sending "investigate why
indexing takes an hour across the pipeline" into it.

Breadth is a property of the work, never of the prompt. No token count, no
character count, no prompt length participates.

## Capability Requirements

Eleven capabilities, total and ordered on every record.

| Capability | True when |
| --- | --- |
| `conversational_response_required` | the family's deliverable is an answer |
| `direct_context_analysis_required` | `evidence_scope == direct_context` |
| `repository_read_required` | evidence scope reads the repository |
| `broad_repository_reconnaissance_required` | `broad_repository_scope` |
| `external_information_required` | the contract records it |
| `cross_source_synthesis_required` | repository **and** external evidence |
| `comparison_required` | a comparison relationship survives, or the task is comparative |
| `code_change_required` | `change_shape != no_change` |
| `validation_required` | a change is required |
| `multi_stage_coordination_required` | `interaction_shape == multi_stage` |
| `persistent_project_context_required` | a **verified** evolution declaration |

### Requirements, not permissions

```text
repository_read_required = true      ≠   repository_read_authority = true
```

The first says a future workflow would have to read the repository. The second
does not exist here: every authority is false in every status. WAITER.1 read
nothing.

### Provenance

Each required capability cites the structured facts it came from, drawn from a
bounded vocabulary of INPUT field paths and Task Shape fields:

```text
repository_read_required:
  value: true
  reasons:
    - task_shape.evidence_scope=broad_repository
    - task_contract.execution_requirements.repository_inspection_required=true
    - task_contract.execution_requirements.local_repository_required=true
```

A reason whose source is not in the vocabulary is rejected at construction, so
an inferred requirement can never be phrased as *"the user explicitly requested
repository traversal"*. A required capability with no reasons is likewise
rejected: a demand that cannot say where it came from is not a demand worth
honouring.

## Workflow targets

Four classes, in the repository's existing vocabulary:

| Target | Existing shell names |
| --- | --- |
| `chat` | `chat` |
| `instant_run` | `instant_run` |
| `commander` | `commander_plan` (UX.4), `commander_run` (CMD.1) |
| `project_evolution` | `project_evolution` |

**Mixed Mode and the Unified Workbench are not targets.** They are interaction
shells capable of dispatching; neither is an execution capability class. **Goal
Brief is not a target** either — it is an intake projection.

## The rule table

Deterministic, in precedence order. No scoring, no weighting, no confidence.

| # | Predicate | Result | Reason code |
| --- | --- | --- | --- |
| 0 | entry gate failed | `not_handoff_ready` | `ROUTE_BLOCKED_INPUT_NOT_HANDOFF_READY` |
| 1 | `persistent_project_context_required` | `project_evolution` | `ROUTE_PROJECT_EVOLUTION_EXPLICIT_LONG_HORIZON` |
| 2 | `multi_stage_coordination_required` | `commander` | `ROUTE_COMMANDER_MULTI_STAGE` |
| 2 | `broad_repository_reconnaissance_required` | `commander` | `ROUTE_COMMANDER_BROAD_REPOSITORY_RECON` |
| 2 | `cross_source_synthesis_required` | `commander` | `ROUTE_COMMANDER_CROSS_SOURCE_SYNTHESIS` |
| 3 | `repository_read_required` or `code_change_required` | `instant_run` | `ROUTE_INSTANT_BOUNDED_REPO_OPERATION` |
| 4 | known family needing an answer, supplied context, or external information | `chat` | `ROUTE_CHAT_DIRECT_CONTEXT_ONLY` / `ROUTE_CHAT_EXTERNAL_LOOKUP_ONLY` / `ROUTE_CHAT_NO_EXECUTION_CAPABILITY_REQUIRED` |
| 5 | anything else | `uncertain` | `ROUTE_UNCERTAIN_TASK_SHAPE_UNDETERMINED` |

Rule 2 collects **every** applicable reason, so a Commander route explains all
of its causes rather than the first one matched.

Rule 2 sits above rule 3 because orchestration is a strictly larger capability
set than a bounded operation. Rule 1 sits above rule 2 because an ongoing
process is not merely a large task.

### Why there is no `unsupported` status

Three statuses exist: `routed`, `not_handoff_ready`, `uncertain`. An
`unsupported` status was considered and deliberately not created — every
capability in the bounded vocabulary is within reach of one of the four
workflow classes, so it could never be produced, and a status that cannot occur
is decoration rather than honesty.

`uncertain` is real: a verified handoff whose family is `unknown` and whose
capabilities demand nothing gets no recommendation. Guessing one would be the
original failure in a new costume.

## Broad is not ongoing

`project_evolution` is unreachable by breadth, difficulty, file count,
architecture, or prompt length. `TaskShape` **refuses to be constructed** in
that family without a verified declaration — the invariant is structural, not
merely policy.

INPUT.1's frozen task vocabulary has no value for lifecycle intent, so WAITER.1
cannot read one off the contract. Rather than infer it from complexity, the
declaration is an explicit optional input:

```python
ProjectEvolutionRequest(
    evidence_text="Continue evolving this project through the roadmap phases",
    declared_by="human_declared_workflow_intent",
    source_raw_request_sha256=contract.raw_request.sha256,
)
```

### Literal backing is necessary and not sufficient

The first cut of this record checked one thing: `evidence_text` had to be a
literal span of the preserved raw request. That blocks invented evidence text
and nothing else, and there is a whole class of false declaration it cannot
see — **real words carrying an externally invented label**:

> Do not use Project Evolution; just refactor this architecture.

`"Project Evolution"` is genuinely in that sentence. A caller quoting it was,
under the substring check alone, enough to route an explicit *refusal* of
Project Evolution into Project Evolution. The words were the user's; the
meaning attached to them was not.

`check_project_evolution_request` therefore applies four independent checks, in
a fixed order, all of which must pass:

| # | Check | Disqualifier when it fails |
|---|-------|----------------------------|
| 1 | a declaration was supplied at all | `project_evolution_not_explicitly_requested` |
| 2 | `declared_by` names a trusted source | `project_evolution_not_explicitly_authorized` |
| 3 | `source_raw_request_sha256` is this request's fingerprint | `project_evolution_provenance_unverified` |
| 4a | `evidence_text` is a literal span of the raw request | `project_evolution_declaration_not_literally_supported` |
| 4b | that span is not inside a prohibition the user wrote | `project_evolution_declaration_negated_by_user` |

Checks 1 and 4a were there before. Checks 2, 3 and 4b are the closure.

**Trusted sources are a bounded vocabulary of two:**
`explicit_input_evidence` and `human_declared_workflow_intent`. The untrusted
half — `inferred`, `waiter_inference`, `model_inference`,
`task_shape_inference`, `task_complexity`, `repository_scope` — is
*representable on purpose*. A caller's honest admission that it inferred the
intent has to be sayable, or it gets laundered into a trusted value instead of
being recorded and refused. None of the six can authorise anything. Waiter
inference, model inference, task complexity, repository breadth, architecture
scope, prompt length and a downstream persistent-context need are all, by
construction, incapable of creating Project Evolution intent.

**The fingerprint binds a declaration to one request.** It is
`raw_request.sha256`, an identifier INPUT.1 already publishes; nothing was added
to INPUT.1 to manufacture it. A declaration read from yesterday's order cannot
be replayed against today's.

**Negation is read literally, and scoped the way words are.** The prohibitions
consulted are INPUT.1's own `ExplicitConstraint` extraction — marker words the
user typed, `do not` / `must not` / `never` — and a prohibition binds what
*follows* its marker. So:

- "Do not use **Project Evolution**; just refactor this architecture" → the span
  sits after `do not` → negated, refused.
- "**Continue evolving this project through the roadmap phases** in
  docs/roadmap/phase_registry.json, but do not touch database/schema.py" → the
  span precedes the marker → not negated, honoured.

No meaning is extracted at any point. Checks 3, 4a and 4b are fingerprint and
substring identities, the same literal mechanisms INPUT.1's preservation gate
uses to decide whether an explicit commitment survived.

### Refusing a declaration is not refusing the order

A failed declaration disqualifies **one workflow**, and the request then routes
through the ordinary rule table. "Do not use Project Evolution; just refactor
this architecture across two modules" comes out as `commander` with
`project_evolution_declaration_negated_by_user` recorded — which is exactly
what the user asked for. WAITER.1 asks no clarification question and fails no
request over a declaration it declined to honour.

When no declaration is supplied at all, every Commander route carries
`project_evolution_not_explicitly_requested`, because "this task is big" is the
single most tempting reason to reach for Project Evolution and the single least
sufficient one. When a declaration *was* supplied and refused, that code is
replaced by the specific check it failed: it was requested, and it was not
authorised.

**Known INPUT representation limit, stated plainly:** with no declaration
supplied, `PROJECT_EVOLUTION` is simply never recommended. If a future INPUT
phase learns to represent lifecycle intent structurally, it should fill this
declaration. No INPUT module was changed to accommodate it, in the first cut or
in the closure.

## WAITER does not reinterpret the user

There is no regex over prose for pronouns, comparisons, task type, complexity,
project intent, or repository need. Shape comes from the task classification,
the surviving relationships, the recorded execution requirements, and INPUT.1's
literal explicit evidence.

> INPUT says what the order means.
> WAITER determines what capabilities that order requires.

The consequence is that the policy is language-independent by construction.
"Explain the Bellman equation." and "Giải thích phương trình Bellman." produce
byte-identical task shapes, because neither prompt is read.

## Workflow is not compute

A workflow class is a set of capabilities. It is never a model, a provider, or
a budget.

WAITER.1 **cannot** name Gemini, Gemma, Qwen, Claude, GPT, Ollama, cloud or
local, a model size, a provider, a context window, or a fallback chain —
because no such field exists on any record it produces. A `commander` route
means *"a workflow able to orchestrate several bounded operations"*, never
*"use a bigger model"*. A `chat` route never means *"use a small local model"*.

The proof is a test, not a promise: every routed decision is rendered, the
authority block that names those powers **in order to deny them** is stripped,
and no compute token may survive anywhere else.

## Recommending is not planning

When `commander` is recommended, the decision stops at the workflow name. There
is no stage list, no read set, no file list, no reconnaissance, and no
CTX.SELECT call — not fields WAITER.1 declines to fill, but fields it does not
have.

`external_information_required=true` records a need. No search is performed.
`repository_read_required=true` records a need. No file is opened, no manifest
read, no Canonical Graph or Activation Graph consulted, no index built.

## Determinism

No timestamp, no random id, no model output, no ambient machine state, no
filesystem state, and no network can affect a recommendation. The four modules
import nothing beyond `dataclasses`, `hashlib`, `json` and `typing`; a static
test asserts that none of them contains an `os`, `subprocess`, `socket`,
`requests`, `urllib` or `pathlib` import, or an `open(` call.

Each decision fingerprints the exact contract and completion decision it
consumed, with sha256 over canonical JSON, so a recommendation can be audited
against its inputs.

## Authority

Every decision — including a routed one, including
`recommended_workflow=project_evolution` — serialises:

```json
{
  "routing_execution_authority": false,
  "execution_authority": false,
  "repository_read_authority": false,
  "repository_write_authority": false,
  "patch_authority": false,
  "validation_authority": false,
  "benchmark_authority": false,
  "worker_launch_authority": false,
  "provider_selection_authority": false,
  "model_selection_authority": false,
  "model_escalation_authority": false,
  "dream_authority": false,
  "project_evolution_authority": false,
  "planning_authority": false,
  "context_selection_authority": false,
  "human_approval_required": true
}
```

A recommendation is descriptive. Later wiring may consume it, but must obtain
its own authority under its own gates.

## Not wired

Nothing calls `route_execution_workflow` in a live path. Chat, Instant Run,
Commander, Mixed Mode, the Unified Workbench, Project Evolution, Goal Brief,
Dream, CTX.SELECT, the planner, the indexer, the graph, patching, validation,
benchmarks, the model Driver and provider routing are all untouched. No
workflow starts because of a recommendation.

## Routing matrix, as tested

| Case | Order | Route |
| --- | --- | --- |
| A | "Explain the Bellman equation." | `chat` |
| B | pasted two-function readability comparison | `chat` |
| C | "Fix the typo 'teh' to 'the' in README.md." | `instant_run` |
| D | one-file implementation in a named module | `instant_run` |
| E | broad indexing investigation across the pipeline | `commander` |
| F | **DeepSeek Harness dogfood, repository evidence required** | `commander` |
| G | **the same dogfood prompt, everything supplied** | `chat` |
| H | multi-component storage migration | `commander` |
| I | explicit "continue evolving this project through the roadmap phases" | `project_evolution` |
| J | whole-architecture refactor, no evolution intent | `commander` |
| K | READY preview over a failed preservation gate | *no route* |
| L | missing semantic receipt | *no route* |
| M | `ASK_CLARIFICATION` | *no route* |
| N | `GOAL_BRIEF_ASSIST` | *no route* |
| O | semantic system failure, no contract | *no route* |
| P | "Giải thích phương trình Bellman." | `chat` |
| Q | Vietnamese broad repository analysis | `commander` |
| R | external lookup, no repository work | `chat` |

F and G are the same prompt. Only what INPUT recorded as needed differs.

### Project Evolution provenance matrix

| Case | Declaration supplied | Route | Disqualifier |
| --- | --- | --- | --- |
| 1 | trusted source, bound, literal, un-negated | `project_evolution` | — |
| 2 | same evidence, `declared_by` an inference source | `commander` | `project_evolution_not_explicitly_authorized` |
| 3 | `"Project Evolution"` quoted out of *"Do not use Project Evolution"* | `commander` | `project_evolution_declaration_negated_by_user` |
| 4 | invented evidence over a request that never mentions evolution | `commander` | `project_evolution_declaration_not_literally_supported` |
| 5 | large multi-component architecture refactor, none supplied | `commander` | `project_evolution_not_explicitly_requested` |
| 6 | persistent multi-stage roadmap order, none supplied | `commander` | `project_evolution_not_explicitly_requested` |
| 7 | trusted and literal, fingerprint of another request | `commander` | `project_evolution_provenance_unverified` |
| 8 | trusted and literal, no fingerprint at all | `commander` | `project_evolution_provenance_unverified` |

Cases 1, 3, 5 and 6 differ in the declaration, not in the order. Every refusal
still produces a route: `status` is `routed` in all eight rows.

## Limits

- **Investigate-only versus investigate-and-fix.** INPUT.1 has no field
  distinguishing them, so a `debugging` task that needs the repository is
  conservatively treated as potentially changing. This affects `change_shape`
  and `code_change_required`, never a route in the tested matrix — and a
  requirement is not a permission.
- **`direct_context` detection is literal.** Quoted spans, list items and a
  supplied framework count as supplied evidence. A named entity is a name and a
  URL is a pointer elsewhere; neither counts. Pasted code without any delimiter
  is invisible to INPUT.1 and therefore to WAITER.1.
- **Negation detection is exactly as wide as INPUT.1's prohibition
  extraction.** A refusal phrased without a literal marker word — "skip the
  evolution process", "no need for the roadmap track" — produces no
  `ExplicitConstraint`, so check 4b sees nothing to negate. Checks 2 and 3 still
  stand in the way, so the declaration must still come from a trusted source and
  be bound to this request; what is not caught is a *trusted* caller quoting an
  unmarked refusal. Widening this belongs in INPUT.1's constraint vocabulary,
  not in a heuristic here.
- **Everything downstream of the contract is only as good as the contract.** If
  INPUT.2 records `multi_stage=false` on work that genuinely needs three
  stages, WAITER.1 will route Instant Run and be wrong for the right reason.
  The fix belongs in INPUT, not in a heuristic here.
