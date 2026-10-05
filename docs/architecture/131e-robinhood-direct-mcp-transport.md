# Architecture 131-E — Direct Robinhood MCP Transport

## Decision

The Python application may connect directly to the official Robinhood Trading
MCP endpoint:

```text
https://agent.robinhood.com/mcp/trading
```

using the official MCP Python SDK over Streamable HTTP and standard MCP OAuth
discovery.

This checkpoint adds transport capability only. It does not authenticate to the
real Robinhood service during source certification and it does not place,
cancel, approve, decline, exercise, or otherwise mutate a brokerage order.

## Application allowlist

The direct transport implements the already accepted synchronous
`RobinhoodReviewReadTransport` contract and has exactly three public MCP
operations:

```text
review_equity_order
get_equity_quotes
get_equity_orders
```

There is no generic public `call_tool` method.

The server may advertise many more Robinhood tools. The application deliberately
does not surface them. Before every allowed tool call, the transport enumerates
the MCP tool inventory and proves all three required tools are currently
advertised.

## Connection and authentication

The production network path is:

```text
RobinhoodMcpStreamableHttpTransport
-> OAuthClientProvider
-> httpx2.AsyncClient
-> streamable_http_client
-> mcp.Client
-> list_tools
-> one allowlisted call_tool
```

OAuth configuration is source-owned except for injected token storage and the
human authorization callbacks.

The OAuth provider uses the fixed Robinhood endpoint for protected-resource /
authorization-server discovery. It does not hard-code Robinhood token or
authorization endpoints.

The initial redirect URI must be loopback HTTP:

```text
http://127.0.0.1:<port>/<callback>
or
http://localhost:<port>/<callback>
```

The OAuth token/client-registration store is injected. This checkpoint does not
write tokens to source, environment variables, repository files, or a plaintext
configuration.

## Blocking integration

The existing paper cycle is synchronous. The first direct transport therefore
opens one short-lived Streamable-HTTP MCP session per tool call and runs that
session through `asyncio.run`.

This is intentionally simple and deterministic for initial qualification.
Persisted OAuth storage prevents a normal token refresh from requiring a new
interactive grant on every connection.

The blocking transport refuses to run inside an already-running event loop.
A future optimization may add a persistent async session without changing the
three-tool application contract.

## Tool-call result policy

For every call:

1. enumerate MCP tools to exhaustion with bounded pagination;
2. require all three expected raw Robinhood tool names;
3. call only the exact method selected by the public wrapper;
4. require `is_error is False`;
5. require `structured_content` to be a mapping;
6. return a plain copied mapping to the existing typed parser.

Tool-error content is not promoted into authority. The transport raises a
sanitized local error instead.

Repeated pagination cursors, malformed inventories, missing required tools,
missing structured output, MCP tool errors, dependency absence, and active-loop
misuse all fail closed.

## Dependency boundary

The optional runtime extra is:

```text
robinhood-mcp
  mcp>=2.2,<3
  httpx2>=2.13,<3
```

The SDK imports are lazy. Ordinary development/source gates that do not execute
the network transport do not require the optional extra.

## Token persistence

Architecture 131-E accepts an injected MCP `TokenStorage`-compatible object but
does not implement persistent credential storage.

The first real authentication is blocked until a reviewed persistence choice is
made. The preferred Windows deployment direction is a Windows-backed credential
store rather than plaintext JSON.

## Source checkpoint

Registered source gate:

```text
arch131-robinhood-direct-mcp
```

The gate proves:

- the three raw tool names are the exact allowlist;
- the concrete source contains the expected official SDK/Streamable-HTTP
  bindings;
- no placement/cancellation/options/crypto order tool name appears in the
  transport source;
- no preflight or protected execute profile is registered;
- source-only tests use an injected test caller and never access the network.

## Next step

After source acceptance:

1. design/accept Windows-backed OAuth token persistence and local callback
   handling;
2. perform one explicit human-interactive authentication;
3. run read-only capability qualification;
4. verify `get_equity_quotes` and `get_equity_orders` only;
5. separately authorize the first `review_equity_order` paper-cycle test.

A review call is non-placement, but it is still an external brokerage request
and remains outside source-only certification.
