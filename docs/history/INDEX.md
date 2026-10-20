# Project History Index

Status: **ACTIVE - HIST-2B exact snapshot and bounded current-state model active**

This index routes historical reconstruction without making closed chronology
part of routine startup. Current state belongs in:

- `docs/PROJECT_STATUS.md`;
- `docs/AI_TRADING_BOT_HANDOFF.md`;
- the relevant current architecture or validation document.

## Default startup reference and compatibility/history mirror

Current remote `develop` is the primary/default startup integration reference.
New chats read, in order, its `AGENTS.md`, `docs/AI_DEVELOPMENT_WORKFLOW.md`,
bounded `docs/PROJECT_STATUS.md`, bounded `docs/AI_TRADING_BOT_HANDOFF.md`,
then relevant architecture/validation documents. Separately verify the active
remote product branch and exact executable HEAD/tree/CI before source or
protected work. Startup documentation grants no executable-source or trading
authority.

The former `feature/project-history-storage-foundation` compatibility/history
mirror is retired. Its final synchronized tip was
`19e5859fa83656cc50dbe69f89f3badd57841165`, identical to `develop`, with no
unique commits or open PR dependency. Do not recreate it; historical mentions are
retrieval context only.

## Recent compact closed records

- [2026-10-19 D1R9 NO_SIGNAL and safe-side integration](2026-10-19-d1r9-no-signal-and-safe-side-integration.md) —
  terminal Monday D1R9/D1R8/D1R7 proof chain, accepted executable integration,
  certification preservation, and Architecture-144 successor boundary.

## Immutable HIST-2B snapshot

The exact pre-cutover cumulative documents are preserved under:

`docs/history/legacy/HIST-2B-2026-10-13/`

```text
cutover ID   HIST-2B-2026-10-13
source HEAD  f8e2bd96f5a640c25ea33b56f76b2f06d44bf512
source TREE  4b9c2772c26589c04bd3a50d81387a1c1095846b
```

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `AI_TRADING_BOT_HANDOFF.md` | 1003908 | `be5993375efa8720e9ee8afc25e4a5bf4ba7ce317f4544f23e2229195e27856f` |
| `PROJECT_STATUS.md` | 1006035 | `6bca0c92cc0e237bf0f7037ce550d8edbe14c7f207e63c017c78ecb4952ffe4d` |
| `manifest.json` | 768 | `272c5bbacd690fe2e876ecb06226c9db04fd3403272e59559aee74e075968f8d` |

The exact Git preservation correction was finalized at:

```text
HEAD  83d0ec7d599f7494bb964c756a8b5717ac567d6c
TREE  f6badbe010bd85cbb3dbfd0dd71be7842bbe3612
```

The preceding `97b2c2a` storage state contained line-ending-normalized blobs.
It is superseded and must not be described as the byte-exact Git archive.
The root `.gitattributes` rule `docs/history/legacy/** -text` is required to
keep immutable legacy material byte-preserving in Git.

## Deep architecture and validation references

Use the authoritative contract rather than copying its historical narrative:

- [Architecture 131 paper authority](../architecture/131-robinhood-review-paper-trading.md);
- [Architecture 132 tiered certification profiles](../architecture/132-tiered-certification-profiles.md);
- [Architecture 133 unattended review-paper authority](../architecture/133-robinhood-single-session-unattended-review-paper-authority.md);
- [Architecture 134 production strategy and AI research authority](../architecture/134-production-strategy-and-ai-research-authority.md);
- [Architecture 142 strategy-native evaluation](../architecture/142-research-strategy-native-evaluation.md);
- [Architecture 143 production compatibility proof](../architecture/143-research-strategy-production-compatibility-proof.md);
- [Architecture 144 paper-candidate eligibility](../architecture/144-research-strategy-paper-candidate-eligibility.md).

## Historical lookup order

For a historical question, use this order:

1. bounded current status and handoff from current remote `develop`;
2. this index for historical routing;
3. the referenced architecture or validation document;
4. a compact closed record where one exists;
5. the legacy snapshot only when deeper chronological reconstruction is actually
   required;
6. Git history for exact source-era reconstruction.

Do not create a duplicate milestone ledger here. Historical corrections are
additive records or index annotations and must never silently rewrite the
immutable snapshot.

## Retrieval and immutability rule

The legacy snapshot is an audit and targeted-reconstruction surface, not routine
startup material. Do not modify, normalize, regenerate, or replace any file
beneath `docs/history/legacy/HIST-2B-2026-10-13/`.
