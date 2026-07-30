# INDEX.1E.1 - Manifest Load and Shadow Delta Plan Dispatch

**Status:** `INDEX_1E_1_COMPLETE_WITH_WARNINGS`

## Integration seam

`core.indexer.index_repository` prepares the diagnostic after the one shared inventory and identity/scope observation, then continues its existing full-processing loop. The web runner uses that same entrypoint.

## Applied/observed boundary

The previous applied manifest remains historical authority. The current observed manifest is request-scoped evidence only; it is never saved, advanced, or converted into a trusted-current receipt in this phase.

## Manifest loading

Explicit outcomes: `loaded`, `missing`, `invalid`, `root_mismatch`, `repository_mismatch`, `epoch_mismatch`, `scope_mismatch`, `unsupported_schema`. Reads are bounded to 4 MiB; duplicate keys, unsafe paths, invalid policy fingerprints, and identity/epoch/scope mismatch fail closed. File hashes are descriptor-bound and verify stable file identity.

## Run characterization

| Run | Delta A/M/D/U | Planned P/E/R/D | Actual P/E/R | Result |
|---|---:|---:|---:|---|
| A cold | 3/0/0/0 | 3/3/3/0 | 3/3/3 | cold parity |
| B unchanged | 0/0/0/3 | 0/0/0/0 | 3/3/3 | expected shadow/full mismatch |
| C modified | 0/1/0/2 | 1/1/1/0 | 3/3/3 | expected shadow/full mismatch |
| D deleted | 0/0/1/2 | 0/0/0/1 | 2/2/2 | expected shadow/full mismatch |

Run B is the decisive shadow-only proof: the plan recommends zero changed-file work while production still parses, embeds, and replaces all three files.

## Traversal and immutability

Canonical and web operations each perform exactly one repository-membership walk. Manifest and graph consumers add zero. Applied manifests remain byte-for-byte unchanged for unchanged, modified, deleted, persistence-failure, reconciliation-failure, persistence-disabled, and identity-blocked runs; a cold run creates none.

## Compatibility

`delta_shadow` is additive. For stable valid entries, production parsing, embedding, replacement, deletion-by-reconciliation, completion, and manifest behavior remain authoritative full-processing behavior. A post-inventory entry that becomes unsafe now fails closed before replacement and suppresses reconciliation; this guardrail is independent of the shadow plan. No Activation Graph runtime, migration, model/network call, or worker was added.

Compatibility review explicitly audited retriever setup as unchanged, Code DNA as unchanged, graph builders as unchanged with zero added membership walks, and health/status surfaces as unchanged or additive with no new trusted-current or mutation-authority claim.

## Validation

Prior baseline: 6309 passed, 5 skipped, 48 known unrelated failures. Observed repository-wide result: 6366 passed, 6 skipped, 48 failed.

## Warnings

- Legacy applied manifests without a persisted embedding signature fail closed with planner_unavailable when embeddings are enabled; cold builds and signature-bound manifests remain deterministic.
- The repository-wide suite retains 48 classified unrelated baseline failures and must not be described as fully green.
- Production extract_file_text still has a pre-existing check-then-open race; descriptor-bound reads are future security hardening outside this shadow-dispatch phase.
- Production reconciliation exposes aggregate deletion counters rather than per-file deletion paths, so Run D cannot claim deletion path parity.

## Readiness

Ready to design `INDEX.1E.2 - Unchanged File Fast Path`. INDEX.1E.2 was not started or authorized here.
