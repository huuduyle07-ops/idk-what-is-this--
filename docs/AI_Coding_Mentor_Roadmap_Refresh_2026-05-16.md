# AI Coding Mentor — Roadmap Refresh

> Updated after AgentBench 31-case suite expansion, Phase 2 reporting upgrades, Dream V2 benchmark seeding (with dedupe + flaky-case seeding), local DB recovery, **Phase 5 web workspace revamp completion (Slices 1-5 shipped 2026-05-16)**, flaky-case Benchmarks tab rendering, **Dream execution-quality Slices alpha/beta/gamma shipped (2026-05-16)** including ready-to-apply revalidation + lesson-quality badges, **Dream Slice γ3.3 shipped (2026-05-17)** explaining why planned items are not `ready_to_apply`, **Phase 4.6 Dream reference-study case-idea mode shipped (2026-05-25)**, **Brain version stamp + Phase 4.5 Level 1 background reporter shipped (2026-05-17)**, **Phase 4.5 Levels 2-3 CLI MVP shipped (2026-05-17)**, and **Phase 6 manual-safe memory loop shipped (2026-05-17)** — bucketed lesson storage, Memory tab promote/block UI, active-only retrieval, CONTROL prompt injection behind `LESSON_RETRIEVAL_ENABLED`, manual proposal→lesson CLI, lesson tags, the Phase 6.4b benchmark-report lesson seeder, and the Phase 6.4c proposal-artifact lesson seeder (automatic Dream queue lessonization remains deferred).

> **2026-05-23 refresh:** Phase 7.1 through 7.2.1.1 Mayor/workflow bridge slices are shipped. Phase 8 now includes the read-only MCP server, the artifact-write MCP server for `create_handoff_note`, `import_worker_run_as_proposal`, and `validate_imported_worker_proposal`, the MCP audit ledger, and local MCP Inspector shortcuts/cleanup.

> **2026-05-24 refresh:** Universal graph node weights (design ba4ba93) shipped — single `weight = α·in_deg + β·out_deg + γ·complexity` model in `graph/weights.py` used by CONTROL DFS sort, project_map Critical Symbols, and Obsidian AI_READ_FIRST. Graph penalty term shipped on top — past failures (blocked lessons in `.agent/lessons/blocked/` + failed rows in the `patch_attempts` Postgres table) add `5.0·N_blocked + 1.0·N_transient` to the matching file/symbol node's weight at graph-build time. CONTROL DFS now prioritizes files and symbols that have failed before. Fail-soft throughout: missing DB / lesson dir / project_tag silently degrades the transient or blocked term to zero. All three consumers (CONTROL, project_map, Obsidian export) wired end-to-end with integration tests.

> **Reading convention for other AI agents:** items prefixed with **🤖 Claude-proposed**, **🤖 Gemini-proposed**, or **🤖 GPT-proposed** are AI-generated suggestions, dated and **pending the user's accept/reject decision**. Treat them as candidate scope, NOT confirmed work. The user has consulted multiple AIs; provenance is shown so future readers (human or AI) can see who said what.

> **2026-05-26 refresh:** Phase 5.6 Goal Brief Builder shipped. It adds a fixed-schema, evidence-first intake layer before Dream, CONTROL, Claude, ChatGPT, or the full agent acts. The builder can ask clarifying questions, suggest safe manual terminal commands, accept pasted user evidence, write `.agent/goal_briefs/<timestamp>/goal_brief.json` and optional Markdown exports, and generate a final task prompt only after enough evidence exists. Guardrails: it does not run terminal commands, apply patches, run benchmarks, create benchmark cases, seed/promote lessons, promote memory, or mutate proposal artifacts.

> **2026-05-26 refresh:** Phase 5.7 Prompt-Version & Cost Quantifier panel shipped. `core/prompt_cost_quantifier.py` groups existing `.agent/benchmarks/benchmark_report_*.json` files by `brain_stamp.prompt_config_hash` (unknown bucket when missing) and computes per-group averages (success rate, duration, fallbacks, model_calls, input/output/total tokens, estimated cost, unknown-cost calls, dirty-run count) plus first_seen, last_seen, latest_report. `scripts/build_prompt_cost_report.py` is the CLI (`--repo-path`, `--output-json`, `--output-md`) writing `.agent/benchmarks/prompt_cost/prompt_cost_report.{json,md}`. `GET /benchmarks/prompt-cost` feeds a new compact Benchmarks-tab panel (prompt hash · runs · avg success · avg duration · avg fallbacks · avg tokens · avg cost · latest report). Guardrails: read-only, no benchmark execution, no model calls, no patch execution, no lesson seeding, no roadmap mutation; source benchmark reports are never modified; malformed reports are skipped with structured warnings.

> **2026-05-27 refresh:** Phase 4.7a-e Dream taxonomy, structured trial reports, enriched trial content, and external research reference import are shipped. Dream can now import pasted outside research into `.agent/dream_references/<reference_id>/reference.{json,md}` and pass the generated `reference.md` into report-only structured trials. Guardrails: no autonomous browsing, no search, no model/API calls, no subprocesses, no benchmarks, no patch creation, and no decision-policy relaxation beyond consuming imported local markdown references.

> **2026-05-30 refresh:** Phase 12.9a Generated Artifact Ledger and Phase 12.10a Runtime Environment Selector are shipped. Benchmark reports now keep `changed_files` as the full observed set while separately reporting `patched_files`, allowed `generated_artifacts`, and `unexpected_mutations`; `allowed_generated_files` is exact-path only and never overrides `forbidden_changed_files`. The web app now records where C.A.T.T.U.S itself is running via `runtime_environment`, `runtime_environment_custom_name`, and `runtime_environment_notes`, with deterministic helper functions in `core/runtime_environment.py`, a Patch-tab dropdown/help text, session/result metadata, and runner debug metadata. Guardrails: no patch-logic changes, no path-guard relaxation, no broad generated-file patterns, no shell-based runtime detection, and no agent feature expansion yet. Roadmap maintenance note: this file is long; future agents should add compact dated memory notes near the top and move deep historical detail into an archive only when explicitly requested or when editing that section anyway.

> **2026-05-30 refresh:** Phase 12.10b Adaptive Harness Modes and the follow-up hard-deny runtime/path conflict message are shipped. `core/harness_modes.py` now makes deterministic `normal_patch`, `source_missing`, `path_outside_repo`, `codespaces_local_path_mismatch`, `ungrounded_patch_blocked`, and `degraded_context` decisions; web runner metadata surfaces the decision; hard path/runtime conflicts return a user-readable deny block before draft generation, including current runtime, active repo root, requested path, detected path environment, reason, and fix instructions. Guardrails: no Dream changes, no benchmark scoring changes, no prompt-heavy model intelligence, no patch-gate relaxation, no patch generation or apply when hard-denied.

> **2026-05-31 refresh:** Phase 12.13c-e explainability layers are shipped. Phase 12.13c adds `core.related_notes`, a deterministic explain-only scorer/Markdown formatter for already-loaded lesson/proposal/memory-style notes. Phase 12.13d adds a pure `Related Notes / Lessons` debug/report formatter in `web.graph_evidence` that accepts already-loaded note records only. Phase 12.13e adds default-off graph explainability attraction notes to `scripts/explain_graph_weights.py` via `--include-attraction`, with optional `--query` and `--target-node`, reusing `graph.attraction` and preserving default table/JSON output. Guardrails: no graph weight math changes, no CONTROL ranking changes, no Phantom Limb ranking changes, no Evidence Spread scoring changes, no patch generation/selection changes, no validation or benchmark scoring changes, no model/API calls, no DB/storage writes, and no lesson seeding. See the 2026-05-31 explainability-stack refresh below for Phase 12.12b and 12.13a/b/f.

> **2026-05-31 refresh:** Phase 12.12b, 12.13a, 12.13b, and 12.13f explain-only explainability slices are shipped (read-only; no CONTROL ranking, Evidence Spread scoring, graph-weight math, Phantom Limb ranking, patch generation, validation, benchmark scoring, model/API, or DB changes). **Phase 12.12b** attaches Evidence Confidence to Evidence Spread Markdown via `web.graph_evidence`: `classify_spread_node_confidence()` maps each serialized spread node to a `core.evidence_confidence` band (direct target / distance-0 = highest, distance-1/2 lower, missing/out-of-window = 0.0), and a new "Evidence Confidence" section renders combined score, strongest evidence, a per-node confidence table, and the `EVIDENCE_CONFIDENCE_GUARDRAIL`. **Phase 12.13a** adds `graph/attraction.py` — an immutable `GraphAttraction` dataclass plus `classify_node_attraction()`, `is_generic_utility_hub()`, `explain_attraction_batch()`, and `format_attraction_markdown()`; query/target/confidence/failure/graph-weight pull attraction, generic hubs + high-in-degree-without-query-match push repulsion, `net_score = clamp(attraction − repulsion, −1, 1)`, with a query-match override so a directly-named node is never classified a hub. **Phase 12.13b** renders a "Graph Attraction / Repulsion" section in the Evidence Spread report (after Evidence Confidence) by feeding the already-serialized spread nodes — enriched with their already-computed confidence on a shallow copy, never mutated — into `explain_attraction_batch`, with `GRAPH_ATTRACTION_REPORT_GUARDRAIL`. **Phase 12.13f** surfaces the explain-only layers in artifacts/UI: the presentation evidence pack now emits `07_graph_attraction_explainability.md` (embeds the latest `.agent/reports/graph_attraction/` report or a graceful explain-only placeholder; source report never modified) and the evidence index links it; a read-only `GET /graph/explainability/view` route renders the already-computed Evidence Confidence, Graph Attraction / Repulsion, and a `core.related_notes`-derived Related Notes / Lessons section (optional `as=html`, no model calls). Full suite green at 1294 passed; `benchmark --check` 32/0.

> **2026-05-31 refresh:** Phase 12.13g Explainability Dogfood Experiment Record is shipped (read-only; no model calls, no benchmark execution, no ranking/patching/validation/benchmark-scoring/UI changes). `core/explainability_dogfood.py` reuses `core.experiments` (`list_benchmark_reports`, `extract_benchmark_metrics`) to compare the latest two meaningful benchmark reports before/after the explainability stack when available, and degrades gracefully when fewer than two exist. It references the five Phase 12.12-12.13f artifacts (Evidence Confidence section, Graph Attraction/Repulsion section, Related Notes/Lessons debug output, the `explain_graph_weights --include-attraction` smoke report, and presentation pack file `07_graph_attraction_explainability.md`) with on-disk existence flags, and records a behavior-focused decision (correctness unchanged, `benchmark --check` 32/0, full pytest 1294 passed, explainability added). Correctness assessment matches the experiment decision policy: a `total` (suite-size) change marks the before/after pair inconclusive and falls back to the asserted fact (passed↑ alone is never a regression); a same-size `failed`/`flaky` increase or `passed` decrease flags `human_review_required`. `scripts/create_explainability_dogfood.py` is the CLI; output is `.agent/experiments/<timestamp>_explainability-stack-dogfood.{json,md}`. Tests: `tests/test_explainability_dogfood.py` (13). Full suite green at 1319 passed; `benchmark --check` 32/0.

> **2026-05-31 refresh:** Phase 12.14b Memory Temperature in Related Notes / Explainability UI is shipped (UI/report visibility only; reuses `core.memory_temperature`; no lesson-retrieval, CONTROL-prompt, ranking, graph-weight, Phantom-Limb-scoring, patch-generation, validation, benchmark-scoring, lesson-write, model/API, or DB changes). `web.graph_evidence` gains `memory_temperature_badge()` (🔥 hot / 🌤 warm / ❄️ cold / 🧊 frozen, unknown bands echo gracefully) and `format_memory_temperature_section()`, which classifies already-loaded note records via `classify_memory_batch` and renders an explain-only `## Memory Temperature` table (item_id · band badge · temperature · should_surface · short reasons) closed by `MEMORY_TEMPERATURE_GUARDRAIL`. `build_related_notes_debug_markdown(..., include_memory_temperature=False, now=None)` appends the section when opted in (default off preserves existing callers/tests); frozen notes still appear but are flagged `should_surface=no`. `GET /graph/explainability/view` now also renders the Memory Temperature section over its derived spread notes and adds `"Memory Temperature"` to `sections`. Tests: `tests/test_related_notes_memory_temperature.py` (10). Full suite green at 1329 passed; `benchmark --check` 32/0.

> **2026-05-31 refresh:** Phase 12.14c Memory Temperature Evidence Pack / Dogfood Record is shipped (read-only evidence artifacts; reuses `core.memory_temperature` + existing presentation-evidence/experiment infra; no lesson-retrieval, CONTROL-prompt, ranking, graph-weight, Phantom-Limb-scoring, patch-generation, validation, benchmark-scoring, lesson-write, model/API, or DB changes; no benchmark runs except `--check`). `scripts/build_presentation_evidence_pack.py` now emits `08_memory_temperature_explainability.md` (embeds the latest `.agent/reports/memory_temperature/` report when present, else a graceful explain-only placeholder covering the hot/warm/cold/frozen bands, the cooling formula `T_now = clamp(T_base * exp(-lambda * age_days) + reheating - risk, 0, 1)`, the hard-freeze override, and `MEMORY_TEMPERATURE_GUARDRAIL`; source report never modified) and the evidence index links it. `core/memory_temperature_dogfood.py` (+ CLI `scripts/create_memory_temperature_dogfood.py`) reuses `core.explainability_dogfood.build_benchmark_comparison` for an optional before/after benchmark comparison and writes `.agent/experiments/<timestamp>_memory-temperature-dogfood.{json,md}` with a behavior-focused decision marked `behavior_unchanged_memory_temperature_added` (memory temperature core added, UI/report visibility added, full pytest 1329 passed, `benchmark --check` 32/0, behavior unchanged, retrieval/ranking influence not enabled; an observed same-size correctness regression flips it to `needs_review_correctness_changed`). Tests: `tests/test_presentation_evidence_pack.py` (+8 memory-temperature cases incl. forbidden-import/call AST guard) and `tests/test_memory_temperature_dogfood.py` (7). Full suite green at 1344 passed; `benchmark --check` 32/0.

> **2026-05-31 refresh:** Phase 12.14d Memory Temperature Retrieval Experiment Plan is shipped (read-only plan artifact only; does NOT enable memory temperature to affect retrieval/ranking; no changes to `core/lesson_retrieval.py`, `core/control_engine.py` prompt injection, `lesson_store`, ranking, graph weights, Phantom Limb, patch generation, validation, benchmark scoring, model/API, or DB; no benchmark runs except `--check`). `core/memory_temperature_experiment_plan.py` (+ CLI `scripts/plan_memory_temperature_retrieval_experiment.py`) writes `.agent/experiments/<timestamp>_memory-temperature-retrieval-plan.{json,md}` stating: default-off feature flags (`MEMORY_TEMPERATURE_RETRIEVAL_ENABLED=false`, `MEMORY_TEMPERATURE_TIEBREAK_ONLY=true`); first-experiment safety constraints (tie-breaker only, no hard filtering of cold memories, frozen/audit-only stays excluded and never retrievable, watch fallback/model-call/token pressure); protocol (baseline vs experiment via the existing `core.experiments` registry, dev suite first, held-out only after dev passes, greenlight requires no correctness regression); and a greenlight / needs_review / reject decision policy (reject includes a frozen/audit-only memory becoming retrievable). Carries the full plan guardrail verbatim. The suggested flags are documented only — never read, set, or honored. Tests: `tests/test_memory_temperature_experiment_plan.py` (12, incl. forbidden-import/call AST guard barring model/API/patching/validation/benchmark-runner/DB and `lesson_retrieval`/`lesson_store`/`control_engine` imports). Full suite green at 1356 passed; `benchmark --check` 32/0.

> **2026-06-01 refresh:** Phase 12.15a Harness Control Registry MVP is shipped (control surface only; no `.env`/`docker-compose.yml` writes — that is 12.15b/12.15c; no ranking, CONTROL prompt, lesson-retrieval, patch-generation, validation, or benchmark-scoring changes; no model/API calls; no DB writes; no container lifecycle). Design spec: `docs/superpowers/specs/2026-06-01-harness-controls-design.md` (Phase 12.15 split into 12.15a registry MVP / 12.15b `.env` apply with backup / 12.15c docker-compose patch preview). `core/harness_controls.py` defines a declarative registry of `HarnessControl`s (fields incl. `control_type`, `source_of_truth`, `wired`, `risk`, `value_kind`, `enum_options`, `env_targets`, `plan_ref`) plus a fail-soft overlay store at `.agent/harness_overrides.json` (`load_overlay`/`save_overlay`/`set_override`/`current_effective`/`list_categories`). `set_override` persists the desired value and, for `editable_live` controls only, patches the in-process `config` attribute so call-time readers honor it immediately; `editable_restart_required` controls persist only (UI marks them restart-required); planned/locked/unknown controls and invalid values raise `HarnessControlError`. Registry: editable-live `LESSON_RETRIEVAL_ENABLED`/`MUTATION_ORACLE_ENABLED`/`OLLAMA_ENABLED`; editable-restart `AUTO_PATCH_ENABLED`/`DB_ENABLED`/`EMBEDDING_PROVIDER` (enum off/local_minilm/gemini); read-only-planned `MEMORY_TEMPERATURE_RETRIEVAL_ENABLED`/`MEMORY_TEMPERATURE_TIEBREAK_ONLY`/`dream_create_patches` (honors the 12.14d guardrail — documented-only, never set); and five locked invariants (quote grounding, patch-safety/path-traversal guard, frozen/audit-only exclusion, harness hard-deny path/runtime conflict, human approval for dangerous writes) that always render on and are rejected server-side if mutated. Blueprint `web/routes/harness_controls_routes.py` adds read-only `GET /harness/controls` (grouped categories + reused read-only docker probe; no lifecycle shelling) and `POST /harness/controls/overlay` (Save overlay; rejects planned/locked/unknown with 400). A Harness Controls panel in the Settings/Health tab renders state/live-vs-restart/source/risk badges, bool toggles + enum dropdowns for editable controls, and read-only badges for planned/locked. Tests: `tests/test_harness_controls.py` + `tests/test_harness_controls_routes.py` (23, incl. AST guard barring patching/validation/benchmark-runner/model-API/DB imports & calls). Full suite green at 1379 passed; `benchmark --check` 32/0.

## Current checkpoint

The project is a coding-agent workspace, not a Gemini patch script. Phase 4.7a-e Dream report-only trial/reference import, Phase 5 web revamp plus Phase 5.6 Goal Brief Builder, Phase 5.7 Prompt-Version & Cost Quantifier, Phase 7.1-7.2.1.1 Mayor/workflow bridge, and Phase 8.1/8.2a/8.2b/8.2c/8.3 MCP foundations are shipped.

### Stable / mostly working

- Core patch flow:
  - CONTROL / Scout context
  - Gemini draft
  - patch gates
  - executor validation
  - rollback / self-correct loop
- Context Poisoning Guard (Phase 6 prerequisite) shipped 2026-05-16, wired into Phase 6 storage/retrieval 2026-05-17:
  - `core/lesson_quality.py` exposes `evaluate_lesson_candidate(candidate)`
  - classifies lesson candidates as `auto_approved`, `needs_human_review`, or `blocked`
  - `active_knowledge_allowed` is true only for auto-approved candidates
  - blocks failed validation, rollback, forbidden/test/env/.agent/node_modules/target/benchmark-validation touches
  - keeps missing/malformed data and oversized diffs in human review
  - now wired into `lesson_store` routing (candidate/active/blocked buckets) and `lesson_retrieval` (only active reads); still not wired into benchmark runner behavior
- Phase 6 manual-safe memory loop shipped 2026-05-17:
  - `core/lesson_store.py` — bucketed `.agent/lessons/{candidate,active,blocked}/<id>.json` storage plus repo-scoped `.agent/lessons/repos/<repo_scope_id>/{candidate,active,blocked}/<id>.json` storage with atomic moves, path-traversal guards, optional `LESSON_AUTO_ACTIVE` flag (default false → human must promote), and `derive_lesson_tags()` helper.
  - Memory tab — filter buttons (All/Candidate/Active/Blocked), promote/block actions, lesson cards with tag chips, safety copy explaining advisory-only status
  - `core/lesson_retrieval.py` — `list_active_lessons` / `find_active_lessons` / `format_lessons_for_prompt`; reads ONLY `active/`; defensive double-filter on the top-level `active_knowledge_allowed` flag. With `repo_path`, retrieval uses current repo-scoped active lessons plus explicitly global active lessons; without `repo_path`, it preserves legacy global-only behavior.
  - Deterministic keyword scoring: case_name +100, tag +25, language/category +10, query-token +5 (all binary); tokenized free-form queries with English + generic-action-word stopword list (`fix`, `bug`, `patch`, `issue`, `problem`) to prevent cross-language false positives; limit clamped to [1, 20]
  - CONTROL prompt injection (`core/control_engine.py`) gated by `LESSON_RETRIEVAL_ENABLED` (default false), with `LESSON_RETRIEVAL_LIMIT` and `LESSON_RETRIEVAL_MAX_CHARS`; `[ACTIVE LESSONS — advisory hints, lowest priority]` block sits between `[PHANTOM LIMB SUGGESTIONS]` and `[USER]`; fail-closed (any error → empty block, prompt still builds); 4 production callers updated to pass `repo_path`
  - `scripts/create_lesson_from_proposal.py` — manual CLI that turns a validated `.agent/proposals/<run>/<item>/` artifact into a lesson candidate; explicitly populates tags; refuses by default if validation/apply failed (override with `--allow-failed`); path-traversal guarded; never modifies the real repo
  - `scripts/seed_lessons_from_benchmark.py` — Phase 6.4b CLI seeder that reads existing `.agent/benchmarks/benchmark_report_*.json` evidence and creates global lesson candidates only through `lesson_store` / `lesson_quality`; dry-run and report summaries supported; no benchmark runs, model calls, patch application, report mutation, active auto-promotion, or retrieval enablement
  - `scripts/seed_lessons_from_proposals.py` — Phase 6.4c CLI seeder that batches existing validated `.agent/proposals/<run>/<item>/` artifacts into repo-scoped lesson candidates by default; `--global-candidate` is explicit; failed evidence is skipped unless `--include-failed` and `lesson_quality` keeps it blocked or human-review only
  - Dream queue auto-creation remains **explicitly deferred** after 6.4c; current-repo Dream/proposal artifacts should remain repo-scoped by default, and human promotion is still required before any seeded lesson becomes retrieval-eligible
- Phase 7 Mayor/workflow bridge shipped 2026-05-21:
  - Phase 7.1 creates handoff notes and can optionally run external workers in temp clones only.
  - Phase 7.2 imports complete worker runs into the existing proposal review path without auto-apply.
  - Phase 7.2.1 validates imported worker proposals in a temp clone and writes apply/validation evidence into the proposal artifact.
  - Phase 7.2.1.1 deterministically synthesizes `case.json` and `patch_proposal.json` after passing validation so the existing manual lesson CLI can create a candidate lesson.
- Graph universal weights + lesson penalty shipped 2026-05-24:
  - `graph/weights.py` — `compute_node_weights(graph, repo_path=None)` returns `dict[str, NodeWeight]` with `weight = α·norm(in_deg) + β·norm(out_deg) + γ·norm(complexity) + penalty`, plus `penalty`, `reasons`, and per-source breakdown fields. Defaults: α=2.0, β=1.0, γ=0.5. Excludes call/expression noise nodes by default.
  - `graph/penalty.py` + `graph/penalty_constants.py` — `build_penalty_map(graph, repo_path)` returns `PenaltyResult(penalty_map, unmatched_paths, blocked_counts, transient_counts)`. Two sources combined per file/symbol node:
    - **Blocked lessons** via `core.lesson_store.list_lessons(status="blocked")` → `OMEGA_BLOCKED·N` where `OMEGA_BLOCKED = 5.0` per record touching the file.
    - **Failed `patch_attempts` rows** via SQL on `codex_db` filtered by `project_tag` → `OMEGA_TRANSIENT·N` where `OMEGA_TRANSIENT = 1.0` per row with phase in (`validation_failed`, `apply_failed`, `dry_run_blocked`), `validation_ok IS FALSE`, or `rollback_performed IS TRUE`.
    - Symbol-level routing: when `patch_attempts.target_node_name` is recorded and the symbol node exists (`<rel_path>::<symbol>`), penalty lands there; otherwise it rolls up to the file node. Missing symbols go to `unmatched_paths` — no silent rollup.
    - Path matching: slash + `./` normalization, then exact match, then case-insensitive fallback against a case-folded file-node index (Windows-recorded paths can match canonical lowercase graph node ids).
  - Fail-soft per spec table: `DB_ENABLED=false`, Postgres unreachable, `project_tag` underivable, missing `.agent/lessons/blocked/`, malformed JSON, or path/symbol mismatch all degrade to zero counts and never block weight computation. `unmatched_paths` is returned alongside the map for test/debug inspection — no global logger noise.
  - Consumers threaded: `core/control_engine.run_control_structured` → `control_dfs_v2(repo_path=...)` → DFS sort sees the bumped weight. `graph/project_map.compute_symbol_hotspots(repo_path=...)` → Critical Symbols section. `graph/obsidian_exporter.export_graph_to_obsidian(repo_path=...)` → `write_summary` → AI_READ_FIRST ranking.
  - 14 unit tests in `tests/test_graph_penalty.py` covering empty graph, blocked-only, transient-file/symbol/mixed, symbol-gone, combined sources, DB disabled, stale lesson, malformed records, path normalization, case-insensitive fallback, DB-failure fail-soft, and per-source breakdown. 2 DFS integration tests in `tests/test_control_graph_weights.py` (high-penalty file/symbol outranks tied sibling). 1 end-to-end Obsidian test verifying AI_READ_FIRST order flips with penalty.
  - Out of scope for v1 (deferred to future work): time-based decay, penalty capping / sigmoid smoothing, symbol-level penalty for blocked lessons (their schema has no symbol info), container roll-up, avoid-mode (negative penalty), pruning, precomputed cache, global logger warnings on unmatched paths.
- Phase 8 MCP foundations shipped through 2026-05-23:
  - Phase 8-prep tool registry and Phase 8.1 read-only MCP server expose safe evidence-reading tools.
  - Phase 8.2a artifact-write MCP exposes `create_handoff_note`; Phase 8.2b adds `import_worker_run_as_proposal`; Phase 8.2c adds temp-clone `validate_imported_worker_proposal`.
  - Phase 8.3 records bounded MCP invocation summaries in `.agent/mcp_audit/invocations.jsonl` and exposes `GET /mcp/audit`.
  - Local MCP Inspector shortcuts launch only fixed read-only/artifact-write targets, and web shutdown now cleans up matching Inspector process trees.
  - MCP validation applies an already-imported worker proposal only in a temp clone and writes evidence under `.agent/proposals/`.
- AgentBench:
  - recursive `case.json` discovery
  - `--check`, `--report`, `--latest`, `--compare`
  - `--summary`, `--quiet`, `--fast`, `--turbo`
  - filters by case/language/category/difficulty
  - `--limit`, `--fail-fast`, `--skip-toolchain-failures`
  - Markdown report output
  - model-call statistics, selected model, fallback count
  - slowest-case and average-duration summaries
  - temp repo cleanup with retry on Windows
- Benchmark suite:
  - 32 cases exist across C++, Go, HTML, JavaScript, Python, Rust, and TypeScript.
  - `--check`: 32 cases, 0 errors.
  - Latest full fast run after Phase 12.5k:
    - latest historical 31/31, current suite 32 cases passed, 100% success rate.
    - Hard TypeScript nested-dispatch case passed.
    - Linter fusion preserved correctness but increased fallback pressure, so it is marked cost-sensitive.
- Phase 4.5 CLI background/proposal MVP:
  - Level 1 reporter: `scripts/run_background_reporter.py` runs benchmark checks/runs, writes `.agent/reports/background_report_*.md/json`, includes Brain Stamp, and emits regression alerts.
  - Level 2 planner: `scripts/run_background_dream_planner.py` reads the latest meaningful benchmark report and writes `.agent/reports/background_dream_plan_*.md/json` with failed, flaky, and slow-passing cases.
  - Level 3 proposal queue: `scripts/run_patch_proposal_queue.py` reads Level 2 plan JSON and processes only items explicitly marked `human_approved_for_proposal=true`; default `--max-items 1`.
  - Guardrails: CLI-only; no Flask background thread; no automatic schedule; no benchmark runner changes; no Dream queue format changes; no real-repo patch/apply/commit/push.
- **Web workspace (Phase 5 complete — 2026-05-16):**
  - 7 workspace tabs: Chat/Patch, Goal Brief, Benchmarks, Dream, Memory, Graph, Settings/Health
  - ARIA-correct workspace tablist (role=tablist/tab/tabpanel, aria-controls/labelledby/selected)
  - Settings/Health panel: 15 checks (API keys, Postgres, embeddings, Ollama, Tree-sitter, Python/Node/Go/Rust/g++ toolchain)
  - Benchmarks tab: sidebar of past runs (newest first), structured detail panel (totals/groups/flaky/slowest/failed cases), flaky count + Flaky Cases table, "Seed Dream queue from this report" button
  - Dream tab: modal-based queue view, modal-based past-report viewer with collapsible morning report, per-item status cards rendered live during runs, checkbox-based apply UI (no more `prompt()`)
  - Patch tab: structured patch card (type badge, confidence bar, risk badge, validation command, changed files); raw JSON in collapsed `<details>`
  - Goal Brief tab: guided fixed-schema intake flow that collects evidence before agent action and writes `.agent/goal_briefs/<timestamp>/goal_brief.json`
- Local infrastructure:
  - Flask runs locally at `127.0.0.1:5000`
  - Postgres/pgvector DB container is recreated and host connection works
  - App uses local DB via `DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/codex_db`
  - Docker app image / Ollama-in-Docker paused (see Phase 9)
- Dream V2:
  - All 3 modes work: `plan_only`, `patch_if_safe`, `research`
  - **Phase 4.6 shipped (2026-05-25):** `reference_study` / `case_idea_research` turns pasted notes, repo-local markdown files, and snippet fields into `.agent/dreams/.../case_ideas.json`, `case_ideas.md`, and optional `LESSONS_LEARNED.md` drafts. It never creates benchmark folders, runs benchmarks, applies patches, seeds lessons, or promotes memory.
  - **Phase 4.7a-e shipped (2026-05-27):** Dream has explicit `dream_type` / `action_level` taxonomy, deterministic structured trial reports, enriched report sections, and safe external research import under `.agent/dream_references/`. Imported reference markdown can feed `create_structured_dream_trial(markdown_files=...)`; imported claims remain notes, not truth.
  - Queue/status/report routes, artifacts produced (plan_analysis.json, proposal.md, morning_report.txt)
  - `patch_if_safe` uses temp clone (success criterion met)
  - `patch_if_safe` now attempts patch generation for narrow `bug` **and `debt`** items when the planner marks them safe
  - Scout source-snippet hydration is wired into Dream patch generation, so small markdown/doc targets can become grounded patch plans instead of falling back to `planned_no_patch`
  - **Dream Slice gamma.1 shipped (2026-05-16):** refinement phase for `planned_no_patch` and `research_note_created`, writing `*.refined_passN.*` artifacts plus `refinement_history`
  - **Dream Slice gamma.2 shipped (2026-05-16):** `ready_to_apply` items revalidate saved `patch_plan.json` in a fresh temp clone, write `patch_revalidation_passN.json`, hoist `lesson_evaluation`, and show `auto_approved` / `needs_human_review` / `blocked` lesson badges in the UI
  - gamma.2 guardrails: no LLM call, no original patch modification, no real-repo apply, no lesson auto-promotion, no Active_Knowledge retrieval wiring, and no benchmark-runner behavior change
  - **Dream Slice γ3.1 shipped(2026-05-16):** timestamped run artifact isolation.Each run writes under .agent/dreams/YYYY-MM-DD/HHMMSS-run/, with legacy report compatibility.
- **Dream Slice γ3.2 shipped(2026-05-16):** preferred refined artifact promotion.Users can mark plan_analysis.refined_passN.json / proposal.refined_passN.md as preferred via metadata in list.json without overwriting originals.
  - **Dream Slice γ3.3 shipped (2026-05-17):** `planned_no_patch` / non-ready Dream items now carry `patch_blockers[]` and `patch_blocker_summary` metadata explaining why no patch is ready
  - γ3.3 detects `safe_to_patch_false`, `missing_validation_command`, `target_file_uncertain`, `patch_style_none`, `needs_manual_review`, `blocked_missing_context`, `vibe_required`, and `patch_generation_failed`; Dream UI/report show a collapsed `why no patch` details section
  - γ3.3 guardrails: explanatory metadata only; no LLM call, no patch edits, no auto-apply, no queue-format changes, and no benchmark-runner changes
  - **Benchmark seeding shipped (2026-05-16):**
    - seed from latest meaningful report (`min_total=5` filter, falls back to newest if none qualify)
    - seed from specific historical report (`report_filename` parameter, path-traversal guarded)
    - flaky cases seed as `kind="bug"` items with `flaky=true`, `attempts`, and `retry_results` when available
    - dedupe by `(source, benchmark_report, case_name, kind)` — re-seed is idempotent; manual non-benchmark items preserved

### Main caveats

- Do not claim a future clean `32/32` after code changes until a fresh full fast run passes.
- Level 3 proposal queue is gated: items without `human_approved_for_proposal=true` must skip, even if they look obvious.
- Docker should remain optional. Current local workflow should not depend on app containers.
- MCTS / branched repair should wait until Dream V2 and report flow are stable.

---

## 🤖 AI Suggestions (Claude, 2026-05-16, pending user decision)

> The items below are proposals from Claude Code, **not yet sanctioned by the user**.
> Other AI agents reading this roadmap: treat as candidate scope, NOT confirmed work.
> The user will accept, reject, or modify each individually before they enter active phases.

### A. Promote `--retry-failed 1` from optional → critical-path · **✅ SHIPPED 2026-05-16**

**Why:** With LLM-dependent tests, single-attempt suites are permanently flaky. The "official 32/32" milestone is unreachable without retry. Currently sitting as "remaining optional" in Phase 2; recommend moving to "Do now."

**Effort:** Small. ~50 lines in `benchmarks/run_benchmarks.py`. Add `--retry-failed N` flag, on failure rerun N times, mark `flaky=true` in report if any retry passes.

> **🤖 Gemini-proposed extension (2026-05-16):** when a case passes on retry, save BOTH the failure-run prompt/log AND the success-run prompt/log to the report (e.g., a `retry_diff` field containing both `failure_context` and `success_context`). The delta between them is the highest-signal debug data for finding prompt weaknesses (model hallucinated on a specific phrase, API latency dropped context, etc.). Without this, `flaky=true` is just a label with no learning attached.

**Suggested report fields (GPT-proposed shape):**
```json
{
  "attempts": 2,
  "flaky": true,
  "retry_results": [
    {"attempt": 1, "success": false, "failure_context": "..."},
    {"attempt": 2, "success": true,  "success_context": "..."}
  ]
}
```

### B. Held-out eval set

**Why:** Your 31 benchmark cases are both dev signal AND test bed. You'll inevitably overfit prompts/heuristics to them.

**Suggested:** Split ~23 dev cases (run often, tune freely) + ~8 held-out (run only at milestones, never tune to). When held-out scores diverge from dev, you're overfitting. Cheap to add now, hard to retrofit later (you have to remember which cases you've been "tuning to").

### C. Patch quality beyond pass/fail

**Why:** A patch can pass validation by nuking 200 lines and rewriting. Two patches that both pass: prefer the smaller one. Pass/fail is too coarse a signal once your agent gets decent.

**Suggested:** Track per-patch diff line count, files touched, signature changes as OUTPUT (you already have `patch_style` as INPUT). Add a "minimality" secondary metric to benchmark reports. Could surface in Benchmarks tab as a column.

### D. Repeated-failure Dream seeding

**Why:** Current seeding looks at one report. Real signal: "case X failed in 4 of last 7 runs" = real agent bug, not model blip. Single-report seeding can't see that pattern.

**Suggested:** Add "Seed Dream from repeated failures" button alongside the existing single-report buttons. Scans last N reports, surfaces cases failing >50% of the time. Highest-signal queue items you can generate.

### E. Cost panel

**Why:** You track `model_calls`, `fallback_count` per case, but not estimated $/run. Important for capacity planning ("can I run this 100x today?") and for catching prompt regressions that secretly 2× your token use.

**Suggested:** Multiply per-model attempts by per-model token prices (rough is fine). Add a "$ this run" + "$ avg/case" line to benchmark reports; surface in Settings/Health panel as cumulative.

### F. Self-bench

**Why:** Eat your own dog food. Run AgentBench on the AI Coding Mentor codebase itself (in temp clones — never the real one). Catches dogfooding gaps you can't see otherwise.

**Caveat:** Design carefully so it can never patch the live agent code while running. Temp-clone discipline must be airtight.

### G. Brain version stamp · **✅ SHIPPED 2026-05-17**

> **Shipped:** benchmark reports now include `brain_stamp` provenance: git SHA, branch, dirty state/summary, capped diff stat, prompt/config hash, and prompt/config file hashes.

**Why:** When benchmark scores drop, you currently can't tell: was it the model? The prompt? Your code? Without provenance, debugging takes hours.

**Suggested:** Each benchmark report includes git SHA of agent code at run time + hash of active prompt files (`config.py`, control prompts, etc.). 30-min implementation, hours of debug-time savings later.

> **🤖 Gemini-proposed extension (2026-05-16):** also embed `git diff --stat` of uncommitted changes at run time, **capped** to top ~10 files by line count (or summarized as `"N files dirty"` if larger than that). Catches the "reports from a working tree with uncommitted edits" case — without this, two weeks later you'd have to manually diff between SHAs to remember what was different. Implementation safeguard: skip the embed if `--stat` output exceeds ~500 chars; show summary count only.

### H. Regression alert (Phase 4.5 piggyback) · **✅ SHIPPED 2026-05-17**

> **Shipped:** `scripts/run_background_reporter.py` writes `.agent/reports/background_report_*.md/json`, includes Brain Stamp, compares to the previous benchmark report, and emits `regression_alert` when the success-rate drop crosses the configured threshold.

**Why:** If a benchmark goes from 31/31 to 29/31 after a code change, you should be told without having to look.

**Suggested:** When you ship Phase 4.5 Level 1 (background reporter), have it compare `--latest` to the previous report and flag if `success_rate` dropped >5pp. Could append a short "⚠ Regression detected" block to the morning report. Combines well with **G** (brain version stamp) — alert can say "regression after agent SHA <X> → <Y>."

### I. Viability concern: MCTS for code edits (Phase 10)

**Why:** Search-space explosion is real. Most successful agentic patching today is iterative refinement (test → fix → test → fix), not tree search. Academic appeal ≠ practical wins.

**Suggested:** Before sinking real time, run a small experiment: 10 hard benchmark cases, MCTS branch vs your existing `self_correct_loop`. Require ≥5× improvement to greenlight Phase 10 properly. Could remain a research-only side experiment indefinitely. (Your existing `core/self_correct_loop.py` is already an iterative-refinement loop — it's mostly working.)

### J. Viability concern: Browser agent (Future)

**Why:** Cool but years from real value. Reference study can be done by you pasting doc snippets into queries.

**Suggested:** Defer until MCP sidecar (Phase 8) is shipped. The abstractions (whitelisted tool surface, read-only default) are similar; MCP is more immediately useful (lets other Claude agents query your benchmarks/dream/health).

### K. Phase 5.5 (parser service): defer indefinitely

**Why:** Health panel already surfaces tree-sitter failures gracefully. Building parser-service infrastructure only pays off if TS failures actually correlate with benchmark misses.

**Suggested:** Don't schedule. Track tree-sitter status via Health panel. If benchmark scores ever clearly drop with TS off, revisit.

### N. Adversarial Self-Play — Counter-Knowledge + Reverse Dream

**🤖 Claude-proposed (2026-05-17), user-accepted as a research thread.** See **Phase 11** for the design.

**Why:** Phase 6 stores only "what worked." Real engineering memory is asymmetric — patches that *passed validation but were brittle* contain more signal than patches that just passed. Mutation oracle (already in repo) generates that signal today but throws it away after the run.

**Suggested:** add `kind: "lesson" | "anti_lesson"` to the existing lesson record. Anti-lessons come from mutation-oracle survivors on passing patches. A new Dream mode (`attack_past_self`) periodically tries to break recent successes; survivors become anti-lessons + new Dream `bug` items. Contrastive prompt block surfaces both. Lessons whose anti-lessons accumulate auto-demote from `active/` to `candidate/`.

**Why it's "weird":** most agent research in 2025 is *more memory* / *better retrieval* / *bigger context*. This one says: deliberately remember the failures of your own successes, and use Dream offensively against your past self. Psychologically uncomfortable framing, but that's the point.

**Hard prerequisites:** § B (held-out eval set) AND § C (patch minimality metric). Without both, the falsifier experiment is meaningless. Greenlight rule: minimality must improve ≥15% without pass-rate dropping ≥5pp on held-out cases. Full design + greenlight criteria + alternates (Phase 11b invariant verification, Phase 11c honeypot cases) in the **Phase 11** section.

---

### M. Context Poisoning Guard for Phase 6 lessons · **✅ MVP SHIPPED 2026-05-16 · ✅ wired into Phase 6.0–6.3 storage/retrieval 2026-05-17**

**🤖 Gemini-proposed (2026-05-16), user-accepted for MVP:**

> **MVP (2026-05-16):** standalone evaluator in `core/lesson_quality.py` with smoke tests in `tests/test_lesson_quality.py`. Quality classification primitive only.
>
> **Wired (2026-05-17):** the guard now drives `lesson_store` bucket routing (auto_approved/needs_review/blocked → candidate/active/blocked), feeds `lesson_retrieval`'s active-only reads, and gates `control_engine`'s `[ACTIVE LESSONS]` block. Phase 6.4b/6.4c now seed candidates from existing benchmark reports and proposal artifacts through the same guard; Dream queue auto-creation remains deferred.

**Why:** If the agent solves a case by deleting tests or nuke-and-rewrite, and that "solution" gets auto-promoted to a lesson card, the agent will look up that lesson next time it sees a similar failure type and reinforce the bad pattern. Lesson storage without quality gating poisons your knowledge base over time. This is a real architectural risk that Claude's original Phase 6 design missed.

**Suggested:** Two-tier promotion before any lesson is consumed by the patch flow:

1. New lesson cards start as `Candidate_Lesson` (visible in Memory tab but NOT retrieval-eligible by the patch pipeline).
2. Promotion to `Active_Knowledge` (retrieval-eligible) requires EITHER:
   - **Auto-criteria:** fewer lines than the buggy version + lower or equal token cost + validation OK + no test/forbidden files touched
   - **Human approval:** user clicks "Promote" in the Memory tab
3. The Phase 6 retrieval call site only reads from `Active_Knowledge`.

This makes Phase 6 a precondition-design problem, not just a storage problem. **Should be a Phase 6 PREREQUISITE** — don't ship lesson auto-creation without the gate, or the knowledge base will self-poison within weeks.

### L. Suggested ordering when user picks next task

> Historical note: A, G, H, Patch Safety, Phase 4.5 Levels 1-3, and Phase 6 manual-safe loop have shipped. Current near-term ordering is tracked in **Near-term action list**.

1. ~~Manual Level 3 trial on one reviewed `human_approved_for_proposal=true` item.~~ ✅
2. ~~Prompt-version quantifier panel, paired with Brain Stamp hashes.~~ ✅ (Phase 5.7, shipped 2026-05-26)
3. ~~Patch Safety gate (forbidden-files + path-traversal at apply time).~~ ✅
4. Held-out eval set.
5. Repeated-failure Dream seeding.
6. ~~Phase 6 lessons — § M guard MVP is shipped; still wire `Candidate_Lesson` → `Active_Knowledge` storage, human approval, and retrieval that reads only active knowledge.~~ ✅ (manual-safe loop shipped; benchmark-report seeding shipped as 6.4b; proposal-artifact seeding shipped as 6.4c; Dream queue auto-creation remains)

### O. λ-Driven Task Decomposition (Thinking Chunk Orchestration)

**🤖 Gemini-proposed (2026-05-31), user-accepted as a research thread.** See **Phase 15** for the design.

**Why:** In high-complexity zones (dense call graph, many coupled files), a single large model call either runs out of context or produces shallow analysis. Instead of forcing the model to "think slower," decompose the task at the Orchestrator layer: measure zone density via static analysis (Semble), compute a λ Task Decomposition Factor, and break the query into N parallel sub-tasks for fast model calls, then refine.

**Semble's role:** CPU-based static scanner acts as a zero-cost radar. It reports coupling density and cross-file call graph complexity to the λ function, which decides how many Thinking Chunks to spawn.

**Concern (specific to this hardware):** Parallel API requests on a battery-throttled machine may hit network latency walls before model speed matters. Context drift across sub-tasks ("Tam sao thất bản") is also a real coherence risk — each parallel sub-task loses global C.A.T.T.U.S graph context, and the Refine step must merge potentially contradictory outputs. The Phase 15 design includes falsifiable experiment criteria to avoid building this speculatively.

**Suggested first step:** Phase 15a — implement λ as a complexity classifier only (no decomposition, no parallel calls). Measure whether the classifier's output correlates with cases where the agent currently under-performs. Only greenlight decomposition after that data exists.

---

## Phase 1 — Lock the 10-case benchmark milestone

**Status: DONE**

- 10 benchmark cases reached
- `--check` worked
- fast benchmark mode worked
- 10/10 milestone achieved before expanding

---

## Phase 2 — Finish AgentBench as the teacher system

**Status: DONE / stable enough**

### Completed

- Toolchain classification and `--skip-toolchain-failures`
- Short summary / quiet output
- JSON and Markdown reports
- `--latest` and `--compare`
- Patch kind tracking: `patch_candidate` / `patch_plan` / unknown
- Rollback detection
- Model stats: selected model, model attempts, fallback count, models by role
- Duration summary: average duration, slowest cases
- Temp repo cleanup: explicit `agentbench-*` temp folders, retry cleanup on Windows lock, cleanup status saved in report

### Remaining

- [x] **`--retry-failed N`** — **shipped 2026-05-16**. CLI flag in `benchmarks/run_benchmarks.py`. Reruns failed cases up to N times; marks `flaky=true` if a retry passes (still counts as passed). Toolchain failures, forbidden-file touches, and structural errors are excluded from retry. Per-case `attempts`, `flaky`, `retry_results[]` fields added with Gemini's failure/success log diff capture per attempt + GPT's JSON shape. Top-level `flaky` counter + Markdown "Flaky Cases" table.

> 🤖 **Claude-proposed (2026-05-16) — RESOLVED ✅:** Promoted from optional → shipped. With `--retry-failed`, "official 31/31" is now reachable honestly: passes-with-flake are visible (`flaky=true`), not hidden. Three-AI consensus (Claude/Gemini/GPT) on prioritization. See **AI Suggestions § A**.

---

## Phase 3 — Expand benchmark suite from 10 to 20+

**Status: DONE**

Current suite has 31 cases:

- C++: `cpp_account_interest`, `cpp_boundary_check`
- Go: `go_logging_side_effect`, `go_missing_import_error`, `go_multifile_root_cause`, `go_wallet_transfer`, `go_wrong_file_temptation`
- HTML: `html_signup_form_accessibility`
- JavaScript: `js_array_mutation_side_effect`, `js_async_missing_await`, `js_null_user_profile`, `js_temperature_converter`
- Python: `python_callback_dispatch_ambiguity`, `python_central_node_temptation`, `python_discount_test`, `python_duplicate_filename_temptation`, `python_exception_parse_config`, `python_false_positive_no_patch`, `python_multifile_root_cause`, `python_mutable_default`, `python_off_by_one_pagination`, `python_sql_account_transfer`, `python_sql_join_filter`
- Rust: `rust_cart_reservation`, `rust_result_error_handling`
- TypeScript: `ts_callback_dispatch_ambiguity`, `ts_false_positive_no_patch`, `ts_import_export_mismatch`, `ts_inventory_restock`, `ts_nested_dispatch_root_cause`, `ts_optional_property_guard`

### Current benchmark status

```text
--check: 31 cases, 0 errors
official clean full fast run achieved: 31/31 passed, flaky: 0, with --retry-failed 1
```

### Next benchmark goal

```text
official full fast run: 31/31 passed (with --retry-failed 1 — flaky-pass counts but is visible)
```

Use:

```bash
python benchmarks/run_benchmarks.py --fast --summary --skip-toolchain-failures --markdown --retry-failed 1
```

A "true 31/31" passing run will look like one of:
- `Passed: 31 · Flaky: 0` → real clean run, no flake
- `Passed: 31 · Flaky: 2` → 31/31 but 2 cases needed a retry (failure-vs-success log diff captured in `retry_results[]` per case)
- `Passed: 29 · Failed: 2 · Flaky: 0` → real regression, no flake to blame

> 🤖 **Claude-proposed (2026-05-16):** Once the 31 cases are stable, split into ~23 dev + ~8 held-out to avoid overfitting. See **AI Suggestions § B**.

---

## Phase 4 — Stabilize Dream V2

**Status: MOSTLY DONE**

Dream is the planning/research layer; benchmark seeding is shipped with dedupe. Execution-quality Slices alpha/beta/gamma and Phase 4.6 reference-study case-idea mode are now shipped.

### Completed (2026-05-16)

- All 3 Dream modes work: `plan_only`, `patch_if_safe`, `research`
- Dream queue controls in web; queue/status/report routes
- `patch_if_safe` uses temp clone (success criterion met)
- `patch_if_safe` can patch narrow `bug` and `debt` items when the planner marks `safe_to_patch_now=true`
- Dream patch generation hydrates `patch_intent.source_snippet` from Scout file picks, including small markdown/doc targets
- **Dream Slice alpha shipped** - time budget UI with backend clamp
- **Dream Slice beta shipped** - graceful stop-between-items with `skipped_user_stop`
- **Dream Slice gamma.1 shipped** - plan/research refinement for `planned_no_patch` and `research_note_created`, preserving originals and writing refined-pass artifacts
- **Dream Slice gamma.2 shipped** - `ready_to_apply` revalidation in fresh temp clones + `lesson_quality` grading; UI shows lesson badge (`auto_approved`, `needs_human_review`, `blocked`) beside the refined badge
- **Dream Slice γ3.3 shipped** - `patch_blockers[]` + `patch_blocker_summary` explain why a planned/non-ready item has no patch; UI/report render a compact collapsed `why no patch` list
- **`seed_queue_from_latest_benchmark()` shipped** — bug items from failed cases, bug items from flaky cases, debt items from slowest passing cases, `source`/`benchmark_report`/`case_name` metadata; flaky items also carry `flaky=true`, `attempts`, and `retry_results` when available
- **Specific-report seeding** via `report_filename` — used by Benchmarks tab "Seed from this report" button
- **Dedupe** by `(source, benchmark_report, case_name, kind)` — re-clicking seed is idempotent; manual non-benchmark items preserved
- **`min_total=5` filter** — skips one-off rerun reports (e.g., single-case retries); falls back to newest report only if no larger report exists
- **Phase 4.6 shipped** - `reference_study` item / `case_idea_research` mode writes case idea candidates from reference notes to `case_ideas.json` and `case_ideas.md`, with `human_approved_for_case_creation=false` by default and a Dream-tab "Case idea candidates" report table
- Phase 5 Slice 4 closed the Dream UI alert-hell: modal queue view, modal report viewer, per-item status cards, checkbox apply UI

### Remaining (manual / by-running)

- [x] Run a real Dream queue with 3 items end-to-end (1 bug + 1 debt + 1 research)
- [x] Confirm artifacts visually: `plan_analysis.json`, `proposal.md`, morning report, per-item status
- [ ] Belt-and-suspenders assertion: `plan_only` mode never invokes patch executor (likely a test, not a feature)

### Success criteria

```text
Dream can turn benchmark reports into useful queue items.   [met]
Dream can produce readable plans without patching.           [met]
Patch_if_safe does not touch the real repo directly.         [met - uses temp clone]
Ready_to_apply items can be revalidated and lesson-graded.   [met - gamma.2]
Reference notes can become case idea candidates only.          [met - 4.6]
No-patch Dream items explain why no patch is ready.           [met - γ3.3]
```

---

## Phase 4.5 — Background Worker / Long-running Agent

**Status: CLI MVP SHIPPED 2026-05-17 (Levels 1-3); no scheduler/background thread yet**

> 🤖 **Claude-proposed (2026-05-16):** Level 1 (background reporter) is the 80/20 win. Recommend shipping Level 1 as a complete phase milestone; treat Levels 2 and 3 as separate future projects. Add the regression-alert idea (**AI Suggestions § H**) onto Level 1 to make it immediately operationally useful.

### Goal

Let the agent run safe background work without requiring the user to watch the terminal.

### Safe levels

#### Level 1 — Background reporter

- run `--check`
- run `--fast --summary`
- create `.agent/reports/morning_report.md` or `.agent/reports/evening_report.md`
- no code changes
- > 🤖 **Claude-proposed:** also compare to previous report and flag `success_rate` drop >5pp ("⚠ Regression detected after agent SHA X → Y"). See **AI Suggestions § H**.

- **Phase 4.5 Level 1 Background Reporter**: DONE
- runs --check
- runs full fast benchmark with retry visibility
- writes .agent/reports/background_report_*.md/json
- includes Brain Stamp
- compares previous report
- emits regression_alert when needed

#### Level 2 — Background Dream planner

- **Phase 4.5 Level 2 Background Dream Planner**: DONE / CLI MVP shipped 2026-05-17
- implemented in `scripts/run_background_dream_planner.py`
- reads latest meaningful benchmark report from `.agent/benchmarks`, preferring reports with `total >= 5`
- writes `.agent/reports/background_dream_plan_YYYYMMDD_HHMMSS.md/json`
- includes failed cases, flaky cases, and slowest passing cases
- each item carries `kind`, `case_name`, `reason`, `source_benchmark_report`, `suggested_mode`
- every item defaults to `human_approved_for_proposal=false`; human review must opt in before Level 3
- no patching; no repo writes except `.agent/reports`

#### Level 3 — Patch proposal queue

- **Phase 4.5 Level 3 Patch Proposal Queue**: DONE / CLI MVP shipped 2026-05-17
- implemented in `scripts/run_patch_proposal_queue.py`
- reads latest `background_dream_plan_*.json`
- processes only items explicitly marked `human_approved_for_proposal=true`
- default `--max-items 1`
- copies benchmark case `buggy_repo` into temp, generates proposals there, and validates there
- writes proposal artifacts to `.agent/proposals/YYYYMMDD_HHMMSS/`
- validation commands come only from benchmark case metadata and must pass a tool allowlist
- subprocess calls use timeouts and UTF-8 env; per-item exceptions become `proposal_error` instead of crashing the queue
- never modifies the real repo, never applies automatically, and keeps user approval required

### Safety rules

```text
Default = read-only / report-only
Dream = plan-only
Patch = proposal only
Apply = human approval only
No direct commit to main
No arbitrary shell command from background worker
Level 3 requires explicit human_approved_for_proposal=true per item
Validation commands come from benchmark metadata allowlist only
No Flask background thread or automatic scheduler in CLI MVP
```

---

## Phase 4.7 — Dream Taxonomy + Structured Trial Reports

**Status: a / b / c / d / e all shipped 2026-05-27**

Five small slices that retire the confusing `kind` + `mode` overlap, replace the free-form Dream "idea / research / reference" flow with a structured report-only trial, and add a safe import layer for pasted external research. Patch / proposal execution for `bug_investigation` / `debt_cleanup` is unchanged.

### Phase 4.7a — Dream Type / Mode Cleanup (shipped 2026-05-27)

- `core/dream_taxonomy.py` (new): `DREAM_TYPES` (6), `ACTION_LEVELS` (4 base + `case_idea_research` specialty), `ALLOWED_COMBINATIONS` matrix, `validate()`, `normalize_legacy(kind, mode)`, `legacy_kind_for_dream_type()`
- `/dream/queue` POST accepts new `dream_type` + `action_level` AND legacy `kind` + `mode`; invalid combos rejected with a friendly error (no silent coercion)
- New `/dream/taxonomy` GET route exposes the matrix to the UI
- `core/sleeping_consultant.py::_normalize_dream_mode` extended with `proposal_draft → plan_only` and `report_only → research` aliases (no behavior change)
- UI: dropdowns relabeled **Work type** / **Action level**, populated dynamically from `/dream/taxonomy`; changing Work type re-renders Action level so only valid combos are selectable; all existing buttons preserved
- Tests: `tests/test_dream_taxonomy.py` (30) + `tests/test_dream_taxonomy_routes.py` (9)

### Phase 4.7b — Structured Idea Trial Report (shipped 2026-05-27)

- `core/dream_trials.py` (new): `create_structured_dream_trial()` writes `trial.json` + 7 numbered markdown files into `.agent/dream_trials/<trial_id>/`. Pure-Python, deterministic, **no model calls, no benchmarks, no patch executor, no subprocess**
- `DECISION_POLICY` data table: every decision (including `recommend_human_approval`) lists `patch` / `apply` / `commit` in `blocked_actions` and never in `allowed_actions`
- `_compute_decision()` is pure: (proposal_score, refutation_strength, confidence, risk, has_evidence) → one of `greenlight_report_only` / `recommend_human_approval` / `needs_human_review` / `needs_more_evidence` / `rework` / `rejected`
- Heuristic `_compute_judge_scores()` over title / hint / notes / loaded-files / missing-files
- `_read_markdown_files()` records out-of-repo / non-markdown / unreadable / missing files as `unknowns` rather than crashing
- `scripts/create_dream_trial.py` (new): argparse CLI with friendly `ValueError → stderr + exit 2` handling
- Tests: `tests/test_dream_trials.py` (31)

### Phase 4.7c — Dream Trial Web Integration (shipped 2026-05-27)

- `web/routes/dream_trials_routes.py` (new): Flask Blueprint with three routes
  - `POST /dream/trials/create` — delegates to Phase 4.7b core; returns `{ok, trial_id, status, decision, artifact_dir, files, allowed_actions, blocked_actions}` or `{ok:false, error}`
  - `GET /dream/trials/list?repo_path=…` — newest-first; malformed folders / bad JSON / missing `trial.json` are skipped silently (never 500)
  - `GET /dream/trials/file?repo_path=…&trial_id=…&file=…` — filename allowlist (the 7 .md files + `trial.json`), strict trial_id regex, `relative_to()` containment check; blocks path traversal and arbitrary file access
- UI: new "Structured Trial Reports" section in the Dream tab between queue/run controls and Plan items
  - Create Trial Report + Refresh Trials buttons; Create is auto-disabled (with a small note) unless Work type ∈ {idea_trial, research_study, reference_study, case_idea_research} AND Action level = report_only
  - Trial list with title / type / status / risk / confidence / created_at + 8 per-trial file buttons (Reference / Baseline / Reasoning / Evaluation / Refutation / Judge / Final / JSON)
  - Plain-preformatted file viewer (no markdown editor, per spec)
- Forbidden-import guard test confirms the routes module imports no patch executor, benchmark runner, shell-out, or model client
- Tests: `tests/test_dream_trials_routes.py` (30)

### Phase 4.7d — Structured Trial Content Enrichment (shipped 2026-05-27)

`core/dream_trials.py` content builders rewritten to interpolate the actual inputs instead of generic prompt questions. Web routes / CLI / UI / decision policy all unchanged.

- `_build_reference_study` — splits `reference_notes` and each loaded markdown file into concrete snippets at line/sentence boundaries; explicit `"Evidence is weak…"` assumption when no grounded source is attached
- `_build_baseline_answer` — concrete 3–5-sentence paragraph that quotes the title, hint, and first sentence of the notes; default position adapts to weak-vs-grounded
- `_build_reasoning_chunks` — five concrete chunks in the spec ordering: problem → affected surface → produced artifact → risk boundary → safe next action. Surface hints heuristically extracted via `_extract_surface_hints` (backticked tokens + file-path-shaped substrings)
- `_build_multi_perspective` — five views (beginner / professor / profit / maintainer / safety) namedrop the title, hint, and reference notes; no view body is just a placeholder question anymore
- `_build_refutation` — main objections, worst-case, and simpler alternative quote the title and adapt to weak-vs-grounded evidence
- `_compute_judge_scores` — explicit caps: no grounded source → confidence ≤ 30; ≥ 2 unreadable referenced files → confidence ≤ 60
- Three new pure helpers: `_split_into_snippets`, `_extract_surface_hints`, `_first_sentence`
- Tests: `tests/test_dream_trials_enriched.py` (12) including regression guards that `DECISION_POLICY` still blocks code changes and module imports stay pure

### Phase 4.7e - Dream External Research Import (shipped 2026-05-27)

Safe import/normalization only. Users can paste research from Zapier, Discord, manual web search, papers, or notes into local artifacts under `.agent/dream_references/<reference_id>/`, then use the generated markdown file as a Dream Trial reference.

- `core/dream_references.py` (new): `create_dream_reference(repo_path, topic, raw_input, source_type="manual_paste", sources=None, key_ideas=None, risks_or_weaknesses=None, do_not_assume=None, suggested_dream_trial_input="", now=None)` writes `reference.json` and `reference.md`.
- `reference.json` stores topic, source type, raw input, summary, normalized source entries, key ideas, risks/weaknesses, do-not-assume notes, suggested Dream Trial input, and `usable_as_markdown_file=true`.
- `reference.md` renders the structured sections expected by Dream Trial markdown ingestion: Topic, Source Type, Summary, Sources, Key Ideas, Risks / Weaknesses, What C.A.T.T.U.S Should Not Assume, Suggested Dream Trial Input, and Raw Input.
- `scripts/import_dream_reference.py` (new): CLI accepts `--repo-path`, `--topic`, `--raw` and/or `--input-file`, `--source-type`, repeated `--key-idea`, `--risk`, and `--do-not-assume`; prints `reference_id`, `reference.md`, `reference.json`, and short summary.
- `web/routes/dream_references_routes.py` (new): `POST /dream/references/import`, `GET /dream/references/list`, `GET /dream/references/file`.
- Dream tab: new "Research References" section with Topic, Source type, raw notes textarea, Import Reference, Refresh References, latest-reference cards, and "Use in markdown files field" button.
- `core.dream_trials._read_markdown_files()` now accepts markdown files that resolve inside the repo root or inside that repo's `.agent/dream_references/` root; traversal and non-markdown files still become unknowns, not evidence.
- Tests: `tests/test_dream_references.py` (14), `tests/test_dream_references_routes.py` (10), and `tests/test_dream_references_ui.py` (1).

### Phase 4.7e-a — Loose Research Note Normalizer (shipped 2026-05-27)

Some Zapier / Discord research outputs come back as a free-form blob with headings like `Summary`, `Key Papers & Articles`, `Key Insights`, `Resources & Links`, `Risks / Weaknesses`, etc. instead of structured JSON. This slice makes those usable without hand-editing.

- `core/dream_references.py` — new public helper `normalize_loose_research_text(raw_input, topic=None) -> dict`. Pure-Python parser; preserves `raw_input` verbatim.
- `_LOOSE_HEADINGS` dict recognizes 20+ heading variants (case-insensitive, tolerant of `#` markdown prefix and trailing `:`), including a `Research Results` skip-section marker.
- URL-based sources from `Key Papers` + `Resources` + `Sources` sections are deduplicated by URL. Source-type inference is conservative: `gnu.org/software/.../manual`, `/manual/`, `/refman/`, `/reference/`, `/spec/`, `/docs/`, `docs.*` → `official_docs` (`high`); `oreilly.com`/`catb.org`/`/book/`/`.epub` → `book` (`medium`); `regular-expressions.info` → `web_guide` (`unknown`); `blog`/`/forum/`/`stackoverflow.com`/`reddit.com` → `blog` (`unknown`); else → `unknown` (`unknown`).
- `SOURCE_ENTRY_TYPES` extended with `official_docs`, `book`, `web_guide` (backward compatible with existing `paper`/`docs`/`blog`/`forum`/`unknown`).
- Conservative defaults injected only when the corresponding section is absent: 3 risk warnings ("Imported research was not independently verified.", "Source labels may be inaccurate.", "Performance or quality claims need supporting evidence.") and 2 do-not-assume warnings ("Do not treat imported research as verified truth.", "Do not auto-create patches or proposals from this reference alone.").
- `create_dream_reference(..., normalize_loose=False)` — new opt-in flag. When `True` and `raw_input` is non-empty, the parser fills any field the caller didn't explicitly supply. Explicit non-empty caller values always win. Summary uses the parsed `Summary` section when available.
- `scripts/import_dream_reference.py` — new `--normalize-loose` flag threaded through to the core API.
- `/dream/references/import` accepts `normalize_loose` as JSON bool or form string (`1`/`true`/`yes`/`on`).
- Dream tab — new "Normalize loose Zapier/Discord research" checkbox in the Research References section; `importDreamReference()` reads the checkbox state and includes `normalize_loose: <bool>` in the POST body.
- Tests: `tests/test_dream_references_loose.py` (15) covering Summary extraction, numbered URL lines, cross-section dedup, key-insights → key_ideas, conservative defaults, no-overwrite of present sections, raw input preservation, explicit-override, parser-fills-missing, source-type / reliability inference, CLI flag end-to-end, web route flag (on / off), forbidden imports.

### Phase 4.7e-b — Title-only Source Capture (shipped 2026-05-27)

Zapier sometimes returns "Key Papers & Articles" lists without URLs (e.g. *The Unix Programming Environment*, *grep: A Pattern Matching Utility*). Phase 4.7e-a was dropping those silently. This slice captures them as honest, low-confidence source entries instead.

- `_loose_parse_source_line` — now returns a `{title, url:""}` dict for URL-free lines that look like a real title, and still returns `None` for noise: markdown headings echoed in body, pure separators (`---`, `===`), fragments shorter than 3 chars, and generic section labels echoed in body (anything that matches `_LOOSE_HEADINGS`).
- `_loose_extract_sources` rewritten with two passes — URL sources deduped by URL (Phase 4.7e-a behavior preserved); title-only sources deduped among themselves by normalized title and **suppressed when a URL source with the same normalized title exists** (URL preferred per spec).
- Title-only entries carry `source_type="unknown"`, `reliability="unknown"`, and `why_relevant="Title-only source from imported notes; URL missing."` so the markdown renderer makes the gap visible.
- `_render_reference_markdown` now renders an empty `url` as `URL: _missing_` instead of a dangling `URL:` line — true for both normalizer-produced and explicit-source entries.
- Helper `_loose_normalize_title_for_dedup` (lowercase, collapse whitespace, strip punctuation) is the dedup key.
- Tests: `tests/test_dream_references_title_only.py` (14) covering title-only capture, empty URL, low-confidence labels, missing-URL warning, case/whitespace-insensitive dedup, URL parsing unchanged, URL dedup unchanged, URL-vs-title preference, markdown `URL: _missing_` rendering, JSON-level distinctness, separator / label / short-line / stray-heading noise filtering, and the no-network guard (`requests`, `httpx`, `urllib`, `aiohttp`, `socket`).

### Phase 4.7e-c — Markdown File Upload Fix (shipped 2026-05-27)

**Bug found while reviewing the nearest dream trial:** browsers don't expose absolute filesystem paths from a file picker, so the Dream tab's "double-click to choose markdown files / drop markdown files here" affordance was effectively broken — the field got set to a bare filename like `notes.md`, the backend resolved it as `<repo>/notes.md`, and every picked file ended up marked `missing` in `markdown_file_details`. The reference notes textarea worked; the file picker did not.

- `core/dream_trials.py` — new `_uploads_root(repo_path)` helper returning `.agent/<tag>/dream_trials_uploads/`. `_read_markdown_files` now includes this dir as a third valid allowed root alongside the repo and the `dream_references/` import root.
- `web/routes/dream_trials_routes.py` — new `POST /dream/trials/upload-markdown` (multipart). Validates `repo_path` is a directory, requires a non-empty `file`, strips path components from the filename, requires `.md`/`.markdown` suffix, caps at 5 MiB, sanitizes the saved stem (`a-zA-Z0-9._-` only, ≤ 60 chars), stamps with `%Y%m%d-%H%M%S`, and collision-suffixes if needed. Saved path is containment-checked against the uploads root before write. Returns `{ok, path, name, size}` or `{ok:false, error}`.
- Dream tab JS — `appendDreamReferenceFilePaths(files)` is now async. For each picked/dropped `.md`/`.markdown` file, it POSTs to `/dream/trials/upload-markdown` (using the current repo input) and inserts the returned sandboxed path into the markdown-files field. Failures surface in a single `alert()` listing the offending filenames. Legacy fallback (bare filename) only when no repo path is set yet.
- Tests: `tests/test_dream_trials_upload.py` (13) covering happy path, round-trip-into-trial (uploaded file content lands in `reference_study.evidence`), distinct saved names on duplicate filenames, missing repo / missing file / non-markdown / size-cap / bad-repo rejections, traversal sanitization (`../`, `..\\`, `sub/dir/`, `/absolute/`), and the no-forbidden-imports guard on the routes module.

### Hard rules upheld by tests (all eight slices)

```text
Phase 4.7a    no patch behavior change; invalid combos rejected, not coerced
Phase 4.7b    report-only; no model / benchmark / patch / subprocess imports
Phase 4.7c    read-only file access stays inside .agent/dream_trials; path
              traversal blocked at trial_id regex + filename allowlist + relative_to()
Phase 4.7d    recommend_human_approval still has patch/apply/commit in blocked_actions;
              missing markdown files still land in reference_study.unknowns;
              confidence capped when evidence is weak
Phase 4.7e    import/normalization only; URLs stored as inert text; no browsing,
              search, model/API client, subprocess, benchmark, patch executor,
              or patch candidate imports; reference file route serves only
              reference.md/reference.json and stays inside .agent/dream_references
Phase 4.7e-a  loose parsing is pure-Python; raw_input preserved verbatim; explicit
              caller fields override parsed values; conservative warnings injected
              only when matching section is absent; no requests/httpx/urllib/aiohttp
Phase 4.7e-b  title-only entries carry url=""+source_type="unknown"+reliability=
              "unknown"+why_relevant warning; URL source preferred when titles match;
              noise lines (separators, labels, <3 chars, stray headings) filtered
Phase 4.7e-c  upload route: .md/.markdown only, 5 MiB cap, filename sanitized,
              saved path containment-checked, uploads stay inside
              .agent/<tag>/dream_trials_uploads; no forbidden imports added
```

### Success criteria

```text
Old kind/mode overlap is gone; only valid combos can land on the queue.   [met - 4.7a]
Structured trial artifacts are written under .agent/dream_trials/.        [met - 4.7b]
Trials are creatable / listable / readable from the web UI.                [met - 4.7c]
Section bodies are concrete and namedrop the actual idea.                  [met - 4.7d]
External research paste imports produce local markdown reference files.    [met - 4.7e]
Imported reference markdown can feed structured Dream Trial evidence.      [met - 4.7e]
Loose Zapier/Discord research blobs parse into structured fields.          [met - 4.7e-a]
Title-only Key-Papers entries no longer disappear from sources.            [met - 4.7e-b]
File-picker / drag-drop of markdown files actually feeds Dream Trials.     [met - 4.7e-c]
recommend_human_approval never auto-approves code changes.                 [met - 4.7b/d]
```

Test sweep at end of 4.7e-c: **1106 passed** (compileall clean).

---

## Phase 5 — Web workspace revamp

**Status: Phase 5 Core — DONE · Phase 5 Polish — REMAINING**

The web UI is now a real workspace (one-shot form → tabbed workspace milestone achieved). Slices 1–5 shipped 2026-05-16. Polish items below are non-blocking enhancements; the main Web V2 milestone has landed.

> **🤖 GPT-proposed naming clarification (2026-05-16):** split status into "Core DONE / Polish REMAINING" so readers don't think the main Web V2 milestone is still pending — it isn't. Core ≠ all polish items.

### Completed (Slices 1–5)

- **Slice 1:** Workspace tab skeleton, ARIA-correct tablist, active-state styling
- **Slice 2:** Settings/Health panel with 15 checks + status badges
- **Slice 3:** Benchmarks tab — sidebar of past runs, structured detail panel (totals/groups/flaky/slowest/failed), flaky count + Flaky Cases table, seed-from-this-report button
- **Slice 4:** Dream UI cleanup — reusable modal singleton, per-item status cards, checkbox apply UI (replaces alert/prompt hell)
- **Slice 5:** Patch card — type/confidence/risk/validation/changed-files/forbidden-check structured view; raw JSON in collapsed details
- **Phase 5.6 shipped 2026-05-26:** Goal Brief Builder adds `core/goal_brief.py`, `scripts/create_goal_brief.py`, `/goal-brief/start`, `/goal-brief/update`, and a Goal Brief workspace tab. The schema is fixed; interviewer guidance is model-optional and cannot invent evidence; user-pasted answers are the only source for command output. Final prompts include goal, evidence, constraints, validation command, and success criteria.
- Backend additions: `/health`, `/benchmarks/list`, `/benchmarks/report`, `risk` + `validation_command` in `/test_patch` and `/apply_patch` (and `_plan` variants)
- Tab patterns: workspace tabs + result tabs both have active-state styling; lazy-load panels (health/benchmarks) on first show; ESC-to-close modal
- **Web benchmark execution + Add Case clerk shipped 2026-05-17:** Benchmarks tab now has `Run all`, `Run selected`, stop/status polling, and an `Add case` modal. Add Case can copy a source repo into `benchmarks/cases/<language>/<case>/buggy_repo`, infer default validation command via existing repo/language rules, infer expected/allowed changed files from current patch state or repo `git diff`/staged/untracked evidence, and optionally ask the LLM to classify category/difficulty plus rewrite rough human intent into strict benchmark requirements. Guardrail: generated lessons still do not auto-promote; proposal -> lesson remains evidence-gated/manual-safe.
- **Lesson proposal viewer shipped 2026-05-17:** Memory lesson cards created from `patch_proposal` now expose a read-only `View proposal` button that opens the originating `proposal.md` through a path-guarded Flask route, preserving the rule that lessons should be understandable through their proposal evidence.

### Phase 5 Polish tasks

- [ ] **Render Dream report markdown properly** (currently `<pre>` — works but not pretty). Would need a small markdown lib (~10KB) or simple inline parser.
- [x] **Improve Benchmark tab - execution controls shipped 2026-05-17:** `Run all`, `Run selected`, stop/status polling, and Add Case UI are now available from the web tab.
- [ ] **Improve Benchmark tab - remaining polish:** run language/category batch trigger, show model usage/fallbacks per case, and improve report drill-down density.
- [x] **Prompt-version quantifier panel (Phase 5.7) shipped 2026-05-26:** lives as a "Prompt / Cost Quantifier" panel inside the Benchmarks tab. `core/prompt_cost_quantifier.py` reads existing `.agent/benchmarks/benchmark_report_*.json` only, groups runs by `brain_stamp.prompt_config_hash` (falling back to an explicit `unknown` bucket so malformed/missing stamps don't crash), and computes per-group averages (`avg_success_rate`, `avg_total/passed/failed/flaky`, `avg_duration`, `avg_fallback_count`, `avg_model_calls`, `avg_input/output/total_tokens`, `avg_estimated_cost`) plus `unknown_cost_call_count`, `dirty_run_count`, `first_seen`, `last_seen`, and `latest_report`. Default sort is newest `last_seen` first; the summary surfaces the highest avg-cost and highest avg-fallback groups so regressions like "I changed the system prompt and tokens silently 2×ed" jump out. `scripts/build_prompt_cost_report.py` is the CLI (`--repo-path`, `--output-json`, `--output-md`) and writes `.agent/benchmarks/prompt_cost/prompt_cost_report.{json,md}`. `GET /benchmarks/prompt-cost?repo_path=…` feeds the web table (prompt hash · runs · avg success · avg duration · avg fallbacks · avg tokens · avg cost · latest report). Guardrails: read-only, no benchmark execution, no model calls, no patch execution, no lesson seeding, no roadmap mutation, malformed reports are skipped with structured warnings, and source benchmark reports are never modified (asserted in tests).
  > **🤖 Gemini-proposed reframe (2026-05-16, accepted):** scope this as a "prompt-version quantifier" instead of a generic stats table. Group by prompt-file hash (paired with the brain version stamp from § G), show columns: `runs · avg model_calls · avg duration · est cost`. Lets you spot regressions like "I changed the system prompt and tokens silently 2×ed." Start with table; add line chart only if patterns aren't obvious from numbers.
- [x] **Patch Safety gate** (forbidden files + path-traversal). Runs at **apply-time**, not memory-time. Sits naturally alongside the existing Patch card from Slice 5 (visual surface for "this patch was blocked because…"). Replaces the current "Forbidden-file check: not yet implemented" placeholder row in the Patch card.
- [x] **Post-patch explanation card (for the human user)** — after a successful patch, render a small card with: (1) what was wrong, (2) why the patch works, (3) concept the user should learn, (4) similar bug pattern to watch for. Pulls from existing `patch_proposal.summary` + lesson record + `validation_output`; no new LLM calls. **🤖 GPT-proposed brainstorm (2026-05-17) "Tutor Mode" + Claude-condensed:** kept the lightweight explanation card piece; full Tutor/Curriculum phase deferred (would pivot the product from patcher → mentor).
- [x] **Goal Brief Builder (Phase 5.6) shipped 2026-05-26:** fixed-schema draft/update/final-prompt workflow with CLI and web UI. Writes only goal-brief artifacts; no patch execution, no benchmark execution/case creation, no lesson seeding, no memory promotion, and no proposal artifact mutation.
- [x] **Dream Slice gamma guardrails shipped 2026-05-16**
  - `max_refine_rounds` clamped to [1, 3], and 0 disables refinement
  - does not refine error/blocked/skipped statuses
  - records before/after summary, elapsed time, artifact, ok flag, and failed artifact metadata
  - gamma.2 `ready_to_apply` path revalidates only in temp clones; it does not mutate status, apply to the real repo, promote lessons, or wire Active_Knowledge retrieval
  - γ3.3 adds explanatory-only `patch_blockers` / `patch_blocker_summary` metadata and collapsed Dream UI/report details; it does not call the LLM, modify patches, auto-apply, change queue format, or change benchmark-runner behavior
  > **Origin note:** Claude originally placed this in Phase 6 (memory/lessons). GPT-corrected: forbidden-file is an apply-time policy gate, not a memory concern. Phase 6 may *consume* forbidden-file events as lessons, but does not own the gate. Lives in Phase 5 Polish next to the Patch card it surfaces on.

---

## Phase 5.5 — Parser Backend / Optional Tree-sitter Service

**Status: DEFERRED**

Tree-sitter should remain an optional precision layer, not a core dependency.

### Principle

```text
Tree-sitter = precision layer
literal/fuzzy/control fallback + executor validation = survival path
if Tree-sitter dies, agent still runs
```

### Future design (if needed)

- parser abstraction: local tree-sitter → optional parser service/container → regex/text fallback
- env: `PARSER_BACKEND=auto`, `TREE_SITTER_SERVICE_URL=http://localhost:7001`, `TREE_SITTER_REQUIRED=false`

> 🤖 **Claude-proposed (2026-05-16):** Likely defer indefinitely. See **AI Suggestions § K**. Health panel already surfaces tree-sitter failures gracefully. Build the parser-service infrastructure only if TS failures actually correlate with benchmark misses — they probably don't.

### Do not do yet

- Do not make Tree-sitter required.
- Do not block benchmark on parser service.
- Do not add container dependency before Web/Dream stabilize.

## A Referrence:
### Candidate indexing backend: CocoIndex

CocoIndex may be studied as an optional indexing backend for lessons, code context, and reference-study notes.

Potential uses:
- Incremental indexing for project files.
- Code chunking with Tree-sitter support.
- Fresh context for Dream and patch planning.
- Indexing `.agent/lessons/` and reference-study notes.
- Possible MCP-readable context source.

Rules:
- Do not replace existing CONTROL/Scout indexing until AgentBench proves it improves results.
- Must remain optional.
- Must not block basic local mode.
- Must not require Docker.
- Compare against current indexer using AgentBench before adopting.

### Candidate embedding model: Model2Vec

Model2Vec creates ultra-fast, tiny static embedding models by distilling a Sentence Transformers model — CPU-only inference, no GPU, minimal Torch footprint.

Potential uses:
- Replace or complement `EMBEDDING_PROVIDER=local_minilm` with a smaller, faster option.
- Back lesson retrieval scoring or graph similarity without API calls.
- Low memory overhead — viable on an 8GB RAM machine with no GPU.

Rules:
- Do not replace the current embedding provider before AgentBench proves retrieval quality matches or improves.
- Must remain optional (`EMBEDDING_PROVIDER=model2vec`).
- Must not require Docker or heavy Torch startup overhead.
- Compare retrieval precision vs MiniLM using held-out lesson lookup before adopting.

### Candidate static analysis tool: Semble

Semble performs code similarity and semantic clone detection using CPU-based static analysis with no API calls.

Potential uses:
- Fast pre-filter ("static radar") before graph expansion — scan for high-coupling zones and cross-file call graph density in milliseconds.
- Feed coupling/complexity signals to the λ Task Decomposition Factor (see Phase 15 research thread).
- Augment Phantom Limb by flagging structurally similar code clusters as likely root-cause candidates.
- Index `.agent/lessons/` to surface structurally similar past patches for a new case.
- Possible component of the reference study loop (Phase 7).

Rules:
- Do not replace existing Scout/CONTROL indexing until AgentBench proves it improves results.
- Must remain optional; must not block basic local mode or require Docker.
- Compare against current indexer using AgentBench before adopting.
---

## Phase 6 — Memory, lessons, and compression

**Status: MANUAL-SAFE LOOP SHIPPED 2026-05-17 · benchmark/proposal evidence seeders shipped 2026-05-25 · Dream auto-creation deferred**

> 🤖 **Claude-proposed (2026-05-16):** Anchor "lessons cards" to a specific consumer: *"the agent looks up past lessons before drafting a patch for similar failure type."* Without the lookup-integration in the patch flow, lesson cards become a museum nobody reads. First Phase 6 iteration should include the **retrieval call site**, not just the storage.
>
> **🤖 Gemini-proposed HARD PREREQUISITE (2026-05-16) — see AI Suggestions § M:** Context Poisoning Guard MVP shipped 2026-05-16 as a standalone evaluator (`core/lesson_quality.py`). The two-tier `Candidate_Lesson` → `Active_Knowledge` gate is **now wired** into storage (6.0) and retrieval (6.2/6.3); benchmark-report seeding is shipped as 6.4b and proposal-artifact seeding is shipped as 6.4c, while Dream queue auto-creation remains deferred.

### Goal

Turn benchmark and Dream outputs into useful knowledge the agent actually consults — safely, behind a quality gate, with human approval before anything becomes retrieval-eligible.

### Scope policy

- Benchmark reports produce **global lesson candidates** by default because AgentBench cases are generic bug patterns.
- Phase 7 worker proposals from a real repo should produce **repo-scoped lesson candidates** by default because the evidence may be project-specific.
- Dream/proposal artifacts from the current repo should also produce **repo-scoped lesson candidates** by default.
- A lesson becomes **global active knowledge** only after a human clicks Promote or an operator uses an explicit CLI flag. Auto-approved quality evidence may create a candidate, but it must not silently become global retrieval context.

### Shipped 2026-05-17 (manual-safe loop)

- **6.0 — Candidate Lesson Store** (`core/lesson_store.py`):
  - bucketed global storage under `.agent/lessons/{candidate,active,blocked}/<id>.json`; Phase 6.4d adds repo-scoped storage under `.agent/lessons/repos/<repo_scope_id>/{candidate,active,blocked}/<id>.json`
  - `save_candidate_lesson()` routes by `lesson_quality.promotion` (blocked → `blocked/`; auto_approved → `candidate/` by default, `active/` only if `LESSON_AUTO_ACTIVE=true`)
  - `list_lessons`, `promote_lesson`, `block_lesson` with atomic moves + path-traversal guard
  - 13-field lesson record; top-level `active_knowledge_allowed` strictly mirrors the bucket (file-in-active iff field-true) — belt-and-suspenders against retrieval bugs reading the field instead of the folder
- **6.1 — Memory tab promote/block UI**:
  - `GET /lessons/list`, `POST /lessons/promote`, `POST /lessons/block` with friendly JSON errors (no tracebacks)
  - Memory tab section: filter buttons (All/Candidate/Active/Blocked), refresh, lesson cards with status badge + tag chips, promote/block actions, safety copy explaining advisory-only status
- **6.2 — `Active_Knowledge` retrieval helper** (`core/lesson_retrieval.py`):
  - reads ONLY `active/`; defensive double-filter on top-level `active_knowledge_allowed`
  - `find_active_lessons()` with deterministic keyword scoring: case_name +100, tag +25, language/category +10, query-token +5 (all binary boosts)
  - tokenized free-form queries with English + generic-action-word stopword list (`fix`, `bug`, `patch`, `issue`, `problem`) to prevent cross-language false positives
  - `format_lessons_for_prompt()` — compact text (title/case/source/summary/top reasons), never embeds raw `candidate` payload, capped at `max_chars`
  - limit clamped to [1, 20]
  - **6.2.1 / 6.4d:** retrieval scope contract — with `repo_path`, current-repo active lessons union with explicitly global active lessons; without `repo_path`, retrieval stays global-only for backward compatibility
  - **6.2.2:** lesson `tags` field with `derive_lesson_tags()` (language / category / case_name slug / file basenames / distinctive content tokens); tag matches outrank summary-only matches
- **6.3 — CONTROL prompt injection** (`core/control_engine.py`):
  - `[ACTIVE LESSONS — advisory hints, lowest priority]` block injected between `[PHANTOM LIMB SUGGESTIONS]` and `[USER]` in both feature-extension and normal bug-fix branches
  - gated by `LESSON_RETRIEVAL_ENABLED` (default `false`); `LESSON_RETRIEVAL_LIMIT` (5), `LESSON_RETRIEVAL_MAX_CHARS` (3000)
  - fail-closed: any retrieval error / empty result / disabled flag → empty block, prompt still builds
  - 4 production callers pass `repo_path`: `/generate_patch`, `/generate_candidates`, `core/pipeline.py`, `core/sleeping_consultant.py`
  - import isolation locked by test: `control_engine` reaches lessons only through `lesson_retrieval`, never `lesson_store` directly
- **6.4a — Manual proposal → lesson CLI** (`scripts/create_lesson_from_proposal.py`):
  - reads `.agent/proposals/<run>/<item>/` artifacts (item / case / patch_proposal / apply_result / validation)
  - explicitly populates tags via `derive_lesson_tags`
  - refuses by default if `validation_ok` or `apply_success` is false; `--allow-failed` opt-in (lesson_quality will then mark it blocked)
  - path-traversal guarded; summary truncated; never modifies the real repo
- **6.4b — Benchmark report lesson candidate seeder** (`scripts/seed_lessons_from_benchmark.py`):
  - reads existing `.agent/benchmarks/benchmark_report_*.json` reports via `--latest` or `--report`, with optional `--case`, `--limit`, and `--dry-run`
  - creates global lesson candidates only through `core.lesson_store.save_candidate_lesson()` and `core.lesson_quality.evaluate_lesson_candidate()`
  - never writes directly to `active/`, never flips `LESSON_RETRIEVAL_ENABLED`, never runs benchmarks, never calls models, never applies patches, and never modifies benchmark reports
  - prefers passed `validation_ok=true` cases; flaky cases are saved as human-review candidates; failed/unsafe cases are saved only when `lesson_quality` routes them to `blocked/`
  - skips missing patch evidence, path-traversal report names, and duplicate source keys based on `benchmark_report + case_name + patch_hash/changed_files_hash`
  - can write optional `.agent/reports/lesson_seed_report_*.json` / `.md` summaries
- **6.4c — Proposal evidence lesson candidate seeder** (`scripts/seed_lessons_from_proposals.py`):
  - reads existing `.agent/proposals/<run>/<item>/` artifacts via `--latest`, `--run`, or `--proposal-ref`, with optional `--limit`, `--repo-path`, and `--dry-run`
  - creates repo-scoped candidates by default from validated proposal evidence (`patch_proposal`, `apply_result`, validation, `apply_success=true`, `validation_ok=true`); `--global-candidate` is the explicit operator escape hatch
  - skips failed or incomplete proposals by default; `--include-failed` still routes through `lesson_quality` and never writes failed evidence directly to `active/`
  - never writes directly to `active/`, never flips `LESSON_RETRIEVAL_ENABLED`, never runs benchmarks, never calls models, never applies patches, and never modifies proposal artifacts
  - dedupes with stable source keys based on `proposal_ref + patch_hash` or `proposal_ref + changed_files_hash + validation_hash`
  - can write optional `.agent/reports/proposal_lesson_seed_report_*.json` / `.md` summaries
- **6.4d — Scoped lesson storage/runtime isolation**:
  - `save_candidate_lesson()` stores benchmark-report lessons globally by default and repo/current-proposal lessons under safe `repos/<repo_scope_id>/` buckets when `repo_path` is available
  - `list_lessons(repo_path=...)` includes current repo-scoped lessons plus global lessons by default, can exclude global lessons, and never reads other repo scopes
  - `promote_lesson()` / `block_lesson()` accept scope identity and preserve `active_knowledge_allowed` invariants across global and repo buckets
  - Memory tab shows `global` / `repo:<repo_scope_id>` badges and passes scope identity for promote/block actions

### Deferred (Phase 6.4 follow-ups, Phase 6.5+)

- [ ] **6.4 follow-up auto-creation** — wire Dream/proposal queues to feed repo-scoped lesson candidates without manual CLI runs. Benchmark-report seeding exists as an explicit global-candidate CLI, and proposal-artifact seeding exists as an explicit repo-scoped CLI. All paths still must go through `lesson_quality`; promotion must remain human-approved by default.
- [x] **6.4d scoped lesson storage/runtime isolation** — make `repo_path` meaningful in `lesson_store` and retrieval, preserve benchmark report seeding as global, preserve worker/current-repo Dream/proposal candidates as repo-scoped by default, and keep global active promotion explicit.
- [ ] "Save this session to memory" button
- [ ] Log compression in lesson body (validation summary, patch summary, failure category — no raw dumps)
- [ ] Smarter scoring beyond binary token substring (bigram phrase boosts, embeddings) — only after AgentBench proves it improves results
- [ ] ~~Forbidden-file security gate~~ — moved to Phase 5 Polish per GPT-proposed correction (2026-05-16); apply-time policy, not a memory concern

### Original task list (status)

- [x] Add `.agent/lessons/` — **shipped as bucketed `.agent/<project_tag>/lessons/{candidate,active,blocked}/`**
- [x] **🤖 Gemini-proposed PREREQUISITE MVP — see § M:** Context Poisoning Guard evaluator (`core/lesson_quality.py`)
- [x] Wire the guard into Phase 6 lesson storage/promotion (`Candidate_Lesson` → `Active_Knowledge`, auto-criteria OR human approval, retrieval reads ONLY active/)
- [x] **🤖 Claude-proposed:** Wire lesson lookup into the patch pipeline (`core/control_engine.py`) — **shipped via 6.3 behind `LESSON_RETRIEVAL_ENABLED`**
- [x] "Consolidate memory" button (already exists in Memory tab)
- [x] Convert benchmark reports into lesson candidates — shipped as explicit 6.4b CLI seeder, not an automatic benchmark-run side effect
- [x] Convert proposal artifacts into repo-scoped lesson candidates — shipped as explicit 6.4c CLI seeder, not an automatic worker/Dream side effect
- [ ] Save Dream plans as knowledge entries (auto-flow — deferred to 6.4)
- [ ] "Save this session to memory" button
- [ ] Log compression: validation summary, patch summary, failure category

---

## Phase 7 — Reference study loop

**Status: Reference-study loop DEFERRED; Mayor/operator bridge slices 7.1-7.2.1.1 SHIPPED.**

> 🤖 **Claude-proposed (2026-05-16):** Defer harder. Most "learn from OpenHuman/Hermes" insight can be captured by the user reading them once and updating prompts. Heavy investment here pays low dividends compared to Phase 4.5 / lessons / cost tracking.

### References

- OpenHuman: Memory Tree / vault, background collector, token/log compression, model routing, UI-first agent workspace
- AiToEarn: workflow/productization ideas, multi-tool packaging
- Hermes: self-improving skill loop, long-running agent pattern
- Gastown: Mayor / worker-agent coordination pattern, persistent work state across agent sessions, task ownership / delegation / handoff notes, accountability metadata for agent work, possible future inspiration for MCP/tool-registry orchestration.

Gastown is a reference for the Mayor/operator pattern: a high-level coordinator maintains work state and delegates bounded tasks to worker agents. For AI Coding Mentor, this should first become an operator workflow and handoff-note pattern, not a new autonomous subsystem.

Apply to AI Coding Mentor:
- Treat the human user as the first "Mayor".
- Keep AI Coding Mentor as the workspace/evidence layer, not an autonomous boss.
- Lightweight operator artifacts have now shipped through Phase 7.2.1.1:
  - handoff notes under `.agent/handoffs/`
  - temp-clone worker runs under `.agent/worker_runs/`
  - worker-run import into `.agent/proposals/`
  - temp-clone validation evidence for imported proposals
  - deterministic lesson-artifact synthesis after passing validation
- Remaining reference-study ideas should add evidence/workflow notes before adding more autonomy:
  - `WORK_STATE.md` or `.agent/work_state.json`
  - task owner / status / next safe action
  - handoff notes for Dream/proposal items
  - proposal -> validation -> lesson evidence chain
- Future MCP tools can expose safe workspace operations to external agents.

Do NOT copy yet:
- Do not implement full multi-agent orchestration now.
- Do not add automatic delegation.
- Do not make agents patch/apply/commit without human approval.
- Do not replace the current Dream/proposal/lesson flow.
- Do not add new core architecture during the current soft-freeze / learn-to-operate period.

### Tasks

- [ ] Create `LESSONS_LEARNED.md`
- [ ] Add reference-study Dream item type
- [ ] Use format:

```text
Repo:
Pattern:
Why it matters:
Apply to AI Coding Mentor:
Do NOT copy:
Minimal experiment:
```

---

## Future — Browser Agent / WebBridge-style Research Tool

> 🤖 **Claude-proposed (2026-05-16):** See **AI Suggestions § J**. Defer until MCP sidecar (Phase 8) is shipped. The abstractions are similar; MCP is more immediately useful.

Goal: Allow the agent to browse public documentation and GitHub repositories through a real browser-like interface.

Reference: Kimi WebBridge / browser-control agents; WebArena / WebChoreArena.

Use cases:
- Research GitHub reference projects
- Read docs/releases/issues
- Collect architecture lessons
- Produce research notes for Dream

Rules:
- Read-only by default
- No login-required actions at first
- No form submission without user approval
- No downloading/running arbitrary files
- No direct patch/apply/push from browser tool
- Outputs must become notes/proposals, not automatic code changes

Position: Browser agent is not core patching. It is a research/input tool for Dream and reference-study loop.

---

## Phase 8 — MCP sidecar

**Status: Phase 8-prep + 8.1 + 8.2a + 8.2b + 8.2c + 8.3 SHIPPED**

MCP is an external safe API, not the brain.

### Phase 8.1 — read-only MCP server MVP (shipped)

Local MCP server (`scripts/mcp_readonly_server.py` / `mcp_server/read_only.py`)
exposes a strict read-only subset of the C.A.T.T.U.S tool registry over stdio
using the official `mcp` Python SDK (FastMCP).

**What it CAN do:**
- enumerate the tool registry (`list_tool_registry`)
- read workspace health, benchmark reports, Dream reports, lessons,
  lesson source proposals, and worker run artifacts
- every wrapper is path-traversal guarded and reads metadata only

**What it CANNOT do (enforced by `core.tool_registry`):**
- write files, run subagents, apply patches, or promote/block lessons
- create/import/validate proposals
- expose any tool whose `mcp_exposable=False`
- be reconfigured into `unsafe_dev` mode from outside

The server is gated by `tool_registry.is_tool_allowed(name, "read_only")`
on every startup — no hardcoded name lists. Importing the module does
not start the server; the friendly missing-dep message
`"MCP package not installed. Install optional MCP dependencies to run
this server."` prints to stderr (exit 2) if `mcp` is not installed.

### Safe tools (read-only baseline, exposed by 8.1)

- `get_health`
- `list_benchmark_reports`
- `read_benchmark_report`
- `list_dream_reports`
- `read_dream_report`
- `list_lessons`
- `read_lesson_proposal`
- `list_worker_runs`
- `read_worker_run`
- `list_tool_registry`

### Phase 8.2 — artifact-write MCP server (partially shipped)

`mcp_server.artifact_write` is the narrow write-capable MCP surface. It reuses the 10 read-only tools and adds only explicitly allowlisted artifact-write helpers.

- **Phase 8.2a shipped 2026-05-22:** `create_handoff_note` harness + `scripts/mcp_artifact_write_server.py`. It writes only handoff notes under `.agent/handoffs/`, accepts strict dict input, keeps the default safety rules, runs no subprocess, and cannot launch a worker.
- **Phase 8.2b shipped 2026-05-22:** `import_worker_run_as_proposal` harness. It accepts only a `worker_run_id`, copies an existing complete worker run into `.agent/proposals/`, writes no validation or lesson-ready artifacts, and runs no subprocess.
- **Phase 8.2c shipped 2026-05-23:** `validate_imported_worker_proposal` harness. It accepts only a relative proposal ref plus an existing repo directory, runs validation through the existing temp-clone core helper, writes evidence artifacts under `.agent/proposals/`, and audits success/blocked calls.
- **Current artifact-write MCP surface:** 13 tools total: 10 read-only tools + `create_handoff_note` + `import_worker_run_as_proposal` + `validate_imported_worker_proposal`.

### Phase 8.3 — MCP invocation audit ledger (shipped)

- `core/mcp_audit.py` writes bounded JSONL invocation summaries to `.agent/mcp_audit/invocations.jsonl`.
- `create_handoff_note` and `import_worker_run_as_proposal` harness calls record allowed/blocked audit events at the artifact-write boundary.
- `GET /mcp/audit?limit=50` lists recent valid events without adding any MCP write capability.
- Audit failures are observational only; they are logged and do not turn a valid harness result into a failure or a blocked result into success.

### Future Phase 8.4 — Gemini Managed Agent Worker Adapter

- Use Gemini Managed Agents as an optional cloud worker backend for bounded handoff tasks. Managed Agent outputs must be imported as worker_run/proposal artifacts and validated locally in temp clones before any lesson seeding or user approval. No direct real-repo patching, no automatic promotion, and no broad credentials.

### MCP Inspector local operator tools (shipped)

- `POST /mcp/inspector/launch` launches MCP Inspector only for fixed targets: the read-only server or the artifact-write server.
- The Sub-agent header exposes compact Inspector shortcuts plus a link to recent MCP audit events.
- `web/mcp_inspector_processes.py` and `web.runner` stop matching local MCP Inspector process trees on terminal shutdown paths such as `Ctrl+C`.
- The browser route never accepts arbitrary Inspector commands from the web UI.

### Avoid first (still deferred past the current MCP surface)

- arbitrary shell command
- arbitrary file write outside narrow `.agent` artifact helpers
- direct patch apply to real repo
- delete/move files
- DB writes
- subagent execution / handoff runs over MCP
- lesson promotion or blocking over MCP
- real-repo validation or arbitrary proposal paths over MCP

> 🤖 **Claude-proposed (2026-05-16):** Once Phases 4–6 are stable, MCP becomes very high-value because other Claude agents (or any MCP-aware AI tool) can query your benchmarks/dream/health directly instead of relying on the user pasting context. The whitelisted-tools approach in the current plan is correct — keep it.
>
> **Gastown cross-reference:** Gastown-like Mayor/operator coordination becomes more useful once MCP exposes safe workspace APIs. Keep this as tool-registry orchestration inspiration only: external agents may query evidence, work state, and handoff notes through whitelisted tools, but they should not patch/apply/commit without human approval.

---

## Phase 9 — Portable packaging

**Status: PARTIAL — 9.1a through 9.1d shipped; 9.2 deferred**

Local safe mode works. Docker runtime is stabilized with pluggable embeddings and optional sandbox images. Sandbox worker wiring is deferred.

### Phase 9.1a — Lean Docker Image Split

**Status: Shipped**

- Move sentence-transformers/Torch out of default requirements
- Add `requirements_embeddings.txt`
- Keep default Docker image small
- `INSTALL_EMBEDDINGS=false` by default

### Phase 9.1b — Pluggable Embedding Provider

**Status: Shipped**

- `EMBEDDING_PROVIDER=off | local_minilm | gemini`
- Gemini embeddings for Codespaces / lean Docker
- Metadata signature guard
- No silent fallback

### Phase 9.1c — Docker Compose Web + DB Runtime

**Status: Shipped**

- `cattus-web` runs on `127.0.0.1:5056`
- Postgres/pgvector runs in Docker
- Local Windows web can connect via `localhost:5433`
- Docker web uses `db:5432` internally
- Ollama off by default
- Embeddings off by default

### Phase 9.1d — Optional Manual Sandbox Images

**Status: Current / small checkpoint**

- Re-pulled `ubuntu:24.04`
- Re-pulled `python:3.12-slim`
- Added optional `ubuntu-sandbox` / `python-sandbox` Compose profile
- Kept them separate from `cattus-web`
- No Docker socket mounted into web container

### Phase 9.2 — Sandbox Worker Wiring

**Status: Deferred**

- `cattus-web` talks to `sandbox-worker`
- `sandbox-worker` controls temp containers
- No direct Docker socket in web app
- Audit artifacts preserved

### Modes

#### Safe local mode
- DB off, embeddings off, Ollama optional/off, API keys local, no Docker required

#### Full local mode
- Flask local, Postgres/pgvector Docker container, DB enabled, embeddings optional, Ollama installed directly on Windows if needed

#### Docker mode
- App container stabilized via 9.1c; Ollama container remains later
- Sandbox images available via optional Compose profile (9.1d)
- Do not run benchmarks automatically in container

### Tasks

- [ ] Finalize `.env.example`
- [x] Keep `.env` ignored (user confirmed `.gitignore` handles this)
- [ ] Keep `.dockerignore` strong: `.git`, `.agent`, `node_modules`, Rust `target`, temp/build outputs, `.env`
- [x] Split compose: `docker-compose.yml` = db + web runtime; optional sandbox profiles separate
- [ ] Document: local safe mode, local full mode, DB-only Docker mode, full Docker mode

---

## Phase 10 — Research: branched repair / MCTS / mutation oracle

**Status: Temporary neglect it**

Do not jump here before Dream/Web are stable.

### Order

1. Branched repair K=3
2. Mutation oracle for stronger validation
3. Dream-mode MCTS scaffold
4. Edit-operation MCTS later, maybe separate project

### Rule

```text
MCTS belongs in Dream / offline / benchmark experiment mode.
Do not put MCTS into synchronous web patch flow.
```

> 🤖 **Claude-proposed (2026-05-16):** Viability concern. See **AI Suggestions § I**. Before sinking real time, run a 10-case mini-experiment comparing MCTS vs the existing iterative `self_correct_loop`. Require ≥5× improvement on hard cases to greenlight Phase 10 properly. Iterative refinement (already implicit in your codebase) often beats MCTS for code edits in the wild. Could remain research-only indefinitely.

---

## Phase 10.5 - — Graph Role Classification:

### Add labels like:
- utility_hub
- architecture_hub
- bug_prone_hub
- query_relevant_hub

#### 1. Utility hub

**Example:**

write_text()
read_json()
save_artifact()
format_summary()

**Meaning:**

Many files use it, but it is probably not the root cause.

**Graph behavior:**

inspect: yes
blame/root-cause rank: lower
edit risk: medium/high
#### 2. Architecture hub:

**Example:**

control_engine.py
patch_gates.py
sandbox_runner.py
graph/schema.py

**Meaning:**

This coordinates system behavior.

**Graph behavior:**

inspect: high
root-cause rank: high
edit risk: high
require stronger validation
#### 3. Bug-prone hub

**Example:**

files with failed patches
blocked lessons
flaky benchmark history
many recent fixes

**Meaning:**

This area has caused trouble before.

**Graph behavior:**

inspect: high
root-cause rank: boosted
edit risk: boosted
ask for extra tests
#### 4. Query-relevant hub

**Example user asks:**

Docker sandbox not working

Then:

sandbox_runner.py
health.py
docker-compose.yml

should outrank a generic utility with more calls.

**Graph behavior:**

temporary boost only for this query
Better formula later

Instead of one weight:

weight = in_degree + out_degree + complexity + penalty

Use multiple scores:

inspect_score
root_cause_score
edit_risk_score
utility_suppression_score
query_relevance_score

That is much closer to how a real reviewer thinks.
---

## Phase 11 — Adversarial Self-Play (Counter-Knowledge + Reverse Dream)

**Status: 🤖 Claude-proposed (2026-05-17), user-accepted as a research thread, not yet scheduled**

> See **AI Suggestions § N** for the short pitch. This section is the design.

### Core idea (deliberately contrarian to Phase 6's positive-only memory)

Phase 6 stores "what worked." Real engineering memory is asymmetric — humans remember "the time we deleted that index" much longer than "the time the query was fast." Phase 11 adds the missing half: memory of patches that *passed validation but were brittle*, used to push future patches toward smaller, safer fixes.

### What it adds

1. **Anti-lessons** — when the mutation oracle (`core/mutation_oracle.py`, already in repo) finds a *surviving mutant* on a passing patch, save the pair: the lesson PLUS an anti-lesson recording "a patch of shape X passed tests but mutation `M` survived." Storage delta: one `kind: "lesson" | "anti_lesson"` field on the existing record. Same buckets, same promote/block, same `lesson_quality` gate.
2. **Reverse Dream** (new mode `attack_past_self`) — Dream periodically picks N recent successful patches, regenerates mutations against them, and tries to break them. Survivors become anti-lessons AND new Dream `bug` items to strengthen the validator. Closes the loop without human intervention.
3. **Contrastive prompt injection** — `_lessons_prompt_block` returns two sections when both exist:
   ```
   [ACTIVE LESSONS — what worked]
   ## ...do X...
   [ACTIVE ANTI-LESSONS — past patches that passed tests but were brittle]
   ## ...a patch of shape X passed but mutation Y survived; prefer Z...
   ```
4. **Honesty calibration loop** — lessons whose anti-lesson pile crosses a threshold get auto-demoted from `active/` back to `candidate/`. Inverse of the Phase 6.1 manual promote.

### Code reuse (why this is viable now, not earlier)

Every piece exists:
- `core/mutation_oracle.py` — survives-mutation detection
- `core/lesson_store.py` (6.0) — bucketed storage with atomic moves
- `core/lesson_retrieval.py` (6.2) — query scoring with tags
- `core/lesson_quality.py` — same gate works (inverted for anti-lessons)
- `core/dream_v2.py` — mode enum just needs a fourth value

Concrete delta: ~30 lines retrieval + ~50 lines new Dream mode + 1 config flag `LESSON_ANTI_KNOWLEDGE_ENABLED` (default `false`).

### Debate (genuinely two-sided — kept here so future readers can attack it)

**For:**
- Goodhart's law: if validation defines success, the agent will overfit to validation. Anti-lessons attack the validator itself.
- Real engineering memory is asymmetric (we remember pain longer than success).
- Keeps the agent humble — counteracts the "31/31 yesterday, ship it" overconfidence.

**Against:**
- Context tokens are finite; anti-lessons compete with positive lessons for the same budget. Net effect could be *worse* prompts.
- Mutation survival ≠ real fragility — mutations are synthetic operators, production failures aren't. Noisy signal.
- Could induce paralysis: agent sees too many warnings, marks everything `needs_escalation=true`, becomes useless.
- The "self-adversarial" framing might just be the agent chasing its tail — most surviving mutants point at weak *tests*, not weak *patches*. The correct fix is "strengthen the validator," not "don't write that patch again."

### Falsifiable experiment (greenlight criteria, not vibes)

Pair with **AI Suggestion § B (held-out eval set)** — Phase 11 cannot ship before § B exists.

1. Save lessons + anti-lessons from one normal week of runs (~50-100 records).
2. Run the held-out cases twice: `LESSON_ANTI_KNOWLEDGE_ENABLED=false` then `true`.
3. Three measurements:
   - **Pass rate** — if anti-lessons drop it ≥5pp, fail the experiment.
   - **Patch minimality** (AI Suggestion § C, also a prereq) — anti-lessons should push toward smaller patches; if they don't, the contrastive framing isn't landing.
   - **`needs_escalation` rate** — if it ≥2×s, the agent has become a coward; turn it off.
4. Greenlight only if minimality improves ≥15% without pass-rate dropping ≥5pp.

Either outcome is valuable: shipping it OR proving positive-only memory is enough at this scale.

### Prerequisites (hard order)

1. **AI Suggestion § B — held-out eval set** (otherwise the experiment is meaningless)
2. **AI Suggestion § C — patch minimality metric** (the key dependent variable)
3. Optional but recommended: **Phase 6.4 auto-creation** (so the lesson pool is large enough for the experiment to have signal)

### Alternates (smaller scopes if Phase 11 feels too ambitious)

- **Phase 11b — Two-language invariant verification.** Force the agent to output every patch as both code AND a plain-English invariant ("after this fix, `principal < 0 → throws`"). The invariant is testable against the diff and the validator output. Lessons store the invariant, not just the patch. Catches "patch silenced symptom without fixing cause." Tiny scope, high signal. Independent of Phase 11; could ship first as a warm-up.
- **Phase 11c — Honeypot benchmark cases.** Add 3-5 cases where the *obvious* fix is wrong (systematic extension of the existing `wrong_file_temptation` case). If pass rate on real cases stays high but honeypot pass rate is also high, the agent is pattern-matching, not reading. Cheap; calibrates everything else. Pure benchmark work, no agent-code changes.

### Do not do without these

- Do not ship Phase 11 without § B (held-out set) and § C (minimality metric); the experiment becomes unfalsifiable.
- Do not let Reverse Dream attack lessons less than 7 days old — give patterns time to stabilize before adversarial pressure.
- Do not surface anti-lessons through any path that bypasses the `active/` bucket gate; they are still subject to the Phase 6 quality contract.

---

## Phase 12 — Experiment Lab / Evaluation Governance

**Status: Shipped through Phase 12.5k on 2026-05-24**

Phase 12 upgraded AgentBench from a pass/fail runner into an experiment governance layer: runs can now be registered, compared, explained, reported, and reviewed against explicit decision rules.

### Shipped

- **12.1 — Experiment Registry MVP**  
  Added experiment records, create/compare CLI, and metric tracking from existing benchmark reports.

- **12.2 — Markdown Experiment Report Export**  
  Added Markdown reports with summary, metrics, comparison result, and decision block.

- **12.3 — Experiment List CLI**  
  Added filtered, limited, JSON-capable experiment listing with newest-first sorting.

- **12.4 — Experiment Decision Helper**  
  Added decision policy for regressions, unknowns, suite changes, cost/speed changes, and warnings.

- **12.4a — Compare Summary Decision Display**  
  Added decision status, review requirement, reasons, and warnings to CLI comparison output.

- **12.5 — Latest Benchmark Report Picker**  
  Added latest meaningful report selection and create-from-latest workflow.

- **12.5b — Graph Weight Explainability CLI**  
  Added read-only node weight explanations for topology, complexity, failure penalty, degree, and reasons.

- **12.5c — Graph Explainability Presentation Filters**  
  Added filters to make graph explanations easier to present and review.

- **12.5d — Hard/Wrong Python Benchmark Cases**  
  Added adversarial Python cases for duplicate files, multi-file root cause, no-patch false positives, callback ambiguity, and central-node temptation.

- **12.5e — Cross-language Medium Adversarial Cases**  
  Added TypeScript and Go adversarial cases for no-patch, multi-file, and callback-dispatch scenarios.

- **12.5f — First Hard Benchmark Case**  
  Added hard TypeScript nested-dispatch root-cause benchmark with a 5-hop flow.

> Note: 12.5g was investigated as grounding recovery but superseded by 12.5h/12.5i after benchmark evidence showed the real issue was TS/JS import handling, not snippet grounding.

- **12.5h — TS/JS Import-Aware Patch Candidate Promotion**  
  Improved handling for model snippets that place imports inside function-level replacements.

- **12.5i — TS/JS Missing Import Repair**  
  Added repair for TS/JS patch candidates that introduce local exported identifiers needing imports.

- **12.5j — Linter Adapter for Phantom Limb**  
  Added read-only ESLint/Pylint JSON normalization into `.agent/linter/findings.json`.

- **12.5k — Budgeted Linter Fusion for Phantom Limb**  
  Added strict-budget linter hints into Phantom Limb / CONTROL prompts.

### Validation Checkpoint

- Unit tests: **714 passed**
- AgentBench: **31/31 passed**
- Hard TypeScript nested-dispatch case: **passed**
- Linter fusion preserved **31/31 correctness**, but increased fallback count.

### Current Tradeoffs

- Graph weights can over-rank utility hubs.
- Linter fusion is correctness-safe but cost-sensitive.
- MCTS remains research-only and experiment-gated.
---
## Phase 12.8 - Web UI for seeing presentation proofs
### Shipped 
- Added markdown folders in benchmark specifically for for seeing proofs
- Make a HTML rendering for showing tables
---

## Phase 13 — Replay Debugger + Artifact Janitor

**Status: 🤖 GPT-proposed brainstorm (2026-05-17) + Claude-condensed (2026-05-17), pending user scheduling**

> Two halves of one phase. Replay can't exist without retention; retention only exists to support Replay. Bundling them prevents the classic "we'll add cleanup later" rot.

### Goal (Replay half)

Extend the existing `.agent/debug_last_control_prompt.txt` (single-file, overwritten every run) into a structured **replay bundle per agent run**, so "why pass yesterday, fail today" is answerable without re-running the model.

Layout:

```
.agent/replays/YYYYMMDD_HHMMSS_<short_id>/
  user_query.txt
  control_result.json
  scout_snippets.json
  active_lessons_injected.json        ← Phase 6.3 output
  model_prompt.txt                    ← what control_engine produced
  model_raw_response.txt
  patch_parsed.json
  apply_result.json
  validation_output.txt
  self_correct_attempts.json
  brain_stamp.json                    ← Phase 12 link by hash
  final_status.json
```

UI affordances (small additions to the existing Chat/Patch tab):

- "Replay this run" button on each completed run → opens the bundle side-by-side
- "Compare with current prompt" → diffs `model_prompt.txt` against what the *current* `build_control_prompt` would produce for the same input (uses Phase 12 comparison logic)

### Goal (Janitor half)

Retention/cleanup policy **hard-coded from day one** (no "we'll add cleanup later"):

| Artifact | Default policy |
|---|---|
| Replays < 14 days | keep raw |
| Replays 14–60 days | gzip in place |
| Replays > 60 days | delete unless pinned |
| `.agent/proposals/` > 30 days | archive |
| `.tmp/` after benchmark run | clear |
| `raw_model_response.txt` > 500 KB | gzip individually |

### Hard rules

- **Never delete active lessons** (Phase 6 contract — even if `active/` somehow grows huge, lessons are pinned)
- **Never delete pinned replays** (user marks via UI)
- Janitor runs only on user invocation or after a benchmark completes — **never as a background timer**
- Dry-run mode prints what would be deleted with sizes before doing anything (default mode for first invocation)

### Prerequisites

None — can ship independently. Pairs naturally with Phase 12 ("compare bundle A vs bundle B" is the most common debug workflow).

---

## Phase 14 — Failure Taxonomy

**Status: 🤖 GPT-proposed brainstorm (2026-05-17) + Claude-condensed (2026-05-17), BLOCKED on Phase 6.4 (auto-creation)**

### Why blocked on 6.4 (read this first)

The Phase 6.2.2 lesson `tags` are a **soft prototype** of taxonomy. A fixed taxonomy designed *before* observing real patterns will lock in bad categories. Example: we'd guess at `null_guard / off_by_one / state_leak / forbidden_file_touch`, but the actual distribution from 6.4-generated lessons might show 80% are `validation_too_weak` and our invented categories are noise.

**Order of operations (do not skip):**

1. Phase 6.4 auto-creation accumulates 200–500 real lessons with auto-derived tags
2. Cluster the tags. Look at which tags co-occur. Look at which benchmark categories produce which tag clusters.
3. **THEN** design the fixed taxonomy from observed clusters, not from imagined ones
4. Backfill: re-tag existing lessons against the new taxonomy

### What it adds (once prerequisites are met)

- Fixed `failure_category` enum stored on: lesson record, benchmark per-case result, Dream item
- Lesson retrieval gets a `category` boost (already supported in `find_active_lessons` signature — just unused so far)
- Benchmark reports show "failures by category" breakdown
- Dream seeding can prioritize by category ("3 oldest open `null_guard` cases")
- Phase 11 anti-lessons can be category-scoped ("anti-lessons in category X tend to be brittle, demote faster")

### Do not do

- **Do not invent the taxonomy in advance.** Wait for data.
- Do not make `failure_category` required for any Phase 6 / Phase 11 work — it's a precision improvement, not a prerequisite
- Do not remove the tag-based scoring once category exists; both should coexist (tags = fine-grained, category = coarse-grained)

### Prerequisites

- **Phase 6.4 auto-creation** (hard)
- ~200+ active lessons with derived tags (observation budget — informs the taxonomy)

---

## Phase 15 — λ-Driven Task Decomposition / Thinking Chunk Orchestration

**Status: 🤖 Gemini-proposed research thread (2026-05-31), user-accepted as candidate scope, not yet scheduled**

> Core concept originated from a wave-physics analogy for agent behavior. The λ (lambda) function was originally proposed as a "wave density" parameter; Gemini reinterpreted it as a **Task Decomposition Factor** at the Orchestrator layer — not a model-level slowdown (which is impossible with Chat/Flash APIs), but a scheduling decision the system makes before any model call.

### Core idea

When a query hits a high-complexity zone (many interconnected files, dense call graph, high coupling), the Orchestrator breaks the task into N parallel sub-tasks — each processed by a fast, cheap model (Gemini Flash / Haiku) — then uses a final Refine task to synthesize results. This is **Map-Reduce + Fixed-Time Budgeting**.

λ controls the decomposition count. High λ = many sub-tasks; low λ = single call.

```text
[Complex query]
      │
      ▼  Semble: CPU-based static scan, milliseconds, no API call
┌──────────────────────────────────────────────────────────┐
│  Report: coupling density, cross-file call graph depth   │
└──────────────────────────────────────────────────────────┘
      │
      ▼  λ function: density = f(coupling, file count, complexity)
      │
  [λ low] ──────────────────────► single model call (normal path)
      │
  [λ high]
      │
      ▼  Orchestrator: time-sliced sub-tasks (budget: e.g. 10 sec)
 Task 1   Task 2   Task 3   Task 4   ← parallel Flash calls, ~1-2s each
      └────────────┬────────────┘
                   ▼
              Task 5: Refine          ← synthesis call, coherence check
```

### Semble → λ → C.A.T.T.U.S pipeline

Semble acts as a zero-cost pre-filter. It reports which zones are genuinely dense before λ computes a decomposition count. This is compatible with the existing graph weights architecture (`graph/weights.py` + `graph/penalty.py`) — λ would consume the same complexity/coupling signals already produced by the weight computation, not duplicate them.

Full pipeline: **Semble measures coupling** → **λ computes density** → **Orchestrator schedules Thinking Chunks** → **C.A.T.T.U.S controls graph structure safely at output**.

### Extended architecture: Dual-Sided Vector Embedding Space

The current graph nodes are positioned purely by structural signals (in_degree, out_degree, complexity, penalty). This design splits the node space into two symmetric sides that **superpose**:

**Static side (Semble — "structural body"):** Scans AST via tree-sitter to anchor each Node (file/class) to a hard coordinate determined by call-graph link counts. Runs local on CPU in milliseconds. Produces a Background Mesh — a fixed coordinate grid for the codebase.

**Dynamic side (LLM semantic — "semantic soul"):** Computes pairwise Cosine Similarity between code segments using attention weights from Opus 4.8. These distances are not fixed; they shift with query context — what the user is asking about pulls semantically similar nodes closer.

**Superposition — Hybrid Potential Field:**

```
V(r) = Attraction_semantic(r) − Repulsion_structural(r) + Penalty_flaky
```

- `Attraction_semantic` — LLM cosine similarity: files that *mean* similar things attract each other.
- `Repulsion_structural` — structural graph distance: files with many intermediate hops between them are pushed apart (partially implemented already via `graph/weights.py` topology terms).
- `Penalty_flaky` — the existing `graph/penalty.py` blocked-lesson + failed-patch-attempts penalty, already wired into all three consumers (CONTROL, project_map, Obsidian).

> **Connection to shipped code:** `graph/attraction.py` (Phase 12.13a) already computes `net_score = clamp(attraction − repulsion, −1, 1)` using query-match and graph-weight signals. The Dual-Sided design would upgrade `attraction` to include LLM cosine similarity and upgrade `repulsion` to use structural distance more precisely — but the consumer API (`explain_attraction_batch`) stays the same. The `Penalty_flaky` term is already there.

The static side already exists. The missing piece is the LLM semantic embedding layer and the superposition formula that merges both into a single field value per node pair. Model2Vec (see "A Reference") is the candidate for producing the static embedding component without GPU overhead.

### Extended architecture: λ as Tensor Density Field

The basic Phase 15 design treats λ as a scalar threshold. The full architecture upgrades it to a **matrix field** covering the entire codebase:

```
λ(x, y) = ∇² · M_complexity + T_network_latency
```

- `∇² · M_complexity` — the Laplacian of the complexity matrix: measures how *sharply* complexity changes across the codebase landscape. A zone that transitions from simple to dense very quickly has a high second derivative and therefore high λ. Flat complexity regions have λ ≈ 0 regardless of absolute complexity.
- `T_network_latency` — a runtime term: measured API round-trip times from recent Flash calls fed back into λ. High latency → raise the decomposition threshold, because parallelism won't pay off on a slow network.

**"Contextual Black Hole" condition:** When `λ(x,y)` crosses a critical density in a zone, the surrounding metric space collapses — the Wavefront BFS treats that zone as a high-cost sink where further decomposition loses coherence faster than it gains coverage. The correct response is to escalate to a stronger model (Opus) or insert a human checkpoint rather than spawning more Flash sub-tasks.

> **Practical note for this hardware:** The `T_network_latency` term makes λ self-regulating. On a battery-throttled machine with high network latency, λ will naturally stay below the decomposition threshold more often — degrading gracefully to single-call mode without manual tuning. This is a feature, not a limitation: the system adapts to the environment it is running in.

### Concrete Thinking Chunk sub-task design (Micro-kernel scheduling)

When `λ(x,y)` exceeds the decomposition threshold, the Orchestrator fires a parallel worker pool — analogous to CPU micro-scheduling where a blocked thread yields to ready threads:

| Task | Worker | What it does | Dependencies |
|------|--------|-------------|--------------|
| Task 1 | Semble (CPU-local) | Parse AST of the affected zone; emit call-graph density and coupling report | None — runs first |
| Task 2 | Phase 6 lesson retrieval | Scan `active/` memory for structurally similar past bugs; return top-N candidates | None — parallel with Task 1 |
| Task 3 | Sandbox Draft Patcher | Run a draft patch attempt in temp-clone isolation (Dream Trial rapid mode) | Task 1 output |
| Task 5 (Refine) | Flash / Haiku | Wave interference: collect outputs from Tasks 1–3, identify maximum-amplitude results (highest agreement, lowest divergence), synthesize a single patch candidate | Tasks 1, 2, 3 complete |

**Wave interference metaphor for Refine:** The final Flash call does not "think freely" — it performs mathematical aggregation. Outputs that agree across Tasks 1–3 are reinforced (constructive interference); outputs that contradict are suppressed (destructive interference). The final patch is the superposition state with maximum amplitude, i.e. highest agreement across workers.

**Infrastructure reuse:** Task 2 is `core/lesson_retrieval.py` (already exists). Task 3 is the existing temp-clone Dream patch path (already exists). Only the Orchestrator scheduling layer and the Refine aggregator are new code. This is not a rewrite — it is a thin coordination layer over existing machinery.

### Practical concerns (8GB RAM, battery-throttled hardware)

The Gemini analysis identified three hard constraints before this can work on this machine:

1. **Network I/O bottleneck.** Parallel API requests compete for a bandwidth-throttled network interface (battery-saving mode). Five simultaneous Flash requests may exceed the 10-second budget due to network latency alone, not model speed. The first request's response may not arrive before the second is issued. This alone can shatter the fixed-time budget.

2. **Context Drift ("Tam sao thất bản").** Each parallel sub-task receives only a slice of the global C.A.T.T.U.S graph context. The Flash instance handling Task 1 has no visibility into what Task 3 is doing. The Refine task must merge outputs that may contradict each other or miss global invariants. This is a real coherence risk that grows with the number of chunks.

3. **Orchestrator state management.** The coordinating model must maintain task-slicing state across the parallel wave. Using a Flash-class model to manage its own decomposition state in a 10-second loop is a fragile design; state ownership must live in deterministic Python code, not inside a model.

### Falsifiable experiment (greenlight criteria)

Do not schedule without:

1. **Baseline single-call latency.** Record median wall-clock latency for complex CONTROL runs today on this hardware.
2. **Parallel decomposition pilot.** Run 5 adversarial benchmark cases with λ-triggered decomposition (3–4 sub-tasks + refine). Measure wall-clock latency including network round-trips.
3. **Context coherence check.** For each decomposed case, compare the Refine output against a single-call output. Track divergence rate.
4. **Greenlight rule:** Decomposition must reduce wall-clock time by ≥30% WITHOUT increasing output divergence/hallucination rate on held-out cases ≥5pp.

If network latency dominates (likely on this hardware), defer until a better-networked environment is available — not to add orchestration complexity to work around bad hardware.

### Prerequisites (hard order)

1. **AI Suggestion § B — held-out eval set.** The coherence experiment requires a fixed test set that has never been tuned to.
2. **Semble benchmarked as a static filter** (see "A Reference" section). Must prove it identifies the right high-complexity zones before wiring its output into λ.
3. **Graph weights and Phantom Limb stable.** They supply the complexity signals λ would consume.

### Alternates (smaller scope if Phase 15 feels too ambitious)

- **Phase 15a — λ as complexity classifier only (no decomposition).** Let λ annotate each CONTROL request with `complexity_class: low | medium | high` and surface that in the debug trace. This is the observability prerequisite that makes Phase 15 proper falsifiable. No parallel calls, no orchestration risk, no context drift.
- **Phase 15b — Sequential Thinking Chunks (no parallelism).** Run sub-tasks serially, not concurrently. Avoids the network I/O race condition and context drift problem. Slower in theory but safer on this hardware, and preserves global context intact between chunks because each chunk can receive the previous chunk's output.

### Do not do without these

- Do not add parallel API request patterns until the network bottleneck is measured on this specific machine.
- Do not let the Orchestrator slice tasks without a deterministic Python state-keeper (not another model call) managing the decomposition.
- Do not wire Semble into the live patch path before its output is validated against AgentBench results.
- Do not surface Thinking Chunks in the synchronous web patch flow — keep them in Dream / offline experiment mode only, mirroring the MCTS rule from Phase 10.

---

## Brainstorm absorption log (2026-05-17)

A larger brainstorm (11 candidate phases) was condensed into the 3 phases above. The rest were folded into existing scope or demoted to sub-tasks. Recorded here so future readers don't re-propose the same eleven.

| Originally proposed | Disposition |
|---|---|
| **PromptOps / Prompt Version Control** | folded into **Phase 5 Polish** (Prompt-version quantifier panel, already scheduled) + **Phase 12** (A/B comparison layer) |
| **Trust Dashboard** | folded into **Phase 5 Polish** — Settings/Health panel evolves into Trust Dashboard via composition of existing signals (latest benchmark, flaky count, dirty tree, prompt hash changed, lesson retrieval enabled, regression alerts). No rewrite. |
| **Skill / Tool Registry** | demoted to **Phase 8 prep** — MCP needs the registry to expose tools safely; everyone else can hardcode for now |
| **Multi-Repo / Workspace Memory** | folded into **Phase 6 as 6.4d scoped lesson storage/runtime isolation** (priority chain: current repo → explicitly global benchmark-derived → reference). Phase 6.4b ships global benchmark candidates, 6.4c ships repo-scoped proposal candidates, and 6.4d ships physical repo-scoped storage/retrieval isolation. |
| **Permission & Capability System** | start as **docs-only "Capability Map"** (single `docs/capability_map.md` listing every gate with its current default). Programmatic enforcer deferred until MCP / browser-agent / Docker app mode actually make it necessary. |
| **Tutor Mode / Curriculum** | reduced to a single **Phase 5 Polish item**: "Post-patch explanation card." Full curriculum/exercise scope deferred — it would pivot the product from "patcher named mentor" to "actual mentor," which is a different roadmap. |
| **Multi-Agent Council Mode** | reframed as **Phase 10 alternative to MCTS**, decided by head-to-head experiment (Phase 12 `exp_council_vs_mcts`), not built in parallel. Both are "more compute → better patches" bets; pick one based on data. |
| **Gastown / Mayor pattern** | folded into **Phase 7 Reference Study** and **Phase 8 MCP prep**. Keep as operator-workflow inspiration; no new numbered phase. |
| **Artifact Janitor** | merged into **Phase 13** as the retention half (Replay can't exist without retention) |

**Rationale:** roadmaps lose force past ~10 active phases. The original 11 proposals would push the count to 22; most were either already-scoped or scope-creep. Keeping 3 new numbered phases (12 / 13 / 14) preserves directional clarity while not losing the good ideas. Future brainstorms should be subjected to the same condensation pass.

---

## Near-term action list

### Done since last roadmap refresh

- [x] AgentBench 31 cases stable
- [x] Dream seed button + backend with dedupe shipped
- [x] Web workspace Phase 5 Slices 1–5 shipped (tabs, health, benchmarks, dream modal, patch card)
- [x] Local DB recovery confirmed working
- [x] ARIA accessibility fix for workspace tablist
- [x] Patch routes now expose `risk` + `validation_command` for the Patch card
- [x] User confirmed `.gitignore` handles `.env`, `.agent/`, etc. — no commit-hygiene blockers
- [x] **AgentBench `--retry-failed N`** shipped (AI Suggestions § A + Gemini's retry-diff logging + GPT's `retry_results[]` shape). New top-level `flaky` counter + Markdown "Flaky Cases" table. Toolchain/forbidden/error failures excluded from retry. Three-AI consensus pick.
- [x] **Benchmarks tab flaky rendering** shipped: report detail totals now show `flaky`, and reports with flaky cases render a Flaky Cases table (`name`, `passed on attempt`, `total attempts`). Old reports without flaky fields default cleanly.
- [x] **Dream benchmark seeding now includes flaky cases**: `result.flaky=true` creates `kind="bug"` queue items titled `Flaky case: <case_name>` with `flaky`, `attempts`, and `retry_results` metadata. Existing failed-case and slow-case seeding plus dedupe key are unchanged.
- [x] **CSS inline-style cleanup**: moved `<head><style>` block + JS template inline `style="…"` attrs into `web/static/style.css` via new classes (`.diff-add/del/hunk/ctx`, `.critique-error/section/verdict-*`, `.bench-detail-filename`, `.bench-fail-meta`, graph styles). Only remaining inline is the legitimately dynamic patch-confidence-bar `width: ${pct}%` (commented). VS Code `no-inline-styles` lint warnings resolved.
- [x] **Dream Slice α — Time Budget UI** shipped: preset dropdown (30 min / 1 hr / 2 hr / 6 hr default / 12 hr) in Dream tab; threaded through `/dream/run` → `start_overnight_async()`. Backend clamps to [60, 86400]. Defaults unchanged for users who ignore the dropdown.
- [x] **Dream Slice β — Stop button** shipped: graceful stop-between-items via `stop_requested` flag in `_RUN_STATE`. New `POST /dream/stop` route + `request_stop()` helper. Remaining items get `skipped_user_stop` status (added to `STATUS_LEGEND`). UI: orange "🛑 Stopping after current item" header + disabled "Stopping…" button label during the drain. Hard LLM-call cancellation explicitly deferred (would need cancellation tokens through every client).
- [x] **Dream Slice gamma shipped**: gamma.1 plan/research refinement plus gamma.2 `ready_to_apply` temp-clone revalidation and `lesson_quality` grading. UI shows `auto_approved`, `needs_human_review`, or `blocked`; debt patch generation and Scout markdown/source hydration are also in place.
- [x] γ3.1 Timestamped run artifact isolation — shipped.
- [x] γ3.2 Preferred refined artifact promotion — shipped.
- [x] **Dream Slice γ3.3 — why no patch** shipped 2026-05-17: `classify_patch_blockers()` attaches `patch_blockers[]` / `patch_blocker_summary`; Dream cards and reports show collapsed `why no patch` details. Tests cover blocker classification and UI renderer output.
- [x] **Phase 4.6 Dream reference-study case-idea mode** shipped 2026-05-25: `reference_study` / `case_idea_research` accepts pasted notes, repo-local markdown files, and snippets, writes `.agent/dreams/.../case_ideas.json` + `.md` and optional `LESSONS_LEARNED.md` drafts, and never creates benchmark cases, runs benchmarks, applies patches, seeds lessons, or promotes memory.
- [x] **Brain version stamp in benchmark reports** shipped 2026-05-17: reports include git SHA, branch, dirty state/summary, capped diff stat, prompt/config hash, and prompt/config file hashes.
- [x] **Phase 4.5 Level 1 background reporter + regression alert** shipped 2026-05-17: `scripts/run_background_reporter.py` runs checks/benchmarks, writes `.agent/reports/background_report_*.md/json`, includes Brain Stamp, compares previous reports, and emits `regression_alert` when needed.
- [x] **Phase 4.5 Level 2 Background Dream Planner** shipped 2026-05-17: `scripts/run_background_dream_planner.py` creates report-only `.agent/reports/background_dream_plan_*.md/json` from the latest meaningful benchmark report, including failed, flaky, and slow-passing cases.
- [x] **Phase 4.5 Level 3 Patch Proposal Queue CLI MVP** shipped 2026-05-17: `scripts/run_patch_proposal_queue.py` processes only `human_approved_for_proposal=true` items, copies benchmark repos to temp, validates with benchmark-metadata commands only, and writes proposal artifacts under `.agent/proposals/` without touching the real repo.
- [x] **Phase 6 manual-safe memory loop** shipped 2026-05-17: bucketed global lesson storage (`core/lesson_store.py`), Memory tab promote/block UI + tag chips, `core/lesson_retrieval.py` reading only `active/`, deterministic keyword scoring (case_name +100 / tag +25 / language+category +10 / query +5) with tokenized free-form queries + stopword list, CONTROL prompt injection (`core/control_engine.py`) gated by `LESSON_RETRIEVAL_ENABLED` and fail-closed on errors, manual `scripts/create_lesson_from_proposal.py` CLI, and `derive_lesson_tags` helper. Repo-scoped candidate defaults are still a follow-up.
- [x] **Phase 6.4b benchmark-report lesson seeder** shipped 2026-05-25: `scripts/seed_lessons_from_benchmark.py` reads existing `.agent/benchmarks/benchmark_report_*.json` evidence and creates global candidate/blocked lessons only through `lesson_store` + `lesson_quality`; no active auto-promotion, no retrieval enablement, no benchmark run, no model call, no patch application, and no benchmark-report mutation.
- [x] **Phase 6.4c proposal-artifact lesson seeder** shipped 2026-05-25: `scripts/seed_lessons_from_proposals.py` reads existing validated `.agent/proposals/` evidence and creates repo-scoped candidate/blocked lessons only through `lesson_store` + `lesson_quality`; `--global-candidate` is explicit, failed evidence requires `--include-failed`, and it does not run workers, benchmarks, models, validation, patch application, or mutate proposal artifacts.
- [x] **Web proposal/benchmark workflow adjustment** shipped 2026-05-17: lesson cards can open originating proposal.md; Benchmarks tab can run all or selected cases without terminal; Add Case can infer validation command + expected changed files from patch/git evidence and optionally use the LLM as a requirements clerk for category/difficulty/strict prompt generation.
- [x] **Patch Safety gate** shipped: `core/patch_safety.py` blocks forbidden files and traversal at apply/test time; web apply routes surface `patch_safety` details instead of letting unsafe targets proceed.
- [x] **Phase 7.1-7.2.1.1 Mayor/workflow bridge** shipped 2026-05-21: handoff notes, optional temp-clone subagent runs, worker-run review/import, imported-proposal temp-clone validation, and deterministic lesson-artifact synthesis after passing validation.
- [x] **Phase 8-prep + Phase 8.1 MCP read-only foundation** shipped 2026-05-21: tool registry, `mcp_server.read_only`, and `scripts/mcp_readonly_server.py` expose 10 read-only evidence tools over stdio without write/apply/execute capabilities.
- [x] **Phase 8.2a artifact-write MCP handoff harness** shipped 2026-05-22: `mcp_server.artifact_write` exposes the read-only tools plus `create_handoff_note`; no subagent run, patch apply, lesson write, or arbitrary file write.
- [x] **Phase 8.2b MCP import-worker-run harness** shipped 2026-05-22: artifact-write MCP added `import_worker_run_as_proposal`, making the server 12 tools at that slice and leaving validation/lesson creation out of the import harness.
- [x] **Phase 8.2c MCP validate-imported-worker-proposal harness** shipped 2026-05-23: artifact-write MCP now also exposes `validate_imported_worker_proposal`, keeping validation temp-clone-only and evidence-writing under the proposal artifact directory.
- [x] **Phase 8.3 MCP audit ledger** shipped 2026-05-22: bounded invocation summaries in `.agent/mcp_audit/invocations.jsonl`, read-only `GET /mcp/audit`, and audit integration for artifact-write harness calls.
- [x] **MCP Inspector operator shortcuts and shutdown cleanup** shipped 2026-05-23: fixed-target Inspector launch route/UI for read-only and artifact-write servers, plus terminal-shutdown cleanup of matching local Inspector process trees.
- [x] **Phase 12.5i TS/JS Missing-Import Repair** shipped 2026-05-25: new `promote_ts_missing_import_candidate_to_patch_plan` in `patching/patch_gates.py` mirrors the Phase 12.5h dedup helper for the opposite failure mode. When a TS/JS `patch_candidate` uses an identifier exported by a same-directory sibling module but missing from both the snippet's own imports and the target file's imports, it gets promoted to a `patch_plan` that merges the missing specifier into an existing import line or inserts a fresh top-level named import, then runs the function replacement. New regexes capture `export function/const/class/type/interface/enum/let/var/async/abstract` declarations and `export { A, B as C }` lists; `export default` and `export *` are deliberately skipped. Path-traversal guarded via `_resolve_inside_repo` (rejects absolute paths and `..` escapes, every sibling read is `relative_to(repo_root)`-checked after `.resolve()`). Wired into `main.py` and `web/runner.py` alongside the dedup helper. The ts_nested_dispatch_root_cause benchmark now passes 1/1 on first attempt with no retries. Tests: `tests/test_ts_missing_import_promotion.py` — 13 cases covering merge-into-existing, fresh-insert, no-duplicate, no-export, no-new-identifier, the actual fixture end-to-end, non-TS/JS skip, existing-patch_plan respect, drift bailout, missing-file safety, path traversal refusal, and main/web wire-up checks.
- [x] **Phase 12.5j Linter Adapter for Phantom Limb** shipped 2026-05-25: new `core/linter_adapter.py` provides a read-only adapter that normalizes ESLint and Pylint JSON reports into a uniform finding shape (`tool`, `file`, `line`, `column`, `severity`, `rule_id`, `message`, `symbol`, `source`) and writes them to `<repo>/.agent/linter/findings.json`. Severity normalization: ESLint `1`→warning, `2`→error; Pylint `error`/`fatal`→error, `warning`→warning, `convention`/`refactor`/`info`→info. Path normalization runs every `filePath` through `_normalize_path`: converts `\` → `/`, resolves the path, refuses anything that lands outside `repo_root` (path-traversal guard), and emits POSIX-relative paths via `as_posix()`. Malformed entries are silently skipped with a `skipped_count`. CLI: `scripts/import_linter_findings.py --repo-path . --eslint-json eslint.json --pylint-json pylint.json` — argparse front-end with friendly exit-2 errors for missing reports, invalid JSON, and bad `--repo-path`. Console summary matches spec: `imported: N` / `skipped: M` / `output: .agent/linter/findings.json`. No linter execution, no npm/pip install, no model calls, no patch apply. Tests: `tests/test_linter_adapter.py` — 15 cases including ESLint/Pylint normalization, backslash → forward-slash conversion at adapter and unit-helper level, paths outside repo skipped + counted, malformed entries skipped (bad top-level, bad message dicts, unknown severity codes, non-string message fields, broken `messages` types, unknown Pylint types), output directory created on demand, and CLI happy/error paths including combined ESLint+Pylint runs.
- [x] **Phase 12.5k Budgeted Linter Fusion for Phantom Limb** shipped 2026-05-25: new `core/linter_fusion.py` lets Phantom Limb consume the normalized linter findings from `.agent/linter/findings.json` as read-only evidence. `load_linter_findings(repo_path)` is a path-traversal-guarded loader that returns `[]` on missing/malformed/non-list input. `fuse_into_phantom(phantom_findings, linter_findings)` is a pure fusion that annotates each phantom finding with `linter_evidence` (severity/line-sorted) and `linter_suspicion_boost` (cumulative: error +0.25, warning +0.10, info +0.05, capped at +0.40), and builds a prompt block from linter findings whose file matches a phantom candidate — irrelevant files are never injected. Strict prompt budget: `MAX_LINTER_FINDINGS_IN_PROMPT = 5`, `MAX_LINTER_PROMPT_CHARS = 800`. Prompt format matches the spec: `[LINTER HINTS — relevant static-analysis evidence]` header + bullets like `- pricing.ts:12 eslint/no-undef error: multiplyCents is not defined`, sorted by severity → file → line → rule_id. Header-only blocks are never emitted. Wired into `core/control_engine.py` `build_control_prompt` — one fusion call computes a `linter_hints_block` and is injected after each `[PHANTOM LIMB SUGGESTIONS …]` section (three identical templates updated via `replace_all`); on exception the fusion is skipped silently. Input dicts are never mutated by `fuse_into_phantom`; the control-engine wrapper does update `control_result["phantom_limb"]["findings"]` in place so downstream consumers can see the per-candidate evidence. PHANTOM_LIMB.json on disk is left alone — write-side belongs to the scanner. Tests: `tests/test_linter_fusion.py` — 26 cases covering loader robustness, severity boost differentiation, cap-at-0.40, mixed-severity sum-then-cap, no-match no-boost, input-immutability, prompt block size/char/relevance budgets, sort ordering, irrelevant-file exclusion, missing/malformed file no-ops via `fuse_for_repo`, existing Phantom Limb scan regression, and end-to-end `build_control_prompt` injection.

### Do next (refreshed 2026-05-23 after Phase 8.2c/8.3 and MCP Inspector cleanup shipped)

> 🤖 Order is **Claude-proposed**. User picks any in any order.

- [x] **Manual Level 3 trial on one reviewed item** — mark a single plan item `human_approved_for_proposal=true`, run `python scripts/run_patch_proposal_queue.py --max-items 1`, inspect `.agent/proposals/...`, and keep apply approval manual.
- [x] **Prompt-version quantifier panel (Phase 5.7) shipped 2026-05-26** — lives in the Benchmarks tab as "Prompt / Cost Quantifier". Reads `.agent/benchmarks/benchmark_report_*.json` only, groups by `brain_stamp.prompt_config_hash` (unknown bucket when missing), and shows runs · avg success · avg duration · avg fallbacks · avg tokens · avg cost · latest report. CLI: `scripts/build_prompt_cost_report.py`. Web route: `GET /benchmarks/prompt-cost`. Read-only — no benchmark execution, no model calls, no patch execution, no lesson seeding.
- [x] **Patch Safety gate** (forbidden-files + path-traversal, apply-time) — shipped; Phase 5 Polish, GPT-relocated from Phase 6.
- [ ] **Held-out eval set** (AI Suggestions § B) — cheap now, hard to retrofit.
- [ ] **Repeated-failure Dream seeding (deferred § D)** — still valid. Scans last N reports for cases failing >50% of the time.

### Do later

- **Dream execution quality - user-proposed direction (2026-05-16)**, sliced alpha/beta/gamma:
  - [x] **alpha. Time budget UI** - shipped 2026-05-16. Preset dropdown next to Start Overnight Run; clamped to [60, 86400] backend-side.
  - [x] **beta. Skip / Stop button** - shipped 2026-05-16. Graceful stop-between-items; `skipped_user_stop` status; orange stopping UI. Hard LLM-call cancellation deferred to beta.2 (would need cancellation tokens in every client).
  - [x] **gamma. Iterative self-improvement within budget** - shipped 2026-05-16. gamma.1 refines `planned_no_patch` and `research_note_created`; gamma.2 revalidates `ready_to_apply` via temp-clone patch-plan apply + validation + `lesson_quality` grading. UI now surfaces `auto_approved`, `needs_human_review`, or `blocked` lesson badges.
  - [x] **γ3.3. Explain why no `ready_to_apply`** - shipped 2026-05-17. Adds `patch_blockers[]` / `patch_blocker_summary`, detects common blockers (`safe_to_patch_false`, missing validation, uncertain files, vibe/manual/context restrictions, no generated patch), and renders a collapsed `why no patch` UI/report section.
- [x] **Context Poisoning Guard MVP** (AI Suggestions § M — Gemini-proposed PREREQUISITE for Phase 6 lessons). Standalone evaluator shipped 2026-05-16; wired into lesson storage + retrieval + CONTROL prompt 2026-05-17.
- [x] **Phase 6 lesson cards anchored to retrieval call site + behind § M promotion gate** — shipped 2026-05-17 as the manual-safe loop (6.0–6.3 + 6.4a manual CLI), with benchmark-report seeding shipped 2026-05-25 as 6.4b and proposal-artifact seeding shipped as 6.4c.
- [ ] **Phase 6.4 follow-up auto-creation** — wire Dream/proposal queues to feed repo-scoped lesson candidates without manual CLI runs. Must still gate through `lesson_quality`; human promotion or explicit CLI/operator intent required before anything becomes global active knowledge.
- [x] Phase 5 Polish: Benchmark run buttons shipped (`Run all` / `Run selected` / stop/status) plus Add Case clerk UI.
- [ ] Phase 5 Polish: markdown rendering of Dream report + benchmark language/category batch polish.
- [ ] Phase 8 remaining MCP polish: registry-driven Settings/Health row, handler-resolution smoke checks, optional schema metadata, and capability-mode persistence. Do not expose real-repo writes.
- [ ] Cost tracking (AI Suggestions § E)
- [ ] Self-bench experiment (AI Suggestions § F)
- [ ] Patch quality metrics (AI Suggestions § C) — diff size / files touched as quality signal

### Do much later / research / probably defer

- [ ] Phase 5.5: Parser backend service (probably indefinite defer — AI Suggestions § K)
- [ ] Phase 7: Reference-study loop (low ROI; AI Suggestion to defer harder)
- [ ] Phase 9: Docker app image (after SSD)
- [ ] Phase 10: Branched repair / MCTS — **mini-experiment first** (AI Suggestions § I)
- [ ] **Phase 11: Adversarial Self-Play (Counter-Knowledge + Reverse Dream)** — Claude-proposed 2026-05-17 (AI Suggestions § N). Blocked on § B (held-out eval set) and § C (patch minimality metric); experiment-gated (minimality ≥15% improvement without pass-rate drop). Two smaller alternates: Phase 11b (two-language invariant verification) and Phase 11c (honeypot benchmark cases) can ship independently as warm-ups.
- [ ] **Phase 12: Experiment Lab / Evaluation Governance** — GPT-proposed brainstorm 2026-05-17 + Claude-condensed. Hard prerequisite for Phase 11, Phase 10, and any speculative comparison. Builds on Brain Stamp; adds paired-run experiments with explicit greenlight rules.
- [ ] **Phase 13: Replay Debugger + Artifact Janitor** — GPT-proposed brainstorm 2026-05-17 + Claude-condensed. Extends `debug_last_control_prompt.txt` into structured per-run replay bundles; retention/cleanup rules hard-coded from day one. Ships independently; pairs naturally with Phase 12.
- [ ] **Phase 14: Failure Taxonomy** — GPT-proposed brainstorm 2026-05-17 + Claude-condensed. Blocked on Phase 6.4 auto-creation. Do NOT design the taxonomy upfront; derive it from accumulated lesson tags + benchmark failure clusters.
- [ ] Future: Browser agent (after Phase 8; AI Suggestions § J)
- [ ] Future: Gastown / Mayor pattern reference study (covered by Phase 7; possible MCP/tool-registry inspiration for Phase 8; no new numbered phase)
---

## One-line focus

```text
Phase 5 Core done. AgentBench --retry-failed shipped and the clean 31/31 fast run exists.
Brain Stamp plus Phase 4.5 Levels 1-3 CLI MVP shipped: reporter, Dream planner, and gated patch proposal queue.
Phase 6 manual-safe memory loop shipped (2026-05-17): bucketed lesson storage, Memory tab promote/block UI,
  active-only retrieval with tags, CONTROL prompt injection behind
  LESSON_RETRIEVAL_ENABLED, manual proposal→lesson CLI. Phase 6.4b benchmark-report lesson seeder
  shipped 2026-05-25 as global-candidate-only; Phase 6.4c proposal-artifact seeder shipped
  as repo-scoped-by-default with explicit global opt-in. Dream auto-lessonization remains deferred.
Phase 7.1 Mayor Mode handoff + optional subagent runner shipped (2026-05-21): pure storage handoff notes under .agent/handoffs/, temp-clone subprocess runner, memory-tab UI panel.
Phase 7.2 Worker Run Review / Import shipped (2026-05-21): core/worker_runs.py + /worker-runs/view + /worker-runs/import + Memory tab Worker Runs subsection. Bridges 7.1 outputs into the existing proposal -> lesson review path without bypassing safety gates.
Phase 7.2.1 Validate Imported Worker Proposals shipped (2026-05-21): core.worker_runs.validate_imported_worker_proposal + POST /proposals/validate + UI Validate button. Applies worker patch_plan.json in a temp clone of repo_path, runs the inferred validation command, writes apply_result.json + validation.json + validation_output.txt into the proposal_dir. Real repo / repo_path byte-identical before/after.
Phase 7.2.1.1 Make Validated Worker Imports Lesson-Promotable shipped (2026-05-21): synthesize_lesson_artifacts_for_validated_worker_proposal writes deterministic case.json + patch_proposal.json after a passing validate. End-to-end test proves scripts/create_lesson_from_proposal.py accepts the synthesized dir as a candidate lesson.
Phase 8-prep Tool Registry MVP shipped (2026-05-21): core/tool_registry.py + GET /tools/registry. Metadata-only catalog of 18 operations (9 read + 3 artifact_write + 6 disabled-for-MCP) with four capability modes (read_only / artifact_write / operator / unsafe_dev). No MCP server, no network exposure, no behavior changes — just the source of truth for "what's safe to hand to an external agent."
Phase 8.1 Read-only MCP server shipped (2026-05-21): mcp_server.read_only + scripts/mcp_readonly_server.py expose 10 evidence-reading tools over stdio; no writes, subprocesses, proposal creation, validation, apply, or lesson mutation.
Phase 8.2a/8.2b/8.2c Artifact-write MCP shipped (2026-05-22/23): mcp_server.artifact_write exposes exactly 13 tools: the 10 read-only tools plus create_handoff_note, import_worker_run_as_proposal, and validate_imported_worker_proposal.
Phase 8.3 MCP audit ledger shipped (2026-05-22): bounded invocation summaries under .agent/mcp_audit/invocations.jsonl plus GET /mcp/audit. Audit is observational, not an authorization gate.
MCP Inspector operator shortcuts/cleanup shipped (2026-05-23): fixed-target launch route/UI for read-only and artifact-write servers, plus shutdown cleanup for matching local Inspector process trees.
Next: prompt-version quantifier / held-out eval / repeated-failure Dream seeding, then optionally Dream lesson auto-creation. Benchmark run buttons + Add Case clerk are now shipped; remaining Benchmark polish is category/language batch + report density.
Do not add MCTS yet — require a 10-case mini-experiment first.
```

---

## Phase 7.1 — Mayor Mode handoff + optional subagent runner (shipped 2026-05-21)


Spec: `docs/superpowers/specs/2026-05-20-phase-7-1-mayor-mode-design.md`
Plan: `docs/superpowers/plans/2026-05-20-phase-7-1-mayor-mode.md`

MVP for operator-driven external-agent handoffs. Sits next to the existing
proposal queue / lesson loop, does not replace any of it.

### What this phase adds

- `core/handoff_notes.py` — pure storage for `.agent/handoffs/<YYYYMMDD_HHMMSS>_<slug>.md` notes with JSON frontmatter (HTML-comment-delimited so no new YAML dep), default safety rules, default forbidden files (`.env`, `.agent`, `.git`, `node_modules`, `target`, `tests`), brain stamp via `core.brain_stamp.collect_brain_stamp`, and a `safety_overrides` audit list when `allowed_files` overlaps a default-forbidden path.
- `scripts/create_handoff_note.py` — CLI wrapper, no web required.
- `scripts/run_subagent_handoff.py` — temp-clone runner. **Default: dry-run.** `--allow-run` is the only switch that actually executes a subprocess. Always `shutil.copytree`s the repo to a temp clone first; never writes back to the real repo (artifacts go under `.agent/worker_runs/<run>/`). 300s default timeout, overridable with `--timeout-sec`. Worker command map (`codex / claude-code / gemini / other`) is env-var overridable (`HANDOFF_<WORKER>_CMD`). Status transitions `draft → ran / failed` only on real runs; dry-run leaves the note as `draft`.
- Web routes: `POST /handoffs/create`, `GET /handoffs/list`, `POST /handoffs/run`, `GET /worker-runs/list`.
- Memory tab: new "Mayor Mode (Handoffs)" panel between the proposals and lessons sections, with the explicit "Allow running subagent in temp clone" checkbox. Clicking "Create + Run" without ticking it is refused client-side.
- Tests: 25 covering core, runner script, and web routes. Real-repo byte-identical assertion in the temp-clone test (SHA-256 of every tracked file before/after).

### Guardrails (verified by tests, not just claimed)

- Subagents do not run by default.
- Subagents never run in the real repo.
- Patches are never applied to the real repo from a handoff run.
- Nothing commits or pushes.
- Lessons are not auto-promoted.
- Patch Safety gate is unchanged.
- Dream / proposal / lesson flow is unchanged.

### 🤖 Claude-proposed Phase 7.1.1+ follow-ups (pending user decision)

These are extensions Claude noticed while designing 7.1. They are **candidate
scope, not yet sanctioned by the user**:

1. **"Create handoff from this item" button** on proposal cards and Dream item cards. Pre-fills title, `repo_path`, `validation_command`, and `allowed_files` from the source artifact. Low cost, high UX value once the panel is in place. Deferred from MVP to keep the surface small.
2. **Surface worker `proposal.md` back into the proposals queue.** If a temp-clone run produces a `proposal.md` and `patch_plan.json`, offer a one-click promotion path that materializes a normal `.agent/proposals/<run>/<item>/` so the Patch Safety gate + lesson flow runs on it like any other proposal. This is the natural bridge between Mayor Mode and the existing Phase 6.4 lesson loop.
3. **Streaming worker output.** The current `/handoffs/run` route blocks until the subprocess exits, which can hit Flask's default request timeout for slow agents. Replace with an async runner + status polling, modeled on `core/proposal_runner.py`.
4. **Worker-quota meter.** Show a small estimate of "this handoff has X allowed_files and ~Y context tokens" to help operators gauge cost before clicking Run. Cheap to add; high signal.
5. **Replay-from-handoff.** Add `python scripts/run_subagent_handoff.py --note <path> --replay` that re-runs an existing handoff with the same command but a fresh temp clone. Useful for retrying after a flaky network error without re-typing context.
6. **End-to-end env-var override test.** Today the env-var override is unit-tested at the resolver level only; an end-to-end test that actually shells out to a stub `HANDOFF_OTHER_CMD` script would catch shell-quoting bugs.
7. **Handoff archival UI.** The data model already supports `status: archived`; expose an Archive button + filter on the panel so the active list stays readable past 20+ handoffs.

---

## Phase 7.2 — Worker Run Review / Import (shipped 2026-05-21)

Spec: `docs/superpowers/specs/2026-05-21-phase-7-2-worker-run-review-design.md`
Plan: `docs/superpowers/plans/2026-05-21-phase-7-2-worker-run-review.md`

The bridge from Phase 7.1 worker outputs into the existing proposal review path. No execution, no validation, no apply.

### What this phase adds

- `core/worker_runs.py` — pure storage + validation. Public API: `list_worker_runs`, `read_worker_run`, `detect_worker_outputs`, `import_worker_run_as_proposal`. Path-traversal guarded against escaping `.agent/worker_runs/`. Never writes outside the new proposal dir.
- Web routes:
  - `GET /worker-runs/list` — refactored to delegate to `core.worker_runs.list_worker_runs`, **preserving the Phase 7.1 response shape** (additive new fields only: `run_id`, `handoff_title`, `has_proposal_md`, `has_patch_plan_json`, `has_handoff_md`, `has_worker_run_json`).
  - `GET /worker-runs/view?run_id=...` (or `?path=...`) — full detail including `raw_output_preview` (capped at 2000 chars).
  - `POST /worker-runs/import` — imports a complete, non-dry-run worker run.
- Memory tab: new "Worker Runs" subsection under Mayor Mode with View details (inline raw output preview, command, started_at, duration) and Import as proposal (button disabled for dry-run / incomplete runs, with explicit tooltip).
- Imported proposals land in `.agent/proposals/<YYYYMMDD_HHMMSS>/01-<slug>/` with a synthetic `item.json` (`kind=worker_run_import`, `source=worker_run`, `human_approved_for_proposal=false`, `needs_revalidation=true`) and a `source_metadata.json` pointing back to the original `worker_runs/` dir. The four required files (`handoff.md`, `worker_run.json`, `proposal.md`, `patch_plan.json`) plus optional `raw_output.txt` are copied across.
- Tests: 25 new (17 in `tests/test_worker_runs.py` + 8 in `tests/test_worker_runs_routes.py`). Full suite at 274/274 passing. Real-repo SHA-256 byte-identical assertion in the import tests.

### Guardrails (verified by tests, not just claimed)

- Subagents do not run in this slice.
- Worker output is never auto-applied to the real repo.
- Imported proposals carry `human_approved_for_proposal=false`, so `scripts/run_patch_proposal_queue.py` will skip them by default.
- The lesson-promotion path is unchanged: a worker-run import is intentionally NOT directly promotable because it lacks `apply_result.json` / `validation.json` / `case.json`. The operator must re-run through validation first (deferred to Phase 7.2.1).
- Patch Safety gate is unchanged.
- Path traversal: any `run_id` or `path` that escapes `.agent/worker_runs/` is rejected before any disk read of the content.

### 🤖 Claude-proposed Phase 7.2.1+ follow-ups (pending user decision)

1. **Re-validate worker patch_plan in a temp clone.** The natural next slice. Takes an imported worker-run proposal, applies the patch_plan in a temp clone, runs a user-supplied or detected validation command, and stamps the proposal with `apply_result.json` + `validation.json` — at which point it becomes lesson-promotable like any other proposal.
2. **Diff preview against real repo.** Compute `git diff` between real repo state and the worker's patch_plan before import, so the operator can eyeball the change inline.
3. **Idempotency / dedup.** Hash the worker run's `(handoff.md + patch_plan.json)` and refuse re-import if the same proposal already exists.
4. **"Imported from worker_run" badge in the Proposals list.** The list view currently treats worker-run imports the same as normal proposals (because `item.json` is structurally compatible). A small visual badge would surface provenance.
5. **Tail-streaming raw_output.** For long worker runs, the inline preview is capped at 2000 chars. A "show full output" toggle that fetches the file in chunks would help debug timeouts.

---

## Phase 7.2.1 — Validate Imported Worker Proposals (shipped 2026-05-21)

Spec: `docs/superpowers/specs/2026-05-21-phase-7-2-1-validate-imported-proposals-design.md`
Plan: `docs/superpowers/plans/2026-05-21-phase-7-2-1-validate-imported-proposals.md`

The validation half of the Phase 7.1 → 7.2 bridge. After 7.2.1, the operator can see whether the worker's `patch_plan.json` actually applies and validates without touching the real repo.

### What this phase adds

- `core.worker_runs.validate_imported_worker_proposal(proposal_dir, repo_path, *, proposals_root=None, validation_timeout_sec=60)` — copies `repo_path` to a temp clone with the standard ignore_patterns (`.git`, `.agent`, `node_modules`, `target`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, `dist`, `build`), applies the imported `patch_plan.json` via `run_patch_plan_with_artifacts(validation_command=None)`, then runs the inferred validation command via `scripts.run_patch_proposal_queue._run_validation_command` (same allow-list + segmented-timeout discipline as the existing proposal queue). Writes `apply_result.json`, `validation.json`, `validation_output.txt` into the proposal_dir. Updates `item.json` with `needs_revalidation=False` and `validation_status` (`passed` / `failed` / `no_command`) without rewriting any other fields.
- Web route: `POST /proposals/validate` taking `proposal_dir` + `repo_path` + optional `validation_timeout_sec`. Maps `FileNotFoundError` / `ValueError` to 400, unexpected to 500.
- UI: Worker Runs section's post-import status now offers a **Validate imported proposal** button. Reads `repo_path` from the existing input or via prompt, posts to `/proposals/validate`, and renders the result inline (apply ✓/✗, validation ✓/✗/·, message, artifact paths).
- Tests: 7 new in `tests/test_worker_runs.py` (refuses missing `patch_plan.json`, rejects path traversal, rejects missing `repo_path`, writes all three artifact files on happy path, real-repo SHA-256 byte-identical before/after, failed apply doesn't crash, empty inferred command records `no_command`). 4 new in `tests/test_worker_runs_routes.py` (happy path, missing proposal_dir, missing repo_path, path-traversal rejection). Full suite at **285/285** passing.

### Guardrails (verified by tests, not just claimed)

- Real repo and `repo_path` are byte-identical before and after every validate call.
- Subagents do not run in this slice.
- Patch is never applied to the real repo or to `repo_path` directly — only to the temp clone.
- `case.json` / `patch_proposal.json` are NOT synthesized — worker-run imports remain non-lesson-promotable via `scripts/create_lesson_from_proposal.py` until a follow-up slice handles their shape explicitly.
- Path traversal: any `proposal_dir` that escapes `.agent/proposals/` is rejected before any file read.
- Failed apply records `apply_success=False` and `validation_status="failed"` without raising; UI surfaces the error inline.

### 🤖 Claude-proposed Phase 7.2.1.1+ follow-ups (pending user decision)

1. **Worker-run lesson candidacy.** Synthesize a minimal `case.json` + `patch_proposal.json` from `handoff.md` + worker artifacts after a passing validate, so the existing `create_lesson_from_proposal.py` flow accepts the import. This closes the last gap between Phase 7.1 and lesson candidacy.
2. **Validate button on every worker-run-import proposal card.** Today the button only appears in the Worker Runs section's post-import status. Adding it to each card in the Proposals list lets the operator re-validate later runs of the same import.
3. **Custom validation_command override.** UI input to override the inferred command (useful when `inspect_repo_inventory` guesses wrong, or for ad-hoc smoke tests).
4. **Explicit patch-safety call.** The validate step currently relies on `apply_patch_plan`'s per-op gates. Calling `evaluate_patch_safety` upfront would short-circuit clearly-unsafe plans with a 400 instead of an apply error.
5. **Async + progress polling.** The route is synchronous; long validation can hit Flask's default timeout. Mirror `core/proposal_runner.py` for an async variant with state polling.

---

## Phase 7.2.1.1 — Make Validated Worker Imports Lesson-Promotable (shipped 2026-05-21)

Spec: `docs/superpowers/specs/2026-05-21-phase-7-2-1-1-lesson-artifact-synthesis-design.md`
Plan: `docs/superpowers/plans/2026-05-21-phase-7-2-1-1-lesson-artifact-synthesis.md`

Closes the last gap between Phase 7.1 handoff output and the lesson candidacy path. After a passing validate, `scripts/create_lesson_from_proposal.py` now accepts a worker-run import end-to-end — without any change to the lesson promoter, `lesson_quality`, or any safety gate.

### What this phase adds

- `core.worker_runs.synthesize_lesson_artifacts_for_validated_worker_proposal(proposal_dir, validation_result=None, *, proposals_root=None)` — deterministic synth (no LLM) that writes a minimal `case.json` and `patch_proposal.json` into the proposal_dir. Self-gates on `apply_result.success=True` AND `validation.validation_ok=True`; returns `{ok=False, skipped_reason}` otherwise. Preserves any existing `case.json` / `patch_proposal.json` verbatim and records them in `preserved`.
- `validate_imported_worker_proposal` now always calls the synth helper. The validate response carries a new `lesson_artifacts: {ok, created, preserved, skipped_reason}` field; existing keys unchanged.
- UI: the validate-result panel renders one muted line — "Lesson artifacts ready (case.json, patch_proposal.json)" on success, "Lesson artifacts not created: \<reason\>" on skip.
- Tests: 13 new helper tests (happy path, both failure gates, both preservation paths, both missing-file refusals, path traversal, language inference, summary extraction + fallback, real-repo SHA-256), 2 new wiring tests, 2 new route tests, and 1 end-to-end integration test that proves `create_lesson_from_proposal.create_lesson_from_proposal(proposal_dir)` returns `status="candidate"` after the synth. Full suite at **300+/300+** passing.

### Synthesis details

- **case.json:** carries both `name` and `case_name` (= slug from `item.json.title` or `proposal_dir` name minus numeric prefix), `language` (inferred from the first recognized changed-file extension via `config.LANGUAGE_MAP`, else `"unknown"`), `category="worker_import"`, `difficulty="unknown"`, `validation_command` from `validation.json.command`, `source="worker_run"`, and explicit empty `expected_changed_files` / `forbidden_changed_files` lists so the lesson promoter's set math short-circuits cleanly.
- **patch_proposal.json:** carries `source="worker_run"`, `patch_kind="patch_plan"`, `summary` (first non-blank line of `proposal.md` that isn't a markdown header / code fence / HTML comment; falls back to `"Worker-run import: <slug>"`), `changed_files` (from plan ops), `validation_ok=True`, `apply_success=True`, the full `patch_plan` embedded verbatim (so `_determine_patch_kind` returns `"patch_plan"`), `patch_candidate=null`, and `needs_human_review=false`.

### Guardrails (verified by tests)

- No LLM call. Pure deterministic synth from existing artifacts.
- No auto-creation of lessons. The CLI still runs.
- No auto-promotion. The end-to-end test asserts `status="candidate"` and `active_knowledge_allowed=False`.
- No real-repo writes. SHA-256 round-trip check in the synth tests.
- No subagent re-runs.
- `lesson_quality` behavior unchanged — it evaluates the synthesized artifacts the same way it evaluates queue-proposal artifacts.
- `create_lesson_from_proposal.py` safety gate unchanged — it still refuses unless `apply_success` AND `validation_ok` are both True (which the synth guarantees by gating).
- Patch Safety gate unchanged.

### 🤖 Claude-proposed Phase 7.2.1.1+ follow-ups

1. **"Create candidate lesson" button in the Worker Runs section.** Right after a passing validate with `lesson_artifacts.ok=True`, offer a one-click button that POSTs to a new `/proposals/promote` (existing) or a new `/proposals/lessonize` endpoint. Today the operator runs the CLI manually.
2. **Custom `case_name` / `category` override on synth.** UI text inputs so the operator can label the worker-derived case more usefully than the auto-derived slug.
3. **Surface `expected_changed_files` from operator input.** The current empty default short-circuits the lesson promoter's set math; an operator-supplied expected list would make the resulting lesson stricter.
4. **Re-synthesize on demand.** Today the helper preserves existing artifacts; a future `?regenerate=true` query param or `--force` flag would let the operator re-derive after editing `proposal.md`.
5. **Async + progress polling for the whole validate+synth flow.** Same deferred follow-up as 7.2.1; not specific to synthesis.

---

## Phase 8-prep — Tool Registry MVP (shipped 2026-05-21)

Spec: `docs/superpowers/specs/2026-05-21-phase-8-prep-tool-registry-design.md`

Single source of truth describing which CATTUS operations are candidates for future MCP exposure. **Metadata only.** No MCP server, no network exposure, no SDK dependency, no behavior changes anywhere else.

### What this phase adds

- `core/tool_registry.py` — a constant tuple of 18 tool dicts. Public API: `list_tools()`, `get_tool(name)`, `tools_by_category(category)`, `is_tool_allowed(name, capability_mode="read_only")`. All accessors return deep copies; the registry itself is immutable from outside.
- `GET /tools/registry` — read-only endpoint wrapping `list_tools()`. Intended for the future Settings/Health debug UI.
- Module-import-time invariant assertions: a tool with `category="real_repo_write"` MUST have `can_touch_real_repo=True`; a `category="read"` tool MUST have `can_touch_real_repo=False` and `can_run_subprocess=False`. Malformed registry entries fail loudly the first time anyone imports the module.
- Tests: 26 unit tests in `tests/test_tool_registry.py` + 3 Flask client tests in `tests/test_tool_registry_routes.py`. Full suite at **352/352** passing.

### Initial roster (18 tools)

- **Read (9):** `get_health`, `list_benchmark_reports`, `read_benchmark_report`, `list_dream_reports`, `read_dream_report`, `list_lessons`, `read_lesson_proposal`, `list_worker_runs`, `read_worker_run`.
- **Artifact-write (3):** `create_handoff_note`, `import_worker_run_as_proposal`, `validate_imported_worker_proposal`. Only `validate_imported_worker_proposal` has `can_run_subprocess=True` (inside a temp clone) and `requires_human_approval=True`.
- **Registered but disabled for MCP (6):** `apply_patch`, `apply_patch_plan`, `dream_apply` (all `real_repo_write`); `run_subagent_handoff` (`temp_clone_execute`, quota-spending); `promote_lesson`, `block_lesson` (`memory_write`). All carry `mcp_exposable=False` and `default_enabled=False`.

### Capability mode semantics

| Mode | Allowed categories | mcp_exposable kill switch? |
|---|---|---|
| `read_only` | `read` | yes |
| `artifact_write` | `read` + `artifact_write` | yes |
| `operator` | `read` + `artifact_write` + (`memory_write` / `temp_clone_execute` when `requires_human_approval=True`); **never** `real_repo_write` | yes |
| `unsafe_dev` | everything | **no** (this mode is for internal dashboards only and must never reach a real MCP server) |

`is_tool_allowed(unknown_name, "read_only")` returns `False`, not an exception. `is_tool_allowed("get_health", "bogus_mode")` raises `ValueError`.

### Guardrails (verified by tests)

- No MCP dependency added. `requirements.txt` is untouched.
- No network server. The only new HTTP surface is `GET /tools/registry`, which reads in-process data.
- No tool is wired to its underlying function in this slice — `route_or_function` is a string pointer that future code can resolve.
- Disabled-for-MCP tools (`apply_patch`, `dream_apply`, etc.) are blocked in every mode except `unsafe_dev`.
- `real_repo_write` is never allowed in `operator` mode, even if `requires_human_approval=True`. Real-repo writes from external agents remain out of scope until at least Phase 8.x.

### Phase 8 follow-up status (refreshed 2026-05-23)

1. ~~**MCP server scaffolding.**~~ Shipped as Phase 8.1 read-only MCP and Phase 8.2 artifact-write MCP. Real-repo writes remain unexposed.
2. **Per-tool input schemas.** Partially handled by strict dict-in/dict-out MCP harnesses, including validate-imported-proposal input validation; registry-level JSON Schema metadata is still deferred.
3. **Capability-mode persistence.** Still deferred. Current MCP servers use fixed, narrow surfaces rather than a runtime mode selector.
4. ~~**Per-tool audit log.**~~ Shipped as Phase 8.3 for artifact-write harness calls. A generic wrapper for every MCP tool remains future scope.
5. **Registry-driven Settings/Health row.** Still deferred.
6. **`Validate that handler exists` smoke check.** Still deferred.

---

## Phase 8.2a — Artifact-Write MCP Handoff Harness (shipped 2026-05-22)

Spec: `docs/superpowers/specs/2026-05-22-phase-8-2a-artifact-write-mcp-design.md`
Plan: `docs/superpowers/plans/2026-05-22-phase-8-2a-artifact-write-mcp.md`

Second MCP server, still narrow by construction. It exposes all 10 read-only MCP tools plus exactly one write-capable helper in this slice: `create_handoff_note`.

### What this phase adds

- `mcp_server/artifact_write.py` — importable without `mcp`, fixed `CAPABILITY_MODE="artifact_write"`, and an explicit `_EXTRA_WRITE_TOOLS` allowlist stricter than the registry's whole artifact-write mode.
- `create_handoff_note_harness(input)` — strict dict-in/dict-out boundary around `core.handoff_notes.create_handoff_note`.
- `scripts/mcp_artifact_write_server.py` — stdio server shim mirroring the read-only MCP launcher.
- Tests for the exposed surface, strict input validation, path safety, missing optional `mcp` dependency behavior, and subprocess tripwires.

### Guardrails

- Writes only handoff-note artifacts under `.agent/handoffs/`.
- Does not run subagents, execute validation, apply patches, touch the real repo, promote lessons, or accept arbitrary paths.
- Does not expose `import_worker_run_as_proposal` or `validate_imported_worker_proposal` in this slice.

## Phase 8.2b — MCP Import Worker Run Harness (shipped 2026-05-22)

Spec: `docs/superpowers/specs/2026-05-22-phase-8-2b-import-worker-run-mcp-design.md`
Plan: `docs/superpowers/plans/2026-05-22-phase-8-2b-import-worker-run-mcp.md`

Extends the artifact-write MCP server with one more narrow helper: `import_worker_run_as_proposal`.

### What this phase adds

- `_EXTRA_WRITE_TOOLS` now contains `create_handoff_note` and `import_worker_run_as_proposal`.
- `import_worker_run_as_proposal_harness(input)` accepts exactly one field, `worker_run_id`, and rejects absolute paths, separators, traversal-shaped ids, empty ids, and unknown fields before core code runs.
- The harness delegates to `core.worker_runs.import_worker_run_as_proposal(worker_run_id)` and returns only `{ok, proposal_dir, message}`.
- At the end of this slice, artifact-write MCP exposed exactly 12 tools: 10 read-only tools plus the two artifact-write helpers.
- Phase 8.3 audit events cover success and blocked import attempts.

### Guardrails

- The harness copies an existing complete worker-run artifact into `.agent/proposals/`; it does not run a worker.
- It writes no `validation.json`, `apply_result.json`, `case.json`, or `patch_proposal.json`.
- It does not validate, apply, create lessons, promote lessons, or mutate the real repo.
- `mcp_server.read_only` remains exactly 10 tools and exposes no artifact-write helpers.

---

## Phase 8.2c — MCP Validate Imported Worker Proposal Harness (shipped 2026-05-23)

Spec: `docs/superpowers/specs/2026-05-23-phase-8-2c-validate-imported-worker-proposal-mcp-design.md`
Plan: `docs/superpowers/plans/2026-05-23-phase-8-2c-validate-imported-worker-proposal-mcp.md`

Adds the third narrow artifact-write tool: `validate_imported_worker_proposal`. It wraps the existing Phase 7.2.1 core helper for MCP clients without opening a real-repo write path.

### What this phase adds

- Accept only `proposal_ref` under `.agent/proposals/` and an existing directory `repo_path`.
- Apply the proposal's `patch_plan.json` only in a temp clone.
- Run the inferred validation command only in that temp clone.
- Write validation evidence back into the proposal artifact directory.
- Preserve Phase 7.2.1.1's self-gated lesson-artifact synthesis behavior: `case.json` and `patch_proposal.json` appear only after apply and validation both pass.
- Audit success and blocked calls through the Phase 8.3 ledger.
- Artifact-write MCP now exposes exactly 13 tools.

### Guardrails

- No real-repo patch apply.
- No subagent launch.
- No arbitrary proposal path from MCP.
- No lesson creation beyond existing synthesized proposal artifacts.
- No lesson promotion/blocking.
- No read-only MCP surface expansion.

---

## Phase 8.3 — MCP Invocation Audit Ledger (shipped 2026-05-22)

Spec: `docs/superpowers/specs/2026-05-22-phase-8-3-mcp-invocation-audit-ledger-design.md`
Plan: `docs/superpowers/plans/2026-05-22-phase-8-3-mcp-invocation-audit-ledger.md`

Adds accountability for MCP artifact-write calls without expanding the MCP permission surface.

### What this phase adds

- `core/mcp_audit.py` — append-only, bounded JSONL ledger at `.agent/mcp_audit/invocations.jsonl`.
- Sanitized event shape: id, timestamp, tool name, capability mode, allowed flag, bounded input/result summaries, artifact paths, and bounded error text.
- Artifact-write harness integration for success and blocked validation paths.
- `GET /mcp/audit?limit=50` — read-only route for recent valid events, with limits clamped to a maximum of 200.

### Guardrails

- Audit records summaries, not full prompts, secrets, environment variables, or validation output.
- Corrupt JSONL lines are skipped on read instead of breaking the audit view.
- Audit persistence failures are logged and swallowed; observability never changes authorization or harness success/failure behavior.

---

## MCP Inspector Operator Shortcuts (shipped 2026-05-23)

Plan: `docs/superpowers/plans/2026-05-22-mcp-inspector-subagent-shortcut.md`

Adds local operator convenience for inspecting the two MCP servers without turning the browser into an arbitrary command launcher.

### What this phase adds

- `POST /mcp/inspector/launch` — accepts only fixed targets: `read_only` or `artifact_write`.
- Fixed command map to `scripts/mcp_readonly_server.py` and `scripts/mcp_artifact_write_server.py` through `npx -y @modelcontextprotocol/inspector python <script>`.
- Sub-agent header UI controls for "Inspect read-only MCP" and "Inspect artifact-write MCP".
- A compact link to `/mcp/audit?limit=10`.

### Guardrails

- The route does not accept arbitrary commands or script paths.
- Unknown targets are rejected before process launch.
- Launch failures return a bounded error to the UI.

---

## MCP Inspector Web Shutdown Cleanup (shipped 2026-05-23)

Plan: `docs/superpowers/plans/2026-05-23-mcp-inspector-web-shutdown-cleanup.md`

Stops local MCP Inspector process trees when the Flask web server exits from normal terminal shutdown paths.

### What this phase adds

- `web/mcp_inspector_processes.py` — standard-library process snapshot/matching/termination helper for Windows and POSIX.
- `web.runner` — shared Flask run wrapper that calls `stop_mcp_inspectors()` after `app.run()` exits, including `KeyboardInterrupt`.
- `web.app` direct entrypoint now uses the same runner wrapper.
- Tests for command matching, cleanup selection, current-process protection, and runner shutdown behavior.

### Guardrails

- Matches only command lines containing the official `@modelcontextprotocol/inspector` package token.
- Does not terminate unrelated `npx`, `node`, Python MCP server, or URL-only processes.
- Skips process trees containing the current process.


