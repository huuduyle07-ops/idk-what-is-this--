# Pure validation evidence

Validation in this phase uses the historical audit harness copied into this new
directory. Historical harnesses, owners, tests, registry and reversal files are
preserved. Python bytecode writes are disabled. Captured logs and scratch writes
stay in this phase directory.

The harness blocks operational capability-owner imports, process launches,
network activity, capability issuance or transitions, verifier/executor calls,
and repository writes outside this phase. Dependency-only IPv6 availability
probing is disabled before importing benchmark dependencies, following the
frozen contract's documented technique. Production validators are not patched
and production registries are not seeded.

Safe commands, run with `PYTHONDONTWRITEBYTECODE=1`:

```text
python docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/validate_historical_pure.py --mode registry_baseline
python docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/validate_historical_pure.py --mode registry_after
python docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/validate_historical_pure.py --mode focused
python docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/validate_historical_pure.py --mode frozen
python docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/validate_historical_pure.py --mode benchmark
python docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/check_historical_sources.py
python docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/finalize_safe_validation.py
```

`focused` in the historical harness selects only the frozen reflection contract's
152 source/AST/JSON tests. It is separate from this phase's focused isolated-owner
implementation tests. `frozen` executes fourteen explicitly inspected test bodies
against source-path facades without importing capability owners or executing
historical issuance fixtures. Ten additional independent AST/source checks cover
unchanged request/renderer boundaries, old admission scope, old reflection
lifecycle binding and state authentication, permanent historical tombstones, and
pinned runtime unresolved consumer readiness. Historical executor stop conditions
are inspected as source only.

The registry/picker baseline has 299 tests: 292 passed and seven failed. These are
preexisting stale registry-history assumptions and are retained unchanged. The
after run is compared by complete failed-node list, passed-node list, collection
count, registry projection and picker projection. Baseline failures are not
repaired by modifying frozen registry/test history.

The benchmark path is `benchmarks/run_benchmarks.py --check`, executed inside the
guarded process. It checked 54 static cases with zero errors. No benchmark case
was behaviorally executed.

`preservation_baseline.json` captures 2,410 preimplementation files, including
existing untracked history. `preservation_check.json` compares exact SHA-256 and
byte length against the current files. `static_validation.json` records in-memory
compilation, AST parsing, strict UTF-8 JSON readability and authored whitespace
checks. `safe_validation_summary.json` joins those measurements with the guarded
run results. Final success requires preservation, exact registry/picker
equivalence, successful pure contract/source checks, successful benchmark check,
and zero operational attempts in each guarded run.

No full suite or issuance-dependent frozen suite is claimed.
