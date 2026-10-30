# Architecture 147 — Desktop product pivot validation

Status: CURRENT P1 source-only validation contract.

## Scope

This checkpoint establishes the ordinary single-user desktop research profile,
the profile-owned acquisition persistence seam, the OPEN-only loader, and the
explicit Architecture-145 final-holdout admission boundary. It preserves the
deterministic Architecture 146-A dataset contracts and the accepted published
session authority. It does not perform real acquisition or create the fixed
production root.

The fixed source-owned root is
`F:\AI\ai-trading-bot\data\research\desktop-v1`. Tests must use a fresh
explicit temporary root seam under the external pytest temporary-root policy.
No ACL, SID, SDDL, token/elevation, ownership, privilege, credential, provider,
Robinhood, paper, broker, or live operation is in scope.

## Required source behavior

The desktop storage profile must use ordinary create-only filesystem behavior:
exact-byte hashing, readback verification, normal flush/fsync where practical,
manifest and size checks, visible incomplete state, and no automatic cleanup.
It must reject arbitrary production-root substitution, never overwrite an
existing completed file, and contain no rename/promotion or junction/symlink
publication path.

The OPEN loader must read only normalized OPEN bytes and required non-price
metadata, validate canonical CSV, hash/size/manifest membership, snapshot
bindings, and the accepted authority
`nyse-published-regular-sessions-2016-2026-v1` (2718 sessions and the frozen
published digest). It must not read FINAL_HOLDOUT bytes or require
`ACCEPTED_CUSTODY_ADMISSIONS`.

The final loader must require the exact existing
`ResearchStrategyFinalHoldoutAdmission`, reject missing/wrong admissions and
policy/dataset/partition mismatches, validate FINAL_HOLDOUT physical integrity,
and return only the explicitly admitted holdout. Optimizer, walk-forward, and
candidate-selection modules must not import or call that loader.

The acquisition kernel must retain the existing fake-transport normalization,
partition, raw-page, corporate-action, published-session, snapshot, and full
fingerprint semantics while delegating persistence to the injected profile.
The protected custody adapter remains isolated legacy behavior; it is not
constructed unconditionally by the current desktop path.

## Focused evidence

The focused P1 checks cover fixed-root/test-seam behavior, ordinary filesystem
invariants, create-only/readback and incomplete/corrupt/manifest mismatch
blocking, OPEN-only reads, final-holdout admission and integrity, optimizer
import ownership, fake acquisition composition, readiness classification, and
checkpoint/source authority. Retained compatibility coverage covers the
Architecture 146 acquisition/custody and dataset tests; affected Architecture
145 robustness and candidate/walk-forward tests remain required focused
coverage.

The checkpoint is registered as `arch147-desktop-research-profile` with
`preflight=None` and `execute=None`, mapped to GitHub-owned FULL. The consumed
Architecture 146 `HOST_UNKNOWN` observer report is historical evidence only
and must not be retried. P1 has no Robinhood MCP call, OAuth read, account
query, order review, order mutation, or live effect.

## Admission and handoff

Before publication, run focused tests, whole-root Ruff diagnostics, and
`git diff --check`. Then exact-file stage only the intended files, verify the
staged filename set and `git diff --cached --check`, create one atomic commit,
and run:

    .\ops.ps1 admit

The admission must report `FEATURE PASS` and
`PROSPECTIVE_DEVELOP PASS` for the exact same final HEAD/tree and stable
identity. Publish one ordinary push and wait for the mapped GitHub FULL run to
reach a terminal result. Do not run canonical FULL locally. A deterministic
stale current assertion tied only to the retired protected-custody next action
must be corrected inside this checkpoint; unexpected security, authority,
credential, provider, or effect ambiguity is a STOP for ChatGPT review.

After terminal CI, ChatGPT independently reviews the exact source and decides
whether to fast-forward `develop`. P2 real SPY acquisition is a later
separately reviewed milestone.
