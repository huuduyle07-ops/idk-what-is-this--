# Repository organization: first extraction

This pass starts grouping runtime code and tests by responsibility while
preserving the current, substantially modified working tree. It does not migrate
all 407 original flat core modules or all 542 original flat test modules.

## Implemented layout

```text
core/
  runtime/
    synthetic/             9 owner implementations
  README.md                ownership and extraction boundaries
tests/
  runtime/
    synthetic/             14 existing test modules
  architecture/            relocation integrity checks
  fixtures/                existing evidence, unchanged
  README.md                suite commands and historical-test policy
scripts/
  source_layout.py          explicit historical source resolver
docs/architecture/
  source_relocations.json   old/new paths, hashes, exact reversible edits
```

Consumers now import from `core.runtime.synthetic`. Existing serialized owner
identities, HMAC domains, schemas, permissions and state transitions remain
unchanged. An AST check confirms that runtime edits consist only of imports.
The new package does not eagerly load owners. There is one implementation of
each owner and one collected copy of each test.

The manifest covers moved files and their edited consumers. It preserves the
exact earlier bytes by reversing recorded line edits only after validating the
current hash. Historical fixtures and phase reports keep their original content.
This bridge supports old evidence; it does not claim the relocated source is
byte-identical to its previous version.

`replay_synth_auth_pinned1.py` still checks **current source bytes** against its
operational gate. A prior gate bound to pre-migration source can therefore stop
with `source_changed_after_gates`; this is intentional. The migration does not
refresh an operational approval, consume a one-shot attempt or run a live replay.

## Why the broader move needs another boundary

All tracked flat core modules appeared in test fixture manifests at inspection.
Many tests and maintenance helpers are themselves hash-pinned. Additional source
baselines also exist in phase documents. Broadly replacing paths or moving files
without tracing these readers would break evidence checks or make absence tests
pass merely because a file changed location.

The extraction therefore updates source readers as well as imports. In
particular, historical assertions that an owner does not yet exist resolve its
new location and continue to report the pre-existing mismatch.

## Next extraction priorities

1. Separate historical phase-state assertions from current behavior regressions.
   Keep original evidence immutable and retain current authority tests.
2. Extract lesson storage, retrieval and teaching support into `learning/`, with
   their tests and shared fixtures. Distinguish agent lessons from learner state.
3. Extract context acquisition and coding verification by complete dependency
   family; avoid moving individual files across unresolved fixture cycles.
4. Move report-only planning/checkpoint families into `governance/`. Their volume
   should not define the product-facing core or the default learning workflow.

The [core index](../../core/README.md) and [test index](../../tests/README.md)
describe these responsibilities. Validation results are recorded alongside this
document in `organization-validation.json`.
