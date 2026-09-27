# DEFECT.PROBE.LIVE.1 — Bounded Defect Reproduction Evidence

## Outcome

C.A.T.T.U.S can now execute one immutable, provenance-backed reproduction for
an already-localized defect when whole-repository validation is inconclusive.
The reproduced observation enters the existing PATCH.BASIS boundary; it does
not replace repository validation and grants no write authority.

The deliberately unfixed live case is:

```text
target       core/code_dna.py::_classify_indent
task fact    2-space indentation is classified as 4-space
expected     2space
observed     4space
result       reproduced
```

The full suite may simultaneously remain:

```text
category     validation_budget_exhausted
outcome      inconclusive
```

Those facts answer different questions and coexist without rewriting either.

## Boundary

The live sequence is:

```text
preserved defect-repair task
  -> baseline validation is inconclusive
  -> canonical recall already selected an eligible source target
  -> CONTROL acquired the exact target source
  -> deterministic typed probe contract
  -> static isolated worker
  -> reproduced / not_reproduced / inconclusive / invalid_probe / unavailable
  -> reproduced + valid provenance + fresh exact binding
  -> existing PATCH.BASIS.LIVE.1 grounded_defect boundary
```

Analysis, explicit-change, passing-baseline and genuine executed-failure routes
do not enter the probe. The last condition preserves the existing T1/T2/T3
paths rather than forcing already-meaningful failures through a second gate.

## Independent expectation

The contract records three separate provenance fields:

| Field | Question |
|---|---|
| `probe_basis` | Why may this probe exist? |
| `input_basis` | Who established the concrete input? |
| `expected_behavior_basis` | Who established the oracle? |

The allowed families are deliberately small:

- explicit preserved user reproducer;
- pre-existing source-backed repository test;
- repository contract/specification;
- deterministic fixture adapter from a preserved literal task fact.

Model-authored input, a model-authored expectation, ambiguous provenance and a
test authored by the same patch response are not independent evidence. They
produce `invalid_probe` before any subprocess starts.

The user-requirement case is labeled precisely. If a preserved user requirement
says `add(2, 2) == 5`, observing `4` reproduces disagreement with that user
requirement; it does not claim objective mathematical truth.

## Typed execution

`DefectProbeContract` is frozen. Inputs and expected values are canonical JSON,
not Python or shell text. Its invocation kind chooses code already present in
`core/defect_probe_worker.py`. No contract can supply an arbitrary command,
module expression, assertion, `exec`, `eval`, or `python -c` program.

Two invocation kinds exist:

1. `python_pure_function` imports one exact `.py` file and calls one simple
   identifier with JSON args/kwargs.
2. `existing_pytest` runs one already-known `path.py::test_node`, after the
   named test source is directly bound to the grounded target symbol.

The test runner does not discover a probe. It receives the selector from an
already-established source and disables plugin autoload and pytest's repository
cache.

## Execution safety and freshness

The parent uses the existing `SafeValidationCommand` runner:

- argv execution with `shell=False`;
- a five-second default and ten-second hard maximum;
- timeout kill/reap;
- secret-scrubbed child environment;
- OPS.VALIDATE.2's fresh temporary `PYTHONPYCACHEPREFIX`.

A verdict requires bytecode isolation. The contract records the localized
target's source digest, the pre-patch run refuses if those bytes changed, and
the worker records the bytes it actually executed. Repository `__pycache__`
content is neither read nor deleted.

The worker guards repository writes, network connection constructors and child
processes. A refused side effect is `inconclusive`; it never becomes a
reproduced defect. No repository copy, scan, graph walk or test search was
added. Only the exact target and, when explicitly selected, exact test file are
read.

## T6 deterministic adapter

The adapter recognizes a literal preserved family:

```text
N-space indentation is classified as M-space
```

It creates nested text whose depth `d` starts with exactly `N * d` spaces and
expects `Nspace`. This is a reusable indentation-style fixture family; it does
not name or branch on `_classify_indent`.

With `N=2`, more fixture lines occur at depth two or greater than at depth one.
The current implementation counts four-space prefixes as independent style
votes, so it returns `4space`. The probe records that observed value against the
independently preserved `2space` expectation. The source remains unchanged.

## PATCH.BASIS integration

Only a pre-patch receipt with all of the following may ground a defect:

- `probe_result=reproduced`;
- allowed independent probe, input and expectation bases;
- exact eligible source target binding;
- current-source isolated-bytecode freshness;
- an executed source digest.

CONTROL then emits `kind=bounded_defect_reproduction` and
`patch_basis_source=bounded_defect_reproduction` through the existing
`grounded_defect` route. It does not create a parallel patch-authority path.
`write_authority` and `patch_application_authority` remain false. Patch safety,
`AUTO_PATCH_ENABLED`, execution authorization, human approval, post-patch
validation and rollback retain their existing meanings.

The same immutable semantic contract can be rerun with
`execution_stage=post_patch`; its input and oracle do not change. A post-patch
receipt can show `not_reproduced`, but it cannot retroactively establish the
pre-patch defect and it is not whole-repository validation.

## Telemetry

The bounded top-level fields are:

```text
defect_probe_attempted
defect_probe_basis
defect_probe_target
defect_probe_result
defect_probe_observed
defect_probe_expected_basis
defect_probe_freshness
```

The structured receipt also retains input basis, exact target binding,
execution kind, expected value, timeout, execution stage, executed source
digest and categorical reason. It contains no confidence score or hidden model
reasoning.

## Frozen systems

This phase does not change `_classify_indent`, the global validation timeout,
test selection policy, general affected-test optimization, retrieval,
identifier recall, ranking, graph/index construction, patch generation, patch
safety, write authority, execution policy, answer grounding or network policy.
It adds no model call, verifier model, model-generated TDD oracle, targeted
validation acceptance policy, background process, repository traversal or
parallel authority route.

