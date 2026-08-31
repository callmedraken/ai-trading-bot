# Architecture 94 P3 provisioning release-wheel certification

## Status

This record freezes the accepted release artifact for the Architecture-94 P3
production paper-account provisioning checkpoint. It is evidence only and does
not change the accepted P3/provisioning source, paper-account bundle, Windows
security model, C1/C2/C3 authority, or P4/A67 contract.

The release source remains exactly:

```text
SOURCE_COMMIT=bc1536316e153048833db7a2769f811007382d0e
SOURCE_TREE=ff3428b459ebfa0ebd36e15d889efcf2d5628da7
```

The later docs-only checkpoint present when release certification completed was:

```text
DOCS_CHECKPOINT=cd0d80208b874bbb6702fdccfc021840b8335743
```

Production/live trading remains NO-GO. Provider call #7 remains unauthorized.
Creation of `F:\AITradingBot\Paper` remains unauthorized until the separately
reviewed sealed-runtime deployment and one-time Administrator publication gates.

## Retained failed release envelopes

The first three release envelopes are retained historical evidence and must not
be deleted, repaired, overwritten, reused, or promoted:

```text
F:\AI\p3-provisioning-release-v1
state = FAILED_RETAINED
reason = operator verifier assumed an exact Git object-format string

F:\AI\p3-provisioning-release-v2
state = FAILED_RETAINED
reason = git archive/export representation was not byte-identical to Git blob bytes

F:\AI\p3-provisioning-release-v3
state = FAILED_RETAINED
reason = CRLF-sensitive literal METADATA substring check
```

The v3 source materialization itself passed exact Git-blob reconciliation and its
wheel was successfully built offline. A read-only diagnostic proved that the
wheel METADATA contained the correct project name, version, and Requires-Python
fields. The v3 wheel was therefore retained as an immutable candidate rather than
rebuilt.

## Accepted certification envelope

The certified release envelope is:

```text
F:\AI\p3-provisioning-release-v4
state = ACCEPTED
```

V4 performed certification only. It did not rebuild the wheel. It reread and
reproved the exact retained v3 source and candidate wheel, then copied those same
wheel bytes into the clean v4 envelope.

Exact accepted release evidence:

```text
RELEASE_SOURCE_COMMIT=bc1536316e153048833db7a2769f811007382d0e
RELEASE_SOURCE_TREE=ff3428b459ebfa0ebd36e15d889efcf2d5628da7
SOURCE_FILES_RECONCILED=569
SOURCE_MANIFEST_SHA256=6bba236fd12fb8bd2bfa7db5df2ccb8bda1fc9850380fefb151fd9afaadab281
SOURCE_MANIFEST_BYTES=132713
WHEEL_FILENAME=ai_trading_bot-0.1.0-py3-none-any.whl
WHEEL_SHA256=86834a81dd21887fafd6efc3af1d2525ff9a37a3229dbea6e8cd7cfaba5b8a27
WHEEL_BYTES=764270
RECORD_ROWS=220
PACKAGE_FILES_RECONCILED=216
METADATA_NAME=ai-trading-bot
METADATA_VERSION=0.1.0
METADATA_REQUIRES_PYTHON=>=3.12
WHEEL_TAGS=py3-none-any
WHEEL_ROOT_IS_PURELIB=true
RELEASE_CERTIFICATION_SHA256=c71b97c8a9215797e2ca1c4806e1980bb89a19b08838d32193b217ee06fcd8fa
RELEASE_CERTIFICATION_BYTES=1638
V3_EXACT_SOURCE_REVERIFIED=PASS
V3_CANDIDATE_WHEEL_IDENTITY=PASS
WHEEL_RECORD_VERIFICATION=PASS
WHEEL_PACKAGE_BYTE_RECONCILIATION=PASS
WHEEL_METADATA_VERIFICATION=PASS
V4_CERTIFIED_WHEEL_COPY_IDENTITY=PASS
WHEEL_REBUILT_DURING_CERTIFICATION=False
PRODUCTION_RUNTIME_MUTATED=False
PRODUCTION_PAPER_ROOT_CREATED=False
PROVIDER_CALL_PERFORMED=False
PROVIDER_CALL_7_AUTHORIZED=False
```

The accepted production paper-account bundle remains independently frozen as:

```text
PAPER_ACCOUNT_ID=d1510a4b-6ebf-58ef-92a4-e743ca91151e
GENESIS_CHECKPOINT_ID=7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7
GENESIS_SHA256=b6172753ee4f30a82265ff38b341c3de42869ba6af7ccb69739234135183026d
GENESIS_BYTES=534
ANCHOR_SHA256=650b977db5ea5f5f1d89e3ed5bf52dfb5b2c5c44c3b34ccceb6d22dd492df871
ANCHOR_BYTES=411
PROVISIONING_MANIFEST_SHA256=8505eddd07be2f90d1211ee49a9cac4829d0faff9d88d0dc4c609b209a2e8801
PROVISIONING_MANIFEST_BYTES=522
PRODUCTION_BUNDLE_FREEZE_EVIDENCE_SHA256=7f2824adf5105f66e16b62aa4c6659d16669dea8208bbd2496eb96adbab0e034
```

No filesystem path can substitute for these bytes. The sealed-runtime deployment
must rehash the exact v4 wheel immediately before installation and reject any
SHA-256 or byte-length mismatch.

## Next gate

The next authorized step is the sealed-runtime deployment preflight and then the
separately reviewed Administrator deployment sequence:

```text
certified v4 wheel
-> reprove wheel SHA-256/length
-> validate Administrator identity and runtime quiescence
-> validate exact Trading SID and existing sealed-runtime/authority state
-> revoke Trading runtime RX
-> prove Trading runtime access absent
-> force-install exact wheel offline/no-deps/no-cache
-> reconcile every hashed installed RECORD payload
-> compare security-sensitive installed source/resources with frozen v4 source
-> reprove frozen production SQL and SQLite expectations
-> normalize/verify Administrators ownership and sealed ACL topology
-> republish exact Trading Read & Execute boundary
-> close Administrator shell
-> separate Trading zero-provider preflight
```

This checkpoint does not authorize one-time production paper-root publication.
That remains a later explicit gate after sealed-runtime deployment acceptance.
P4 production execution remains blocked.

```text
P3_PROVISIONING_RELEASE_WHEEL=ACCEPTED
P3_SEALED_RUNTIME_DEPLOYMENT=PENDING
P3_NATIVE_PROVISIONING=NOT_AUTHORIZED
P4_PRODUCTION_EXECUTION=BLOCKED
PROVIDER_CALL_7=NOT_AUTHORIZED
PRODUCTION_LIVE=NO-GO
```
