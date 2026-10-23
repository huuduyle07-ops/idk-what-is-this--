# Retained live preparation controller protocol

Pure contract only. Read [the report](SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1_REPORT.md),
[contract.json](contract.json), [message_schema.json](message_schema.json) and
[validation_summary.json](validation_summary.json).

No controller source or workspace owner exists. Source identity and concrete
transport remain unresolved. Behavioral readiness is false / PROOF_UNRESOLVED.

Validation from repository root:

```powershell
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/validate_pure.py --mode MODE
```

Modes: snapshot, git_baseline and registry_baseline are immutable and run once
before authoring. Then author, focused, registry_after, compare, benchmark,
static, git_diff, preservation and report. All generated evidence/scratch stays
in this phase. Guarded modes deny owner imports, operational processes,
network and writes outside this phase. Git modes perform source-control
whitespace checks only and never mutate the index. Existing baseline failures
are compared rather than repaired. Historical files are hashed before/after.

The schema is declarative contract data; no parser/controller is implemented.
STOP after contract freeze; no live operations or capabilities are issued.
