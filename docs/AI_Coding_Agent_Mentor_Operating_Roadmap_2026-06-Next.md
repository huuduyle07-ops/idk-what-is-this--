# C.A.T.T.U.S Next Operating Roadmap — Post-Autonomy Command Doctrine

## 1. Executive Summary

The previous C.A.T.T.U.S operating roadmap arc is complete after ROAD.4. The completed work established a machine-readable phase registry, a phase picker with night candidate reporting, a post-MODEL checkpoint audit, a full EVAL benchmark evidence arc (EVAL.1–3), a full CMD orchestration doctrine arc (CMD.1–4), and a post-EVAL/CMD checkpoint audit (ROAD.4). The autonomy experiment is now frozen: the system has tested local autonomy boundaries, recorded the results, and should not chase broader autonomy as the next default move.

The next roadmap should turn the tested boundary into controlled operating doctrine. That means selecting the next work deliberately, branch by branch, with evidence and human authorization before action. C.A.T.T.U.S may recommend, summarize, compare, classify, and prepare reports, but the human operator remains the final authority for direction, approval, execution, merge decisions, and any future unlock.

NEXT.1 is the seed for that decision. It defines candidate branches and decision rules. It does not implement features, add runtime behavior, increase autonomy, or open remote execution.

## 2. Frozen Checkpoint

The completed roadmap arc is frozen at the following checkpoint.

### ROAD: Governance, Registry, Picker, Audit

- ROAD.1 created the machine-readable phase registry.
- ROAD.2 added the phase picker and night candidate report.
- ROAD.3 completed the post-MODEL checkpoint audit.
- ROAD.4 completed the post-EVAL/CMD checkpoint audit (verifies EVAL.1–3 and CMD.1–4).
- The phase registry is valid (113 phases: 3 ADOPT + 4 ROAD + 3 AUTO + 11 MODEL + 11 EVAL + 5 HUMAN + 11 CMD + 9 HARDEN + 4 OPS + 2 DOGFOOD + 1 VERIFY + 15 MIRROR + 27 UX + 7 INDEX).
- The phase picker recommends `DOGFOOD.1B` - Real Operator Run Evaluation. `VERIFY.TEST.1` remains proposed but waits for DOGFOOD.1B to complete.

### AUTO: Remote Safety Contracts, Dry Run Only

- AUTO.2a defined the Telegram evidence summary contract.
- AUTO.2b defined the GitHub remote PR safety contract.
- AUTO.2c defined the n8n orchestration dry run.
- Remote work remains contract-first and dry-run-only.
- No live remote execution is authorized by the completed AUTO arc.

### MODEL: Advisory Dataset And Baseline Pipeline

- MODEL.1 created the C.A.T.T.U.S artifact dataset builder.
- MODEL.2 created the driver classifier baseline.
- MODEL.3 created the lesson graph activation dataset.
- MODEL outputs remain advisory only.
- No learned model has live routing, veto, merge, or execution authority.

### Validation State

- Registry validation is passing.
- DOGFOOD.1A completed the pure operator-evaluation framework and generated a safe evidence artifact. It does not fabricate real runs; the artifact remains explicitly insufficient until three to five sanitized real observations are recorded.
- HARDEN.PROGRESS.1 completed the narrow early-error terminal observation correction on a separate hardening track. It reuses the stable progress run ID, records a genuine early application error as terminal `error_reported`, preserves the application error result, and leaves UX.LIVE, UI, polling, freshness, and defaults unchanged. Its status is `early_error_terminal_coverage_ready_with_warnings` because a genuine post-fix DOGFOOD repeat remains pending.
- DOGFOOD.1B is proposed to collect the actual sanitized operator evidence: at least three real observations, including success, error, and multistage coverage. The current phase picker recommends DOGFOOD.1B, while UX.LIVE remains frozen and any corrective product work still requires a separately approved phase.
- The old roadmap arc is complete and should not be stretched to imply new authorization.

### Benchmark State

- One live benchmark flake was observed.
- An isolated rerun passed 3/3.
- No urgent patch is required.
- The flake still creates a trust question for future benchmark interpretation, which makes benchmark evidence work the strongest next candidate.

### INDEX: Canonical Index Integrity Boundary

- `INDEX.1D.1` shipped the contract-only separation between task-scoped
  Activation Graphs and the persistent Canonical Incremental Graph.
- Ordinary narrow coding tasks may use Direct Context or a bounded Activation
  Graph; they are not required to run canonical repository indexing.
- Activation Graphs have a sliding 72-hour TTL, lazy dry-run-first cleanup,
  pin/lease protection, freshness checks before reuse, and no database,
  manifest, reconciliation, or repository-completeness authority.
- The Canonical Incremental Graph is explicitly built or refreshed, is isolated
  from Activation Graph cleanup, and requires confirmed identity plus trusted
  completion before manifest advancement, reconciliation, epoch replacement,
  or current/completeness claims.
- This phase added no graph runtime, route, worker, database write, manifest
  access, model/API call, embedding, repository scan, or deletion behavior.
- `INDEX.1D.2A` shipped the canonical physical repository identity primitive:
  canonical root, repository ID, compatible artifact storage key, strict
  code-index scope, and optional non-authoritative semantic `project_tag`.
- Identity now resolves an existing directory and hashes only its normalized
  physical path. It performs zero repository walks, reads no source content,
  and is stable across file, Git-object, language, generated-artifact, and
  architecture-content changes.
- The canonical code-index writer and retriever share the same path-derived
  scope and use a strict facade that rejects missing, blank, or semantic-label
  scopes before database access. Legacy unscoped APIs remain compatibility-only.
- The confirmed `DATABASE_URL` construction leak and audited index/web/health
  error sinks now redact PostgreSQL userinfo, query values, and token-shaped
  assignments.
- Default manifest storage keys and code-index scopes remain compatible for
  ordinary root names. Storage slugs longer than 111 characters are bounded for
  filesystem/lesson-scope safety. Automatic inventory-derived project-tag
  namespaces cut over to the canonical storage key; old state is retained
  without migration or deletion.
- `INDEX.1D.2A` does not add identity confirmation, epoch state transitions,
  trusted completion, manifest advancement, delta execution, canonical
  reconciliation changes, or Activation Graph runtime behavior.
- `INDEX.1D.2B` shipped the persistent identity-confirmation and architecture-
  epoch state contract. Its stable states are `uninitialized`,
  `initial_confirmation_required`, `confirmed`,
  `major_change_confirmation_required`, `archived`, and fail-closed `blocked`.
- Human decisions are explicit: `same_project` preserves repository identity,
  epoch, and scope; `new_architecture_epoch` preserves lineage while archiving
  the prior readable, write-disabled scope; `new_project` reports that
  rebinding is required; and `reject_or_defer` unlocks no canonical mutation.
- Confirmed-state permissions are identity-only. They can authorize canonical
  build, refresh, reconciliation, and applied-manifest advancement in
  principle, while trusted-current claims and actual trusted-completion
  evidence remain locked for `INDEX.1D.2C`.
- Versioned identity state is stored as deterministic JSON beneath the
  canonical repository-intelligence root, using a bounded storage namespace,
  strict containment and reparse checks, a per-path lock, a unique
  same-directory temporary file, `fsync`, and atomic replacement. Malformed,
  contradictory, wrong-repository, stale-revision, and unsafe-path state fails
  closed without silently downgrading or repairing confirmed state.
- Activation Graph operation remains independent and available while canonical
  identity is uninitialized, awaiting confirmation, awaiting major-change
  confirmation, or blocked. It gains no power to confirm identity, create an
  epoch, change a project tag, reconcile canonical rows, or advance a canonical
  manifest.
- Supplied legacy namespace evidence produces preservation-only migration
  warnings. `INDEX.1D.2B` performs no namespace scan, rebinding, migration, or
  deletion, and adds no production indexing, delta execution, trusted-
  completion evidence, database or manifest access, reconciliation execution,
  model/API call, embedding, repository scan, or Activation Graph runtime.
- `INDEX.1D.2C` shipped the immutable, fail-closed Honest Persistence
  Completion Contract. Processing, required persistence, reconciliation,
  auxiliary output, manifest eligibility, and trusted-current eligibility are
  now independent evidence dimensions rather than one ambiguous success flag.
- Required added and modified files must be persisted and required deletions
  must be deleted. A required persistence failure latches failure, records
  failed and remaining unattempted files, skips reconciliation, and blocks
  trusted completion even when source processing continues for diagnostics.
- Persistence disabled is explicitly distinct from persistent success.
  Applied-manifest advancement requires confirmed identity plus successful
  required processing, persistence, and reconciliation; pending or blocked
  identity, partial persistence, skipped reconciliation, and contradictory
  evidence fail closed.
- Observed repository state remains scan evidence only and cannot be mistaken
  for applied persistent state. Completion evidence alone cannot claim
  repository intelligence is current: matching applied-manifest evidence for
  the completed run is additionally required, and production manifest commit
  wiring remains deferred.
- Database code-index persistence and required scope reconciliation are
  authoritative. Current ProgramGraph construction, Project Map, Code DNA,
  Phantom Limb, Obsidian export, presentation/report artifacts, and UI
  summaries are auxiliary; unknown future authority fails closed.
- Existing index results remain readable and gain additive completion metadata.
  `INDEX.1D.2C` adds no production delta dispatch, manifest save, repository
  scan, model/API or embedding call, schema migration, Activation Graph
  runtime, legacy namespace migration, or broad execution-flow redesign.
- `INDEX.1D.3` shipped the Traversal Budget Closure. One immutable,
  operation-scoped repository inventory now owns canonical membership;
  downstream indexing, language, Code DNA, dependency, ProgramGraph,
  project-map, manifest, and project-input web consumers reuse that snapshot
  instead of independently rediscovering repository files.
- The canonical index and its project-input web entry path are test-pinned to
  one full membership traversal. Canonical identity and repeated
  `get_agent_dir()` calls add zero walks; supplied-inventory graph, manifest,
  Code DNA, project-map, and dependency consumers add zero membership walks.
- Supplied inventories fail closed on repository-root mismatch, duplicate or
  out-of-root entries, contradictory paths, and nondeterministic ordering.
  Malformed supplied state never triggers a hidden fallback scan. A legacy
  caller that supplies no inventory may scan once for compatibility.
- The inventory is a membership snapshot, not persisted repository truth or a
  content-freshness guarantee. If a file disappears after enumeration,
  processing records an explicit failure, performs no automatic full rescan,
  and INDEX.1D.2C denies trusted completion.
- Traversal diagnostics expose deterministic site labels and reuse booleans
  without absolute repository paths, source content, environment values, or
  secrets. INDEX.1D.3 adds no global repository-truth cache, background
  worker, watcher, retry loop, model/API/network/subprocess inventory, or
  filesystem deletion.
- Production delta dispatch, applied-manifest save/advancement, database
  behavior, graph semantics, legacy namespace migration, and Activation Graph
  runtime remain unchanged and unauthorized.
- `INDEX.1E.0` completed the deterministic Delta Integration Preflight and
  Known-Failure Baseline. It froze observed repository-wide failures by stable
  node ID, category, INDEX-path intersection, reason, and evidence; duplicate
  or unclassified records fail closed.
- The historical preflight readiness decision remains blocked for
  authoritative delta dispatch. Architecture-epoch scope compatibility,
  applied-receipt bridging, planner inputs, auxiliary full-repository outputs,
  and empty-scope reconciliation were not silently declared resolved. Finishing
  the analysis phase did not grant production execution or manifest authority.
- `INDEX.1E.1` shipped Manifest Load and Shadow Delta Plan Dispatch at the one
  canonical seam inside `core.indexer.index_repository`, after the shared
  `RepositoryInventory` and repository identity context are available and
  before the existing full-processing loop.
- The seam now observes the previous applied manifest, builds a current
  observed manifest from canonical indexable inventory membership, classifies
  added, modified, deleted, and unchanged files, and calls the existing pure
  execution planner. Missing applied state is an explicit cold build; invalid,
  unsupported, root-, repository-, epoch-, or scope-mismatched state fails
  closed for shadow planning rather than becoming an authoritative empty
  baseline.
- Applied and observed manifests remain separate roles. `INDEX.1E.1` does not
  save, advance, repair, replace, or create an authoritative manifest, and it
  creates no trusted-current receipt.
- The additive `delta_shadow` result is schema-versioned, deterministic,
  bounded, credential-redacted, repository-relative where paths are exposed,
  and permanently marked non-authoritative. Identity permissions and
  persistence or embedding compatibility can constrain future executability,
  but no shadow status grants mutation authority.
- Embedding compatibility comes from the applied manifest's persisted
  signature and the current configured signature. Exact matches, same-dimension
  drift, dimension changes, disabled embeddings, and cold builds are explicit;
  legacy applied manifests without a signature fail closed for future planning.
- Production processing remains intentionally full for stable valid entries.
  No shadow recommendation skips a file or controls parsing, embedding,
  per-file replacement, deletion, reconciliation, graph construction, Code
  DNA, Project Map, or Phantom Limb behavior. A post-inventory entry that
  becomes unsafe is now an explicit processing failure that suppresses its
  replacement and repository reconciliation independently of the shadow plan.
- Run B is the defining parity proof: the shadow plan recommends zero
  changed-file work for an unchanged repository while production still
  reparses, re-embeds, replaces, and reconciles every current indexable file.
  That expected mismatch proves observation rather than incremental execution.
- Canonical and project-input web operations remain pinned to one repository
  membership walk. Manifest loading is one bounded direct artifact read, and
  observed-manifest, graph, project-map, Code DNA, and dependency consumers add
  zero membership walks when given the shared inventory.
- The frozen pre-`INDEX.1E.1` repository-wide baseline was **6309 passed, 5
  skipped, and 48 known unrelated failures**. The post-phase comparison is
  **6366 passed, 6 skipped, and the same 48 failure node IDs**, with zero new,
  authoritative INDEX, or unclassified failures. Existing failures remain
  visible rather than skipped, weakened, or converted to blanket `xfail`.
- `INDEX.1E.1` adds no production delta dispatch, applied-manifest mutation,
  plan-controlled database or reconciliation change, Activation Graph runtime,
  legacy namespace migration, model/API/network call, background worker,
  scheduler, or benchmark behavior change. Descriptor-bound production content
  reads remain a separate future security-hardening concern.
- Recommended next phase is `INDEX.1E.2` — Unchanged File Fast Path.
  `INDEX.1E.2` is not started or authorized by `INDEX.1E.1`.

## 3. Design Principles

- Evidence before action.
- Advisory models only.
- Remote contracts before remote execution.
- Human approval remains required.
- Benchmark trust before bigger autonomy.
- Operator clarity before feature expansion.

These principles should govern every branch below. Report-only work should come first when a branch touches trust, autonomy, remote action, model influence, or operator-facing execution decisions.

## 4. Candidate Branches

### Branch EVAL — Trust the Run

Purpose:

- Create a benchmark ledger.
- Compare run-to-run evidence.
- Classify flakes.
- Compare replay evidence.
- Track stochastic model behavior.

Example phases:

- EVAL.1 — Live Benchmark Run Ledger — ✅ shipped 2026-06-22 (complete).
- EVAL.2 — Benchmark Report Compare / Single-Case Flake Evidence — ✅ shipped 2026-06-22 (complete).
- EVAL.3 — Flake Classification Report — ✅ shipped 2026-06-22 (complete).
- EVAL.4 — Run Variance Dashboard

Branch boundary:

- EVAL may read benchmark reports and produce evidence summaries.
- EVAL must not change benchmark scoring, benchmark cases, model calls, patch behavior, or runtime behavior unless a later approved phase explicitly changes scope.

### Branch UX — Use It Daily

Purpose:

- Clean up the web/operator surface.
- Reduce button overload.
- Clarify evidence panels.
- Make the common workflow obvious.
- Hide dangerous and debug features behind disclosure.

Example phases:

- UX.1 — Operator Cockpit & Idea Intake Plan — ✅ shipped 2026-06-24 (complete).
- UX.2 — Run Timeline / Progress Surface — ✅ shipped 2026-06-25 (complete).
- UX.3 — Continue-from-Frame Contract — ✅ shipped 2026-06-26 (complete).
- UX.4 — Mixed Mode Intent Router Preview — ✅ shipped 2026-06-26 (complete).
- UX.5 — Goal Brief 4W1H Simplifier — ✅ shipped 2026-06-26 (complete).
- UX.6 — Evidence Card Layout — ✅ shipped 2026-06-26 (complete).
- UX.7 — Cockpit Navigation & Action Hierarchy Cleanup — ✅ shipped 2026-06-27 (complete).
- UX.8 — Cockpit Usability Checkpoint — ✅ shipped 2026-06-27 (complete).
- UX.9 — Unified Workbench Input Plan — ✅ shipped 2026-06-27 (complete).
- UX.10 — Unified Workbench Input Visual Integration — ✅ shipped 2026-06-27 (complete).
- UX.11 — Unified Workbench Behavior Preservation Check — ✅ shipped 2026-06-28 (complete).
- UX.CLOSE — UX Branch Freeze Checkpoint — ✅ shipped 2026-06-28 (complete). UX branch is frozen.

Branch boundary:

- UX may improve operator comprehension and workflow layout.
- UX must not weaken approvals, hide required evidence, make dangerous actions easier to trigger, or add new autonomous behavior.

Next recommendation: the UX branch is complete and frozen at UX.CLOSE,
the earlier hardening checkpoint artifacts have consolidated HARDEN.1-HARDEN.3
evidence, and
MIRROR.1 through MIRROR.CLOSE3 have shipped the report-only trace, scoring,
claim-vs-diff, ingestion-planning, manual trace assembly, manual review
pipeline, branch checkpoint, default-off shadow live trace writer, and post-run
live trace scoring preview foundation, advisory operator panel plan, and
read-only operator panel UI stub, artifact loader preview, and live demo
readiness checker, plus the live/UI readiness checkpoint.
EVAL.CLOSE froze the Evidence Quality branch after EVAL.N7 verified the
EVAL.N5/N6 panel and loader readiness. HUMAN.N1 mapped what the system may
advise or display versus what only the human may approve, HUMAN.N2 defined
the explicit confirmation signal shape before dangerous actions, HUMAN.N3
added report-only dry-run validation for sample approval tokens, HUMAN.N4
added documentation-only sample tokens, and HUMAN.CLOSE froze the human
authority branch before runtime enforcement design. ADOPT.MODEL.CLOSE froze
the model catalog adoption branch after ADOPT.MODEL.1 adopted the advisory
catalog artifact and ADOPT.MODEL.2 verified the active 10-role coverage. The
HARDEN.N1, HARDEN.N2, HARDEN.N3, and HARDEN.N4 have since shipped the approval
enforcement readiness audit, attachment plan, dry-run gate simulator, and
operator report, all report-only and without runtime enforcement. HARDEN.CLOSE
has now frozen HARDEN.N1-N4 as a non-enforcing planning branch. OPS.TEST.1,
OPS.TEST.2, OPS.TEST.3, and OPS.TEST.CLOSE have also shipped, freezing the
test-runtime planning branch before executable manifests or runner commands.
UX.RUN.3 ships a compact read-only panel for loaded progress snapshot artifacts
after UX.RUN.2 made the progress-stage contract loadable. UX.RUN.CLOSE now freezes
UX.RUN.1 through UX.RUN.3 as a safe read-only branch. The phase picker recommends
**DOGFOOD.1B - Real Operator Run Evaluation** after UX.LIVE.CLOSE froze the
browser experiment. DOGFOOD.1B remains proposed and report-only; it may evaluate
operator understanding and usefulness but may not authorize execution or runtime changes.
MIRROR.13 remains a proposed Mirror candidate, ranked after DOGFOOD.1B.

### Branch CMD — Commander Mode

Purpose:

- Design big-task orchestration.
- Define a decomposition contract.
- Estimate budget and time.
- Define stop conditions.
- Support tower-defense style planning.
- Avoid autonomous merge or execution.

Example phases:

- CMD.1 — Commander Run Contract — shipped 2026-06-22 (complete).
- CMD.2 — Task Decomposition Preview — shipped 2026-06-22 (complete).
- CMD.3 — Budget Governor Preview — shipped 2026-06-22 (complete).
- CMD.4 — Commander Readiness / Stop Condition Report — shipped 2026-06-22 (complete).
- CMD.N1 - Boss Half-Life Fracture Plan - shipped 2026-07-02 (complete).
- CMD.N2 - Manual Boss Fracture Report - shipped 2026-07-02 (complete).
- CMD.N3 - Commander Fracture Tree Schema / Registry - shipped 2026-07-02 (complete).
- CMD.N4 - Commander Preflight Contract - shipped 2026-07-02 (complete).
- CMD.N5 - Commander Manual Assignment Plan - shipped 2026-07-03 (complete).
- CMD.N6 - Commander Assignment Review Pack - proposed.

Branch boundary:

- CMD may design previews, reports, contracts, and planning doctrine.
- CMD must not authorize autonomous merge, live execution, remote execution, or model-directed routing.

### Branch MODEL — Advisory Learning

Purpose:

- Improve MODEL.1, MODEL.2, and MODEL.3 datasets.
- Add more labels.
- Compare deterministic signals against learned advisory signals.
- Keep learned outputs advisory.
- Avoid live routing authority.

Example phases:

- MODEL.N1 — Dataset Coverage Report
- MODEL.N2 — Driver Baseline Compare
- MODEL.N3 — Lesson Activation Scorer Preview
- MODEL.N4 — Advisory Model Veto Contract

Branch boundary:

- MODEL may generate reports, coverage analysis, baseline comparisons, and advisory previews.
- MODEL must not grant live authority to learned signals or replace deterministic safety gates.

### Branch REMOTE — Locked Remote Shell

Purpose:

- Keep Telegram, GitHub, and n8n locked.
- Prepare contracts and dry runs only.
- Prevent real network action until an explicit future unlock phase.

Example phases:

- REMOTE.1 — Remote Unlock Criteria
- REMOTE.2 — Human Approval Ceremony Contract
- REMOTE.3 — Dry-Run Replay Before Live Remote
- REMOTE.4 — Remote Kill Switch Contract

Branch boundary:

- REMOTE may define criteria, ceremonies, kill switches, replay checks, and dry-run evidence.
- REMOTE must not send live messages, open remote PRs, trigger n8n, or perform real network side effects.

### Track S — Skill / Prompt Optimization Evidence Loop

S.1 Skill Registry
S.2 Skill Eval Report
S.3 Rejected Edit Buffer
S.4 Bounded Edit Draft
S.5 Promotion Gate
S.6 Optional optimizer experiment

## 5. Recommended Priority

Recommended branch order:

1. HARDEN - HARDEN.N1 is next recommended after ADOPT.MODEL.CLOSE
2. HUMAN - shipped through HUMAN.CLOSE
3. CMD - shipped through CMD.CLOSE
4. MODEL - shipped through MODEL.CLOSE
5. UX - shipped through UX.CLOSE
6. ADOPT - shipped through ADOPT.MODEL.CLOSE
7. DOGFOOD - proposed through DOGFOOD.1B as the current real-use evidence priority
8. MIRROR - proposed through MIRROR.13, ranked after DOGFOOD.1B
9. REMOTE

EVAL went first because a live benchmark flake appeared. EVAL.1, EVAL.2, and EVAL.3 are now shipped, giving C.A.T.T.U.S a report-only benchmark ledger, case comparison evidence, and flake classification before relying on larger operational claims.

CMD is now shipped through CMD.CLOSE: CMD.1-CMD.4 established the original Commander doctrine arc, CMD.N1-CMD.N6 added report-only fracture, preflight, manual assignment, and review-pack structure, and CMD.CLOSE froze the branch before execution-related design. MODEL is also shipped through MODEL.CLOSE, freezing the advisory model-role planning branch. EVAL.CLOSE froze the Evidence Quality branch, HUMAN.N1 mapped human-only review and approval boundaries across the advisory surfaces, HUMAN.N2 defined explicit human confirmation signals before dangerous actions, HUMAN.N3 added dry-run sample token validation against that contract without enforcing runtime behavior, HUMAN.N4 added documentation-only valid, warning, invalid, and blocked sample tokens, HUMAN.CLOSE froze the human authority branch, ADOPT.MODEL.1 adopted the advisory model-role catalog artifact, ADOPT.MODEL.2 verified post-adoption coverage against the active 10-role catalog, ADOPT.MODEL.CLOSE froze the adoption branch through a report-only checkpoint, HARDEN.CLOSE froze the approval-enforcement planning branch, OPS.TEST.CLOSE froze the test-runtime planning branch, UX.RUN.1 defined the read-only run progress visibility contract, UX.RUN.2 made existing progress snapshots loadable through a GET-only boundary, UX.RUN.3 added a read-only snapshot panel, UX.RUN.CLOSE froze the branch, and UX.LIVE.CLOSE froze UX.LIVE.1-10 after adding an optional bounded browser reader. The current picker recommendation is DOGFOOD.1B, a report-only real-operator evaluation that must not add live behavior.

UX remains important because operator clarity is required for daily use. If the operator cannot quickly see evidence, approvals, risk, and common workflow state, the system becomes harder to supervise even when the underlying safety contracts are sound.

MODEL should go fourth because the current dataset is small. More coverage, labels, and comparisons are useful, but model output must remain advisory until there is much stronger evidence and explicit authorization.

REMOTE should go last because remote execution should stay locked. Telegram, GitHub, and n8n work should remain in contract and dry-run form until a future roadmap explicitly accepts unlock criteria and operator approval ceremony requirements.

## 6. First Proposed Next Phase

### EVAL.1 — Live Benchmark Run Ledger

**Status: shipped 2026-06-22 (complete).** Implemented report-only as
`core/benchmark_run_ledger.py` + `scripts/create_benchmark_run_ledger.py`, registered
as a `complete` EVAL-track phase in `docs/roadmap/phase_registry.json`, and validated
with `tests/test_benchmark_run_ledger.py`. The ledger reads
`.agent/benchmarks/benchmark_report_*.json` and writes
`.agent/eval/benchmark_run_ledger/benchmark_run_ledger.{json,md}`. It runs no
benchmarks, calls no models, and changes no scoring or cases.

**EVAL.2 — Benchmark Report Compare / Single-Case Flake Evidence is also shipped
2026-06-22 (complete).** Implemented report-only as `core/benchmark_report_compare.py`
+ `scripts/compare_benchmark_reports.py`, registered as a `complete` EVAL-track phase
(prerequisite EVAL.1) in `docs/roadmap/phase_registry.json`, and validated with
`tests/test_benchmark_report_compare.py`. It explains one case (or every flake
candidate) across `.agent/benchmarks/benchmark_report_*.json` — report ordering, case
timeline, evidence labels, conservative classification, and an optional EVAL.1 ledger
cross-check — and writes `.agent/eval/benchmark_report_compare/<case_id>_compare.{json,md}`.
It runs no benchmarks, calls no models, and changes no scoring or cases.

**EVAL.3 — Flake Classification Report is also shipped 2026-06-22 (complete).**
Implemented report-only as `core/flake_classification_report.py` +
`scripts/create_flake_classification_report.py`, registered as a `complete`
EVAL-track phase (prerequisite EVAL.2) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_flake_classification_report.py`. It reads the EVAL.1
ledger, EVAL.2 compare reports, and benchmark reports only as fallback evidence;
then writes `.agent/eval/flake_classification_report/flake_classification_report.{json,md}`.
It produces stable / likely_flake / likely_broken / needs_rerun /
insufficient_history buckets, conservative human actions, and no benchmark/model/
patch/validation/network/worker/merge power.

**CMD.1 — Commander Run Contract is also shipped 2026-06-22 (complete).**
Implemented report-only as `core/commander_run_contract.py` +
`scripts/create_commander_run_contract.py`, registered as a `complete`
CMD-track phase (prerequisite EVAL.3) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_commander_run_contract.py`. It accepts a plain-text
task and optional scope/risk context, then writes
`.agent/commander/contracts/<contract_id>.{json,md}` classifying the task as
`instant_run`, `commander_run`, `needs_clarification`, or `reject_or_defer`. It
previews required gates and stop conditions, but adds no Commander execution,
agent launch, model call, patch apply, validation run, benchmark run, network
call, database write, worker launch, push, merge, or PR power.

**CMD.2 — Task Decomposition Preview is also shipped 2026-06-22 (complete).**
Implemented report-only as `core/commander_task_decomposition.py` +
`scripts/create_commander_task_decomposition.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.1) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_commander_task_decomposition.py`. It reads an optional
CMD.1 contract or task text, then writes
`.agent/commander/decomposition_previews/<preview_id>.{json,md}` with a deterministic
phase plan plus evidence, validation, benchmark, budget, rollback, and human
checkpoint previews. It adds no decomposition execution, agent launch, model call,
patch apply, validation run, benchmark run, network call, database write, worker
launch, push, merge, or PR power.

**CMD.3 — Budget Governor Preview is also shipped 2026-06-22 (complete).**
Implemented report-only as `core/commander_budget_governor.py` +
`scripts/create_commander_budget_governor.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.2) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_commander_budget_governor.py`. It reads an optional
CMD.1 contract and optional CMD.2 decomposition preview, then writes
`.agent/commander/budget_previews/<preview_id>.{json,md}` with deterministic file,
line, time, phase, budget-limit, escalation-rule, stop-condition, and human
checkpoint previews. It adds no budget enforcement, Commander execution, agent
launch, model call, patch apply, validation run, benchmark run, network call,
database write, worker launch, push, merge, or PR power.

**CMD.4 — Commander Readiness / Stop Condition Report is also shipped 2026-06-22
(complete).** Implemented report-only as `core/commander_readiness_report.py` +
`scripts/create_commander_readiness_report.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.3) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_commander_readiness_report.py`. It reads optional
CMD.1, CMD.2, and CMD.3 artifacts, then writes
`.agent/commander/readiness_reports/<report_id>.{json,md}` with deterministic
readiness status, gate summary, budget summary, stop-condition aggregation,
human-approval requirements, and required-before-implementation items. It adds no
readiness execution, Commander execution, agent launch, model call, patch apply,
validation run, benchmark run, network call, database write, worker launch, push,
merge, or PR power.

**UX.4 — Mixed Mode Intent Router Preview is shipped 2026-06-26 (complete).**
Implemented as `core/mixed_mode_intent_router.py` + `scripts/create_mixed_mode_intent_router_preview.py`,
registered as a `complete` UX-track phase (prerequisite UX.3) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_mixed_mode_intent_router.py` (38 tests +
1 skipped). UX.4 classifies user text into one of six intent modes (chat / instant_run /
continue_from_frame / commander_plan / clarify / reject_or_defer) using deterministic signal matching.
Includes routing policy, UI contract, per-mode allowed/forbidden next steps, mode count summary,
ambiguous and rejected/deferred input surfaces, and demo mode. A read-only "Mixed Mode Router"
placeholder panel was added to `web/templates/index.html` (Views tab group).
Artifacts: `.agent/ux/mixed_mode_intent_router/mixed_mode_intent_router_preview.{json,md}`. No router
dispatch, agent launch, model call, patch apply, validation run, benchmark run, network call, database
write, worker launch, push, merge, or PR power was added.

**UX.5 — Goal Brief 4W1H Simplifier is shipped 2026-06-26 (complete).**
Implemented as `core/goal_brief_4w1h.py` + `scripts/create_goal_brief_4w1h_preview.py`,
registered as a `complete` UX-track phase (prerequisite UX.4) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_goal_brief_4w1h.py` (57 tests).
UX.5 scores operator Goal Briefs across five 4W1H dimensions (What/Why/Where/When-stop/How-validate),
classifies each field as strong/present/weak/missing (score 0–100), generates clarifying questions for
incomplete fields, and recommends a mode hint (instant_run_preview, commander_contract_preview, clarify,
chat). Includes simplified goal brief, field completeness aggregates, allowed/forbidden next steps, demo
mode covering all four hint types, and boundary text. A read-only "4W1H Goal Brief" placeholder panel
was added to `web/templates/index.html` (Views tab group).
Artifacts: `.agent/ux/goal_brief_4w1h/goal_brief_4w1h_preview.{json,md}`. No goal execution,
dispatch, agent launch, model call, patch apply, validation run, benchmark run, network call, database
write, worker launch, push, merge, or PR power was added.

**UX.6 — Evidence Card Layout is shipped 2026-06-26 (complete).**
Implemented as `core/evidence_card_layout.py` + `scripts/create_evidence_card_layout_preview.py`,
registered as a `complete` UX-track phase (prerequisite UX.5) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_evidence_card_layout.py` (42 tests + 1 skipped).
Defines 8 canonical card types (answer_summary, patch_summary, changed_files, validation_summary,
benchmark_summary, risk_summary, human_review, next_action), six card statuses (pass/warn/fail/missing/info/blocked),
three priorities (high/medium/low), five display groups (result/change/checks/risk/decision), and a four-outcome
deterministic operator decision summary (ready_for_human_review, needs_more_evidence, blocked_by_failed_check,
insufficient_information). A read-only "Evidence Cards" placeholder panel was added to `web/templates/index.html`.
Artifacts: `.agent/ux/evidence_card_layout/evidence_card_layout_preview.{json,md}`. No evidence creation,
execution, agent launch, AI service call, patch apply, validation run, benchmark run, network call, database
write, worker launch, push, merge, or PR power was added.

**UX.7 — Cockpit Navigation & Action Hierarchy Cleanup is shipped 2026-06-27 (complete).**
Implemented as `core/cockpit_action_hierarchy.py` + `scripts/create_cockpit_action_hierarchy_report.py`,
registered as a `complete` UX-track phase (prerequisite UX.6) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_cockpit_action_hierarchy.py` (36 tests).
Restructures `web/templates/index.html` navigation into three tiers: Primary (Workbench/Memory/Settings),
Workflow (Run Timeline/Mode Decision/Goal Brief+4W1H/Evidence Cards/Continue From Frame), and a collapsible
Advanced/Debug drawer (Benchmarks/Dream/Graph). Merges the separate "Goal Brief" and "4W1H Goal Brief" nav
tabs into one "Goal Brief / 4W1H" entry. Relabels "Mixed Mode Router" to "Mode Decision". Adds cockpit-section
CSS in `web/static/style.css` for the workflow group and advanced drawer. Extends `showWorkspaceTab()` valid
array to include all UX panel IDs (run-timeline, continue-from-frame, mixed-mode-router, goal-brief-4w1h,
evidence-cards). No new backend routes, mutation routes, execution powers, model calls, network calls,
patches, validation, benchmarks, workers, push, merge, or PRs added.

**UX.8 — Cockpit Usability Checkpoint is shipped 2026-06-27 (complete).**
Implemented as `core/cockpit_usability_checkpoint.py` +
`scripts/create_cockpit_usability_checkpoint.py`, registered as a `complete`
UX-track phase (prerequisite UX.7) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_cockpit_usability_checkpoint.py`. UX.8 is a report-only
checkpoint that audits the goal-to-review cockpit workflow: Goal Brief / 4W1H,
Mode Decision, chat/run/continue/commander start, Run Timeline, Answer / Patch
review, Evidence Cards, Continue From Frame, and Advanced / Debug. It writes
`.agent/ux/cockpit_usability_checkpoint/cockpit_usability_checkpoint.{json,md}`
with deterministic checkpoint usability scores, navigation findings, action hierarchy
findings, operator questions, UX risks, manual review checklist, and a recommended
next phase. Default recommendation: UX.9 — Unified Workbench Input Plan, because
Chat vs Instant Run remains the major structural split. No backend routes, mutation
routes, execution powers, model calls, network calls, patches, validation, benchmarks,
workers, database writes, push, merge, or PRs added.

**UX.9 — Unified Workbench Input Plan is shipped 2026-06-27 (complete).**
Implemented as `core/unified_workbench_input_plan.py` +
`scripts/create_unified_workbench_input_plan.py`, registered as a `complete`
UX-track phase (prerequisite UX.8) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_unified_workbench_input_plan.py`. UX.9 is a plan-only
contract for one Workbench input that conceptually merges Chat, Instant Run, and
Goal Brief / 4W1H. It defines the unified input field schema, the help-only `?`
activation helper, UX.4-style mode preview, explicit confirmation actions, button
reduction plan, future UI layout plan, and staged migration plan. Artifacts:
`.agent/ux/unified_workbench_input_plan/unified_workbench_input_plan.{json,md}`.
Next likely: UX.10 — Unified Workbench Input Visual Integration. No auto-dispatch,
execution-path merge, backend route, mutation route, run start, model call, patch
apply, validation run, benchmark run, network call, database write, worker launch,
push, merge, or PR power was added.

**UX.10 — Unified Workbench Input Visual Integration is shipped 2026-06-27 (complete).**
Implemented in `web/templates/index.html` and `web/static/style.css`, registered as a
`complete` UX-track phase (prerequisite UX.9) in `docs/roadmap/phase_registry.json`,
and validated with `tests/test_unified_workbench_visual_integration.py`. UX.10 makes
the existing agent form read visually as one Unified Workbench: one main intent input,
compact 4W1H helper rows with help-only `?` affordances, preview-only mode chips,
confirmation actions that reuse existing mode switching or workflow navigation, and an
explicit safety note that mode preview does not auto-dispatch. Existing behavior is
preserved: no backend route was added, no execution path was merged, no new fetch/post
path was introduced, and Apply / Review Patch remains separate and human-triggered.
Follow-up: UX.11 — Unified Workbench Behavior Preservation Check.

**UX.CLOSE — UX Branch Freeze Checkpoint is shipped 2026-06-28 (complete).**
Implemented as `core/ux_branch_freeze_checkpoint.py` +
`scripts/create_ux_branch_freeze_checkpoint.py`, registered as a `complete` UX-track
phase (prerequisite UX.11) in `docs/roadmap/phase_registry.json`, and validated with
`tests/test_ux_branch_freeze_checkpoint.py`. UX.CLOSE is a report-only checkpoint that
proves the UX branch (UX.1 through UX.11) is complete, behavior-preserving, and safe to
freeze. It verifies: UX.1–UX.11 are registered complete and report-only; the Unified
Workbench visual integration exists; the UX.11 behavior preservation check exists and
passes; the UX branch added no new execution path; UX.10/UX.11 added no new mutation
route; dangerous actions remain separate and human-triggered; Goal Brief / 4W1H / Mode
Preview remain assistive or preview-only; Apply / Review Patch remains outside the
unified input and requires human action; and remaining UX work is future polish only.
It reuses the phase picker for registry state and ingests the UX.11 report (built from
source text) so the freeze criteria are proven by the same source-level checks. Artifacts:
`.agent/ux/ux_branch_freeze_checkpoint/ux_branch_freeze_checkpoint.{json,md}`. No model
call, patch apply, validation run, benchmark run, network call, database write, worker
launch, backend or mutation route, UI behavior change, push, merge, or PR power was added.
The UX, HARDEN, and MIRROR branches are now frozen through MIRROR.CLOSE3.
MIRROR.1 through MIRROR.CLOSE3 have shipped the trace contract, derailment scoring report,
claim-vs-diff check, real-run ingestion/manual assembly/manual review
foundation, branch checkpoint, default-off shadow live trace writer, post-run
scoring preview, advisory operator panel plan, read-only operator panel UI
stub, artifact loader preview, live demo readiness checker, and live/UI
readiness checkpoint. CMD.N1 has since defined Commander stagnation detection,
CMD.N5 has shipped, and the recommended next move is CMD.N6 - Commander Assignment Review Pack.

**UX.11 — Unified Workbench Behavior Preservation Check is shipped 2026-06-28 (complete).**
Implemented as `core/unified_workbench_behavior_preservation.py` +
`scripts/create_unified_workbench_behavior_preservation_report.py`, registered as a
`complete` UX-track phase (prerequisite UX.10) in `docs/roadmap/phase_registry.json`,
and validated with `tests/test_unified_workbench_behavior_preservation.py`. UX.11
proves UX.10 preserved behavior: the existing `agentForm`, real `query` textarea,
primary submit path, help-only 4W1H helpers, preview-only Mode Preview, Goal Brief
builder access, separate human-triggered Apply / Review Patch, no Workbench POST or
mutation route, and no auto-run/fetch path. Optional artifacts:
`.agent/ux/unified_workbench_behavior_preservation/unified_workbench_behavior_preservation_report.{json,md}`.
Next likely: UX.CLOSE — UX Branch Freeze Checkpoint.

**UX.3 — Continue-from-Frame Contract is shipped 2026-06-26 (complete).**
Implemented as `core/continue_from_frame_contract.py` + `scripts/create_continue_from_frame_contract.py`,
registered as a `complete` UX-track phase (prerequisite UX.2) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_continue_from_frame_contract.py` (25 tests).
UX.3 defines the contract for continuing from a prior run frame: frame schema (24 required fields),
allowed/forbidden continuation modes, reusable/excluded context policies, human confirmation policy,
staleness policy (fresh/possibly_stale/stale/unknown), and UI contract. A read-only "Continue From
Frame" placeholder panel was added to `web/templates/index.html` (Views tab group).
Artifacts: `.agent/ux/continue_from_frame_contract/continue_from_frame_contract.{json,md}`. No
continuation execution, agent launch, model call, patch apply, validation run, benchmark run, network
call, database write, worker launch, push, merge, or PR power was added. Next likely: UX.4 — Mixed
Mode Intent Router Preview.

**UX.2 — Run Timeline / Progress Surface is shipped 2026-06-25 (complete).**
Implemented as `core/run_timeline_surface.py` + `scripts/create_run_timeline_surface.py`,
registered as a `complete` UX-track phase (prerequisite UX.1) in
`docs/roadmap/phase_registry.json`, and validated with `tests/test_run_timeline_surface.py`.
UX.2 is a passive visibility layer: it surfaces run progress from existing or explicitly
supplied event state via a deterministic timeline data model (10 stages, 7 statuses, a
progress-percent heuristic, blocking-event surface, and next-operator-action field).
Artifacts: `.agent/ux/run_timeline_surface/run_timeline_surface.{json,md}`. A read-only
Run Timeline panel was added to `web/templates/index.html` (Views tab group). No new
mutation routes were introduced. No task execution, agent launch, model call, patch apply,
validation run, benchmark run, network call, database write, worker launch, push, merge,
or PR power was added.

**HARDEN.1 — Web Mutation Auth / CSRF Gate is shipped 2026-06-23 (complete).**
Implemented as `web/auth_gate.py` wired into `web/app.py` via `before_request`, registered
as a `complete` HARDEN-track phase (prerequisite ROAD.4) in `docs/roadmap/phase_registry.json`,
and validated with `tests/test_web_mutation_auth_gate.py`. It adds a centralized Flask gate
that blocks unauthenticated or cross-origin mutating HTTP requests (POST/PUT/PATCH/DELETE).
Token reads `WEB_AUTH_TOKEN` env var at request time; loopback-only fallback when unset.
Cross-origin mutations are always rejected. Adds no model call, patch apply, validation run,
benchmark run, network call, database write, worker launch, push, merge, or PR power.

**HARDEN.2 — Web Mutation Surface Audit is shipped 2026-06-28 (complete).**
Implemented report-only as `core/web_mutation_surface_audit.py` +
`scripts/create_web_mutation_surface_audit.py`, registered as a `complete`
HARDEN-track phase (prerequisites UX.CLOSE and HARDEN.1) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_web_mutation_surface_audit.py` plus the HARDEN.1 gate tests. It
inspects the Flask `app.url_map`, classifies safe/read-only versus mutating
methods, flags high-risk route keywords, reports dangerous-sounding GET-only
routes for manual review, checks route modules that define routes but are not in
the app map, and confirms mutating routes are covered by the HARDEN.1 gate.
Artifacts: `.agent/harden/web_mutation_surface_audit/web_mutation_surface_audit.{json,md}`.
Adds no model call, patch apply, validation run, benchmark run, network call,
database write, worker launch, Dream execution, Replay janitor apply, route
behavior change, auth policy change, UI behavior change, push, merge, or PR power.

**HARDEN.3 — Safe Validation / MCP Approval Enforcement Audit is shipped 2026-06-29 (complete).**
Implemented report-only as `core/safe_validation_mcp_approval_audit.py` +
`scripts/create_safe_validation_mcp_approval_audit.py`, registered as a
`complete` HARDEN-track phase (prerequisite HARDEN.2) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_safe_validation_mcp_approval_audit.py` plus the HARDEN.1 and
HARDEN.2 safety tests. It statically inspects local Python source for validation
execution, MCP/tool-style artifact actions, janitor/apply/delete cleanup paths,
approval-sensitive fields, and route metadata. It reports gate evidence such as
safe-validation helpers, command safety checks, temp-clone/sandbox boundaries,
MCP allowlists, audit logging, confirmation tokens, HARDEN.1 auth coverage, and
human-approval policy fields. Artifacts:
`.agent/harden/safe_validation_mcp_approval_audit/safe_validation_mcp_approval_audit.{json,md}`.
Adds no model call, patch apply, validation run, benchmark run, MCP invocation,
worker launch, Dream execution, Replay janitor apply, network call, database
write, route behavior change, auth policy change, UI behavior change, push,
merge, or PR power. The older hardening checkpoint artifacts remain available as
`hardening_branch_checkpoint`; the live `HARDEN.CLOSE` registry slot now names
the approval-enforcement planning checkpoint after HARDEN.N4.

**Legacy hardening branch checkpoint artifacts shipped 2026-06-29.**
Implemented report-only as `core/hardening_branch_checkpoint.py` +
`scripts/create_hardening_branch_checkpoint.py`, and validated with
`tests/test_hardening_branch_checkpoint.py` plus the HARDEN.1, HARDEN.2, and
HARDEN.3 safety tests. It reads the phase registry, HARDEN.1 source markers,
and existing HARDEN.2/HARDEN.3 artifacts, then decides whether the HARDEN branch
is frozen, frozen with manual-review warnings, needs HARDEN.4, or is blocked.
Artifacts:
`.agent/harden/hardening_branch_checkpoint/hardening_branch_checkpoint.{json,md}`.
Adds no model call, patch apply, validation run, benchmark run, MCP invocation,
worker launch, Dream execution, Replay janitor apply, Docker/subprocess use,
network call, database write, route behavior change, auth policy change, UI
behavior change, push, merge, or PR power. MIRROR.1 through MIRROR.CLOSE3 and
CMD.N1, CMD.N2, CMD.N3, CMD.N4, and CMD.N5 have since shipped; next likely: CMD.N6 - Commander Assignment Review Pack.

**MIRROR.1 - Mirror Tunnel Trace Contract is shipped 2026-06-29 (complete).**
Implemented as `core/mirror_tunnel_trace_contract.py` +
`scripts/create_mirror_tunnel_trace_contract.py`, registered as a `complete`
MIRROR-track phase (prerequisite HARDEN.CLOSE) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_trace_contract.py`. It reads explicit existing
artifact paths and writes
`.agent/mirror_tunnel/trace_contract/mirror_tunnel_trace_contract.{json,md}`.
The contract records canonical frame order, frame schema, available and missing
evidence, reusable and excluded context, trust level, artifact references,
boundaries, and `recommended_next_phase = MIRROR.2`. It does not call models,
apply patches, run validation, run benchmarks, invoke MCP tools, launch workers,
execute Dream actions, apply Replay janitor actions, use Docker or subprocess,
contact network services, write to a database, change route behavior, change
auth policy, change UI behavior, score derailment, push, merge, or open PRs.

**MIRROR.2 - Mirror Tunnel Derailment Score Report is shipped 2026-06-29 (complete).**
Implemented as `core/mirror_tunnel_derailment_score.py` +
`scripts/create_mirror_tunnel_derailment_score.py`, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.1) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_derailment_score.py`. It reads a MIRROR.1 trace
contract and writes
`.agent/mirror_tunnel/derailment_score/mirror_tunnel_derailment_score.{json,md}`.
The score report uses deterministic heuristics only across intent drift, scope
drift, evidence loss, claim/action mismatch, validation gap, and confidence
inflation, then emits weighted verdicts and recommended next actions. It does
not call models, use embeddings or semantic APIs, apply patches, run validation,
run benchmarks, invoke MCP tools, launch workers, execute Dream actions, apply
Replay janitor actions, use Docker or subprocess, contact network services,
write to a database, change route behavior, change auth policy, block execution,
push, merge, or open PRs. Recommended next phase: MIRROR.3.

**MIRROR.3 - Claim-vs-Diff Mirror Check is shipped 2026-06-29 (complete).**
Implemented as `core/mirror_tunnel_claim_diff_check.py` +
`scripts/create_mirror_tunnel_claim_diff_check.py`, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.2) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_claim_diff_check.py`. It reads a MIRROR.1 trace
contract, an optional MIRROR.2 derailment score report, and optional explicit
evidence files (`--patch-json`, `--diff`, `--validation-json`,
`--benchmark-json`, `--final-answer-file`, `--worker-reply-file`), then writes
`.agent/mirror_tunnel/claim_diff_check/mirror_tunnel_claim_diff_check.{json,md}`.
The report detects changed-file, no-change, validation, benchmark, test, safety,
scope, completion, and uncertainty claims, compares them against patch/diff,
artifact, validation, benchmark, replay, and safety evidence, and emits matches,
mismatches, unsupported claims, honest uncertainty claims, and a recommended next
action. It does not call models, use embeddings or semantic APIs, apply patches,
run validation, run benchmarks, invoke MCP tools, launch workers, execute Dream
actions, apply Replay janitor actions, use Docker or subprocess, contact network
services, write to a database, change route behavior, change auth policy, block
execution, push, merge, or open PRs. At shipment, its recommended next phase was
MIRROR.4; MIRROR.4 through MIRROR.CLOSE3, CMD.N1, and CMD.N2 have since shipped, so the
current recommended next phase is CMD.N6.

**MIRROR.4 - Real Run Trace Ingestion Plan is shipped 2026-06-29 (complete).**
Implemented as `core/mirror_tunnel_ingestion_plan.py` +
`scripts/create_mirror_tunnel_ingestion_plan.py`, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.3) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_ingestion_plan.py`. It writes
`.agent/mirror_tunnel/ingestion_plan/mirror_tunnel_ingestion_plan.{json,md}`.
The plan inventories artifact sources such as raw query text, Goal Brief JSON,
mode-decision previews, control prompts, worker assignments/replies, patch
proposals, validation evidence, benchmark reports, replay artifacts, final
answers, and lesson cards; maps them to MIRROR.1 frame types with P0/P1/P2
priorities; names required fields; identifies gaps around final answers,
worker replies, control-prompt redaction, and real-run frame emission; and
recommends future integration points. It does not call models, apply patches,
run validation, run benchmarks, invoke MCP tools, launch workers, execute Dream
actions, apply Replay janitor actions, use Docker or subprocess, contact network
services, write to a database, change route behavior, change auth policy, enable
automatic Mirror tracing, block execution, push, merge, or open PRs.
At shipment, its recommended next phase was MIRROR.5; MIRROR.5, MIRROR.6, and
MIRROR.CLOSE, MIRROR.7, MIRROR.8, MIRROR.9, MIRROR.10, MIRROR.11, MIRROR.12,
and MIRROR.CLOSE3, CMD.N1, and CMD.N2 have since shipped, so the current recommended
next phase is CMD.N5.

**MIRROR.5 - Manual Trace Assembler is shipped 2026-06-29 (complete).**
Implemented as `core/mirror_tunnel_manual_trace_assembler.py` +
`scripts/create_mirror_tunnel_manual_trace.py`, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.4) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_manual_trace_assembler.py`. It writes a
MIRROR.1-compatible trace to
`.agent/mirror_tunnel/manual_trace/<trace_id>/mirror_tunnel_trace_contract.{json,md}`.
The assembler maps explicit operator-provided artifact paths such as
`--user-intent-file`, `--goal-brief-json`, `--control-prompt-file`,
`--patch-json`, `--diff-file`, `--validation-json`, `--benchmark-json`,
`--replay-json`, and `--final-answer-file` to fixed MIRROR.1 frame types,
records omitted optional inputs as missing evidence, preserves artifact
references, caps excerpts, stores per-frame manual trust levels, and rejects
unsafe, unreadable, traversal, secret, environment, token, key, or out-of-root
paths. It does not call models, apply patches, run validation, run benchmarks,
invoke MCP tools, launch workers, execute Dream actions, apply Replay janitor
actions, use Docker or subprocess, contact network services, write to a
database, change route behavior, change auth policy, enable automatic live
tracing, block execution, push, merge, or open PRs. MIRROR.6 and MIRROR.CLOSE
have since shipped, MIRROR.7 has added default-off shadow trace writing, and
MIRROR.8 has added post-run scoring previews, MIRROR.9 has added the operator
panel plan, MIRROR.10 has added the read-only UI stub, MIRROR.11 has added the
artifact loader preview, MIRROR.12 has added the live demo readiness checker,
and MIRROR.CLOSE3 has frozen the live/UI slice. CMD.N1 and CMD.N2 have since shipped, so the
current recommended next phase is CMD.N6.

**MIRROR.6 - Manual Trace Score Pipeline is shipped 2026-06-30 (complete).**
Implemented as `core/mirror_tunnel_manual_review_pipeline.py` +
`scripts/create_mirror_tunnel_manual_review.py`, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.5) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_manual_review_pipeline.py`. It reads a manually
assembled MIRROR.5/MIRROR.1 trace, optionally reads existing MIRROR.2 and
MIRROR.3 JSON reports, otherwise calls the MIRROR.2 and MIRROR.3 pure Python
builders directly, and writes
`.agent/mirror_tunnel/manual_review/<review_id>/mirror_tunnel_manual_review.{json,md}`.
The combined review pack summarizes trace status and frame coverage,
derailment verdict/score, claim support verdict, strongest drift dimensions,
mismatches, unsupported claims, missing evidence, human-review notes, and a
recommended next action. It does not call models, apply patches, run validation,
run benchmarks, invoke MCP tools, launch workers, execute Dream actions, apply
Replay janitor actions, use Docker or subprocess, contact network services,
write to a database, change route behavior, change auth policy, enable live
runtime tracing, shell out to CLI scripts, block execution, push, merge, or open
PRs. MIRROR.CLOSE, MIRROR.7, MIRROR.8, MIRROR.9, MIRROR.10, MIRROR.11,
MIRROR.12, MIRROR.CLOSE3, CMD.N1, and CMD.N2 have since shipped; current recommended
next phase: CMD.CLOSE.

**MIRROR.CLOSE - Mirror Tunnel Branch Checkpoint is shipped 2026-06-30 (complete).**
Implemented as `core/mirror_tunnel_branch_checkpoint.py` +
`scripts/create_mirror_tunnel_branch_checkpoint.py`, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.6) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_branch_checkpoint.py`. It reads the phase registry,
MIRROR.1-MIRROR.6 source modules, existing Mirror Tunnel artifacts, and manual
trace/review artifacts, then writes
`.agent/mirror_tunnel/branch_checkpoint/mirror_tunnel_branch_checkpoint.{json,md}`.
The checkpoint verifies the manual evidence loop is complete, reports current
weak real-trace quality as manual-review warnings, confirms no live runtime
instrumentation has been added, and freezes the manual branch before live trace
writer work. It does not call models, apply patches, run validation, run
benchmarks, invoke MCP tools, launch workers, execute Dream actions, apply
Replay janitor actions, use Docker or subprocess, contact network services,
write to a database, change route behavior, change auth policy, enable live
runtime tracing, block execution, push, merge, or open PRs. MIRROR.8, MIRROR.9,
MIRROR.10, MIRROR.11, MIRROR.12, MIRROR.CLOSE3, CMD.N1, CMD.N2, CMD.N3, CMD.N4, CMD.N5, and CMD.N6 have since shipped;
recommended next phase: CMD.CLOSE.

**MIRROR.7 - Shadow Live Trace Writer is shipped 2026-06-30 (complete).**
Implemented as `core/mirror_tunnel_shadow_live_trace.py`, wired only into the
`web.runner.run_agent_web` final-result boundary, registered as a `complete`
MIRROR-track phase (prerequisite MIRROR.CLOSE) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_shadow_live_trace.py`. It is default-off via
`MIRROR_TUNNEL_SHADOW_TRACE_ENABLED=false`; when disabled, it writes nothing and
returns the original web result shape unchanged. When explicitly enabled, it
writes only passive artifacts:
`.agent/mirror_tunnel/live_traces/<run_id>/mirror_tunnel_trace_contract.{json,md}`.
It does not call models, change prompts, apply patches, run validation, run
benchmarks, invoke MCP tools, launch workers, execute Dream actions, apply
Replay janitor actions, use Docker or subprocess, contact network services,
write to a database, change route behavior, change auth policy, block execution,
score during the run, run claim-vs-diff checks during the run, push, merge, or
open PRs. MIRROR.8, MIRROR.9, MIRROR.10, MIRROR.11, MIRROR.12, MIRROR.CLOSE3,
CMD.N1, CMD.N2, CMD.N3, CMD.N4, CMD.N5, and CMD.N6 have since shipped; recommended next phase: CMD.CLOSE.

**MIRROR.8 - Live Trace Scoring Preview is shipped 2026-06-30 (complete).**
Implemented as `core/mirror_tunnel_live_trace_scoring_preview.py` +
`scripts/create_mirror_tunnel_live_trace_scoring_preview.py`, registered as a
`complete` MIRROR-track phase (prerequisite MIRROR.7) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_live_trace_scoring_preview.py`. It reads an existing
MIRROR.7 live trace or MIRROR.1-compatible trace JSON, calls the MIRROR.2 and
MIRROR.3 pure core builders directly, reuses MIRROR.6-style aggregation through
the pure core builder, and writes
`.agent/mirror_tunnel/live_trace_scoring_preview/<preview_id>/mirror_tunnel_live_trace_scoring_preview.{json,md}`.
It does not call CLI scripts, run during the original web run, call the MIRROR.7
live writer, mutate live trace artifacts, call models, apply patches, run
validation, run benchmarks, invoke MCP tools, launch workers, execute Dream
actions, apply Replay janitor actions, use Docker or subprocess, contact network
services, write to a database, change route behavior, change auth policy, block
runs, score during runtime, push, merge, or open PRs. MIRROR.9 through
MIRROR.CLOSE3, CMD.N1, CMD.N2, CMD.N3, CMD.N4, CMD.N5, and CMD.N6 have since shipped; current recommended next phase: CMD.CLOSE.

**MIRROR.9 - Live Trace Operator Report Panel Plan is shipped 2026-06-30 (complete).**
Implemented as `core/mirror_tunnel_operator_panel_plan.py` +
`scripts/create_mirror_tunnel_operator_panel_plan.py`, registered as a
`complete` MIRROR-track phase (prerequisite MIRROR.8) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_operator_panel_plan.py`. It defines how MIRROR.7 live
traces and MIRROR.8 scoring previews should appear to the operator: panel
purpose, placement in Evidence Cards / Review or Advanced / Debug areas, visible
fields, collapsed debug fields, warning language, non-blocking policy, operator
actions, forbidden UI actions, status badge rules, evidence display rules, and
the next UI recommendation. It explicitly keeps Mirror Tunnel advisory only:
not an automatic judge, blocker, approval gate, or trust authority.

MIRROR.9 does not implement UI, call models, change prompts, apply patches, run
validation, run benchmarks, invoke MCP tools, launch workers, execute Dream
actions, apply Replay janitor actions, use Docker or subprocess, contact network
services, write to a database, change route behavior, change auth policy, block
runs, score during runtime, mutate traces or previews, hide Apply controls,
auto-trust results, auto-reject patches, push, merge, or open PRs. MIRROR.10,
MIRROR.11, MIRROR.12, MIRROR.CLOSE3, CMD.N1, and CMD.N2 have since shipped; recommended
next phase: CMD.CLOSE.

**MIRROR.10 - Operator Panel Read-only UI Stub is shipped 2026-07-02 (complete).**
Implemented in `web/templates/index.html` and `web/static/style.css`,
registered as a `complete` MIRROR-track phase (prerequisite MIRROR.9) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_operator_panel_ui.py`. It adds a read-only Mirror
Tunnel panel in the Evidence Cards area with the advisory note, empty-state
badge, visible summary fields, collapsed details, raw JSON placeholder, local
render helper, and copy-only actions.

MIRROR.10 does not add backend routes, call models, change prompts, apply
patches, run validation, run benchmarks, invoke MCP tools, launch workers,
execute Dream actions, apply Replay janitor actions, use Docker or subprocess,
contact network services, write to a database, change route behavior, change
auth policy, score during runtime, mutate live traces, hide Apply controls,
block execution, push, merge, or open PRs. MIRROR.11, MIRROR.12, MIRROR.CLOSE3,
and CMD.N1, CMD.N2, CMD.N3, CMD.N4, CMD.N5, and CMD.N6 have since shipped; recommended next phase: CMD.CLOSE.

**MIRROR.11 - Operator Panel Artifact Loader Preview is shipped 2026-07-02 (complete).**
Implemented in `web/templates/index.html`, `web/static/style.css`, and
`web/app.py`, registered as a `complete` MIRROR-track phase (prerequisite
MIRROR.10) in `docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_operator_panel_loader.py`. It adds a sanitized
GET-only `/mirror-tunnel/preview/<preview_id>` route that reads only an existing
MIRROR.8 preview JSON from
`.agent/mirror_tunnel/live_trace_scoring_preview/<preview_id>/mirror_tunnel_live_trace_scoring_preview.json`,
then renders status, trace/run ids, derailment verdict and score, claim support,
missing evidence count, warnings, artifact paths, and raw JSON into the existing
read-only Mirror Tunnel panel.

MIRROR.11 does not POST, generate MIRROR.8 previews, call MIRROR.2/MIRROR.3
builders, call the MIRROR.7 live writer, score traces, mutate live trace or
preview artifacts, alter Submit / Apply / Patch / Validation behavior, run
validation or benchmarks, call models, invoke MCP tools, launch workers, apply
patches, block Apply controls, change auth policy, write to the database, use
Docker/subprocess, contact the network, push, merge, or open PRs.

**MIRROR.12 - Mirror Tunnel Live Trace Demo Run / Readiness Check is shipped 2026-07-02 (complete).**
Implemented as `core/mirror_tunnel_live_demo_readiness.py` +
`scripts/create_mirror_tunnel_live_demo_readiness.py`, registered as a
`complete` MIRROR-track phase (prerequisite MIRROR.11) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_live_demo_readiness.py`. MIRROR.12 inspects an
existing MIRROR.7 live trace, an existing MIRROR.8 preview, and MIRROR.11
preview-id loader compatibility, then writes a report-only readiness verdict
for one manually controlled demo run.

**MIRROR.CLOSE3 - Mirror Tunnel Live UI Readiness Checkpoint is shipped 2026-07-02 (complete).**
Implemented as `core/mirror_tunnel_live_ui_readiness_checkpoint.py` +
`scripts/create_mirror_tunnel_live_ui_readiness_checkpoint.py`, registered as a
`complete` MIRROR-track phase (prerequisite MIRROR.12) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_mirror_tunnel_live_ui_readiness_checkpoint.py`. MIRROR.CLOSE3
freezes the MIRROR.7 through MIRROR.12 live trace and read-only UI readiness
chain while preserving advisory/non-blocking policy. It writes
`.agent/mirror_tunnel/live_ui_readiness_checkpoint/mirror_tunnel_live_ui_readiness_checkpoint.{json,md}`.
It does not execute demos, generate previews, score traces, mutate artifacts,
change UI behavior, or add approval gates.

**CMD.N1 - Boss Half-Life Fracture Plan is shipped 2026-07-02 (complete).**
Implemented as `core/boss_half_life_fracture_plan.py` +
`scripts/create_boss_half_life_fracture_plan.py`, registered as a `complete`
CMD-track phase (prerequisite MIRROR.CLOSE3) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_boss_half_life_fracture_plan.py`. CMD.N1 defines the deterministic
Boss Half-Life Fracture model:
`B_t = B_0 * (1/2) ** (t / H)`, `H = T / k`, default `T=6`, `k=2`, `H=3`,
and `tolerance=0.20`. It computes `fracture_pressure =
actual_remaining / expected_remaining` and classifies the boss as
`ahead_of_decay`, `on_track`, `review_recommended`,
`fracture_recommended`, `hard_fracture_required`, or `invalid_parameters`.
Artifacts: `.agent/commander/boss_half_life_fracture_plan/boss_half_life_fracture_plan.{json,md}`.
No task decomposition, worker assignment, model call, Commander launch, routing
change, patch apply, validation run, benchmark run, MCP invocation, Dream
execution, Replay janitor apply, Docker/subprocess use, network call, database
write, auth policy change, push, merge, or PR power was added.

**CMD.N2 - Manual Boss Fracture Report is shipped 2026-07-02 (complete).**
Implemented as `core/manual_boss_fracture_report.py` +
`scripts/create_manual_boss_fracture_report.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.N1), and validated with
`tests/test_manual_boss_fracture_report.py`. CMD.N2 applies the CMD.N1
half-life model to one manually described boss, validates optional manual
sub-boss candidates, compares their expected complexity sum against
`actual_remaining`, and writes
`.agent/commander/manual_boss_fracture_report/<boss_id>/manual_boss_fracture_report.{json,md}`.
It remains report-only: no model call, automatic decomposition, worker
assignment, routing, validation run, benchmark run, patch apply, network call,
database write, route behavior change, auth policy change, push, merge, or PR
power was added.

**CMD.N3 - Commander Fracture Tree Schema / Registry is shipped 2026-07-02 (complete).**
Implemented as `core/commander_fracture_tree_registry.py` +
`scripts/create_commander_fracture_tree_registry.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.N2), and validated with
`tests/test_commander_fracture_tree_registry.py`. CMD.N3 validates durable
manual fracture tree registries from a CMD.N2 report, a manual tree JSON file,
or minimal CLI metadata. It records safe IDs, parent references, dependency
edges, dependency cycles, complexity and attempt budgets, advisory-only role
labels, path safety, validation status, warnings, and blockers, then writes
`.agent/commander/fracture_tree_registry/<tree_id>/commander_fracture_tree_registry.{json,md}`.
It remains report-only: no sub-boss execution, real worker assignment, model
call, Commander launch, routing, validation run, benchmark run, patch apply,
network call, database write, route behavior change, auth policy change, push,
merge, or PR power was added.

**CMD.N4 - Commander Preflight Contract is shipped 2026-07-02 (complete).**
Implemented as `core/commander_preflight_contract.py` +
`scripts/create_commander_preflight_contract.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.N3), and validated with
`tests/test_commander_preflight_contract.py`. CMD.N4 reads a CMD.N3 fracture
tree registry artifact, evaluates one or all manually registered sub-bosses,
checks preflight status, dependency readiness, bounded file scope, evidence
requirements, rollback boundaries, default advisory policies, hidden auto flags,
and executable-worker bindings, then writes
`.agent/commander/preflight_contract/<tree_id>/commander_preflight_contract.{json,md}`.
It remains report-only: no sub-boss execution, real worker assignment, model
call, Commander launch, routing, execution eligibility mutation, validation run,
benchmark run, patch apply, network call, database write, route behavior change,
auth policy change, push, merge, or PR power was added.

**CMD.N5 - Commander Manual Assignment Plan is shipped 2026-07-03 (complete).**
Implemented as `core/commander_manual_assignment_plan.py` +
`scripts/create_commander_manual_assignment_plan.py`, registered as a `complete`
CMD-track phase (prerequisite CMD.N4), and validated with
`tests/test_commander_manual_assignment_plan.py`. CMD.N5 reads a CMD.N4
preflight contract artifact and optional manual advisory role catalog, assigns
role labels for review/preparation only, and writes
`.agent/commander/manual_assignment_plan/<tree_id>/commander_manual_assignment_plan.{json,md}`.
It remains report-only: no worker launch, executable worker binding, real model
binding, model call, routing change, source preflight/tree mutation, patch apply,
validation run, benchmark run, network call, database write, route behavior
change, auth policy change, push, merge, or PR power was added.

**EVAL.N1 - Evidence Quality Planning is shipped 2026-07-05 (complete).**
Implemented as `core/evidence_quality_plan.py` +
`scripts/create_evidence_quality_plan.py`, registered as a `complete`
EVAL-track phase (prerequisite MODEL.CLOSE), and validated with
`tests/test_evidence_quality_plan.py`. EVAL.N1 writes
`.agent/eval/evidence_quality_plan/evidence_quality_plan.{json,md}` and defines
evidence quality dimensions, future verdicts, future score fields, freshness
rules, claim-vs-evidence rules, validation/benchmark relevance rules, missing
evidence rules, confidence alignment rules, human review boundaries, and
guardrails. It remains planning-only: no validation run, benchmark run, model
call, patch apply, scoring-gate change, MCP invocation, worker launch, network
call, database write, route/auth change, or automatic approval/rejection power
was added.

**EVAL.N2 - Evidence Quality Report Contract is shipped 2026-07-05 (complete).**
Implemented as `core/evidence_quality_report_contract.py` +
`scripts/create_evidence_quality_report_contract.py`, registered as a
`complete` EVAL-track phase (prerequisite EVAL.N1), and validated with
`tests/test_evidence_quality_report_contract.py`. EVAL.N2 writes
`.agent/eval/evidence_quality_report_contract/evidence_quality_report_contract.{json,md}`
and defines the first deterministic report contract for existing evidence
artifacts: source artifact inventory, claim inventory, evidence inventory,
dimension reviews, missing evidence, contradiction risks, freshness findings,
confidence alignment, scope alignment, and human review boundaries. It remains
artifact-inspection-only: no validation run, benchmark run, model call, patch
apply, scoring-gate change, MCP invocation, worker launch, network call,
database write, route/auth change, or automatic approval/rejection power was
added.

**EVAL.N3 - Evidence Quality Report Builder is shipped 2026-07-05 (complete).**
Implemented as `core/evidence_quality_report_builder.py` +
`scripts/create_evidence_quality_report.py`, registered as a `complete`
EVAL-track phase (prerequisite EVAL.N2), and validated with
`tests/test_evidence_quality_report_builder.py`. EVAL.N3 writes
`.agent/eval/evidence_quality_report/evidence_quality_report.{json,md}` and
builds an actual evidence quality report from explicitly supplied existing
artifacts using the EVAL.N2 contract. It remains artifact-inspection-only: no
validation run, benchmark run, model call, patch apply, scoring-gate change, MCP
invocation, worker launch, network call, database write, route/auth change, or
automatic approval/rejection power was added.

**EVAL.N4 - Evidence Quality Artifact Loader Plan is shipped 2026-07-05 (complete).**
Implemented as `core/evidence_quality_artifact_loader_plan.py` +
`scripts/create_evidence_quality_artifact_loader_plan.py`, registered as a
`complete` EVAL-track phase (prerequisite EVAL.N3), and validated with
`tests/test_evidence_quality_artifact_loader_plan.py`. EVAL.N4 planned the safe
artifact-loader/display layer for existing EVAL.N3 reports without adding a UI
panel, backend route, runtime artifact loading, validation, benchmarks, model
calls, patch application, scoring gates, or approval/rejection power.

**EVAL.N5 - Evidence Quality Read-only UI Stub is shipped 2026-07-06 (complete).**
Implemented in `web/templates/index.html` and `web/static/style.css`, registered
as a `complete` EVAL-track phase (prerequisite EVAL.N4), and validated with
`tests/test_evidence_quality_panel_ui.py`. EVAL.N5 added the inert advisory
Evidence Quality panel with empty state placeholders, visible summary fields,
collapsed debug placeholders, and read-only refresh/copy controls. It did not
add a backend loader, generate reports, run validation or benchmarks, call
models, apply patches, mutate evidence reports, or block Submit/Apply.

**EVAL.N6 - Evidence Quality GET-only Artifact Loader is shipped 2026-07-06 (complete).**
Implemented as a narrow GET-only route in `web/app.py` plus read-only loader
controls in the Evidence Quality panel, registered as a `complete` EVAL-track
phase (prerequisite EVAL.N5), and validated with
`tests/test_evidence_quality_panel_loader.py`. EVAL.N6 loads existing EVAL.N3
reports only from `.agent/eval/evidence_quality_report/`, supports the default
report and safe report-id subdirectories, blocks unsafe ids, and keeps the panel
advisory. It does not add mutation routes, generate reports, run validation or
benchmarks, call models, apply patches, approve/reject work, mutate evidence
reports, or block Submit/Apply.

**EVAL.N7 - Evidence Quality Loader Readiness Check is shipped 2026-07-06 (complete).**
Implemented as `core/evidence_quality_loader_readiness.py` +
`scripts/create_evidence_quality_loader_readiness.py`, registered as a
`complete` EVAL-track phase (prerequisite EVAL.N6), and validated with
`tests/test_evidence_quality_loader_readiness.py`. EVAL.N7 writes
`.agent/eval/evidence_quality_loader_readiness/evidence_quality_loader_readiness.{json,md}`
and verifies the EVAL.N6 GET loader and EVAL.N5/N6 UI remain safe, read-only,
non-blocking, and compatible with optional existing EVAL.N3 reports. It remains
report-only: no evidence quality report generation, validation run, benchmark
run, model call, patch apply, approval/rejection, evidence report mutation, or
Apply/Submit blocking power was added.

**EVAL.CLOSE - Evidence Quality Branch Checkpoint is shipped 2026-07-06 (complete).**
Implemented as `core/evidence_quality_branch_checkpoint.py` +
`scripts/create_evidence_quality_branch_checkpoint.py`, registered as a
`complete` EVAL-track phase (prerequisite EVAL.N7), and validated with
`tests/test_evidence_quality_branch_checkpoint.py`. EVAL.CLOSE writes
`.agent/eval/evidence_quality_branch_checkpoint/evidence_quality_branch_checkpoint.{json,md}`
and freezes EVAL.N1 through EVAL.N7 as advisory, report-only, non-blocking, and
free of runtime scoring, validation, benchmark, model, patch, approval, or
mutation authority.

**HUMAN.N1 - Human Review Boundary Map is shipped 2026-07-07 (complete).**
Implemented report-only as `core/human_review_boundary_map.py` +
`scripts/create_human_review_boundary_map.py`, registered as a `complete`
HUMAN-track phase (prerequisite EVAL.CLOSE) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_human_review_boundary_map.py`. HUMAN.N1 writes
`.agent/human/review_boundary_map/human_review_boundary_map.{json,md}` and maps
what the system may advise or display versus what only the human may approve,
reject, apply, merge, accept as risk, or treat as sufficient evidence. It does
not enforce approvals, call models, route models, launch workers, apply patches,
run validation or benchmarks, invoke MCP tools, execute Dream or Replay actions,
use Docker/subprocess, contact network services, write to a database, change
route/auth behavior, add scoring gates, approve/reject work, or block
Apply/Submit.

**HUMAN.N2 - Human Approval Token / Confirmation Contract is shipped 2026-07-07 (complete).**
Implemented report-only as `core/human_approval_token_contract.py` +
`scripts/create_human_approval_token_contract.py`, registered as a `complete`
HUMAN-track phase (prerequisite HUMAN.N1) in
`docs/roadmap/phase_registry.json`, and validated with
`tests/test_human_approval_token_contract.py`. HUMAN.N2 writes
`.agent/human/approval_token_contract/human_approval_token_contract.{json,md}`
and defines explicit human confirmation token fields, allowed approval actions,
target types, risk levels, scope, expiry, revocation, confirmation-text rules,
forbidden token behavior, and future enforcement boundaries. It does not enforce
approvals, validate live confirmations, issue tokens, call models, route models,
launch workers, apply patches, run validation or benchmarks, invoke MCP tools,
execute Dream or Replay actions, use Docker/subprocess, contact network
services, write to a database, change route/auth behavior, add scoring gates,
approve/reject work, or block Apply/Submit.

**HUMAN.N3 - Human Approval Token Dry-Run Validator is shipped 2026-07-07 (complete).**
Implemented report-only as `core/human_approval_token_dry_run_validator.py` +
`scripts/create_human_approval_token_dry_run.py`, registered as a `complete`
HUMAN-track phase (prerequisite HUMAN.N2) in `docs/roadmap/phase_registry.json`,
and validated with `tests/test_human_approval_token_dry_run_validator.py`.
HUMAN.N3 writes per-token dry-run artifacts under
`.agent/human/approval_token_dry_run/<token_id-or-sample>/human_approval_token_dry_run.{json,md}`
and reports whether a sample token would be valid, invalid, expired, revoked,
too generic, too broad, unsafe, or blocked in a future enforcement phase. It
does not authorize actions, reject live actions, enforce routes, issue or
consume tokens, apply patches, run validation or benchmarks, call models, route
models, invoke MCP tools, launch workers, write to a database, change auth or
route behavior, or block Apply/Submit.

**HUMAN.N4 - Human Approval Token Sample Catalog is shipped 2026-07-07 (complete).**
Implemented report-only as `core/human_approval_token_sample_catalog.py` +
`scripts/create_human_approval_token_sample_catalog.py` +
`tests/test_human_approval_token_sample_catalog.py`. HUMAN.N4 writes
documentation-only valid, warning, invalid, and blocked sample tokens plus a
JSON/Markdown catalog. The samples are not live approvals and authorize no
action.

**HUMAN.CLOSE - Human Authority Branch Checkpoint is shipped 2026-07-08 (complete).**
Implemented report-only as `core/human_authority_branch_checkpoint.py` +
`scripts/create_human_authority_branch_checkpoint.py` +
`tests/test_human_authority_branch_checkpoint.py`. HUMAN.CLOSE writes
`.agent/human/authority_branch_checkpoint/human_authority_branch_checkpoint.{json,md}`
and freezes HUMAN.N1-N4 before runtime enforcement, route integration, token
issuance/consumption, approval gates, patch apply, validation/benchmark
execution, worker launch, model routing, or auth policy changes. Current status:
`human_authority_branch_frozen_with_warnings`.

**ADOPT.MODEL.1 - Human-Approved Model Role Catalog Adoption is shipped 2026-07-08 (complete).**
ADOPT.MODEL.1 adopted the reviewed MODEL.N4 proposed 10-role advisory catalog as
the active artifact, backed up the previous 7-role registry, and wrote JSON plus
Markdown adoption receipts. It did not grant routing, model-call, worker-launch,
executable-binding, validation, benchmark, patch, network, database, route/auth,
approval-token, or automatic authority.

**ADOPT.MODEL.2 - Post-Adoption Role Coverage Recheck is shipped 2026-07-08 (complete).**
ADOPT.MODEL.2 verified the active 10-role advisory catalog, confirmed the
previous MODEL.N3 gaps for `ui_reviewer`, `test_designer`, and
`documentation_reviewer` are resolved, preserved the original 7 roles, and wrote
JSON plus Markdown post-adoption coverage artifacts. It did not grant routing,
model-call, worker-launch, executable-binding, validation, benchmark, patch,
network, database, route/auth, approval-token, or automatic authority.

**ADOPT.MODEL.CLOSE - Model Catalog Adoption Branch Checkpoint is shipped 2026-07-08 (complete).**
ADOPT.MODEL.CLOSE froze the ADOPT model-catalog branch after artifact adoption
and post-adoption coverage verification. It confirmed the active 10-role
advisory catalog, the three added roles, resolved gaps, preserved prior roles,
HUMAN authority boundary reference, and all non-execution guardrails, remaining
report-only and checkpoint-only.

**HARDEN.N1 - Approval Enforcement Readiness Audit, HARDEN.N2 - Approval Enforcement Attachment Plan, and HARDEN.N3 - Approval Enforcement Dry-Run Gate Simulator are shipped 2026-07-08 (complete).**
The HARDEN.N1-N3 chain audited dangerous action surfaces, planned future
approval-token attachment points, and simulated sample approval-gate outcomes
without adding runtime enforcement, issuing or consuming tokens, changing
routes/auth, launching workers, calling models, or routing models.

**HARDEN.N4 - Approval Enforcement Operator Report is shipped 2026-07-08 (complete).**
HARDEN.N4 created a read-only operator-facing report format for simulated
approval-gate outcomes, still without runtime enforcement, live token
validation, token issuance or consumption, route/auth behavior changes, model
calls, model routing, worker launches, patch application, validation runs,
benchmark runs, network access, database writes, push, merge, or PR power.

**HARDEN.CLOSE - Approval Enforcement Planning Branch Checkpoint is shipped 2026-07-08 (complete).**
HARDEN.CLOSE froze HARDEN.N1-N4 as a complete non-enforcing
approval-enforcement planning branch. Its expected current status is
`approval_enforcement_planning_branch_frozen_with_warnings` because runtime
enforcement remains intentionally unimplemented.

**OPS.TEST.CLOSE - Test Runtime Operations Branch Checkpoint is shipped 2026-07-09 (complete).**
OPS.TEST.CLOSE froze OPS.TEST.1-OPS.TEST.3 as a complete test-runtime planning
branch. Its expected current status is
`test_runtime_operations_branch_frozen_with_warnings` because executable suite
manifest files and runner commands remain intentionally unimplemented.

**UX.RUN.1 - Run Progress / Operator Visibility is shipped 2026-07-09 (complete).**
UX.RUN.1 defines the read-only progress-stage contract/report, writes
`.agent/ux/run_progress_visibility/run_progress_visibility_report.json` and
`.agent/ux/run_progress_visibility/run_progress_visibility_report.md`, and keeps
live streaming/polling as future work. Its expected current status is
`run_progress_visibility_ready_with_warnings`.

**UX.RUN.2 - Run Progress Snapshot Loader is shipped 2026-07-10 (complete).**
UX.RUN.2 adds `core/run_progress_snapshot_loader.py`,
`scripts/create_run_progress_snapshot_loader_report.py`,
`tests/test_run_progress_snapshot_loader.py`, and the GET-only route
`/ux/run-progress/snapshot/<snapshot_id>`. It loads existing progress snapshot
or UX.RUN.1 report artifacts read-only, rejects unsafe ids/paths/extensions,
returns safe missing/malformed/blocked JSON states, and writes
`.agent/ux/run_progress_snapshot_loader/run_progress_snapshot_loader_report.json`
and `.agent/ux/run_progress_snapshot_loader/run_progress_snapshot_loader_report.md`.
Its expected current status is `run_progress_snapshot_loaded_with_warnings`
because live progress streaming remains intentionally unimplemented.

**UX.RUN.3 - Run Progress UI Panel Stub is shipped 2026-07-10 (complete).**
UX.RUN.3 adds a compact read-only UI panel that displays operator-selected
progress snapshots through the existing GET-only loader. It does not add live
streaming, polling, POST routes, action buttons, runtime behavior changes, model
calls, worker launches, patch application, or validation/benchmark execution.
Its expected current status is `run_progress_ui_panel_ready_with_warnings`
because live progress streaming remains intentionally unimplemented.

**UX.RUN.CLOSE - Run Progress Visibility Branch Checkpoint is shipped 2026-07-10 (complete).**
UX.RUN.CLOSE reads the UX.RUN.1 visibility contract, UX.RUN.2 loader report, and
UX.RUN.3 static UI markers, then writes `.agent/ux/run_progress_visibility_branch_checkpoint/`
JSON and Markdown artifacts. Its expected current status is
`run_progress_visibility_branch_frozen_with_warnings` because live streaming and
instrumentation remain intentionally unimplemented. It does not add any runtime
behavior, polling, POST routes, action controls, model or worker controls, patch
application, validation/benchmark execution, approval enforcement, or tokens.

**UX.LIVE.1 - Run Progress Instrumentation Plan is shipped 2026-07-10 (complete).**
UX.LIVE.1 described possible
future instrumentation sources, update cadence options, and human review
boundaries, but it must not implement live hooks, polling, or runtime behavior.

**UX.LIVE.7 - Snapshot Freshness and Staleness Plan is shipped 2026-07-11 (complete).**
UX.LIVE.7 writes a report-only contract for advisory classification of approved
snapshot metadata as fresh, recent, terminal, stale, possibly abandoned,
unknown, or invalid. It defines timezone-aware UTC handling, safe threshold
defaults, terminal precedence, clock-skew and malformed timestamp policies,
sequence supporting evidence, warning codes, and the future classifier result
schema. It does not change the writer, loader route, browser behavior, manual
refresh, polling, streaming, retries, cleanup, runtime execution, or snapshot
artifacts. Its expected status is `run_progress_freshness_plan_ready_with_warnings`.

**UX.LIVE.8 - Freshness Classification Implementation is shipped 2026-07-11 (complete).**
UX.LIVE.8 adds a pure deterministic advisory classifier for safe loaded
snapshots, returns its derived result beside the existing GET-only loader
response, and displays freshness, age at load time, terminal outcome, notice,
and warnings in the existing panel. It does not write canonical snapshots or
add polling, timers, background requests, runtime authority, retries,
cancellation, restart, or execution controls. Its expected status is
`run_progress_freshness_ready_with_warnings` because displayed freshness is
recalculated only on an operator's manual load or refresh.

**UX.LIVE.9 - Bounded Progress Polling Experiment Plan is shipped 2026-07-12 (complete).**
UX.LIVE.9 writes a report-only contract for a future default-off experiment:
explicit operator activation, existing GET-only loader reuse, a two-second
minimum and three-second default interval, finite five-minute/100-request/three-
error bounds, one request at a time, terminal and association-change stops,
hidden-tab pause, bounded normal-interval error handling, page-local session
state, and accessible advisory statuses. It adds no timer, browser request,
background refresh, automatic retry, browser control, route, writer, loader,
runtime, snapshot, or execution behavior. Its expected status is
`run_progress_polling_plan_ready_with_warnings` because browser dogfooding
remains future work.

**UX.LIVE.10 - Optional Default-Off Bounded Progress Polling is shipped 2026-07-12 (complete).**
UX.LIVE.10 adds a default-off, page-local browser reader behind an explicit
Start progress updates control. It reuses the existing GET-only snapshot loader,
uses one in-flight guard and chained one-shot timeouts, counts finite duration,
request, and consecutive-error bounds, and stops deterministically for terminal,
association, safety, hidden-tab, page-unload, and operator conditions. It does
not supervise or affect the underlying run, writer, snapshot lifecycle, runtime,
or approval state. Its expected status is
`bounded_run_progress_polling_ready_with_warnings` pending operator dogfooding.

**UX.LIVE.CLOSE - Live Run Progress Branch Checkpoint shipped 2026-07-12 (complete).**
UX.LIVE.CLOSE audits UX.LIVE.1 through UX.LIVE.10 and freezes the branch with
warnings. It certifies truthful partial progress visibility—not complete runtime
tracing—while retaining default-off writer and polling configuration, advisory
GET-only observation, bounded browser polling, and no runtime authority.

**HARDEN.PROGRESS.1 - Early Error Terminal Snapshot Coverage shipped 2026-07-13 (complete).**
HARDEN.PROGRESS.1 is a narrow corrective phase outside the frozen UX.LIVE branch.
It observes the genuine early application-error return boundary after
`request_received`, reuses the existing safe progress run ID, and records one
terminal `error_reported` update with monotonic sequence and deterministic
duplicate handling. The original application error result remains authoritative
and unchanged, and writer failure remains isolated from that result. No UI,
polling, freshness, retry, execution, or default behavior changed; no raw error
message or path is stored. Its status is
`early_error_terminal_coverage_ready_with_warnings`, with no blocker and one
warning: a genuine post-fix operator repeat must still be collected separately
under DOGFOOD.1B. Artifacts:
`.agent/hardening/run_progress_early_error_terminal/run_progress_early_error_terminal.{json,md}`.
The phase picker therefore returns to DOGFOOD.1B.

**DOGFOOD.1B - Real Operator Run Evaluation is proposed.**
DOGFOOD.1B is the current picker recommendation. It remains report-only initially
and should evaluate real operator runs: progress comprehension, freshness-label
utility, manual-refresh sufficiency, bounded-polling usefulness, default-off
discoverability, mistaken validation/approval inference, and whether stage
coverage needs expansion. It must not activate or extend the branch.

**MIRROR.13 - Live Trace Frame Capture Quality Plan is proposed.**
MIRROR.13 remains the next registered MIRROR candidate. It should plan how to
improve live trace frame capture quality after the MIRROR.CLOSE3 freeze, while
keeping Mirror evidence report-only, advisory, non-blocking, and free of runtime
scoring or UI approval-gate behavior. The current top picker recommendation is
DOGFOOD.1B.

**UX.1 — Operator Cockpit & Idea Intake Plan is shipped 2026-06-24 (complete).**
Implemented report-only as `core/operator_cockpit_plan.py` +
`scripts/create_operator_cockpit_plan.py`, registered as a `complete`
UX-track phase (prerequisite HARDEN.1) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_operator_cockpit_plan.py`. It builds a deterministic UX
planning report inventorying 8 pain points, a 5-step operator workflow (Start/Run/Review/
Continue/Learn), 10 cockpit sections (Task Bar, Mode Decision, Run Timeline, etc.),
primary/advanced/debug action maps, an idea intake board (use_now/prototype_later/park/block),
metaphor placement for 4W1H/Navier-Stokes/Excavator, and a UX roadmap proposal (UX.1–UX.6).
Artifacts: `.agent/ux/operator_cockpit_plan/operator_cockpit_plan.{json,md}`. It adds no
UI implementation, backend behavior change, task execution, agent launch, model call,
patch apply, validation run, benchmark run, network call, database write, worker launch,
push, merge, or PR power.

**ROAD.4 — Post-EVAL/CMD Checkpoint Audit is shipped 2026-06-23 (complete).**
Implemented report-only as `core/post_eval_cmd_checkpoint_audit.py` +
`scripts/create_post_eval_cmd_checkpoint_audit.py`, registered as a `complete`
ROAD-track phase (prerequisite CMD.4) in `docs/roadmap/phase_registry.json`, and
validated with `tests/test_post_eval_cmd_checkpoint_audit.py`. It reads the
phase registry, EVAL.1–3 artifact roots, CMD.1–4 artifact roots, and project
documentation, then writes
`.agent/roadmap/post_eval_cmd_checkpoint/post_eval_cmd_checkpoint_audit.{json,md}`
verifying that all seven required phases are registered, complete, report-only,
artifact-backed, and documented. Audit statuses: `pass`, `pass_with_warnings`,
`blocked`. It adds no model call, patch apply, validation run, benchmark run,
network call, database write, worker launch, push, merge, or PR power.

Purpose:

Track full benchmark runs as artifacts so operators can understand benchmark health over time instead of treating each run as an isolated event.

The ledger should record:

- Run id.
- Timestamp.
- Model config.
- Pass/fail per case.
- Duration.
- Fallback count.
- Token/cost summary.
- Failed cases.
- Rerun evidence.
- Flake classification.

Boundary:

- Reads benchmark reports.
- Writes ledger/report.
- Does not run benchmarks itself.
- Does not call models.
- Does not patch code.
- Does not alter benchmark cases.

Expected first shape:

- A report-only phase.
- Deterministic parsing of existing benchmark report artifacts.
- Backward-compatible handling for older benchmark reports.
- Clear classification of confirmed failures, isolated rerun passes, and unresolved flakes.
- Tests only if they fit the existing documentation/reporting pattern for this repository and do not require runtime behavior changes.

## 7. Parking Lot

- Commander Mode execution beyond the CMD.1 report-only contract.
- Model Lab specialist models.
- Remote execution unlock.
- Cross-district architecture.
- Biology/Math/Physics inspiration districts.
- AI-agent-as-customer idea.

These ideas remain useful but are not selected by NEXT.1. They should not be smuggled into EVAL.1 or any first branch phase without explicit approval.

## 8. Decision Rule

Before implementing any branch:

- Create a machine-readable phase entry.
- Require explicit human approval.
- Prefer report-only first.
- Validate with tests.
- Update the ROAD picker only after the new map is accepted.

The branch selector should be treated as a map, not permission to execute. Each branch still requires a concrete phase proposal, a registry entry, and human acceptance before implementation begins.

## 9. Boundary Statement

This roadmap does not authorize live autonomy.

This roadmap does not authorize remote execution.

This roadmap does not authorize auto-merge.

This roadmap does not authorize model authority.

It only defines the next candidate map.

## HARDEN Track

HARDEN phases add defensive hardening to the CATTUS web app. They do not redesign the app, add new automation power, call models, contact network services, run validation, apply patches, push, merge, or open PRs.

### HARDEN.1 — Web Mutation Auth / CSRF Gate

**Status:** Complete  
**Prerequisite:** ROAD.4  
**Risk:** Medium (modifies web/app.py before_request behavior)

Adds a centralized `@app.before_request` security gate to the Flask web app. For safe HTTP methods (GET, HEAD, OPTIONS), all requests are allowed. For mutating methods (POST, PUT, PATCH, DELETE):

- If `WEB_AUTH_TOKEN` is set: all mutating requests require a matching token in `X-CATTUS-Web-Token` or `Authorization: Bearer <token>`.
- If `WEB_AUTH_TOKEN` is not set: mutating requests are allowed only from loopback addresses (127.0.0.1, ::1, localhost); all others receive 403.
- Cross-origin mutating requests are always rejected (Origin/Referer CSRF check).

**New env vars:**
- `WEB_AUTH_TOKEN` — token for web mutation auth; unset means loopback-only
- `WEB_SECRET_KEY` — Flask secret key; generates a dev-only placeholder if unset

**New files:**
- `web/auth_gate.py` — pure gate helpers, GateDecision dataclass
- `tests/test_web_mutation_auth_gate.py` — 21-test suite (15 cases)

**No new automation power.** Does not run models, apply patches, validate, benchmark, contact network services, push, merge, or open PRs.

### HARDEN.2 — Web Mutation Surface Audit

**Status:** Complete  
**Prerequisites:** UX.CLOSE, HARDEN.1  
**Risk:** Medium (security audit of route mutation surface; report-only)

Creates a report-only inventory of all Flask routes from the registered app
route map. Routes are classified by safe methods (GET, HEAD, OPTIONS), mutating
methods (POST, PUT, PATCH, DELETE), mixed method surfaces, high-risk route
keywords, and category hints including artifact-writing, validation-running,
benchmark-running, worker-launching, replay/janitor-related, and
external-integration-related.

**Artifacts:**
- `.agent/harden/web_mutation_surface_audit/web_mutation_surface_audit.json`
- `.agent/harden/web_mutation_surface_audit/web_mutation_surface_audit.md`

**No new automation power.** Does not call handlers, run models, apply patches,
validate, benchmark, launch workers, execute Dream actions, apply Replay janitor
actions, contact network services, write to a database, change routes, change
auth policy, change UI behavior, push, merge, or open PRs.

### HARDEN.3 — Safe Validation / MCP Approval Enforcement Audit

**Status:** Complete  
**Prerequisite:** HARDEN.2  
**Risk:** Medium (security audit of execution and approval surfaces; report-only)

Creates a report-only static source audit for validation execution, MCP/tool
artifact actions, janitor/apply/delete cleanup paths, approval-sensitive fields,
and route metadata. The report inventories audited files, routes, functions,
validation surfaces, MCP surfaces, janitor or cleanup surfaces, and approval
gate surfaces. It distinguishes blockers from manual-review warnings and records
gate evidence such as safe validation helpers, command safety checks,
temp-clone/sandbox boundaries, MCP tool allowlists, audit logging, confirmation
tokens, HARDEN.1 auth coverage, and human-approval policy fields.

**Artifacts:**
- `.agent/harden/safe_validation_mcp_approval_audit/safe_validation_mcp_approval_audit.json`
- `.agent/harden/safe_validation_mcp_approval_audit/safe_validation_mcp_approval_audit.md`

**No new automation power.** Does not import audited application modules, call
handlers, invoke MCP tools, run models, apply patches, validate, benchmark,
launch workers, execute Dream actions, apply Replay janitor actions, contact
network services, write to a database, change routes, change auth policy, change
UI behavior, push, merge, or open PRs.

### HARDEN.CLOSE - Approval Enforcement Planning Branch Checkpoint

**Status:** Complete
**Prerequisite:** HARDEN.N4
**Risk:** Low (planning branch checkpoint; report-only)

Freezes HARDEN.N1-N4 as a complete non-enforcing approval-enforcement planning
branch. It reads the readiness audit, attachment plan, dry-run gate simulator,
and operator report artifacts, then decides whether the planning branch is
frozen, frozen_with_warnings, incomplete, or blocked.

**Expected artifacts:**
- `.agent/harden/approval_enforcement_planning_branch_checkpoint/approval_enforcement_planning_branch_checkpoint.json`
- `.agent/harden/approval_enforcement_planning_branch_checkpoint/approval_enforcement_planning_branch_checkpoint.md`

**No new automation power.** Must not enforce approval gates, validate live
tokens, issue or consume tokens, approve or reject real actions, apply patches,
validate, benchmark, invoke MCP tools, launch workers, call or route models,
contact network services, write to a database, change route behavior, change
auth policy, push, merge, or open PRs. MIRROR.13 remains a proposed Mirror
candidate, but DOGFOOD.1B is now the current picker recommendation.

### OPS.TEST.CLOSE - Test Runtime Operations Branch Checkpoint

**Status:** Complete
**Prerequisite:** OPS.TEST.3
**Risk:** Low (checkpoint only; report-only)

Freezes OPS.TEST.1-OPS.TEST.3 as a complete test-runtime planning branch before
any executable suite manifests, runner commands, or CI changes are added.

**Expected artifacts:**
- `.agent/ops/test_runtime_operations_branch_checkpoint/test_runtime_operations_branch_checkpoint.json`
- `.agent/ops/test_runtime_operations_branch_checkpoint/test_runtime_operations_branch_checkpoint.md`

**No new automation power.** Must not delete, skip, or weaken tests; treat
timeout as pass; hide failures; add executable runner behavior; alter runtime
routes; change auth; call or route models; launch workers; apply patches; invoke
MCP tools; contact network services; write to a database; push, merge, or open
PRs. Current recommended next phase: DOGFOOD.1B - Real Operator Run Evaluation.

### HARDEN.N1 - Approval Enforcement Readiness Audit

**Status:** Complete
**Prerequisite:** ADOPT.MODEL.CLOSE  
**Risk:** Low (readiness audit only; no enforcement)

Creates a report-only audit of where approval enforcement could safely attach
later after HUMAN.CLOSE and ADOPT.MODEL.CLOSE. It should inventory candidate
route, token, validation, benchmark, worker-launch, and patch-apply attachment
points, but it must not add enforcement, issue or consume approval tokens, call
models, route models, launch workers, apply patches, run validation or
benchmarks, invoke MCP tools, contact network services, write to a database, or
change route/auth behavior.

**Expected artifacts:**
- `.agent/harden/approval_enforcement_readiness_audit/approval_enforcement_readiness_audit.json`
- `.agent/harden/approval_enforcement_readiness_audit/approval_enforcement_readiness_audit.md`

### HARDEN.N2 - Approval Enforcement Attachment Plan

**Status:** Complete
**Prerequisite:** HARDEN.N1
**Risk:** Low (attachment plan only; no enforcement)

Mapped each dangerous action category from HARDEN.N1 to future attachment
layers, required token/context fields, confirmation surfaces, audit-log needs,
bypass risks, and blocked boundaries. It did not add approval enforcement,
validate live tokens, issue or consume tokens, block routes, change auth, call
models, route models, launch workers, apply patches, run validation or
benchmarks, invoke tools, contact network services, write databases, push,
merge, or open PRs.

**Expected artifacts:**
- `.agent/harden/approval_enforcement_attachment_plan/approval_enforcement_attachment_plan.json`
- `.agent/harden/approval_enforcement_attachment_plan/approval_enforcement_attachment_plan.md`

### HARDEN.N3 - Approval Enforcement Dry-Run Gate Simulator

**Status:** Complete
**Prerequisite:** HARDEN.N2
**Risk:** Low (simulation only; no enforcement)

Simulates what a future approval gate would decide for sample action requests
and sample approval tokens using the HARDEN.N2 attachment plan. Even a
`would_allow_with_valid_token` result remains simulation-only and does not
authorize, dispatch, block, issue, consume, validate, route, or enforce any real
action.

**Expected artifacts:**
- `.agent/harden/approval_enforcement_dry_run_gate_simulator/approval_enforcement_dry_run_gate_simulator.json`
- `.agent/harden/approval_enforcement_dry_run_gate_simulator/approval_enforcement_dry_run_gate_simulator.md`

### HARDEN.N4 - Approval Enforcement Operator Report

**Status:** Complete
**Prerequisite:** HARDEN.N3
**Risk:** Low (operator report only; no enforcement)

Creates a read-only operator-facing report format for simulated approval-gate
outcomes. It makes simulated allow/warn/deny/block outcomes easier to review,
while preserving the same non-authoritative boundary as HARDEN.N3.

**Expected artifacts:**
- `.agent/harden/approval_enforcement_operator_report/approval_enforcement_operator_report.json`
- `.agent/harden/approval_enforcement_operator_report/approval_enforcement_operator_report.md`

Expected current status is
`approval_enforcement_operator_report_ready_with_warnings` because future
enforcement remains intentionally unimplemented. The recommended next phase is
HARDEN.CLOSE - Approval Enforcement Planning Branch Checkpoint.
