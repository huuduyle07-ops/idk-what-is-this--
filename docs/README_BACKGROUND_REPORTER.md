# Background Reporter

## Purpose

Run safe read-only benchmark reports in the background.

This does not patch code, does not apply changes, and does not commit.

## Smoke run

```bash
python scripts/run_background_reporter.py --case ts_inventory_restock --timeout-sec 600
```

## FULL RUN

python scripts/run_background_reporter.py --timeout-sec 3600

## OUTPUT

- .agent/reports/background_report_YYYYMMDD_HHMMSS.md
- .agent/reports/background_report_YYYYMMDD_HHMMSS.json
- .agent/benchmarks/benchmark_report_*.json
- .agent/benchmarks/benchmark_report_*.md

## What the report contains
- Benchmark --check
- Full or smoke benchmark summary
- Brain Stamp
- Regression comparison
- Regression alert, if success rate drops enough

## Safety rules
- Report-only
- No patching
- No real repo writes except .agent/reports and .agent/benchmarks
- No auto-commit
- No auto-apply