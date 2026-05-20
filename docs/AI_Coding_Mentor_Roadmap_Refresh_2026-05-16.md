# AI Coding Mentor — Roadmap Refresh

> Updated after AgentBench 22-case expansion, Phase 2 reporting upgrades, Dream V2 benchmark seeding (with dedupe + flaky-case seeding), local DB recovery, **Phase 5 web workspace revamp completion (Slices 1-5 shipped 2026-05-16)**, flaky-case Benchmarks tab rendering, **Dream execution-quality Slices alpha/beta/gamma shipped (2026-05-16)** including ready-to-apply revalidation + lesson-quality badges, **Dream Slice γ3.3 shipped (2026-05-17)** explaining why planned items are not `ready_to_apply`, **Brain version stamp + Phase 4.5 Level 1 background reporter shipped (2026-05-17)**, **Phase 4.5 Levels 2-3 CLI MVP shipped (2026-05-17)**, and **Phase 6 manual-safe memory loop shipped (2026-05-17)** — bucketed lesson storage, Memory tab promote/block UI, active-only retrieval, CONTROL prompt injection behind `LESSON_RETRIEVAL_ENABLED`, manual proposal→lesson CLI, and lesson tags (auto-creation from benchmarks/Dream remains deferred).

> **Reading convention for other AI agents:** items prefixed with **🤖 Claude-proposed**, **🤖 Gemini-proposed**, or **🤖 GPT-proposed** are AI-generated suggestions, dated and **pending the user's accept/reject decision**. Treat them as candidate scope, NOT confirmed work. The user has consulted multiple AIs; provenance is shown so future readers (human or AI) can see who said what.

## Current checkpoint

The project is a coding-agent workspace, not a Gemini patch script. Phase 5 web revamp is fully shipped.

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
  - `core/lesson_store.py` — bucketed `.agent/<project_tag>/lessons/{candidate,active,blocked}/<id>.json` storage with atomic moves, path-traversal guards, optional `LESSON_AUTO_ACTIVE` flag (default false → human must promote), and `derive_lesson_tags()` helper
  - Memory tab — filter buttons (All/Candidate/Active/Blocked), promote/block actions, lesson cards with tag chips, safety copy explaining advisory-only status
  - `core/lesson_retrieval.py` — `list_active_lessons` / `find_active_lessons` / `format_lessons_for_prompt`; reads ONLY `active/`; defensive double-filter on the top-level `active_knowledge_allowed` flag; per-repo + global scope union so lessons saved without `--repo-path` are visible everywhere; per-repo lessons stay isolated
  - Deterministic keyword scoring: case_name +100, tag +25, language/category +10, query-token +5 (all binary); tokenized free-form queries with English + generic-action-word stopword list (`fix`, `bug`, `patch`, `issue`, `problem`) to prevent cross-language false positives; limit clamped to [1, 20]
  - CONTROL prompt injection (`core/control_engine.py`) gated by `LESSON_RETRIEVAL_ENABLED` (default false), with `LESSON_RETRIEVAL_LIMIT` and `LESSON_RETRIEVAL_MAX_CHARS`; `[ACTIVE LESSONS — advisory hints, lowest priority]` block sits between `[PHANTOM LIMB SUGGESTIONS]` and `[USER]`; fail-closed (any error → empty block, prompt still builds); 4 production callers updated to pass `repo_path`
  - `scripts/create_lesson_from_proposal.py` — manual CLI that turns a validated `.agent/proposals/<run>/<item>/` artifact into a lesson candidate; explicitly populates tags; refuses by default if validation/apply failed (override with `--allow-failed`); path-traversal guarded; never modifies the real repo
  - Auto-creation from benchmark/Dream/proposal queues is **explicitly deferred** to Phase 6.4 — today only the manual CLI flow exists, keeping the loop "manual-safe"
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
  - 22 cases exist
  - `--check`: 22 cases, 0 errors
  - Official clean full fast run achieved:
    - 22/22 passed, flaky: 0, with --retry-failed 1 enabled.
- Phase 4.5 CLI background/proposal MVP:
  - Level 1 reporter: `scripts/run_background_reporter.py` runs benchmark checks/runs, writes `.agent/reports/background_report_*.md/json`, includes Brain Stamp, and emits regression alerts.
  - Level 2 planner: `scripts/run_background_dream_planner.py` reads the latest meaningful benchmark report and writes `.agent/reports/background_dream_plan_*.md/json` with failed, flaky, and slow-passing cases.
  - Level 3 proposal queue: `scripts/run_patch_proposal_queue.py` reads Level 2 plan JSON and processes only items explicitly marked `human_approved_for_proposal=true`; default `--max-items 1`.
  - Guardrails: CLI-only; no Flask background thread; no automatic schedule; no benchmark runner changes; no Dream queue format changes; no real-repo patch/apply/commit/push.
- **Web workspace (Phase 5 complete — 2026-05-16):**
  - 6 workspace tabs: Chat/Patch, Benchmarks, Dream, Memory, Graph, Settings/Health
  - ARIA-correct workspace tablist (role=tablist/tab/tabpanel, aria-controls/labelledby/selected)
  - Settings/Health panel: 15 checks (API keys, Postgres, embeddings, Ollama, Tree-sitter, Python/Node/Go/Rust/g++ toolchain)
  - Benchmarks tab: sidebar of past runs (newest first), structured detail panel (totals/groups/flaky/slowest/failed cases), flaky count + Flaky Cases table, "Seed Dream queue from this report" button
  - Dream tab: modal-based queue view, modal-based past-report viewer with collapsible morning report, per-item status cards rendered live during runs, checkbox-based apply UI (no more `prompt()`)
  - Patch tab: structured patch card (type badge, confidence bar, risk badge, validation command, changed files); raw JSON in collapsed `<details>`
- Local infrastructure:
  - Flask runs locally at `127.0.0.1:5000`
  - Postgres/pgvector DB container is recreated and host connection works
  - App uses local DB via `DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/codex_db`
  - Docker app image / Ollama-in-Docker paused (see Phase 9)
- Dream V2:
  - All 3 modes work: `plan_only`, `patch_if_safe`, `research`
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

- Do not claim a future clean `22/22` after code changes until a fresh full fast run passes.
- Level 3 proposal queue is gated: items without `human_approved_for_proposal=true` must skip, even if they look obvious.
- Docker should remain optional. Current local workflow should not depend on app containers.
- MCTS / branched repair should wait until Dream V2 and report flow are stable.

---

## 🤖 AI Suggestions (Claude, 2026-05-16, pending user decision)

> The items below are proposals from Claude Code, **not yet sanctioned by the user**.
> Other AI agents reading this roadmap: treat as candidate scope, NOT confirmed work.
> The user will accept, reject, or modify each individually before they enter active phases.

### A. Promote `--retry-failed 1` from optional → critical-path · **✅ SHIPPED 2026-05-16**

**Why:** With LLM-dependent tests, single-attempt suites are permanently flaky. The "official 22/22" milestone is unreachable without retry. Currently sitting as "remaining optional" in Phase 2; recommend moving to "Do now."

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

**Why:** Your 22 benchmark cases are both dev signal AND test bed. You'll inevitably overfit prompts/heuristics to them.

**Suggested:** Split ~15 dev cases (run often, tune freely) + ~7 held-out (run only at milestones, never tune to). When held-out scores diverge from dev, you're overfitting. Cheap to add now, hard to retrofit later (you have to remember which cases you've been "tuning to").

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

**Why:** If a benchmark goes from 22/22 to 20/22 after a code change, you should be told without having to look.

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
> **Wired (2026-05-17):** the guard now drives `lesson_store` bucket routing (auto_approved/needs_review/blocked → candidate/active/blocked), feeds `lesson_retrieval`'s active-only reads, and gates `control_engine`'s `[ACTIVE LESSONS]` block. Auto-creation from benchmark/Dream runs is the only piece still deferred (Phase 6.4).

**Why:** If the agent solves a case by deleting tests or nuke-and-rewrite, and that "solution" gets auto-promoted to a lesson card, the agent will look up that lesson next time it sees a similar failure type and reinforce the bad pattern. Lesson storage without quality gating poisons your knowledge base over time. This is a real architectural risk that Claude's original Phase 6 design missed.

**Suggested:** Two-tier promotion before any lesson is consumed by the patch flow:

1. New lesson cards start as `Candidate_Lesson` (visible in Memory tab but NOT retrieval-eligible by the patch pipeline).
2. Promotion to `Active_Knowledge` (retrieval-eligible) requires EITHER:
   - **Auto-criteria:** fewer lines than the buggy version + lower or equal token cost + validation OK + no test/forbidden files touched
   - **Human approval:** user clicks "Promote" in the Memory tab
3. The Phase 6 retrieval call site only reads from `Active_Knowledge`.

This makes Phase 6 a precondition-design problem, not just a storage problem. **Should be a Phase 6 PREREQUISITE** — don't ship lesson auto-creation without the gate, or the knowledge base will self-poison within weeks.

### L. Suggested ordering when user picks next task

> Historical note: A, G, H, Phase 4.5 Levels 1-3, and Phase 6 manual-safe loop have shipped. Current near-term ordering is tracked in **Near-term action list**.

1. ~~Manual Level 3 trial on one reviewed `human_approved_for_proposal=true` item.~~ ✅
2. Prompt-version quantifier panel, paired with Brain Stamp hashes.
3. Patch Safety gate (forbidden-files + path-traversal at apply time).
4. Held-out eval set.
5. Repeated-failure Dream seeding.
6. ~~Phase 6 lessons — § M guard MVP is shipped; still wire `Candidate_Lesson` → `Active_Knowledge` storage, human approval, and retrieval that reads only active knowledge.~~ ✅ (manual-safe loop shipped; Phase 6.4 auto-creation is the remaining piece)

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

> 🤖 **Claude-proposed (2026-05-16) — RESOLVED ✅:** Promoted from optional → shipped. With `--retry-failed`, "official 22/22" is now reachable honestly: passes-with-flake are visible (`flaky=true`), not hidden. Three-AI consensus (Claude/Gemini/GPT) on prioritization. See **AI Suggestions § A**.

---

## Phase 3 — Expand benchmark suite from 10 to 20+

**Status: DONE**

Current suite has 22 cases:

- C++: `cpp_account_interest`, `cpp_boundary_check`
- Go: `go_logging_side_effect`, `go_missing_import_error`, `go_wallet_transfer`, `go_wrong_file_temptation`
- HTML: `html_signup_form_accessibility`
- JavaScript: `js_array_mutation_side_effect`, `js_async_missing_await`, `js_null_user_profile`, `js_temperature_converter`
- Python: `python_discount_validation`, `python_exception_parse_config`, `python_mutable_default`, `python_off_by_one_pagination`, `python_sql_account_transfer`, `python_sql_join_filter`
- Rust: `rust_cart_reservation`, `rust_result_error_handling`
- TypeScript: `ts_import_export_mismatch`, `ts_inventory_restock`, `ts_optional_property_guard`

### Current benchmark status

```text
--check: 22 cases, 0 errors
official clean full fast run achieved: 22/22 passed, flaky: 0, with --retry-failed 1
```

### Next benchmark goal

```text
official full fast run: 22/22 passed (with --retry-failed 1 — flaky-pass counts but is visible)
```

Use:

```bash
python benchmarks/run_benchmarks.py --fast --summary --skip-toolchain-failures --markdown --retry-failed 1
```

A "true 22/22" passing run will look like one of:
- `Passed: 22 · Flaky: 0` → real clean run, no flake
- `Passed: 22 · Flaky: 2` → 22/22 but 2 cases needed a retry (failure-vs-success log diff captured in `retry_results[]` per case)
- `Passed: 20 · Failed: 2 · Flaky: 0` → real regression, no flake to blame

> 🤖 **Claude-proposed (2026-05-16):** Once the 22 cases are stable, split into ~15 dev + ~7 held-out to avoid overfitting. See **AI Suggestions § B**.

---

## Phase 4 — Stabilize Dream V2

**Status: MOSTLY DONE**

Dream is the planning/research layer; benchmark seeding is shipped with dedupe. Execution-quality Slices alpha/beta/gamma are now shipped.

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
- Backend additions: `/health`, `/benchmarks/list`, `/benchmarks/report`, `risk` + `validation_command` in `/test_patch` and `/apply_patch` (and `_plan` variants)
- Tab patterns: workspace tabs + result tabs both have active-state styling; lazy-load panels (health/benchmarks) on first show; ESC-to-close modal
- **Web benchmark execution + Add Case clerk shipped 2026-05-17:** Benchmarks tab now has `Run all`, `Run selected`, stop/status polling, and an `Add case` modal. Add Case can copy a source repo into `benchmarks/cases/<language>/<case>/buggy_repo`, infer default validation command via existing repo/language rules, infer expected/allowed changed files from current patch state or repo `git diff`/staged/untracked evidence, and optionally ask the LLM to classify category/difficulty plus rewrite rough human intent into strict benchmark requirements. Guardrail: generated lessons still do not auto-promote; proposal -> lesson remains evidence-gated/manual-safe.
- **Lesson proposal viewer shipped 2026-05-17:** Memory lesson cards created from `patch_proposal` now expose a read-only `View proposal` button that opens the originating `proposal.md` through a path-guarded Flask route, preserving the rule that lessons should be understandable through their proposal evidence.

### Phase 5 Polish tasks

- [ ] **Render Dream report markdown properly** (currently `<pre>` — works but not pretty). Would need a small markdown lib (~10KB) or simple inline parser.
- [x] **Improve Benchmark tab - execution controls shipped 2026-05-17:** `Run all`, `Run selected`, stop/status polling, and Add Case UI are now available from the web tab.
- [ ] **Improve Benchmark tab - remaining polish:** run language/category batch trigger, show model usage/fallbacks per case, and improve report drill-down density.
- [ ] **Prompt-version quantifier panel** (Settings/Health subsection or its own tab). Was originally framed as a generic "performance/model usage panel."
  > **🤖 Gemini-proposed reframe (2026-05-16):** scope this as a "prompt-version quantifier" instead of a generic stats table. Group by prompt-file hash (paired with the brain version stamp from § G), show columns: `runs · avg model_calls · avg duration · est cost`. Lets you spot regressions like "I changed the system prompt and tokens silently 2×ed." Start with table; add line chart only if patterns aren't obvious from numbers.
- [x] **Patch Safety gate** (forbidden files + path-traversal). Runs at **apply-time**, not memory-time. Sits naturally alongside the existing Patch card from Slice 5 (visual surface for "this patch was blocked because…"). Replaces the current "Forbidden-file check: not yet implemented" placeholder row in the Patch card.
- [x] **Post-patch explanation card (for the human user)** — after a successful patch, render a small card with: (1) what was wrong, (2) why the patch works, (3) concept the user should learn, (4) similar bug pattern to watch for. Pulls from existing `patch_proposal.summary` + lesson record + `validation_output`; no new LLM calls. **🤖 GPT-proposed brainstorm (2026-05-17) "Tutor Mode" + Claude-condensed:** kept the lightweight explanation card piece; full Tutor/Curriculum phase deferred (would pivot the product from patcher → mentor).
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
---

## Phase 6 — Memory, lessons, and compression

**Status: MANUAL-SAFE LOOP SHIPPED 2026-05-17 · auto-creation deferred to 6.4**

> 🤖 **Claude-proposed (2026-05-16):** Anchor "lessons cards" to a specific consumer: *"the agent looks up past lessons before drafting a patch for similar failure type."* Without the lookup-integration in the patch flow, lesson cards become a museum nobody reads. First Phase 6 iteration should include the **retrieval call site**, not just the storage.
>
> **🤖 Gemini-proposed HARD PREREQUISITE (2026-05-16) — see AI Suggestions § M:** Context Poisoning Guard MVP shipped 2026-05-16 as a standalone evaluator (`core/lesson_quality.py`). The two-tier `Candidate_Lesson` → `Active_Knowledge` gate is **now wired** into storage (6.0) and retrieval (6.2/6.3); auto-creation from benchmarks/Dream remains deferred (6.4).

### Goal

Turn benchmark and Dream outputs into useful knowledge the agent actually consults — safely, behind a quality gate, with human approval before anything becomes retrieval-eligible.

### Shipped 2026-05-17 (manual-safe loop)

- **6.0 — Candidate Lesson Store** (`core/lesson_store.py`):
  - bucketed storage under `.agent/<project_tag>/lessons/{candidate,active,blocked}/<id>.json`
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
  - **6.2.1:** scope union — lessons saved without `--repo-path` (global bucket) are visible from any per-repo retrieval call; per-repo lessons stay isolated
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

### Deferred (Phase 6.4 full auto-creation, Phase 6.5+)

- [ ] **6.4 full auto-creation** — wire benchmark/Dream/proposal queues to feed lesson candidates without manual CLI runs. Still must go through `lesson_quality` gate; promotion must remain human-approved by default.
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
- [ ] Convert benchmark reports into lesson cards (auto-flow — deferred to 6.4)
- [ ] Save Dream plans as knowledge entries (auto-flow — deferred to 6.4)
- [ ] "Save this session to memory" button
- [ ] Log compression: validation summary, patch summary, failure category

---

## Phase 7 — Reference study loop

**Status: DEFERRED**

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
- Add lightweight operator artifacts before adding more autonomy:
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

**Status: DEFERRED**

MCP is an external safe API, not the brain.

### Safe tools first

- `get_latest_benchmark_report`
- `run_benchmark_case` with whitelist
- `read_project_map`
- `get_code_dna`
- `get_phantom_limb_report`
- `local_critique`
- `list_dream_reports`

### Avoid first

- arbitrary shell command
- arbitrary file write
- direct patch apply to real repo
- delete/move files
- DB writes

> 🤖 **Claude-proposed (2026-05-16):** Once Phases 4–6 are stable, MCP becomes very high-value because other Claude agents (or any MCP-aware AI tool) can query your benchmarks/dream/health directly instead of relying on the user pasting context. The whitelisted-tools approach in the current plan is correct — keep it.
>
> **Gastown cross-reference:** Gastown-like Mayor/operator coordination becomes more useful once MCP exposes safe workspace APIs. Keep this as tool-registry orchestration inspiration only: external agents may query evidence, work state, and handoff notes through whitelisted tools, but they should not patch/apply/commit without human approval.

---

## Phase 9 — Portable packaging

**Status: PARTIAL / PAUSED**

Local safe mode works. Docker app packaging is paused due to disk/Docker issues.

### Current reality

- Local Flask works
- DB container works
- App image build remains paused (user force-deleted the docker_data.vhdx 2026-05-16)
- Ollama-in-Docker remains paused
- Docker currently used only as optional infrastructure for Postgres/pgvector

### Modes

#### Safe local mode
- DB off, embeddings off, Ollama optional/off, API keys local, no Docker required

#### Full local mode
- Flask local, Postgres/pgvector Docker container, DB enabled, embeddings optional, Ollama installed directly on Windows if needed

#### Docker mode
- Paused until SSD/Docker storage is stable
- app container optional, Ollama container later
- do not run benchmarks automatically in container

### Tasks

- [ ] Finalize `.env.example`
- [x] Keep `.env` ignored (user confirmed `.gitignore` handles this)
- [ ] Keep `.dockerignore` strong: `.git`, `.agent`, `node_modules`, Rust `target`, temp/build outputs, `.env`
- [ ] Split compose later:
  - `docker-compose.yml` = db-only safe infra
  - `docker-compose.full.yml` = app + db + ollama
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
- Keeps the agent humble — counteracts the "22/22 yesterday, ship it" overconfidence.

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

**Status: 🤖 GPT-proposed brainstorm (2026-05-17) + Claude-condensed (2026-05-17), pending user scheduling**

> Hard prerequisite for Phase 11 (anti-lessons experiment), Phase 10 (MCTS greenlight), and any "did this prompt change help?" question. Without it, every "did X help?" call is settled by vibes.

### Goal

Brain Stamp already captures *what version* of the agent ran (`git_sha`, `prompt_hash`, dirty state, etc.). Phase 12 adds the **comparison layer** on top — register paired runs as experiments with explicit hypotheses, dependent variables, and greenlight rules.

> **Frame:** Brain Stamp = "what version ran this benchmark report." Phase 12 = "which two versions am I comparing, on which subset, with what success rule." It does NOT duplicate Brain Stamp metadata; it references it by hash.

### What it adds

- `.agent/experiments/exp_<id>.json` registry. Each entry:
  ```json
  {
    "experiment_id": "exp_anti_lessons_001",
    "hypothesis": "anti-lessons reduce patch size without lowering pass rate",
    "baseline_brain_stamp_hash": "<sha>",
    "variant_brain_stamp_hash": "<sha>",
    "subset": "held_out_v1",
    "dependent_vars": ["pass_rate", "minimality", "needs_escalation_rate", "cost_usd"],
    "greenlight_rule": "minimality >= +15% AND pass_rate >= -5pp",
    "result": { "...filled after both runs..." },
    "notes": "..."
  }
  ```
- CLI wrapper (`scripts/run_experiment.py`) that runs the benchmark twice (baseline / variant), diffs the metrics using existing `benchmarks.report_compare`, and writes the experiment file
- Pre-registered experiment templates for the current open questions:
  - `exp_anti_lessons` — Phase 11 prerequisite
  - `exp_mcts_vs_self_correct` — Phase 10 greenlight
  - `exp_council_vs_mcts` — alternative to Phase 10 (see absorption log below)

### Do not do

- Do not duplicate Brain Stamp metadata; reference by hash only
- Do not run experiments inline with normal benchmark runs; they're separate CLI invocations with explicit variant config
- Do not greenlight any speculative phase (11, 10, council-mode) without registering the experiment first

### Prerequisites

- Brain Stamp ✅ (shipped 2026-05-17)
- AI Suggestion § B (held-out eval set) — strongly recommended for non-trivial experiments
- AI Suggestion § C (patch minimality metric) — required for any experiment whose hypothesis is about patch size/quality

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

## Brainstorm absorption log (2026-05-17)

A larger brainstorm (11 candidate phases) was condensed into the 3 phases above. The rest were folded into existing scope or demoted to sub-tasks. Recorded here so future readers don't re-propose the same eleven.

| Originally proposed | Disposition |
|---|---|
| **PromptOps / Prompt Version Control** | folded into **Phase 5 Polish** (Prompt-version quantifier panel, already scheduled) + **Phase 12** (A/B comparison layer) |
| **Trust Dashboard** | folded into **Phase 5 Polish** — Settings/Health panel evolves into Trust Dashboard via composition of existing signals (latest benchmark, flaky count, dirty tree, prompt hash changed, lesson retrieval enabled, regression alerts). No rewrite. |
| **Skill / Tool Registry** | demoted to **Phase 8 prep** — MCP needs the registry to expose tools safely; everyone else can hardcode for now |
| **Multi-Repo / Workspace Memory** | folded into **Phase 6 as 6.2.3 increment** (priority chain: current repo → language/category → benchmark-derived → reference). Phase 6.2.1 already shipped the scope union foundation. |
| **Permission & Capability System** | start as **docs-only "Capability Map"** (single `docs/capability_map.md` listing every gate with its current default). Programmatic enforcer deferred until MCP / browser-agent / Docker app mode actually make it necessary. |
| **Tutor Mode / Curriculum** | reduced to a single **Phase 5 Polish item**: "Post-patch explanation card." Full curriculum/exercise scope deferred — it would pivot the product from "patcher named mentor" to "actual mentor," which is a different roadmap. |
| **Multi-Agent Council Mode** | reframed as **Phase 10 alternative to MCTS**, decided by head-to-head experiment (Phase 12 `exp_council_vs_mcts`), not built in parallel. Both are "more compute → better patches" bets; pick one based on data. |
| **Gastown / Mayor pattern** | folded into **Phase 7 Reference Study** and **Phase 8 MCP prep**. Keep as operator-workflow inspiration; no new numbered phase. |
| **Artifact Janitor** | merged into **Phase 13** as the retention half (Replay can't exist without retention) |

**Rationale:** roadmaps lose force past ~10 active phases. The original 11 proposals would push the count to 22; most were either already-scoped or scope-creep. Keeping 3 new numbered phases (12 / 13 / 14) preserves directional clarity while not losing the good ideas. Future brainstorms should be subjected to the same condensation pass.

---

## Near-term action list

### Done since last roadmap refresh

- [x] AgentBench 22 cases stable
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
- [x] **Brain version stamp in benchmark reports** shipped 2026-05-17: reports include git SHA, branch, dirty state/summary, capped diff stat, prompt/config hash, and prompt/config file hashes.
- [x] **Phase 4.5 Level 1 background reporter + regression alert** shipped 2026-05-17: `scripts/run_background_reporter.py` runs checks/benchmarks, writes `.agent/reports/background_report_*.md/json`, includes Brain Stamp, compares previous reports, and emits `regression_alert` when needed.
- [x] **Phase 4.5 Level 2 Background Dream Planner** shipped 2026-05-17: `scripts/run_background_dream_planner.py` creates report-only `.agent/reports/background_dream_plan_*.md/json` from the latest meaningful benchmark report, including failed, flaky, and slow-passing cases.
- [x] **Phase 4.5 Level 3 Patch Proposal Queue CLI MVP** shipped 2026-05-17: `scripts/run_patch_proposal_queue.py` processes only `human_approved_for_proposal=true` items, copies benchmark repos to temp, validates with benchmark-metadata commands only, and writes proposal artifacts under `.agent/proposals/` without touching the real repo.
- [x] **Phase 6 manual-safe memory loop** shipped 2026-05-17: bucketed lesson storage (`core/lesson_store.py`), Memory tab promote/block UI + tag chips, `core/lesson_retrieval.py` reading only `active/` with per-repo+global scope union, deterministic keyword scoring (case_name +100 / tag +25 / language+category +10 / query +5) with tokenized free-form queries + stopword list, CONTROL prompt injection (`core/control_engine.py`) gated by `LESSON_RETRIEVAL_ENABLED` and fail-closed on errors, manual `scripts/create_lesson_from_proposal.py` CLI, and `derive_lesson_tags` helper. Auto-creation from benchmarks/Dream still deferred (Phase 6.4).
- [x] **Web proposal/benchmark workflow adjustment** shipped 2026-05-17: lesson cards can open originating proposal.md; Benchmarks tab can run all or selected cases without terminal; Add Case can infer validation command + expected changed files from patch/git evidence and optionally use the LLM as a requirements clerk for category/difficulty/strict prompt generation.

### Do next (refreshed 2026-05-17 after Phase 4.5 Levels 1-3 CLI MVP shipped)

> 🤖 Order is **Claude-proposed**. User picks any in any order.

- [x] **Manual Level 3 trial on one reviewed item** — mark a single plan item `human_approved_for_proposal=true`, run `python scripts/run_patch_proposal_queue.py --max-items 1`, inspect `.agent/proposals/...`, and keep apply approval manual.
- [ ] **Prompt-version quantifier panel** in Settings/Health (Phase 5 Polish; Gemini-reframed performance panel) — pairs naturally with brain-stamp.
- [ ] **Patch Safety gate** (forbidden-files + path-traversal, apply-time) — Phase 5 Polish, GPT-relocated from Phase 6.
- [ ] **Held-out eval set** (AI Suggestions § B) — cheap now, hard to retrofit.
- [ ] **Repeated-failure Dream seeding (deferred § D)** — still valid. Scans last N reports for cases failing >50% of the time.

### Do later

- **Dream execution quality - user-proposed direction (2026-05-16)**, sliced alpha/beta/gamma:
  - [x] **alpha. Time budget UI** - shipped 2026-05-16. Preset dropdown next to Start Overnight Run; clamped to [60, 86400] backend-side.
  - [x] **beta. Skip / Stop button** - shipped 2026-05-16. Graceful stop-between-items; `skipped_user_stop` status; orange stopping UI. Hard LLM-call cancellation deferred to beta.2 (would need cancellation tokens in every client).
  - [x] **gamma. Iterative self-improvement within budget** - shipped 2026-05-16. gamma.1 refines `planned_no_patch` and `research_note_created`; gamma.2 revalidates `ready_to_apply` via temp-clone patch-plan apply + validation + `lesson_quality` grading. UI now surfaces `auto_approved`, `needs_human_review`, or `blocked` lesson badges.
  - [x] **γ3.3. Explain why no `ready_to_apply`** - shipped 2026-05-17. Adds `patch_blockers[]` / `patch_blocker_summary`, detects common blockers (`safe_to_patch_false`, missing validation, uncertain files, vibe/manual/context restrictions, no generated patch), and renders a collapsed `why no patch` UI/report section.
- [x] **Context Poisoning Guard MVP** (AI Suggestions § M — Gemini-proposed PREREQUISITE for Phase 6 lessons). Standalone evaluator shipped 2026-05-16; wired into lesson storage + retrieval + CONTROL prompt 2026-05-17.
- [x] **Phase 6 lesson cards anchored to retrieval call site + behind § M promotion gate** — shipped 2026-05-17 as the manual-safe loop (6.0–6.3 + 6.4a manual CLI). Auto-creation (6.4 full) deferred.
- [ ] **Phase 6.4 full auto-creation** — wire benchmark/Dream/proposal queues to feed lesson candidates without manual CLI runs. Must still gate through `lesson_quality`; human promotion required by default.
- [x] Phase 5 Polish: Benchmark run buttons shipped (`Run all` / `Run selected` / stop/status) plus Add Case clerk UI.
- [ ] Phase 5 Polish: markdown rendering of Dream report + benchmark language/category batch polish.
- [ ] Phase 8: MCP sidecar (after Phases 4–6 stable)
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
Phase 5 Core done. AgentBench --retry-failed shipped and the clean 22/22 fast run exists.
Brain Stamp plus Phase 4.5 Levels 1-3 CLI MVP shipped: reporter, Dream planner, and gated patch proposal queue.
Phase 6 manual-safe memory loop shipped (2026-05-17): bucketed lesson storage, Memory tab promote/block UI,
  active-only retrieval with tags + per-repo/global scope union, CONTROL prompt injection behind
  LESSON_RETRIEVAL_ENABLED, manual proposal→lesson CLI. Auto-creation (Phase 6.4) still deferred.
Next: prompt-version quantifier / Patch Safety gate / held-out eval, then optionally Phase 6.4 auto-creation. Benchmark run buttons + Add Case clerk are now shipped; remaining Benchmark polish is category/language batch + report density.
Do not add MCTS yet — require a 10-case mini-experiment first.
```

---

## Phase 7.1 — Mayor Mode handoff + optional subagent runner (planned 2026-05-20)

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


