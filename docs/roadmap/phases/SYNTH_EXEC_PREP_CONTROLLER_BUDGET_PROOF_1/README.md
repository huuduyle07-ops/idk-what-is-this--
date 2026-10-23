# SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1

Result: **AGGREGATE_BUDGET_SCOPE_UNRESOLVED**.

Read [REPORT.md](REPORT.md) for the frozen lifecycle audit, conservative byte bounds, scope gap, per-message/subtree contributions and stress profiles. [The machine-readable report](SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1_REPORT.json) and [full byte witness](budget_witness.json) preserve exact canonical payloads and their limitations.

No truthful feasible witness or unconditional impossibility is claimed. No requirement, historical artifact or transport selection is changed. All authority flags remain false and operational effects zero.

`proof.py` only constructs declarative schema length probes. They are explicitly not authenticated execution witnesses. `validate_pure.py` runs proof tests, benchmark checks and registry/picker comparisons in memory under process/network/owner-import/outside-write guards. Original preservation and registry baselines are immutable. Reproduction commands are in the report.
