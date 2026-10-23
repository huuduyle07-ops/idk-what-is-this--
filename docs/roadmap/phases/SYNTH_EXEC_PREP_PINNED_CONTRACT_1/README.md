# SYNTH.EXEC.PREP.PINNED.CONTRACT.1

**PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION**

Pure contract/source analysis. The historical reflection contract explicitly
names the BEFORE read as the first behavioral effect, while the exact frozen
source initializes mutable instance state during construction before that read.
The conflict is recorded without changing history or enabling an operation.

- [Analysis and decision](SYNTH_EXEC_PREP_PINNED_CONTRACT_1_REPORT.md)
- [Machine-readable contract and bounded proposed rules](contract.json)
- [Machine-readable report](SYNTH_EXEC_PREP_PINNED_CONTRACT_1_REPORT.json)
- [Raw source hashes and exact evidence anchors](evidence_index.json)
- [Measured validation](validation_summary.json)
- [Source/AST tests](test_contract.py)
- [Guarded validation harness](validate_pure.py)

All authority flags remain false. Runtime readiness remains false with
`PROOF_UNRESOLVED`. No preparation or consumer owner was implemented, and no
operational owner was imported or invoked by validation. Writes are confined to
this new documentation/validation directory; no Java source/class is written.

The proposed preparation rules distinguish exact bytes in memory, a single
ephemeral sandbox source write, and exact scenario compilation. They do not
grant materialization, compilation, runtime or reflection permission. The full
executable harness has no frozen source/hash; the two frozen reflection helpers
are insufficient to establish consumer readiness.

Reproduce source-only checks from the repository root with Python bytecode
writes disabled:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/capture_evidence.py
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/validate_pure.py --mode focused
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/validate_pure.py --mode frozen
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/validate_pure.py --mode benchmark
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/validate_pure.py --mode registry_after
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/validate_pure.py --mode static
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/validate_pure.py --mode preservation
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/validate_pure.py --mode git_diff
python docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/validate_pure.py --mode finalize
```

The original baseline cannot be overwritten. Seven existing registry/picker
test failures are accepted only when their exact node/phase results and the
registry/picker projections match baseline. Full operational suites are outside
this phase. Source-control status/diff processes are recorded separately from
the guarded operational zero-effect checks.

STOP after this contract decision. Resolve the named requirement evolution in a
separate contract review before implementing preparation or consumer owners.
