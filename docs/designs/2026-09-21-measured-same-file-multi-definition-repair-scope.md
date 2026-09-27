# PATCH.BASIS.SCOPE.1 — Measured Same-File Multi-Definition Repair Scope

`PATCH.BASIS.TARGET.1` continues to own one primary target.  This phase adds
an evidence-only `RepairScope` alongside that target when a current
`PREFLIGHT.REQUEST.1` Java compiler handoff proves compiler errors in several
eligible structural definitions in the exact same file.

For the dogfood receipt, the primary remains `MainApp.java::m1`; the measured
repair members are `m1`, `m2`, and `m3`.  Five compiler diagnostics group as
`m1: 1`, `m2: 1`, `m3: 3`.  Members are ordered by structural source position,
not proximity, symbol spelling, or a model decision.

## Admission and refusal

The scope builder reads only the named primary file and uses the existing
`structural_definitions` extractor.  It accepts only typed `compiler_error`,
`severity=error` entries from one `PREFLIGHT.REQUEST.1` `compile_evidence`
handoff.  It verifies the receipt's CONTROL fingerprint, repository identity,
raw source digest, and receipt fingerprint before parsing the current bytes.

Every reported compiler error must have exactly one eligible structural owner.
Zero owners, multiple owners, unavailable structural data, incomplete typed
diagnostics, stale source or bindings, missing primary member, too many members
or source bytes all fail closed.  An error in another admitted file returns
`cross_file_scope_required`; this phase never creates multi-file scope.  The
limits are eight definitions and 16,384 aggregate UTF-8 source bytes, with no
truncation.

## Handoff and boundaries

For more than one member, the existing localized authoring prompt receives an
additive `[MEASURED REPAIR SCOPE — authoritative compiler evidence]` block.
Each entry carries exact source span/snippet and its own diagnostics.  The
single primary `target_file` and `target_symbol` remain unchanged.  A one-member
scope renders no new section, preserving the prior single-target meaning.

Repair scope carries no write, execution, auto-apply, or approval authority.
It does not change `PATCH.BASIS` (`grounded_defect` remains the basis),
localization, `PATCH.AUTHOR`, `PATCH.MINIMAL`, Java final validation, CRLF
handling, Twosum evidence policy, graph/index traversal, or model-call count.
If an existing later contract rejects a properly scoped multi-definition
candidate, that rejection is a newly measured later blocker rather than work
for this phase.
