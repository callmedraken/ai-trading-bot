# Architecture 134-F1R1-C1: standalone qualification operator

Status: implemented source/test checkpoint, pending exact-source review. No
external exercise is performed or authorized by this implementation record.

## Additive evidence split

C1 resolves the disposable-host assumption in B's historical external plan.
Architecture-133 installed-host admission is production-specific; a disposable
process cannot truthfully satisfy it. B remains the accepted historical contract.
C1 does not change ReleasePaths, release_root, PRODUCTION_PYTHON, SITE_PACKAGES,
process/substrate validation, InstalledEvidence, RuntimeAdmissionEvidence,
RuntimeAdmissionResult, Architecture133HostBinding, either B binding/readiness
function, or F1R1-A production admission. No qualification exceptions are added.

C1 owns distinct exact dataclasses for qualification fixture manifest, fixture
evidence, interpreter/process evidence, and admission result/status/reason.
They neither inherit from nor substitute for production evidence. Its closed
readiness is READY_FOR_F1R1_C2_EXTERNAL_QUALIFICATION. Its operational identity
uses qualification-<sha256>, with versioned source inventory, logical predecessor
reference and interpreter version/hash material; paths, clocks, PID and development
Git state do not enter that identity. No result grants successor-soak authority.

## Logical predecessor reference

scripts/arch134_f1r1_qualification_reference.json binds accepted B HEAD
3f2e75f3daee40dfcf094b6057ae1a91f8de8928 and tree
6c53d02418f19769cab7851b5a8dbdbf0acfe514. It contains a complete logical release
manifest over 499 exact Git blobs using the established Architecture-133
strategy/risk declarations, and the pure RuntimeBinding projection. Source tests
independently reconstruct the bundle from that accepted Git commit and use
verify_release_bundle and RuntimeBinding replay. This is a C1 logical reference
to verified accepted source bytes, not a claim about a historical installed image.
No production launcher is used as a qualification launcher or executed.

The reference records release-9cc8db2758205a77a003dd8d6de842e4, manifest SHA
95729fb785e1a9a8b1db8ca396d11c10c57ea73aabce945f56f3efcc209ab13c,
binding SHA 3f8f66df6a093408e0c4d4a4e86b6b6ba99363b611f7d5f565fda41a38c11a13,
and source inventory SHA
ace036c1c1a9d03cdb75a0500ebc8fefa24d1d94ce14393aba3aec6bbe693c99.
Frozen A/B source maps and successor digests are included unchanged. The whole
reference is externally source-pinned and its SHA is checked by the host.
No InstalledEvidence or production runtime-host evidence is fabricated.

## Fixed disposable namespace and fixture

The sole ordinary operator root is
F:\AI\temp\qualification\arch134-f1r1-host-isolation. CLI commands are exactly
prepare, run, status, stop, verify. No path/PID/environment override exists.
Tests inject roots through a private Python-only seam. Equal/descendant
F:\AITradingBot paths, links, reparse points and noncanonical paths are rejected
before access. Existing partial artifacts are preserved, never repaired.

prepare first checks its exact executable bytes against the reviewed C1 source-pin
metadata as inert AST data; it never imports or executes the production runner.
The external C2 source review supplies authority for that initial source snapshot.
Later admission never reads that development metadata. prepare creates fixture/ with only the dedicated launcher, qualification host,
read-only process observer, pinned logical reference, and deterministic manifest.
The manifest covers every executable fixture byte, interpreter observations and
zero protected counters. Files receive read-only attributes to deter accidental
edits; this is hash-bound disposable source, not an Administrator-protected
production ACL/installation claim. Coherent malicious replacement by the owning
user is outside this process-isolation exercise. Re-prepare only inspects an
existing complete fixture; no reset, overwrite, cleanup or upgrade exists.

The ordinary run bootstrap re-execs the observed interpreter with -I -S -B and
the prepared dedicated launcher. The host executes and imports only fixture
source and standard-library modules. It does not import trading_bot or require
site-packages, development files, Git/GitHub, a remote ref or checkout cleanliness.
The actual OS image executable (including Windows venv redirector behavior),
canonical path, version, SHA-256 and stable file identity are revalidated.
An interpreter under F:\AITradingBot is forbidden. It is qualification Python,
never the Architecture-133 production Python declaration.

## Lease, process and durable state

Fixed artifacts are lease.lock, process.json, lifecycle.jsonl, stop.json,
result.json and duplicate.json. A single exclusive process reservation consumes
the attempt before lease acquisition. The lease uses the reviewed standard-library
nonblocking byte-range pattern: msvcrt on Windows, flock for disposable POSIX tests.
OS ownership closes automatically on death. Persistent lock-file existence is
never authority. There is no deletion, stealing, takeover, timeout or reacquisition.
A duplicate start is rejected and preserves a duplicate marker; positive verify
then fails. A consumed attempt never re-enters the lease.

Only successful lease acquisition permits SUPERVISOR_LOCK_ACQUIRED, loop entry
and SAFE_WAITING. Lifecycle JSONL is bounded, canonical, append-only, exact-order,
sequence/runtime-bound, flush/fsync/readback committed, and replayed before append.
NORMAL_RETURN or CAUGHT_INTERNAL_FAILURE commits before explicit lease release.
Unexpected setup/append failure preserves nonterminal evidence; process exit
releases OS ownership but supplies no fabricated terminal record.

status and verify do not modify durable evidence. They combine replay with a
read-handle shared-lock probe and stable process identity. The probe never takes
exclusive host authority. Windows observation uses only
PROCESS_QUERY_LIMITED_INFORMATION plus GetProcessTimes, exit code and executable
image query. Linux tests use boot ID, process start ticks and executable origin.
PID reuse is rejected; an unavailable observation is conservatively UNPROVEN.
Concurrent incomplete transitions cannot return a positive waiting/completed result.

stop writes only the fixed qualification signal for the admitted waiting host;
it never targets or controls a PID. Repeating the same signal is idempotent.
It may cooperatively stop the original host after a duplicate-start rejection,
while duplicate evidence continues to block verification.

verify returns distinct prepared, RUNNING_SAFE and COMPLETED results. Completion
requires exactly one recorded lease authority, canonical terminal replay,
matching manifest/process/lease evidence, a released lease and exact final result.
A live exact process plus held lease and SAFE_WAITING proves running; disappearance
without a terminal record is abrupt, never repaired or automatically restarted.
COMPLETED alone does not prove development/Codex-restart survival: the separately
reviewed C2 exercise must compare its independent baseline observations.

## Effects and source gate

F1, credential, provider, scheduler, production installation, paper, broker, D1,
D2 and live counters are closed exact zeros in manifest/process/journal/result.
Disposable fixture creation is explicitly QUALIFICATION_ONLY_LOCAL_MATERIALIZATION.
There is no production SQLite, F1 evidence, provider, credential, broker, trading,
scheduler/service, installation or successor-soak capability.

arch134-f1r1-c1-qualification-operator is source-only with preflight=None,
execute=None and remote_head_env=None. The existing reviewed robinhood-* push
family admits its branch; GitHub owns canonical ROBINHOOD certification. Explicit
C1 source/test/current-inventory and active-inventory overlays preserve the frozen
predecessor dictionaries/digests. Current profile inventory becomes 195 FULL /
106 ROBINHOOD / 222 LEGACY / 417 EXHAUSTIVE; required 122/49 baselines and existing
lane placements remain unchanged. FULL timing metadata adds the single C1 module.

The later human-only seven-phase exercise is in
../operators/arch134-f1r1-c2-external-qualification.md. C1 source work does not
perform fixed-root prepare/run, restart Codex, authorize a soak, or claim source
acceptance.
