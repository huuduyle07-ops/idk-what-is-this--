# WORKER.DECL.2A.1 — Strict Envelope Emission Adoption Experiment

**Status:** complete, experimental, shadow-only, default off
**Date:** 2026-08-30
**Depends on:** WORKER.DECL.2A (complete, frozen). Not WORKER.DECL.2B. Not CHECK.2.

## The problem this phase closes

WORKER.DECL.2A built a strict one-object patch envelope, wired its parser in
shadow at the real patch-producing sites, and measured what current providers
emit. The answer was `surrounding_prose_rejected`, and
[its own §18](2026-08-29-strict-structured-patch-response-envelope.md) predicted
exactly that:

> Current providers emit fenced or prose-wrapped JSON, so a dogfood run today
> should report mostly `surrounding_prose_rejected`. **That is expected, not a
> bug.**

But the reason it is expected is that 2A changed only the *reader*. Nothing had
ever asked a patch-producing call for one bounded JSON object. So the number
2A produced answers "do providers happen to conform?" and not the question
WORKER.DECL.2B actually needs answered:

```text
can the existing patch-generation call be asked to conform?
```

2A named this as the cheapest next experiment and left the wording ready. This
phase runs it.

## The one thing that changes

```text
                      flag off                     flag on
prompt          the identical object        the identical object + a block
provider args   {} (nothing added)          {} or {"response_mime_type": ...}
model calls     N                           N
parser          frozen 2A parser            frozen 2A parser
applied patch   legacy extraction           legacy extraction
```

`STRICT_WORKER_PATCH_ENVELOPE_EMISSION` is unset by default. Its value names the
arm:

| Value | Strategy |
|---|---|
| unset, `0`, `off`, `false`, `no`, `none`, `legacy`, `legacy_prompt`, or anything unrecognised | `legacy_prompt` |
| `1`, `on`, `true`, `yes`, `prompt`, `strict_prompt` | `strict_prompt` |
| `native`, `native_json`, `provider_native_json` | `provider_native_json` |

An unrecognised value resolves to `legacy_prompt` rather than raising, so a typo
cannot silently enrol a production run; and a bare truthy value gets the
*narrower* prompt-only arm rather than the provider-native one.

### Off is argument-identical, not merely equivalent

§23 asks for the exact old provider arguments with the flag off, so
`apply_strict_emission_to_prompt` returns the **very same object** it was given
and `strict_emission_client_kwargs` returns `{}`, which the call sites spread:

```python
raw = run_gemini_request_2(
    prompt=prompt,
    repo_path=str(temp_repo),
    **strict_emission_client_kwargs(emission),
)
```

With the experiment off this is byte-for-byte the invocation this repository has
always made — not the same invocation carrying a new argument set to `None`.
That distinction is load-bearing, and it proved itself: existing test fakes
pinned to the old signature (`lambda prompt, repo_path: ...`) keep passing
untouched, which no `response_mime_type=None` version would have allowed.

## What the block says, and where the wording came from

§6 asks to reuse the repository's own strict-output convention rather than
invent a second one.
[`SCOUT_PROMPT`](../../core/prompter.py) already carries it, and
`STRICT_TRANSPORT_RULES` is those five lines **verbatim** — pinned by a test that
reads `core/prompter.py` and asserts each rule is present in it:

```text
- Return ONLY valid JSON.
- Do NOT use Markdown.
- Do NOT wrap the JSON in ```json or ``` fences.
- Do NOT include any explanation, preface, or trailing text before or after the JSON.
- The first character of your response MUST be `{` and the last character MUST be `}`.
```

Only the *transport* language is reused. A test asserts the block carries no
scout semantics (`likely_files`, `likely_symbols`, `request_type`, `repo scout`,
`inventory`), no reasoning or planning instruction, no patch-selection policy,
and no `change_intent`. `core/prompter.py` is untouched and in `forbidden_files`.

The block is **appended**, never merged into the existing contract. A boundary
test asserts `apply_strict_emission_to_prompt` contains no `replace`, `split`,
`format` or subscript, and returns either `prompt` unchanged or `prompt` plus the
suffix — so every existing patch rule, policy block and safety instruction
reaches the model exactly as it does today, with the transport request after
them.

## Which sites are enrolled, and why two are not

This is the design decision the phase turns on, and §4 forces it: patch
semantics, the operation schema and safety instructions stay fixed.

The envelope carries a `patch_plan` and nothing else. So appending "return a
patch_plan envelope" to a prompt whose policy **prefers `patch_candidate`**, or
which **forbids `patch_plan` outright**, would not be a transport change — it
would override a patch rule. `PATCH_PLAN_DECLARED_STYLES` is therefore
`{"vibe"}` alone, and eligibility is conservative: an unknown, missing or
unparseable style is not eligible.

| Site | Provider | Enrolled | Why |
|---|---|---|---|
| [`run_patch_proposal_queue._generate_patch_payload`](../../scripts/run_patch_proposal_queue.py) | Gemini | **always** | Its own prompt already fixes `patch_candidate: null` and asks for a `patch_plan`. The block overrides nothing. |
| [`pipeline.run_draft_pipeline`](../../core/pipeline.py) | Gemini | **when the style is `vibe`** | `safe_minimal` forbids a plan; `balanced` prefers a candidate. Under `vibe` a plan is already encouraged and auto-apply is off. |
| [`sleeping_consultant._generate_patch_plan`](../../core/sleeping_consultant.py) | Gemini | **never** | See below. |

### The dream site is a finding, not a gap

`_generate_patch_plan` asks `build_control_prompt` for
`"Generate patch_plan for: {query}"`, but `run_control_structured` sets no
`patch_style`, so `normalize_patch_style(None)` resolves the prompt to
`safe_minimal` — under which the output-format block says *"patch_plan is
FORBIDDEN"*. Meanwhile its caller `_run_patch_item` treats any response without
a non-empty `patch_plan` list as `planned_no_patch`.

That contradiction is **pre-existing**, and resolving it in the model's favour
would be changing a safety instruction to raise an adoption number. So the site
passes `patch_plan_is_declared_shape=False`, requests nothing, and is recorded
honestly as `legacy_prompt` — the experiment's control arm. The seam is wired
and tested, so a later phase that fixes the style plumbing gets the arm for free.

## Provider-native transport (§7, §8, §29, §30)

2A's provider precheck found Gemini's `response_schema` / `response_mime_type`,
Ollama's `format: "json"` and DeepSeek's structured mode all available and none
enabled. This phase enables **one**, narrowly:

```python
def _generation_config(response_mime_type: str | None):
    config_kwargs: dict[str, object] = {"temperature": 0.0}
    if response_mime_type:
        config_kwargs["response_mime_type"] = response_mime_type
    return genai_types.GenerateContentConfig(**config_kwargs)
```

With nothing asked for, the config is constructed from exactly the keywords it
always was. A boundary test asserts this helper contains exactly one conditional,
and that `agents/gemini_client.py` still contains exactly **two**
`generate_content` call sites — the pre-existing draft and reviewer requests. The
media type alters an existing request; it adds none.

**The two concepts stay separate.** `core/strict_envelope_emission.py` imports no
provider SDK (asserted), and names the media type as a plain string in a
dataclass that holds no client and no config object. In the other direction,
`agents/gemini_client.py` imports nothing from the core contract (asserted), so
neither can drag the other along.

**No provider gets weaker semantics.** `provider_native_json` still carries the
same strict prompt, and every arm is judged by the same frozen parser — a test
runs a fenced response through both the Google and Ollama directives and asserts
an identical `surrounding_prose_rejected`. A family with no native mode keeps the
prompt-only arm rather than losing the experiment (§30); it is never dropped to
`legacy_prompt` for lacking an API.

**`provider_native_schema` is not in the vocabulary.** §17 says to use the
distinctions actually implemented, so a label that names no code path is not
offered. `response_schema` does not appear in the module, by test.

## The parser is not weakened (§9)

This is the one thing that would have made the whole experiment worthless, so it
is asserted structurally rather than promised:

| Claim | How |
|---|---|
| no second reader lives here | no `re`, no `json`, no `json.loads`, no `raw_decode`, no `JSONDecoder`, no `extract_json_block` |
| the fence marker is text, not machinery | the ``` marker appears only in module-level rule text; no function body contains it |
| no friendlier status is invented | the module assigns no string equal to any of 2A's `PARSE_STATUSES` |
| the legacy extractor is never re-run | `core.json_utils` is not imported |
| the frozen file is untouched | `core/worker_patch_envelope.py` mentions no `WORKER.DECL.2A.1`, `transport_strategy` or `response_mime_type`, and is in `forbidden_files` |

So a fenced response *that was explicitly asked not to be fenced* is still
`surrounding_prose_rejected`, an unknown field is still `unknown_field`, and
`change_intent` is still `unknown_field`. That rejection **is** the measurement.

## The observation (§16)

```text
StrictEnvelopeEmissionObservation
    provider_family        google | ollama_http | ollama_chat | unknown
    transport_strategy     legacy_prompt | strict_prompt | provider_native_json
    strict_status          2A's eight statuses, plus not_measured
    legacy_status          legacy_plan_available | legacy_no_plan | legacy_not_measured
    agreement_status       agreed | strict_legacy_semantic_mismatch | not_comparable | not_measured
    envelope_fingerprint   only when strict_status == valid (enforced in __post_init__)
    authoritative_effect   False — a property, not a stored field
```

Nothing is parsed here. The observation *labels* WORKER.DECL.2A's frozen
compatibility record with the transport that produced it; a raw mapping is never
laundered into one (a test feeds a dict claiming `strict_status: valid` and gets
`not_measured`). Enabling the emission experiment implies the 2A measurement, so
the two flags compose rather than conflict:

```python
worker_patch_response = (
    safe_compare_strict_and_legacy(raw, payload)
    if (is_strict_worker_patch_envelope_shadow_enabled() or emission_enabled)
    else None
)
```

§18: no second unrestricted raw-response artifact. The record is identity only —
a test feeds a response containing a secret-looking file body, a path and
surrounding prose, and asserts none of them, nor the prompt block, appears in the
serialised observation.

## Deltas

| Delta | Result | How verified |
|---|---|---|
| Model calls (§10, §31) | **zero** | each generator function contains exactly one model call, by AST; a counting fake records one call per arm with the flag off, `strict_prompt` and `provider_native_json` |
| Repair / retry (§11) | **none** | no producer site branches on a strict status, `strict_available`, or `surrounding_prose_rejected`; a rejected fenced response is measured and the run continues |
| Network requests (§35) | **zero added** | a counting fake client records one `generate_content` per arm; the adapter has exactly two request sites, both pre-existing |
| Validation (§32) | **zero** | the same plan and the same `validation_command` reach `apply_patch_plan` in both arms, with identical `validation_ok` / `validation_mode` |
| Patch application (§33) | **identical** | same response fixture through both arms yields the same authoritative legacy payload; two lifecycle runs flag-off vs flag-on give identical `applied_ops`, `diffs`, `rollback_performed`, worktree and result key set |
| Repository traversal (§34) | **zero** | no `pathlib`, `open`, `walk`, `rglob`, `iterdir` or `glob` in the contract; `os.environ.get` appears exactly once |
| Authority (§39) | **unchanged** | authority-shaped fields still `unknown_field`; no observation field names an authority; the prompt block's only mention of permission/approval/merge/authority is the sentence refusing them |
| Model identity, temperature (§24) | **unchanged** | both arms record the same model and `temperature == 0.0` |
| Checkers (§38) | **unchanged** | no checker module imported; `CHECK.2` not mentioned |

## §22 — what this phase does *not* guarantee

Changing the output-format instruction may change what the model generates. This
phase guarantees the **patch execution machinery is unchanged**, verified on
identical response fixtures. It does **not** claim that a live generation under
the strict prompt is byte-identical to one under the old prompt, and no test
compares two independent live generations. That would be an unfalsifiable claim
about a model, not about this code.

## §21 — the baseline, without a live call

[`scripts/strict_envelope_emission_baseline.py`](../../scripts/strict_envelope_emission_baseline.py)
reads artifacts the repository already records — `model_raw_response.txt` from
replay bundles, `raw_model_response.txt` from the proposal queue,
`raw_model_attempt*.txt` from the dream consultant — and classifies each with the
frozen parser. It performs no model call and no network call (asserted), and it
lives outside every run path (asserted: no run-path file mentions it).

Beside each strict status it records a **shape** label — `pure_json_object`,
`fenced_json`, `prose_wrapped_json`, `no_json_found` — computed by asking the
*legacy* extractor what it would have found. That label explains a rejection; it
can never undo one. A test asserts the strict parser is called exactly once, on
the recorded text itself, and that a prose-wrapped response is simultaneously
`prose_wrapped_json` and `surrounding_prose_rejected`.

Bounded scans report what they dropped rather than truncating silently.

Run against a directory of recorded artifacts:

```bash
python scripts/strict_envelope_emission_baseline.py --root .agent --output .agent/roadmap/strict_emission_baseline.json
```

## §20 — no threshold

`summarize_strict_envelope_emission_observations` reports `strict_valid`,
`legacy_only`, `invalid_both`, `semantic_mismatch`, and status counts broken down
by transport strategy and by provider family. It contains no rate, percentage,
ratio, threshold, score, confidence or verdict — a test tokenises every key name
in the summary and asserts each of those words is absent. Nothing in the code
branches on any of it. A human reads the distribution and decides whether
adoption is good enough for WORKER.DECL.2B.

## A test-isolation leak this phase surfaced, and fixed

The queue-site tests passed standalone and failed in the full suite with the
fake model recording **zero** calls. Cause:
`tests/test_seed_lessons_from_proposals.py` raw-popped `agents.gemini_client`
(and five other modules) out of `sys.modules` without restoring them. After
that, `_generate_patch_payload`'s function-local `from agents.gemini_client
import run_gemini_request_2` built a *fresh* module object, while a patch
applied to the object captured at collection time landed on the old one and was
invisible — a failure that could only ever appear in a full-suite run.

Both halves are addressed:

- **The leak.** The raw pops are now `monkeypatch.delitem(sys.modules, name,
  raising=False)`, which removes the entry the same way and restores it at
  teardown. Its sibling `tests/test_lesson_auto_candidates.py` already used
  exactly this, with a comment explaining why; that comment is now mirrored
  here. The test's own assertions — that each guarded module is absent after
  `seed_lessons_from_proposals` runs — are unchanged in meaning and still pass.
- **The test.** `_live_gemini_module()` resolves the module through
  `importlib.import_module` at test time, so the patch lands on exactly the
  object the production import will find. That is the faithful thing to do
  regardless of any leak, so it stays.

Verified in both directions rather than assumed: a throwaway probe asserting
`sys.modules["agents.gemini_client"] is <the collection-time object>` and that a
naive module-level patch reaches a function-local import **passes** after the
seeder suite with the fix, and **fails** when preceded by a raw
`sys.modules.pop` — so the probe was not vacuous and the restore is real.

## Broader validation

Full suite: **8623 passed, 49 failed, 14 skipped** (555s). Every one of the 49 is
pre-existing and none involves a file this phase touched — established by
probe, not by assumption:

| Class | Count | Why it is not this phase |
|---|---|---|
| Stale top-recommendation (`DOGFOOD.1B` vs `UX.RUN.1` / `HARDEN.CLOSE`) | 15 | Removing `WORKER.DECL.2A.1` from the registry in-memory leaves the top recommendation and the whole `safe_to_prepare` list byte-identical; only `complete_or_history` moves 134→135, which none of the 49 asserts |
| Stale phase status (`'complete' == 'proposed'`) | 7 | The set of non-complete phases is identical at HEAD and now: `{MIRROR.13, DOGFOOD.1B, VERIFY.TEST.1}` |
| Missing `.agent/harden/*` and `.agent/human/*` artifacts | 26 | Those directories do not exist in this checkout; the simulators report `*_incomplete` for absent inputs |
| `core/direct_context_patch_attachment.py` imports `core.file_capabilities` | 1 | A file this phase never touched |

Phase file ordering was also cleared: the picker and registry reports are
byte-identical under five random shuffles of the phase list, so the recovered
entries' order cannot affect any output.

## Files changed

| File | Change |
|---|---|
| `core/strict_envelope_emission.py` | new — flag, transport vocabulary, eligibility, prompt block, directive, observation, summary |
| `scripts/strict_envelope_emission_baseline.py` | new — offline recorded-response baseline |
| `agents/gemini_client.py` | optional `response_mime_type` keyword; `_generation_config` builds the config conditionally |
| `core/pipeline.py` | style-gated directive on the draft call; observation in `finalize_answer`; passes it at the apply |
| `core/sleeping_consultant.py` | threads a directive (always `legacy_prompt`) and records the observation |
| `scripts/run_patch_proposal_queue.py` | enrolled site: directive, prompt suffix, client keyword, observation |
| `core/run_lifecycle.py` | optional `strict_envelope_emission=None`; flag-guarded artifact write |
| `core/replay_recorder.py` | one artifact name added to the allow-list |
| `core/agent_state.py` | two optional fields |
| `tests/test_strict_envelope_emission.py` | new — 92 behaviour tests |
| `tests/test_strict_envelope_emission_boundaries.py` | new — 33 static boundary tests |
| `tests/test_worker_patch_envelope_boundaries.py` | one over-tight assertion relaxed to its actual intent |
| `tests/test_native_worker_declaration_qualification.py` | one known-set assertion extended by one file |
| `tests/test_seed_lessons_from_proposals.py` | raw `sys.modules.pop` → `monkeypatch.delitem`, fixing a cross-file isolation leak |
| `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`, `tests/test_phase_picker.py` | registration |

`core/worker_patch_envelope.py`, `core/json_utils.py`, `core/prompter.py`,
`core/control_engine.py`, `policy/decision_helper.py`, `patching/`,
`core/executor.py`, `agents/deepseek_client.py`, `agents/ollama_client.py` and
every frozen checker are untouched and in `forbidden_files`.

### One WORKER.DECL.2A test was relaxed

`test_the_lifecycle_argument_defaults_to_absent` asserted that
`worker_patch_response` was the **last** positional parameter of
`run_patch_plan_with_artifacts`. Its docstring states its actual claim — "an
existing caller that knows nothing of this phase behaves identically" — which is
about the argument being optional and defaulting to `None`, not about its
position. Threading `strict_envelope_emission` through the same entry point broke
the incidental half. It now asserts the parameter is present and defaults to
`None`, matched by name rather than by index. This is the same relaxation 2A
itself applied to a WORKER.DECL.1 assertion, for the same reason.

### One WORKER.DECL.1 known-set was extended

`test_no_production_response_contract_asks_a_worker_to_declare_its_changes`
enumerates every production string literal that specifies a patch response shape
— recognised structurally, by naming `patch_plan` or `patch_candidate` — and
asserts none of them names a declaration field. `STRICT_ENVELOPE_PROMPT_BLOCK`
restates the `patch_plan` shape, so it is a response contract by that test's own
definition and the guard correctly reported that the set had moved. The fix is
to add the file to the known set, not to loosen the detector: the substantive
assertion, that no contract names a declaration field, now covers the new block
too, and it passes. WORKER.DECL.1's `unavailable` outcome is unchanged.

## Known limitations

1. **One site is unconditionally enrolled.** Only the proposal queue is always
   on; the pipeline needs `vibe`, and the dream site needs a `patch_style` fix
   that is out of scope here. Adoption data will be thin until a phase that owns
   `core/control_engine.py` can widen eligibility without changing patch
   semantics.
2. **Only one provider family is exercised in production.** All three
   patch-producing sites call Gemini, so `ollama_http` and `ollama_chat` exist in
   the vocabulary and in the S30 fallback path — which is real code, reached and
   tested — but no production run currently passes them. The cross-provider
   claim is proven by test, not by traffic.
3. **No live provider data is included in this report.** Every number here comes
   from fixtures and fakes. The experiment is *runnable* on real provider paths;
   it has not been *run* against a live provider in this phase, which requires an
   operator with credentials to enable the flag and read the counters.
4. **The recorded baseline found no artifacts in this checkout.** The classifier
   is tested against synthetic recordings; there are no `model_raw_response.txt`
   files on disk here, so the "what do providers emit today" distribution is
   still empty until a dogfood run produces some.
5. **`patch_candidate`-only responses remain invisible**, inherited from 2A: the
   envelope carries no candidate slot, so single-file-edit runs contribute
   `legacy_no_plan` rather than an adoption signal.
6. **Prompt-change effects on patch content are unmeasured**, by §22's own logic.
   Whether the strict block makes the model produce *worse patches* is a
   different experiment, needing paired live generations and a quality judgment
   this phase has no authority to make.
7. **The web routes are still not wired**, inherited from 2A: `web/app.py`'s
   patch-generation endpoints produce a payload for operator review with no
   lifecycle call to attach an observation to.

## What comes next

**A dogfood run.** Enable the flag on the proposal queue with real credentials,
read `strict_status_by_transport_strategy`, and compare `strict_prompt` against
`provider_native_json`. That is the number WORKER.DECL.2B is waiting on, and
this phase is what makes it obtainable.

**WORKER.DECL.2B**, once a human judges adoption sufficient: add
`pre_execution_change_intent` inside the now-emitted envelope, with the
declaration stage and staged provenance vocabulary
[WORKER.DECL.1's qualification](2026-08-28-native-worker-declaration-source-qualification.md)
listed as blocking. Two fields of one model response remain an
`independently_declared_channel` measuring internal output consistency — never
independent evidence, and never input to EVIDENCE.2's independence semantics.

**Then CHECK.LIVE.1B's native declaration seam**, and only after that
CHECK.LIVE.2A.
