# OPS.VALIDATE.1 — Real Repository Validation Recovery

**Date:** 2026-08-31
**Track:** OPS · **Prerequisite:** OPS.PATCH.1 · **Status:** complete
**Kind:** live production fix — deterministic, no model call, no network, not report-only

---

## 1. What broke

The 2026-08-30 black-box field test reproduced four failures on the real
preflight/validation path.

| # | Repository | What production did | Why it is wrong |
|---|---|---|---|
| A | Normal Python repo with tests | emitted `pytest` | The active virtualenv owned pytest; PATH did not. `'pytest' is not recognized`. C.A.T.T.U.S could not validate its own repository. |
| B | Flat `solution.py` + `test_solution.py` | fell through to `python -m unittest` | No `tests/`, no `pytest.ini` — so pytest-style functions were never collected. |
| C | `Ran 0 tests` / `NO TESTS RAN` | classified `test_failure` | No test executed. That is not evidence the patch failed tests. |
| D | Large TypeScript repo | `no_validation_command` + C#/Python advice | `detect_repo_language` returned `typescript`; the detector had no TypeScript branch. |

All four share one root cause: **the path answered one question where there are
three.**

## 2. The three questions

1. *Which command is appropriate for this repository?*
2. *Did validation actually execute meaningful checks?*
3. *If checks executed, did they pass or fail?*

`core/validation_outcome.py` is the vocabulary that keeps them apart:

```
passed         checks ran and passed
failed         checks ran and failed
inconclusive   validation established neither
```

`inconclusive` covers `no_validation_command`, `no_tests_collected`,
`validation_tool_unavailable`, and the pre-existing `missing_toolchain`,
`validation_environment` and `unsafe_validation_command`.

**The category decides the outcome, not the boolean.** A runner that exits `0`
having collected nothing is inconclusive; a runner that could not start is
inconclusive.

There is no score, weight or confidence anywhere in this. An inconclusive
validation is not a weak failure — it is the absence of a result.

### Boolean compatibility

Every existing consumer still reads `ok`, and **only a genuine pass sets it
true**. An inconclusive run that executed is `ok=False`, which keeps automatic
patch safety exactly as conservative as it was: an unvalidated patch is still
not accepted and still rolls back. The categorical reason survives structurally
as `outcome` / `category` / `validation_outcome`, so downstream code can tell
"failed" from "inconclusive" even though the boolean cannot.

## 3. The path, and where each fix lands

```
detect_repo_language
      ↓
detect_default_preflight_command / get_default_validation_command   ← §4, §7
      ↓
explicit `Validation command:` override            (unchanged precedence)
      ↓
validation_command_safety_issue                    (unchanged, still refuses)
      ↓
run_validation_command_detailed → ValidationRun(ok, output, exit_code)  ← §5
      ↓
detect_no_tests_collected / classify_validation_output              ← §6
      ↓
run_preflight_validation → {ran, ok, outcome, category, locations}   ← §3
      ↓
CONTROL prompt · review-skip gate · compiler-grounded gate           ← §8
      ↓
apply → post-patch validation → rollback                             ← §9
      ↓
CHECK.LIVE receipt / worker report                                   ← §10
```

## 4. Python selection

`python -m pytest`, never bare `pytest`.

pytest is selected on any bounded root marker: `pytest.ini`, `conftest.py`,
`[tool.pytest` in `pyproject.toml`, `[tool:pytest]` in `setup.cfg`, a `tests/`
directory, or a root-level `test_*.py` / `*_test.py`. Otherwise the existing
order is unchanged: `test.py` → `main.py` → `app.py` import check → `python -m
unittest`.

Absence of `pytest.ini` is **not** proof a repository uses unittest — that is
exactly what defect B was. unittest is selected when no pytest marker exists,
which is a positive fact, not a fallback.

Every check reads named root files, one non-recursive glob per pattern, or one
small config read. No tree walk, no graph, no embedding, no DB.

## 5. Interpreter strategy

The emitted text is `python -m pytest`. The legacy shell runner then executes a
plain `python …` command **as argv with `sys.executable` in front**, rather than
handing it to the shell.

Why not quote `sys.executable` into the shell string: with `cmd /c`, a quoted
executable beside a quoted argument (`"C:\…\python.exe" -c "import app"`) has
more than two quote characters, so cmd strips the first and the last and mangles
the command. Running argv with `shell=False` avoids the question entirely.

Commands containing shell syntax (`&&`, `|`, `$(`, backticks, redirects) or a
backslash that POSIX splitting would eat still go to the shell exactly as
before. The safe-argv runner already mapped `python` to `sys.executable`.

**No fallback chain.** A bare global `pytest` is never attempted afterwards, and
nothing is ever installed. One deterministic representation, one environment.

## 6. Did anything run?

`ValidationRun` carries the exit code, which is the fact the classifier could
never see.

* **pytest exit code 5** is authoritative for "no tests were collected".
* Output markers — `no tests ran`, `no tests collected`, `collected 0 items`,
  unittest's `Ran 0 tests` — are consulted only when the exit code does not
  already say the run failed for another reason. So a collection *error* at
  pytest exit 2, which also prints `collected 0 items`, stays the import or
  syntax error it really is.
* `No module named pytest` is `validation_tool_unavailable`; `No module named
  requests` remains `import_error`. Only the **runner's** absence is
  infrastructure — a module the repository itself imports is a fact about the
  repository.
* `is not recognized as an internal or external command`, `command not found`,
  `safe validation execution error` and npm's `Missing script:` are likewise
  tool-unavailable.

Zero tests is checked on the **passing** branch too, through a dedicated
`detect_no_tests_collected` rather than the full taxonomy — because a *passing*
pytest run also prints `collected N items`, and running the failure taxonomy
over successful output would misread it.

## 7. TypeScript

Only a script the repository **already declares** is ever run, in the
deterministic order:

```
test → typecheck → check → build
```

`test` first because it is the strongest evidence a patch is correct, and
because it is the script the existing JavaScript branch already selected.
`build` last because compiling is the weakest of the four.

The package manager comes from the repository's own root lockfile:
`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `package-lock.json` → npm, else
npm. `pnpm` and `yarn` joined the safe-argv allowlist for the same reason `npm`
is on it.

Only `<manager> run <script>` is emitted. **Never** `install`, never `npx`. A
`tsconfig.json` repository declaring no usable script returns a
TypeScript-specific `no_validation_command` whose hint names package.json
scripts — not `.csproj` files, not Python tests.

JavaScript detection is byte-for-byte unchanged.

## 8. Grounding: what may still ground a diagnosis

The review-skip gate and the compiler-grounded gate in `core/pipeline.py` now
ask `is_executed_failure_evidence` / `is_compiler_grounded_category` instead of
carrying private category lists — lists that had come to include
`missing_toolchain` and `validation_environment`.

| Case | Grounding |
|---|---|
| pytest ran, assertion failed | **eligible** — the fast path that worked in the 27-second calc.py field test |
| syntax / compiler error | **eligible** |
| pytest could not run | **not eligible** |
| zero tests collected | **not eligible** |

An inconclusive preflight also stops contributing `locations`: a validation that
established nothing has no defect locations to give, and handing CONTROL
file:line pairs scraped out of a toolchain error would manufacture exactly the
false grounding this phase exists to remove.

`import_error` and `missing_dependency` stay grounding, because a module the
repository's own code imports is a fact about that code.

## 9. Apply, rollback, byte fidelity

An inconclusive validation is **not** accepted. Rollback policy is unchanged, so
an unvalidated patch still rolls back — and OPS.PATCH.1's guarantee means it
rolls back to the exact original bytes, CRLF files included. That is re-asserted
here under the new outcome.

What changed is only the sentence: "validation was inconclusive: it established
neither a pass nor a failure", never "validation failed" and never "test
failure", for a run in which no test existed.

## 10. Receipts

The live producers gained an `inconclusive` input:

* CHECK.1 receipt result → `errored` instead of `failed`
* worker declared validation action → `not_run` instead of `failed`

Both are existing values in CHECK.1's **frozen** vocabulary, and `errored` is
still a failing receipt result, so a required expectation is still not
discharged by one. The receipt merely stops claiming a red test suite for a run
with no tests. CHECK.1, CHECK.2, CHECK.LIVE.1/1B and WORKER.DECL were not
promoted, redesigned or made authoritative; the shadow observer reads the typed
outcome the apply path recorded rather than re-classifying any output.

## 11. The benchmark blind spot, closed executably

The 54 benchmark cases hardcode `validation_command`, so default detection was
never exercised by any of them. A case may now omit it by setting
`auto_detect_validation: true`, which routes selection through the **shipped**
detector. Omitting it without the opt-in is still a schema error, and a case may
not set both — a typo cannot become silent auto-detection.

The existing 54 cases were not rewritten and none was added, so the benchmark
corpus and its model-call cost are unchanged. Two deterministic integration
cases — flat Python pytest, and a TypeScript package-script repository, both
with no `validation_command` — select and execute through the production entry
points with no provider call.

## 12. Deltas

| Dimension | Delta |
|---|---|
| Model calls | 0 |
| Network calls | 0 |
| Dependency installation | 0 — forbidden by construction |
| Repository traversal | 0 added; the pre-existing C#/Go/Rust `rglob` count is pinned by test |
| Patch authority | 0 — a detected command grants nothing |
| Command retry loops | 0 — selection is deterministic from repository evidence |
| Confidence scores | 0 — categorical facts only |

CONTROL localization, patch target selection, write authority, CTX.PATCH,
CTX.APPLY, human approval and `AUTO_PATCH_ENABLED` are untouched.

## 13. Known limitations

* **`unknown` + nonzero stays `failed`.** A command that fails for a reason the
  taxonomy cannot name is reported as failed with category `unknown`. It does
  not ground anything (it is in neither grounding set), but it is not called
  inconclusive either. Broadening that would need a subprocess-failure taxonomy
  this phase deliberately did not build.
* **Timeouts are still `unknown`.** A validation that timed out is reported as
  failed/unknown rather than inconclusive.
* **Tool availability is discovered at execution, not selection.** A repository
  whose lockfile names a package manager that is not installed still gets the
  command; the run then classifies as tool-unavailable. That is deliberate — a
  PATH probe in the detector would be a second source of truth.
* **No node_modules check.** A declared script whose tool is missing fails at
  execution and is inconclusive. Nothing is installed to make it pass.

## 14. Follow-ups recorded, not fixed here

* **CLI.RUNTIME.1** — the interactive CLI's single-line input makes the
  prose-embedded `Validation command:` directive awkward or impossible to use
  correctly. A future fix should prefer a typed CLI option or a separate field
  over more regex parsing in prose.
* `cli/interactive.py` `create_session` DB/session fallback — a separate
  runtime/CLI phase.

Explicitly **not** started here: CONTROL.SAFETY.LIVE.1, WAITER.LIVE.1,
retrieval/indexing redesign, `code_dna` indentation, Phantom Limb,
WORKER.DECL.2B, and any change to OPS.PATCH.1's byte-preservation semantics.
