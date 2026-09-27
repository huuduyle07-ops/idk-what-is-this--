# ACQUIRE.1 — Bounded Evidence Acquisition Request Contract

Date: 2026-08-24
Status: complete
Prerequisite: WAITER.2 (frozen, closed)
Next: enforce one request contract against concrete source candidates, behind its own acquisition authority gate

## Decision

WAITER.2 answered *what evidence will the selected workflow need*. ACQUIRE.1
answers the next question and only that one:

> Given an approved Evidence Requirement Contract, what bounded acquisition
> requests should a future acquisition engine receive?

It never answers *go and acquire the evidence*.

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
ACQUIRE.1 write bounded acquisition requests
   ↓
STOP
```

The kitchen analogy runs one step further:

| Phase | Question |
| --- | --- |
| WAITER.2 | What ingredients are required? |
| **ACQUIRE.1** | **Write the shopping list: which aisles, what kinds, how much at most, what to leave on the shelf.** |
| future | Go to the shop. |

Nobody has been to the shop.

## The failure this phase exists to fix

The DeepSeek Harness dogfood considered roughly **6,087 repository files**.
WAITER.2 fixed the half of that failure that was about *priority*: it stated
which classes of evidence matter first and which are restated material.

It could not fix the other half, because it has no vocabulary for it. "Broad
repository reconnaissance" is a true description of what that task needs, and it
is also exactly the phrase a downstream executor reads as *scan everything*.

ACQUIRE.1 closes that gap by making the unbounded reading unrepresentable:

- a request names which **source classes** it may reach — strictly fewer than
  all of them;
- it carries a **named budget profile** whose numeric ceilings are read out of a
  frozen table;
- it travels beside explicit **exclusions**;
- and `AcquisitionBudget` has exactly one field, so there is nowhere at all to
  write "unlimited".

## Modules

| Module | Responsibility |
| --- | --- |
| `core/acquisition_request.py` | Records and bounded vocabularies: source classes, request scopes, freshness, budget profiles and their ceilings, target anchors, reason codes, statuses, inconsistencies, and the authority and guardrail blocks |
| `core/acquisition_policy.py` | Deterministic derivation — role → source class, domain and tier → ceiling, plus the monotonicity, coverage, deferral and bounded-reconnaissance checks |
| `core/evidence_acquire_request.py` | Orchestration: the evidence-ready gate, the source-integrity gate, the capability-faithfulness gate, and the contract itself |

## What a request is

```
AcquisitionRequest:
    domain                      where the evidence comes from    (WAITER.2 vocabulary)
    required_roles[]            how it may be used               (WAITER.2 vocabulary)
    tier                        what comes first                 (WAITER.2 vocabulary)
    source_classes[]            what kind of thing may satisfy it
    scope                       how far this request reaches
    budget                      a named, finite ceiling
    freshness                   how current the source must be
    require_current_authority   an expectation, not a verdict
    target_anchors[]            identifiers the *user* wrote
    reasons[]                   the structured facts it came from
```

There is no `path`, no `candidates`, no `query`, no `host`, no `provider`, no
`stage` and no `depends_on`. Those are not fields ACQUIRE.1 declines to fill;
they are fields it does not have.

## Source classes are selectors, not filenames

**11 requestable classes**: `supplied_context`, `runtime_implementation`,
`surrounding_implementation`, `interface_definition`, `configuration`,
`dependency_manifest`, `authoritative_architecture_doc`,
`plugin_or_registration_surface`, `validation_test`,
`historical_design_material`, `authoritative_external_source`.

**4 classes that can only ever be excluded**: `generated_artifact`, `snapshot`,
`temporary_artifact`, `duplicate_rendering`. `AcquisitionRequest` refuses to
name one, so *"request the snapshots"* is not a sentence this schema can form.

`target_artifact` and `runtime_observation` were considered and not created: an
explicitly named artifact is carried as a target anchor instead, and no upstream
role licenses observing a running system.

## Role → source class

Total over WAITER.2's frozen role vocabulary, checked at import.

| Role | Source classes |
| --- | --- |
| `supplied_material` | `supplied_context` |
| `implementation_authority` | `runtime_implementation`, `surrounding_implementation` |
| `interface_contract` | `interface_definition` |
| `configuration_authority` | `configuration`, `dependency_manifest` |
| `architecture_description` | `authoritative_architecture_doc`, `plugin_or_registration_surface` |
| `validation_evidence` | `validation_test` |
| `hypothesis_support` | *(none — fails closed)* |
| `historical_context` | `historical_design_material` |
| `current_external_authority` | `authoritative_external_source` |

`hypothesis_support` maps to nothing on purpose. A hypothesis is something a
reader forms about evidence, not a class of source anyone can go and find.
WAITER.2 never derives it; were it ever required, the honest answer is that this
vocabulary cannot express the request — so the contract fails closed with
`unmappable_evidence_role` rather than inventing a class.

## Budgets

A budget is a **name**. The numbers are the whole of what a name means, and a
caller cannot supply its own.

| Profile | `max_candidates` | `max_initial_sources` | `max_total_bytes` | `max_per_source_bytes` |
| --- | --- | --- | --- | --- |
| `none` | 0 | 0 | 0 | 0 |
| `existing_context` | 1 | 1 | 65,536 | 65,536 |
| `external_bounded` | 8 | 4 | 262,144 | 65,536 |
| `secondary_verification` | 12 | 4 | 262,144 | 131,072 |
| `bounded` | 24 | 8 | 524,288 | 131,072 |
| `reconnaissance` | **96** | **32** | 2,097,152 | 131,072 |

Documented ceilings: **96 candidates, 32 initial sources, 2 MiB total, 128 KiB
per source.** Every profile sits at or under them, and the module refuses to
import if one does not.

Not one number is derived from how many files the repository holds, how much
memory the machine has, or anything else that differs between two runs.

### Which profile, and why

The ceiling follows **domain, tier and reach** — never the workflow.

```
tier is deferred or excluded        -> none
direct_context                      -> existing_context
external_information                -> external_bounded
required_secondary                  -> secondary_verification
broad_repository_reconnaissance     -> reconnaissance
otherwise                           -> bounded
```

`COMMANDER` is not a budget. The DeepSeek rubric run over supplied context alone
routes to CHAT and asks for a single existing-context reference; the same rubric
run over the repository routes to COMMANDER and asks for a bounded
reconnaissance. Nothing in the derivation reads the selected workflow at all.

The ladder is the policy: existing context is a reference to what is already
here, a secondary check is smaller than the primary evidence it checks, and
broad reconnaissance is larger than a bounded operation and still finite.

## Tiers survive translation

| WAITER.2 tier | ACQUIRE.1 |
| --- | --- |
| `required_primary` | initial request |
| `required_secondary` | smaller request |
| `deferred` | request in `deferred_requests`, budget `none` |
| `excluded_initially` | exclusion — never a request |

Enforced structurally, not by convention:

- a request at an active tier with an inactive budget cannot be constructed;
- a deferred request with an active budget cannot be constructed;
- `tier=excluded_initially` cannot be a request at all.

"Deferred, with a reconnaissance budget" is the shape of a promotion, so the
record refuses to hold it.

## Broad is not everything

`check_bounded_reconnaissance` refuses a request set in which a broad request

- has no active budget, **or**
- names every requestable class, **or**
- travels without exclusions.

For the dogfood, the broad request names 7 of the 11 requestable classes;
`validation_test` and `historical_design_material` are deliberately *not* among
them, because they belong to other requests at other tiers.

## The DeepSeek dogfood request set

```
workflow:        commander
evidence_scope:  broad_repository_reconnaissance

requests
  direct_context / required_primary
      supplied_context
      existing_context (1 candidate)
  repository / required_primary
      runtime_implementation, surrounding_implementation,
      interface_definition, configuration, dependency_manifest,
      authoritative_architecture_doc, plugin_or_registration_surface
      reconnaissance (96 candidates, 32 initial sources)
  validation_artifacts / required_secondary
      validation_test
      secondary_verification (12 candidates)

deferred_requests
  historical_context / deferred
      historical_design_material
      none (0 candidates)

exclusions
  generated_artifact     excluded_initially
  snapshot               excluded_initially
  temporary_artifact     excluded_initially
  duplicate_rendering    deferred
```

No filename. No path. No query. Total active candidate ceiling: **109**.

## Monotonic in both directions

This is the invariant pair inherited from WAITER.2 and extended.

**No widening** (`check_request_monotonicity`): a request whose domain the
contract never named, a role at a tier other than its own, or a class the
contract excluded all produce `acquisition_requirement_widened`.

**No required loss** (`check_requirement_coverage`): every requirement must have
**exactly one** request carrying it, at its own tier, with a budget that permits
the work and at least one source class; an external requirement must keep its
`current` freshness expectation. Otherwise: `required_evidence_dropped`.

**No forgotten deferral** (`check_deferred_source_coverage`): every class
WAITER.2 pushed back is accounted for. Four have acquisition counterparts and
appear as exclusions with the disposition they were given. The fifth,
`unrelated_validation_artifacts`, has none — it is not a kind of source, a test
is a test — so it appears as a smaller ceiling and an explicit
`ACQUIRE_UNRELATED_VALIDATION_DEFERRED` reason on the validation request. The
mapping table is total over WAITER.2's deferred classes and checked at import.

## Explicit target anchors

For `Fix the typo 'teh' to 'the' in README.md.`:

```
target_anchors: [
  { value: "README.md",
    source: "explicit_input_evidence",
    discovered: false,
    existence_verified: false }
]
```

The anchor comes from `TaskContract.explicit_evidence.file_paths` — what INPUT.1
preserved from what the user wrote. ACQUIRE.1 has no way to discover a path, and
the anchor asserts nothing about whether the thing exists, can be read, can be
written, or is safe to reach. A future acquisition phase establishes all of
that for itself.

Anchors attach to the validation request when the order is about validation
artifacts (`tests/test_indexer.py` on a failing-test investigation), and to the
repository request otherwise.

## Freshness

Three values: `not_applicable` (material already in hand), `current` (repository,
validation and external sources), `historical` (deferred design material).

`recent` and `stable_reference` were considered and not created: upstream states
no fact that could produce either, and a value nothing can reach is decoration
rather than honesty. No day count appears anywhere, because nobody upstream
supplied one.

## No planning

There is no `depends_on`, no `stage`, no `step`, no `sequence` and no `after`
anywhere in the schema. Requests are independent. Priority tiers are evidence
priority, not an execution order, and a regression asserts none of those words
appears in a rendered contract.

## Fail closed

| Condition | Status | Inconsistency |
| --- | --- | --- |
| evidence contract not `specified` | `not_evidence_ready` | `evidence_contract_not_specified` |
| WAITER.1 decision not routed | `inconsistent_input` | `waiter_decision_not_routed` |
| evidence workflow ≠ routed workflow | `inconsistent_input` | `workflow_mismatch` |
| any of four fingerprints disagree | `inconsistent_input` | `source_fingerprint_mismatch` |
| requirement outside the envelope | `inconsistent_input` | `capability_envelope_widened` |
| required capability not represented | `inconsistent_input` | `required_capability_dropped` |
| role with no source class | `inconsistent_input` | `unmappable_evidence_role` |
| request wider than its requirement | `inconsistent_input` | `acquisition_requirement_widened` |
| requirement with no request | `inconsistent_input` | `required_evidence_dropped` |

A refused contract carries no requests, no deferred requests and no exclusions:
guessing what an unspecified contract would need is exactly the kind of
helpfulness this layer exists to refuse.

## Fingerprint and source binding

Four fingerprints, re-derived rather than believed: the task contract, the
completion decision, the routing decision, and the evidence contract's own
identity. Tampering with any upstream record invalidates the request set instead
of quietly producing requests for a different order. No timestamp and no random
identifier appears anywhere.

## Authority

Every flag is false in **every** status, including `ready`:

```
evidence_acquisition_authority     repository_read_authority
repository_traversal_authority     repository_write_authority
external_search_authority          web_fetch_authority
context_selection_authority        indexing_authority
graph_authority                    retrieval_authority
validation_authority               command_execution_authority
execution_authority                worker_launch_authority
patch_authority                    planning_authority
routing_authority                  provider_selection_authority
model_selection_authority          dream_authority
project_evolution_authority

human_approval_required = true
```

`status = ready` says the request set is well formed. It says nothing else.

## No model, no provider, no compute

The record has no field for a provider, a model, local or cloud, a context
window, a temperature, an endpoint, an API key or a fallback chain. ACQUIRE.1
asks for evidence **sources**, not compute resources.

## Determinism and static inertness

The modules import no `os`, `subprocess`, `socket`, `requests`, `urllib`,
`pathlib`, `random` or `time`, open no file, and import no selector, index,
manifest or graph. An English broad-analysis order and its Vietnamese equivalent
produce identical acquisition contracts, because none of the derivation reads
words.

## Request matrix, as tested

| Order | Workflow | Requests | Ceiling |
| --- | --- | --- | --- |
| explain a concept | chat | direct context only | 1 |
| pasted comparison | chat | direct context only | 1 |
| README typo | instant_run | + bounded repository (anchor `README.md`), secondary validation | 37 |
| one-file implementation | instant_run | + bounded repository (anchor `core/text_utils.py`) | 37 |
| broad indexing investigation | commander | + reconnaissance, secondary validation, deferred history | 109 |
| DeepSeek dogfood (repository) | commander | as above | 109 |
| DeepSeek dogfood (supplied) | chat | direct context only | 1 |
| current external lookup | chat | + external authority, `current` | 9 |
| supplied material + external | chat | direct context + external | 9 |
| repository + external | commander | + reconnaissance + external | 117 |
| failing-test investigation | instant_run | validation **primary** (anchor `tests/test_indexer.py`) | 49 |
| project evolution | project_evolution | reconnaissance, bounded per cycle | 109 |

## Limits

- **Source classes are unenforced here.** Nothing checks that a real repository
  member is of the class a request names; that is the next phase's job, under
  its own gate.
- **A ceiling is a ceiling, not a plan.** 96 candidates is the most a
  reconnaissance request may consider, not a promise that 96 will be used or
  that 96 is the right number for any particular repository.
- **Anchors are unverified.** `README.md` in a request means the user typed it,
  and nothing more.
- **`unrelated_validation_artifacts` is coarse.** It becomes a smaller ceiling
  and a reason code, not a relevance test — a relevance test needs evidence, and
  there is none yet.
- **`hypothesis_support` is unreachable.** WAITER.2 never derives it, so the
  fail-closed path exists and is exercised only by a hand-built contract.

## Not wired

Nothing calls `derive_acquisition_requests` in a live path. CTX.SELECT, the
Canonical Graph, the Activation Graph, the indexer, the repository manifest, web
search, the browser, the planner, Instant Run, Commander, Project Evolution,
Dream, the Workbench and Mixed Mode are all untouched. A test walks the
repository sources to assert no caller exists outside the tests.
