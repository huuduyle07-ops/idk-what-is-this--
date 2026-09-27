# INPUT.2 — Semantic Waiter Model Adapter & Semantic Evaluation

Date: 2026-08-22
Status: complete
Next: INPUT.3 — Progressive Clarification / Goal Brief Escalation

## Decision

INPUT.1 gave C.A.T.T.U.S a lossless representation of what the user typed and a
deterministic gate that catches mistranscription. It could not yet understand
what the user *meant* — its interpreter only re-shaped literal evidence.

INPUT.2 adds the first real Semantic Waiter: one model call that reads the
order. It changes nothing about who is allowed to act on it.

```text
User Prompt
    ↓
Explicit Evidence Extractor      [INPUT.1, deterministic, frozen]
    ↓
Semantic Waiter Model Adapter    [INPUT.2]
    ↓
SemanticInterpretation           (intermediate, never authoritative)
    ↓
Task Contract Builder            [INPUT.1, deterministic, frozen]
    ↓
Requirement Preservation Gate    [INPUT.1, deterministic, frozen]
    ↓
valid / invalid interpretation
```

The waiter may understand the order. The waiter still may not enter the
kitchen.

## Modules

| Module | Responsibility |
| --- | --- |
| `core/semantic_waiter_adapter.py` | Prompts, strict response parsing, the `SemanticInterpreter` implementation |
| `core/semantic_waiter_runner.py` | Bounded repair loop, outcome statuses, telemetry, fallback |
| `core/semantic_waiter_evals.py` | Semantic case matrix and deterministic checker |
| `core/semantic_waiter_client.py` | Opt-in live transport over one configured model |

No INPUT.1 module was modified.

## The trust boundary

The model does not create the authoritative Task Contract. It returns a
`SemanticInterpretation`, which the runner feeds through the existing
`understand_request` path — the same deterministic conversion and the same gate
INPUT.1 already used. `routing_allowed` still comes from the gate alone.

Response keys that would claim authority are rejected before parsing begins:

```text
routing_allowed · preservation · preservation_status · mode · execution_mode
model · provider · read_authority · write_authority · apply_authority
patch_authority · human_approval · human_approval_required · guardrails
```

Their mere presence fails the response closed. So does any unknown top-level
key, which stops the same claims arriving under a creative name.

## Structured output only

The response must be exactly one JSON object (bare, or in a ```json fence) over
a fixed key set. There is no best-effort conversion from prose. Rejected:
non-JSON text, JSON arrays, missing `task`, unsupported task/relationship/
framework/constraint/output vocabulary, unknown provenance, non-numeric or
out-of-range confidence, and any collection past its INPUT.1 bound. Over-bound
collections fail rather than truncate, because silent truncation is how an
explicit item disappears.

## Explicit vs inferred

The deterministic provenance rules stay authoritative, and three normalizations
keep the model from eroding them:

- `task.provenance` is always forced to `inferred`. A task classification is a
  conclusion, never a quotation.
- `execution_requirements.provenance` is always forced to `inferred`.
- A confidence attached to an `explicit` value is stripped, not honoured.
  INPUT.1 rejects a probability on a quotation; dropping the number removes a
  false claim rather than weakening a rule.

Everything else is left to the gate. A model marking something `explicit`
without literal backing in INPUT.1 evidence fails preservation — which is how
the Vietnamese case stays honest: INPUT.1's extractor is English-only, so the
comparison and the criteria there *must* be `inferred`, and claiming otherwise
fails.

The system instruction tells the model to copy the `EXPLICIT EVIDENCE` section
character for character. That section is the only thing that can back an
`explicit` label, so verbatim copying is the mechanism, not just an aspiration.

## Bounded repair

```text
attempt 1 → preservation PASS → semantic_interpretation_ok
attempt 1 → preservation FAIL → repair → PASS → semantic_interpretation_repaired
                                       → FAIL → semantic_interpretation_failed
```

At most **two** semantic model calls per request, enforced by
`MAX_SEMANTIC_MODEL_CALLS` and re-checked in the receipt's `__post_init__`.
Malformed first output fails closed immediately with no repair call: a model
that cannot emit JSON is not repaired by being asked again, and spending a
second call on it buys nothing.

No recursive retry. No stronger-model escalation. No provider switch. No
automatic question to the user — that is INPUT.3.

The repair message is built from deterministic gate evidence and names the
exact missing items, the exact rubric order, and the exact constraint texts. It
is never "try again" or "think harder".

## Failure and fallback statuses

| Status | Meaning |
| --- | --- |
| `semantic_interpretation_ok` | First attempt passed the gate |
| `semantic_interpretation_repaired` | Second attempt passed the gate |
| `semantic_interpretation_failed` | Gate still failed after the one repair |
| `semantic_output_invalid` | Response was not a valid non-authority structure |
| `semantic_model_unavailable` | Configured model could not be reached |
| `semantic_deterministic_fallback` | Model failed; INPUT.1's deterministic reading was substituted |

Fallback is off by default. When enabled it is never disguised as
understanding: it gets its own status, records in `model_status` which model
failure it replaced, still runs the preservation gate, and is forced to
`routing_allowed=false`. A deterministic reading of the words may describe the
request; it may not authorize acting on it.

## Provider policy

INPUT.2 adds a Semantic Waiter implementation. It adds **no Driver or
model-routing authority**.

Two providers ship, both opt-in, selected by `SEMANTIC_WAITER_PROVIDER`:

| Provider | Transport | Default model |
| --- | --- | --- |
| `ollama` (default) | Local, via the existing `agents.ollama_client.OllamaClient` | `deepseek-r1:1.5b` |
| `gemini` | Google GenAI API, native JSON response mode | `gemma-4-31b-it` |

**Selection is configuration, not escalation.** The provider is resolved once,
before the request starts. One request uses one provider and one model from
start to finish. There is no local-to-cloud failover, no cheap-then-strong
escalation, and no retry against a different model — if the configured model
fails, the request fails and reports *which* failure it was. An unrecognised
provider raises rather than quietly defaulting to local, because silently
running somewhere the operator did not ask for is the behaviour this phase
refuses to have.

Local is the default so an interpretation pass never silently spends on cloud.
An operator who selects `gemini` is choosing to make network calls and to spend
on a provider; nothing in this phase makes that choice for them. The credential
is read at call time and never stored on the client or in telemetry.

The existing Gemini helper was deliberately not reused: `run_gemini_request`
iterates a model list, which is exactly the routing INPUT.2 must not perform.

Any other provider can be used without touching INPUT.2 — implement
`SemanticModelClient` (`model_id` plus `complete`) and inject it.

The client is inert until `complete` runs: the transport import is lazy, so
importing the module, constructing a client, and building an adapter all stay
offline. The default test suite needs no network and no credentials.

### Context window sizing

A reasoning model bills its hidden `thinking` block against the same context
window as the prompt and the answer. Measured on the dogfood case with
`qwen3.5:4b`:

| `num_ctx` | prompt | generated | `done_reason` | `response` |
| --- | --- | --- | --- | --- |
| 4096 (stock) | 939 | 3157 | `length` | empty |
| 16384 | 939 | 4058 | `stop` | valid JSON |

At the stock window the model is cut off mid-thought and returns an empty
string, which is indistinguishable from an unreachable model — the adapter
reports `semantic_model_unavailable`, correctly but unhelpfully. This looked
like model incapability and was not.

`agents/ollama_client.py` therefore gained one optional, additive
`generate(options=...)` parameter that merges over its existing defaults. Every
prior caller is byte-for-byte unaffected, and `tests/test_ollama_client_options.py`
pins that. The semantic client requests `SEMANTIC_WAITER_NUM_CTX`, default
16384.

This is a transport option, not model routing: one configured model, one call,
no fallback.

## Cost boundary

The request carries the raw prompt (capped at `MAX_SEMANTIC_PROMPT_CHARS`, with
truncation recorded in telemetry) plus the deterministic explicit evidence plus
a compact schema. It never carries the project map, repository index, graph,
lessons, benchmark reports, source files, tests, Dream artifacts, or run
history. This is intake semantics, not repository reasoning.

## Semantic evaluation

Twelve cases, checked deterministically, covering the original dogfood
sentence, an English paraphrase, a Vietnamese rendering, a bounded snippet
comparison, a plain explanation, an ambiguous reference, an explicit
prohibition, an output contract, a notes list that is *not* a rubric, allowed
inferred metadata, an OWASP reference, and an invent-nothing package question.

The same cases drive the scripted default run and the opt-in live smoke, so the
two cannot drift.

Anti-hallucination is tested by construction: for the invent-nothing cases the
suite feeds a *deliberately inventive* response and asserts the eval fails —
invented comparisons, invented rubrics, invented repository inspection, and
guessed entities behind an ambiguous reference.

## Known INPUT.1 extraction limits surfaced by the matrix

These are literal-extractor quality issues in the frozen INPUT.1 layer, not
INPUT.2 defects. None of them loses a user commitment; all of them make the
contract uglier or push something from `explicit` to `inferred`.

- Comparison subjects over-capture past the clause boundary: "Compare
  C.A.T.T.U.S with DeepSeek Harness and tell me where they overlap" yields the
  subject `DeepSeek Harness and tell me where they overlap`. The clean subjects
  are also present, so nothing is lost.
- `Compare A and B ...` extracts no comparison, because `A` is filtered as a
  stopword-shaped token.
- `return a Markdown table` matches no output cue, so the format is honestly
  inferred rather than explicit.
- `OWASP Top 10` is captured as the entity `OWASP Top`; the full string still
  survives verbatim inside the `authority_reference` constraint.
- The extractor is English-only, so non-English comparisons and rubrics are
  correctly `inferred`.

## Registry mismatch, stated plainly

The ROAD.1 schema hard-errors on `network_allowed=true` and requires
`model_calls_allowed=false` across the seed registry. INPUT.2 is registered
with both false, which is true of the phase itself: the implementation, the
default behavior, the test suite, and every validation command perform zero
model and zero network calls.

What the schema cannot express is that the phase *ships an opt-in capability it
never exercises*. That gap is recorded in the phase notes rather than papered
over. No registry safety rule was weakened to make INPUT.2 fit.

## Not wired

The Mixed Mode router does not consume Semantic Waiter output. Nothing calls
`understand_request_semantically` in a live path. Instant Run, Commander, Chat,
Dream, and Project Evolution are untouched. Goal Brief remains optional and
unmodified. Reconnaissance, indexing, and CTX.SELECT are untouched.

## Next

INPUT.3 should decide what happens when a contract is incomplete: continue when
sufficiently complete, offer Goal Brief assistance when recoverable, and ask the
user only on genuine ambiguity — using the `ambiguities` and
`missing_information` the waiter now produces, plus the `semantic_interpretation_failed`
outcome this phase stops at.
