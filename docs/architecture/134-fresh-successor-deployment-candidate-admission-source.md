# Architecture 134 — Frozen fresh-successor candidate / admission source

Status: SOURCE IMPLEMENTED; publication, terminal CI and ChatGPT exact-source
review pending. Source selection only. Live remains NO-GO.

## Exact selection and distinct implementation source

    repository callmedraken/ai-trading-bot
    candidate reference develop
    candidate HEAD 61836d6adadf25907c0347d42012bc4200a179ff
    candidate TREE eabbf166db2d14ce7fed603df3f8b6762394e3c7
    accepted successor HEAD b18c6e32606828beeebc540a93c9f05e3e024323
    accepted successor TREE b082c15bc697bf289fc7997b3d7bf87050082dc3

The candidate is terminal-green R3N develop: feature #733 / 40271136792 and
develop #734 / 40271802280, both original attempt 1 SUCCESS. #734 reused
`exact_feature_broad_source_gate` without duplicate broad execution. Primary
local develop was reconciled to the exact candidate before this checkpoint.

This selection is not an installed production image. The new admission-source
implementation is a separate descendant commit, whose final HEAD/tree/terminal
CI are reported after publication and require ChatGPT exact-source acceptance.
No self-hash, production manifest, release ID or future installed destination is
predicted here. Later host admission must prove the exact accepted selection
and the separately accepted implementation/integration lineage. Normal develop
integration advancing beyond the selected commit does not silently select a new
production candidate. A replacement candidate requires a new reviewed freeze.

`deployment_candidate.py` contains frozen typed source identities and canonical
JSON evidence. UUID5 uses explicit versioned logical repository/ref/HEAD/tree,
accepted-successor and consumed-state fields. It excludes clocks, ordinal host
state, artifact bytes and filesystem paths. There is no freeze wall clock.
`verify_candidate` checks exact canonical evidence and an independently supplied
selection-time develop identity. A stale or changed selection-time identity is
rejected; this pure verifier never reads Git or certifies current host state.
The later host observer must prove candidate ancestry in the exact separately
accepted integrated source, rather than demand that develop never advance.

## Consumed and incident closure

R1 is reconciled and permanently CONSUMED. No latch is read, written or renewed.
These preserved incident roots and their underlying release IDs are forbidden:

- F:\AITradingBot\releases\release-18d5d329c1d458558e98d7effe523c3b
- F:\AITradingBot\releases\release-cb94451fc3295a97afffe9fac5d09ff3.installing
- F:\AITradingBot\releases\release-03c42597246752319956ab96e01ed61c.installing

They remain non-authoritative immutable evidence. Do not traverse, repair,
rename, delete, reuse or trust them. Exact lexical final-path validation rejects
incident release IDs even without the historical .installing suffix. It also
rejects alternate spellings, aliases and destinations outside the fixed namespace.
Lexical validation cannot establish real filesystem identity or safe absence.

Deployment mode is fresh successor only. A later generation receives one unique
final directory identity before creation and keeps that identity through logical
admission and binding. No directory rename/move/reparent/replace/alias promotion
or consumed-generation reuse is allowed. Historical D1S4/R1/D1S3/R5 operators
cannot substitute for the new boundary. The accepted successor source and all
predecessor implementations, authority dictionaries, latches and incident reports
remain exact; an additive before/after overlay admits only this checkpoint's
specific test/workflow-doc successors and pins the new pure source/guard code.
At this required runner-touch checkpoint, the current checker skips obsolete
status/handoff blob checks under the normative mutable-doc rule; their literal
historical maps and all executable pins remain intact.

## Next read-only admission contract

Boundary: `arch134-fresh-successor-readonly-deployment-admission`.
`readonly_admission_design` is an inert descriptor. There is no host observer,
preflight/execute dispatch or host-admission PASS in this checkpoint.

A separately reviewed observer must bind complete canonical evidence to exact
accepted candidate and implementation source identities, source inventory,
strategy/config and production Python identity, exact successor ancestry, and a
fresh release-derived destination/attempt. It must independently establish
kernel-resolved namespace/ancestor/volume/object identities and safe absence of
final or partial successor material without following aliases into incident
objects. Missing, conflicting, changing or indeterminate observations STOP.

Observe the current Windows principal SID, elevation, groups/privileges, parent
owner/security descriptors, inherited/effective access and relevant filesystem
security capabilities. Report unavailable SACL/security facts explicitly; do not
enable privileges or mutate ACLs to obtain them. Observe recovered parent policy
and predecessor closure without renewing consumed authority. Establish disabled/
quiesced scheduler and absent active runtime through read-only metadata only;
never start a runtime or invoke a provider/broker to gather evidence.

Prove absence using safe parent metadata; do not create a test file/root or
access credential/provider material. No writes to production, ACL mutation,
namespace promotion, scheduler/runtime mutation, network/provider acquisition or
broker/live activity may occur. External evidence output for that later observer
needs separately reviewed bounds; this design grants no write authority.
A read-only admission PASS would support the next write-authority / ACL review,
not grant materialization, binding, runtime or soak authority. Ambiguity preserves
all evidence and prevents automatic repair, retry or consumed-path reuse.

## Frozen future sequence and authority

terminal-green develop production candidate
-> exact fresh-successor deployment-admission source
-> ChatGPT exact-source acceptance
-> develop integration + terminal gate
-> local-main reconciliation
-> real-host READ-ONLY deployment admission
-> successor-root write-authority / ACL review
-> separately reviewed protected fresh materialization
-> manual-start fresh F1 successor soak
-> fresh F1 evidence
-> Architecture 145-B
-> Research Results GUI
-> large strategy campaigns

No later step is authorized merely because this source checkpoint exists.
Architecture 146-B is not started. The module exposes no host/network/native,
scheduler, provider, credential, runtime, paper, broker, F1 or live entry point.
Import, parsing and verification are pure. Every eligibility flag remains false.
The source guard rejects effect imports/calls and retired deployment dispatch;
exact source pins provide an additional fail-closed non-regression boundary.

## Source verification and publication

Use the existing current successor test module; module ownership, required
122/49 baselines, six/four lane topology and active registry remain unchanged.
The new feature/robinhood-* branch is already admitted by the base workflow and
uses its existing unregistered four-shard broad source gate. No new canonical
profile mapping or local FULL/ROBINHOOD run is introduced.

Before edits, prove exact base/branch/origin/cleanliness. After focused checks,
create one exact-file atomic unpublished commit, run PRE-PUBLICATION
`ops.ps1 admit` on its clean strict-descendant HEAD, then ordinary-push once and
poll CI to terminal. Preserve the earlier pre-edit admission failure as sequencing
evidence; it requires no code fix or published corrective checkpoint. Any bounded
terminal-red correction follows the current R3N workflow, preserving failed runs.
See [validation](../validation/arch134-fresh-successor-deployment-candidate-admission-source.md).

Next owner: ChatGPT exact-source/terminal-CI review. Do not run real-host admission,
materialize a release, start F1 or begin Architecture 146-B in this task.

Also remove or update any tests and docs that referenced the old behavior.
