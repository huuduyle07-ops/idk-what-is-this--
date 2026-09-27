# WORKER.DECL.2B — Pre-Execution Change Intent Channel

**Status:** active; implementation/offline validation complete, live v2 dogfood incomplete; shadow only, default off  
**Depends on:** WORKER.DECL.2A.2  
**Does not begin:** CHECK.LIVE.2A, CHECK.2 promotion, CHECK.3, or a
post-execution completion report

## Outcome

A real strict worker response can now carry these two sibling structures from
the same existing provider call:

```text
WorkerPatchEnvelope v2
├── patch_plan
└── change_intent
```

`change_intent` answers what repository changes the worker intends the patch to
cause. It is frozen before application. It does not say what completed, what the
worker later observed, or what the filesystem proves.

The channel is **independently declared from programmatic derivation**: software
does not build it from `patch_plan`, prose, legacy extraction, likely files, or
observed changes. It is **not independent evidence**, because the same model
invocation emits both sibling fields.

## Protocol evolution

V1 retains its exact historical meaning:

```json
{
  "schema_version": "worker_decl_2a_patch_envelope_v1",
  "patch_plan": []
}
```

`parse_strict_worker_patch_envelope` remains the v1 entry point and continues to
reject `change_intent` as an unknown field. Stored v1 artifacts remain readable
and are not migrated.

V2 is an explicit additive protocol:

```json
{
  "schema_version": "worker_decl_2b_patch_envelope_v2",
  "patch_plan": [
    {
      "op": "replace_snippet",
      "relative_path": "src/example.py",
      "target_snippet": "old",
      "patched_snippet": "new"
    }
  ],
  "change_intent": {
    "stage": "pre_execution_intent",
    "intended_changes": [
      {"path": "src/example.py", "change_kind": "modified"}
    ]
  }
}
```

`parse_strict_worker_patch_envelope_v2` requires all three top-level keys. It
still rejects fences, surrounding prose, multiple objects, unknown keys,
authority-shaped keys, unsafe paths and over-bound values. Missing or malformed
intent invalidates the strict v2 envelope whole. There is no repair, truncation,
retry, prose recovery, or plan-derived backfill.

The first intent schema is deliberately minimal. It carries only stage and
explicit path/kind pairs. The allowed kinds are `added` and `modified`, matching
the executor's actual `create_file` and `replace_snippet` vocabulary. Deletion
and rename are not advertised as worker intent operations because the current
patch executor cannot express them.

## Request and provider transport

`PRE_EXECUTION_CHANGE_INTENT` is a second, default-off flag composed with
`STRICT_WORKER_PATCH_ENVELOPE_EMISSION`. It cannot enroll a legacy call on its
own. When both flags enroll a site, 2B replaces only the strict output-format
suffix with the v2 three-key contract. Every planning, safety, operation and
reasoning instruction ahead of that suffix is unchanged.

Both proven transports are reused:

- `strict_prompt` appends the v2 block;
- `provider_native_json` appends the identical block and reuses the existing
  `application/json` media type on the same Google request.

No provider response-schema argument was added. No second request exists.

## Freeze and declaration adaptation

The v2 parser returns immutable `PreExecutionChangeIntent` and `IntendedChange`
records. `PreExecutionIntentCapture` keeps that accepted object in memory and
serializes only status, stage, provenance and fingerprints—not patch payloads or
response text.

After the lifecycle creates its run identity, and before it reads any pre-apply
path digest, the accepted intent becomes:

```text
WorkerChangeDeclaration
  declaration_stage = pre_execution_intent
  source_provenance = pre_execution_worker_intent
  channel_provenance = independently_declared_channel
```

The frozen CHECK.1 `WorkerReport` requires a status vocabulary designed for
completion-era reports. The adapter uses `partial` as a compatibility marker,
not as a model claim of completion. Live receipt metadata preserves the real
stage and exposes `pre_execution_intent_not_completion`, so a
`declared_but_unobserved` CHECK.1 finding is interpreted as
`intended_change_not_materialized`, not a false completion claim. CHECK.1 reason
codes and policy are unchanged.

Derived measurability is fixed by provenance, not caller-supplied booleans:

| Source | Intent fidelity | Post-execution self-report fidelity |
|---|---:|---:|
| `pre_execution_worker_intent` | true | false |
| `post_execution_worker_declaration` / legacy independent completed declaration | true | true |
| `legacy_plan_derived` | false | false |
| `unavailable` | false | false |

## Three-way diagnostics

The integration preserves three distinct facts:

```text
worker intent  ── compared with ── patch plan
      │
      └──────── compared with ── observed final changes
```

Intent-versus-plan records `agreed`, `intent_missing_plan_change`,
`plan_change_missing_intent`, `kind_mismatch`, `mixed`, or `unavailable`.
Equality is never a schema invariant and never controls execution.

Intent-versus-observed records bounded path buckets for
`intended_and_observed`, `intended_not_observed`, `observed_not_intended`, and
`intended_kind_mismatch`, plus an overall relation. The comparison consumes the
existing typed final change set after apply/rollback/inline validation. It does
not rewrite intent to match reality.

## Authority and authoritative outcome

The legacy extractor remains the source of the plan supplied to
`apply_patch_plan`. The strict v2 plan and intent are telemetry. In particular:

- intent is never unioned with the executable plan;
- an intent path grants no write or path-expansion authority;
- intent cannot add, remove, reorder, or rewrite operations;
- an intent mismatch triggers no retry or normalization;
- a malformed v2 response cannot fail an otherwise valid legacy run;
- CHECK.1 remains shadow-only even when it returns a stricter status;
- CHECK.2 and CHECK.3 are not invoked.

Enabling 2B composes in the existing CHECK.LIVE.1 bounded observer so the phase
can compare intent with actual changes. That observer reads only paths already
named by the executable plan and the already-existing validation side-effect
receipt. It performs no repository-membership traversal. Validation is not
rerun.

## Durable dogfood telemetry

The lifecycle writes a bounded capture record into the normal replay bundle.
The proposal-queue replay bundle lives in a disposable benchmark clone, so the
proposal runner additionally exports one bounded
`pre_execution_change_intent.json` receipt into its established durable
`.agent/proposals/<run>/<case>/` directory before clone cleanup.

The durable receipt carries only run/case identity, v2 status, provider and
transport, intent/envelope fingerprints, intent-plan relation, intent-observed
relation, CHECK.1 shadow status and authoritative outcome. It explicitly records
that it contains no raw response and that same-model intent is not independent
evidence. It contains no prompt, snippet, file body, diff, validation log,
environment value, credential, or secret. The temporary repository lifetime is
unchanged.

Read-only aggregation reports raw counts by stage/source, v2 validity,
intent-plan relation, intent-observed relation, CHECK.1 status, provider and
transport. There is no fidelity score, confidence, honesty score, severity, or
threshold, and counts decide nothing.

## Cost deltas

| Dimension | Delta |
|---|---:|
| model calls | 0 |
| network requests | 0 |
| validation executions | 0 |
| repository traversals | 0 |
| patch operations/order/payload | 0 |
| authoritative checker decisions | 0 |
| temp repositories retained | 0 |

## Live dogfood observations

No percentage or threshold is derived from this tiny sample. A run is never
retried because intent disagrees or because v2 is invalid.

| Arm | Raw observation |
|---|---|
| `strict_prompt` | Google proposal-queue run `.agent/proposals/20260830_094941`, case `python_off_by_one_pagination`: one existing provider generation, no fallback; v2 status `surrounding_prose_rejected`; native intent unavailable; intent-plan and intent-observed relations unavailable; legacy plan applied and benchmark validation passed; CHECK.1 shadow status `reconciled`; authoritative outcome success; 2B-added model calls 0. The bounded receipt survived deletion of replay run `20260830_005045_f57574fd` with `contains_raw_response=false`. |
| `provider_native_json` | Not executed. The host denied the second network escalation before process creation, so no provider request was made and no compliance result is claimed. |

The first arm is useful negative evidence: the two-key 2A.2 result did not carry
over automatically to the larger v2 contract. The phase remains active until a
real v2-valid run demonstrates that `patch_plan` and `change_intent` can be
preserved together on the production site; the unrun native arm must also be
measured before a two-transport conclusion is made.

## Known limitations and next phase

- The provider sample remains one model family and one production site.
- The only completed v2 live arm was invalid, and the native-JSON arm was not
  authorized to start. Therefore the live stop condition is not yet met.
- The initial operation/intent vocabulary cannot express delete or rename.
- The proposal queue performs its benchmark validation after the lifecycle's
  apply receipt; the intent comparison therefore covers the final apply state
  and any inline lifecycle validation, while the existing proposal validation
  result remains separately recorded.
- The frozen CHECK.1 report has no native stage field; stage remains attached in
  live metadata, and `partial` is the documented adapter marker.
- Same-response channel separation is useful instrumentation, never independent
  evidence for EVIDENCE.2.

The implementation is ready for a later CHECK.LIVE.2A design to consume the
three-way dataset. That phase should not begin until these observations are read;
it must not reinterpret pre-execution intent as completion evidence.
