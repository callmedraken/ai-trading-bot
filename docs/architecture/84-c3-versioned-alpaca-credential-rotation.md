# C3 versioned Alpaca credential rotation

## 1. Scope and decision

This architecture defines the credential-rotation boundary required after the
August 26, 2026 C3 provider lineage returned a durable, confirmed HTTP 401.

The observed failure does not authorize a retry and does not weaken the existing
C1/C2/C3 effect-ordering, provider-call-budget, child-containment, or recovery
contracts. The consumed `/v1` credential references are treated as uncertain and
quarantined for future provider effects.

The next production credential policy is versioned rather than mutable:

```text
credential policy:
  windows-credential-manager-alpaca-market-data/v2

credential targets:
  AITradingBot/MarketData/Alpaca/ApiKeyId/v2
  AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
```

The existing `/v1` targets remain historical inputs to already-consumed
lineages. They must not be overwritten, reused through fallback, or silently
aliased to `/v2`.

Production brokerage and real-money trading remain NO-GO. This milestone changes
only the C3 Alpaca market-data credential reference policy and the operator
cutover procedure.

## 2. Controlling predecessor contracts

Architectures 82 and 83 remain authoritative for C3 effect ordering, secret-free
parent operation, exact Trading-SID validation, one-shot provider transport,
child containment, evidence handling, and fail-closed recovery.

Their `/v1` credential target definitions remain the historical contract of the
E3.5 release source. Architecture 84 supersedes only the credential-policy and
credential-target values for a future certified release.

The following remain unchanged:

- C1 approved Trading account and SID;
- C2 schema and durable lifecycle semantics;
- C2 provider-call budget of one per claim;
- provider host, operation, and daily-snapshot request semantics;
- isolated-child-only production credential use;
- no environment, file, CLI, or alternate-store credential fallback;
- no automatic retry;
- no provider effect during credential provisioning or local credential
  attestation;
- no brokerage credential or order path.

## 3. Why rotation is versioned

The August 26 lineage proved that the `/v1` values were readable by the exact
Trading SID and structurally valid enough to reach the Alpaca HTTPS transport,
but Alpaca returned HTTP 401. The secret value cannot be positively reconciled
with the currently displayed dashboard key after the fact.

Overwriting `/v1` would destroy the distinction between:

```text
historical credential reference used by consumed lineages
and
new credential reference intended for future lineages
```

A versioned cutover preserves auditability and makes source, release, child
request, and operator evidence agree on which credential generation is in use.

## 4. Fixed `/v2` production contract

The future certified C3 release must hard-code exactly:

```text
C3_CREDENTIAL_POLICY_VERSION =
  windows-credential-manager-alpaca-market-data/v2

ALPACA_API_KEY_ID_CREDENTIAL_TARGET =
  AITradingBot/MarketData/Alpaca/ApiKeyId/v2

ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET =
  AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
```

These values remain nonsecret but are production authority material. They stay
bound into the existing provider launch plan and canonical child request.
Because the credential-policy version participates in the current deterministic
daily-snapshot request UUID material, the `/v2` release receives different C3
request identity material where that policy is semantic.

The C2 `capture_request/v2` payload and its digest are not expanded merely to
carry credential target names. Credential choice remains release-owned rather
than caller-owned.

No runtime switch, environment variable, config file, command-line option,
registry setting, database field, GUI control, or fallback list may select
between `/v1` and `/v2`.

## 5. `/v1` quarantine

After Architecture 84 acceptance:

- `/v1` is never used for a new real provider effect;
- `/v1` is not modified during `/v2` provisioning;
- `/v1` may be retained temporarily as historical operational evidence;
- no code may attempt `/v2` and then fall back to `/v1`;
- no code may compare secrets between versions during production capture;
- removal of `/v1`, if desired later, is a separate operator cleanup decision
  after `/v2` acceptance and is not required for this milestone.

## 6. Fresh-key generation gate

No fresh Alpaca pair is generated until the `/v2` architecture and operator
procedure are frozen. Generation is then performed once from the intended Alpaca
Trading API dashboard account.

The operator must keep both newly displayed values local. Neither the key ID nor
the secret is pasted into ChatGPT, committed to Git, written to validation docs,
placed on a command line, or stored in a repository artifact.

Immediately while the newly generated pair is still available, the operator
creates a local nonsecret witness for each value using the fixed fingerprint
contract in section 7. The dashboard is then refreshed or revisited and the
operator confirms that the dashboard's current key ID is the just-generated key,
not an older remembered key.

Alpaca's published market-data guidance states that API keys are generated in
the dashboard and that a lost secret is handled by regenerating keys. Alpaca
also documents key/secret header authentication for Trading API market data.
Those provider facts motivate generation of a new pair rather than attempting
to infer the old secret.

## 7. Local credential witness contract

Credential freshness and provisioning identity are proven without network
traffic by comparing two independently obtained fingerprints:

1. fingerprints computed locally from the newly displayed dashboard pair before
   the values are discarded; and
2. fingerprints computed locally from the exact `/v2` Windows Credential Manager
   entries after provisioning under the Trading account.

The witness algorithm is:

```text
prefix = UTF8("AITradingBot/C3CredentialWitness/v1\0")
role   = UTF8("api_key_id") or UTF8("api_secret_key")
value  = exact UTF-8 credential bytes

fingerprint = SHA256(prefix || role || UTF8("\0") || value).hexdigest()
```

For each role the operator compares:

```text
fingerprint
UTF-8 byte length
```

The full credential value must never be printed by the witness procedure.
Fingerprints are comparison evidence, not authentication credentials and not
production authority. They must not be embedded into deterministic C2/C3
identities or provider requests.

The local dashboard-side fingerprint procedure must accept values through an
interactive input path that does not place the secret in shell history or
process arguments. The Credential Manager readback procedure must read only the
exact `/v2` targets, verify the exact Trading SID, compute the same witness, and
release the native credential entries before exit.

The two fingerprint/length pairs must match exactly before the credential
cutover is considered locally proven.

## 8. Meaning of "fresh" and "active"

This milestone uses three deliberately distinct states:

```text
FRESH_GENERATED
  A new key/secret pair was generated once in the intended Alpaca dashboard and
  dashboard-side witnesses were captured immediately.

LOCAL_EXACT_MATCH
  The exact `/v2` Credential Manager values read under the approved Trading SID
  reproduce both dashboard-side fingerprints and byte lengths.

DASHBOARD_CURRENT
  After generation/provisioning, the Alpaca dashboard still displays the
  just-generated key ID as the current key for the intended account/environment.
```

All three are mandatory before another production capture may even be
considered.

They do not claim to cryptographically prove that Alpaca's remote API will
accept the pair. Remote acceptance cannot be proven offline; it requires an
authenticated external request. Architecture 84 intentionally does not add a
second ad-hoc network/authentication path merely to probe credentials, because
that would broaden the reviewed secret/network boundary and create another
external-effect class.

Therefore the first future C3 capture using `/v2`, if separately authorized on a
new session/digest, remains the remote-acceptance proof. A separate remote auth
probe may be designed later only through an explicit architecture review and
would itself be treated as an external provider effect.

## 9. Provisioning boundary

Provisioning is an operator/deployment action, not a C3 runtime capability.

The operator provisions exactly two new Windows Generic Credentials under the
Trading account using the `/v2` target names. The existing requirements remain:

- exact target spelling;
- Generic Credential type;
- local-machine persistence compatible with the reviewed reader;
- nonempty exact UTF-8 value;
- no leading/trailing whitespace;
- no CR, LF, or NUL;
- no copy into repository files, `.env`, CLI arguments, or logs.

C3 runtime code still has no credential create/update/delete API.

## 10. Source and release cutover

The `/v2` target change is a production source change and must not be performed
by editing the deployed installation in place.

Required sequence:

```text
Architecture 84 + validation plan accepted
-> implement exact `/v2` policy/targets and tests
-> source certification
-> frozen wheel build and offline artifact verification
-> administrator runtime replacement using the existing sealed procedure
-> Trading RX republication
-> non-admin zero-provider preflight
-> generate one fresh Alpaca pair
-> capture dashboard-side fingerprints locally
-> provision exact `/v2` entries under Trading
-> read back `/v2` entries and compare fingerprints/lengths
-> refresh/revisit Alpaca dashboard and confirm current key ID
-> record only PASS/FAIL and nonsecret witness metadata locally
-> wait for a genuinely new XNYS session and planner clock eligibility
-> prove a fresh C2 request digest and zero durable lineage
-> separately review/authorize at most one provider effect
```

The credential pair may be generated after deployment because all pre-generation
release gates are zero-provider and do not require credential reads.

## 11. No same-lineage retry

Credential rotation does not authorize another attempt against the consumed
August 26 request/session.

The next real provider effect must use a genuinely new XNYS session and a fresh
C2 request digest with zero prior durable rows. The four consumed provider
lineages remain historical evidence and are never retried.

`session.state=OPEN` or `next_attempt_ordinal=1` on the August 26 session is not
provider authorization.

## 12. Compatibility and schema decision

Architecture 84 does not require a C2 SQL migration.

The existing child request already carries explicit credential policy and target
fields. A new credential-policy value therefore does not by itself require a new
child-request JSON schema or a new result schema. Implementation must update the
fixed accepted production values and affected deterministic vectors/tests while
preserving unrelated protocol semantics.

Historical terminal/cleanup evidence remains immutable and must continue to pass
current read-only production validation. No historical row is rewritten to say
it used `/v2`.

## 13. Acceptance conditions

The `/v2` rotation is not accepted until all of the following are true:

- source exposes only the exact `/v2` credential policy and target names for new
  production capture;
- `/v1` fallback is absent;
- affected canonical child-request and deterministic identity tests are updated
  deliberately;
- historical durable evidence validation remains green;
- source/artifact/deployment gates pass;
- user-side dashboard witness proves a newly generated pair;
- Trading-side `/v2` readback fingerprints and byte lengths match the dashboard
  witnesses exactly;
- the dashboard still shows the just-generated key ID as current;
- no credential value appears in console output, repository content, logs,
  command-line arguments, C2/C3 durable evidence, or ChatGPT conversation;
- no network/provider request occurs during fingerprinting/provisioning/readback;
- a future provider effect remains separately authorized and limited to one
  genuinely fresh session/digest.

Until those conditions are accepted, provider call #5 remains NOT AUTHORIZED.

## 14. Provider references

The operator procedure should be checked against current official Alpaca
material at execution time, especially:

- `https://docs.alpaca.markets/us/docs/getting-started-with-alpaca-market-data`
- `https://docs.alpaca.markets/us/docs/market-data-faq`

Architecture relies only on documented key/secret authentication and dashboard
key generation/regeneration behavior; it does not rely on undocumented dashboard
internals.
