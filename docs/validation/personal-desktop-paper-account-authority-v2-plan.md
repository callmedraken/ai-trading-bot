# PD1 validation plan: personal-desktop paper-account authority v2

## Status

This plan validates Architecture 103. It is intentionally staged so source can be implemented and certified while every production paper-v2 effect remains disabled.

Production/live trading remains NO-GO.

## Fixed source line

Branch:

```text
feature/personal-desktop-paper-runtime
```

Architecture-94 P2 base:

```text
a810122a96b6fc90da25d71eede8da64b7272c98
```

Before each implementation/checkpoint task prove:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
```

A worktree/branch/HEAD mismatch is a STOP. Do not self-correct with checkout, switch, reset, rebase, clean, or worktree mutation.

## Production non-effect invariant

Through all PD1 source implementation and certification:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED=false
```

Forbidden during source implementation/certification:

- create/modify/delete/rename `F:\AITradingBot\Paper-v2`;
- create/modify/delete/rename `F:\AITradingBot\.Paper-v2.provisioning`;
- touch retained `F:\AITradingBot\.Paper.provisioning-v1`;
- recreate `F:\AITradingBot\Paper`;
- account/group/password/LSA/KSP mutation;
- provider call #7;
- broker order effects;
- live trading.

Disposable filesystem tests must use an isolated fresh test root, never an alternate production root interpreted as authority.

## PD1A: pure authority / bundle model

### Required behavior

Verify:

1. strict `personal-desktop-paper-account-authority/v1` model;
2. exact `personal-desktop-paper-layout/v1` binding;
3. deterministic UUID5 account identity under namespace `022bbd87-6bea-5fd0-a323-5fa355616643`;
4. strict canonical anchor serialization/parsing;
5. strict `personal-desktop-paper-account-provisioning/v1` manifest;
6. manifest-to-anchor-to-GENESIS reconciliation;
7. positive explicit starting-cash requirement with no default;
8. cash-only/zero-position/zero-realized-P&L opening policy;
9. GENESIS `as_of` derived only from a fully verified P2 selected-snapshot result;
10. no provider/network/filesystem output from pure preparation.

### Negative matrix

At minimum reject:

- unknown/missing/duplicate fields;
- BOM/trailing bytes/noncanonical JSON;
- uppercase/malformed UUID or SHA text;
- float/non-finite/noncanonical number forms;
- wrong layout/schema;
- wrong machine-authority ID;
- wrong Trading SID;
- changed GENESIS checkpoint ID/hash/length;
- changed anchor hash/length in manifest;
- zero/negative/missing/defaulted starting cash;
- non-cash opening state;
- caller wall-clock substitution for selected-snapshot `captured_at`;
- caller path/environment material entering account identity.

### PD1A focused gate

Run only the new pure tests plus directly invalidated Architecture-61/P2 tests during iteration. Ruff check/format and `git diff --check` must pass on touched files.

## PD1B: Windows read-only authority and security policy

### Path/object gates

Read-only tests must prove production constants are exact:

```text
F:\AITradingBot\Paper-v2
F:\AITradingBot\.Paper-v2.provisioning
F:\AITradingBot\Paper-v2\runtime
F:\AITradingBot\Paper-v2\runtime\paper-operations
```

No caller-provided production root is accepted.

No-follow/path tests cover:

- reparse points;
- unsafe final-path resolution;
- wrong object kind;
- case/alias/path traversal variants;
- unexpected top-level names;
- recognized-layout collisions;
- bounded inventory limits;
- object replacement/identity drift during a pinned read session.

### Runtime token gate

Using testable token abstractions plus Windows integration where practical, prove that runtime authority requires:

- exact approved Trading SID;
- primary token;
- no thread impersonation;
- non-elevated token;
- Administrators membership absent/disabled.

Explicitly prove that no LSA account-right enumeration is required.

### ACL policy

Tests cover exact roles:

- immutable root;
- authority anchor;
- GENESIS directory/file;
- runtime container;
- paper-operations container;
- runtime-created output directory/file.

Reject:

- unrecognized principals;
- inherited accidental grants;
- Trading write/delete authority on immutable anchor/GENESIS roles;
- `WRITE_DAC`/`WRITE_OWNER` where Architecture 103 forbids them;
- missing SYSTEM/Administrators authority;
- wrong immutable owner.

### Authority reconciliation

A successful read authority must prove:

- genuine validated C1 authority;
- exact machine-authority ID;
- exact approved Trading SID;
- exact anchor account-ID rederivation;
- exact canonical GENESIS bytes/hash/length;
- Architecture-61 verification pass;
- bounded recognized runtime inventory;
- Architecture-66 unique full-lineage verification;
- unique terminal checkpoint exposed only after all checks pass.

Negative tests include conflicting successor edges, corrupt receipts/reports/checkpoints, stale anchor, unrecognized recognized-layout contents, unsafe historical dependency paths, and ACL drift.

## PD1C: disabled publisher and disposable publication tests

Production gate remains false.

### Disposable publication harness

Exercise the same logical algorithm under a fresh disposable root with explicit test-only dependency injection. The test root must not share a production path prefix interpreted as authority.

Test:

1. final/staging absence requirement;
2. staging create-new behavior;
3. exact layout creation;
4. create-new anchor/GENESIS writes;
5. flush/reread/hash/strict parse;
6. final ACL application and exact inspection;
7. no-clobber same-parent staging-to-final rename;
8. final reopen and complete verification;
9. pre-existing final blocks;
10. pre-existing staging blocks;
11. rename collision blocks;
12. staged-byte corruption blocks before publication;
13. ACL drift blocks before publication;
14. final verification failure reports blocked state without cleanup;
15. no automatic delete/repair/retry.

### Crash-state classification

Tests model at least:

```text
final absent / staging absent
final absent / staging present
final present / staging absent
final present / staging present
```

No test may turn a crash-left state into an automatic production retry.

### Hard production-gate test

A direct attempt to invoke the production publisher while the certified constant is false must stop before the first production filesystem mutation.

## PD1 concurrency seam

Before PD2 source can perform an Architecture-67 mutation, test an account-scoped Windows mutex contract:

- deterministic source-owned name from exact paper-account ID;
- bounded acquisition;
- one writer admitted;
- second concurrent writer blocked/times out deterministically;
- mutex held across authoritative inspection through transition/receipt commitment;
- mutex identity cannot create account authority.

This may be implemented in PD1B or immediately before PD2, but it is a hard prerequisite for PD2 mutation acceptance.

## Test execution workflow

During iteration use focused tests only.

Every controlled Windows pytest command uses a fresh external base temp, for example:

```text
F:\AI\ai-trading-bot\.venv\Scripts\python.exe -m pytest <focused paths> --basetemp F:\AI\temp\pytest\pd1-<unique> -p no:cacheprovider
```

Use the venv appropriate to the eventual dedicated personal-desktop worktree if different; prove interpreter/source provenance before broad certification.

Do not delete, repair, or move historical inaccessible pytest/cache evidence merely to make a gate pass.

## Source review gate

Before broad certification, ChatGPT/Sol reviews the authoritative GitHub compare/diff and requires:

- only frozen PD1 scope changed;
- no accidental P3-R1 KSP/account-ceremony source imported;
- no weakening of C1/C2/C3, P2, Architecture-61/66/67 contracts;
- no provider/broker/live path added;
- production v2 effect gate remains false;
- fixed paths and schema/UUID constants exactly match Architecture 103;
- test-only path injection cannot select production authority at runtime;
- no ambient env/path/clock value becomes authority.

## Broad certification

After source diff acceptance:

1. run the appropriate full repository test suite locally using fresh external `--basetemp` and `-p no:cacheprovider`;
2. if the known legacy Windows cache-path issue is still present and relevant, use the already-validated clean integration-harness procedure rather than repairing historical cache state;
3. run Ruff check;
4. run Ruff format check on tracked Python source/tests;
5. run `git diff --check`;
6. prove exact final HEAD/tree and clean worktree.

Broad certification must not perform production paper-v2 effects.

## Post-certification readiness (separate milestone)

Source certification does **not** authorize publication.

A later PD1 production-readiness freeze must separately prove/freeze:

- accepted source commit/tree;
- reviewed artifact/deployment if a sealed runtime is used;
- exact C1 machine-authority ID and Trading SID;
- current safe fixed `F:\AITradingBot` parent;
- v2 final/staging absence;
- retained v1 staging unchanged;
- exact selected C3 call-#6 P2 reread/chronology dependency as permitted;
- explicit starting cash;
- exact GENESIS bytes/hash/length;
- exact anchor bytes/hash/length;
- exact provisioning manifest bytes/hash/length;
- current elevated administrator gate for publication;
- exact future source-enablement diff;
- one-shot/ambiguous-loss operator rule.

Only after ChatGPT/Sol accepts that readiness freeze is a separate explicit production-effect authorization discussed with the user.

## Milestone completion definitions

```text
PD1_ARCHITECTURE_ACCEPTED
  Architecture 103 + this plan frozen

PD1_SOURCE_ACCEPTED
  PD1A/B/C exact source diff accepted

PD1_SOURCE_CERTIFIED
  focused + broad tests/checks accepted with production effects disabled

PD1_PRODUCTION_READY
  separate exact bundle/readiness freeze accepted

PD1_V2_PUBLISHED
  separate one-shot production publication executed and final root independently verified
```

None of the first three states imply the next one.
