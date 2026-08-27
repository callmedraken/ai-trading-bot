# C3 pre-first-effect credential staging validation

## 1. Purpose

This plan validates Architecture 84A,
`docs/architecture/84a-c3-pre-first-effect-credential-staging.md`.

It applies only to a superseded `/v2` credential pair that was staged in Windows
Credential Manager but never used by a real `/v2` provider effect.

Provider call #5 remains outside this procedure and is NOT AUTHORIZED.

## 2. Required precondition evidence

Before deleting or replacing `/v2`, the operator must establish all of the
following:

```text
V2_SOURCE_CERTIFIED=True
V2_ARTIFACT_ACCEPTED=True
V2_DEPLOYMENT_ACCEPTED=True
V2_ZERO_PROVIDER_PREFLIGHT=PASSED
V2_REAL_PROVIDER_EFFECT_COUNT=0
V2_STAGING_PAIR_SUPERSEDED=True
PROVIDER_CALL_5_AUTHORIZED=False
```

The four historical real provider effects are `/v1` lineages and remain
permanently consumed.

If any `/v2` provider effect has occurred, stop. This restaging plan is no longer
valid and a new credential-reference version is required.

## 3. Exact account and target gate

Run only under the exact approved standard Trading account:

```text
DESKTOP-I4DOKM7\Trading
SID S-1-5-21-1397534616-3988210162-180023805-1009
non-administrator / non-elevated token
```

The only mutable credential targets are:

```text
AITradingBot/MarketData/Alpaca/ApiKeyId/v2
AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
```

The `/v1` targets must not be read, modified, deleted, or used as fallback by the
restaging operation.

## 4. Superseded-pair deletion gate

Before deletion, the operator procedure must verify that both `/v2` entries are
present and structurally readable as Generic Credentials with the reviewed local-
machine persistence.

The procedure must not print either value.

Then delete both exact `/v2` entries. After deletion, independently prove:

```text
V2_KEY_TARGET_PRESENT=False
V2_SECRET_TARGET_PRESENT=False
```

If deletion of either target fails or either target remains present, stop. Do not
provision a replacement pair into a partially cleared state.

## 5. Replacement-generation witness gate

Use one current Alpaca Trading API dashboard generation for both values.

If the operator still has the current pair available locally, it may be used. If
the secret is no longer available, generate one final fresh pair and immediately
capture the Architecture-84 dashboard witnesses.

Interactive input must keep raw values out of shell history and process
arguments.

For each role compute only:

```text
UTF-8 byte length
Architecture-84 domain-separated SHA-256 fingerprint
```

Do not print or persist raw key/secret values.

## 6. Pair provisioning gate

Provision both exact `/v2` targets as Windows Generic Credentials with the
reviewed local-machine persistence.

The operation must be fail closed:

- create the key target;
- create the secret target;
- on any failure, delete every `/v2` target created by this execution;
- never accept a partial or mixed-generation pair.

The procedure must not make a network request, launch the production child, or
mutate the authority database.

## 7. Independent readback witness gate

Read only the two exact `/v2` targets under the approved Trading SID and verify:

- exact target names;
- Generic Credential type;
- local-machine persistence;
- nonempty value;
- strict UTF-8;
- no leading/trailing whitespace;
- no CR, LF, or NUL;
- approved byte bound;
- readback byte lengths equal the dashboard-side lengths;
- readback fingerprints equal the dashboard-side fingerprints;
- raw bytes of each readback equal the corresponding interactive input value.

All acquired native credential buffers must be released/cleared according to the
reviewed local operator procedure.

Required result:

```text
KEY_ID_LOCAL_EXACT_MATCH=True
SECRET_LOCAL_EXACT_MATCH=True
LOCAL_EXACT_MATCH=PASSED
```

## 8. Dashboard-current gate

After successful readback, refresh/revisit the intended Alpaca dashboard
account/environment and confirm that the displayed current key ID is the same
replacement generation whose witness was captured.

Record only:

```text
FRESH_GENERATED=PASSED
LOCAL_EXACT_MATCH=PASSED
DASHBOARD_CURRENT=PASSED
```

If the dashboard is regenerated again before a provider effect, these witness
states are superseded again and this entire restaging gate must be repeated.

## 9. Freeze-after-first-effect rule

Once any real `/v2` provider effect is launched, `/v2` restaging is permanently
closed.

The first effect consumes the mutable staging window regardless of terminal
outcome. Any later credential replacement requires a new source-owned credential
reference version and security review.

## 10. Zero-provider evidence

The restaging procedure must finish with explicit evidence that it performed:

```text
NETWORK_OPERATION_PERFORMED=False
PRODUCTION_CHILD_LAUNCHED=False
AUTHORITY_DATABASE_MUTATION=False
PROVIDER_REQUEST_PERFORMED=False
PROVIDER_CALL_5_AUTHORIZED=False
```

Credential Manager reads/writes/deletes are expected operator effects in this
procedure and are not provider effects.

## 11. Next gate after acceptance

Only after the replacement `/v2` generation passes all three witness states may
C3 return to the normal provider pre-effect sequence:

```text
wait for eligible new XNYS session
-> pure planner
-> deterministic fresh C2 request digest
-> prove zero durable lineage for that digest
-> separately review and explicitly authorize at most one provider effect
```

No command in this validation plan authorizes the capture itself.
