# Debug Workflow Map

A.2 defines the canonical stage map for the normal C.A.T.T.U.S debug and repair
path. This is a clarity contract only. It documents ownership, artifacts,
approval points, and boundaries; it does not change CONTROL prompts, patch
generation, patch safety, validation command safety, validation behavior,
benchmark scoring, lesson retrieval, anti-lesson behavior, routes, model/API
calls, Docker/subprocess lifecycle, or automation.

Canonical order:

1. Intake
2. Context
3. Proposal
4. Safety
5. Execution
6. Validation
7. Evidence
8. Learning

## Intake

Intake captures what the human is asking for and the per-run constraints around
that request. It is the place for repo path, query, mode/options, validation
intent, runtime environment, patch style, repo-DNA preference, and per-run
toggles.

Existing modules roughly in this stage:

- `web.runner.run_agent_web`
- `cli.interactive`
- `core.router`
- `core.agent_state`
- `core.goal_brief`
- `core.runtime_environment`

Artifacts produced:

- `AgentState` request fields
- `task_info`
- repo path, query, language, mode, patch style, runtime environment
- optional Goal Brief artifacts under `.agent/goal_briefs/`
- per-run anti-lesson CONTROL request metadata when the operator asks for it

Human/operator approval:

- The human supplies the repo path and query.
- The human chooses run mode/options and per-run toggles.
- Supplying a repo path is not approval to write.

Boundaries:

- Intake must not call models, apply patches, run validation, run benchmarks, or
  promote lessons.
- Per-run toggles must not silently become saved global behavior.
- Intake must not cross from "describe this run" into "execute this run."

## Context

Context assembles repo evidence before any model output is trusted. This is
where CONTROL prompt assembly inputs, Scout snippets, graph evidence, active
lessons, and optional anti-lesson eligibility checks belong.

Existing modules roughly in this stage:

- `core.control_engine`
- `core.feature_context`
- `core.source_snippet_fallback`
- `core.indexer`
- `core.repo_librarian`
- `core.lesson_retrieval`
- `core.anti_lesson_control_injection`
- `graph.builder`
- `graph.weights`

Artifacts produced:

- `control_result`
- related snippets
- Scout likely files and snippets
- graph evidence and weighted hypotheses
- `.agent/debug_last_control_prompt.txt`
- active lessons injected into CONTROL when lesson retrieval is enabled
- optional anti-lesson CONTROL metadata when both keys are enabled

Human/operator approval:

- Lesson retrieval is gated by its existing configuration and remains advisory.
- Anti-lessons use the anti-lessons default-off two-key gate: the server flag
  must be enabled and the operator must opt in for the specific run.
- Context evidence is not approval to generate, apply, validate, or promote.

Boundaries:

- CONTROL prompt content must not be changed by this map.
- Lesson retrieval must remain advisory and lowest priority.
- Anti-lessons must not become active retrieval knowledge by accident.
- Context must not mutate lessons, patch plans, benchmark reports, routes, or
  validation behavior.

## Proposal

Proposal creates untrusted draft output: model draft, answer text, patch
candidate, patch plan, and candidate alternatives. This stage may normalize or
repair structured JSON through existing code, but it does not approve execution.

Existing modules roughly in this stage:

- `core.pipeline`
- `core.prompter`
- `core.json_utils`
- `patching.patch_gates`
- `patching.patch_planner`
- `patching.patch_synthesizer`
- `agents.gemini_client`
- `agents.deepseek_client`
- `agents.ollama_client`

Artifacts produced:

- answer text
- `json_block`
- `patch_candidate`
- `patch_plan`
- candidate alternatives
- reviewer or repair output
- model raw response when replay captures it

Human/operator approval:

- Model output is not approval.
- Confidence scores are not safety approval.
- Human/operator approval is evaluated later by Safety, route, harness, and
  policy gates.

Boundaries:

- Proposal must not directly apply patches.
- Proposal must not bypass patch safety.
- Proposal must not change model/API routing, CONTROL prompt behavior, patch
  generation behavior, or schema-repair behavior in this contract slice.

## Safety

Safety decides whether a proposal is allowed to proceed. It owns patch safety,
path traversal guard, forbidden files, validation command safety, harness mode,
and server/operator gates.

Existing modules roughly in this stage:

- `core.patch_safety`
- `core.security`
- `core.validation_command`
- `core.harness_modes`
- `core.harness_controls`
- `policy.decision_helper`
- `web.routes.patch_routes`

Artifacts produced:

- patch safety result
- blocked paths
- safety reasons
- validation command safety reason when blocked
- harness mode decision
- route/policy apply decision

Human/operator approval:

- Dangerous writes require explicit human/operator approval.
- Harness controls and harness mode may deny generation or apply.
- A validation command is still screened even if it came from a default,
  profile, or operator-provided path.

Boundaries:

- Do not bypass `evaluate_patch_safety`.
- Do not bypass `validation_command_safety_issue`.
- Do not weaken path traversal, forbidden-file, harness, server, or operator
  gates.
- Safety must not be treated as a model prompt concern; it is a gate.

## Execution

Execution applies an allowed patch through the existing executor boundary. This
stage includes patch apply, executor, lifecycle runner, and temp clone or
sandbox boundary.

Existing modules roughly in this stage:

- `core.executor`
- `patching.patch_engine`
- `patching.patch_plan_executor`
- `core.run_lifecycle`
- `core.sandbox_runner`
- `core.worker_runs`
- `core.sleeping_consultant`
- `benchmarks.run_benchmarks`

Artifacts produced:

- apply result
- diffs
- rollback status
- patched files
- generated artifacts
- temp clone or sandbox output

Human/operator approval:

- Real-repo apply uses the existing route/policy/operator gate.
- Dream, worker runs, imported proposal validation, and benchmarks use temp
  clones or sandbox boundaries unless a separate apply path is explicitly used.
- Benchmark execution is evaluation, not approval to mutate the source repo.

Boundaries:

- Execution must not be reached from the metadata helper.
- Execution must not cross temp clone or sandbox boundaries into the real repo.
- This contract slice must not change executor, patch engine, lifecycle,
  Docker/subprocess lifecycle, sandbox, worker-run, or benchmark behavior.

## Validation

Validation records whether the executed change passed the existing validation
path. It owns validation output, self-correct attempts, failure taxonomy, and
environment/toolchain/security-tool classification.

Existing modules roughly in this stage:

- `core.validator`
- `core.validation_command`
- `core.self_correct_loop`
- `core.failure_taxonomy`
- `patching.patch_plan_executor`
- `benchmarks.run_benchmarks`

Artifacts produced:

- validation output
- validation pass/fail fields
- self-correct attempts
- failure taxonomy classification
- environment/toolchain/security-tool failure fields

Human/operator approval:

- Passing validation is evidence, not automatic promotion or unrelated apply
  approval.
- Unsafe validation commands are blocked before execution.
- Environment/toolchain failures should stop patch repair instead of asking the
  model to rewrite a patch for a broken local setup.

Boundaries:

- Do not change validation behavior.
- Do not change validation command safety.
- Do not run validation from the metadata helper.
- Failure taxonomy is read-only display/reporting metadata and must not affect
  benchmark scoring.

## Evidence

Evidence stores and displays what happened so a human can inspect it without
re-running the workflow. Replay, benchmark report output, diff, raw JSON,
presentation evidence pack, and run details belong here.

Existing modules roughly in this stage:

- `core.replay_recorder`
- `core.run_artifacts`
- `core.replay_compare`
- `core.review_pack_generator`
- `core.benchmarks_view`
- `benchmarks.run_benchmarks`
- `scripts.build_presentation_evidence_pack`
- `web.routes.replay_routes`
- `web.app`

Artifacts produced:

- replay bundle under `.agent/replays/`
- benchmark report JSON and Markdown under `.agent/benchmarks/`
- diff
- raw JSON
- presentation evidence pack
- run details

Human/operator approval:

- Evidence is review material, not an apply decision.
- Replay compare is read-only unless a separate explicit cleanup/apply route is
  used.
- Benchmark reports may seed follow-up queues only through existing explicit
  flows.

Boundaries:

- Evidence views must not execute patches, validation, benchmarks, models, or
  lesson mutation.
- A benchmark report must not change benchmark scoring after the fact.
- Raw JSON and presentation evidence are not operator approval.

## Learning

Learning turns reviewed evidence into optional memory through the existing
manual lesson lifecycle. Lesson candidates, anti-lessons, lesson promotion and
blocking, dogfood reports, and default-off memory behavior belong here.

Existing modules roughly in this stage:

- `core.lesson_auto_candidates`
- `core.lesson_store`
- `core.lesson_retrieval`
- `core.lesson_quality`
- `core.anti_lessons`
- `core.anti_lesson_retrieval_shadow`
- `core.anti_lesson_control_injection`
- `core.anti_lesson_dogfood`
- `scripts.create_lesson_from_proposal`
- `scripts.seed_lessons_from_benchmark`

Artifacts produced:

- lesson candidates
- active lessons
- blocked lessons
- anti-lessons
- dogfood reports
- lesson promotion/blocking records

Human/operator approval:

- Candidate lessons require human promotion before they become active retrieval
  knowledge.
- Blocking is a human/operator action.
- Anti-lesson CONTROL warnings require the default-off server flag plus the
  per-run checkbox.

Boundaries:

- Do not promote, block, merge, create, or mutate lessons from this metadata
  helper.
- Do not change lesson retrieval or anti-lesson behavior in this slice.
- Do not make anti-lessons default-on.
- Learning artifacts do not outrank user intent, repo state, validation, or
  patch safety.

## Cross-Cutting Surfaces

Replay belongs mainly to Evidence. The lifecycle runner may create replay
artifacts during Execution and Validation, but the replay viewer and compare
surfaces are review tools.

Benchmarks exercise the workflow through temp repos and produce benchmark report
artifacts. Benchmark report fields may include failure taxonomy display fields,
patch minimality, validation output, and toolchain/security classification, but
this map does not change benchmark scoring.

Lessons are advisory memory. Lesson retrieval feeds Context only when enabled,
and promoted active lessons remain lowest-priority hints. Lesson candidates and
promotion/blocking live in Learning.

Anti-lessons are counter-knowledge. Reports and shadow retrieval are read-only.
CONTROL warnings require the anti-lessons default-off two-key gate: server flag
plus per-run checkbox. This map does not make anti-lessons active retrieval
knowledge.

Harness controls belong to Safety as operator-visible gates and configuration
overrides. They describe and control existing flags; this map does not add new
harness controls or new automation behavior.

Failure taxonomy belongs to Validation and Evidence. It classifies already
captured failure evidence and may appear in reports, but it must remain
read-only and must not alter patching, validation, benchmark scoring, or lesson
promotion.

## Boundaries That Must Not Be Crossed

- Do not change CONTROL prompt assembly or prompt text.
- Do not change patch generation, schema repair, patch candidate, or patch plan
  behavior.
- Do not change patch safety, path traversal guard, forbidden-file policy,
  validation command safety, harness mode, or operator gates.
- Do not change executor, patch engine, lifecycle runner, sandbox, Docker, or
  subprocess behavior.
- Do not change validation behavior or validation output classification.
- Do not change benchmark scoring, benchmark execution semantics, or report
  pass/fail rules.
- Do not change lesson retrieval, lesson promotion/blocking, anti-lesson
  storage, anti-lesson CONTROL gating, or default-off memory behavior.
- Do not add new top-level buttons, routes, automations, model calls, API calls,
  or background workers.
- Do not wire `core.debug_workflow` into runtime behavior; it is a safe-to-import
  metadata contract only.
