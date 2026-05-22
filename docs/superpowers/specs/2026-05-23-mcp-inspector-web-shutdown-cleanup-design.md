# MCP Inspector Web Shutdown Cleanup

> Status: design approved 2026-05-23.
> Scope: stop MCP Inspector sessions when the local web UI is stopped.

## Goal

Link MCP Inspector lifetime to the local web UI shutdown path so pressing
`Ctrl+C` in the web terminal closes any MCP Inspector process on the machine.

## Non-goals

- Changing the existing Inspector target list or Inspector launch route behavior
- Changing MCP server allowlists, MCP audit behavior, subagent gates, or worker
  run import behavior
- Stopping arbitrary `node`, `npx`, Python, or browser processes
- Adding new MCP tools or running subagents automatically

## Shutdown Behavior

The web runner owns shutdown cleanup. When the Flask web UI exits from its
terminal shutdown path, including `Ctrl+C`, it attempts to find and terminate
MCP Inspector processes that are running on the machine.

The cleanup is intentionally broader than the web app's own launched-process
tracking. If an MCP Inspector session was started elsewhere but matches the
Inspector command signature, web shutdown may close it too.

## Process Selection

Match MCP Inspector narrowly by its official command/package signature, such as
the `@modelcontextprotocol/inspector` launch token. Do not terminate processes
only because they are `node`, `npx`, Python, or happen to expose a local port.

When a matching Inspector is found, terminate the Inspector process tree so its
stdio MCP server child exits with it rather than being left detached.

## Failure Handling

Inspector cleanup is best effort during shutdown. A missing process-inspection
capability, an already-exited process, permission denial, or a termination
failure should not prevent the web UI from exiting. Failures may be reported in
terminal output if they help local diagnosis.

## Testing

Add focused coverage that:

- accepts a command line that clearly identifies MCP Inspector
- rejects unrelated `node`, `npx`, Python, and local-port-looking processes
- verifies the web shutdown path requests Inspector cleanup without killing
  real processes in tests
- keeps existing Inspector launch route and MCP/UI tests passing
