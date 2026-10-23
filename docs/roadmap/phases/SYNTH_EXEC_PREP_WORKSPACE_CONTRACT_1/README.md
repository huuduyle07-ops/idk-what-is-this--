# Live preparation workspace contract

**WORKSPACE_REQUIRES_CONTROLLER_EVOLUTION**

This additive pure contract freezes the future exact live workspace boundary
and records the required additive retained controller. The historical controller
always tears down before returning. No workspace, container, authority, owner,
harness or operational effect is created here.

Read [the report](SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1_REPORT.md),
[contract.json](contract.json), [evidence_index.json](evidence_index.json) and
[validation_summary.json](validation_summary.json).

From the repository root:

```powershell
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/validate_pure.py --mode MODE
```

Modes: snapshot (immutable inventory, once), git_baseline (immutable, once),
registry_baseline (immutable, once), author, focused, registry_after, compare,
benchmark, static, git_diff, preservation, report. `author` reads frozen
contracts/source/AST only; `report` aggregates measured results. Both use the
operational guard. Git modes run only source-control whitespace checks and
never modify the index. All scratch/evidence remains inside this phase.

Registry comparison preserves existing failures and raw diagnostics. It
normalizes only process-specific allocator addresses in Python reprs before
comparing signatures. No registry changes or baseline repairs are authorized.
All pre-existing non-cache files/links are hashed before and after; this phase,
Git metadata and recorded caches are excluded, and links are never followed.

STOP after this contract. Additive controller, workspace/preparation owner,
issuance, full harness and consumer implementation require separate work.
