# Architecture 131-F — Windows Robinhood OAuth persistence and callback

## Source-only contract

This checkpoint implements inert Windows composition for the accepted 131-E
OAuth factory. Construction does not read credentials, open a browser, bind a
listener, authenticate, contact Robinhood, or call an MCP tool. No real OAuth
grant or brokerage request is authorized by this source checkpoint.

The application transport remains the three existing review/read methods.
Neither `sdk_transport.py` nor the package initializer changes. The composition
function imports the existing factory inside the function, avoiding a new
package import cycle.

The SDK model/protocol contract follows the [official MCP OAuth client
documentation](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/client/oauth-clients.md)
and [shared authentication models](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/shared/auth.py).

## Windows persistence boundary

`WindowsOAuthStorage` implements the four async MCP TokenStorage methods.
`WindowsCredentialApi` uses only exact `CredReadW` / `CredWriteW` generic
credentials with local-machine persistence in the current Windows user account:

```text
AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1
AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1
```

Local-machine persistence is the Credential Manager persistence setting; it
does not make these credentials available to all users. The Robinhood OAuth
store is independent of the Alpaca C3 credential reader and does not assume or
reuse a Trading SID. Account placement and operator identity remain separate
future host-qualification decisions.

There is no credential enumeration, environment lookup, .env, repository/config
file, plaintext persistence, alternate target, record splitting, or fallback.
The native and protocol boundaries reject malformed data using fixed local
messages, suppressing upstream exception details.

The entire SDK token/client-information model is serialized with
`model_dump_json()` and validated with the full SDK model on reads and writes.
No persistence field whitelist drops client registration metadata, issuer,
expiry, refresh-token, or client-secret state. Models returned by this helper
inherit the SDK schemas with redacted repr/str; their explicit data/JSON
serialization still contains secrets and is only for trusted SDK/storage use.

Missing credentials return None. Orphaned tokens fail closed from either getter;
token writes require an existing valid client registration. Malformed existing
records are errors rather than missing state. There is no transactional pair
write: client registration is written before tokens, and a failed token write
leaves registration available for the SDK's subsequent flow.

The Windows generic credential blob limit is **2,560 bytes per record**, measured
in the serialized UTF-8 bytes. Oversized token or registration state raises
`WindowsOAuthStorageSizeError` without writing any part of it. Real Robinhood
record sizes have not been qualified. If the limit proves inadequate, protected
DPAPI persistence requires a new architecture decision; this implementation
cannot silently adopt it.

Read allocations are copied directly into bytearrays; valid native blob memory
is zeroed before CredFree, including validation failures. Write buffers use
mutable ctypes views and are zeroed on native completion/failure. Storage-owned
copies are cleared in finally blocks. Invalid native ranges are never dereferenced
or zeroed blindly and the native allocation is still freed.

Python immutable serialized strings and Pydantic model strings cannot be
guaranteed to be zeroized. Redaction and bounded lifetime reduce accidental
exposure; they do not constitute a process-memory erasure guarantee.

## Loopback callback boundary

`LoopbackOAuthCallback` accepts only a canonical explicit IPv4 redirect:

```text
http://127.0.0.1:<port>/<non-root-path>
```

The port is 1–65535. No localhost alias, IPv6, wildcard, LAN address, userinfo,
query, or fragment is accepted. Listener construction happens in
`redirect_handler`, before the injected browser opener is invoked. Production
uses Python's standard browser-opening facility; tests inject an opener.

The callback is exact GET path plus one exact Host header containing the
configured IPv4 address and port. Only HTTP/1.0 and HTTP/1.1 are accepted.
Request lines are limited to 4,096 bytes, headers to 8,192 aggregate bytes and
32 fields, and query parsing to 16 fields. Request bodies, transfer encoding,
duplicate Host headers, malformed text/percent encoding, extra query fields,
and wrong method/path/host fail closed. The listener uses a bounded stream
reader and an independent flow deadline, including incomplete/slow requests.

Successful callbacks contain exactly one nonempty code, exactly one nonempty
state, and zero or one nonempty iss. Standard query decoding preserves their
exact values, including spaces and issuer trailing slashes. The returned object
is an SDK AuthorizationCodeResult subclass with redacted repr/str.
This helper does not derive or replace state/issuer and does not decide whether
they match the provider's expectations: the SDK retains that validation.
OAuth error callbacks return a sanitized local rejection.

A helper admits one active flow and one callback waiter. Concurrent redirects
or waiters are rejected. The timeout defaults to 120 seconds and is bounded
above by 300 seconds. A background flow owner closes the listener and accepted
connections even if the callback waiter is never invoked. Success, rejection,
timeout, browser failure, and cancellation all close server resources.
Outstanding client transports close before waiting for the server shutdown.

The browser opener runs in a worker to keep the flow deadline responsive.
Python cannot forcibly stop an already-running browser-opening OS call on
cancellation; callback resources still close and no late callback is accepted.

There is no authorization-URL persistence or request logging. Browser HTTP
responses contain only fixed success/failure instructions, never callback
parameters or upstream error text, and carry no-store/connection-close headers.

## Composition and gates

`create_windows_robinhood_oauth_factory(...)` wires Windows storage and the two
loopback methods into `create_robinhood_oauth_factory(...)`. The optional MCP
model imports remain lazy.

Registered source checkpoint:

```text
arch131-robinhood-oauth-windows
remote branch = feature/robinhood-review-paper-mode
preflight = None
execute = None
```

The Windows GitHub workflow runs it after the existing Architecture-131 gates.
AST-based authority checks freeze targets, generic/native persistence bindings,
loopback bind, and source-only registration, and reject enumeration, fallback,
unreviewed imports, generic tool callers, and brokerage mutation tool names.
Mutation tests prove meaningful boundary drift fails.

Focused tests use native/API doubles and synthetic loopback callbacks. They never
access real Credential Manager records, open a real browser, or contact Robinhood.
An optional real-SDK model round-trip test runs when the MCP extra is installed.

The unified verify command retains its clean-worktree admission requirement.
During uncommitted implementation it stops at that admission gate; focused tests,
Ruff, diff checks, and the structural authority test provide local source evidence.
After separate source review/commit approval, run the same checkpoint on the clean
reviewed source. Canonical status/handoff closeout follows acceptance.
