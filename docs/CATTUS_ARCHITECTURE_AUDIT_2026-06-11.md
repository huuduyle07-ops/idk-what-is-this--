# C.A.T.T.U.S Architecture Audit — 2026-06-11

> **Method note:** this audit was produced by a multi-agent workflow — parallel read-only subagents over 9 subsystem areas, with cut/merge candidates adversarially verified against the code and the README Permission Matrix. Five areas (Proposal→Lesson, Lesson Seeds, Goal Brief, Dream, Core Pipeline) completed with formal verification verdicts; four areas (Project Evolution, External Queue, redundancy sweep, prior-audit cross-check) were completed inline after the workflow was interrupted by session breaks. Where a claim rests on a single pass, it is marked as such.
>
> Audit was read-only: no source, test, config, or `.agent/` files were modified.

## Project Purpose

C.A.T.T.U.S is a **local-first AI coding agent and mentor** operated by one person. It reads a repository, builds a weighted program graph of it, retrieves the code that matters for a question, asks models (Gemini drafting, DeepSeek/Ollama reviewing) to propose a fix, and then puts that fix through an unusually deep safety funnel: grounding gates that reject patches quoting code that doesn't exist, a patch-safety gate that blocks forbidden paths, validation in temporary repo clones, rollback on failure, and forensic replay bundles. What survives can become "lessons" — advisory memory that only reaches future prompts after an explicit human Promote click.

The defining design idea is the **Operating Modes / Permission Matrix** (`README.md:659-726`): every workflow (Chat, Patch, Dream, Lessons, Project Evolution, Mayor Mode, MCP, External Queue) has an explicit row stating what it may do, and "power leakage" between modes is forbidden. The human is the only authority; everything else produces evidence.

## Strengths

1. **The safety architecture is real, not aspirational.** Temp-clone validation for web patch tests (`web/routes/patch_routes.py:178-213`), a patch-plan chokepoint that runs `evaluate_patch_safety` before every plan apply (`core/run_lifecycle.py:114`, pinned by `tests/test_patch_safety_chokepoint.py`), candidate-only lesson writes with human Promote, and hardcoded External Queue gates (`auto_dream_allowed: false` is not settable from caller input — `docs/superpowers/specs/2026-06-10-external-queue-import-design.md`).
2. **Anti-hallucination grounding.** `reject_ungrounded_patch` and quote-grounding gates (`patching/patch_gates.py:1016, :1198`) run on both CLI and web paths; the graph penalty layer (`graph/penalty.py`, `graph/weights.py`) biases attention toward files that failed before.
3. **Forensics and reversibility.** Every patch-plan execution is wrapped in a replay bundle (brain stamp, events.jsonl, apply result, validation output — `core/run_lifecycle.py:36-172`); the Executor restores backups on validation failure and the plan executor unwinds ops in reverse (`patching/patch_plan_executor.py:27-59`).
4. **Test discipline that actually closed prior audit findings.** 2,700 tests collect cleanly in ~20s. The Phase 13 audit's top backlog items were genuinely implemented since: the patch-plan safety chokepoint, `tests/test_router_gating.py`, `tests/test_executor_single_file_path.py`, `tests/test_validation_command_safety.py`, the lesson-scope docstring fix, and the `graph/builder.py` double-edge fix are all verifiably in place.
5. **Institutional self-awareness.** The project audits itself rigorously (`docs/phase13_ultracode_audit.md` is excellent, including corrections of its own over-claims), keeps a truth-audited roadmap, and runs a 54-case multi-language benchmark suite with a held-out adversarial split.

## Weaknesses / Complexity Traps

1. **Phase accretion without retirement — the dominant trap.** Each phase adds a new layer that never retires the previous one. Lesson candidates can be created through **seven distinct code paths** across three phase generations (6.4a/6.4c/6.4e), with two incompatible source labels (`patch_proposal` vs `proposal_artifact`) and two dedup schemes that cannot see each other — running both on the same proposal silently creates duplicate lessons (cross-verified by two independent readers; evidence: `scripts/create_lesson_from_proposal.py:270-280` vs `scripts/seed_lessons_from_proposals.py:340-377`).
2. **Safety depends on the entry point, not an invariant.** The single-file `patch_candidate` auto-apply path (`pipeline.maybe_run_auto_patch` → `self_correct_loop` → `Executor` → `apply_patch_from_json`) still bypasses `evaluate_patch_safety` entirely — its only path guard is the traversal check at `patching/patch_engine.py:274`. The README matrix row (`README.md:678`) claims the gate "auto-runs" for the whole Debug/Patch Flow; that's true for patch plans, not for this branch. Phase 13 flagged this (R1); it was half-fixed.
3. **A confirmed power-leakage hole: `LESSON_AUTO_ACTIVE`.** Every lesson-creation path force-disables this flag around its write *except* the 6.4a path (`create_lesson_from_proposal`, used by the queue's `--create-lesson-candidates` and web `/proposals/promote`). With `LESSON_AUTO_ACTIVE=1` in the env, a batch queue run would write `auto_approved` lessons **straight into `active/` with no Promote click** — violating the matrix row at `README.md:680` and the module's own "never auto-promotes" docstring. An adversarial verifier confirmed this end-to-end, including that no test pins the flag-on behavior for this path.
4. **God modules.** `web/app.py` is 3,563 lines with 79 inline routes (only 7 blueprints extracted — and `docs/TECHNICAL_DEBT.md` still lists just one); `core/control_engine.py` is 1,751 lines mixing graph DFS, hypothesis inference, a ~370-line prompt builder, and symbol extraction; `core/sleeping_consultant.py` is 1,530 lines mixing threading, case-idea research, item runners, and refinement; the post-processing gate battery is duplicated verbatim between `main.py:93-122` and `web/runner.py:476-515` including a copied indentation quirk, and the CLI copy has no harness gating at all.
5. **Report-layer sprawl.** Of the 7 anti-lesson modules, only `anti_lesson_control_injection` is in the live CONTROL path (gated off by default per the roadmap); the other 5 serve report routes or one-shot scripts. Of the 6 memory-temperature modules, 2 are live-but-default-off, 4 are dogfood/experiment scaffolding. Add `core/experiments.py` + 6 experiment scripts, the 40KB presentation evidence pack, and docs drift (README claims 31 benchmark cases, 54 exist; `.agent/PROJECT_MAP.md` indexes its own `.tmp/pytest` junk). None of it is dangerous; all of it taxes comprehension.

## Possible Cuts or Merges

Verified candidates, with adversarial-verification status and Permission Matrix safety:

| Component | Action | Verdict | Matrix-safe? |
|---|---|---|---|
| Dual proposal→lesson stacks (`create_lesson_from_proposal` vs `seed_lessons_from_proposals`/`lesson_auto_candidates`) | Merge to one creation function with unified source label + `source_key` dedup | Strong evidence, 2 independent readers | ✅ Yes — entry-layer only; gates live in `lesson_store`/`lesson_quality` |
| `scripts/create_lesson_candidate.py` CLI | Merge forward into the seeder (add `--dream-item-dir` there) | **Confirmed** by verifier (forward direction only; one test to port) | ✅ Yes |
| Web route `/lessons/create-candidate-from-proposal` (`web/app.py:3044`) | Cut — no UI caller; duplicates `/proposals/promote` via the parallel stack | Single-pass finding; verify no external client before cutting | ✅ Yes |
| Dual dream web endpoints (`/dream/create-lesson-candidate` vs `/lessons/create-candidate-from-dream`) | **KEEP — merge refuted.** The split is intentional, spec'd design; merging would no-op the button for all non-`ready_to_apply` items and break pinned tests. Fix the missing dedup in place instead | **Refuted** by verifier | n/a |
| `LESSON_AUTO_ACTIVE` gap in the 6.4a path | Freeze/fix: add the force-off guard (or a pinning test) | **Confirmed** by verifier | ✅ Closing it *restores* matrix compliance |
| `core/mode_router.py` → merge into `core/goal_brief_autocomplete.py`; `core/handoff_composer.py` → into `core/handoff_notes.py`; review-pack prompt builder → unify with `build_final_prompt` | Merge (~90% duplicated keyword tables, 3 inconsistent `DEFAULT_FORBIDDEN_FILES` copies — one silently drops `tests`) | Single-pass, concrete line evidence | ✅ Yes — all draft-only modules |
| Dead Interviewer model hook in `core/goal_brief.py` | Cut (or wire a real model) — no production caller ever passes an interviewer | Single-pass, grep-verified | ✅ Yes — makes mode *more* restrictive than its matrix row |
| Broken F.1→Goal Brief bridge (`web/templates/index.html:5786`) | Fix or cut — `suggested_mode` values never pass the `problem_type` whitelist; the button silently fails | Single-pass | ✅ Yes |
| Dead `write_report_markdown` (`core/dream_artifacts.py:983-1071`) + stale `morning_report.txt` log line | Cut — shadowed by an alias; a test asserts the file is never written | Single-pass, test-backed | ✅ Yes |
| `scripts/seed_lessons_from_benchmark.py` | Freeze — used once ever (2026-05-25), no programmatic caller; but it's the only benchmark→lesson path | Reader + import-map grep agree | ✅ Yes (freeze, not cut) |
| `route_request` (`core/router.py:362`), `core/reverse_dream_planner.py`, `core/repo_inventory.py` | Freeze the first two (pinned by tests / one read-only route); `repo_inventory.py` is a Phase-13-confirmed orphan still undeleted — cut | P13 + re-check | ✅ Yes |
| Report-only families (anti-lesson reports/dogfood/shadow ×5, memory-temperature dogfood/experiment ×4, `experiments.py` tooling) | Freeze — inert, tested, but a growth moratorium is warranted | Import map verified inline | ✅ Yes (freeze only; deleting breaks tests/scripts) |
| Gate battery duplicated in `main.py`/`web/runner.py`; temp-clone ignore-list duplicated twice in `patch_routes.py` | Merge into shared helpers | Reader, concrete lines | ⚠️ Safety-relevant code — do it behind the existing characterization tests |

## Proposal → Lesson Evaluation

**The storage/quality/retrieval core is clean; the entry layer is over-built.**

- **The lifecycle is sound and matrix-compliant**: proposal artifacts (validated in temp clones) → human creates a candidate → `lesson_quality` routes it to `candidate/` or `blocked/` → human Promote moves it to `active/` → retrieval requires `LESSON_RETRIEVAL_ENABLED=true` on top. Promotion is genuinely human-only on every default path; `lesson_retrieval` re-checks status defensively and excludes anti-lessons fail-closed.
- **Lesson seed vs lesson proposal**: a "seed" is **not a distinct artifact type** — seeding is just batch creation of ordinary lesson candidates from existing evidence (benchmark reports or proposal dirs), with a summary report under `.agent/reports/`. Both seeders converge into the same `save_candidate_lesson` store with `LESSON_AUTO_ACTIVE` forced off. The two seed scripts share **346 byte-identical lines (~48% of one file)** of copy-pasted scaffolding. Real-world usage is lopsided: the benchmark seeder ran once (17 lessons, 2026-05-25); the proposal seeder and the single-item proposal CLI have persisted **zero** lessons in `.agent/lessons/` (138 of the 156 stored lessons came from Dream).
- **Dream producing lessons directly: it doesn't, and that's verified.** `core/sleeping_consultant.py` never writes into `.agent/lessons/` in any bucket. The only "lessons"-named output is a draft `LESSONS_LEARNED.md` inside the dream report dir, explicitly labeled "These are not seeded lessons." The `auto_approved`/`needs_human_review`/`blocked` badges from refinement-phase grading are annotations stored in item metadata and rendered in the UI — they trigger nothing. The badge only acquires routing power inside `lesson_store`, and every dream-sourced path forces `LESSON_AUTO_ACTIVE` off.
- **The two real problems**: (1) the seven-path entry fan-out with mutually invisible dedup (detailed above); (2) the `LESSON_AUTO_ACTIVE` hole in the one path that doesn't guard it. Operator cost is acceptable — 2 clicks minimum from dream item to active lesson — but note there is **no CLI for Promote** (web button or tool-registry only).

## Goal Brief Evaluation

**The guardrail is real; the construction around it is over-built for one operator.**

The "collector, not solver" guarantee holds at the import level: all five modules import only stdlib (+`json_utils`); patch/run/promote concepts exist only as blocked-phrase strings in the command deny-list. Path sanitization, brief-ref containment, and command filtering are all present and tested.

But: the live system is **100% deterministic** — no production caller ever wires the model Interviewer, so the README matrix's "Can call model? Yes (interviewer only)" overstates current behavior. Track F then adds four more deterministic text-mappers (~918 LOC) whose job is shuttling text between five draft formats with a two-state state machine: F.1 and F.3 are ~90% duplicate keyword classifiers; F.2 duplicates `handoff_notes` constants and is re-validated by it anyway; F.4 rebuilds the prompt `build_final_prompt` already produces, with a third inconsistent forbidden-files list. The F.1→Goal Brief handoff button is provably broken (mode values never pass the `problem_type` whitelist). Roughly **1,556 core LOC + 1,120 test LOC + 6 routes** could be about half that with zero capability loss. The roadmap itself already says "Future freeze: optional polish only" — the merges above are consistent with it.

## Project Evolution Evaluation

*(Inline verification: stage scripts, hash-chain greps, model-call greps, web-wiring greps. No adversarial verifier ran on this section — confidence is medium-high on structure, lower on internal duplication percentages.)*

The B.1→B.10 chain is **ten operator-driven stages** (map v2 → node summaries → migration plan → approval → patch draft → patch candidates → patch text draft → sandbox validation → executable patch draft → review gate), ~200KB across 8 core modules plus 8 CLI scripts, with only the B.4a approval panel wired into the web UI. Two things it gets right, verified: **no model is ever called anywhere in the chain** (the only "gemini" hits are keyword strings in classifiers), and each downstream stage re-verifies the full upstream chain by `source_plan_hash` + approval ID (`core/project_evolution_executable_patch_draft.py:361-408`) — a real tamper-evidence mechanism.

The problem: **five post-approval stages (B.5–B.9) each produce progressively more detailed *descriptions* of a patch that still doesn't exist** — the B.9 executable draft has `old_text`/`new_text` as `null` placeholders and `apply_allowed: false` everywhere. Each stage re-implements the same plan-loading/chain-verification plumbing (visible as repeated `source_plan_hash=` blocks across `core/project_evolution_patch_candidates.py`, text draft, sandbox validation, executable draft, review gate). The stages that carry matrix weight are **B.4 approval, B.8 sandbox validation, and B.10 review gate** — those must survive untouched. B.5/B.6/B.7 are intermediate elaborations that could collapse into a single "draft package" stage (one artifact with files + candidate areas + narrative) without weakening any gate, since none of them holds a unique approval or lock. Mark that consolidation **safe**: it removes no gate, and the hash chain shortens rather than weakens.

## External Queue Evaluation

**Right-sized to slightly under-built, and the safest subsystem in the project.**

- **B.12 import** (`core/external_queue_import.py`): normalizes source/kind, redacts secrets before anything touches disk, bounds result/metadata size, classifies risk by text analysis only, hardcodes `import_status: pending_review` / `auto_dream_allowed: false` / `human_review_required: true` (not settable from input), and verifies output-path containment inside `.agent/external_queue/`.
- **B.14 review** (`core/external_queue_review.py`): pure keyword heuristic, no model call, advisory-only with `action_performed: False` hardcoded; reject rules fire first (destructive keywords, bypass-safety phrases, detected secrets); writes `external_queue_review.json/.md` next to the item with strict schema validation of the input.
- **Reality vs matrix**: there is **no webhook endpoint** — `git grep external_queue -- web/` returns nothing. The matrix row says "Typical input: Webhook payload," but today the only entry is the manual CLI. Likewise, B.14's recommended conversions (`create_dream_candidate_manually` etc.) have **no implemented converter** — the operator does each by hand. The forbidden transitions hold trivially because nothing is wired to violate them.
- Verdict: keep as-is. If B.15 is the webhook receiver (unsure — see below), the hardcoded-gate pattern here is the right template for it.

## Recommended 3-Phase Roadmap

**Note on B.13/B.15: neither could be found anywhere in the repo** — grep finds only B.12 (`docs/superpowers/specs/2026-06-10-external-queue-import-design.md`) and B.14 (`tests/test_external_queue_review.py`); the roadmap doc stops at B.10. "After B.14/B.15" is treated here as "after the External Queue track lands." If B.15 has unwritten scope, slot it before Phase 1.

**Phase 1 — Safety closure (small, do first, ~1 session each):**
1. Close the single-file bypass: enforce `evaluate_patch_safety` at the `Executor.run`/`apply_patch_from_json` chokepoint, mirroring what `core/run_lifecycle.py:114` already does for plans. This finishes Phase 13's #1 item.
2. Close the `LESSON_AUTO_ACTIVE` hole: add the force-off guard to `create_lesson_from_proposal` (or a test pinning the exception if it's intentional).
3. Extract the duplicated gate battery from `main.py`/`web/runner.py` into one shared function (behind the existing characterization tests), and decide whether the CLI should get harness gating.
4. Doc truth pass: README benchmark count (54, not 31), the Debug/Patch matrix row wording, `docs/TECHNICAL_DEBT.md` blueprint list, and exclude `.tmp` from the project-map indexer.

**Phase 2 — Consolidation (the merges, all verified matrix-safe):**
1. Lesson entry layer: one creation function with unified source label + `source_key` dedup; merge `create_lesson_candidate.py` forward into the seeder; cut the caller-less `/lessons/create-candidate-from-proposal` route; extract the seeders' 346 shared lines. **Do not** merge the two dream endpoints (refuted) — just add dedup to the simple one.
2. Track F: `mode_router` → `goal_brief_autocomplete`; `handoff_composer` → `handoff_notes`; one prompt builder; one forbidden-files constant; fix or remove the broken F.1 bridge; cut the dead Interviewer hook.
3. Dream hygiene: delete dead `write_report_markdown` + stale log line; unify the mode-alias tables; optionally extract case-idea research from `sleeping_consultant.py` (~300 lines of pure code motion).
4. Continue blueprint extraction of `web/app.py` (dream and lessons route groups first — the pattern already exists and works).

**Phase 3 — Freeze and refocus (policy, not code):**
1. Declare a written freeze list: anti-lesson report/dogfood family, memory-temperature dogfood/experiment family, `experiments.py` tooling, `reverse_dream_planner`, `seed_lessons_from_benchmark`, Track F features, and Evolution stages B.5–B.7 pending the consolidation decision. Freeze means: no new features, no new siblings, tests stay.
2. Adopt a "retire when you re-solve" rule — the inverse of the power-leakage rule: a new phase that re-solves an existing problem must retire or delegate to the old path in the same phase.
3. Redirect capacity to one of the two things the system is actually weakest at per its own roadmap: Track C (external real-world benchmark cases) or designing the real Evolution apply step under the B.10 Review Gate — which is where the ten-stage chain finally pays for itself.

## Risks if We Cut Too Much

- **Never touch the enforcement core**: `patch_safety`, `lesson_store`/`lesson_quality` routing, the Promote step, temp-clone isolation, the hash-chain verification, and the B.4/B.8/B.10 evolution gates. Every recommendation above is entry-layer or report-layer.
- **The dual dream endpoints look redundant and aren't** — the verifier proved merging them breaks lesson creation for every non-`ready_to_apply` item and violates a written spec (`docs/superpowers/specs/2026-06-03-dream-report-lesson-ux-design.md`). This is the cautionary example: in this codebase, apparent duplication is sometimes deliberate mode separation.
- **"Dead" code is often pinned**: `route_request` and the never-produced dream statuses are held by characterization tests; cutting them means test surgery for zero behavior gain — freeze instead.
- **Report-only modules have consumers**: the dogfood/experiment families are imported by scripts and tests; deletion breaks the suite. Freeze costs nothing; deletion costs a cleanup project.
- **`seed_lessons_from_benchmark` is the only benchmark→lesson path** and the only non-route caller of `evaluate_patch_safety` — cut it and you lose a capability, not just code.
- **Evolution stage removal must respect the hash chain**: `_verify_chain` in B.9 checks B.4/B.5/B.6/B.7 records by hash; collapsing stages requires updating that verification in the same change or every downstream artifact fails validation.

## Final Verdict

C.A.T.T.U.S is a genuinely well-engineered safety-first agent wrapped in about one-and-a-half systems' worth of accumulated scaffolding. The things that matter — grounding, gating, temp-clone isolation, human-only promotion, replay — are real, tested, and in two verified cases *better* than the previous audit found them (the chokepoint and router gaps were actually fixed). The cost center is not danger but **accretion**: seven ways to make a lesson, five modules to draft a prompt, five stages to describe a patch that can't be applied, and a report layer growing faster than the core it reports on. The two items that deserve immediate attention are small and specific: the single-file patch path that skips the safety gate, and the `LESSON_AUTO_ACTIVE` hole — both are one-guard fixes that restore the README's promises. After that, the consolidation list above removes roughly 15–20% of `core/` and `scripts/` surface area without deleting a single capability or weakening any row of the Permission Matrix — which is exactly the standard the project sets for itself.
