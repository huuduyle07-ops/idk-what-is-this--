# OPS.VALIDATE.2 — Timeout Truthfulness, Budget Exhaustion & Python Cache Freshness

**Track:** OPS · **Prerequisite:** EXEC.AUTH.LIVE.1 · **Shipped:** 2026-09-01
**Kind:** live production validation correctness fix. Not report-only, not a
plan, not a shadow experiment.

Two reproduced defects, one claim: *the thing validation reports must be the
thing that actually happened.*

---

## Defect A — timeout laundering

On the C.A.T.T.U.S self-repository black-box task:

| | |
|---|---|
| repository tests | ≈ 8,944 (measured: 8,966 collected) |
| validation command | `python -m pytest` |
| validation budget | 30 s |
| production reported | `test_failure` |

That statement is false. The validation infrastructure exhausted its allowed
time; the tests never established that the candidate was wrong.

### Why it happened

`core.validator.classify_validation_output` received only `(output, exit_code,
command)`. On a timeout the runner returned partial output — and partial pytest
output contains `collected 8944 items` and, very often, a `FAILED …` line. The
classifier's generic `test_patterns` branch matched, and the run came back as
executed-failure evidence.

Pinned in `test_partial_pytest_output_looks_like_defect_evidence_on_its_own`:
classified without knowing a budget ran out, that text really does land in
`EXECUTED_FAILURE_CATEGORIES` — the set that is allowed to ground a diagnosis.

### The fix

`core/validation_outcome.py` gains one canonical category:

```
CATEGORY_VALIDATION_BUDGET_EXHAUSTED = "validation_budget_exhausted"
```

It joins `INCONCLUSIVE_CATEGORIES` and **nothing else**. It is deliberately not
also spelled `validation_timeout`: one vocabulary, no synonym for a reader to
map back. `budget_exhausted_info(timeout_seconds)` builds the one classifier
payload every timeout site returns, so the category, reason and hint cannot
drift between the four call sites.

`classify_validation_output` now takes `timed_out` and `timeout_seconds`, and
settles the budget **first, above every taxonomy branch**. Both runners also
write a fixed marker (`validation budget exhausted`) into their output, and
`detect_validation_budget_exhausted` reads it — defence in depth, so a caller
that drops the flag still cannot launder a budget into a test failure.

### What follows for free

Because the new category is inconclusive and never executed-failure evidence,
every existing shared predicate refuses it without a single downstream category
list being copied or edited:

| consumer | predicate | result |
|---|---|---|
| `core.control_engine` grounding | `is_executed_failure_evidence` | not a genuine failure |
| `core.pipeline` review-skip | `is_executed_failure_evidence` | no grounded fast path |
| `core.pipeline` compiler-grounded fix | `is_compiler_grounded_category` | false |
| `core.executor` | `is_inconclusive_category` | phase `validation_environment_failed` |
| `core.self_correct_loop` | that phase | stops instead of re-prompting |
| `core.candidate_sandbox_validation` | inherited `validation_outcome` | `inconclusive`, `approval_ready=False` |
| `core.execution_outcome_telemetry` | inherited `validation_outcome` | `final_validation_outcome=inconclusive` |

### A timeout is an *attempted* validation

§3, asserted directly in
`test_timeout_is_not_represented_as_validation_not_run`:

```
command_selected  = True
command_attempted = True
command_completed = False        # exit_code is None
timed_out         = True
outcome           = inconclusive
```

It is never `validation not run`. The command did run; it did not finish.

### The budget itself is unchanged

The global default stays **30 s** (`test_default_validation_budget_was_not_raised`
pins both runner signatures). The pre-existing explicit override —
`run_validation_command_detailed(timeout=…)` and
`SafeValidationCommand.timeout_sec` — is preserved, and no second timeout
configuration system was introduced. Trading false semantics for runaway
weak-machine cost would have been a worse bargain than the one this phase makes.

---

## Defect B — stale Python bytecode

CPython accepts a cached `.pyc` when two numbers in its header match the
source: **size in bytes** and **mtime truncated to whole seconds**. A same-size
patch inside one timestamp second satisfies both — which is exactly the shape
of this project's patches:

```python
return a - b        # baseline, imported once, cached
return a + b        # same-size replacement, same second
```

Reproduced on CPython 3.14 (`test_fixture_really_reproduces_the_stale_pyc_defect`):
`return "A"` → same-size `return "B"` with the original mtime restored, and the
interpreter kept printing `A`.

### `-B` does not fix it

§19 warned not to assume it; it was measured rather than assumed.
`test_dont_write_bytecode_does_not_fix_stale_reads` runs the reproduction under
both `-B` and `PYTHONDONTWRITEBYTECODE=1` and still observes `"A"`. They
suppress *writes*. The stale file is already on disk and is still *read*.

### The fix: an ephemeral cache location, not a deletion

`core/validation_bytecode_cache.py` gives each validation execution a **fresh,
empty temp directory** as `PYTHONPYCACHEPREFIX`. `sys.pycache_prefix` redirects
the whole cache — reads included — into a mirror tree at that path. An empty
tree has nothing in it to be stale, so every module the run imports is compiled
from the bytes that are on disk right now.

The repository's own `__pycache__` is **not read, not trusted, and not
deleted** — it is simply not consulted. That is the whole difference between
this and `rm -rf` over somebody's working tree.

| requirement | how |
|---|---|
| repository `__pycache__` not trusted | prefix redirects reads elsewhere |
| repository `__pycache__` not deleted | never touched; asserted by test |
| validation bytecode outside the repo | `tempfile.mkdtemp` under the system temp root |
| cleanup best-effort | `shutil.rmtree(ignore_errors=True)` in a `finally` |
| cleanup cannot mutate the repository | ownership guard: name prefix **and** under temp root |
| no reuse of a stale source-state cache | a *fresh* directory per execution |
| zero repository traversal | the module never looks at the repository at all |

Applied through the existing environment construction in both runners
(`_build_scrubbed_env`, `_validation_command_env`) and set **last**, over
anything the parent environment or a caller supplied — an inherited
`PYTHONPYCACHEPREFIX` pointing at an older source state is precisely the state
being defended against. Command safety is not bypassed: the argv screen,
allowlist and secret scrub are untouched.

### Non-Python validation

Unchanged. `PYTHONPYCACHEPREFIX` is inert for `go`, `cargo`, `node`, `dotnet`
and `g++`, which is why the freshness mechanism needs no per-language branch —
the narrowest implementation, exactly as §21 permits. No language's command
selection was altered.

### Cost

A fresh prefix means the stdlib and the project are compiled once per
validation invocation. Measured on this repository's import set: ~0.2 s warm
vs ~0.6–0.7 s cold, i.e. **~0.4–0.5 s per validation execution**. Correctness
is the invariant; the cost is bounded, and it is recorded here rather than
hidden.

---

## Files changed

| file | change |
|---|---|
| `core/validation_outcome.py` | `validation_budget_exhausted` category, `is_validation_budget_exhausted`, `budget_exhausted_info` |
| `core/validation_bytecode_cache.py` | **new** — the whole freshness mechanism |
| `core/validation_execution.py` | budget marker; `timeout_sec` + `python_bytecode_cache_isolated` on the result; fresh cache per run |
| `core/validator.py` | `timed_out`/`timeout_seconds` on `ValidationRun` and the classifier; budget branch first; fresh cache per run |
| `core/preflight.py` | threads the flag; reports `timed_out`, `timeout_seconds`, `validation_budget_exhausted`, `python_bytecode_cache_isolated` |
| `core/executor.py` | captures the budget fact from either runner; budget outranks the taxonomy |
| `core/self_correct_loop.py` | comment only — the stop condition already covered it |
| `core/run_lifecycle.py` | reads the typed `validation_timed_out` field |
| `core/post_run_reconciliation_shadow.py` | carries it into the receipt producer |
| `patching/patch_plan_executor.py` | both branches; adds `validation_timed_out`, `validation_timeout_seconds`, `python_bytecode_cache_isolated` |
| `scripts/run_patch_proposal_queue.py` | freshness only — see below |
| `tests/test_validation_timeout_and_bytecode_freshness.py` | **new** — 50 tests |
| `tests/test_post_run_reconciliation_shadow.py` | traversal counter bucketing made precise (see below) |

### The worker-proposal queue runner

`core.worker_runs` reaches
`scripts.run_patch_proposal_queue._run_validation_command` for real worker
proposals, validating in a temp clone that carries the source repository's
`__pycache__` with it — so §17 applies to it, and it now takes the same fresh
`PYTHONPYCACHEPREFIX`, held for the whole multi-segment run and released on
every exit path.

Its *timeout* vocabulary was deliberately left alone: it already reports a
stopped segment as its own error with `validation_ok=false` and never produces
a classifier category, so there was nothing to launder there.

### The one existing test that changed, and why

`test_the_shadow_adds_no_repository_membership_traversal` counted *any*
directory enumeration outside `.agent/` as a repository traversal. On Windows
`shutil.rmtree` walks the directory it removes, so cleaning up our own temp
cache registered as a repository walk. The counter now buckets that path
separately — the same exception, on the same grounds, that the `.agent`
artifact bundle already had. The claim is unchanged and, if anything, sharper:
the test now asserts the extra enumeration is under the temp cache prefix and
that enabling the shadow does not add one.

---

## Projections

**CHECK.LIVE.** `live_validation_result` already accepted `timed_out` and
already mapped it onto `RECEIPT_TIMED_OUT`, which is in CHECK.1's frozen
vocabulary and is already a *failing* receipt result. The fact simply had no
way to reach it. `validation_inconclusive` stays true alongside it, so the
worker's declared action remains `not_run`. CHECK.1 is not redesigned, not
promoted, and its vocabulary is not extended.

**EXEC.AUTH.** `final_validation_outcome` already accepted
`VALIDATION_INCONCLUSIVE`; a post-patch timeout now reports it truthfully.
Authorization semantics are untouched. The full telemetry for an authorized
grounded-defect run whose post-patch validation times out:

```
execution_authorized     = True
execution_attempted      = True
mutation_observed        = True
final_validation_outcome = inconclusive
rollback_performed       = True
application_status       = rolled_back
patch_applied            = False
final_repository_changed = False
```

**Sandbox (OPS.PATCH.2).** A candidate whose sandbox validation times out is
`inconclusive` — never `failed`, never `passed` — and `approval_ready` is
`False`. The real repository is untouched.

---

## Deltas

| | |
|---|---|
| model calls added | **0** |
| network calls added | **0** |
| repository traversal added | **0** |
| repository cache mutation | **0** — nothing deleted, nothing written into the repo |
| execution/write authority change | **none** |
| global timeout change | **none** (still 30 s) |
| test-selection change | **none** |
| retrieval / indexing change | **none** |
| `_classify_indent` | deliberately still broken — it is the live retrieval target |

Historical artifacts recording `test_failure` for past timeouts remain readable
and were not rewritten. New results use the truthful typed semantics.

---

## Known limitations

1. **Cold-compile cost.** ~0.4–0.5 s per validation execution, as measured
   above. The trade is correctness for a bounded constant.
2. **The 8,944-test cost problem is untouched.** A 30 s budget still cannot run
   this suite; it now says so honestly instead of inventing a verdict. Budget
   scheduling and targeted validation are a separate optimisation phase, and
   §31 explicitly kept them out of this one.
3. **`.pytest_cache` is a different thing** and was not redesigned. This phase
   is about executed Python bytecode.
4. **Registry schema limitation**, unchanged from OPS.PATCH.1 / OPS.VALIDATE.1:
   `automation_level` has no value meaning "human-authored production bug fix",
   so `LOCAL_1_PREPARE` remains the closest honest value and
   `writes_real_repo=true` carries the fact that matters.
5. **Pre-existing suite failures were not touched.** 50 tests failed before this
   phase (registry/picker phase-advance assertions, plus
   `test_context_selection_contract`); they fail for reasons unrelated to
   validation and are out of scope here.

## Readiness for retrieval work

Retrieval work was deliberately not begun. What it inherits: a baseline
validation that can now say *"the budget ran out"* instead of *"the tests
failed"*, which is the precondition for measuring whether a retrieval change
helped — previously a slow run and a broken run were indistinguishable in the
telemetry. `_classify_indent` remains a live dogfood bug for that phase to
target.
