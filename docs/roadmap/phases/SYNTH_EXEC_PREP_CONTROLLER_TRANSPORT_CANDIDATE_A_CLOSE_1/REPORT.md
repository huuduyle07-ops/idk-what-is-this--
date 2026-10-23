# Candidate A budget incompatibility closure audit

**CANDIDATE_A_CLOSURE_UNRESOLVED**

The requested exact proof cannot be frozen unchanged. The retained projection
has a five-digit class-size assignment, while the frozen class-size envelope
allows one through five digits. Those two variable fields are absent from the
projection's nonnegative residuals. The conditional 637-byte excess is exact;
the assertion that 637 is an unconditional minimum is not established.

A separate conservative width comparison still exceeds the cap by 629 bytes.
Thus this audit identifies a defect in the required exact premise, not evidence
that Candidate A can fit. The user explicitly gated the requested rejection on
all premises being exact and fixed its minimum at 637. This phase records the
permitted unresolved outcome instead of substituting another formal proof.

## Confirmed candidate and capture premises

The historical reviewed candidate is A: a persistent, single-thread in-container
Python controller using the original persistent stdio channel. It remains
formally UNSELECTED. Historical preference remains
`PREFERRED_BUT_SELECTION_UNRESOLVED`; the historical transport result is still
`TRANSPORT_SELECTION_UNRESOLVED`.

| Premise | Frozen source |
| --- | --- |
| Persistent single-thread controller | `TRANSPORT_1/selection.json`: candidate A criteria and `child_process.ownership` |
| Responses use controller stdout | `BUDGET_PROOF_1R/budget_witness.json`: selected profile message directions and physical streams |
| One four-octet u32be header per response | `TRANSPORT_1/selection.json`: `wire.length_encoding`, `wire.maximum_header_bytes` |
| Both MATERIALIZE COMPLETE and COMPILE COMPLETE responses count | `BUDGET_SCOPE_REQ_1/requirement.json`: `counter_interval`, `normative_table`; frozen witness `effect_sequence` |
| Requests remain controller input and add zero stdout bytes | Frozen witness profile `physical_stream`, `inside_stdout_cap`, `request_bytes_added_to_stdout` |
| Successful controller stderr is zero | `TRANSPORT_1/selection.json`: `wire.stream_budgets`; frozen witness profile |
| Cumulative stdout cap remains 8192 | `BUDGET_SCOPE_REQ_1/requirement.json`: `caps`, `counter_interval`; `TRANSPORT_1/selection.json`: `wire.stream_budgets` |

The scope starts at the preparation owner's authenticated materialization
admission before dispatch, and ends at the final physical byte of the complete
terminal COMPILE response. Counters do not reset between effects. Full response
evidence and actual framing count; input requests do not become stdout. No extra
observation exchange is invented.

Candidate A's quoted container/workspace-generation/controller-generation
widths of 66 are justified by its own frozen full 64-hex container identity and
independent 32-byte hex generation tokens. They are conditional for general
transport arithmetic, but exact for this reviewed candidate profile.

## Arithmetic and residual audit

Read-only evaluation of the frozen symbolic layouts and recorded width
substitutions reproduces:

| Retained five-digit class profile | Bytes |
| --- | ---: |
| MATERIALIZE response | `3567 + R_M` |
| COMPILE response | `5254 + R_C` |
| Semantic response aggregate | `8821 + R_M + R_C` |
| Two response headers | `8` |
| Candidate A physical aggregate | `8829 + R_M + R_C` |
| Excess over 8192 in this profile | `637 + R_M + R_C` |

All 88 **listed** residual leaves are nonnegative: 39 in MATERIALIZE and 49 in
COMPILE. Every residual is actual canonical scalar width minus its assigned
partial lower width, with path multiplicity retained separately per response.
Nonempty generic IDs have quoted width at least 3; unsigned/positive integers
need at least one decimal byte; raw start strings need at least 3 quoted bytes;
namespace grammar minima are the kind length plus 6; required full regular-file
and directory modes need at least five decimal digits. No listed unresolved
kernel or numeric term has a legally negative difference. No kernel values or
identity encodings are instantiated.

The coverage gap is in **two omitted class-size fields**:

- `/result/class_metadata/size_bytes`
- `/result/workspace_state/work_manifest/2/size_bytes`

Both frozen symbolic leaves have canonical-width interval `[1,5]`. The selected
profile assigns 5. Kernel `budget_projection.py` includes `class_size` in
`EXACT_FAMILIES`, so neither occurrence enters `R_C`.

The full response comparison therefore also needs the already-frozen width
term `2*(D_class-5)`, where `D_class` is in `{1,2,3,4,5}`. Its interval is `[-8,0]`.
This is a width interval, not an observed class size or an attainable execution
witness. The current source does not prove an actual class size of at least
10000 bytes. Such a premise cannot be added here.

| Class decimal width | Physical lower subtotal with listed residuals zero | Excess |
| --- | ---: | ---: |
| 1 | 8821 | 629 |
| 2 | 8823 | 631 |
| 3 | 8825 | 633 |
| 4 | 8827 | 635 |
| 5 | 8829 | 637 |

The conservative comparison `8829-8=8821>8192` follows without observing a class
or changing a kernel projection. It establishes incompatibility mathematically,
but does not establish the exact universal 8829/637 premise mandated for this
closure. Neither the historical projection nor its residual definitions are
rewritten to hide this distinction.

## Writer topology and preserved boundaries

The retained shape is one accounted controller writer with two potential-root
handles in each response. It is explicitly a structural LOWER profile, not a
complete inventory. Truthful additional mandatory writer/task/handle records
append positive JSON record bytes and separators under the unchanged schema.
No shortening, record replacement, omission or deduplication is authorized.

Overall transport selection and budget feasibility remain unresolved. Candidate
A receives no formal rejection in this exact phase. No replacement is selected
and remaining candidates are not ranked. There is no global stdio/controller/
transport impossibility or `FROZEN_AGGREGATE_BUDGET_IMPOSSIBLE` classification.

`KERNEL_IDENTITY_CONTRACT_UNRESOLVED` and
`WRITER_INVENTORY_COMPLETENESS_UNRESOLVED` remain unchanged; settled kernel
projection rules remain frozen and incarnation-bearing fields remain unresolved.
No schema, evidence, cap, owner encoding, PREP/workspace contract or historical
artifact is edited or repinned. A later formal closure must be additive; any
explicit requirement evolution belongs to a new epoch.

The production registry has no entry for the frozen TRANSPORT.1 or subsequent
identity phases. `roadmap_addendum.json` follows their additive artifact
convention and records the historical candidate, later evidence, exact-premise
failure and closure linkage without rewriting phase completion history or
activating supersession.

## Validation evidence

`input_artifacts.json` records 59 input artifact hashes and checks 48 embedded
source-hash references. `premise_audit.json` contains every audited residual and
both omitted class-size paths. `closure.json` is the machine-readable outcome.

The pure validation helper denies child-process creation, network activity,
runtime/capability-owner imports, issuance, transitions and writes outside this
new phase. All guarded operational counters are zero. No Docker, controller,
Java, compiler, live kernel inspection, writer inventory or capability issuance
is run. Historical Python sources are hashed/compiled in memory, never imported
as capability owners or executed as proofs.

Benchmark `--check` passes 54 cases with zero errors. Registry/picker checks
retain the same seven baseline failures and identical projections. Focused
checks include the nine new closure tests plus frozen source/contract tests.
One frozen kernel test already rejects its own historical `git_checks.py`
subprocess import; this source is preserved, and the same failure is confirmed
by the historical-only focused comparison. See `validation_summary.json` for
counts, exact diagnostic comparisons and final validation status.

Whole non-cache preservation compares all 27062 preexisting files. It covers
all historical contracts, schema, budget proofs, workspace/PREP and sandbox/
provider/runtime artifacts, as well as the user's existing dirty files. JSON,
whitespace, in-memory compilation and fixed read-only Git checks are recorded.
Git commands are solely the user-required validation checks, not runtime
process probes. No stash/reset/clean is used. Validation scratch and all authored
files remain in this additive phase.

STOP. No replacement transport is selected.
