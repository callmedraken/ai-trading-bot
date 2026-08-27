# C3 pre-first-effect credential staging amendment

## 1. Scope and decision

This document is a narrow amendment to Architecture 84,
`84-c3-versioned-alpaca-credential-rotation.md`.

Architecture 84 remains authoritative for the `/v2` production credential
policy, fixed target names, isolated-child credential use, local witness
algorithm, no-fallback rule, provider-effect ordering, and separate provider-call
authorization.

This amendment changes only the operator treatment of a credential pair that was
provisioned into the fixed `/v2` targets and then superseded in the Alpaca
dashboard **before any real provider effect used `/v2`**.

The decision is:

```text
before first /v2 provider effect:
  /v2 Credential Manager contents are staging state and may be discarded and
  reprovisioned through the reviewed two-target operator procedure

after first /v2 provider effect:
  /v2 becomes immutable historical credential-reference state; any later
  credential rotation requires a new credential-policy/target version
```

This amendment does not authorize provider call #5.

## 2. Preconditions for pre-effect restaging

Restaging `/v2` is allowed only when all of the following are true:

- the certified/deployed C3 runtime still hard-codes exactly the Architecture-84
  `/v2` credential policy and targets;
- no real provider effect has ever been executed from a `/v2` C3 launch plan;
- no durable consumed provider lineage claims use `/v2` credential-policy
  semantics;
- the previously provisioned `/v2` pair has been superseded or otherwise
  abandoned before provider use;
- the operator remains under the exact approved non-administrator Trading SID;
- the replacement operation itself performs no provider/network request and
  launches no production capture child.

If any `/v2` provider effect has occurred, these preconditions are false and
`/v2` must not be changed.

## 3. Atomic pair-generation rule

The key ID and secret are one credential generation and must never be treated as
independently replaceable production state.

A restaging operation must therefore:

1. verify both exact `/v2` targets refer to the abandoned staging generation;
2. delete both `/v2` targets as one reviewed operator maintenance operation;
3. verify both targets are absent;
4. provision both values from one current Alpaca key generation;
5. if only one new target is created before an error, clean up every `/v2` target
   created by that operation and stop;
6. never leave a deliberately accepted mixed-generation key/secret pair.

No overwrite-in-place correction of just one `/v2` target is accepted.

The operation is pair-atomic at the operator-procedure level; Windows Credential
Manager does not provide a two-entry transaction, so fail-closed cleanup and
post-operation absence/exact-match checks are required.

## 4. Witness semantics after restaging

Any witness evidence from the abandoned `/v2` staging pair is superseded and
must not be carried forward as acceptance evidence.

The replacement generation must independently satisfy all Architecture-84
witness gates again:

```text
FRESH_GENERATED=PASSED
LOCAL_EXACT_MATCH=PASSED
DASHBOARD_CURRENT=PASSED
```

Only the replacement generation's fingerprint/UTF-8-length pairs are relevant to
the eventual pre-effect review.

Raw key IDs and secrets remain local and must not be copied into Git, ChatGPT,
logs, validation documents, command arguments, or durable C2/C3 evidence.

## 5. Immutability boundary

The first real provider effect launched under `/v2` permanently closes the
pre-effect staging window, regardless of whether the effect succeeds, fails,
blocks after the provider fence, or produces ambiguous external-effect evidence.

After that point:

- `/v2` targets must not be overwritten, deleted for replacement, or reused for
  a different Alpaca pair;
- a future rotation must introduce a new fixed credential-policy/target version;
- consumed provider evidence continues to identify the release-owned `/v2`
  credential reference without mutable aliasing.

This preserves Architecture 84's auditability objective for every actual provider
lineage while avoiding an unnecessary source/release rotation for an abandoned
pre-use staging pair.

## 6. Unchanged security and authority boundaries

This amendment does not change:

- C1/C2/C3 effect ordering or provider-call budget;
- the four already-consumed `/v1` provider lineages;
- C2 schema, production SQL, planner clock, request semantics, provider host,
  feed, or transport behavior;
- hard-coded `/v2` production targets or credential-policy value;
- absence of `/v1` fallback or runtime credential selection;
- exact Trading-SID enforcement;
- Generic Credential / local-machine persistence / UTF-8 credential checks;
- isolated-child-only production credential use;
- requirement for a fresh session/digest and zero durable lineage before any
  future provider effect;
- requirement for explicit user authorization of at most one future provider
  effect.

Production/live trading remains NO-GO.

## 7. Current application

The first `/v2` pair was locally witnessed and provisioned after the accepted
E3.6 zero-provider preflight, then the Alpaca dashboard key was regenerated again
before any `/v2` provider effect occurred.

That first `/v2` pair is therefore classified as:

```text
SUPERSEDED_BEFORE_FIRST_PROVIDER_EFFECT
```

Its prior `FRESH_GENERATED`, `LOCAL_EXACT_MATCH`, and transient
`DASHBOARD_CURRENT` observations are not sufficient for provider-call review.
The deployed `/v2` runtime remains accepted; only the two Credential Manager
staging entries require reviewed restaging.

Provider call #5 remains NOT AUTHORIZED.
