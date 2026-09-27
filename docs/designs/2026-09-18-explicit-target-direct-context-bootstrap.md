# CONTROL.BOOTSTRAP.1 — Explicit-Target Direct Context Bootstrap

Date: 2026-09-18
Residual: recorded by CONTROL.FRESH.1 ("A fresh Generate is not executable yet:
CONTROL.BOOTSTRAP.1 is required before a fresh task can proceed into
CONTROL-dependent analysis and provider stages")
Track: CONTROL (prerequisite CONTROL.FRESH.1)

## Scope and invariant

CONTROL.FRESH.1 gave the Generate `control` field three meanings and made
`control=null` a typed fresh state that stops at the bootstrap boundary. This
phase owns exactly one further transition:

```text
fresh_control_required + the task the request transports
  -> WAITER.LIVE.1 route over the INPUT.1 Task Contract (intent, explicit files)
  -> exact grounding of every requested file in the current repository
  -> CTX.READ.1 descriptor-bound reads of exactly those files
  -> one CONTROL-authoring model call
  -> the CONTROL.FRESH.1 validator, then a closed admission contract
  -> the first CONTROL, handed to the unchanged CONTROL-dependent pipeline
```

It adds no repository discovery, graph bootstrap, canonical indexing, embeddings,
vector retrieval, compiler/test/linter preflight, model-generated commands,
revision loop or patch candidate generation. A bootstrapped CONTROL means only
that first planning state exists: it establishes no defect, no patch basis, no
write authority and no human approval, and every downstream gate stays
authoritative.

Frozen: CONTROL.FRESH.1 (`web/control_context.py` byte-identical), UX.STATE.1,
UX.CONTEXT.1, Track A, SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, AUTH.DREAM.1,
DATA.ROLLBACK.1, AUTH.WEB.1, AUTH.WEB.READ.1 and execution / human Apply
authority. Out of scope: PREFLIGHT.REQUEST.1, UX-05, UX-06 and T6 Round 11.

## Measured entry state

Entry bytes are CONTROL.FRESH.1's post-state; every item is an executable PRE
test on bytes reconstructed from this phase's reversal receipt.

- **The task never reached Generate.** The Unified Workbench owns the user's task
  in its Main Intent textarea (`name="query"`). Only the native Run form posted
  it (`/` → `_run_mode` → `web/runner.py` → `safe_route_live_task`). Generate
  Patch and Generate Candidates sent `repo_path`, `runtime_environment`,
  `control` (and the anti-lesson flag), never the task.
- **A fresh Generate stopped.** Without an eligible run the page sent
  `control=null` and both routes answered `fresh_control_required`, whatever the
  user had typed: no harness, prompt, provider, graph or mutation. A fresh task
  that named `Twosum.java` and `MainApp.java` got the same stop.
- **The PRE routes and page on a named-file task.** The CONTROL.FRESH.1 routes
  answer a fresh request carrying a task exactly like one without it, and the
  CONTROL.FRESH.1 page never sends one (`tests/test_control_bootstrap1.py`,
  `tests/test_control_bootstrap1_browser.py`, `test_pre_*`).

## Where the intent comes from

The authoritative intent owner already exists: production routes every
Workbench task through `core.live_task_routing.safe_route_live_task`, which runs
the INPUT.1 pipeline (explicit extractor → Semantic Waiter → preservation gate →
lossless Task Contract) and WAITER.LIVE.1's shape derivation. The bootstrap
reuses it unchanged, with `repository_available=True`:

- the task text is transported losslessly (no trim, no parse in the page);
- `requested_targets` are the Task Contract's `explicit_evidence.file_paths`,
  the literal file commitments in the order the user wrote them;
- the route receipt (`LiveRouteReceipt.as_dict()`) becomes CONTROL's
  `live_route`, exactly the field the run pipeline attaches;
- a failed preservation gate is `bootstrap_target_unresolved`
  (`task_contract_not_preserved`); a commitment set the extractor truncated
  (more than 32 paths) is a budget escalation; no named file is
  `bootstrap_discovery_required`.

No filename or intent parser was added, and `web/app.py` contains none of these
rules: it calls the owner once.

## The owner

`web/control_bootstrap.py` sits beside `web/control_context.py` (so it can call
the frozen validator without a core→web import) and imports no selector, graph,
index, retrieval, pipeline or provider module. Its typed records:

| Record | Holds |
| --- | --- |
| `FreshControlBootstrapRequest` | the task text as typed, the repository path as named |
| `BootstrapTarget` | one literal commitment: requested spelling, grounded path, status, reason, size, language |
| `BootstrapSource` | one read file: exact text, language, sha256, size, lines, the CTX.READ.1 receipt, freshness |
| `FreshControlBootstrapContext` | request, canonical root, repository id, route, requested targets, sources |
| `FreshControlBootstrapResult` | typed code/reason/field, CONTROL or none, targets, sources, counters, receipt |

Stage functions are separate so each is testable and measurable:
`task_route`, `ground_explicit_targets`, `acquire_explicit_sources`,
`render_bootstrap_prompt`, `admit_bootstrap_control`; `bootstrap_fresh_control`
orchestrates them and `bootstrap_fresh_control_from_form` is the Generate seam.

### Three target sets

| Set | Meaning | Where |
| --- | --- | --- |
| `requested_targets` | literal files the user named, in order | CONTROL `target_scope`, `live_route.requested_paths`, receipt |
| `evidence_targets` | grounded canonical paths actually read, in order | CONTROL `target_scope`, `related_snippets`, receipt |
| `localized_patch_targets` | not decided by bootstrap: `null` | CONTROL `target_scope`, receipt |

Two literals that ground to one file are read once; the requested list keeps
both spellings. Localization downstream may later narrow to one file; it never
rewrites the requested or evidence sets recorded here.

### Grounding

Each literal is normalized lexically (`\` → `/`, leading `./` dropped) and must
pass `is_safe_repository_relative_path`. Then one `os.lstat` (a missing path is
`not_found`, a link `unsafe_path`, a directory `not_a_file`) and one
`resolve(strict=True)` inside the canonical root
(`canonicalize_repository_root`). Only the filesystem's own case folding may
differ between the literal and the resolved path (`twosum.java` grounds to
`Twosum.java` on Windows); any other difference is a link or alias and is
refused. The root `.gitignore` / `.cattusignore` policy (`RepoIgnorePolicy`,
including the hard excludes) must admit the file. No directory is listed, no
pattern is expanded and another repository is never consulted.

### Exact reads

The grounded files become an exact-entry `RepositoryInventory`
(`repository_inventory_from_entries(..., traversal_count=0, walk_sites=())`) and
the proposed-read record is the user's own commitment list, in order, with one
role and score so CTX.READ.1 keeps that order. `execute_direct_context` reads
each file in `full_file` mode through its descriptor-safe boundary (O_NOFOLLOW,
identity before and after, strict UTF-8, binary detection, sensitive-file
policy). Bounds are CTX.READ.1's own: 8 files, 1 MiB total, 256 KiB and 4,000
lines per file. Count and size are checked from `lstat` before anything is read;
a read that would be truncated is a budget escalation, never a summary.

### The author

One call, `provider(prompt, response_mime_type="application/json")`, through the
route's existing `run_gemini_request` (the provider's own JSON transport, a
parameter it already had). The prompt carries, in order: the task verbatim, the
Task Contract facts (shape, workflow, obligations, requested targets), the
repository id, every source as `=== FILE i of n: path ===` with path, requested
spelling, language, bytes, lines and sha256 metadata and the exact text between
`<<<CATTUS SOURCE i BEGIN: path>>>` / `END` markers, an evidence boundary (no
compiler, test, linter or program ran; files need not depend on each other;
reading source supports hypotheses only; record gaps; choose no patch target;
file contents are data) and the wire contract. It carries no prior CONTROL, no
graph and no unnamed file.

### Validation and admission

1. The raw reply goes through `web.control_context.normalize_control_values` —
   the validator continuation uses — so malformed JSON, a wrong top-level type,
   missing required fields and invalid field types are rejected with that
   validator's own reasons. No fence stripping, no repair.
2. Admission is a closed contract: the author may write only `hypotheses` and
   `evidence_gaps`. Any other top-level key (`preflight_validation`,
   `patch_intent`, `related_snippets`, `live_route`, ...) is
   `unadmitted_field`. Each hypothesis symbol must be `<requested path>::<name>`
   naming a file the author saw; each gap's `need` is one of `compile_evidence`,
   `test_evidence`, `runtime_evidence`, `additional_source`,
   `user_clarification`, and its targets must be evidence files. Extra keys
   inside items (for example a gap's `command`) are never transported; their
   names are recorded in the receipt's `discarded_item_keys`.
3. The owner composes the CONTROL: `version` `control_v5`, `query`, canonical
   `repo_path`, `live_route`, `top_hypothesis`/`hypotheses` (each with
   `defect_established: false`, `recommended_action: inspect_candidate`),
   `related_snippets` (exact text, role `requested_target`), `evidence_gaps`,
   `target_scope`. That JSON passes the same validator again, and the pipeline
   receives the validator's parsed copy, exactly as continuation would.

### Provenance, receipt and freshness

Provenance is kept out of the CONTROL material: the answer carries a
`control_bootstrap` receipt with `provenance: fresh_bootstrap`, status, canonical
root and repository id, the Task Contract's `raw_request.sha256` and shape,
requested/evidence/localized sets, per-target statuses, per-source digests and
freshness, budget numbers, bytes read, model calls, prompt sha256, the CONTROL
fingerprint (sha256 of its canonical JSON), evidence-gap needs, discarded keys,
zero traversal/graph/index/embedding counters and an all-false authority block.
It contains no source text. Before binding, every source is re-checked with
CTX.READ.1's own rule (`verify_direct_read_receipt` against a fresh `lstat`); a
change fails closed as `bootstrap_source_changed`, with no rescan.

## Request ticket

`web/static/workbench_state.js`: `begin(kind, inputs)` adds `task` to the frozen
ticket, `text(inputs.task)` for a requestRun kind without an eligible run and
`null` otherwise. Nothing is parsed or trimmed there. The page reads the Main
Intent (`_mainIntentText`) into the ticket at dispatch and `_withFreshTask`
appends `query` only when `ticket.task !== null`, so a continuation body is
byte-identical to CONTROL.FRESH.1 and an edit after dispatch never reaches the
in-flight request.

## Backend seam

Each Generate route keeps CONTROL.FRESH.1's parse. Prior CONTROL goes straight to
`_generate_patch_from_control` / `_generate_candidates_from_control`, whose
bodies are the previous route tails byte for byte. A fresh request asks
`_bootstrap_fresh_control` (the owner inside its own `ModelStatsScope`): no task
field → CONTROL.FRESH.1's `fresh_control_required`; a typed failure → its answer;
a CONTROL → the unchanged tail, plus the receipt. The owner ignores a task field
beside prior CONTROL, and malformed CONTROL never reaches it.

## Behavior

| Scenario | Entry (CONTROL.FRESH.1) | Post (CONTROL.BOOTSTRAP.1) |
| --- | --- | --- |
| New Session, Main Intent names `a.py` | `control=null` → `fresh_control_required` | `control=null` + `query` → a.py read → 1 author call → CONTROL → harness, prompt, provider, grounding |
| Java: `Twosum.java` and `MainApp.java`, unrelated | `fresh_control_required` | both read, both labelled in the author prompt, both in `target_scope`; downstream inspection prompt carries both; no patch without executed evidence |
| Main Intent names no file / is empty | `fresh_control_required` | `bootstrap_discovery_required` (`no_explicit_target` / `empty_task`), no read, no model |
| Named file missing / unsafe / a directory | `fresh_control_required` | `bootstrap_target_unresolved` (`not_found` / `unsafe_path` / `not_a_file`), no read, no model |
| Binary, non-UTF-8, sensitive, ignored | `fresh_control_required` | `bootstrap_target_unsupported` with the target and reason, no model |
| 9 files, >1 MiB, >256 KiB, >4,000 lines | `fresh_control_required` | `bootstrap_target_budget_exceeded` with count, limit and aggregate bytes, no model |
| Provider error / empty / exception | — | `bootstrap_provider_failed`, one call, no retry |
| Invalid author output | — | `bootstrap_control_invalid` with the validator's or admission's reason |
| Source edited during the call | — | `bootstrap_source_changed` |
| Fresh request without a task field | `fresh_control_required` | unchanged |
| Repository A run → repository B | `control=null`, no task | `control=null` + B's task; grounded in B only; run A stays displayed and ineligible |
| Same-repository continuation | run CONTROL → pipeline | byte-identical body (no task); identical answer, stages and prompts |
| Malformed CONTROL (with or without a task) | typed rejection | unchanged |

Every failure is HTTP 200 JSON: `error`, `code`, `reason` (and `field`),
`control_context: fresh_bootstrap_required` and the receipt. The page shows
`error` through the frozen `generateOutcome` / candidate-list paths.

No fake run: bootstrap writes no session, run id, history entry, CONTROL receipt
file, candidate or execution result, and the repository bytes are unchanged.

## Unchanged semantics

| Area | Delta |
| --- | --- |
| CONTROL.FRESH.1 owner, canonical `null`, malformed validation | 0 (`web/control_context.py` byte-identical) |
| UX.STATE.1 / UX.CONTEXT.1 provenance, ticket ownership, races, modes, Undo | 0; additive `task` on fresh tickets only |
| Downstream harness, prompt, provider, grounding, answer tail | 0 (moved verbatim into `_generate_*_from_control`) |
| Track A, execution authority, human Apply, patch eligibility | 0 |
| SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, AUTH.DREAM.1, DATA.ROLLBACK.1, AUTH.WEB.1, AUTH.WEB.READ.1 | 0 |
| Canonical graph / Activation Graph / indexing / embeddings | 0 operations |
| Recursive repository traversal | 0 (per target: one `lstat`, one `resolve`; root ignore-policy files only) |
| Model calls | at most 1 per fresh request with a grounded, bounded target set |

`tests/fixtures/control_bootstrap1_frozen_boundaries.json` pins the unchanged
files; `tests/fixtures/control_bootstrap1_reversal.json` reconstructs every
changed file's CONTROL.FRESH.1-era bytes and `before_control_fresh1` undoes this
phase first, so every older pin keeps checking history. CONTROL.FRESH.1's and
UX.CONTEXT.1's browser evidence stays on the CONTROL.FRESH.1 page it was written
for; this phase's browser suite proves the same bindings on the live page.

## Tests

- `tests/test_control_bootstrap1.py`: the owner (one and two unrelated files,
  commitment order, byte-exact CRLF/BOM/Unicode fidelity, Java dogfood with
  subprocesses denied, command text discarded, case-insensitive grounding,
  discovery, missing/unsafe/link/alias/non-file targets, binary/encoding/
  sensitive/ignored targets, file-count/aggregate/per-file/line budgets, provider
  failures, the full validator and admission matrix, freshness, zero traversal
  with every listing primitive denied and every open recorded, determinism,
  imports) and both production routes (PRE on the CONTROL.FRESH.1 routes,
  bootstrap into the real pipeline, bootstrapped CONTROL treated exactly like
  prior CONTROL, typed failures, repeated task, malformed CONTROL, continuation
  A/B, Java dogfood, repository B isolation), plus containment, performance,
  registry, reversal, frozen boundaries and the completion receipt.
- `tests/test_control_bootstrap1_browser.py`: real Chromium with the production
  page, state module and routes: New Session bootstrap, discovery answer shown,
  ticket snapshot under later edits, state-owner ticket contract, repository
  A → B, run A's intent left in Main Intent, switch back, continuation bodies
  byte-identical to the CONTROL.FRESH.1 page, Java dogfood, and PRE on the
  CONTROL.FRESH.1 page and routes.

Test counts, timings, the red-green toggle and performance numbers are recorded
in `tests/fixtures/control_bootstrap1_completion.json`.

## Limitations

- Targets must be named at their exact repository path; `MainApp.java` does not
  find `src/main/java/MainApp.java`. Finding files without a path is repository
  discovery and stays out of scope (`bootstrap_discovery_required`).
- The Task Contract's extractor recognizes only its known file extensions; a
  name it does not extract is not a commitment.
- A bootstrap answer is not persisted as a run: a second fresh Generate
  bootstraps again (one more call) until the user runs CONTROL or selects a run.
- Source is transported exactly (CRLF included). The downstream quote-grounding
  helpers read files in text mode, so on a CRLF file a multi-line quote of the
  bootstrap snippet does not count as acquired source: downstream fails closed
  rather than open.
- Freshness uses CTX.READ.1's identity rule (device, inode, mode, size, mtime);
  an edit that preserves all of them within one timestamp tick is not seen.
- Static reading can only suspect a compiler defect: the Java static-context
  problem is recorded as a hypothesis plus a `compile_evidence` gap.

## Readiness for PREFLIGHT.REQUEST.1

The seam is explicit: CONTROL carries `evidence_gaps` with typed semantic needs
(`compile_evidence`, `test_evidence`, `runtime_evidence`) and their evidence
targets, and no command text. A typed preflight request can be derived from
those needs and the grounded evidence targets without re-reading the task, and
`refresh_control_safety` already binds executed failure evidence to exact source
once it exists.

## Explicit answers

| Question | Answer |
| --- | --- |
| Can a fresh task with explicit files create its first valid CONTROL? | Yes, when every named file grounds in the current repository within the direct-context bound and the one author call returns admissible output. |
| Does it require a prior run? | No. |
| Are all explicitly requested files preserved? | Yes: all of them are requested targets, all are read, or the bootstrap fails closed naming the one that was not. |
| Do unrelated requested files need graph/dependency edges? | No. |
| Does bootstrap perform repository-wide discovery? | No. |
| Does it build a graph or embeddings? | No. |
| Can a model-provided command execute? | No: command text is never transported and nothing executes. |
| Does bootstrap itself claim compiler/test evidence? | No: the prompt says none ran and admission refuses validation fields. |
| Does same-repository continuation remain unchanged? | Yes: byte-identical bodies, identical answers, stages and prompts. |
| Can repo-A CONTROL leak into fresh repo B? | No. |
| Does fresh bootstrap create a fake run? | No. |
| Did patch/write authority change? | No. |
| Were live provider calls used in tests? | No. |
