# MCP Inspector Sub-agent Shortcut

> Status: design approved 2026-05-22.
> Scope: local web shortcut for inspecting the repo's existing MCP servers.

## Goal

Add a compact MCP Inspector entry beside the Sub-agent audit shortcut so the
operator can intentionally inspect either existing C.A.T.T.U.S MCP server from
the web UI.

## Non-goals

- Adding, removing, or re-authorizing MCP tools
- Changing the read-only or artifact-write server allowlists
- Changing MCP audit behavior
- Hiding the distinction between the safer read-only server and the
  artifact-write server
- Expanding Sub-agent worker execution behavior

## UI Design

Keep `View MCP audit` in the Sub-agent header. Add a neighboring compact
`MCP Inspector` control with two explicit choices:

- `Inspect read-only MCP`
- `Inspect artifact-write MCP`

The choices are spelled out rather than collapsed into one ambiguous launch
button so the operator sees which MCP capability surface is being inspected
before a local process starts.

## Inspector Targets

Both choices launch/connect the official MCP Inspector to existing stdio server
entry points already present in the repo:

- read-only: `scripts/mcp_readonly_server.py`
- artifact-write: `scripts/mcp_artifact_write_server.py`

The artifact-write option must stay visibly labeled as artifact-write anywhere
it appears in the UI or response text.

## Web Boundary

The web app may add the minimum local route/action support needed to open MCP
Inspector for those two approved targets. Target selection must be explicit and
validated against those two server ids; arbitrary command input is not accepted
from the browser.

Inspector launch support is separate from MCP capability definition. It starts
or opens a local developer inspection flow and must not change server allowlists,
MCP audit events, subagent launch gates, or worker-run import behavior.

## Failure Handling

If Inspector cannot be launched because its runtime or dependencies are missing,
the web action returns a clear local error that names the selected Inspector
target. It does not silently fall back to another MCP server or broaden access.

## Testing

Add focused web coverage for:

- the new Sub-agent Inspector control and its two labels
- successful target selection for the existing read-only and artifact-write
  launchers without executing arbitrary browser-supplied commands
- rejection of unknown Inspector targets
- no regression to the existing MCP audit route and MCP server allowlist tests
