# Manual guarded capture-only runner

The manual runner composes the existing local authorities for one explicit,
capture-only attempt. It is invoked directly with a strict nonsecret config:

```text
python scripts/run_guarded_capture.py --config <absolute-runner-config.json>
```

The sequence is fixed: validate configuration, derive the session and launch
identities, acquire the Windows named mutex and publish the lease start,
verify the lineage head, verify the explicit production XNYS-hours authority,
load the fixed capture policy and Credential Manager reference, verify the
pointer-selected attempt history, evaluate pure readiness, publish the exact
readiness decision, allocate one authoritative attempt, publish one isolated
child request, launch the child once, verify its process/result/snapshot
evidence, publish one schema-2 terminal, select a verified success, re-evaluate
readiness, and release the lease before closing the mutex handle.

The parent process never reads or carries brokerage secrets. The child receives
only the nonsecret Credential Manager reference and reads the secret after its
own SID gate. The child contract is fixed to long-only SPY/QQQ daily RAW data
from the ALPACA_MARKET_DATA descriptor using the SIP feed and USD. The provider
call budget is exactly one; no retry, fallback, reconciliation, paper
operation, strategy, target, scheduling, lineage advance, or repair is part of
this runner.

The runner fails closed when the official production XNYS-hours provenance is
unresolved. Existing structural schedule fixtures are not treated as
production authority. Timeout, forced termination, missing result, or any
post-resume evidence gap is ambiguous and never becomes zero-call proof.
Ambiguous history remains for manual review; the runner does not repair it or
reuse the attempt.

The current mutex implementation uses the process default DACL when
`ALLOW_DEFAULT_DACL` is selected and reports that the DACL is not hardened.
`REQUIRE_VERIFIED_DACL` remains unsupported. Therefore unattended operation is
not enabled by this milestone.
