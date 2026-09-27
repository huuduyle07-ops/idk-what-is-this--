# PATCH.BASIS.TARGET.1 — Structural Short-Identifier Target Source Grounding

Date: 2026-09-20
Residual: measured by the DOGFOOD.JAVA.1 audit (live Workbench replay of
`C:\Users\Admin\Documents\Code\Side quest\java`, 2026-09-19), whose first and
only blocker was `core/control_engine.py`'s `len(symbol_name) < 3` guard
dropping the grounded Java method `MainApp.java::m1`.
Track: CONTROL (prerequisite PREFLIGHT.REQUEST.1); `PATCH` is an existing ID
namespace inside that track, alongside PATCH.BASIS.LIVE.1.

## Scope and invariant

**Identifier length is not evidence.** A symbol spelled `m1`, `f` or `x` must
not be refused because its name is short. A short spelling must equally not
*gain* source grounding merely because the characters occur somewhere in the
file. Grounding must be structural.

This phase owns exactly one transition:

```text
already-grounded target (exact file + exact symbol, from existing provenance)
  -> the existing language-aware extractor (core/treesitter_parse)
  -> exactly one definition of that spelling, or refusal
  -> compatibility with the measured defect location, when one exists
  -> the unchanged extract_symbol_snippet source representation
  -> the unchanged _source_is_exactly_grounded / PATCH.BASIS machinery
```

Nothing else changes. The phase grants no authority, adds no model call, adds
no network call and performs no repository traversal.

## Measured entry state

Entry bytes are PREFLIGHT.REQUEST.1's post-state (reconstructed by this
phase's reversal receipt, `tests/fixtures/patch_basis_target1_reversal.json`).

DOGFOOD.JAVA.1 measured the chain working end to end until one guard:

```text
javac 26.0.2.1 -> 5 errors (lines 12, 20, 26, 28, 28)
  -> binder grounds MainApp.java::m1, direct_location, line 12
  -> build_patch_intent: len("m1") < 3  ->  target_file=None, source_snippet=""
  -> exact_source_grounded=false
  -> patch_basis=unresolved
  -> build_control_prompt takes the inspection-only branch; no candidate
```

Re-measured against the entry bytes of `core/control_engine.py`
(sha256 `a29d8db2…fa8e7`) on the real dogfood file:

| target | entry `target_file` | entry `target_symbol` |
| --- | --- | --- |
| `MainApp.java::m1` | `None` | `None` |
| `MainApp.java::MainApp` | `MainApp.java` | `main` |
| `svc.py::calculate_total` | `svc.py` | `calculate_total` |

The middle row matters: `MainApp` equals the file stem, so the *pre-existing*
`infer_symbol_from_query_in_file` branch rewrites it to `main` before any
grounding runs. That behaviour is out of scope and is pinned unchanged.

## The old rule and the new rule

**Old.** `if not symbol_name or len(symbol_name) < 3: return <no target>`.
An arbitrary threshold, shared by every language, with no structural content.

**New.** The gate consults the structural extractor and refuses only when that
extractor *positively contradicts* the target:

| status | meaning | gate |
| --- | --- | --- |
| `structurally_resolved` | exactly one definition, location-compatible | accept |
| `not_found` | extractor available, zero definitions of that spelling | refuse |
| `ambiguous` | more than one plausible definition, nothing disambiguates | refuse |
| `location_mismatch` | resolves, but the measured defect owns another definition | refuse |
| `file_target` | the spelling names the file, not a symbol | unchanged (§10) |
| `structure_unavailable` | no extractor for the language, or a legacy qualified spelling | unchanged (§23) |

`structure_unavailable` preserves prior behaviour precisely because the
extractor proves nothing either way there; such a target still acquires no
snippet, so `_source_is_exactly_grounded` keeps failing it closed downstream.

## Structural authority

`core/treesitter_parse.py` gains one additive function, `structural_definitions`.
Parsing semantics are untouched: the definitions it returns are exactly the
symbols the existing walker already emits, with their existing kinds, names and
byte spans. It adds only what the grounding decision needs and
`parse_code_with_treesitter` cannot express:

- **availability** — an empty `symbols` list currently means both "no parser for
  this language" and "this file declares nothing"; only the second may refuse a
  target;
- **line range** — 1-based `start_line` / `end_line` derived from the same byte
  buffer tree-sitter indexed, so a measured diagnostic line can be tested for
  structural ownership.

Because the same extractor builds the graph (`graph/builder.py`) that produces
CONTROL's hypotheses, a legitimate target is a tree-sitter symbol *by
provenance*. `not_found` therefore means the extractor genuinely disagrees.

## Ambiguity, overloads and location binding

Never "first match in file order wins". With no location, two definitions of the
same spelling are `ambiguous`. With a location, a definition structurally owns
the line when `start_line <= line <= end_line`; exactly one owner resolves, and
overlapping owners (nested definitions) stay ambiguous. A location naming a
*different* file is not evidence about this file and is ignored.

`MainApp.java::m1` spans lines 7–13 and the measured diagnostic is line 12, so
it resolves. The same spelling against line 20 — inside `m2` — is
`location_mismatch` and refuses to bind.

## What this phase is not

- Not a new grounding algorithm for normal identifiers: every previously valid
  `>=3`-character symbol is pinned behaviourally unchanged.
- Not a widening of target *kinds*: local variables and fields are not symbols
  the extractor emits, so they cannot become function targets.
- Not target discovery: exactly one already-named file is read. No walk, glob,
  index, graph, embedding or vector retrieval.
- Not authority: `write_authority`, `execution_authorized`, Apply authority and
  `auto_patch` are untouched, and `patch_basis` is still decided entirely by the
  unchanged PATCH.BASIS logic — never hardcoded.
- Not a prompt change: whether authoring now enters the localized bug-fix branch
  is an *observation* of the unchanged prompt builder, not something engineered.

## Frozen

Zero semantic change to CONTROL.FRESH.1, CONTROL.BOOTSTRAP.1,
PREFLIGHT.REQUEST.1, PATCH.MINIMAL.LIVE.*, PATCH.AUTHOR.LIVE.*,
CANDIDATE.VERIFY.*, DEFECT.PROBE.*, ANSWER.COHERENCE.*, UX.STATE.1,
UX.CONTEXT.1, SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, AUTH.DREAM.1,
DATA.ROLLBACK.1, AUTH.WEB.1 and AUTH.WEB.READ.1. DOGFOOD.JAVA.1 is preserved
as audit evidence and is not re-run to a different conclusion.

## Deferred (explicitly not addressed here)

Multi-method repair scope (MainApp's errors span `m1`, `m2` and `m3`), Twosum
compile coverage, downstream task-text transport (the `[USER]` section is the
literal "Generate patch"), Java final validation
(`get_default_validation_command` has no Java branch), CRLF apply-time
matching, the Generate success / null-candidate UI, UX-05, UX-06,
Docker/MCP/plugin capabilities, CAPABILITY.BROKER.1 and T6 Round 11.
