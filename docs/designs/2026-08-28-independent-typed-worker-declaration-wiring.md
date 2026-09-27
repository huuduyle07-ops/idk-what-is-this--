# CHECK.LIVE.1B — Independent Typed Worker Declaration Wiring

**Status:** complete, shadow-only, default off
**Date:** 2026-08-28
**Depends on:** CHECK.LIVE.1 (complete). Not CHECK.2. Not CHECK.LIVE.2's semantic slice.

## The question this phase answers

CHECK.LIVE.1's own design doc names its most important limitation:

> "The live worker report cannot lie about paths. The declaration and the
> authorization are both derived from the same patch plan, so an
> undeclared-but-authorized change is structurally unreachable through the
> wired path today."

So the open question is:

> Can CHECK.1's declared-vs-observed comparison become a real independent
> measurement, instead of comparing a fact against a re-derivation of itself?

## The defect, exactly

`WorkerReport.declared_changes` is built by
[`declared_changes_from_patch_plan`](../../core/live_worker_report.py) walking
`observation.plan`. That `plan` is the *same* list `run_lifecycle.py` hands to
`apply_patch_plan` — not `applied_ops`, not anything sourced from a model
response. Tracing the full chain:

```text
run_patch_plan_with_artifacts(project_root, plan, ...)
    → LiveExecutionObservation(plan=plan, ...)          # the same list, unfiltered by success
    → declared_changes_from_patch_plan(observation.plan)
    → WorkerReport.declared_changes
```

`ExecutionAuthorization`'s authorized paths are *also* derived from this same
plan's target paths (via `evaluate_patch_safety`). Two of CHECK.1's three
independent inputs currently trace back to one list. Declared-vs-observed is
not yet a cross-check; it is closer to a tautology with a rollback-shaped
escape hatch.

## The true worker output boundary, as it actually is

Traced before anything was written, across `agents/gemini_client.py`,
`agents/ollama_client.py`, `core/semantic_waiter_adapter.py`,
`core/executor.py`, `patching/patch_plan_executor.py`, and
`core/worker_result_review.py`:

- The model call that drafts a patch (`agents/gemini_client.py ::
  run_gemini_request`) returns a bare `response.text` string. No structured
  field, no JSON mode, nothing beyond prose that later gets mechanically
  parsed into patch ops.
- The only place in the repository a model is asked for validated, schema-checked
  JSON is `core/semantic_waiter_adapter.py` — and that is intake-side
  (interpreting the user's request), architecturally upstream of and
  disconnected from patch execution.
- The only place free-text worker output is read after the fact is
  `core/worker_result_review.py`, which mines it with a path-looking-string
  regex and explicitly treats it as "untrusted evidence until a human reviews
  it" — precisely the prose-heuristic reader `core/live_worker_report.py`'s
  own docstring refuses to become.

**Conclusion: no independent, structured "what the worker believes it did"
channel exists anywhere in this codebase today.** Building one for real would
mean changing the prompt/response contract of the patch-drafting model call —
which lives in `agents/`, `patching/`, `core/pipeline.py`,
`core/self_correct_loop.py`, `core/executor.py` — every one of which
CHECK.LIVE.1 already places in its own `forbidden_files`, and none of which
this phase's `allowed_files` will include either.

Per the phase brief's own instruction for this situation: don't fabricate an
automatic production source, and record the honest state. This phase reads
that as "don't invent a fake **production producer**" — not "build nothing."
The distinction below is the crux of the design.

## What this phase builds anyway, and why that is still honest

CHECK.1's own reconciliation core (frozen) accepts a `WorkerReport` value
without caring where it came from — tests already construct one directly,
the same way they construct `LiveExecutionObservation` and
`ExecutionAuthorization` values directly, without a live model in the loop.
CHECK.LIVE.1B builds the same kind of seam one level lower: a typed
`WorkerChangeDeclaration` contract plus the wiring that lets `WorkerReport`
be built from one when a caller supplies it, instead of from the patch plan.

That seam is real, typed, bounded, tested end-to-end through the actual live
producer path, and structurally incapable of being derived from the patch
plan or the observed facts (enforced by a boundary test, not by convention).
What is *not* real yet is a production caller on the other side of that seam
— nothing in `core/pipeline.py` or `core/self_correct_loop.py` constructs a
`WorkerChangeDeclaration` today, because doing so needs the worker-protocol
change this phase deliberately does not make.

So: in dogfood today, every live run reports
`worker_declaration_source = legacy_plan_derived`, honestly, every time. What
changes is that this is now a *recorded, measured* fact instead of an
structurally-unavoidable one — and the moment a future phase wires a real
producer through this exact seam, `independent_worker_declaration` starts
appearing with zero further change to CHECK.LIVE.1B's own code.

## Architecture

```text
worker execution
    ├── executable patch operations ─────────────┐
    │       ↓                                     │
    │    patch executor (unchanged)                │
    │                                               │
    └── typed WorkerChangeDeclaration               │
        (supplied by a caller; none exists yet)     │
            ↓                     ↓                 │
      [independent path]   [no declaration supplied]│
            ↓                     ↓                 ↓
   declared_changes_from_    declared_changes_from_patch_plan
   worker_declaration()      (existing CHECK.LIVE.1 behaviour, unchanged)
            └───────────┬───────────┘
                         ↓
                   WorkerReport
                         +
              ObservedPostRunFacts  (unchanged, from live_change_observation.py)
                         ↓
                  frozen CHECK.1
                         ↓
           ShadowPostRunCheckReceipt
      (+ worker_declaration_source, worker_declaration_invalid)
```

`ExecutionAuthorization` and `ObservedPostRunFacts` are untouched — this phase
closes exactly one edge (`plan → declared_changes`), not the whole graph.

## New module — `core/live_worker_declaration.py`

A new `live_*` producer, following the exact house style of
`live_execution_authorization.py` / `live_validation_receipt.py`.

```python
PHASE_ID = "CHECK.LIVE.1B"
PRODUCER_KIND = "live_worker_declaration"

DECLARATION_STAGE_COMPLETED = "completed"   # the only stage this contract accepts

#: Sentinel for "the worker did not independently know the kind" — never
#: guessed, never copied from the plan or from observation.
CHANGE_KIND_UNAVAILABLE_CLAIM = "change_kind_unavailable"

DECLARATION_SOURCE_INDEPENDENT = "independent_worker_declaration"
DECLARATION_SOURCE_LEGACY_PLAN_DERIVED = "legacy_plan_derived"
DECLARATION_SOURCE_UNAVAILABLE = "unavailable"
```

```python
@dataclass(frozen=True, slots=True)
class DeclaredChangeClaim:
    path: str
    change_kind: str                 # CHANGE_KINDS ∪ {CHANGE_KIND_UNAVAILABLE_CLAIM}
    from_path: str | None = None     # required iff change_kind == "renamed"
    # Deliberately NO expected_change_identity_sha256 / content digest field:
    # a real hash here would re-couple the declaration to observation.

@dataclass(frozen=True, slots=True)
class WorkerChangeDeclaration:
    declaration_id: str
    execution_run_id: str
    worker_id: str | None
    declaration_stage: str                                    # must be "completed"
    declared_status: str                                      # WORKER_STATUS_CLAIMS (reused)
    declared_changes: tuple[DeclaredChangeClaim, ...] = ()     # unique by path, bounded
    declared_validation_actions: tuple[DeclaredValidationAction, ...] = ()  # reused type
    limitations: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()
    schema_version: str = WORKER_CHANGE_DECLARATION_SCHEMA_VERSION
```

Bounds reuse CHECK.1's own constants by import
(`MAX_DECLARED_CHANGES`, `MAX_DECLARED_VALIDATION_ACTIONS`, `MAX_LIMITATIONS`,
`MAX_UNRESOLVED_ITEMS`, `MAX_IDENTIFIER_CHARS`, `MAX_TEXT_CHARS`), and paths are
validated through the same frozen `repository_path_policy` gate CHECK.1
itself uses — so bounds don't drift between the two.

`declared_validation_actions` reuses CHECK.1's own `DeclaredValidationAction`
type directly rather than inventing a parallel one: reusing a *shape* is not
reusing a *data source*, and every existing `live_*` producer already
assembles CHECK.1's frozen record types from independently-sourced facts.
`declared_changes` cannot reuse `DeclaredChange` directly, because
`DeclaredChange.__post_init__` rejects any `change_kind` outside the four real
kinds — there is no way to represent "unknown" in it. That is exactly why
`DeclaredChangeClaim` exists as its own type with one extra sentinel value.

`WorkerChangeDeclaration.__post_init__` rejects a duplicate path in
`declared_changes` outright (raises), rather than silently last-wins
deduplicating the way the patch-plan translator must (that translator dedupes
because a mechanical op list can legitimately name a path twice; a
purpose-built declaration claiming the same path twice with two different
kinds is a malformed declaration, not a legitimate ambiguity to paper over).

Two more functions complete the module:

- `worker_change_declaration_fingerprint(declaration)` — sha256 over canonical
  JSON, `type(x) is WorkerChangeDeclaration` exact-type check, mirroring
  `worker_report_fingerprint`. (The phase brief describes a
  `declaration_fingerprint` *field*; this phase implements it as a derived
  function instead, matching how every other fingerprint in this codebase
  works — a self-referential hash stored as a field of the same frozen object
  is not a pattern used anywhere else here, and introducing one would be
  needless divergence.)
- `worker_change_declaration_from_mapping(raw)` — a strict, allow-listed
  mapping→dataclass validator (unknown keys rejected, authority-claiming keys
  like `write_authority`/`patch_authority` explicitly rejected, exactly the
  `semantic_waiter_adapter.py` pattern) for a future caller that hands in
  already-structured data — e.g. JSON-decoded model output — without this
  phase ever parsing prose. Raises `LiveWorkerDeclarationInputError` (matching
  the existing `LiveWorkerReportInputError` / `LiveAuthorityInputError` /
  `LiveValidationInputError` naming convention) on any malformed input —
  including a duplicate-path `WorkerChangeDeclaration` construction failure,
  which it catches and re-wraps rather than letting a bare `ValueError`
  escape; never guesses a field into existence.
- `worker_declaration_authority()` → `{write_authority: False, patch_authority:
  False, validation_authority: False, observed_fact_authority: False,
  worker_self_report_authority: True}`.
- `worker_declaration_guardrails()` → every power declined, matching the
  sibling modules' `*_guardrails()` shape (`derived_from_patch_plan: False`,
  `derived_from_execution_authorization: False`,
  `derived_from_observed_facts: False`, `prose_parsed: False`, `model_called:
  False`, ... `human_approval_required: True`).

### Structural independence, enforced not just asserted

A boundary test asserts `core/live_worker_declaration.py`'s own source never
imports from `core.live_execution_authorization`,
`core.post_run_reconciliation_shadow`, `core.live_change_observation`'s
observation types, or `patching.*`, and never references
`patch_plan`/`ExecutionAuthorization`/`ObservedPostRunFacts` by name — mirroring
the existing style of `tests/test_post_run_reconciliation_shadow_boundaries.py`.

## Extending `core/live_worker_report.py`

Three new pure functions alongside the existing patch-plan-derived ones
(nothing existing is modified or removed):

```python
def declared_changes_from_worker_declaration(
    declaration: WorkerChangeDeclaration,
) -> tuple[tuple[DeclaredChange, ...], tuple[str, ...]]:
    """Mirrors declared_changes_from_patch_plan's return shape exactly."""

def declared_status_from_worker_declaration(declaration) -> str: ...
def declared_validation_actions_from_worker_declaration(declaration) -> tuple[DeclaredValidationAction, ...]: ...
```

A claim whose `change_kind` is `CHANGE_KIND_UNAVAILABLE_CLAIM` never becomes a
`DeclaredChange`; its path is recorded in the same `untranslated` bucket the
patch-plan path already uses, surfacing as the existing
`typed_worker_fact_unavailable` missing-fact code. No new missing-fact
vocabulary is needed for this — it means the same thing structurally in
either source.

`build_live_worker_report`'s signature is **unchanged** — it already takes
already-derived `declared_changes`/`declared_status`/
`declared_validation_actions` as plain arguments, so which producer function
built them is entirely the caller's decision. That caller is
`post_run_reconciliation_shadow.py`.

## Extending `core/post_run_reconciliation_shadow.py`

`LiveExecutionObservation` gains one new field:

```python
worker_declaration: WorkerChangeDeclaration | Mapping[str, Any] | None = None
```

Accepting either an already-built `WorkerChangeDeclaration` or a raw
`Mapping` lets a future producer hand in either a Python value (tests, or an
in-process caller) or JSON-decoded structured data (a future model-adapter
producer) — through the *same* strict validator, never through prose parsing.

Inside `run_shadow_post_run_reconciliation`, the existing worker-report block
(current lines 733–756) becomes a source selection:

```python
declaration, worker_declaration_invalid = _resolve_worker_declaration(
    observation.worker_declaration
)
if declaration is not None:
    declared_changes, untranslated = declared_changes_from_worker_declaration(declaration)
    declared_status = declared_status_from_worker_declaration(declaration)
    declared_validation_actions = declared_validation_actions_from_worker_declaration(declaration)
    worker_declaration_source = DECLARATION_SOURCE_INDEPENDENT
else:
    declared_changes, untranslated = declared_changes_from_patch_plan(observation.plan)
    declared_status = declared_status_from_apply_outcome(...)          # unchanged
    action = declared_validation_action(...)                            # unchanged
    declared_validation_actions = () if action is None else (action,)
    worker_declaration_source = (
        DECLARATION_SOURCE_LEGACY_PLAN_DERIVED if observation.plan
        else DECLARATION_SOURCE_UNAVAILABLE
    )
```

`_resolve_worker_declaration`:

- `None` in → `(None, False)` — nothing was attempted; the caller preserved
  exactly today's behaviour.
- a `WorkerChangeDeclaration` in → `(that value, False)` — already valid by
  construction (frozen dataclass, validated in `__post_init__`).
- a `Mapping` in → attempt `worker_change_declaration_from_mapping`; on
  success `(declaration, False)`; on `LiveWorkerDeclarationInputError`,
  `(None, True)` — falls through to the legacy path below, but the failure is
  recorded, never silently absorbed into "everything matched."

This is the one behavioural branch point in the whole phase. Everything
downstream of it (fingerprints, `PostRunReconciliationRequest`,
`reconcile_post_run`) is unchanged — CHECK.1 already accepts any well-formed
`WorkerReport` regardless of how it was built.

`ShadowPostRunCheckReceipt` gains two fields:

```python
worker_declaration_source: str | None = None    # None only on not-reached / checker-error receipts
worker_declaration_invalid: bool = False
```

plus a computed property:

```python
@property
def independent_worker_declaration_missing(self) -> bool:
    return self.worker_declaration_source != DECLARATION_SOURCE_INDEPENDENT
```

Both fields (and the property) are added to `as_dict()`. `result_metadata()`
— the minimal keys copied onto the authoritative run's own result dict — is
**not** touched, to avoid widening an existing, already-tested surface for a
shadow-only, dogfood-facing detail.

`summarize_shadow_post_run_checks` gains one more tally
(`worker_declaration_source_counts`) and one more count
(`worker_declaration_invalid_runs`), following the exact pattern of every
other counter already in that function. This is what makes §36's dogfood
question answerable: *of the runs with a receipt, how many actually measured
independent self-report fidelity, versus fell back, versus supplied something
invalid?*

## Extending `core/run_lifecycle.py`

One new optional keyword parameter threaded end to end, default `None`,
fully backward compatible:

```python
def run_patch_plan_with_artifacts(
    project_root: str,
    plan: list[dict],
    validation_command: str | None = None,
    safe_validation_command: SafeValidationCommand | None = None,
    require_safe_validation: bool = False,
    user_query: str = "",
    control_result: dict[str, Any] | None = None,
    source: str = "pipeline",
    worker_declaration: Any = None,          # new
) -> dict[str, Any]:
```

passed straight through `_attach_shadow_post_run_reconciliation(...,
worker_declaration=worker_declaration)` into
`LiveExecutionObservation(worker_declaration=worker_declaration, ...)`. No
existing call site changes behaviour, because no existing call site passes
this argument.

## Persistence — `core/replay_recorder.py`

No new artifact file. `worker_declaration_source` and
`worker_declaration_invalid` already ride inside the existing
`post_run_reconciliation_shadow.json` receipt (the same additive artifact
CHECK.LIVE.1 introduced) — there is nothing about them that needs a second
file. A bundle written before this phase loads exactly as it does today
(`load_shadow_post_run_check` already defaults missing keys sanely via
`payload.setdefault`/`.get`, which this phase extends the same way for the
two new keys, defaulting to `None`/`False`).

## Required live regressions

All of these call the real `run_patch_plan_with_artifacts` (or
`run_shadow_post_run_reconciliation` directly with a hand-built
`LiveExecutionObservation`, which is itself how every existing CHECK.LIVE.1
regression already works) — never a hand-built `WorkerReport`.

| # | Scenario | Declaration | Plan / actual | Expected |
|---|---|---|---|---|
| Omission | declares A only | ops touch A + B, both actually change | `B` → `undeclared_change`, shadow `suspicious`/`blocked` per frozen CHECK.1 policy |
| Overclaim | declares A + B | plan/actual only touch A | `B` → `declared_but_unobserved_change` |
| Exact agreement | declares A | ops touch A, actual A changes | `matched` — proves independence doesn't force disagreement |
| Forbidden honesty | declares a forbidden path, honestly | that path is objectively forbidden and objectively changed | still `blocked` — declaring it changes nothing about authority |
| Declaration invalid | malformed mapping (bad `change_kind`, unknown key) | any | run completes normally; `worker_declaration_source = legacy_plan_derived`; `worker_declaration_invalid = True` |

**Kind-mismatch (§24)** is investigated but not guaranteed representable: the
live patch executor's op table (`create_file` → added, `replace_snippet` →
modified) has no delete/rename op, so there is currently no way to make the
*actual observed* side of a real `run_patch_plan_with_artifacts` call produce
a `deleted` or `renamed` change kind. If confirmed unreachable through the
live executor during implementation, this regression is exercised one layer
down — directly against `run_shadow_post_run_reconciliation` with a
hand-built `LiveExecutionObservation` whose `pre_apply_digests` already
reflect a pre-existing file and whose plan/side-effects omit it (so
`derive_observed_change_records` — the real, unmodified CHECK.LIVE.1
observation function — reports `deleted` on its own) — still the real
producer chain, just without the full patch-executor round trip. This is
documented as a known limitation either way, not silently worked around.

Plus: model-call / validation-execution / repository-traversal /
patch-application count deltas, all asserted at zero against an instrumented
baseline, exactly as CHECK.LIVE.1's own boundary suite already does.

## Registry

New entry `CHECK.LIVE.1B` in `docs/roadmap/phase_registry.json`:

- `track: "CHECK"`, `prerequisites: ["CHECK.LIVE.1"]`, `risk_level: "medium"`
  (same as CHECK.LIVE.1 — it's still live-integration, still shadow-only).
- `allowed_files`: `core/live_worker_declaration.py`,
  `core/live_worker_report.py`, `core/post_run_reconciliation_shadow.py`,
  `core/run_lifecycle.py`, `tests/test_live_worker_declaration.py`,
  `tests/test_post_run_reconciliation_shadow.py`,
  `tests/test_post_run_reconciliation_shadow_boundaries.py`,
  `tests/test_post_run_reconciliation_boundaries.py`,
  `tests/test_phase_registry.py`, `tests/test_phase_picker.py`, this design
  doc, `docs/roadmap/phase_registry.json`.
- `forbidden_files`: everything CHECK.LIVE.1 already forbids (frozen CHECK.1,
  CHECK.2, `agents/`, `patching/`, `core/pipeline.py`, `core/executor.py`,
  `core/self_correct_loop.py`, `core/worker_result_review.py`,
  `core/worker_runs.py`, `core/worker_assignment.py`, etc.), unchanged.
- `human_approval_required: true`, `merge_allowed: false`,
  `model_calls_allowed: false`, `writes_real_repo: false`.

`tests/test_phase_registry.py`'s seed-registry assertions
(`len(phases) == 134`, `counts_by_track["CHECK"] == 3`) become `135` and `4`.

## Known limitations (stated up front, not discovered later)

1. **No production producer exists yet.** Every live dogfood run reports
   `worker_declaration_source = legacy_plan_derived` until a future
   worker-protocol phase wires a real caller through this seam. This phase
   proves the seam is correct; it does not populate it in production.
2. **Kind-mismatch may not be reachable through the full live executor
   round-trip** — see the regression table above.
3. **`expected_change_identity_sha256` is never populated from a
   declaration**, by design (§6) — `CLASSIFICATION_IDENTITY_MISMATCH` stays
   unreachable via this path, same as it already is via the patch-plan path.
4. **A `Mapping`-form declaration is validated once, at ingestion.** There is
   no repair/retry loop; a malformed declaration falls back to legacy for
   that run and is flagged, not corrected.

## What does not change

Authoritative run results, CHECK.1's own two frozen modules, CHECK.2,
`ObservedPostRunFacts`/`ExecutionAuthorization` producers, the feature flag
default (off), model-call count, validation-execution count, repository-walk
count, and patch-application count and order. CHECK.2 and CHECK.3 remain
unwired and unreachable from this path, same as CHECK.LIVE.1 already
guarantees.
