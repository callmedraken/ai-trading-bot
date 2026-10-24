# Architecture 134-F1R1-D1S3-R5 — preserved-release publication recovery

## Source-only boundary and frozen incident

R5 is source-only pending terminal mapped CI and ChatGPT exact-source review.
No recovery execution or production preflight has run in this checkpoint.
Corrected D1S3 was accepted/integrated at HEAD
`ad4c3d3334048054df6d8f046040349619c277f2`, tree
`b4cbf3039171673d3fba44e4999b172e658a4f91`. Its read-only preflight passed
INSTALL_REQUIRED. It attempted to read the installation latch and established
AVAILABLE from absence; it did not create, consume or mutate the latch.

The later installation attempt is permanently consumed. Original latch:
`F:\AI\temp\arch134-f1r1-d1s3-installation-attempt\attempt.json`.
Consumed payload SHA256:
`6677dd0d690fc611d6d4ba643179d78f0f168dfc2183c4310aae26e6d84c5f67`.

Failed execute report:
`F:\AI\temp\ai-trading-bot-checkpoints\arch134-f1r1-d1s3-successor-release-installation-operator\execute-20261024T061344.551535Z\report.json`.
SHA256: `2b62f5718c1d9ed70b9cbf5232129c76734fdb1b77ae690137e6c7a5234fd84d`.
Protected execution ATTEMPTED, runner STOPPED, source stable, result
INDETERMINATE / MAY_HAVE_OCCURRED, primary PUBLICATION /
PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY, attempt CONSUMED. Automatic retry is
NOT_AUTHORIZED. Never refresh or rerun installation authority.

Subsequent blocked preflight report:
`F:\AI\temp\ai-trading-bot-checkpoints\arch134-f1r1-d1s3-successor-release-installation-operator\preflight-20261024T063211.998964Z\report.json`.
SHA256: `cd14c43cb9e2c9d500941c0cd026e7e14617d2a9a1c0a377e5d6b06c75debeec`.
Protected execution NOT_AUTHORIZED, source stable, result BLOCKED /
NOT_STARTED / INSTALLATION_BLOCKED, installation classification BLOCKED,
attempt CONSUMED, automatic retry NOT_AUTHORIZED.

Exact release `release-cb94451fc3295a97afffe9fac5d09ff3` lives under
`F:\AITradingBot\releases`. FINAL is the release name; STAGING is that exact
sibling name with `.installing` appended.

| Material | SHA256 |
| --- | --- |
| manifest | `e36ca8cdd163a3a93137e50972913acfe468745639ec773ba21e842d8d814875` |
| binding | `5ee1ea4218114b78d24b82ab7369972eafcaf332fa0b8e5ae59e5da08b953329` |
| source inventory | `cd1b9ad5ec963916b6de6d5b81ebbad75d79ebcd5c4fc86fc991bfd0e1225d21` |

Staging identity `(1855336320, 281474982917732)`, parent identity
`(1855336320, 281474980511321)`, Python identity
`(1855336320, 281474977875353)`. Python 3.14.3 SHA256
`cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b`.
Dependency closure UNPROVEN. Exact image policy: local NTFS, persistent ACLs,
non-reparse, one link, Administrators owner, protected, IMAGE_ACES direct allow
Administrators/SYSTEM `0x1F01FF` and Trading `0x1200A9`.

Preserved observations: FINAL absent, STAGING present, stable repeated namespace,
two identical immutable staging replays without error. Chat diagnostics are
context, not durable production authority. Registered R5 preflight independently
reproves frozen records, source and native image facts.

## Separate recovery authority

Checkpoint: `arch134-f1r1-d1s3-r5-successor-release-publication-recovery`.
New fixed latch:
`F:\AI\temp\arch134-f1r1-d1s3-r5-publication-recovery-attempt\attempt.json`.
Canonical ASCII bytes are this sequence followed by exactly one LF:

```json
{"automatic_retry":"NOT_AUTHORIZED","schema":"arch134-f1r1-d1s3-r5-publication-recovery-attempt/v1","status":"CONSUMED"}
```

Execute interlock:
`AI_TRADING_BOT_ARCH134_F1R1_D1S3_R5_PUBLICATION_AUTHORIZATION` =
`ARCH134_F1R1_D1S3_R5_ONE_PRESERVED_RELEASE_PUBLICATION_AUTHORIZED`.
Source interlocks:
`AI_TRADING_BOT_ARCH134_F1R1_D1S3_R5_ACCEPTED_HEAD` and
`AI_TRADING_BOT_ARCH134_F1R1_D1S3_R5_ACCEPTED_TREE`. A later review must supply
the actual accepted R5 identities. Source work never sets execute authorization.

Read-only admission order: exact current R5 source -> accepted D1S3 source ->
consumed original latch and both exact reports -> Administrator -> exact release
reconstruction -> exact parent and repeated namespace -> repeated immutable
image replay -> R5 latch observation -> repeat critical source, incident,
namespace and image checks. The accepted collector replays exact frozen D1S3
checkout bytes, including admitted CRLF conversion, complete inventory and
stable source bytes. It never installs or materializes an image.

| R5 latch | Namespace/image | Closed result | Execute eligible |
| --- | --- | --- | --- |
| AVAILABLE | exact stable STAGING only | PASS / READY_FOR_EXACT_PRESERVED_RELEASE_PUBLICATION | true |
| CONSUMED | exact stable FINAL only | PASS / FINAL_PUBLISHED_VERIFIED | false |
| CONSUMED | exact stable STAGING only | BLOCKED / CONSUMED_RECOVERY_ATTEMPT | false |
| either | both objects | BLOCKED / NAMESPACE_CONFLICT | false |
| either | neither object | BLOCKED / PRESERVED_IMAGE_MISSING | false |
| AVAILABLE | FINAL only | BLOCKED / FINAL_PRESENT_BEFORE_RECOVERY | false |
| either | identity/security/evidence/source drift | BLOCKED or INDETERMINATE | false |
| either | repeated observation drift | INDETERMINATE | false |

Every existing latch object consumes authority. Preflight never creates a latch
or parent, writes production files, loads the native writer, repairs state or
retries. Its result preserves latch state, parent names/identity, sole-image
classification, exact image/Python evidence, source and incident report hashes.

## Protected execute seam — implemented, not run

Authorization -> complete read-only admission -> new latch AVAILABLE -> repeat
full admission -> exclusive recovery latch creation -> exact write/flush/fsync/
close/readback -> lazy native writer import -> ONE handle-relative
SetFileInformationByHandle FileRenameInfo request, ReplaceIfExists FALSE ->
independently observe FINAL and replay at least twice -> prove STAGING absent
and staging identity preserved -> prove parent namespace changed only by the
exact `.installing` to final-name rename -> repeat incident/source checks ->
PASS / FINAL_PUBLISHED_VERIFIED / EXACT_FINAL_ONLY / CONFIRMED.

The native writer has no materializer, installer, directory creation, file
write, delete, cleanup, replacement, arbitrary destination, retry loop, fallback
rename, rollback, scheduler or trading API. It opens existing exact handles,
independently checking parent and image security/identity. Latch I/O ambiguity,
false native return, exceptions, KeyboardInterrupt/SystemExit, replay failure or
post-fence drift is terminal consumed INDETERMINATE / MAY_HAVE_OCCURRED /
PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY. Automatic retry is always NOT_AUTHORIZED.
Later registered preflight reconciles read-only without renewing authority.

Historical installation_reconciliation.py, publication_recovery.py and
native_publication.py remain byte-identical. Their fixed old 133-AG/AJ incident,
release, image and dispatch cannot substitute for R5.

## Excluded next boundary

Publication success grants neither successor-root provisioning nor runtime start.
`F:\AITradingBot\Arch133\arch134-f1r1-d1-successor-soak-v1` remains uncreated.
Its future reserve/append needs conflict with Trading read/execute-only
IMAGE_ACES and require separate ChatGPT architecture review. R5 changes no root
policy. Original F1/C2 evidence remains consumed and immutable; scheduler,
credentials, provider, paper, broker, D1/D2/live effects are excluded.
Roadmap: F1R1 recovery/hardening -> fresh F1 successor soak -> 145-B -> Research
Results GUI -> large strategy campaigns. Live remains NO-GO.

Also remove or update any tests and docs that referenced the old behavior.
