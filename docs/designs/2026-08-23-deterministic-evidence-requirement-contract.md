# WAITER.2 — Deterministic Evidence Requirement Contract

Date: 2026-08-23
Closure check: 2026-08-24 — no-capability-loss invariant added; WAITER.2 CLOSED / FROZEN
Status: complete
Prerequisite: WAITER.1 (frozen)
Next: ACQUIRE.1 — bounded evidence acquisition requests

## Decision

WAITER.1 answered *which kitchen receives the order*. WAITER.2 answers the next
question and only that one:

> What evidence will the selected workflow need?

It never answers *go and obtain it*.

```
INPUT.1  preserve
   ↓
INPUT.2  understand
   ↓
INPUT.3  complete
   ↓
WAITER.1 select workflow
   ↓
WAITER.2 specify evidence requirements
   ↓
STOP
```

The deliverable is an **Evidence Requirement Contract**: an immutable,
deterministic statement of evidence *classes*, priorities and handling rules. It
is not a read set, a file list, a search query, a retrieval result, a repository
manifest, a graph activation or an execution plan.

## The failure this phase exists to fix

The second DeepSeek Harness dogfood failure was not a routing failure — WAITER.1
already sends that request to Commander. It was an **evidence failure**.

C.A.T.T.U.S considered roughly 6,087 repository files as one homogeneous bucket:
end-to-end tests, snapshots, rejected and proposed design notes, and duplicate
bilingual documentation, all weighed as if they were equally authoritative
statements about how the system works.

Nothing in the pipeline had ever been asked to state, *before* any acquisition
started, which classes of evidence a task of this shape actually needs — and,
just as importantly, what each class is allowed to be used *for*.

## Modules

| Module | Responsibility |
| --- | --- |
| `core/evidence_requirements.py` | Records and bounded vocabularies: domains, roles, tiers, scopes, deferred source classes, reason codes, verification requirements, the capability-licence table, and the authority block |
| `core/evidence_policy.py` | Deterministic derivation of what evidence one order needs — **never told which workflow was selected** |
| `core/waiter_evidence.py` | Orchestration: the routed-decision gate, the source-integrity gate, the capability-envelope check, and the contract itself |

## Domain is not role

This is the distinction that fixes the dogfood.

> **Evidence domain** = where it comes from.
> **Evidence role** = how it may be used.

**Domains** (5): `direct_context`, `repository`, `validation_artifacts`,
`historical_context`, `external_information`.

**Roles** (9): `supplied_material`, `implementation_authority`,
`interface_contract`, `configuration_authority`, `architecture_description`,
`validation_evidence`, `hypothesis_support`, `historical_context`,
`current_external_authority`.

A test and a runtime module can share a domain and must never share a role:

| Thing | Domain | Role |
| --- | --- | --- |
| runtime implementation | `repository` | `implementation_authority` |
| a test | `validation_artifacts` | `validation_evidence` |
| a rejected design note | `historical_context` | `historical_context` |
| the rubric the user pasted | `direct_context` | `supplied_material` |

Only `implementation_authority`, `interface_contract` and
`configuration_authority` carry `current_authority: true` — the right to be read
as a statement about what the system does *now*. Everything else may explain,
illustrate or corroborate.

## Scope, and why it is never a number

Bounded words, mapped one-to-one from WAITER.1's frozen `TaskShape.evidence_scope`:

| `TaskShape.evidence_scope` | WAITER.2 scope |
| --- | --- |
| `none`, `direct_context` | `direct_context_only` |
| `bounded_repository` | `bounded_repository` |
| `broad_repository` | `broad_repository_reconnaissance` |
| `external_information` | `external_only`, or `mixed_sources` when the order also carries its own material |
| `mixed_sources` | `mixed_sources` |

One refinement, added by the 2026-08-24 closure check. WAITER.1 picks a single
scope and answers external before direct context, so
`Compare this pasted API description with the current official API` arrives
labelled `external_information` with the direct-context half of its evidence no
longer visible in the shape. WAITER.2 has the preserved contract in front of it,
sees that the order carried quoted material, and calls that reach
`mixed_sources` — because a contract that says `external_only` while holding a
required-primary `supplied_material` requirement is a label contradicting its own
record. An order that carries nothing stays `external_only`; no repository scope
is reachable from here, so the refinement cannot widen the work; and WAITER.1 was
not modified.

Scope is never expressed as `number_of_files = 6087`. WAITER.2 does not know what
the repository contains, and a scope expressed as a count would be a claim about
membership it has no way to make.

## Priority, not sweep

Tiers are deterministic: `required_primary`, `required_secondary`, `deferred`,
`excluded_initially`. There is deliberately **no 0–100 relevance score**. A later
retrieval layer may score *inside* a tier; it may not invent one.

For a broad architectural survey the contract says:

```
tier 1 (required_primary)
    direct_context      / supplied_material
    repository          / implementation_authority
    repository          / interface_contract
    repository          / configuration_authority
    repository          / architecture_description

tier 2 (required_secondary)
    validation_artifacts / validation_evidence

deferred
    historical_context   / historical_context
    duplicate_renderings
    unrelated_validation_artifacts

excluded_initially
    generated_artifacts
    snapshots
    temporary_artifacts
```

Not one file is named. `deferred_sources` are stated as **classes**; no ignore
file is read and no directory is walked to discover a member of any of them.

## Tests are task-sensitive, not globally secondary

"Tests are noise" would be a bad rule and this phase does not encode it.

Validation artifacts are **secondary** when they are the *instrument* of a survey
and **primary** when they are its *subject*:

| Order | Tier of `validation_artifacts` | Reason |
| --- | --- | --- |
| architecture comparison across the repository | `required_secondary` | `EVIDENCE_TESTS_FOR_VERIFICATION` |
| "why does `tests/test_indexer.py` fail?" | `required_primary` | `EVIDENCE_TESTS_ARE_THE_SUBJECT` |

The distinction is decided from what INPUT.1 already preserved — its literal file
paths and the surviving subjects — by a narrow lexical rule: a `test`/`tests`
directory segment the user wrote, or a final segment starting `test_` or
containing `_test.`. No prose is read and the filesystem is never consulted, so
`core/text_utils.py` is not mistaken for a test and "the tests are slow" names no
artifact at all.

## History explains, it does not testify

Proposed, rejected and superseded material is required at the `deferred` tier
with the role `historical_context`, never carries `current_authority`, and the
contract emits the verification requirement
`current_implementation_outranks_historical_material`.

It can say *why* something was built. It can never say *what* is built. A later
verifier may promote a historical claim; nothing in this phase can.

## No capability escalation

Every domain names the upstream capability that licenses it:

| Domain | Licensed by |
| --- | --- |
| `direct_context` | *nothing* — it is already in hand |
| `repository` | `repository_read_required` |
| `validation_artifacts` | `repository_read_required` |
| `historical_context` | `repository_read_required` |
| `external_information` | `external_information_required` |

`validation_artifacts` and `historical_context` are repository-resident classes,
so requiring them **restates** a capability WAITER.1 already recorded rather than
adding a new one — the documented invariant B17 asks for.

A requirement outside the envelope does not widen the scope. It fails the whole
contract closed with `capability_envelope_widened`, and
`check_capability_envelope` is public so the refusal can be exercised directly.

## No required-capability loss

*Added by the 2026-08-24 closure check.*

Refusing to widen is only half of faithfulness. A layer that quietly **dropped** a
required evidence capability would answer a smaller question than the one that was
asked, and — this is the part that matters — nothing downstream would ever know a
smaller question had been substituted. A widened scope announces itself when the
work costs more than expected. A narrowed one just produces a confident wrong
answer.

So the licence table is read in both directions. `CAPABILITY_EVIDENCE_OBLIGATIONS`
says what each capability obliges the contract to state:

| Capability required by WAITER.1 | Must appear as an active requirement |
| --- | --- |
| `direct_context_analysis_required` | `direct_context` / `supplied_material` |
| `repository_read_required` | `repository` / `implementation_authority` |
| `broad_repository_reconnaissance_required` | `repository` / `implementation_authority`, `interface_contract`, `configuration_authority`, `architecture_description` |
| `external_information_required` | `external_information` / `current_external_authority` |
| `cross_source_synthesis_required` | both of the two above |
| `code_change_required` | `repository` / `implementation_authority` |
| `validation_required` | `validation_artifacts` / `validation_evidence` |
| `conversational_response_required` | *(nothing)* |
| `comparison_required` | *(nothing)* |
| `multi_stage_coordination_required` | *(nothing)* |
| `persistent_project_context_required` | *(nothing)* |

An empty obligation is a deliberate answer, not an oversight: conversational
response, comparison and multi-stage coordination are things a workflow does
*with* evidence, and persistent project context is a horizon rather than a
source.

Two properties make the check worth having.

**Active means active.** A requirement at `deferred` or `excluded_initially` does
not discharge an obligation. Deferred material is on the record and out of the
work, so representing a required capability only as deferred is a loss wearing a
disguise.

**The table is total.** It is checked against `CAPABILITY_NAMES` at import, so a
capability added upstream cannot slip through this layer by simply never being
considered here.

A dropped capability fails the whole contract closed with
`required_capability_dropped`, and `check_required_capability_coverage` is public
so the refusal can be exercised directly.

Together with the envelope check:

```
WAITER.1 capability envelope
        ↓   not wider   (check_capability_envelope)
        ↓   not narrower (check_required_capability_coverage)
WAITER.2 evidence contract
```

### The case that motivated it

WAITER.1 intentionally leaves a simple current-fact lookup on the CHAT route:
needing something from outside the repository is not, by itself, a reason to wake
Commander. External evidence is a **source**, not a workflow class.

That makes the CHAT + external combination the place where a reduction to
"whatever the user pasted is the whole evidence set" would be easiest to
introduce and hardest to notice. Regression tests now pin all three shapes:

| Order | Workflow | Scope | Domains |
| --- | --- | --- | --- |
| `Explain the Bellman equation.` | chat | `direct_context_only` | direct context |
| `What changed in the latest release of X?` | chat | `external_only` | direct context, external information |
| `Compare this supplied API description with the current official API.` | chat | `mixed_sources` | direct context, external information |

The direct-context requirement is present in all three because the preserved
order is itself evidence and no acquisition step stands between the work and it.
What changes is whether anything *else* is required, and no case is ever reduced
to `direct_context_only` when it is not.

## No workflow escalation, proved structurally

`derive_evidence_policy` is **never given the selected workflow**. It cannot tune
the evidence set to a workflow and — the part that matters — it has no argument by
which an evidence need could tune the workflow. `derive_evidence_requirements`
then copies `recommended_workflow` verbatim.

Chat is never promoted to Commander, Instant Run never to Commander, Commander
never to Project Evolution. A discovered inconsistency produces
`inconsistent_input`, never a different route. A static test asserts
`core/evidence_policy.py` contains no router symbol at all.

## Fail closed

| Condition | Status | Inconsistency |
| --- | --- | --- |
| WAITER.1 status is not `routed` | `not_routed` | `waiter_decision_not_routed` |
| contract or completion does not fingerprint to the routed pair | `inconsistent_input` | `source_fingerprint_mismatch` |
| workflow outside the bounded targets | `inconsistent_input` | `unsupported_workflow` |
| a requirement outside the capability envelope | `inconsistent_input` | `capability_envelope_widened` |
| a required capability no active requirement discharges | `inconsistent_input` | `required_capability_dropped` |

In every refusal the contract carries **no requirements at all**. Guessing what an
unrouted workflow would need is exactly the kind of helpfulness this layer exists
to refuse.

## No model, no provider, no compute

The record has no field for a provider, a model, local or cloud, a context
window, a temperature or a fallback chain. Evidence source is not compute choice.
Regression tests render every contract, strip the authority block that names those
powers in order to deny them, and assert that no compute token survives anywhere
else.

## Authority

Every one of these is `false` in every status, including a fully specified one:

```
repository_read_authority        repository_write_authority
external_search_authority        context_selection_authority
indexing_authority               graph_authority
retrieval_authority              execution_authority
patch_authority                  validation_authority
benchmark_authority              worker_launch_authority
provider_selection_authority     model_selection_authority
planning_authority               routing_authority
dream_authority                  project_evolution_authority

human_approval_required = true
```

A required evidence domain grants nothing. `repository / implementation_authority`
at `required_primary` is a *description of a need*; it opens no file and records
that WAITER.2 opened none.

The guardrail block states the same thing from the other side, field by field:
`evidence_acquired`, `repository_read_performed`, `repository_traversal_performed`,
`ignore_rules_consulted`, `context_selection_performed`, `read_set_generated`,
`file_paths_produced`, `index_consulted`, `graph_activated`,
`retrieval_performed`, `web_search_performed`, `network_call_performed`,
`language_system_call_performed`, `plan_generated`, `workflow_reselected`,
`execution_performed` — all false.

## Determinism

The same routed decision over the same upstream records always produces the same
contract, on any machine, at any time, with any repository state and no network.
The three modules import no `os`, `subprocess`, `socket`, `requests`, `urllib`,
`pathlib`, `random` or `time`, and open no file — asserted statically.

An English broad-analysis order and its Vietnamese equivalent produce byte-
identical evidence contracts, because none of the derivation reads words.

## Requirement matrix, as tested

| Case | Order | Workflow | Scope | Evidence |
| --- | --- | --- | --- | --- |
| A | "Explain the Bellman equation." | `chat` | `direct_context_only` | direct context only |
| B | pasted two-function readability comparison | `chat` | `direct_context_only` | direct context only, nothing deferred |
| C | "Fix the typo 'teh' to 'the' in README.md." | `instant_run` | `bounded_repository` | implementation primary, validation secondary |
| D | one-file implementation in a named module | `instant_run` | `bounded_repository` | implementation primary |
| E | broad indexing investigation | `commander` | `broad_repository_reconnaissance` | four primary roles, validation secondary |
| F | **DeepSeek Harness dogfood** | `commander` | `broad_repository_reconnaissance` | full priority table above |
| G | **the same dogfood prompt, everything supplied** | `chat` | `direct_context_only` | direct context only |
| H | repository plus current external guidance | `commander` | `mixed_sources` | repository + `current_external_authority` |
| I | explicit Project Evolution | `project_evolution` | `broad_repository_reconnaissance` | repository evidence, zero execution authority |
| J | "why does `tests/test_indexer.py` fail?" | `instant_run` | `bounded_repository` | **validation primary** |
| K | WAITER.1 not routed | — | — | no requirements |
| L | tampered source fingerprints | — | — | rejected |
| M | a requirement outside the envelope | — | — | rejected |
| N | evidence needs cannot change the workflow | — | — | structural |
| O | Vietnamese equivalents | same as English | same | byte-identical |

F and G are the same prompt with the same rubric. Only what INPUT recorded as
needed differs — which is what proves both the route and the evidence
requirements depend on capability needs rather than on the word "compare".

## Limits

- **Validation-artifact detection is lexical and narrow.** It reads the paths and
  subjects INPUT.1 preserved, not the repository. An order about tests that names
  no test-shaped path — "why is the suite red?" — will not raise validation
  artifacts to primary. Widening this belongs in INPUT's representation, not in a
  heuristic here.
- **`direct_context` is required on every contract.** The preserved order is
  always material the work reasons over, and acquiring it is not an action anyone
  has to take. It therefore costs no capability and can never be the thing that
  widens an envelope.
- **Roles are stated, sources are not.** `architecture_description` says
  "authoritative description of the architecture"; it does not say which document
  is one. Deciding that is acquisition, and acquisition is the next phase.
- **`hypothesis_support` is in the vocabulary and not yet emitted.** No upstream
  record represents runtime or performance observations, so there is nothing for
  the role to attach to. It is present because the role exists as a distinct way
  of *using* evidence, not because a rule needs it today.
- **Everything downstream of the contract is only as good as the contract.** If
  INPUT.2 records `repository_inspection_required=false` on work that genuinely
  needs the repository, WAITER.1 routes chat and WAITER.2 asks for direct context
  only — correctly, given what it was told. The fix belongs in INPUT.

## Not wired

Nothing calls `derive_evidence_requirements` in a live path. CTX.SELECT, the
Canonical Graph, the Activation Graph, the indexer, the repository manifest, web
search, the planner, Instant Run, Commander, Project Evolution, Dream, the
Unified Workbench and Mixed Mode are all untouched — and a test walks the
repository sources to assert that no caller exists outside the tests.

INPUT.1–3 and WAITER.1 modules were not modified. WAITER.2 is built entirely
around their public contracts.

## Closed and frozen

As of the 2026-08-24 closure check, WAITER.2 is **CLOSED / FROZEN**. The
capability relationship with WAITER.1 is faithful in both directions — not wider,
and not narrower where evidence is required — and both halves are covered by
regression tests over every fixture in the matrix.

`core/evidence_requirements.py`, `core/evidence_policy.py` and
`core/waiter_evidence.py` are listed in ACQUIRE.1's `forbidden_files`. Downstream
phases build on WAITER.2's public contract and do not edit it.
