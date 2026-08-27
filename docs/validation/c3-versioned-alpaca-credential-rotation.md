# C3 versioned Alpaca credential rotation validation plan

## 1. Purpose

This plan validates Architecture 84,
`docs/architecture/84-c3-versioned-alpaca-credential-rotation.md`.

The objective is not merely to replace one secret with another. The evidence
must prove that a newly generated Alpaca key/secret pair is bound to a new fixed
`/v2` credential policy, is provisioned exactly into the Trading account's
Windows Credential Manager entries, can be verified locally without exposing
secret material or contacting Alpaca, and cannot fall back to the uncertain
`/v1` pair.

Provider call #5 is outside this validation plan and remains NOT AUTHORIZED.

## 2. Frozen target values

Implementation and acceptance tests must freeze exactly:

```text
credential policy:
  windows-credential-manager-alpaca-market-data/v2

key target:
  AITradingBot/MarketData/Alpaca/ApiKeyId/v2

secret target:
  AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
```

Tests must reject `/v1`, `/v3`, case variants, trailing/leading whitespace,
alternate separators, caller-selected names, environment overrides, and target
fallback lists on the future production capture path.

## 3. Source-impact gate

Before implementation, inspect every use of:

- `C3_CREDENTIAL_POLICY_VERSION`;
- `ALPACA_API_KEY_ID_CREDENTIAL_TARGET`;
- `ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET`;
- provider launch-plan construction;
- isolated child request construction/serialization/parsing;
- deterministic daily-snapshot request-ID vectors;
- Windows Credential Manager reader tests;
- production child tests;
- production composition tests;
- release/deployment smoke tests that assert credential-policy values.

The implementation must remain narrowly scoped. It must not change C2 request
schema, SQL, provider host/query/feed, retry authority, planner clock semantics,
native process ordering, or snapshot verification/publication semantics.

## 4. Deterministic contract gate

Focused tests prove:

- the provider launch plan fixes credential policy `/v2`;
- the child request fixes both `/v2` targets;
- canonical child request serialization contains exactly those values;
- parsing rejects an otherwise valid request carrying either `/v1` target;
- parsing rejects mismatched key/secret target generations;
- callers cannot override target names;
- the daily-snapshot request UUID changes according to the existing versioned
  material contract because credential-policy version is semantic;
- C2 `capture_request/v2` canonical bytes/digest remain unchanged for identical
  caller-safe capture intent;
- unrelated deterministic snapshot/domain identities are unchanged.

Any accidental change to C2 request bytes, SQL, provider descriptor, or output
policy is a blocker.

## 5. Historical compatibility gate

The four consumed real-provider lineages remain immutable.

Read-only authority validation must continue to accept their durable evidence,
including historical schema-1 and schema-2 C3 evidence where already supported.
No migration or rewrite may replace historical `/v1` meaning with `/v2`.

The August 26 lineage remains permanently consumed:

```text
request digest:
cccf56d1361ee4df8cf34745f68b32b29c52efdaaa80d2a02d4a32323dedce7f

terminal:
FAILED / CONFIRMED / HTTP_FAILED / 401
```

Credential rotation must not make that lineage retryable.

## 6. Credential-reader gate

Injected credential-reader tests prove that the future production reader:

- performs exact Trading-SID verification before `CredReadW`;
- reads `/v2` key target exactly once;
- reads `/v2` secret target exactly once;
- never reads `/v1` on success or failure;
- never enumerates Credential Manager;
- never creates, updates, or deletes credentials;
- preserves existing type/persistence/blob/UTF-8/whitespace/CR/LF/NUL checks;
- releases every acquired native credential exactly once;
- emits no secret-bearing exception or representation.

A missing or malformed `/v2` entry must produce the existing credential failure
behavior. It must not trigger `/v1` fallback.

## 7. Source certification gate

After implementation and exact-diff review:

1. run focused C3 planning/protocol/credential/child/composition tests;
2. run Ruff check and format check on touched Python files;
3. run `git diff --check`;
4. after the final implementation tree is accepted, run the full repository
   regression once;
5. verify frozen production SQL is byte-for-byte unchanged unless a separately
   approved architecture change explicitly says otherwise.

The full-suite result belongs to source certification, not iterative development.

## 8. Artifact and deployment gate

Build a new frozen wheel from the certified `/v2` source using the established
offline export/build procedure. Reconcile wheel payloads to the exact source,
verify package metadata and frozen SQL, then deploy through the existing sealed
runtime replacement procedure.

The deployment sequence remains:

```text
runtime quiescent
-> revoke Trading RX
-> offline exact-wheel replacement
-> installed payload verification
-> semantic smoke / SQL / authority verification
-> owner/ACL normalization and seal
-> republish Trading RX
-> verify inherited RX topology
```

No credential generation/read and no network/provider request occurs during
artifact build or administrator deployment.

## 9. Zero-provider `/v2` runtime preflight

Under the exact non-administrator Trading token, prove the installed runtime
contains the `/v2` policy/targets and rejects alternate targets without reading
Credential Manager.

This preflight must explicitly report:

```text
credential read: false
network operation: false
production child launch: false
authority database mutation: false
provider request: false
```

Do not generate the fresh Alpaca pair until this release/deployment gate is
accepted, so the pair is as fresh as practical when provisioned.

## 10. Dashboard-side fresh-generation witness

After the `/v2` runtime is deployed and zero-provider preflight passes:

1. operator opens the intended Alpaca Trading API dashboard account;
2. operator generates/regenerates one new key pair once;
3. while both new values are available, operator runs the approved local
   non-network fingerprint procedure through interactive input;
4. the procedure outputs only the domain-separated SHA-256 fingerprint and
   UTF-8 byte length for `api_key_id` and `api_secret_key`;
5. operator does not paste or save the raw values into ChatGPT, Git, shell
   history, scripts, `.env`, logs, or validation documents;
6. operator retains the two fingerprint/length pairs locally until the
   Credential Manager readback comparison is complete.

The exact witness algorithm is frozen by Architecture 84.

A screenshot or memory of the key ID alone is not sufficient evidence that the
secret being provisioned belongs to that key.

## 11. `/v2` provisioning gate

While operating as the approved Trading account, provision exactly two Windows
Generic Credentials:

```text
AITradingBot/MarketData/Alpaca/ApiKeyId/v2
AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
```

The values must be the just-generated dashboard pair. The `/v1` entries are not
edited or deleted.

Before saving each credential, verify the exact target spelling. After
provisioning, do not infer success from the Credential Manager UI alone.

## 12. Trading-side local readback witness

Run the approved one-shot, zero-network Credential Manager witness procedure
under:

```text
DESKTOP-I4DOKM7\Trading
SID S-1-5-21-1397534616-3988210162-180023805-1009
non-administrator token
```

The procedure must:

- verify the exact token SID before credential access;
- call `CredReadW` only for the exact two `/v2` targets;
- validate Generic Credential type and required persistence;
- validate the same credential string rules as production;
- compute the Architecture-84 domain-separated witness inside the process;
- print only fingerprints, UTF-8 byte lengths, target-version labels, and
  PASS/FAIL status;
- never print raw key/secret values;
- never place raw values in command arguments or environment variables;
- clear/release native buffers according to the reviewed procedure;
- perform no network operation;
- perform no authority database mutation;
- launch no production capture child;
- perform no provider request.

The dashboard-side and readback witness pairs must match exactly for both roles.
Any mismatch is a hard stop: delete/recreate only the new `/v2` entry through a
reviewed operator correction; never test the mismatch against Alpaca.

## 13. Dashboard-current gate

After successful local readback comparison, revisit or refresh the Alpaca
dashboard and confirm the current displayed key ID is still the just-generated
key whose dashboard-side witness was captured.

Record only:

```text
FRESH_GENERATED=PASSED
LOCAL_EXACT_MATCH=PASSED
DASHBOARD_CURRENT=PASSED
```

Raw credentials are not recorded.

This proves the operator has a freshly generated pair, has provisioned that exact
pair locally, and sees the generated key as current in the provider dashboard.
It does not claim remote API acceptance, because no authenticated request has
occurred.

## 14. No ad-hoc remote auth probe

Do not use curl, PowerShell web requests, an SDK, a browser extension, a temporary
script, the Trading API `/v2/account` endpoint, or an alternate market-data call
to test the new secret before the reviewed C3 gate.

Such a test would be a real authenticated external effect and would create a
second secret/network execution path outside the reviewed C3 boundary.

If a future need for remote credential validation before capture is strong enough
to justify that new effect class, design it separately. It is not silently
included in Architecture 84.

## 15. Provider pre-effect gate after rotation

Only after source/deployment and all three credential witness states are
accepted may planning begin for a future real provider effect.

The candidate must use the next genuinely new XNYS session that satisfies the
existing New-York-calendar-date rollover rule. Before authorization, prove:

- exact caller-safe request shape;
- expected authorized XNYS session;
- deterministic C2 request digest;
- digest differs from all four consumed lineages;
- zero durable rows for that digest in `sessions`, `attempts`,
  `provider_call_claims`, `launch_reservations`, and `terminals`;
- no Credential Manager read/network/provider effect during planning/freshness;
- the local `/v2` witness evidence remains accepted;
- provider-call authorization count remains zero until the user explicitly
  authorizes one call.

## 16. One-call acceptance rule

A future provider effect, if separately authorized, is exactly one supervised C3
capture. Regardless of success, failure, block, or ambiguity, the authorization
is consumed on first execution and the command is never immediately rerun.

Afterward perform read-only durable inspection before any further action.

A successful remote result must still pass the existing complete C3 chain:
provider response -> child acceptance -> staged canonical bytes -> independent
parent verification -> publication -> terminal -> selection.

## 17. Required operator evidence before provider call #5

The final pre-effect review must be able to state all of the following without
revealing credentials:

```text
V2_SOURCE_CERTIFIED=True
V2_ARTIFACT_ACCEPTED=True
V2_DEPLOYMENT_ACCEPTED=True
V2_ZERO_PROVIDER_PREFLIGHT=PASSED
FRESH_GENERATED=PASSED
LOCAL_EXACT_MATCH=PASSED
DASHBOARD_CURRENT=PASSED
V1_FALLBACK_PRESENT=False
NEW_SESSION_CLOCK_ELIGIBLE=True
NEW_DIGEST_DURABLE_COUNT=0
REAL_PROVIDER_EFFECTS_ALREADY_CONSUMED=4
PROVIDER_CALL_5_AUTHORIZED=False
```

Only a subsequent explicit user authorization may change the last line.

## 18. Current provider documentation check

Before generation/provisioning, re-check current official Alpaca documentation.
The present architecture was based on current Alpaca guidance that market-data
Trading API authentication uses `APCA-API-KEY-ID` and
`APCA-API-SECRET-KEY`, that keys are generated from the dashboard, and that a
lost secret is handled by regenerating keys.

Current references:

- `https://docs.alpaca.markets/us/docs/getting-started-with-alpaca-market-data`
- `https://docs.alpaca.markets/us/docs/market-data-faq`

If Alpaca changes its credential model before execution, stop for architecture
review rather than adapting the operator procedure ad hoc.
