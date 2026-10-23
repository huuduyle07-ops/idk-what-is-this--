# Documentation relocation record

[Phase index](../README.md) | [Documentation home](../../README.md)

The roadmap's 94 movable phase artifacts are grouped into 36 phase folders.
Retries and lifecycle retries share their parent phase folder. Five files retain
their original paths because code, tests or registry reversal receipts depend
on them; the phase index lists the reasons and the relevant phase folders link
to those files.

- [Relocation map](relocations.json): former path, current path, before/after
  SHA-256 and the exact Markdown link repairs for each moved file.
- [Preservation record](preservation.json): original file hashes and verification
  that unrelated files and retained inputs were unchanged.
- [Validation results](validation.json): link, evidence-integrity and pure
  regression checks for this documentation move.
- [Integrity checks](integrity_checks.json): file-preservation and navigation
  checks across the documentation move.

JSON reports, captured text logs, registry metadata, historical commands and
source citations preserve their original contents. Markdown repairs change only
relative link destinations so navigation works at the new locations. Historical
paths inside evidence describe the layout at the time of that evidence; use the
relocation map to locate the current file rather than rewriting the evidence.

No runtime code, tests, authority, policy, schema, historical hash pins or registry
contents were changed by this organization.

Validation passed: 84 pure regressions, all local documentation links, and
verification of 1,864 existing files against their originals. The only content
edits to moved reports repair 18 relative links across seven Markdown files.
