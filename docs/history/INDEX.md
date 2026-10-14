# Project History Index

Status: **ACTIVE - HIST-2B exact snapshot and canonical cutover complete**

This index routes historical reconstruction without making closed chronology
part of routine startup. Current state belongs in:

- `docs/PROJECT_STATUS.md`;
- `docs/AI_TRADING_BOT_HANDOFF.md`;
- the relevant current architecture or validation document.

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
- [Current D1R4 provisioning concurrency and authentication-preparation authority](../architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md);
- [Current D1R4 generation and authentication-preparation validation](../validation/arch134-d1r4-alpaca-v3-credential-generation.md).

## Historical lookup order

For a historical question, use this order:

1. current status and handoff for the current state;
2. this index for historical routing;
3. the referenced architecture or validation document;
4. the legacy snapshot only when deeper chronological reconstruction is
   actually required;
5. Git history for exact source-era reconstruction.

Do not create a duplicate milestone ledger here. Historical corrections are
additive records or index annotations and must never silently rewrite the
immutable snapshot.

## Retrieval and immutability rule

The legacy snapshot is an audit and targeted-reconstruction surface, not
routine startup material. Do not modify, normalize, regenerate, or replace any
file beneath `docs/history/legacy/HIST-2B-2026-10-13/`.
