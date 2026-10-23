# Architecture 134-F1R1-D1S2 — successor installed-release readiness

## Status and boundary

This document defines the source-only checkpoint
`arch134-f1r1-d1s2-successor-installed-readiness`. It composes the accepted
Architecture-133 immutable-release primitives with F1R1-A, F1R1-B, and the
D1 successor manual-start contract. It does not install, publish, start, or
execute a successor release.

D1S1 is source accepted and integrated at:

- HEAD `88d6a4ba11a77ca4a7b04b102b914e9e4ea9bd96`
- tree `eae9ad713620f1a030a981f27e0a2672d0222fa0`
- feature CI `39754184070`, attempt 1, SUCCESS
- preserved failed first source attempt `39751885721`
- post-merge `develop` CI `39756068943`, attempt 1, SUCCESS

The original F1 remains FINAL / INDETERMINATE / CONSUMED. C2 remains consumed
immutable evidence. D1 successor execution remains unauthorized. The next
boundary is installed-release/readiness. Architecture 145 remains separate
and offline, and live remains NO-GO.

The implementation is intended for branch
`feature/robinhood-production-paper-134f1r1-successor-readiness-current` in
the fresh worktree
`F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-successor-readiness-current`.

## Source and release policy

`SuccessorSourcePolicy` requires the exact accepted repository remote, an
explicit `refs/heads/...` or `refs/tags/...` ref, nonzero accepted HEAD/tree
identities, and the canonical complete source-path tuple. It deliberately
does not contain a guessed future commit. A separately reviewed protected
operator must supply the exact accepted D1S2 HEAD/tree after ChatGPT source
acceptance.

`SuccessorReleaseDeclaration` replays the existing `ReleaseBundle` and
`VerifiedRelease`, checks the complete manifest/source inventory, requires the
canonical `RuntimeBinding`, and joins those bytes to the explicit source
policy. Installed bytes alone cannot infer accepted source identity.

The future image is valid only at
`F:\AITradingBot\releases\<release-id>` and only with
`F:\AITradingBot\runtime\python.exe` under `-I -S -B`. A mutable Git
checkout/worktree is not an installed runtime and cannot satisfy admission.

## Read-only installation split

The successor-specific observer classifies the exact derived final release
path and its sibling `.installing` staging path as:

- `INSTALL_REQUIRED`: both exact paths are absent and a later one-shot
  Architecture-133 installation operation may be reviewed separately;
- `ALREADY_INSTALLED_EXACT`: the final image, installed evidence, manifest,
  binding, and object identity agree exactly and staging is absent;
- `BLOCKED`: a conflict, foreign object, consumed/malformed evidence, replaced
  object, or other policy violation is observed;
- `INDETERMINATE`: observation is incomplete or cannot prove the state.

Readiness observation never creates the release root, writes evidence, deletes
conflicting material, retries an ambiguous entry, or repairs production state.
An old final release or `.installing` object fails closed. A later protected
installation operation must use fresh one-shot durable attempt authority and
the accepted Architecture-133 installation engine.

## Successor-root observation

The frozen logical root is
`F:\AITradingBot\Arch133\arch134-f1r1-d1-successor-soak-v1`. D1S2 defines an
injected native/read-only observation seam; it does not create this root.
The observer distinguishes:

- `ABSENT_ELIGIBLE`;
- `EMPTY_FRESH_ADMITTED`;
- `ALREADY_BOUND_EXACT`;
- `ACTIVE_CURRENT_EXACT`;
- `CONFLICTING_FOREIGN`;
- `ALIAS_OR_REPARSE`;
- `WRONG_PARENT_OR_POLICY`;
- `REPLACED_OBJECT`;
- `CONSUMED`;
- `MALFORMED`; and
- `INDETERMINATE`.

Positive root observation requires the exact production path and parent,
directory kind, local NTFS storage, no reparse point or alias, one link, the
accepted owner and protected image ACL, stable object identity, and either the
empty fresh namespace or the quiescent progression-ready parent/session-01
namespace with `STORE_IDENTITY`. Active reservations are not positive fresh-
manual-start readiness. A second read detects replacement or drift. The C2 root
`F:\AI\temp\qualification\arch134-f1r1-host-isolation`, old-F1 namespaces,
and historical qualification evidence cannot substitute.

## R3A root-state refinement and R3 session binding

ChatGPT reviewed the unpublished R3A refinement in principle and required the
additional R3 phase/date invariant below. These are successor refinements;
the original D1S2 source did not explicitly implement them. The accepted D1
controller/evidence codecs and fixed tuple remain unchanged.

Child reservation consumption is permanent and per-attempt. Root-level
`consumed` means no legally usable current continuation or future fixed-ordinal
grant remains. A progressing child 01 remains consumed while the same parent
can still admit exactly one fresh child 02 from a fresh manual process.
`evidence_complete=True` means phase-complete canonical replay, not completion
of both sessions or the entire series.

| Current phase | Exact filenames | Fresh-start classification |
| --- | --- | --- |
| Before session 01 | none | `EMPTY_FRESH_ADMITTED` |
| Session 01 active in its exact owning process | parent + session 01 | `ACTIVE_CURRENT_EXACT`; no fresh start |
| Benign session 01 final, before session 02 reservation | parent + session 01 | `ALREADY_BOUND_EXACT` |
| Session 02 active in its exact owning process | parent + both sessions | `ACTIVE_CURRENT_EXACT`; no fresh start |
| `SERIES_COMPLETED` or `SERIES_HALTED` | exact replayed phase namespace | `CONSUMED`; no fresh start |

`ALREADY_BOUND_EXACT` means only quiescent progression-ready exact state:
`names == (PARENT_NAME, SESSION_NAMES[0])`, exact `STORE_IDENTITY`, phase-complete
evidence, `consumed=False`, and `malformed=False`, with the existing exact
physical-root/security/stability facts. Session 01 must end in `NO_SIGNAL`,
`RISK_REJECTED`, or `PAPER_EXECUTED`; the parent must contain its exact
`SESSION_01_FINAL`, no `SESSION_02_GRANT_INTENT`, no session-02 file, and no
series terminal. Filenames alone never establish those facts.

`ACTIVE_CURRENT_EXACT` means a replay-valid nonterminal reservation bound to
the exact currently observed owning manual process, exact parent/grant prefix,
and exact prior progression. Only that process may legally continue the
already-consumed child. D1S2 fresh-start readiness returns
`BLOCKED / CURRENT_MANUAL_START_ACTIVE`, not positive installed-release
preflight readiness. It creates no continuation or effect authority.

A gone/mismatched owner after reservation is `CONSUMED`; unprovable ownership
or liveness is `INDETERMINATE`. Active/orphaned reservations never become new
start authority and never permit a second reservation of the same ordinal.
The R3 native observer derives these facts from actual parent/session replay
and exact process observation. Pure D1S2 checks the relationship independently:
`EMPTY_FRESH_ADMITTED` requires the admitted process date `SESSIONS[0]`, and
`ALREADY_BOUND_EXACT` requires `SESSIONS[1]`. Both exact observations are retained
when a mismatch returns `BLOCKED / MANUAL_START_SESSION_MISMATCH`; it cannot
produce a RUNNING manual-start transition. Positive result construction also
rejects an inconsistent phase/date pair. Native adapter code belongs to D1S3;
this D1S2 module remains pure and effect-free.

## Readiness composition

The exact source-only chain is:

`Architecture-133 release/binding -> Architecture-133 host admission -> F1R1-A installed-runtime admission -> F1R1-B host readiness -> D1 STORE_IDENTITY/root/process observation`

The manual lifecycle remains exactly:

`RUNNING -> shutdown/reboot/logoff -> STOPPED after boot/login -> optional read-only reconciliation -> explicit operator start -> fresh release/runtime/host admission -> RUNNING`

The result
`READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT` is closed and positive
only when the accepted source policy, complete release bundle/inventory,
canonical binding, exact installed-image observation, production runtime and
process evidence, Architecture-133 host binding, F1R1-A, F1R1-B, D1 lineage
and `STORE_IDENTITY`, exact successor namespace, repeated stable observation,
manual-start transition, and all zero protected-effect counters are present.

It grants only the right for ChatGPT to review a separate protected
installation/readiness operator boundary. It grants no provider, credential,
paper, broker, D1, D2, live, scheduler, service, boot, logon, resume, retry,
catch-up, or automatic-recovery authority.

## Launcher classification

`scripts/run_arch133_supervised_release_review_paper.py` is unchanged. Its
current Architecture-133 launcher is an immutable `-I -S -B`, no-caller-args,
fixed-release-root/fixed-site-packages, no-pycache launcher that imports only
runtime admission and then fails closed. D1S2 explicitly records that it is
an inert launcher/runtime-host gap. Wiring it to provider or paper execution
would cross the current readiness boundary and is deferred. A future
readiness-only entry, if separately reviewed, may only observe, emit closed
status evidence, and exit.

## Effects and next boundary

All protected effect counters are fixed at zero: installation, publication,
successor provisioning, scheduler reads/mutations, credentials, provider,
paper, broker, D1, D2, and live. Tests use injected fakes only. No real
successor root, installed release, scheduler task, credential, or provider
request is created or read by D1S2.

After exact source review and acceptance, the next separately reviewed step is
a protected operator preflight that constructs the exact accepted successor
bundle, classifies the exact installed state, and—only if explicitly accepted
by that later boundary—installs/observes the immutable release and returns a
closed readiness result. That step remains outside D1S2.

Also remove or update any tests and docs that referenced the old behavior.
