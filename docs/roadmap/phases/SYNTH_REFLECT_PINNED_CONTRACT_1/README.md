# SYNTH.REFLECT.PINNED.CONTRACT.1

Pure additive pinned reflection admission and one-shot lifecycle contract.
No owner, adapter or capability is implemented or issued.

Start with [the normative contract](SYNTH_REFLECT_PINNED_CONTRACT_1.md),
[contract.json](contract.json) and [source proof](source_proof.md).
The measured [completion report](SYNTH_REFLECT_PINNED_CONTRACT_1_REPORT.json)
and [validation summary](validation_summary.json) record the final result.
Behavioral readiness remains false with PROOF_UNRESOLVED; compilation authority
remains false. Stop after contract freeze.

Reproduce source-only validation from the repository root with
`python -B docs/roadmap/phases/SYNTH_REFLECT_PINNED_CONTRACT_1/validate_pure_contract.py --mode MODE`.
Modes: `frozen`, `focused`, `benchmark`, `registry_baseline`, `registry_after`.
The original registry baseline cannot be overwritten. `frozen` extracts only
reviewed source/AST assertions into file-only facades; owner modules, fixtures,
objects and production validators are never executed. Guarded checks deny
capability imports/issuance/transitions, execution, process/network effects and
runtime writes. Scratch stays within this new phase and bytecode/cache writes
are disabled. Existing baseline failures are compared, not repaired here.

`capture_preservation.py baseline|after` hashes historical workspace bytes;
`finalize_validation.py --mode static|finalize` checks in-memory compilation,
JSON/whitespace, source invariants and measured validation evidence. Baselines
are historical evidence; do not recapture them as part of reproduction.
Never run owner `verify()` or issuance-dependent suites for this phase.
