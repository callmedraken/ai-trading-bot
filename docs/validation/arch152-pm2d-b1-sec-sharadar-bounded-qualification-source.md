# Architecture 152-PM2D-B1 — SEC/Sharadar Qualification Validation

**Validation boundary:** source-only and fake-only.
**NO REAL PROVIDER OBSERVATION AUTHORIZED.** This checkpoint does not read SEC,
Nasdaq Data Link, Sharadar, brokerage accounts, credentials, AI providers, or
Arch149 data.

## 1. Parent and checkpoint status

PM2D-A is accepted and integrated at HEAD
`9b9f5e0c7f0f5ab7addbe2c291c20df4b4d2903b` / tree
`1b42c70df8a686dcd231b6dd563640ad18f1b200`. The PM2D-A feature docs run
`46105978117` and develop docs run `46106912628` are terminal green. PM2D-B1
is registered as a separate source-only checkpoint mapped to canonical FULL.
Exact-source acceptance and mapped B1 certification evidence are pending; no
result or candidate SHA is claimed here.

## 2. Required fake-only coverage

The B1 source acceptance review must establish deterministic behavior for the
following cases using synthetic bytes and exact fake provider types only:

1. Exact SEC/SF1 match.
2. Different SEC accession.
3. Different issuer.
4. Different fiscal period.
5. Different unit or currency.
6. Different sign or value.
7. Rejection of `MRQ`, `MRY`, and `MRT` for historical PM2C facts.
8. Rejection of `ART` as original-quarter history.
9. `datekey` without a vendor-version availability witness.
10. `lastupdated` not treated as an immutable version witness.
11. SEC report-period end and filing date not treated as public availability.
12. Amendment preserved as a later version without rewriting the original.
13. Early 8-K not backdating a later SF1 value without exact same-fact lineage.
14. True zero distinct from null and missing.
15. Unsupported/custom-dimensional SEC context mismatch.
16. Duplicate/conflicting SEC facts.
17. Duplicate/conflicting SF1 rows.
18. Page limit.
19. Total-attempt limit.
20. Provider exception after its attempt counter increments.
21. Custody-write failure.
22. Source HEAD/tree mismatch or failed source admission.
23. Future/unapproved real provider implementation is structurally rejected.
24. Credential, account, AI, broker and production-mutation counters remain
    zero.
25. No PM1 recommendation, optimizer, target or dispatch authority is
    reachable.
26. No automatic retry, and consumed attempt identity cannot be reused.
27. ARQ Q1 requires a separate exact grain witness that matches the parsed SEC
    and SF1 facts; an SF1 row alone does not prove discrete-quarter grain.

Any scenario outside the selected issuer, accession, revenue field, periods,
and declared plan bounds remains unqualified. No test may contact a provider or
use real credentials, account state, paid-plan access, downloaded samples, or
sealed data.

## 3. Source gate and focused checks

The checkpoint must remain effect-free: `preflight`, `execute`, and
`remote_head_env` are absent; PM2D-B1 routes only for the exact B1-owned source
or test paths on the persistent Portfolio Manager feature branch; PM1 remains
the established no-diff and unrelated-path fallback. Pull requests do not
select this push-only route. The workflow's current mutable projection must
include B1 while the historical predecessor projection remains unchanged.

Focused implementation verification covers the B1 operator and comparison
tests, the checkpoint-runner route/authority tests, any directly reused PM2C
evidence/snapshot tests, Ruff check/format on changed Python files, and
`git diff --check`. Use the repository's registered CI route for terminal
mapped FULL. Do not run local whole-project FULL for this checkpoint. Exact
focused command results belong in the final source review record; this document
does not claim tests or certification have already run.

The canonical local FULL reference, if the owner later requests a materially
distinct local run, is the repository-owned runner with exact verified source
identity and a fresh external evidence directory:

```powershell
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B `
  'scripts\run_test_certification.py' --profile full `
  --root 'F:\AI\worktrees\ai-trading-bot-portfolio-manager-current' `
  --python 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' `
  --expected-head '<verified source HEAD>' `
  --expected-tree '<verified source tree>' `
  --expected-base-head '<verified origin/develop HEAD>' `
  --expected-branch 'feature/robinhood-portfolio-manager-current' `
  --expected-feature-ref 'origin/feature/robinhood-portfolio-manager-current' `
  --expected-feature-head '<verified source HEAD>' `
  --temp-root 'F:\AI\temp\pytest' `
  --evidence-dir 'F:\AI\temp\arch152-pm2d-b1-full-<fresh-guid>'
```

The placeholders must be replaced only after exact source/base identities are
verified. The mapped GitHub FULL is the canonical checkpoint certification;
this reference is not an instruction to run a duplicate local profile.

## 4. Later B1-O boundary

Real observation is a separate transition after independent exact-source
acceptance and develop integration. It requires separately reviewed real-
observation wiring; the B1 operator accepts only exact offline fake providers
and cannot be used as a real transport. Before that transition, the owner must
review one immutable attempt plan that binds:

- accepted source HEAD/tree and one unique attempt ID;
- exact issuer/CIK and primary, amendment, or early 8-K accessions;
- exact SEC document/member names and Sharadar SF1 table/dimension;
- `revenue` only, in USD, with explicit ARY and any requested ARQ Q1 period
  plus a separate exact discrete-grain witness matched to parsed SEC/SF1 facts;
- requested fiscal periods, provider-attempt/doc/page/row/byte ceilings and no
  retry;
- exact external evidence root and custody/retention terms.

The B1 plan supports only ARY and optional ARQ direct Q1. It does not implement
Q2/Q3/Q4 quarterization; these remain unavailable here. Any later support must
bind compatible same-FY YTD components for Q2/Q3 or annual and same-FY Q3 YTD
for Q4. SEC public
availability and the exact Sharadar vendor-version boundary are separate
proofs. A datekey, lastupdated value, report-period end, digest, or later
observation cannot substitute. A blocked/unqualified one-shot result is
terminal; there is no expanded search or automatic retry. Alpaca price/action
qualification is a separate PM2D-B2 decision.
