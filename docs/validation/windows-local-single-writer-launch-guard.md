# Windows local single-writer launch guard validation

## Scope

Focused tests validate deterministic lease schemas, native outcome mapping,
ownership lifecycle, abandoned-owner handling, conservative evidence
publication, and a gated real-Windows mutex integration. They do not invoke
market-data capture, readiness evaluation, paper-operation execution, lineage
head advancement, credentials, providers, brokers, notifications, retry, or a
scheduler.

## Golden vectors

The reviewed schema-1 vectors are:

| Artifact | UUID | Canonical-byte SHA-256 |
| --- | --- | --- |
| lease start | `95706ff2-56b8-5bb1-860e-9e2ac4179a3d` | `d95b0ceeac22b4e9fd4b5b259bf058f6097dea03b46fe7a950465d6be3e2121a` |
| lease release | `190f1034-cd47-525e-92d4-7f89e0241dc4` | `5caf0cbdefa1e0f7e183fae9631cb7dbffde3ea32f4ab36c38bb7f437c61766c` |

Tests prove round-trip canonical bytes, content-bound start references, identity
changes for changed explicit evidence, and rejection of wrong identities,
noncanonical JSON, duplicate members, unknown members, BOMs, and floats.

## Native and lifecycle coverage

Injected-adapter tests cover all nonplatform acquisition classifications,
bounded timeout propagation, no evidence for nonacquired outcomes, private
handle ownership, exact-once release/close, context-managed release from
pre-supplied evidence, use-after-release rejection, publication failure cleanup,
release-publication failure with native release still attempted, and native
release failure requiring manual review.

The abandoned-owner test proves that start evidence records
`ABANDONED_ACQUIRED`, the result is explicitly unsafe, and release remains
available without authorizing domain work.

## Filesystem coverage

Tests cover safe child creation, exclusive staging, flushed canonical bytes,
bounded reread, fixed final names, identical-byte idempotency, preservation of
crash-left/unexpected entries, conflict failure, release-before-native ordering,
and release after publication failure. Existing evidence is never repaired,
overwritten, or removed.

## Real Windows integration

Windows-gated tests use the actual global named mutex. One test holds ownership
on a worker thread, proves a zero-timeout contender receives `ALREADY_HELD`,
then publishes release evidence and releases from the owning thread. A child
process test exits while owning the mutex and proves the next bounded wait
returns `ABANDONED_ACQUIRED`; the caller publishes abandoned start evidence,
performs no domain action, publishes release evidence, and releases.

On non-Windows platforms these integration tests are skipped. There is no
fallback lock implementation.

## ACL validation

Tests prove `REQUIRE_VERIFIED_DACL` returns `UNSUPPORTED` without calling the
native API. Default-DACL mode reports `NOT_IMPLEMENTED`; no ACL hardening claim
is tested or made.

## Required regression commands

```text
python -m pytest tests/runtime/test_launch_guard.py
python -m pytest tests/cli/test_windows_launch_guard.py
python -m pytest tests/cli/test_windows_launch_guard_integration.py
python -m pytest <related scheduled-readiness, lineage-head, and safe-output tests>
python -m pytest
ruff check .
ruff format --check .
git diff --check
```

