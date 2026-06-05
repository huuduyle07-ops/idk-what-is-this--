# 08 Memory Temperature Explainability

_No memory-temperature report was found under `.agent/reports/memory_temperature/` (or `.agent/memory_temperature.md`)._

This section is explain-only: it shows how warm each already-loaded lesson / proposal / note is, so a reviewer can see *why* a memory would or would not be surfaced. It never changes retrieval, ranking, or scoring.

## Thermal bands

- 🔥 **hot** (`temperature >= 0.75`): recently reinforced or trusted; would be surfaced.
- 🌤 **warm** (`temperature >= 0.40`): still relevant; would be surfaced.
- ❄️ **cold** (`temperature < 0.40`): cooled off; not surfaced by default.
- 🧊 **frozen** (`temperature == 0.0`): hard-frozen; never surfaced.

## Cooling formula

```
T_now = clamp(T_base * exp(-lambda * age_days) + reheating - risk, 0, 1)
```

where `lambda` is the cooling rate, `age_days` is how long since the memory was last used, `reheating` rewards human approval / repeated use / recent success, and `risk` subtracts needs-review and risk-score penalties.

## Hard-freeze override

Records marked `blocked`, `unsafe`, failed-validation, or `audit-only` are hard-frozen to `temperature == 0.0` regardless of reheating, so an unsafe memory can never be surfaced. They remain visible here purely for explanation.

A report is produced by the read-only memory-temperature classifier, which is also embedded in the Related Notes / Lessons explainability output:

```
GET /graph/explainability/view  (repo_path, query)
```

> Memory temperature is explain-only. It does not change lesson retrieval, CONTROL prompts, ranking, patch generation, validation, benchmark scoring, or storage behavior.
