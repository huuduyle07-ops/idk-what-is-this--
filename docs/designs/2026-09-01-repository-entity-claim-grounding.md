# ANSWER.GROUND.LIVE.1 — Repository Entity Claim Grounding

## Scope

This phase fixes one live answer-boundary defect: a model response could safely
produce no patch and no write authority, then still name nonexistent repository
files and symbols as facts in the user-visible diagnosis.

It does not establish that a grounded symbol caused a defect. It establishes
only that the repository entity identity is backed by evidence the current run
already acquired. CHECK.2 remains unwired.

## Traced production path

The terminal and web paths share the same model/pipeline boundary and then
diverge at display:

```text
model response
  -> run_review_pipeline
  -> pipeline.finalize_answer (parse prose + structured payload)
  -> shared postprocess gate battery
  -> execution/authorization terminal outcome
  -> answer_entity_grounding.ground_state_answer
  -> one safe display/persistence payload
       -> terminal print, log, artifact, session message
       -> web answer, patch field, session message, live trace
```

Read-only `analysis_only` answers take the same final grounding boundary after
their no-execution fact is attached. Interactive follow-up answers use
`ground_answer_for_display` before printing, history insertion, persistence, or
artifact creation.

Grounding deliberately runs after execution/authorization has terminated. It
cannot grant, widen, or disturb defect grounding, patch basis, patch safety,
write authority, execution authorization, or human approval.

## Evidence membership

One operation-scoped repository subject is identified by the existing canonical
root-derived repository identity and aliases already present on the run. Entity
membership is assembled from runtime objects already in hand:

- canonical `RepositoryInventory` entries for repository files;
- eligible source-backed symbols already present in the loaded graph, when that
  operation object is retained;
- CONTROL entry, hypothesis, evidence, exact source, and related-snippet fields;
- `AnalysisEvidence` paths actually acquired by the read-only route;
- typed preflight locations and bounded paths observed in validation output;
- `create_file` operations in an existing patch plan, typed as proposed new.

No directory walk, index query, graph rebuild, source reread, model call, or
network call is performed at the answer boundary. A mismatched inventory or
CONTROL repository identity is ignored. Evidence explicitly marked stale fails
conservatively.

An execution-observed file path establishes that the execution named the file.
It does not establish a source symbol within the file. Analysis documents bind
through their acquisition receipt and need not be code-index members.

## Bounded extraction

Free-text extraction recognizes only common repository-like file names with an
optional `::qualified.symbol` and optional line number. It does not parse
English or infer arbitrary words as symbols. Fenced code, shell examples, and
pseudocode are skipped. Sentence-local markers such as “for example” or “could
put” classify a recognized path as hypothetical rather than an existing-source
assertion.

Structured patch operations supply stronger typing:

- `create_file new_priority.py` is `proposed_new`;
- source-backed existing file/symbol membership is `grounded_existing`;
- a traceback location may be `grounded_execution_observed`;
- a missing user referent is `user_supplied_unverified`;
- a clear example is `hypothetical`;
- unsupported assistant specificity is `unverified_model_assertion`.

The user's wording may be repeated to explain that a path could not be
established, but it never proves the path exists.

## Failed-grounding behavior

When a sentence or structured narrative field contains an unsupported concrete
entity, that assertion is removed and a short evidence-gap statement is placed
at the same display boundary. The entity name remains visible only inside that
explicitly unverified statement. Grounding never substitutes a different
ranked file.

The safe structured copy replaces the operational payload only after execution
is terminal. Consequently CLI output, web `answer`, web `patch`, saved session
messages, logs, artifacts, and live-trace final text cannot select an older raw
model field.

## Receipt

Every new terminal result carries bounded `answer_entity_grounding` telemetry:

- asserted, grounded, and unverified entity counts;
- `unchanged` or `downgraded_unsupported_specificity` action;
- at most twelve entity/status records and unverified records;
- evidence identity gaps;
- extraction, membership-check, and total boundary timing;
- explicit `authority_effect=none` and `retrieval_effect=none` facts.

The receipt contains no confidence, source content, hidden reasoning, or model
review output.

## Frozen systems

The phase changes no retrieval, recall, ranking, graph construction, index
lifecycle, validation semantics, patch basis, patch safety, write mechanics,
execution authorization, model prompts, or `_classify_indent`. Added model and
network calls are zero. Historical runs are not rewritten.

## Regression matrix

The focused matrix pins:

- nonexistent files and nonexistent symbols in real files;
- real source-backed files and symbols;
- acquired analysis documents and execution-observed traceback paths;
- user-supplied missing paths, proposed new files, and hypothetical examples;
- repository-qualified same-relative-path references and ambiguous unqualified
  multi-repository references;
- stale/mismatched evidence refusal and bounded receipts;
- CLI and web display copies, including alternate structured fields;
- T6's fabricated `patcher/generator.py::PatchGenerator.generate` and
  `config/settings.py::ConfigurationOptions` pair with `patch_candidate=null`;
- no silent substitution and no authority widening.

## Verification

- 271 final answer-grounding, registry, and picker tests passed.
- Three frozen compatibility groups passed 1,225 tests.
- The phase registry validates with 152 phases and the benchmark check passes
  54/54 cases; compileall and `git diff --check` pass.
- A representative boundary call measured 0.000143 s extraction, 0.000013 s
  membership checking, and 0.007817 s total.
- The broad suite completed with 9,166 passed, 14 skipped, and 49 historical
  registry/checkpoint and selector-runtime failures. This is three fewer than
  the preceding phase's documented 52-failure baseline, and no grounding test
  failed.
