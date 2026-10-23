# SYNTH.AUTH.LIFECYCLE.PINNED.1A

Additive pinned execution-lease owner implemented against the unchanged
[frozen contract](../SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/contract.json).

- [Implementation report](SYNTH_AUTH_LIFECYCLE_PINNED_1A_REPORT.md)
- [Machine-readable report](SYNTH_AUTH_LIFECYCLE_PINNED_1A_REPORT.json)
- [Validation summary](validation_summary.json)
- [Historical preservation](preservation_check.json)
- [Registry and picker comparison](registry_comparison.json)
- [Independent source review](implementation_review.json)

The owner is `core.synthetic_runtime_authorization_pinned_lifecycle`, with the
distinct `PinnedSyntheticRuntimeExecutionLease` type and
`synthetic_runtime_execution_lease_pinned_1_v1` schema. It authenticates through
the unchanged public pinned authorization validator and binds every public
provider field. Consumption remains blocked by `PROOF_UNRESOLVED` until a
separately reviewed pinned consumer/source/compile contract exists.

Validation uses isolated source-loaded owner and authorization copies with an
inert public-validator seam. No production registry is seeded, no production
validator is patched, no provider graph is built, and no consumer-readiness
bypass is supplied. Isolated records are test evidence, never operational
capability evidence. No operational lease is issued or consumed.

Reproduce the safe validation using `python -B validate_pure_implementation.py`
with `--mode implementation`, `focused`, `registry_after`, or `benchmark`, and
`--scratch-root` pointing to a writable directory outside this repository.
The baseline modes were run before adding the owner; their artifacts are frozen.
Run `python -B check_preservation.py --mode check` to compare historical bytes.

The historical CONTRACT test asserting that the future module is absent passed
before implementation. Its bytes remain unchanged. The after selection excludes
that single stage-specific test and runs the remaining frozen safe checks.
Registry/picker checks retain the same seven baseline failures; the comparison
records unchanged selected tests, results, registry summary, and picker output.
No full issuance-dependent suite is claimed.
