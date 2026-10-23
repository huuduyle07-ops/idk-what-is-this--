# Candidate A conservative budget rejection

**CANDIDATE_A_REJECTED_BUDGET_INCOMPATIBLE**

The reviewed Candidate A persistent-stdio profile cannot satisfy the frozen
8192-byte cumulative preparation stdout requirement. Its physical stdout is
at least **8821 bytes**, proving excess **at least 629 bytes**. This is a
conservative lower bound; attainable equality is not established or needed.

The rejection applies only to Candidate A's reviewed persistent single-thread
in-container Python controller, response-to-stdout mapping, four-byte u32be
response framing, current frozen message/evidence semantics and cumulative
8192-byte effect-attempt cap. Candidate A was historically UNSELECTED and has
never been selected. Its new candidate-level status is
`REJECTED_BUDGET_INCOMPATIBLE`.

Overall transport selection remains `TRANSPORT_SELECTION_UNRESOLVED`.
Universal budget feasibility remains unresolved. No replacement is selected
and no remaining designs are ranked.

## Corrected conservative theorem

For the retained lower writer topology, the frozen symbolic profile yields:

```text
retained_topology_physical_stdout_bytes
    = 8829 + R_M + R_C + 2 * (D_class - 5)

R_M >= 0
R_C >= 0
D_class in {1, 2, 3, 4, 5}

2 * (D_class - 5) >= -8

physical_stdout_bytes >= 8829 - 8 = 8821
8821 > 8192
physical_stdout_bytes - 8192 >= 629
```

For every Candidate-A preparation effect encoding satisfying the reviewed
profile, frozen schema and current frozen evidence semantics, physical stdout
therefore has this lower bound. Completing truthful mandatory writer, process,
task or handle evidence cannot reduce it: additional records add nonnegative
canonical JSON bytes. No removal, replacement or deduplication is authorized.

No actual class size, kernel identity encoding, exact numeric observation,
finite residual maximum, attainable execution witness or writer-completeness
proof is required.

## Exact class-width correction

The prior partial profile has MATERIALIZE `3567 + R_M` and COMPILE
`5254 + R_C`, totaling `8821 + R_M + R_C` semantic bytes. Two four-byte response
headers yield the retained five-digit-class physical subtotal
`8829 + R_M + R_C`.

Exactly two COMPILE scalar occurrences share symbol `class_size_digits` and
had been assigned five decimal bytes outside the existing residuals:

- `/result/class_metadata/size_bytes`
- `/result/workspace_state/work_manifest/2/size_bytes`

The unchanged class-size envelope is `1..32768`, whose legal decimal widths
are `{1,2,3,4,5}`. The width-only correction is therefore
`2 * (D_class - 5)`, with interval `[-8,0]`.

| D_class decimal width | Lower physical subtotal | Excess over 8192 |
| --- | ---: | ---: |
| 1 | 8821 | 629 |
| 2 | 8823 | 631 |
| 3 | 8825 | 633 |
| 4 | 8827 | 635 |
| 5 | 8829 | 637 |

No row is asserted to be the actual compiled size or an attainable equality.
The minimum of these relaxed width subtotals is 8821; this establishes physical
stdout **>=8821** and proven excess **>=629**. No javac or class-size observation
is performed, and the frozen class-size envelope is unchanged.

## Residual and scalar coverage audit

Every existing residual is the actual canonical scalar width minus its valid
assigned lower width. Every path occurrence and symbol multiplicity is
reaudited independently per response. MATERIALIZE has 39 residual leaves and
COMPILE has 49, totaling 88.

| Residual family | Occurrences | Valid lower canonical width |
| --- | ---: | ---: |
| Canonical unsigned/positive integers | 27 | 1 |
| Nonempty generic ID strings | 27 | 3 |
| Quoted canonical decimal start ticks | 4 | 3 |
| Full regular-file/directory st_mode | 9 | 5 |
| Raw namespace strings, kinds mnt/net/pid/ipc/uts | 15 | 9 |
| Raw namespace strings, user | 3 | 10 |
| Raw namespace strings, cgroup | 3 | 12 |

Generic strings cannot be empty; canonical integers require at least one
decimal byte; raw starts require quotes around at least one decimal digit;
full allowed file/directory mode includes the required type bits; raw namespace
grammar requires the exact kind, colon, brackets and at least one decimal
digit, plus JSON quotes. Thus every listed difference is nonnegative and both
residual sums are nonnegative.

Every symbolic scalar is covered by an existing residual, a currently frozen
exact width, or one of the two explicit class-width corrections. Frozen exact
widths include 19-byte quoted owner handles, 66-byte quoted digests and settled
equality projections, and Candidate A's 66-byte quoted container/generation
identities. The latter come from its own full 64-hex container identity and
independent 32-byte hex generation tokens; no universal encoding is inferred.

Unresolved mount, namespace generation, root, controller process, writer
process/task, process group and descriptor identities stay unresolved. Actual
namespace/start widths and numeric values are not selected. Only their
nonnegative remaining contributions matter.

## Candidate and capture premises

The sources are the frozen `TRANSPORT_1/selection.json`,
`BUDGET_SCOPE_REQ_1/requirement.json`, `BUDGET_PROOF_1R/budget_witness.json`,
owner-encoding contract and partial kernel projection. Paths below are within
`docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_...`.

| Confirmed premise | Source field |
| --- | --- |
| Reviewed persistent in-container controller / persistent stdio | `TRANSPORT_1/selection.json`: `reviewed_candidate_architecture`, `reviewed_candidate_transport` |
| Persistent single-thread PID1 Python ownership | `selection.json`: `child_process.ownership`, `bootstrap` |
| Two COMPLETE effect responses on stdout | Frozen witness: `effect_sequence`, selected profile `messages` |
| Four-byte u32be header per response | `selection.json`: `wire.length_encoding`, `wire.maximum_header_bytes` |
| Requests remain input and add zero stdout | Witness profile: `physical_stream`, `inside_stdout_cap`, `request_bytes_added_to_stdout` |
| Successful controller stderr is zero | `selection.json`: `wire.stream_budgets`; witness profile |
| Cumulative 8192 stdout cap, no effect-boundary reset | Scope requirement: `caps`, `counter_interval`; `selection.json`: `wire.stream_budgets` |
| Candidate-specific full container and generation widths | `selection.json`: `bootstrap.start_channel`, `generations.workspace_generation`, `generations.controller_generation` |

The effect interval runs from the preparation owner's authenticated
materialization admission before dispatch to the final physical byte of the
complete terminal COMPILE response. Both required COMPLETE responses retain
their full evidence; framing counts. Requests remain controller stdin.
Successful controller stderr contributes zero to its separate stream.

## Writer and historical boundaries

The frozen structural LOWER profile retains one accounted controller writer
and two potential-root handles per response. It is not a complete writer
inventory. Appending a record to a nonempty canonical JSON array adds the
record's positive width and a comma. Additional required nested evidence also
has nonnegative width. Under unchanged semantics, incomplete inventory cannot
reduce the retained bound.

`KERNEL_IDENTITY_CONTRACT_UNRESOLVED` and
`WRITER_INVENTORY_COMPLETENESS_UNRESOLVED` remain unchanged. Settled kernel
projection rules remain frozen. No incarnation semantics or inventory is
completed, and no controller is implemented.

Historical CLOSE.1 remains **CANDIDATE_A_CLOSURE_UNRESOLVED**, byte-identical.
It correctly stopped because its requested universal 8829/637 premise omitted
the variable class-width term. This additive CLOSE.1R uses the corrected
conservative theorem and records the resulting candidate rejection without
rewriting the prior closure or historical preference.

The registry has no entries for these controller phases. Following the existing
additive roadmap convention, `roadmap_addendum.json` links historical candidate
A, later owner/kernel evidence, the prior unresolved closure and this rejection.
No production registry or phase-completion history is changed.

The rejection is scoped to the current reviewed profile and remains immutable
historical evidence. Reconsideration after explicit evolution of architecture,
stdout mapping, framing, current message/evidence semantics or cap requires a
new epoch and additive phase. No global controller, stdio, transport or universal
aggregate-budget impossibility is classified.

## Validation

`input_artifacts.json` verifies 93 input artifact hashes against the initial
preservation snapshot, 48 embedded source-hash references, and the prior
closure's 34 indexed artifact hashes. `premise_audit.json` records all 88
residuals, all remaining exact-width leaves and the two class corrections.
`closure.json` contains the formal theorem and scoped candidate status.

All 20 focused closure tests pass: 11 new corrected-closure tests and the nine
frozen prior-closure tests. Benchmark `--check` passes all 54 cases with zero
errors. Registry/picker baseline and after results are compared without
repairing their seven preexisting failures or altering projections.

In-memory Python compilation, JSON/whitespace validation, fixed read-only Git
checks and historical preservation are recorded in `validation_summary.json`.
The preservation snapshot covers all 27101 preexisting non-cache files,
including TRANSPORT.1, controller/schema, all budget/scope proofs, owner/kernel
contracts, CLOSE.1, PREP/workspace contracts, historical sandbox/provider/runtime
artifacts and the user's original dirty worktree.

Guarded validation denies child-process/runtime execution, network actions,
capability-owner imports, issuance/transitions and writes outside this new
phase. All guarded counters are zero. No Docker, Java/javac, actual class-size
observation, live kernel inspection, controller, writer inventory or capability
issuance occurs. Historical proof sources are data, never imported or executed.
The separately recorded read-only Git checks are the user-requested validation,
not runtime probes. No stash/reset/clean is used.

STOP. Candidate A is rejected; no replacement transport is selected.
