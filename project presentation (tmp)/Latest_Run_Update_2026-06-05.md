# Latest Run Update — 2026-06-05

Use this as the presentation addendum / speaking note for the latest run.

## Headline

- Full pytest suite: **2436 passed**, **1 warning**, **0 failures**.
- Latest benchmark run: **50 / 54 passed**, **92.6% success rate**.
- Flaky case: `ts_migration_import_path_case` passed on retry.
- Benchmark report: `.agent/benchmarks/benchmark_report_1780663060.json`
- Markdown report: `.agent/benchmarks/benchmark_report_1780663060.md`

## Benchmark Evidence

- Total cases: 54
- Passed: 50
- Failed: 4
- Skipped: 0
- Languages/families covered: C++, C#, Go, HTML, JavaScript, Python, Rust, TypeScript
- Tokens: 171000 input / 54162 output / 225162 total
- Estimated known API cost: `$0.0649`
- Unknown-cost calls: 53
- Model fallbacks: 8
- Self-corrected cases: 2

## Current Failure Set

| Case | Language | Category | Note |
|---|---:|---|---|
| `cpp_string_view_lifetime_trap` | C++ | logic_error | Missing expected `processor.cpp`; 2 failed attempts |
| `go_validation_command_misleading_success` | Go | correctness | Missing expected `calculator.go`; 2 failed attempts |
| `python_embedding_provider_switch` | Python | migration | Missing expected `embedding_adapter.py`; 2 failed attempts |
| `ts_callback_dispatch_ambiguity` | TypeScript | callback_dispatch_ambiguity | Missing expected `handlers.ts`; 2 failed attempts |

Failure taxonomy from the report:

- `model_fallback_instability`: 3
- `unknown`: 1

## Presentation Framing

Do not present this as "perfect benchmark performance." Present it as:

> The core test suite is green, benchmark coverage has expanded to 54 cases, and the benchmark now exposes four concrete hard cases instead of hiding them.

The strongest claim is not perfection. The strongest claim is observability:

- failures are named
- expected files are named
- retry behavior is visible
- model fallbacks are counted
- cost and token budget are quantified

## Updated Conclusion Line

The system is stable under the full unit/integration suite, broader benchmark coverage now shows a 92.6% pass rate, and the remaining benchmark failures are specific enough to drive the next engineering iteration.

## Folder Updates

- `Presentation_Script.md` conclusion updated to 54 benchmark cases and 2436 pytest passes.
- `latest_benchmark/benchmark_report_1780663060.md` copied from `.agent/benchmarks`.
- `latest_benchmark/benchmark_report_1780663060.json` copied from `.agent/benchmarks`.
- `presentation_evidence/` regenerated from existing benchmark, experiment, trend, watchlist, graph, and memory-temperature artifacts.
