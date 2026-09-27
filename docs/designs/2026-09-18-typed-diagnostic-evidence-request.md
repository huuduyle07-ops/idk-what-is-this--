# PREFLIGHT.REQUEST.1 — Typed Diagnostic Evidence Request & Java Compile Adapter

Date: 2026-09-18
Residual: recorded by CONTROL.BOOTSTRAP.1 ("Static reading can only suspect a
compiler defect: the Java static-context problem is recorded as a hypothesis
plus a `compile_evidence` gap")
Track: CONTROL (prerequisite CONTROL.BOOTSTRAP.1); `PREFLIGHT` is a new ID
namespace inside that track, not a new track.

## Scope and invariant

CONTROL.BOOTSTRAP.1 ends with a schema-valid CONTROL whose `evidence_gaps`
name semantic needs over grounded evidence targets. This phase owns exactly
one further transition:

```text
typed evidence gap
  -> EvidenceNeed (kind, targets, language, provenance, CONTROL + repository binding)
  -> deterministic policy (supported? authorized? budget? language? adapter?)
  -> the harness-owned JavaCompileDiagnosticAdapter (bounded, isolated)
  -> DiagnosticEvidenceReceipt (measured, provenance-bound, no authority)
  -> CONTROL's existing preflight_validation record
  -> the unchanged DEFECT.FACT / PATCH.BASIS reasoning (refresh_control_safety)
```

The model requests **what** evidence is needed. The harness alone decides
**how** it is measured. No text from CONTROL or a model becomes execution
authority, diagnostic capability is not mutation authority, and a measured
compiler failure is not patch, write or approval authority.

Not implemented here: arbitrary or model-provided command execution, Docker,
MCP or plugin work, a capability broker, repository discovery, graph / index /
embeddings, Maven / Gradle, patch-authoring changes, auto-apply, UX-05, UX-06,
T6 Round 11 and CRLF remediation.

## Measured entry state

Entry bytes are CONTROL.BOOTSTRAP.1's post-state (reconstructed by this
phase's reversal receipt). On the Java dogfood — `Twosum.java` and
`MainApp.java`, unrelated — a fresh Generate bootstraps a CONTROL with the
hypothesis `MainApp.java::main` (suspected static-context defect) and one gap
`{"need": "compile_evidence", "targets": ["MainApp.java", "Twosum.java"]}`.
`refresh_control_safety` then reports `defect_established=false`,
`patch_basis=unresolved`, `recommended_action=needs_grounding`, and every
downstream prompt is inspection-only (`auto_patch_candidate_allowed=false`).
Nothing measures the gap: the existing `core/preflight.py` has no Java command
and would be `no_validation_command` anyway (`test_pre_*` in
`tests/test_preflight_request1.py` replays the CONTROL.BOOTSTRAP.1 routes).

## The owner

`web/preflight_request.py` sits beside `web/control_bootstrap.py`, whose
evidence-gap vocabulary it imports rather than forks (`EVIDENCE_NEEDS`,
`EVIDENCE_GAP_FIELDS`, the direct-context bounds, `control_fingerprint`). It
imports no graph, index, retrieval, provider, validator or network module.

| Record | Holds |
| --- | --- |
| `EvidenceNeed` | `kind`, exact `targets`, `language` (derived lexically by the harness), `reason` (the gap's detail), `provenance` (`evidence_gaps[i]`), `control_sha256`, `repository_id`; frozen; no command, executable, argv, environment or script field |
| `PreflightScope` | canonical root, repository id, CONTROL fingerprint, the exact sources CONTROL.BOOTSTRAP.1 read (path, language, sha256, CTX.READ.1 receipt) |
| `PolicyDecision` | `admitted` or a typed rejection, with the adapter id the policy chose |
| `DiagnosticPlan` | one adapter, the union of admitted targets (each once), need identities, CONTROL and repository binding |
| `DiagnosticEvidenceReceipt` | kind, adapter id/version, tool/version, availability, attempted, outcome, per-target measurements, version probe, environment keys (names only), timings, warnings, evidence fingerprint, all-false authority |
| `PreflightRequestResult` | cycle status, the CONTROL that continues (or none), derivations, decisions, receipts, dedup references, freshness, timings |

Stage functions are separate and pure where they can be:
`derive_evidence_needs`, `decide_evidence_need`, `source_freshness`,
`JavaCompileDiagnosticAdapter.measure`, `parse_javac_diagnostics`,
`compile_evidence_handoff`; `run_preflight_request` orchestrates one cycle and
`preflight_bootstrapped_control` is the Generate seam.

## EvidenceNeed and policy

A gap is read as `{need, detail, targets}` only. Every other key (`command`,
`argv`, `executable`, `tool`, `adapter`, `env`, `script`, ...) is recorded by
name in `ignored_item_keys` and never read. Malformed gaps (not an object, a
non-text or empty need, missing / empty / non-text targets, non-text detail,
`evidence_gaps` not a list or over the 16-gap bound) are
`malformed_evidence_need` with the offending field.

Policy, in order, reading nothing and starting nothing:

1. **Supported kind.** Exactly one executable kind: `compile_evidence`.
   `test_evidence` / `runtime_evidence` → `unsupported_evidence_need`
   (`deferred`); `additional_source` / `user_clarification` →
   `not_a_diagnostic_measurement`; any other spelling (`shell_command`,
   `run_anything`, `preflight_validation`, `docker_exec`,
   `docker_container_status`, `mcp_health`, `plugin_connection`,
   `skill_requirement`, `COMPILE_EVIDENCE`, ...) → `unknown_evidence_kind`.
2. **Budget.** At most the direct-context bound (8 targets) → else
   `target_budget_exceeded`.
3. **Authorization.** Every target must be an evidence target of the scope,
   spelled exactly (no normalization, so no alias): `./MainApp.java`,
   `mainapp.java`, `../MainApp.java`, `Secret.java` → `unauthorized_target`,
   and the whole need is rejected before any read.
4. **Language.** The scope's language for every target must be one language
   with a registered adapter → else `language_unsupported`.
5. **Adapter.** `ADAPTER_REGISTRY[(kind, language)]` — a closed harness
   table, today `{("compile_evidence", "java"): "java_compile_diagnostic"}`.
   CONTROL can never name javac, ecj, Maven, Gradle or a container image.

## Repository and freshness binding

Before anything is read, the cycle checks that CONTROL is the one the scope
was built from (`control_fingerprint`), that its `repo_path` is the scope's
canonical root, that the root still canonicalizes to itself, that the
repository id derives from it, and that CONTROL's declared evidence targets
equal the scope's. Any mismatch is `preflight_binding_mismatch` with nothing
measured: repository A's CONTROL never runs against repository B's scope.

Freshness reuses CTX.READ.1: `verify_direct_read_receipt` on a fresh `lstat`
identity plus the exact content digest (read through a descriptor whose
identity must equal the `lstat`). It runs before measurement and again after
the compiler ran. A changed, deleted or replaced target is
`preflight_source_changed`: nothing is compiled from stale assumptions, and a
measurement taken while a source changed is recorded but never handed to
reasoning. The fresh Generate request stops with a typed answer.

## JavaCompileDiagnosticAdapter

**Availability.** `resolve_javac` searches absolute PATH directories only (no
working-directory lookup), accepts only real executables (`.exe`/`.com` on
Windows, never `.bat`/`.cmd`), and skips anything inside the repository. Then
one bounded `javac -version` probe. Absent → `tool_unavailable`
(`javac_not_found`); probe timeout → `diagnostic_timeout`
(`version_probe_timeout`); nothing is installed, downloaded or configured and
PATH is never modified.

**Deterministic command construction** (argv list, no shell, no string):

```text
<javac> -J-Duser.language=en -J-Duser.country=US -J-XX:-UsePerfData
        -J-Dstdout.encoding=UTF-8 -J-Dstderr.encoding=UTF-8
        -encoding UTF-8 -proc:none -implicit:none
        -sourcepath <isolated-empty> -classpath <isolated-empty>
        -d <isolated-output> -Xmaxerrs 100 -Xmaxwarns 100 <exact target>
```

The empty isolated source and class paths are load-bearing: measured with
javac's defaults, compiling `UsesMissing.java` silently read and compiled
`Missing.java` from the working directory. `-proc:none` runs no annotation
processor, so no repository code executes. A target that would read as an
option or argument file (`-x.java`, `@x.java`) or a `module-info.java` is
`diagnostic_inconclusive`, never passed to javac.

**Working directory.** The canonical repository root, so each exact
repository-relative target resolves where CONTROL.BOOTSTRAP.1 read it and
diagnostics print repository-relative paths. Nothing is searched from it (the
source and class paths are isolated) and nothing is written to it. The
version probe runs in the isolated directory.

**Compilation sandbox.** One `tempfile.mkdtemp` directory outside the
repository (verified; inside → `adapter_error`) holds the empty path, one
class-output directory per compile and the captured streams. It is removed on
every outcome with bounded retries; a failed removal is the operational warning
`isolated_output_cleanup_failed` and never changes the outcome. Repository
sources stay read-only; no `.class` file reaches the repository.

**Environment.** Only `PATH`, `SYSTEMROOT`, `SYSTEMDRIVE`, `WINDIR` are
inherited; `TEMP`/`TMP`/`TMPDIR` point at the isolated directory.
`JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, `JDK_JAVA_OPTIONS`, `JDK_JAVAC_OPTIONS`,
`CLASSPATH`, API keys and every other variable stay behind (measured: leaked,
`JDK_JAVAC_OPTIONS=-Xmaxerrs 1` truncates diagnostics and `JAVA_TOOL_OPTIONS`
prints "Picked up"). The receipt records variable names, never values.

**Bounds.** Process timeout 60 s (a timeout is `diagnostic_timeout`, never
`compile_failed`; the launcher tree is killed), version probe 30 s, cycle
budget 180 s (unattempted targets are `diagnostic_inconclusive`,
`cycle_budget_exhausted`), 64 KiB captured per stream, 8,000 characters of
normalized text and 32 diagnostics per target, and the direct-context target
bound. The Oracle `javapath` launcher ends its compiler child when killed
(measured); `taskkill /T` (Windows) or a process-group kill (POSIX) covers
launchers that do not.

**Independent / grouped strategy.** Each target is compiled on its own (the
dogfood files are unrelated). A target whose only errors are unresolved names
(`cannot find symbol`, `package … does not exist`, `cannot access …`) is
`diagnostic_inconclusive` (`unresolved_reference`) — the name may live outside
the explicit targets — and gets at most one grouped compile with the explicit
targets that compiled: resolved → `compile_passed` (`grouped`), still
unresolved → `unresolved_reference_outside_explicit_targets`. No dependency
tree is discovered and no repository file outside the explicit targets is read.

## Receipt and outcomes

Closed vocabulary: `compile_passed`, `compile_failed`, `tool_unavailable`,
`diagnostic_timeout`, `diagnostic_inconclusive`, `adapter_error`. Per target:
path, source digest, attempted, outcome and reason, compile mode and group,
exit status, timeout flag, elapsed time, structured diagnostics
(file, line, 1-based caret column, severity, message) beside bounded raw text,
bounded stdout/stderr (byte totals, truncation, digest) and the normalized
invocation. Output is decoded as UTF-8, CRLF-normalized, host paths replaced
(repository root → relative, isolated directory → placeholders) and credential
redacted. The evidence fingerprint covers what was measured, never timings.

* `compile_passed` proves only that the target compiled under this invocation
  and environment — not behavior, tests or correctness.
* `compile_failed` proves only that compilation failed under it — it does not
  decide which change is correct.
* `diagnostic_inconclusive` covers unresolved external names, compiler failures
  without a source diagnostic, unsupported target spellings and exhausted
  budgets; `tool_unavailable` is evidence about the environment only.

## Handoff and reassessment

`compile_evidence_handoff` renders the receipt as CONTROL's existing
`preflight_validation` record, the field `refresh_control_safety` already
reads: `compile_failed` → `ran=true, ok=false, outcome=failed,
category=build_error`, the failing targets' own normalized output (javac's
exact per-file output for an independent compile; for a grouped compile only
the diagnostic blocks attributed to that target, so another member's file name
can never let the existing output-path binding attach the failure to it) and
typed `compiler_error` locations; all passed → `outcome=passed, category=passed`;
otherwise `inconclusive` with an existing inconclusive category
(`validation_tool_unavailable`, `validation_budget_exhausted`,
`validation_environment`). A passing target is summarized, never named in the
output a defect could bind to. Provenance fields (`evidence_source`,
`measured`, `adapter`, `tool_version`, `receipt_fingerprint`, `control_sha256`,
`semantics`, all-false `authority`) keep measured evidence distinct from
hypotheses, user claims and prior CONTROL text. The continuing CONTROL is the
bootstrapped CONTROL plus that one field, re-parsed by the frozen
CONTROL.FRESH.1 validator; hypotheses and the route are untouched.

No DEFECT.FACT / PATCH.BASIS rule changed. The existing binding grounds
`MainApp.java::main` as `grounded_defect` (`executed_validation_failure`,
`direct_location`, line 9) because a compiler-kind location names its file;
`Twosum.java` gets no defect; write, apply, execution and approval authority
stay false. Final validation is untouched: preflight asks "is there a
compilation defect now?", candidate validation still asks "did the candidate
fix it?".

## Generate seam

Each Generate route's fresh branch calls `preflight_bootstrapped_control`
once after CONTROL.BOOTSTRAP.1 succeeds. No evidence gap → the answer is
byte-for-byte CONTROL.BOOTSTRAP.1's. Gaps → the answer carries
`preflight_request` (the cycle receipt) beside `control_bootstrap`; a
non-executable need only reports its policy decision and the pipeline input is
unchanged. `preflight_source_changed` stops with HTTP 200 JSON (`error`,
`code`, `reason`, `control_context: fresh_bootstrap_required`, both receipts).
Continuation (prior CONTROL) never runs preflight. The downstream model reply
is never read for new needs: one cycle per request.

## Java dogfood (measured, javac 26.0.2.1, Windows 11)

| | PRE (CONTROL.BOOTSTRAP.1) | POST (PREFLIGHT.REQUEST.1) |
| --- | --- | --- |
| Twosum.java | unmeasured | `compile_passed`, exit 0, no diagnostics |
| MainApp.java | unmeasured | `compile_failed`, exit 1: 9:9 non-static method `increment()`…, 10:42 non-static variable `counter`… |
| defect facts | none established, `needs_grounding` | `MainApp.java::main` grounded (`direct_location`, line 9); Twosum none |
| downstream prompt | inspection-only | localized to `MainApp.java::main` with the measured preflight |
| patch candidate | null | may still be null (the goal is evidence, not a forced patch) |
| repository | unchanged | unchanged, no `.class` files |

Harness overhead ≈ 7 ms against ≈ 1.4 s of process time (probe ≈ 0.3 s, two
compiles ≈ 1.1 s); exact numbers are in the completion receipt.

## CRLF

A CRLF `MainApp.java` is compiled as-is and fails identically; preflight never
rewrites or normalizes source. Downstream, `extract_symbol_snippet` reads in
text mode, so the grounded snippet is LF and `refresh_control_safety` and the
Generate CONTROL gate both accept a verbatim quote of it: no CRLF blocker is
reached inside Generate. CRLF quote remediation beyond that stays deferred.

## Future seams (not implemented)

* A `docker_container_status` adapter would be one more `ADAPTER_REGISTRY`
  entry; model-facing authority would not change. Today it is
  `unsupported_evidence_need` and starts no process.
* `mcp_health`, `plugin_connection`, `skill_requirement`: unknown kinds; this
  phase connects, installs and authorizes nothing.
* **CAPABILITY.BROKER.1** (deferred) owns adapter/provider availability,
  MCP/plugin/skill health, human-gated connection or installation and
  permission-scoped operations.
* Build-system-aware compilation (Maven/Gradle, source roots) is a later
  adapter; unresolved names stay `diagnostic_inconclusive` until then.

## Unchanged semantics

| Area | Delta |
| --- | --- |
| CONTROL.BOOTSTRAP.1 owner, CONTROL.FRESH.1 validator | 0 (byte-identical) |
| DEFECT.FACT / PATCH.BASIS / OPS.VALIDATE vocabulary (`core/control_engine.py`, `core/patch_basis.py`, `core/validation_outcome.py`) | 0 |
| Existing preflight and final validation (`core/preflight.py`, `core/validator.py`, candidate verification) | 0 |
| Page, WorkbenchState, UX.STATE.1, UX.CONTEXT.1 | 0 |
| Track A, SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, AUTH.DREAM.1, DATA.ROLLBACK.1, AUTH.WEB.1, AUTH.WEB.READ.1 | 0 |
| Continuation and CONTROLs without evidence gaps | 0 |
| Graph / index / embeddings / repository traversal / network / model calls for diagnostics | 0 |

`tests/fixtures/preflight_request1_frozen_boundaries.json` pins the unchanged
files; `tests/fixtures/preflight_request1_reversal.json` reconstructs every
changed file's CONTROL.BOOTSTRAP.1-era bytes and `before_control_bootstrap1`
undoes this phase first, so every older pin keeps checking history.
CONTROL.BOOTSTRAP.1's raw live-file pins and its subprocess-denying Java route
test were re-homed onto its own post-state; its assertions are unchanged.
AUTH.WEB.1's frozen-manifest check hashed `core/phase_registry.py` raw (no phase
since had touched it); it now reads AUTH.WEB.1's post-state through
`before_auth_web_read1`, like its other definition pins.

## Tests

`tests/test_preflight_request1.py`: the need contract (bounded frozen fields,
shared vocabulary, unsupported kinds including future Docker/MCP spellings,
duplicates, unauthorized and aliased targets, wrong language, malformed gaps,
the gap-key read set, command/adapter fields, binding mismatch), the adapter
with real javac (availability probe, unavailable and repository-internal
javac, pass, fail, timeouts, bounded streams, spaced paths, argv shape,
minimal environment, implicit-source isolation, grouped and outside
dependencies, cleanup and cleanup failure, source changed before and during
compilation), static no-shell regressions, the Java dogfood without traversal
or mutation, receipt determinism and provenance, reassessment through the
unchanged PATCH.BASIS, pass-not-promoted, distinguishability, final-validation
separation, CRLF, both Generate routes (POST, PRE on CONTROL.BOOTSTRAP.1's
routes, no-gap and continuation equivalence, non-executable needs, source
changed, one cycle), performance and governance.

## Explicit answers

| Question | Answer |
| --- | --- |
| Can the model execute arbitrary command text? | No. Gap keys other than need/detail/targets are never read; the only launch site takes an argv the adapter built. |
| Can the model choose javac/Gradle/Maven itself? | No. `ADAPTER_REGISTRY` is a closed harness table keyed by (kind, language). |
| Can preflight compile a target outside current evidence scope? | No. Exact evidence-target spelling only; the whole need is rejected before any read. |
| Does javac output count as measured evidence? | Yes, as a provenance-bound receipt and the `preflight_validation` record. |
| Does javac failure automatically authorize a patch? | No. It may ground a defect through the unchanged PATCH.BASIS rules; every authority flag stays false. |
| Does javac success prove behavioral correctness? | No. It proves only that the target compiled under the recorded invocation. |
| Are .class files written into the repository? | No. Output goes to an isolated temporary directory outside the repository, removed afterwards. |
| Is repository-wide discovery performed? | No. Empty isolated source/class paths; only the exact targets are read. |
| Is any graph/index/embedding work performed? | No. |
| Can Docker/MCP/plugin capabilities execute in this phase? | No. They are unsupported kinds; CAPABILITY.BROKER.1 is deferred. |
| Were patch/write authority semantics changed? | No. |
| Were live provider calls added for diagnostics? | No. Zero model calls; tests use stub authors and local javac only. |
