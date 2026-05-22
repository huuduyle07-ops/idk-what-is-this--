# Mayor Mode Sub-agent UI Polish

> Status: design approved 2026-05-22.
> Scope: Memory tab Sub-agent presentation only.

## Goal

Make the Mayor Mode handoff cards and Worker Runs surfaces visually consistent
with the existing dark Memory tab while clarifying which handoff action is a
safe command preview path and which action may spend external agent quota.

## Non-goals

- Changing Flask routes, worker-run import behavior, audit logic, or backend
  handoff execution behavior
- Adding MCP tools or automatically running subagents
- Redesigning the broader Memory tab

## UI Design

The existing Sub-agent grouping remains intact. Handoff and Worker Runs cards
move from light inline card styling to dark-theme CSS classes that reuse the
panel's current visual language: dark surfaces, clear low-contrast borders,
readable secondary metadata, and compact spacing suited to the Memory tab.

Handoff cards keep the title and status badge in the header row. The status
badge stays visible at the right edge of the card, and worker, task, and created
metadata remain legible below the title. Card actions gain clearer visual
meaning:

- Rename the dry-run button to `Copy command` while preserving its existing
  dry-run handler and route behavior.
- Rename the execution button to `Run subagent in temp clone`.
- Style the execution button as a warning outline action because it can consume
  Claude, Codex, or Gemini quota.

Worker Runs cards and expanded detail surfaces receive matching dark card
treatment so populated worker-run content does not reintroduce the same bright
surface contrast problem. Their view and import controls keep existing
behavior.

The Sub-agent header gains a small `View MCP audit` link to
`/mcp/audit?limit=10`. Worker Runs uses the requested empty-state copy:
`No worker runs yet. Run a handoff in a temp clone to create .agent/worker_runs/.`

## Implementation Boundary

Changes stay in the web template/CSS surface:

- `web/templates/index.html` updates labels, link markup, empty-state copy, and
  emitted card class names.
- `web/static/style.css` owns card, metadata, badge, action-row, warning-outline
  button, header-link, and worker-run detail styling.

No backend handlers, route response shapes, MCP audit logic, worker-run import
logic, or subagent launch conditions change.

## Testing

Add focused template coverage for the requested UI contract:

- the Sub-agent audit link
- the renamed handoff actions
- the new Worker Runs empty-state copy
- dark-theme class hooks for emitted handoff and worker-run surfaces

Run the relevant web/template tests and the existing handoff and worker-run
route tests after the CSS/template change to confirm the presentation update
does not change route behavior.
