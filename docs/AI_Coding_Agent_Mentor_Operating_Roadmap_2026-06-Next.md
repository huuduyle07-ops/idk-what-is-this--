# C.A.T.T.U.S Next Operating Roadmap — Post-Autonomy Command Doctrine

## 1. Executive Summary

The previous C.A.T.T.U.S operating roadmap arc is complete after ROAD.3. The completed work established a machine-readable phase registry, a phase picker with night candidate reporting, and a post-MODEL checkpoint audit. The autonomy experiment is now frozen: the system has tested local autonomy boundaries, recorded the results, and should not chase broader autonomy as the next default move.

The next roadmap should turn the tested boundary into controlled operating doctrine. That means selecting the next work deliberately, branch by branch, with evidence and human authorization before action. C.A.T.T.U.S may recommend, summarize, compare, classify, and prepare reports, but the human operator remains the final authority for direction, approval, execution, merge decisions, and any future unlock.

NEXT.1 is the seed for that decision. It defines candidate branches and decision rules. It does not implement features, add runtime behavior, increase autonomy, or open remote execution.

## 2. Frozen Checkpoint

The completed roadmap arc is frozen at the following checkpoint.

### ROAD: Governance, Registry, Picker, Audit

- ROAD.1 created the machine-readable phase registry.
- ROAD.2 added the phase picker and night candidate report.
- ROAD.3 completed the post-MODEL checkpoint audit.
- The phase registry is valid.
- The phase picker currently has no safe candidates.
- The top recommendation is `null`.

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
- The current phase picker result is intentionally empty because no safe candidate is available under the old map.
- The old roadmap arc is complete and should not be stretched to imply new authorization.

### Benchmark State

- One live benchmark flake was observed.
- An isolated rerun passed 3/3.
- No urgent patch is required.
- The flake still creates a trust question for future benchmark interpretation, which makes benchmark evidence work the strongest next candidate.

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
- EVAL.2 — Single-Case Replay Compare
- EVAL.3 — Flake Classification Report
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

- UX.1 — Operator Workflow Map Refresh
- UX.2 — Evidence Panel Simplification
- UX.3 — Dangerous Action Disclosure Pass
- UX.4 — Daily Debug Session Layout

Branch boundary:

- UX may improve operator comprehension and workflow layout.
- UX must not weaken approvals, hide required evidence, make dangerous actions easier to trigger, or add new autonomous behavior.

### Branch CMD — Commander Mode

Purpose:

- Design big-task orchestration.
- Define a decomposition contract.
- Estimate budget and time.
- Define stop conditions.
- Support tower-defense style planning.
- Avoid autonomous merge or execution.

Example phases:

- CMD.1 — Commander Run Contract
- CMD.2 — Task Decomposition Preview
- CMD.3 — Budget Governor Preview
- CMD.4 — Stop Condition Report

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

## 5. Recommended Priority

Recommended branch order:

1. EVAL
2. UX
3. CMD
4. MODEL
5. REMOTE

EVAL should go first because a live benchmark flake appeared. Even though the isolated rerun passed 3/3 and no urgent patch is required, C.A.T.T.U.S should improve trust in benchmark interpretation before relying on larger operational claims.

UX should go second because operator clarity is required for daily use. If the operator cannot quickly see evidence, approvals, risk, and common workflow state, the system becomes harder to supervise even when the underlying safety contracts are sound.

CMD should go third because Commander Mode needs doctrine before implementation. Big-task orchestration should start as contracts, previews, budgets, and stop conditions, not as live autonomous execution.

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

- Commander Mode / Tower Defense Commander.
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
