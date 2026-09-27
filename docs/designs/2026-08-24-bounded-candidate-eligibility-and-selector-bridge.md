# ACQUIRE.2 — Bounded Candidate Eligibility & Selector Bridge

Date: 2026-08-24
Status: complete
Prerequisite: ACQUIRE.1 (frozen)
Next: ACQUIRE.3 — bounded content acquisition and unverified source receipts

## Decision

ACQUIRE.1 wrote a shopping list in classes and ceilings. ACQUIRE.2 answers the
next question and only that one:

> Given a valid bounded acquisition request and an already-authorized candidate
> inventory, which concrete candidates are **eligible** to be considered by the
> existing selector machinery?

It never answers *read these*, *these prove it*, or *run CTX.SELECT against the
live repository*.

```
INPUT.1 preserve → INPUT.2 understand → INPUT.3 complete
   ↓
WAITER.1 workflow → WAITER.2 evidence requirements
   ↓
ACQUIRE.1 bounded abstract acquisition request
   ↓
ACQUIRE.2 bounded candidate eligibility envelope
   ↓
STOP
```

## The distinction the whole phase exists to keep

> A **candidate** may satisfy an acquisition request.
> **Evidence** has been acquired and can support a claim.

ACQUIRE.2 outputs candidates. Never evidence. Every candidate serialises:

```
content_read:      false
evidence_status:   not_acquired
authority_status:  expected_not_verified
```

There is no value in the vocabulary that says otherwise, so no code path can
produce one. This is the third DeepSeek dogfood failure — *a file that was
found being treated as a fact that was checked* — made unrepresentable.

## Precheck: what CTX.SELECT.1 already provides

Inspected before writing anything.

| Module | Pure? | Traverses? | Reads content? | Accepts supplied inventory? | Importable without `pathspec`? |
| --- | --- | --- | --- | --- | --- |
| `core/context_selection.py` | yes | no | no | yes — ranked candidates / mappings | **no** |
| `core/file_candidate_selector.py` | yes | no | no | yes — `build_candidate_filename_report`, `rank_candidates` | **no** |
| `core/file_actionability.py` | yes | no | no | yes | **no** |
| `core/file_capabilities.py` | yes | no | no | yes — `classify_file_capability`, `capability_from_repository_entry` | **no** |
| `core/repo_ignore.py` | no | yes | yes (ignore files) | n/a | no |
| `core/repository_inventory.py` | no — **`os.walk`** | **yes** | no | n/a | no |
| `core/repository_path_policy.py` | yes — lexical only | no | no | n/a | **yes** |

The **logic** of CTX.SELECT is pure and already consumes supplied metadata. Its
**import graph** is not: `file_capabilities → repo_ignore → pathspec`, plus the
ignore-file reader and the repository walker.

So, following the phase brief's own instruction — *build a narrow adapter rather
than rewriting CTX.SELECT* — ACQUIRE.2:

- **reuses** `core/repository_path_policy.is_safe_repository_relative_path` (the
  canonical, I/O-free path-shape policy);
- **mirrors** `FileCapability`'s field names so a member converts to the mapping
  CTX.SELECT accepts, with no translation table;
- **does not import** the selector stack, so the whole INPUT→WAITER→ACQUIRE line
  stays importable and stdlib-only;
- **proves** compatibility by test, driving the real
  `build_candidate_filename_report` and `rank_candidates`.

CTX.SELECT was not modified. No second lexical engine, filename ranker, read-set
planner, actionability scorer or patch classifier was written.

## Modules

| Module | Responsibility |
| --- | --- |
| `core/candidate_inventory.py` | The inventory input contract: `InventoryMember`, `CandidateInventory`, the CTX.SELECT capability-mapping bridge in both directions, and the snapshot fingerprint |
| `core/candidate_eligibility.py` | Records and bounded vocabularies: classification bases, ineligibility reasons, `EligibleCandidate`, `ExclusionSummary`, `SelectorEnvelope`, `ExternalCandidateEnvelope`, `CandidateEligibilityReceipt`, authority and guardrails |
| `core/eligibility_policy.py` | Deterministic classification, tier and exclusion enforcement, budget enforcement, ordering, and the monotonicity and selector-output validators |
| `core/evidence_candidate_pool.py` | Orchestration: the acquisition-ready gate, source-integrity gate, inventory gate, and the receipt |

## The inventory input

```
InventoryMember:
    identifier              repository-relative, portable, membership-checked
    size_bytes              int | None      (None means nobody measured it)
    parser_support          supported | partial | unsupported | not_applicable
    read_policy             auto_read_allowed | explicit_human_approval_required
                            | hard_no_auto_read
    repository_contained    bool
    symlink_escape          bool
    generated               bool
    vendor                  bool
    declared_source_class   str | None
    duplicate_of            str | None
```

Every field is metadata somebody upstream established. Nothing here needs the
bytes of a file, an AST, an embedding, a graph or a database.

`as_capability_mapping()` emits exactly the keys CTX.SELECT reads;
`from_capability_mapping()` ingests a `FileCapability.as_dict()` without
importing its module.

**Identity binding.** `CandidateInventory.fingerprint()` is re-derived from the
members rather than believed. A `declared_fingerprint` that disagrees fails the
receipt closed, as does a `repository_identity` that does not match.

**One extra path rejection.** `is_safe_repository_relative_path` is lexical, and
on a platform whose paths are not rooted at `/` it accepts a leading slash. So
`is_acceptable_identifier` refuses a leading separator on top of it. *(This is a
pre-existing quirk of the shared helper, noted under Limits — ACQUIRE.2 defends
against it locally rather than modifying a frozen shared primitive.)*

## Classification: metadata, never inference

| Rule | Class | Basis |
| --- | --- | --- |
| `read_policy = hard_no_auto_read` | `temporary_artifact` | `inventory_hard_exclusion` |
| path segment in `tmp/.tmp/temp/.temp/scratch/tmp_tests` | `temporary_artifact` | `known_temporary_location` |
| `generated = true` | `generated_artifact` | `inventory_generated_marker` |
| segment in `snapshot(s)/__snapshots__`, or `.snap`/`.snapshot` | `snapshot` | `known_snapshot_location` |
| `duplicate_of` set | `duplicate_rendering` | `inventory_duplicate_marker` |
| segment in `test/tests/testing`, or `test_*`/`*_test.` | `validation_test` | `known_test_location` |
| basename in the manifest name set | `dependency_manifest` | `known_manifest_name` |
| basename in the configuration name set | `configuration` | `known_configuration_name` |
| segment in `archive/history/proposals/rejected/superseded/deprecated` | `historical_design_material` | `known_historical_location` |
| parser says code, not vendored, not generated, not a test | `runtime_implementation`, `surrounding_implementation` | `inventory_parser_support` |
| an authorized builder declared it | *(that class)* | `inventory_declared_class` |

**Extension is not authority.** `docs/notes.md` classifies as nothing.
`core/thing.py` with `parser_support = not_applicable` classifies as nothing.
`interface_definition`, `authoritative_architecture_doc` and
`plugin_or_registration_surface` have **no location rule at all** — no directory
name has ever made a document authoritative — and require a declaration.

**A location rule is only ever a demotion or a kind.** A test mistaken for a
test is still a test; a snapshot mistaken for a snapshot is still kept out.
`docs/designs/` is deliberately *absent* from the historical set: a current
design note is not history.

**Vendored code is code somebody else wrote.** It gets no implementation class.

## Unknown is a first-class safe answer

```
identifier: weird/custom/file.xyz
eligible_source_classes: []
classification_status: unknown
```

An unknown member is eligible for no role and cannot discharge a required one.

### The one candidate with no class at all

`Fix the typo 'teh' to 'the' in README.md.` — the user named `README.md`, the
inventory contains it, and *nothing establishes what it is*. Markdown prose is
not implementation authority just because an order pointed at it.

So the candidate is admitted on membership, and claims nothing:

```
identifier:             README.md
target_anchor_match:    true
classification_status:  unknown
eligible_source_classes: []
eligible_roles:         []
satisfies_a_role:       false
content_read:           false
evidence_status:        not_acquired
```

Borrowing the request's classes to fill that gap would be exactly the widening
this phase exists to refuse. An anchor whose kind *is* known —
`tests/test_indexer.py` — carries both `known_test_location` and
`explicit_target_anchor` as its basis.

### Explicit-target closure — frozen

`target_anchor_match=true`, together with the structured
`CANDIDATE_EXPLICIT_TARGET_MATCHED` and `CANDIDATE_INVENTORY_MEMBER` reasons, is
the ACQUIRE.2 representation equivalent to `target_artifact`. It can be reached
only when an identifier explicitly preserved from the user's input matches a
member of the supplied authorized inventory. The same member without the
explicit anchor has no target status; an anchor absent from inventory remains
unmatched and invents no candidate; and exclusions still win before admission.

Target status establishes no source authority, evidence role, content-read
permission, modification permission, architecture meaning, configuration
meaning, or verified-current status. The explicit-target behavior is closed by
regression and **ACQUIRE.2 is CLOSED / FROZEN**.

## Pools, tiers and exclusions

| ACQUIRE.1 | ACQUIRE.2 |
| --- | --- |
| `required_primary` | `active_candidates` |
| `required_secondary` | `secondary_candidates` |
| `deferred` | `deferred_candidates`, acquisition budget **0** |
| `excluded_initially` | never a candidate — `EligibleCandidate` refuses to hold one |

**Deferred is listed, not lost.** A deferred request has an acquisition budget
of zero — that is what deferred *means* — but the pool is still populated under
its own bound (`MAX_DEFERRED_CANDIDATES = 64`), because knowing what was set
aside is the whole value of setting it aside deliberately. Byte ceilings are not
applied to it: nothing about it will be fetched.

**Exclusions win, before anything else.** An anchor the user wrote does not
readmit a snapshot, and neither does a second class the same member carries.

## Budgets

| Ceiling | Behaviour |
| --- | --- |
| `max_candidates` | bounds the eligible pool; overflow is narrowed deterministically |
| `max_per_source_bytes` | a larger member is refused — without opening it |
| `max_total_bytes` | accumulated in selection order; the pool stops when the next member would exceed it |
| `max_initial_sources` | **carried forward untouched** — nothing was acquired, so no source budget was spent |

`source_budget_consumed` is always `0`. Pretending otherwise would let a later
phase believe its allowance had already been drawn down.

**Unknown size → refused from the active pool** (`size_unverifiable`). Documented
and deliberate: assuming a member is small would let an unknown quantity through
a ceiling that exists precisely to stop unknown quantities. It is a per-candidate
refusal, not a whole-request failure — and if it starves a required role, the
receipt says `insufficient_candidates` anyway.

### Ordering, and why it is not alphabetical

1. identifiers the user wrote, first;
2. then **round-robin across the roles the request named**, each role's queue
   ordered by (class priority from the request, canonical identifier).

Pure class-priority ordering starves rare roles: a repository with nine hundred
implementation modules and one architecture document spends the whole ceiling on
modules and reports the architecture unsatisfied — a smaller, quieter version of
the failure this line of phases exists to fix. Round-robin is still
deterministic, still metadata-only, and carries no notion of relevance.

Order is a function of the metadata alone: hand the same members in a different
sequence and the same pool comes out in the same order.

**No relevance ranking of any kind.** No embeddings, no vector search, no
0–100 score, no graph centrality, no language system. CTX.SELECT may rank
*within* the envelope later, using rules it already has.

## No required-role loss

A required role with no confidently eligible candidate is reported:

```
status: insufficient_candidates
unsatisfied_required_roles: [interface_contract, architecture_description,
                             configuration_authority]
```

Widening a classification until the roles come out satisfied is refused. Zero
candidates for a required primary role is a factual result and not a green
light. A `ready` receipt is, by construction, one with no unsatisfied roles.

## The DeepSeek dogfood

Nineteen-member fixture, broad reconnaissance request:

```
status: ready          candidate_limit: 109      candidate_used: 12

active (10)
   supplied_context:<fingerprint>
   core/router.py, core/executor.py, core/indexer.py, core/text_utils.py
   core/phase_registry.py   [runtime + surrounding + plugin_or_registration_surface]
   core/api.pyi             [interface_definition]
   pyproject.toml, requirements.txt   [dependency_manifest]
   docker-compose.yml                 [configuration]
   docs/architecture.md               [authoritative_architecture_doc]

secondary (2)
   tests/test_indexer.py, tests/test_router.py

deferred (1)
   docs/proposals/old-idea.md         budget 0, current authority false

excluded
   source_class_excluded: 4      (bundle.js, a.snap, scratch.txt, README.vi.md)
   classification_unknown: 2     (README.md, weird/thing.xyz)
```

`core/phase_registry.py` satisfies two roles and is counted **once**.

### Anti-6087, at scale

A synthetic inventory of **6,200 members** — implementation, interfaces,
configuration, architecture docs, tests, snapshots, generated bundles, scratch
files, rejected proposals and unrelated assets — produces:

- active repository pool **capped at 96**, `candidate_budget_remaining = 0`;
- no generated, snapshot, temporary or duplicated member anywhere active;
- no historical material active;
- **every required role still covered** (the round-robin);
- `candidate_contents_read = false`.

The regression creates no file, reads no file, and runs in about a second.

## The selector bridge

```
SelectorEnvelope:
    domain, tier
    allowed_candidate_identifiers[]
    allowed_roles[], allowed_source_classes[], excluded_source_classes[]
    candidate_budget_remaining, source_budget_reserved, byte_budget_remaining
    acquisition_request_fingerprint, inventory_fingerprint, repository_identity
    is_read_set: false
    selector_executed: false
```

`validate_selector_output(envelope, identifiers, inventory=…)` returns every
violation found:

`candidate_outside_envelope`, `candidate_in_excluded_source_class`,
`candidate_from_wrong_tier`, `candidate_budget_exceeded`,
`candidate_from_wrong_inventory`, `candidate_repeated`.

**Proved against the real thing.** With the CTX.SELECT dependency graph
installed, the tests drive `build_candidate_filename_report` and
`rank_candidates` over `as_capability_mapping()` output and assert the result is
a subset of the envelope; and when the selector is handed the whole inventory
plus user-named files, it ranks `tests/test_router.py` into a *primary
repository* context and the bridge check catches it. Neither call reads a file.

**The selector is never executed by ACQUIRE.2.** The caller runs whatever it
likes and hands the identifiers back for checking.

**No actionability or patch semantics are inherited.** Editability is about
whether a file may be *changed*, not whether it may be *believed*. There is no
`patch_candidate`, no `write_authority` and no `editability` field anywhere in
the receipt.

## External information

An external request produces an abstract envelope and **zero concrete
candidates** — which is correct, because discovery needs a network capability
this phase does not have:

```
required_role: current_external_authority
allowed_source_classes: [authoritative_external_source]
freshness: current
candidate_budget: 8       source_budget_reserved: 4
concrete_candidates: []
discovery_requires_later_authorized_phase: true
network_called: false
```

No host, address, query, engine or provider — not fields it declines to fill,
fields it does not have.

## Direct context

One candidate, identified by the fingerprint of the record INPUT preserved:

```
identifier: supplied_context:<task contract fingerprint>
```

No content copied, nothing re-parsed. A direct-context order needs **no
inventory at all** — which is what keeps the DeepSeek differential intact one
layer further down.

## Fail closed

| Condition | Status | Inconsistency |
| --- | --- | --- |
| acquisition contract not ready | `not_acquisition_ready` | `acquisition_contract_not_ready` |
| evidence contract does not fingerprint to the request's | `inconsistent_input` | `source_fingerprint_mismatch` |
| repository request, no inventory | `inventory_required` | `inventory_absent` |
| inventory describes another repository | `inconsistent_input` | `inventory_identity_mismatch` |
| declared fingerprint disagrees with the members | `inconsistent_input` | `inventory_fingerprint_mismatch` |
| pool reaches beyond the request | `inconsistent_input` | `eligibility_envelope_widened` |
| required role has no eligible candidate | `insufficient_candidates` | *(none — a factual result)* |

A refused receipt carries no candidates, no envelopes and no exclusions.

## Authority

Every flag false in **every** status, including `ready`:

```
evidence_acquisition_authority      candidate_content_read_authority
repository_read_authority           repository_traversal_authority
repository_write_authority          external_search_authority
web_fetch_authority                 context_selection_execution_authority
selector_bridge_authority           indexing_authority
graph_authority                     retrieval_authority
validation_authority                command_execution_authority
execution_authority                 worker_launch_authority
patch_authority                     planning_authority
routing_authority                   provider_selection_authority
model_selection_authority           dream_authority
project_evolution_authority

human_approval_required = true
```

`selector_bridge_authority = false` is the one worth naming twice: ACQUIRE.2
*produces* a selector envelope, and producing one is not permission to run a
selector against live sources.

## Determinism and static inertness

The modules import no `os`, `subprocess`, `socket`, `requests`, `urllib`,
`pathlib`, `random` or `time`; open no file; and import no walker, ignore
policy, index, manifest, graph or selector. An English broad-analysis order and
its Vietnamese equivalent produce identical eligibility, because none of the
derivation reads words.

## Cross-stage monotonic narrowing

```
ACQUIRE.1 request ceiling  ≥  ACQUIRE.2 eligible pool  ≥  future read set  ≥  actual reads
```

ACQUIRE.2 makes the **first** inequality checkable:
`CandidateEligibilityReceipt` cannot be constructed with `candidate_used`
above `candidate_limit`, and `check_eligibility_monotonicity` rejects a pool
that reaches a domain, tier, class or per-source size the request did not
license.

## Limits

- **Source classes are asserted, not verified.** Nothing here confirms that
  `core/api.pyi` really is an interface definition; it confirms that an
  authorized inventory builder said so. Verification needs content.
- **Declared classes are the only route to three classes.** Without inventory
  declarations, `interface_definition`, `authoritative_architecture_doc` and
  `plugin_or_registration_surface` stay `unknown` and the receipt reports the
  roles unsatisfied. That is the honest failure mode, and it surfaces the gap
  instead of hiding it — but it does mean a bare inventory yields
  `insufficient_candidates` for an architecture survey.
- **`is_safe_repository_relative_path` accepts a leading `/` on Windows.** A
  pre-existing quirk in a shared primitive: `Path('/abs/x').is_absolute()` is
  false where paths are drive-rooted. ACQUIRE.2 rejects leading separators
  itself; the shared helper was not modified, and membership is the real gate
  regardless.
- **A ceiling is a ceiling, not a plan.** 96 candidates is the most a
  reconnaissance pool may offer, not a claim that 96 is the right number.
- **`MAX_DEFERRED_CANDIDATES = 64` is a listing bound**, not an acquisition one.
  A very large deferred set is truncated in the report.
- **The location vocabularies are English-shaped.** `tests/`, `snapshots/`,
  `proposals/` and the manifest names are conventions, not universals.

## Not wired

Nothing calls `derive_candidate_eligibility` in a live path. CTX.SELECT, the
Canonical Graph, the Activation Graph, the indexer, the repository manifest, web
search, the planner, Instant Run, Commander, Project Evolution, Dream, the
Workbench and Mixed Mode are all untouched. A test walks the repository sources
to assert no caller exists outside the tests.
