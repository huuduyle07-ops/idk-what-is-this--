# Frozen lifecycle and cumulative-cap scope audit

The frozen text mandates complete materialization and compilation responses and a new challenged prepared-state observation before readiness or handoff. It does not freeze an endpoint that assigns every such observation to, or outside, the cumulative preparation capture. This audit therefore records **AGGREGATE_BUDGET_SCOPE_UNRESOLVED**. It does not exclude any observation to make the cap fit. A separate arithmetic proof may still establish an excess using a universally included subset; this audit itself supplies no arithmetic impossibility claim.

The complete machine-readable operation inventory, exact quotes, source line references and JSON pointers are in `lifecycle_audit.json`.

| Operation/evidence | Successful lifecycle requirement | Preparation-cap membership |
| --- | --- | --- |
| OBSERVE_EMPTY_WORKSPACE | Initial current empty-state evidence is mandatory | UNRESOLVED_SCOPE: before materialization-origin deadline, but byte-scope exclusion is not frozen |
| MATERIALIZE_EXACT_SCENARIO_SOURCE | Mandatory request/response | MANDATORY_INSIDE_PREPARATION_CAP |
| Materialization response.workspace_state | Mandatory complete embedded post-observation | MANDATORY_INSIDE_PREPARATION_CAP; already part of materialization response |
| COMPILE_EXACT_SCENARIO | Mandatory request/response | MANDATORY_INSIDE_PREPARATION_CAP |
| Compilation response.workspace_state | Mandatory complete embedded post-observation | MANDATORY_INSIDE_PREPARATION_CAP; already part of compilation response |
| OBSERVE_PREPARED_ARTIFACTS | New prepared-state OBSERVE_* mandatory before readiness/handoff; exact dedicated tag not uniquely mandated | UNRESOLVED_SCOPE |
| OBSERVE_CURRENT_WORKSPACE | Optional extra observations; can describe prepared stage and may supply mandatory new OBSERVE_* | UNRESOLVED_SCOPE for wire-level required checks and attempt endpoint |
| PREPARE_EXCLUSIVE_HANDOFF | Optional later separately authorized consumer handoff | UNRESOLVED_SCOPE if invoked; not required for preparation eligibility itself |
| BEGIN_CLEANUP | Mandatory eventual monotonic cleanup duty, not pre-readiness success step | UNRESOLVED_SCOPE; cleanup can preempt an active attempt |
| CLEANUP_AND_REPORT | Mandatory eventual cleanup/evidence duty, not pre-readiness success step | UNRESOLVED_SCOPE; separate cleanup bound is not a cap exemption |

`MANDATORY_BUT_OUTSIDE_PREPARATION_CAP` is not assigned merely because an operation has an observation/cleanup profile or occurs later. The historical contracts do not provide a unique byte-accounting endpoint that supports those exclusions.

Controller `contract.json:486`, `/bounds/attempt_budget_scope`, says exactly:

> One monotonic 5000ms deadline starts at materialization admission and includes materialize, compile, in-attempt observations and intervening time; never reset per operation. Outer preparation attempt hard timeout 10000ms. Total outer stdout/stderr each <=8192 over all attempt frames, not 8192 per unlimited frame. Retained lifetime is not this attempt budget and confers no indefinite readiness.

This supplies a deadline origin, an unchanged cumulative cap and an in-attempt rule. It does not state whether byte-accounted preparation ends at the compile response, receipt, new challenged observation, reservation or cleanup. The transport review preserves the gap: `selection.json:458` requires “explicit frozen attempt boundaries” and prohibits silently excluding required observations.

The contrary scope evidence is preserved as well: PREP closure `contract.json:521`, `/preparation_authority/semantics/preparation_authority_design`, says two facets bind “one fixed materialize-then-compile attempt”; `/ordering/cleanup_is_preparation` is `false` at `:501`. Its `:502` clarification says cleanup after completion or abort remains a cleanup duty. These distinguish effect authority and cleanup conceptually, but do not independently define the controller byte counter's endpoint or the membership of a required fresh prepared-state observation. They do not authorize an inferred counter reset.

The receipt and current readiness are distinct. Controller `contract.json:352` says “return preparation observations; preparation owner alone authenticates success receipt”. `OBSERVE_PREPARED_ARTIFACTS` already requires “prepared-artifacts-present from preparation owner” (`contract.json:248`) and takes `preparation_receipt_id` (`:258`). Requiring that exact operation before creating the initial receipt would be circular. No explicit frozen rule requires it before receipt authentication. After mutation, however, `message_schema.json:1023`, `/cross_field_rules/1`, says exactly:

> Request/response IDs, purpose=operation, all generations and owner sequence/challenge match exact original relation. Challenge non-null exactly for three observation tags. Mutation poststate uses a separate single-use owner-issued post-observation challenge/sequence prebound in its spent admission; it is operation-bound source evidence only, never a current-readiness response. Owner consumes that reference once and requires a new OBSERVE_* challenge before readiness or handoff.

Thus complete mutation poststate cannot stand in for the new readiness observation. The wording requires `OBSERVE_*`, while `OBSERVE_CURRENT_WORKSPACE` permits a “complete current snapshot of stage-appropriate exact manifest” (`contract.json:234`); it does not uniquely mandate the longer dedicated prepared tag. Workspace `contract.json:459` separately requires the original live workspace and fresh artifact integrity at handoff. Compile poststate must be after full reaping and capture/EOF closure, never a snapshot retaining an admitted live compiler to save bytes.

The schema forces complete duplication. `message_schema.json:843` and `:865` require `workspace_state` inside materialization and compilation result records, with `all_fields_required=true` at `:860` and `:872`. That state is not replaceable by a digest reference, and mandatory nullable keys cannot be omitted. These nested bytes are counted once within their enclosing response, without inventing independent poststate frames.

Direction accounting remains conditional on transport. Semantic request and response payload sizes can be calculated independently. For reviewed candidate A, requests travel controller stdin and responses travel controller stdout; every actual frame adds exactly four u32be header bytes in its own direction. Only in-attempt response frames count against controller outer stdout. Requests must be reported separately, without adding their bytes to stdout. Successful controller stderr is empty. Compiler stdout/stderr use separate 2048-byte child captures and must each contain zero successful raw bytes; the required capture metadata is still counted in the serialized compile response. Do not count child bytes or headers twice.

Candidate `selection.json:236`, `/wire/stream_budgets`, preserves “<=8192 captured bytes per outer stream cumulatively over whole preparation attempt, INCLUDING wire headers; no reset at materialize/compile/observation boundaries.” Its separate retained-session ceiling, cleanup slots and reserve do not relax the attempt cap. Candidate framing is reviewed and unaccepted (`selection.json:211`); semantic payload lower bounds must remain separate from this optional four-byte-per-frame overhead.

No authority was issued, transport selected, historical file changed or runtime/process/network observation performed for this audit.
