# SYNTH.EXEC.PREP.CONTROLLER.BUDGET.SCOPE.REQ.1

**SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_COMPLETE**

The new additive requirement defines the unchanged 8192-byte per-outer-stream
capture around the fixed preparation effect attempt: owner materialization
admission before dispatch through the complete compilation response. Initial
empty observation, fresh workspace readiness observation, optional handoff and
mandatory cleanup retain separate existing bounds. In-attempt observations and
pending ordinary response bytes remain in preparation capture.

Read [REPORT.md](REPORT.md), [requirement.json](requirement.json), and the
[normative lifecycle table](normative_table.md). Additive clarification metadata
and frozen source values/hashes are in the requirement. The old budget proof and
all historical bytes remain unchanged. No feasibility or impossibility decision
is made; BUDGET.PROOF.1R must establish a truthful attainable witness.

Validation results: [validation_summary.json](validation_summary.json).

Reproduce from the repository root with its Python environment:

```text
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1/write_requirement.py
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1/validate_pure.py --mode focused
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1/validate_pure.py --mode benchmark
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1/validate_pure.py --mode static
```

Original preservation and registry baselines are immutable. Do not rerun snapshot
or registry-baseline modes over them. The harness has no budget-proof mode. Its
guards prohibit operational effects and outside-phase writes. All authority flags
remain false; operational effects remain zero. STOP after this scope phase.
