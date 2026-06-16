# Persona Governance Manifest (GOV.1)

> **Status: Complete / docs-only.** GOV.1 adds no execution power.
> **GOV.1 does not build new personas. GOV.1 limits and defines personas.**

## Why this document exists

C.A.T.T.U.S has accumulated many bounded roles, contracts, and report-only
workflows (Goal Brief, Worker Assignment, Driver Model Routing, Visual Evidence
Intake, Teaching Card, Worker Result Review, External Queue, Project Evolution
review gates). The [District Model framing](AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-07.md)
and the README [Operating Modes / Permission Matrix](../../README.md) already
exist. The risk now is **architecture sprawl**: every new button, card, report,
or script becoming its own "persona" or "nano-agent".

This manifest is the brake. It defines a small, fixed governance vocabulary and
the rules for when a *new* persona is allowed. If a future idea cannot satisfy
the anti-inflation rules below, it is a button, an artifact, or a function —
not a persona.

GOV.1 is documentation and governance only. It introduces no new agent, no
nano-agent execution, no model call, no worker launch, no patch/apply, no
validation run, no Dream or Project Evolution execution, no webhook/network
behavior, no lesson promotion, no proposal import, no database migration, no new
backend route, and no new UI panel.

---

## 1. Architecture layers

C.A.T.T.U.S is described with four architecture layers. A user action or
implementation detail is **not** a layer and **not** a persona.

| Layer | Meaning | Example |
| --- | --- | --- |
| **City** | The whole AI operating system / ecosystem. | The future "AI city"; C.A.T.T.U.S is one district inside it. |
| **District** | A professional domain. | Coding, Admission Guidance, Research, Teacher. |
| **Persona** | A governance role used inside a district. | Explorer, Verifier, Arbiter, Courier, Human. |
| **Artifact** | A bounded object passed between roles. | Goal Brief, Worker Assignment, Driver Decision, proposal, lesson, review. |

A **button / route / function** is a user action or an implementation detail.
It is **not** a persona. Adding a button never adds a persona.

> **The rule:** District = profession. Persona = governance role. Artifact = transferable record. Button = user action.

---

## 2. Allowed governance personas

There are exactly five governance personas. Districts reuse these roles; they do
not invent new ones (see §4 and §3). Each persona has distinct permissions and
distinct forbidden actions.

### Explorer

- proposes ideas
- combines lessons
- suggests experiments
- may generate hypotheses
- **cannot** apply patches
- **cannot** promote lessons
- **cannot** claim truth without evidence
- **cannot** bypass Verifier / Arbiter / Human

### Verifier

- checks evidence
- detects missing validation
- enforces safety gates
- reviews benchmark / visual / lesson evidence
- can block unsafe claims
- **cannot** invent goals
- **cannot** auto-approve
- **cannot** silently mutate artifacts into accepted truth

### Arbiter

- routes tasks
- chooses mode recommendations
- recommends model / vehicle level
- decides which gate is needed next
- can escalate to human review
- **cannot** silently execute
- **cannot** silently use expensive / strong models
- **cannot** approve itself

### Courier

- carries bounded artifacts or review tasks
- can summarize, compare, classify, or review
- can propose links between artifacts
- must have low TTL / bounded scope
- **cannot** spawn more couriers
- **cannot** patch, apply, promote, call tools freely, or run uncontrolled loops

### Human

- final activation gate
- approves real-world / repo mutation
- may reject or redirect the system
- is the accountable operator, **not** an automatic truth source
- evidence remains the judge

> **Human approval is the final activation gate, but evidence remains the judge.**

---

## 3. Anti-inflation rules

Most new ideas are **not** personas. Do **not** create a new persona for:

- a button
- a UI card
- a report
- a checklist
- a formatting function
- a single route
- a temporary script
- a benchmark case
- a memory note

A new persona is allowed **only** if it has all of:

- a distinct responsibility
- distinct permissions
- distinct forbidden actions
- a distinct artifact boundary
- a failure mode worth governing

If a proposed "persona" fails any one of these, it is a button, an artifact, or
a function — describe it as such and stop. Expanding the role set requires a
manifest update (see the forbidden transition `District → create new persona
without manifest update` in §6).

---

## 4. District reuse

Every district may reuse the same five governance roles. Districts do **not**
create unlimited new inner personas — they reuse Explorer / Verifier / Arbiter /
Courier / Human with **domain-specific artifacts and rules**.

### Coding District (current C.A.T.T.U.S)

- **Explorer** = Dream / hypothesis generator
- **Verifier** = patch safety / benchmark / visual evidence / lesson quality
- **Arbiter** = Driver / Mode Router / Mayor Mode
- **Courier** = Worker Assignment / External Queue item

### Admission Guidance District

- **Explorer** = market / trend hypothesis
- **Verifier** = source / evidence / uncertainty checker
- **Arbiter** = update / review routing
- **Courier** = bounded market scan artifact

The same role names, different artifacts and laws. A district that believes it
needs a brand-new persona must instead either (a) map the need onto an existing
role, or (b) update this manifest first.

---

## 5. Future parking lot — Neural Lesson Graph (not active)

The following is a **parked idea**, recorded so it does not turn into
uncontrolled architecture today:

- **Lesson-as-neuron** — a lesson behaves like a knowledge node.
- **Anti-lesson-as-inhibition** — a blocked lesson behaves like an inhibitory node.
- **Evidence / benchmark links as grounding edges** — links between lessons and
  the evidence that grounds them.
- **Courier / nano-agent as a bounded activation pulse** — a low-TTL Courier
  that touches a small neighborhood, never an autonomous loop.

**Boundary:** This is **not** active implementation. A future phase would be
**report-only**, e.g. **GOV.2 — Neural Lesson Graph Activation Preview**.
**No autonomous nano-agent execution is allowed by GOV.1.**
See the matching Parking Lot note in the
[operating roadmap](AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-07.md).

---

## 6. Forbidden and allowed transitions

These transitions express the persona permissions as movement rules. They mirror
the README [Operating Modes / Permission Matrix](../../README.md) forbidden/
allowed transitions at the persona level.

### Forbidden

- Explorer → patch apply ❌
- Explorer → lesson promotion ❌
- Courier → spawn courier ❌
- Courier → patch / apply ❌
- Verifier → invent new objective ❌
- Arbiter → silently execute ❌
- District → create new persona without manifest update ❌
- Human approval → convert an unsupported claim into truth ❌

### Allowed

- Explorer → proposal artifact ✅
- Verifier → evidence review / blocker ✅
- Arbiter → route recommendation ✅
- Courier → bounded artifact transfer / review ✅
- Human → approve / reject / defer ✅
- Evidence → update confidence ✅

---

## What GOV.1 does not add

GOV.1 is docs-only. It deliberately adds **none** of the following:

- new agents
- nano-agent execution
- model calls
- worker launch
- patch / apply
- validation execution
- Dream execution
- Project Evolution execution
- webhook / network behavior
- lesson promotion
- proposal import
- database migration
- new backend route
- new UI panel

If a future feature needs any of that power, it must pass through a stricter
mode or gate — exactly as the README **power leakage rule** requires — and, if it
needs a new persona, it must update this manifest first.
