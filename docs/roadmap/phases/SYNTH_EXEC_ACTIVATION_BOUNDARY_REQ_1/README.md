# SYNTH.EXEC.ACTIVATION.BOUNDARY.REQ.1

Additive requirement evolution for `synthetic.EXECUTOR.1R.decrement_3` only.
The normative [requirement](requirement.json) supersedes exactly the historical
`first_behavior_boundary.first_behavioral_effect = BEFORE exact read` claim.
The historical contract and all existing implementations remain byte-preserved.

Dispatch of the exact scenario-executing JVM is the conservative behavioral
activation boundary. All preparation evidence, full harness readiness and
consumer readiness must precede runtime consumption. Runtime consumption must
precede BEFORE permission consumption, which must precede dispatch. Only
mandatory authenticated permission checks/commits may intervene between runtime
consumption and dispatch. No preparation or refund is permitted after consumption.

The exact frozen source contains `private int value = 10;`. Ordinary construction
initializes that mutable state before the BEFORE read. The full executable
harness remains unresolved, so this review identifies no earlier exact harness
instruction and makes no general claim about every JVM launch.

Behavioral activation readiness remains **false**, with `PROOF_UNRESOLVED`.
All new phase authority flags remain false and all operational effect counters
remain zero. No preparation owner, receipt, consumer, runtime integration,
harness or executor is implemented. No source/class artifact is materialized.
The historical owners' existing narrow authority matrices are preserved; this
review grants no additional authority.

PREP materialization, compilation and readiness proposals remain non-operational.
A separate small preparation-contract closure review must confirm compatibility
with this boundary before any preparation implementation.

- [Final review and measured outcome](SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_REPORT.md)
- [Machine-readable review](SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_REPORT.json)
- [Static compatibility evidence](compatibility_review.json)
- [Pure requirement/source tests](test_requirement.py)
- [Guarded validation tooling](validate_pure.py)
- [Validation and baseline comparison](validation_summary.json)
- [Historical preservation](preservation_comparison.json)

Validation runs only source/AST/JSON checks and report-only registry/picker and
benchmark checks. The guard denies operational owner imports, capability
issuance/consumption, process/network operations and writes outside this new
phase. Bytecode and pytest cache writes are disabled. Historical bytes and
pre-existing workspace changes are compared against an immutable baseline.
Host Python and source-control commands used to author and validate these
documents grant no runtime shell or repository-write authority.

Reproduce from the repository root with `python -B` and the scripts in this
directory. Run `validate_pure.py --mode focused`, `--mode registry_after`,
`--mode compare`, `--mode benchmark`, `--mode static`, `--mode preservation`
and `--mode git_diff`, then `finalize_report.py`. The original `snapshot` and
`registry_baseline` modes refuse to overwrite their immutable baselines.
The raw focused `passed_count` includes unittest subtest reports; the final
summary counts the 12 unique test nodes separately.

**STOP after this requirement review.** Completion does not authorize launch or
make any PREP proposal an operational requirement.
