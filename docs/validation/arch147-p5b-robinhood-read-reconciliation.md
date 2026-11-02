# Architecture 147 P5B-lite — source validation

All implementation tests use synthetic MCP/account/portfolio/position/quote/
order responses. No actual preflight, OAuth factory invocation, Credential
Manager read, provider call, brokerage operation or production launch is part
of implementation, admission or GitHub CI. Production state is never created.

Focused modules cover the exact five-method read facade, absent mutation/review/
generic methods, fail-closed private dispatch, required read discovery, repeated
discovery cursors, inert composition and sanitized failures; frozen historical
131 tool semantics; unique canonical account and deterministic fingerprint;
strict portfolio/position/SPY data; existing positions/orders as observations;
bounded pagination and zero order attribution; deterministic frozen snapshots;
paper-authority separation; preflight zero counts, sanitized exceptions,
read-only production identities and change detection; cached Qt status; source
admission before provider and create-only attempt/evidence writes.

Run affected tests with the existing project interpreter, `-B -m pytest -q
-p no:cacheprovider`, a fresh GUID basetemp below
`F:\AI\temp\pytest\arch147-p5b-<GUID>`, and synthetic collaborators only.
The registered P5B test inventory includes retained desktop paper B1/B2,
relevant GUI and Robinhood public-boundary tests, Architecture 131 authority,
current/historical runner and source-authority checks. Current route changes
also require retained runner/CI/historical reconstruction regressions and the
prepublication infrastructure coherence bundle.

Complete whole-root `ruff check --no-cache .`, `ruff format --check --no-cache
.`, `git diff --check`, current/routed authority, historical reconstruction and
both publication contexts before the single unpublished atomic candidate.
Then `ops.ps1 admit` must prove FEATURE=PASS, PROSPECTIVE_DEVELOP=PASS and
IDENTITY_STABLE=True on that exact clean HEAD/tree before one ordinary push.
Canonical FULL is GitHub-owned: source-static, active-tests, broad-1 through
broad-7 and source-gates must reach terminal success. Do not run FULL locally
or rerun unchanged CI. Published failed evidence remains immutable.

Exact final source, test totals, admission evidence and terminal run/attempt
belong in the implementation handoff. This document does not claim pending
certification or source acceptance. No merge is authorized to the implementation
agent. ChatGPT owns exact-source review and integration readiness; only after
accepted develop integration will it issue the one protected read-only preflight.
No paper soak follows that baseline. P6 requires a separate reviewed source/
effect checkpoint with explicit live arming and hard live notional limits.
