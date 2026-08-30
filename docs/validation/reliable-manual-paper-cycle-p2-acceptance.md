# Architecture 94 P2 selected-C3 read authority — acceptance record

## Status

Architecture-94 **P2 — read-only selected-C3 snapshot authority is FULLY
ACCEPTED** at source head:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
fix: bind Architecture 94 P2 permit issuance
```

P2 is a read-only later-stage authority over one exact already-selected C3
snapshot. It does not authorize C3 capture, credential access, provider retry,
provider call #7, brokerage, paper-account mutation, unattended scheduling, or
live trading.

**Production/live trading remains NO-GO.**

## Accepted source boundary

The P2 source review accepted all of the following:

- production construction requires genuine `ValidatedProductionAuthority`;
- production SQLite is opened through the approved read-only VFS;
- one query-only transaction reads one exact joined selected lineage;
- exact `selection_id` is an assertion/query key and never authority;
- session and attempt must be `SUCCESS_SELECTED`;
- terminal must be `SUCCEEDED / CONFIRMED`;
- selection/terminal snapshot digests must agree;
- durable semantic evidence is revalidated, including C2 process/resume,
  cleanup, terminal, and selection material;
- no newest/latest/timestamp/filename/row-order fallback exists;
- canonical final artifact name is derived from the durable terminal snapshot
  ID under the fixed C1 capture-output root;
- exact safe artifact reopen, bounded reread, native identity, SHA-256, and byte
  length reconstruct existing `C3ArtifactIdentityEvidence`;
- reconstructed artifact identity SHA-256 must equal the durable terminal
  `artifact_identity_sha256`;
- strict daily-snapshot verification and exact canonical reserialization must
  pass;
- retained snapshot bytes remain bound to audit SHA-256/length and verifier
  evidence;
- successful-read issuance is one-shot and bound by object identity to the exact
  audit/core/reader/registration produced by the successful read;
- production permit validation requires the exact audit object and genuine
  production reader/core provenance;
- the production reader exposes no public `.authority` attribute;
- P1 remains pure and does not bind P2 native identity, artifact-identity
  evidence, filesystem facts, or permits.

No production SQL artifact or schema SQL file changed in P2.

## Source review and local acceptance

Accepted source review result:

```text
P2_B1_RETAINED_BYTES_BINDING=PASS
P2_B2_PERMIT_PROVENANCE=PASS
P2_B2_C1_ATTENUATION=PASS
P2_B3_DURABLE_SEMANTICS=PASS
P2_READ_ONLY_SQLITE_BOUNDARY=PASS
P2_ARTIFACT_IDENTITY_PROOF=PASS
P2_C1_C2_REGRESSION_REVIEW=PASS
P1_BOUNDARY_PRESERVED=PASS
P2_SOURCE_REVIEW=PASS
```

Local focused P2 gate on the exact reviewed source:

```text
tests/runtime/test_manual_paper_selected_c3_snapshot.py
48 passed
```

The selected C2 regression nodes expand to 77 parametrized cases. The paper
worktree's historical `.pytest_cache` was inaccessible/malformed for one
hard-coded lifecycle-arbiter scratch path. The source was not modified to work
around that environment. Instead the unchanged C2 harness was run from the
previously validated integration worktree while `PYTHONPATH` pointed to the
reviewed paper-worktree source. Import provenance was printed first and proved
that the affected transactional/schema/validation modules came from
`F:\AI\ai-trading-bot-paper\src`. Result:

```text
77 passed
```

The accepted tree also had Ruff/format/diff checks passing, a clean tracked
worktree, and exact HEAD `a810122a96b6fc90da25d71eede8da64b7272c98`.

## Windows pytest regression-prevention record

The P2 acceptance exposed two Windows test-environment facts that must be
preserved for future milestones:

1. The user-temp pytest hierarchy
   `C:\Users\John\AppData\Local\Temp\pytest-of-John` can be inaccessible. Use a
   fresh explicit `--basetemp F:\AI\pytest-<milestone>-<gate>` for controlled
   local gates instead of treating those fixture errors as source failures.
2. Some C2 interprocess test infrastructure intentionally uses a worktree-local
   `.pytest_cache\ai-trading-bot-lifecycle-arbiters-v1` path, so `--basetemp`
   cannot relocate it. If that cache is inaccessible, preserve it. Do not
   delete/take ownership/repair it merely to force a test run. Use a known-good
   worktree harness while proving with module `__file__` output that the exact
   reviewed source worktree is imported.

A filesystem command that reports an error must not be followed by an
unconditional success message. Use terminating PowerShell errors/exit-code
checks for gate operations.

## Frozen P2 release artifact

P2 was packaged only after source review/local acceptance. The release artifact
was built from a detached Git export, not the mutable working tree.

```text
source commit:
  a810122a96b6fc90da25d71eede8da64b7272c98
source tree:
  51936b0af02b2a0246dc67b2e30d11a5c5e09b31
source export:
  F:\AI\p2-production-source-v1
wheel:
  F:\AI\p2-production-wheelhouse-v1\ai_trading_bot-0.1.0-py3-none-any.whl
wheel bytes:
  743531
wheel SHA-256:
  3b4862eb44763bead9cf0dd826645043e7de6419a182664ed780248eae6ff0c0
```

Offline wheel verification:

```text
WHEEL_ENTRIES=215
SOURCE_PACKAGE_FILES=211
WHEEL_PACKAGE_FILES=211
PACKAGE_MISSING_COUNT=0
PACKAGE_EXTRA_COUNT=0
PACKAGE_BYTE_MISMATCH_COUNT=0
RECORD_ROWS=215
RECORD_FAILURE_COUNT=0
WHEEL_PACKAGE_EXACT_MATCH=PASS
WHEEL_RECORD_VERIFICATION=PASS
```

## Fixed-runtime deployment acceptance

The first production-runtime provenance probe correctly showed that the fixed
runtime still contained the older accepted C3 package. P2 was not copied into
`site-packages` manually. The accepted deployment path was:

```text
exact reviewed Git source
-> detached export
-> frozen wheel
-> exact package/RECORD verification
-> elevated Administrator sealed deployment
-> installed RECORD reconciliation
-> exact source-module comparison
-> frozen production SQL proof
-> Administrators ownership/ACL normalization
-> exact Trading RX republication
-> separate non-admin Trading zero-provider preflight
```

Accepted installed payload evidence:

```text
RECORD_ROWS=215
HASHED_INSTALLED_PAYLOADS_CHECKED=214
INSTALLED_PAYLOAD_FAILURE_COUNT=0
P2_INSTALLED_RECORD_RECONCILIATION=PASSED
```

Accepted security-sensitive installed source hashes:

```text
runtime/__init__.py
  6630a2edca0b09f850eab269f1cfe35c845a2baebac75315387b0470977295c1
runtime/manual_paper_selected_c3_snapshot.py
  ef49baff52712f3c5c34d760719b0fde2a5ccaf83ba0ceaccdaca15a9c694e8a
runtime/windows_authority_schema.py
  0784ebce1231a018e5c68f78cedf578c04d066ec549a603e098163ad0233d56f
runtime/windows_authority_validation.py
  1f7355e6603af9bf53a81761fd244e895c2d47c3309933abde887a1b616c0299
runtime/windows_transactional_authority.py
  6a847e4385f4ad516031c0c93c572ef98c45a514de41e680e4e8c3828e354874
```

The installed runtime retained SQLite 3.50.4 and the frozen production SQL:

```text
bytes: 118896
SHA-256: aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
```

Ownership normalization processed 12,502 files with zero failures. The final
sealed runtime contained 12,501 descendants with zero ACL anomalies before
Trading RX was republished.

## Operator trust-context lesson

Production validation must keep three identities/contexts separate:

- normal development account for Git/source/tests/artifact build;
- elevated Administrator for fixed-runtime deployment and ACL publication;
- non-elevated `DESKTOP-I4DOKM7\Trading` for genuine production C1/P2
  acceptance.

An `Access is denied` from the normal account when probing the protected fixed
runtime can be the intended security boundary. It is not sufficient evidence
that the runtime is missing. Always prove deployed import provenance before a
production acceptance depending on newly reviewed source.

Windows PowerShell 5.1 is used for production operator gates. It rejected
`New-Item -LiteralPath`; the corrected runtime-write and temp probes used
`[System.IO.File]`. Command/shell failures are operator-gate failures, not
application regressions.

## Non-admin Trading zero-provider preflight

Accepted identity and runtime facts:

```text
identity: DESKTOP-I4DOKM7\Trading
SID: S-1-5-21-1397534616-3988210162-180023805-1009
administrator: False
elevated: False
P2 installed source SHA-256:
  ef49baff52712f3c5c34d760719b0fde2a5ccaf83ba0ceaccdaca15a9c694e8a
```

The genuine Trading process acquired C1, constructed the P2 reader, verified
that no public `.authority` attribute exists, and deliberately did not call
`read_selected_snapshot` during preflight.

Accepted zero-provider facts:

```text
C1_AUTHORITY_ACQUIRED=PASSED
P2_READER_CONSTRUCTED=PASSED
P2_PUBLIC_AUTHORITY_ATTRIBUTE_PRESENT=False
P2_SELECTED_SNAPSHOT_READ_PERFORMED=False
P2_PERMIT_ISSUED=False
SOCKET_CONNECT_COUNT=0
RUNTIME_WRITE_BLOCKED=True
TEMP_WRITE_READ_DELETE=PASSED
NETWORK_OPERATION_PERFORMED=False
PRODUCTION_CHILD_LAUNCHED=False
PROVIDER_REQUEST_PERFORMED=False
AUTHORITY_DATABASE_MUTATION=False
```

Authority database at the accepted preflight checkpoint:

```text
bytes: 331776
SHA-256: 6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76
```

## Final supervised accepted-call-#6 P2 reread

Only after source review, local gates, frozen release artifact, sealed deployment,
Trading RX publication, and zero-provider preflight was one supervised P2 reread
of the already-consumed successful C3 call #6 performed.

The provider effect was **not** rerun.

Accepted durable/audit evidence:

```text
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
session_id: f787e4f6-c3ca-58fe-802b-f068dd474b41
attempt_id: e809f393-b557-5c6b-8665-78d66822fee8
terminal_id: b4c76e5f-44bb-54ce-a917-3e3223b84107
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
terminal_state: SUCCEEDED
provider_call_disposition: CONFIRMED
artifact SHA-256:
  31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
artifact identity SHA-256:
  c23b0c5a8cd5d4808bb18e5f5165344a8013b4c29b9930dc33f74a30846978f2
canonical artifact:
  F:\AITradingBot\Authority\capture-output\daily-market-data-snapshot-eba46838-44ae-5bec-97bf-98c6639ae6a7.json
```

Retained snapshot and strict verifier evidence:

```text
RETAINED_SNAPSHOT_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
RETAINED_SNAPSHOT_BYTES=1291
SNAPSHOT_VERIFICATION_PASSED=True
SNAPSHOT_DIAGNOSTICS=()
SNAPSHOT_VERIFICATION_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
SNAPSHOT_VERIFICATION_BYTES=1291
RESULT_PROVIDER_CALL_PERFORMED=False
RESULT_DATABASE_MUTATION_PERFORMED=False
P2_PRODUCTION_PERMIT_VALID=True
SOCKET_CONNECT_COUNT=0
```

Before/after byte identity:

```text
authority.sqlite3 before/after:
  331776 bytes
  6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76
selected artifact before/after:
  1291 bytes
  31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
AUTHORITY_DATABASE_BYTE_IDENTITY=PASSED
CALL6_ARTIFACT_BYTE_IDENTITY=PASSED
P2_SUPERVISED_CALL6_READ=PASSED
CALL6_PROVIDER_EFFECT_REEXECUTED=False
PROVIDER_CALL_7_PERFORMED=False
PROVIDER_CALL_7_AUTHORIZED=False
```

## Final classification and next stage

```text
P2_SOURCE_REVIEW=PASS
P2_LOCAL_ACCEPTANCE_GATE=PASS
P2_RELEASE_ARTIFACT=ACCEPTED
P2_SEALED_RUNTIME_DEPLOYMENT=ACCEPTED
P2_TRADING_ZERO_PROVIDER_PREFLIGHT=ACCEPTED
P2_SUPERVISED_CALL6_READ=PASS
P2=FULLY_ACCEPTED
```

The next Architecture-94 stage is **P3 — fixed-root paper-account authority /
immutable anchor / graph-derived unique tip / account lifecycle mutex**. P3 is
an authority/filesystem-trust/locking/concurrency/crash-recovery boundary and is
therefore routed to **Codex Sol High** after ChatGPT/Sol freezes the exact P3
contract.

No provider call #7 is authorized. Production/live trading remains NO-GO.
