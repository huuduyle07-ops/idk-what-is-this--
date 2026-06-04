# Phase 11.8 - Anti-Lesson CONTROL Dogfood Evaluation Report

_Checkpoint design - 2026-06-04_

## Motivation

Phase 11.7c introduced the first behavior-changing anti-lesson path: an
experimental CONTROL block can be injected only when both keys are enabled:

1. `ANTI_LESSONS_CONTROL_ENABLED=true`
2. `anti_lesson_control_requested=true` for that specific run

Phase 11.8 evaluates that existing two-key path with evidence from already
written benchmark reports. It does not expand the path, enable it by default,
or recommend default-on behavior. The strongest positive conclusion is only:
safe to keep the default-off, explicitly requested experiment path.

## Scope

This slice adds:

- `core/anti_lesson_dogfood.py`
- `scripts/create_anti_lesson_dogfood_report.py`
- `tests/test_anti_lesson_dogfood.py`
- this checkpoint design doc
- a compact roadmap note after implementation

This slice does not add a web route. Web display can be reconsidered during a
later UI design cleanup.

## Hard Guardrails

The report is evidence-only. It does not:

- enable anti-lessons by default;
- change, widen, or persist the Phase 11.7c two-key injection gate;
- modify CONTROL prompts, prompt builders, active retrieval, benchmark scoring,
  patch generation, validation, or model selection;
- run benchmarks, Dream, the mutation oracle, Docker, subprocesses, or network;
- call models or APIs;
- create, promote, demote, block, archive, merge, or mutate lessons;
- generate or apply patches;
- mutate source benchmark reports.

The implementation must not change `core/control_engine.py`,
`core/prompter.py`, or `core/lesson_retrieval.py`.

The report guardrail note is:

> This report is evidence-only. It does not enable anti-lessons, modify CONTROL
> prompts, run benchmarks, create lessons, promote lessons, or apply patches.

## Core Report Builder

`build_anti_lesson_dogfood_report(baseline_report, experiment_report, *,
generated_at=None)` is pure. It accepts already-loaded benchmark report dicts
and returns a deterministic report dict. It never reads the filesystem, writes
files, runs commands, calls models, imports the benchmark runner, or mutates its
inputs.

The report includes:

- title and `generated_at`
- baseline report id/path when available
- experiment report id/path when available
- total cases
- passed, failed, flaky comparison
- pass-rate delta
- changed-files comparison when available
- patched-files comparison when available
- unexpected-mutations comparison when available
- tokens, cost, fallback, model-call comparison when available
- duration comparison when available
- per-case comparison rows
- decision
- reasons
- guardrail note

`format_anti_lesson_dogfood_markdown(report)` is also pure. It renders the same
information as Markdown, including the guardrail note and the decision wording.

## Case Matching

Cases are matched by benchmark case name. The builder accepts the current
`results[]` shape from `benchmarks/run_benchmarks.py` and degrades gracefully if a
future or older report has missing optional fields.

Top-level case comparability is measured as:

```text
shared_cases / max(total_baseline, total_experiment)
```

If that ratio is below `0.80`, the top-level decision is
`inconclusive_missing_matching_cases`. The report may still include partial
per-case comparison rows for the shared cases, but the decision must not present
the run pair as confidently comparable.

## Per-Case Rows

Each shared case row contains:

- case name
- baseline status
- experiment status
- outcome: `improved`, `regressed`, `unchanged`, or `inconclusive`
- baseline changed files
- experiment changed files
- token/cost delta when available

Outcome rules:

- failed or flaky baseline to passing experiment -> `improved`
- passing baseline to failed or flaky experiment -> `regressed`
- same status class -> `unchanged`
- missing or unknown status -> `inconclusive`

Status classification treats `success=true` as passing, `flaky=true` as
flaky, explicit skipped/missing status as inconclusive, and all other non-passing
runnable cases as failed.

## Decision Policy

Allowed decisions:

- `greenlight_default_off_experiment_path`
- `needs_review_regression`
- `inconclusive_missing_matching_cases`
- `reject_correctness_regression`

Decision order:

1. If shared cases divided by the larger suite total is below `0.80`, choose
   `inconclusive_missing_matching_cases`.
2. If experiment pass rate drops by at least 5 percentage points, choose
   `reject_correctness_regression`.
3. If any previously passing held-out or hard case fails, choose
   `needs_review_regression`; escalate to `reject_correctness_regression` when
   combined with the 5-point pass-rate drop or multiple severe held-out/hard
   regressions.
4. If pass rate is unchanged but token, cost, fallback, model-call, or duration
   pressure rises significantly, choose `needs_review_regression`.
5. If pass rate is unchanged and usage/duration are stable, choose
   `greenlight_default_off_experiment_path`.

`greenlight_default_off_experiment_path` means only:

- safe to keep the default-off, explicitly requested experiment path;
- not safe to make anti-lesson CONTROL injection default-on;
- not a recommendation to change normal CONTROL, retrieval, benchmark, lesson,
   Dream, mutation-oracle, or patch behavior.

Held-out and hard cases are identified from existing report fields when present:
`suite_id` or suite labels containing `held_out`, or per-case `difficulty="hard"`.
If those fields are missing, the held-out/hard rule is skipped and the normal
pass-rate/per-case regression rules still apply.

Usage pressure is "significant" when the experiment increases any comparable
usage metric by at least 20% from a non-zero baseline. For discrete counts
(`fallback_count`, `total_fallbacks`, `model_calls`, `unknown_cost_calls`), the
increase must also be at least 1. Missing baseline or experiment usage values are
recorded as unknown and do not trigger this rule by themselves.

## Comparison Metrics

Top-level comparison uses existing fields where available:

- `total`, `passed`, `failed`, `flaky`
- `duration_sec`, `avg_duration_sec`
- `total_tokens`, `input_tokens`, `output_tokens`
- `total_estimated_cost_usd`, `unknown_cost_calls`
- `model_calls`, `total_fallbacks`, `fallback_count`

Per-case comparison uses existing result fields where available:

- `name`
- `success`, `flaky`, `skipped`
- `changed_files`
- `patched_files`
- `unexpected_mutations`
- `duration_sec`
- `input_tokens`, `output_tokens`, `total_tokens`
- `estimated_cost_usd`
- `model_calls`
- `fallback_count`

Missing optional fields are recorded as unknown, not treated as errors.

## CLI

`scripts/create_anti_lesson_dogfood_report.py` reads existing reports only and
writes JSON/Markdown artifacts. It accepts:

- `--baseline-report`
- `--experiment-report`
- `--repo-path`
- `--output-json` optional
- `--output-md` optional

Default outputs live under:

- `.agent/experiments/<timestamp>_anti-lesson-control-dogfood.json`
- `.agent/experiments/<timestamp>_anti-lesson-control-dogfood.md`

The CLI must not run benchmarks. It only loads JSON, calls the pure builder
and Markdown formatter, and writes the requested artifacts.

## CLI Path Handling

Report paths must be strict but local-friendly:

- file must exist;
- suffix must be `.json`;
- traversal via `..` is rejected;
- source reports must resolve inside accepted local artifact roots:
  `.agent/benchmarks/` or `.agent/experiments/`;
- source files are read-only inputs and must remain byte-identical after CLI
  execution.

Explicit output paths may be used, but they must resolve under
`.agent/experiments/`, use `.json` for `--output-json` and `.md` for
`--output-md`, reject traversal, and must not overwrite either input report.

## Tests

`tests/test_anti_lesson_dogfood.py` covers:

- pass-rate unchanged -> `greenlight_default_off_experiment_path`
- pass-rate drop >= 5 percentage points -> `reject_correctness_regression`
- previously passing held-out/hard case fails -> regression reason
- different suite sizes / low shared-case ratio -> `inconclusive_missing_matching_cases`
- missing optional cost/token fields handled gracefully
- changed-files, patched-files, and unexpected-mutations comparison
- per-case improved/regressed/unchanged/inconclusive classification
- Markdown includes the guardrail
- CLI writes JSON and Markdown only
- source benchmark reports are byte-identical after CLI/report build
- no benchmark runner call
- no model/API call
- no patch/apply call
- no lesson creation, promotion, or demotion
- forbidden-sink AST guard: no subprocess, Docker, network, model, patching,
  benchmark execution, Dream, or mutation oracle imports/calls
- no changes to `core/control_engine.py`, `core/prompter.py`, or
  `core/lesson_retrieval.py`

## Validation

Implementation validation runs:

```text
python -m compileall core scripts tests
python -m pytest tests/test_anti_lesson_dogfood.py -q --basetemp .fresh_tmp_anti_lessons_11_8
python -m pytest tests -q --basetemp .fresh_tmp_phase11_8_full
python -m benchmarks.run_benchmarks --check
```

Expected:

- focused tests pass
- full pytest green
- benchmark `--check` remains 50 checked, 0 errors

## Implementation Report

After implementation, report:

- files changed
- report helper behavior
- CLI behavior
- decision policy
- proof no benchmarks are run
- proof no CONTROL/retrieval behavior changed
- proof source reports are not mutated
- focused pytest result
- full pytest result
- benchmark `--check` result
