# AgentBench 22-case Milestone

Date: 2026-05-16

Command:

```bash
python benchmarks/run_benchmarks.py --fast --summary --skip-toolchain-failures --markdown --retry-failed 1
```

Result:

Passed: 22/22
Failed: 0
Skipped: 0
Flaky: 1
Flaky case: ts_optional_property_guard, passed on attempt 2/2
Duration: 916.72s
Average per case: 38.77s

Notes:

This is a successful full fast run with retry visibility. It should not be described as a clean no-flake run.