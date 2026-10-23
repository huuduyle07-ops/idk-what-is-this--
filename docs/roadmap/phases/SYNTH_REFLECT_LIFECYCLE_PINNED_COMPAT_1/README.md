# SYNTH.REFLECT.LIFECYCLE.PINNED.COMPAT.1

Pure compatibility audit. Outcome: `REFLECTION_PINNED_REQUIRES_ADDITIVE_ADAPTER`.

Start with [the report](SYNTH_REFLECT_LIFECYCLE_PINNED_COMPAT_1_REPORT.md).
The [primitive/admission trace](primitive_admission_trace.md) and
[lifecycle trace](reflection_lifecycle_trace.md) carry source evidence.
[Focused tests](../../../../tests/test_synthetic_reflection_lifecycle_pinned_compat.py)
use source/AST proof and inert pinned rejection data only.

Reproduce with `python -B validate_pure_audit.py --mode MODE --scratch-root PATH`
from this directory or with its full repository-relative path from the repo root.
PATH must be an existing writable directory outside the repository. Modes are
`baseline`, `registry_baseline`, `frozen`, `focused`, `registry_after`, `benchmark`,
and `finalize`. Original baselines are never overwritten. Validation disables
bytecode/plugin/cache writes and denies production/isolated capability issuance
and transitions, execution/proof entry points, process/network and repo writes.
Existing config's no-op mkdir requests and urllib3's IPv6 probe are elided.
Result artifacts are explicitly written after the guard closes.

Do not run full frozen reflection proof suites, isolated pinned transition tests
or any owner `verify()` for this audit. No new capability schema or adapter exists.
