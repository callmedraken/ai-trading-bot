# AI Development and Review Workflow

## Standing authorization for reviewed next steps — current normative rule

Reviewed next-step actions are implicitly authorized by default within their
exact described scope. ChatGPT must not insert an authorization-only turn to
obtain a one-word approval for a bounded action it already reviewed and presented.
For a supplied local command, the user's decision to execute it constitutes
authorization for exactly its described effects and bounds. The user withholds
authorization by not executing it and calling it out for manual review.

This does not broaden a command, authorize unexpected effects or ambiguous/
partial-state repair, permit automatic retry after ambiguity/partially consumed
effects, override real-money NO-GO, or make source/commit authority alone
sufficient for integration. Separately, the user has granted ChatGPT standing
authorization for an ordinary reviewed feature-branch merge into `develop`
after ChatGPT independently determines exact review, required certification,
and merge readiness are complete. That integration authorization does not
extend to Codex, rebase, amend, force-push, pull-request mutation, protected
effects, or ambiguity repair/retry. Unexpected, ambiguous, partially completed,
source-mismatched or broader-than-reviewed effects remain STOP / reconciliation.
Protected source/effect separation, prerequisite checks and reviewed interlocks
remain mandatory. Source or preflight PASS alone grants no effect authority.

After a successful checkpoint, automatically include and proceed to the next
reviewed safe step within scope. A separate new authorization message is not
universally required for reviewed bounded operator actions. Historical accounts
of separate authorization remain historical and do not override this current rule.

## Architecture 132-R3M — predecessor exact develop certification reuse

A develop push retains mandatory source-static classification, exact local
HEAD/tree/branch and origin admission, fast-forward ancestry proof, full-batch
static/authority verification, workflow topology checks and terminal source-gates.
Only redundant broad execution may be skipped. Reuse is optional and requires
one terminal-success push run from an exact registered checkpoint in the reviewed
feature/robinhood-*, feature/research-* or feature/test-suite-* family, for the
identical commit SHA and tree in the exact repository/workflow. Reusable feature
certification is limited to the original push-triggered first attempt: the run,
run detail and every required job must report `run_attempt == 1`. An unchanged-
source rerun, including a coherent successful attempt 2, is never reusable
integration evidence. Source-static, active-tests, source-gates and the
explicitly checkpoint/profile-named canonical certification job and its
execution/hygiene steps must all have succeeded in that same first attempt. The
source-owned profile mapping remains authoritative.

GitHub Actions metadata is read with job-scoped actions:read. The lookup uses
bounded complete metadata pages and records the selected run/attempt/jobs in
source-static's develop-integration-reuse.json evidence. Missing, malformed,
truncated, unavailable, stale or ambiguous evidence means ordinary four-shard
develop broad fallback. SHA changes, including tree-equivalent commits, are
ineligible. Caller-supplied run IDs and artifact names are not certification proof.
Older runs without the explicit checkpoint/profile job binding also fall back.

Feature FULL/ROBINHOOD execution, active source-only checkpoints, docs-only and
pull_request routing remain unchanged. FULL retains six timing-aware lanes;
ROBINHOOD retains four; neither has a serial lane. The 300-second ceilings,
inventories and predecessor authority pins stay intact through an additive R3M
overlay. This checkpoint's reviewed test-suite branch uses normal broad source
CI; no new feature certification mapping or local canonical run is introduced.
ChatGPT owns exact-source review and any selected certification before integration.
No provider, holdout, ACL, scheduler, runtime, broker or live authority follows.

## Architecture 132-R3N — workflow throughput and current-contract consolidation

R3N preserves R3M's exact develop-push admission and extends the reusable
feature evidence set. A develop push may reuse one exact first-attempt mapped
FULL/ROBINHOOD certification, one exact first-attempt registered ACTIVE plus
four-shard broad feature gate, or one exact first-attempt unregistered
four-shard broad feature gate. Broad reuse requires the same repository
identity, active workflow identity, push event, exact SHA/tree, admitted feature
branch family, terminal success, the exact route-specific job set, successful
source-static/source-gates and required execution/hygiene steps, and one unique
qualifying run. Attempt 2 or later, malformed/truncated/ambiguous/unavailable
metadata, missing jobs or steps, unexpected active/certification routing, and
any mismatch fall back to the normal four-shard develop run. Artifact names are
never provenance.

C4 corrects the broad-route skipped certification identity to GitHub's literal
workflow display-name expression:
`certification-tests (${{ needs.source-static.outputs.checkpoint }} / ${{ needs.source-static.outputs.certification_profile }})`.
Both broad routes require that exact job, completed/skipped; registered ACTIVE
also requires active-tests success, while unregistered FULL requires it skipped.
The evaluated-empty name `certification-tests ( / )`, missing/duplicate jobs,
unexpected certification execution and all later attempts remain ineligible.
The fixture models the actual #732 job topology; exact set equality remains.
C4 adds successor authority without rewriting R3M/R3N/C1/C2/C3 literals.

`ops.ps1 admit` is the GENERAL ordinary-feature prepublication gate, not an
R3N-only gate. It performs a read-only remote identity check against the exact
current `origin/develop` commit/tree and admits only clean descendants in the
reviewed `feature/robinhood-*`, `feature/research-*`, or `feature/test-suite-*`
families with a nonempty feature diff. It then checks path classification,
Ruff/diff checks, current authority and workflow topology,
inventory/profile reconciliation, nonempty FULL/ROBINHOOD/LEGACY/EXHAUSTIVE
lane construction, and the small current contract tests. It does not reset,
rebase, merge, repair or rewrite source history, and it does not execute
protected effects or canonical FULL/ROBINHOOD certification.

Pre-edit admission checks the exact base, branch, origin, remote identity and
clean worktree/index. `ops.ps1 admit` is PRE-PUBLICATION admission: run it on
the clean committed candidate after implementation/focused checks and before
the first push. A new branch exactly at develop is intentionally ineligible;
do not weaken the strict-descendant/nonempty-diff gate or run it before edits.
If this unpublished admission fails, preserve its report and classify it before
any push. Replacing an unpublished candidate commit requires explicit task
authorization; the standing prohibition on rewriting published history remains.

One logical checkpoint still receives one prepared atomic commit/push and one
CI admission. A red attempt is preserved; a bounded mechanical correction is a
separately named checkpoint with fresh focused verification and a fresh
pre-publication admission. Codex remains owner across such corrections until
terminal green, without an arbitrary C1/C2/C3 cap. Non-reproducible,
semantic/security/authority, protected-effect, unexpected-state, or
material-scope failures stop for ChatGPT review. Current certification counts,
lane topology, and workflow-contract assertions are owned by the current
certification/profile/lane/CI test surfaces; historical review-paper tests
retain predecessor and incident evidence only.

## CI-owned selected certification — normative expedited path

For reviewed coherent integration checkpoints, the source gate may own the
selected Architecture-132 certification profile directly. The mapping from exact
checkpoint name to `robinhood` or `full` is source-owned, explicit, and
fail-closed; there is no heuristic profile selection.

For a mapped non-docs push:

- `source-static` runs first and emits the exact checkpoint plus selected profile;
- `active-tests` still runs the checkpoint-specific fast/current integration gate;
- the canonical profile runs through `scripts/run_test_certification.py` in
  GitHub Actions with the unchanged profile inventory and lane semantics;
- the redundant four-shard checkpoint-union `full-tests` job is skipped;
- `source-gates` requires source-static + active-tests + canonical certification
  success before the source may advance.

For an unmapped active non-docs push, retain active-tests plus the four-shard
broad checkpoint-union safety net. FULL fallback retains the four-shard broad
path unless the exact develop-only R3M provenance proof above succeeds. Docs-only retains the reviewed cheap path.

A terminal-green CI-owned canonical certification on the exact source satisfies
that profile obligation. Do not ask the human operator to rerun the same profile
locally. Local certification is reserved for an unmapped selected gate, invalid
or incomplete CI evidence, or materially different host/runtime evidence.

### Terminal selected-certification ownership — normative

When a milestone is known before implementation to require terminal
Architecture-132 `FULL` or `ROBINHOOD` certification, that certification is part
of the implementation agent's completion scope automatically. The human operator
must not need a separate follow-up request merely to initiate a known terminal
certification gate.

Use this order:

1. Prefer registering the exact feature/checkpoint in the source-owned
   `CI_CERTIFICATION_PROFILES` mapping before its terminal publication. The
   checkpoint's one ordinary push then owns the selected canonical profile in CI,
   and no duplicate local run is performed.
2. If the terminal feature is intentionally or historically unmapped, Codex runs
   focused verification first, creates the one intended final local commit without
   pushing it, proves the exact clean HEAD/TREE and live base, runs the required
   canonical selected profile against that exact unpublished commit, and ordinary-
   pushes once only after the profile is green.
3. A failed pre-publication canonical profile is preserved as evidence and blocks
   publication. Classify the failure and run focused correction first; never rerun
   unchanged certification merely to seek green.
4. Do not run both a local canonical profile and an identical CI-owned canonical
   profile for the same exact source. A terminal-green CI-owned profile satisfies
   the obligation.
5. Pre-publication history rewrite is never implicit. When preserving one atomic
   terminal commit genuinely requires amending/squashing an unpublished provisional
   commit after a reviewed certification correction, the current bounded task must
   explicitly authorize that pre-publication rewrite. That authority ends at the
   first push. Published commits are never amended/rebased/force-pushed under this
   rule.

Terminal certification is therefore a completion criterion for the implementing
agent, not a post-handoff chore for the human.

Protected provider/OAuth/paper/scheduler/broker operations remain separately
authorized and are never implied by source certification.

The canonical CI profile and each broad shard have a 300-second hygiene ceiling.
Crossing it is a STOP for source acceptance and triggers a test-topology/hygiene
audit; do not normalize recurring >300-second verification by increasing the
budget.

R3 is accepted on `fecc7a7aacefa2b7253f36f5077935c6b76b5810` /
`1eb3d2882af4fb06e17c9e8753d0418830e34790`, CI
**#498 / 38217916400 SUCCESS**. The mapped ROBINHOOD profile selected 92 modules
in 45/47-module lanes and recorded 8,416 passed / 1 skipped / 0 failed/errors in
170.058 seconds. Active tests passed, the redundant four-shard union was skipped,
and terminal source-gates passed. This exact result is the reference proof that
mapped CI certification replaces a duplicate human rerun.

## Canonical source-gate topology non-regression notary — normative

This rule is **normative**, not merely historical. The accepted source-gate
topology is the audited split/sharded workflow. A return to the older monolithic
single-job gate is a workflow regression and is a **STOP** condition.

The incident being notarized is:

~~~text
REGRESSED SOURCE  90f9366f4251f062985ce335bea62e1c747aa1d4
REGRESSED CI      #443 / 38111685698 SUCCESS
REGRESSED WALL    7m 04s
REGRESSED SHAPE   one monolithic source-gates job

RESTORED SOURCE   165bae500ca8f486298d4ede8b6ba7ec5237fe89
RESTORED CI       #445 / 38112755149 SUCCESS
RESTORED WALL     3m 07s
RESTORED SHAPE    source-static + four full-test shards + source-gates

CURRENT AJ SOURCE 9e37d5bf38bc0383e9f84008f8961321771d7254
CURRENT AJ CI     #447 / 38115827585 SUCCESS
CURRENT AJ ROUTE  source-static + active-tests; full-tests skipped
~~~

The accepted workflow contract is:

- `source-static` always owns classification, static checks, and authority;
- an exact registered feature-branch push routes to `active-tests`;
- an explicitly mapped integration checkpoint additionally routes to the
  source-owned canonical `certification-tests` profile and skips the redundant
  four-shard checkpoint-union batch;
- unmapped active and broad/fallback source changes without reusable exact
  develop certification retain the four duration-balanced `full-tests` shards `[0, 1, 2, 3]`;
- `source-gates` is only the terminal aggregator and must depend on
  `source-static`, `active-tests`, `full-tests`, and `certification-tests`,
  requiring the exact applicable combination, including develop-only R3M reuse;
- exact route resolution, source-gate phase controls, concurrency cancellation,
  exit-code propagation, and the terminal aggregator remain fail closed;
- docs-only changes may skip test jobs only through the reviewed docs-only
  classifier; and
- the old single monolithic `source-gates` execution path is not accepted.

The regression occurred because a later checkpoint branch inherited an older
pre-latency lineage. Therefore, before implementation on any branch whose
ancestry predates the restored split gate, the current workflow **and** matching
runner phase/shard support must be reconciled first. Do not copy only the YAML.
If the workflow topology or runner support differs from the current accepted
contract, stop before the implementation push.

This is also machine-enforced. `scripts/checkpoint_runner.py` function
`_batch_workflow_is_reviewed()` freezes the split topology, active/fallback
routing, four-shard matrix, concurrency rule, and aggregator. Source authority
must fail if that contract drifts. Checkpoint-specific tests must continue to
assert `_batch_workflow_is_reviewed()` before source acceptance. Documentation
does not replace that enforcement; both the canonical rule and executable
authority must remain aligned.


This document is the canonical working agreement for AI-assisted development in
this repository. `AGENTS.md` remains the mandatory repository rule set; this
file records the normal handoff, review, testing, and local-operator cycle in
more detail.


### Project-state reconstruction and transition quality

At the start of a new Trading Bot chat, after a substantial context reset, or
whenever the user asks to re-establish the workflow, reconstruct the current
state before recommending or authorizing work. Resolve current remote `develop`,
the primary/default startup integration reference, and read, in order, its
`AGENTS.md`, `docs/AI_DEVELOPMENT_WORKFLOW.md`, bounded `docs/PROJECT_STATUS.md`,
bounded `docs/AI_TRADING_BOT_HANDOFF.md`, and relevant current architecture/
validation documents. Then separately verify the active remote product branch
and exact executable HEAD/tree, recent commits/diff and CI through GitHub when
material. The compatibility/history mirror is optional, never a required first
startup hop. Startup documentation never substitutes for exact executable-source
admission. Read `docs/history/INDEX.md` or an immutable legacy snapshot only
when older provenance, incident reconstruction, predecessor semantics, or
disputed historical evidence is actually necessary. Git-tracked canonical docs
outrank uploaded mirrors or older chat summaries unless the conversation clearly
records a newer intentional change that has not yet been committed.

Do not ask the user to paste GitHub diffs/comments, prior Trading Bot chats,
repository files, or other project material when the available project/GitHub
retrieval tools can obtain it directly.

After reconstruction, and after every milestone/review/certification transition,
leave the project immediately actionable. A substantive transition response
should state, when applicable:

- current verified checkpoint;
- active branch and verified remote HEAD/tree;
- latest relevant implementation/certification identity;
- current unresolved blocker or protected boundary;
- immediate next step;
- recommended owner/model for that step;
- the exact ready-to-run command, ready-to-paste Codex prompt, or ChatGPT-led
  review action;
- expected success evidence and stop condition; and
- exactly what output the user should return when another review turn is
  genuinely required.

The user should not need a follow-up merely to ask what to do next, which model
to use, what command to run, what output to send back, or whether the checkpoint
is ready to advance. If the next action crosses a protected effect boundary,
provide safe preflight/readiness material and state exact reviewed effect
bounds. The user's execution authorizes only those bounds under the standing
rule; never present a protected effect as ordinary verification.

## Supervised release and unattended-runtime invariant

The supported productionization model deliberately separates unattended trading
from code deployment.

- The unattended trading runtime MUST execute an already-installed immutable
  release. It MUST NOT pull Git, install/update code, publish a new generation,
  mutate scheduler configuration, replace its own executable/source tree, or
  autonomously roll back/reprovision itself.
- Trading/runtime mode and deployment/maintenance mode are mutually exclusive.
  Deployment may switch the scheduler to a new release only after scheduled
  execution is disabled/quiesced and the absence of an active bot process/cycle
  is verified. Trading authority must remain unavailable while deployment is in
  progress.
- Releases are immutable, uniquely versioned directories. A strategy code or
  strategy-parameter change creates a new reviewed release; do not hot-reload
  source or strategy configuration into a running release.
- Promotion uses supervised scheduler rebinding to the verified launcher inside
  the new immutable release. Do not require ACTIVE->ARCHIVE or STAGE->ACTIVE
  directory renames for normal deployment. Retain the prior immutable release
  for rollback; rollback is another supervised scheduler rebind.
- Each release must bind an exact release manifest including source identity and
  the active strategy/config identity. Durable trading/account/paper state lives
  outside the immutable release tree and requires explicit compatibility or
  migration handling when its schema changes.
- If a supervised deployment becomes ambiguous, keep scheduled trading disabled
  and reconcile the scheduler/release binding read-only before taking another
  deployment action. Never let an ambiguous deployment fall through into
  unattended trading.
- Preserved Architecture-133 experimental scratch/evidence remains historical
  evidence. It is not part of the normal release path and must not be inspected,
  mutated, cleaned or reused without a separately reviewed housekeeping or
  diagnostic boundary.

### Rename-free immutable-release publication — normative non-regression

This is a **current normative architecture rule**, adopted after the repeated
Architecture-133 Windows rename incidents and the 2026-10-24
Architecture-134-F1R1-D1S3/R5 publication incidents. It is not merely historical
guidance.

The forward production-release path MUST be rename-free at the release-directory
identity boundary:

- a production release/deployment receives one unique immutable directory path
  before materialization begins;
- that same directory identity/path is the path later admitted for runtime use;
- no directory rename/move/reparent, STAGE->ACTIVE, ACTIVE->ARCHIVE,
  `.installing`->FINAL, alias swap, junction/symlink swap, or replace-existing
  filesystem operation may be required to convert an untrusted/materializing
  release into a runnable release;
- "publication" is a logical admission/binding decision after exact verification,
  not a filesystem namespace transition;
- the runtime may bind to an exact verified immutable path only after complete
  read-only verification; it must never infer readiness from a directory name;
- if materialization fails or becomes ambiguous, preserve that unique directory
  and its evidence as inert/non-runnable. A later attempt uses a new unique path.
  Do not repair, rename, promote, clean, or retry the consumed directory as a
  prerequisite for forward progress;
- scheduler/runtime rebinding may select a different already-verified immutable
  release, but rebinding must not rename either release.

The D1S3 installation publication and D1S3-R5 preserved-image publication
mechanisms are **retired forward paths**. Their consumed latches, reports, staging
directory, source, and tests remain incident/history evidence. They confer no
future retry or compatibility authority. Historical Architecture-125/133 rename
qualification/recovery modules are precedent/evidence only and MUST NOT be copied
back into a current deployment path.

The first rename-free successor implementation MUST add machine-enforced
non-regression coverage. At minimum, current-product deployment authority/tests
must reject any implementation that makes the runtime-bound release directory
depend on `FileRenameInfo`/`SetFileInformationByHandle`, `MoveFile*`,
`os.rename`/`Path.rename`, replace-existing directory publication, or an
equivalent namespace-promotion step. It must also prove that retired D1S3/R5 and
historical 125/133 publication operators cannot be selected as the current
forward deployment dispatcher.

A future decision to reintroduce directory-rename publication is an explicit
**architecture reversal**, not a correction, cleanup, compatibility fix, or
backport. It requires all of the following before implementation: a new
architecture decision explaining why the rename-free model is insufficient,
explicit user approval of that reversal, disposable-host qualification of the
exact proposed primitive, a migration/non-regression plan, and fresh source/
protected-effect review. Without all of those, reintroduction is a STOP.

## Roles

### ChatGPT / Sol

ChatGPT owns:

- architecture and milestone planning;
- debugging strategy;
- GitHub commit/diff/pull-request review;
- test-gate and certification decisions;
- merge-readiness decisions;
- production-authority and external-effect review;
- concrete next-step and next-milestone instructions.

ChatGPT also directly handles small, clearly scoped, low-risk project updates
and fixes when the desired behavior, affected files, and focused verification
surface are already known. This is the default for routine docs/status/handoff
closeout, tiny workflow/test/source corrections, and mechanical consistency
fixes where delegating to Codex would add overhead without useful isolation.
Do not hand such work to Codex merely by habit.

Direct ChatGPT changes follow the same repository discipline as delegated work:
prove exact startup identity, edit only the intended files, run the focused
checks appropriate to the change, exact-file stage/commit/push only when
authorized, and leave broad/final certification to the established gate.

After a ChatGPT-direct commit/push that triggers GitHub Actions, ChatGPT must
poll the relevant push-triggered workflow/source gate to a **terminal** state
before reporting the checkpoint complete, accepting the closeout, or advancing
to the next checkpoint. `queued` and `in_progress` are not completion. The
push is the checkpoint's single planned CI admission attempt, not an iterative
debug loop. On failure, preserve the terminal-red attempt, inspect and classify
the exact job/log evidence, and do not automatically end the same delegated
Codex task merely because the attempt ended. If the failure is reproduced and
fully classified as bounded/mechanical, declare the next separately named
corrective checkpoint, add or retain a deterministic regression where
practical, rerun the complete focused/local pre-publication gate, create one
new atomic commit/push, and poll its CI to terminal. Codex remains owner across
bounded mechanical corrective checkpoints until terminal green; there is no
arbitrary C1/C2/C3 cap. Hand back on terminal green, a non-reproducible or
unclassified failure, semantic/security/authority or remote-state ambiguity,
protected effects, or material scope expansion. Never rerun unchanged CI,
rewrite failed evidence, amend, rebase or force-push. On success, verify the
run belongs to the exact pushed HEAD.
Delegate to Luna/Astra/Sol High only when implementation size, discovery,
isolation, or architecture/security sensitivity makes delegation materially
useful.

When the next action is known, ChatGPT must provide it automatically rather
than waiting for the user to ask what to do next. Every accepted checkpoint,
certification, merge and post-merge response must include a concrete
**Next milestone / next step** section. The response should include the
actionable execution material when known: exact operator commands, expected
evidence and stop conditions, a ready-to-paste Codex prompt, or direct
ChatGPT-led work. Merely naming the next milestone is not sufficient when the
execution path is already known. When that next action is safe, fully reviewed,
and requires no new protected effect or repository-control approval, ChatGPT
should continue into it automatically rather than waiting for another prompt.

After every accepted checkpoint, ChatGPT must automatically:

1. accept or reject/fix the current checkpoint;
2. review and update `docs/PROJECT_STATUS.md` and
   `docs/AI_TRADING_BOT_HANDOFF.md` before treating the checkpoint as closed;
3. determine the next milestone/checkpoint;
4. choose ChatGPT, Luna Extra High, Astra, or Sol High according to the routing
   rules below;
5. continue automatically into the next safe docs-only, source-only,
   design-only, or read-only checkpoint when no protected approval boundary is
   crossed; and
6. enforce the exact reviewed approval boundary for production/provider effects,
   provisioning, scheduler mutation, merge/rebase/amend/force-push, PR metadata
   or review-thread changes, broker/live effects, or another explicitly
   protected action. For a reviewed bounded local command, the user's decision
   to execute it supplies approval for that exact boundary under the standing
   rule above; no additional authorization-only message is required. Keep all
   prerequisites, interlocks and STOP/reconciliation conditions intact.

If one of the two canonical status/handoff documents requires no material edit,
ChatGPT should explicitly report that it was reviewed and remains current.

ChatGPT may directly perform small, tightly scoped, low-risk mechanical source,
test, documentation, status, handoff, and workflow changes when delegation
would add overhead without useful isolation. Codex should not receive every
implementation task automatically.

This is a routing invariant, not a preference. Routine docs/status/handoff
closeouts and similarly small known-surface low-risk corrections are ChatGPT-
direct by default when the available repository tools can perform the atomic
change safely. Do not delegate such a closeout to Codex merely to create a
handoff; delegate only when discovery, isolation, implementation scale, or
safety sensitivity provides a material benefit.

### Codex

Codex is the bounded implementation agent. It should:

- implement only the already-scoped change;
- read `AGENTS.md`, `docs/PROJECT_STATUS.md`, and only relevant architecture or
  validation documents;
- run focused tests/checks during implementation;
- preserve unrelated generated/untracked files;
- when the task explicitly authorizes the checkpoint, exact-file stage only the
  intended paths, verify the staged filename set and diff check, create a normal
  commit, and ordinary-push the isolated feature branch;
- report files changed, focused commands/results, commit/push result when
  authorized, and deviations/blockers;
- after an authorized ordinary push that triggers CI/source gates, wait/poll the
  relevant run to a terminal state rather than handing back an `in_progress`
  run as completion;
- treat that push as the logical checkpoint's one planned GitHub CI admission
  attempt; preserve a terminal-red attempt and never rerun unchanged CI;
- if the source gate fails, inspect and classify the preserved evidence. When
  the failure is reproducible and bounded/mechanical, Codex remains owner,
  adds or retains a deterministic regression where practical, reruns the
  complete focused/local pre-publication gate, and declares the next correction
  as a separate corrective checkpoint before another ordinary push. Continue
  automatically through such corrections until terminal green; there is no
  arbitrary C1/C2/C3 cap. Stop for non-reproducible, semantic, security,
  authority, protected-effect, unexpected-state or material-scope failures;
- stop before broad local certification unless the task explicitly says
  otherwise.

If the task does not explicitly authorize commit/push, Codex stops before those
Git operations and reports the local changes.

## Model selection

Use the smallest model class that fits the *uncertainty and safety profile* of
the task, not simply the number of files changed.

### Luna Extra High — known contract, known surface

Use **Luna Extra High** by default when:

- the contract is frozen or nearly frozen;
- the relevant entry points and affected files are already known;
- the focused tests/checks are obvious;
- the work is localized, mechanical, or a small bounded correction;
- implementation should follow an established pattern rather than discover a
  new one.

Typical Luna work includes known-file feature implementation, focused test
additions, narrow bug fixes with an established root cause, small refactors
under a frozen contract, and routine docs/help updates.

### Astra — discovery-aware bounded implementation

Use **Astra** by default when the task is still bounded but useful implementation
requires broader repository understanding first, including when:

- the affected file set is not obvious at the start;
- the root cause must be traced across modules;
- the change crosses multiple non-security subsystems;
- the work is a bounded refactor, migration, hygiene, dependency, or consistency
  pass;
- hidden coupling or duplicated behavior must be found before editing;
- a broad read-only repository audit is explicitly requested.

Astra replaces **Sol Medium** as the normal middle tier for new Codex work.
Astra's broader exploration allowance is not permission to redesign settled
architecture or broaden the authorized checkpoint. If discovery reveals that
the contract itself must change, stop and return the issue to ChatGPT.

### Sol High — safety/authority escalation

Use **Sol High** for native Windows/security, production authority, ordering,
crash/recovery, credential/reference-version changes, external-effect
containment, broker/live boundaries, or other architecture-sensitive
implementation where a mistake could weaken a safety invariant.

Sol Medium is no longer part of the default routing ladder. Use it only when the
user explicitly requests it or Astra is unavailable and the task still fits the
former subtle-but-bounded tier.

A practical routing shortcut is:

```text
contract + entry points + focused tests already known
-> Luna Extra High

root cause / affected files / cross-module consequences require discovery
-> Astra

security / authority / external-effect / crash-ordering invariant involved
-> Sol High
```

Do not escalate to Astra merely because a mechanical change touches several
files. Conversely, do not use Luna to brute-force a task whose root cause or
cross-module impact is still uncertain.

Model choice never transfers architecture or acceptance authority. ChatGPT
still owns architecture, exact GitHub diff review, certification, merge or
deployment decisions, production-effect authorization, and the next milestone.

Do not use subagents unless explicitly requested.

## Standard bounded implementation cycle

The normal cycle is:

```text
ChatGPT scopes/finalizes the contract and explicitly authorizes the checkpoint
-> ChatGPT chooses direct work / Luna / Astra / Sol High from the routing rules
-> implementation occurs
-> focused tests/checks run
-> index is proven initially clean when a commit is planned
-> exact intended paths only are staged
-> staged filename set and git diff --cached --check are verified
-> normal checkpoint commit is created when authorized
-> isolated feature branch is ordinary-pushed when authorized
-> exact remote branch HEAD/tree are verified
-> relevant push-triggered CI/source gate is polled to terminal
-> ChatGPT reviews the exact GitHub commit/diff
-> ChatGPT accepts the reviewed source checkpoint
-> when the checkpoint has an explicit CI profile mapping, terminal GitHub CI
   supplies the canonical certification and no duplicate local profile is run
-> otherwise ChatGPT selects a materially distinct local certification only when required
-> ChatGPT accepts/rejects the resulting certification evidence
-> ChatGPT reviews/updates PROJECT_STATUS + HANDOFF
-> ChatGPT automatically provides and, when safe, advances into the next
   actionable milestone
```

When ChatGPT intentionally withholds commit/push authorization, Codex stops
after focused verification and reports the local change set instead.

Manual patch-file transfer or pasting a large diff into chat is a fallback only
when GitHub/tool access fails. It is not the normal review path.

For a scoped checkpoint with known paths, do not use `git add .` or
`git add -A`. Stage the exact intended files. Before committing, verify the
staged filename set and run `git diff --cached --check`. A normal feature-branch
push does not authorize merge, rebase, amend, force-push, PR metadata changes,
review-thread resolution, branch switching, or unrelated modifications.

## Frozen startup and post-write verification

Before edits, certification, deployment, or operator work in an active worktree,
verify at minimum:

```text
exact worktree path
exact branch
expected local HEAD
expected tree
expected origin/remote ref
clean index
expected worktree state
```

A mismatch is a STOP condition. Do not self-correct by switching branches,
resetting, cleaning, rebasing, force-updating, pulling across unexpected
history, deleting artifacts, or otherwise manufacturing the expected state.
Report the mismatch and preserve evidence.

After an ordinary push or an approved merge, verify the exact remote/resulting
HEAD and tree plus the expected clean local state before reporting success.
Post-merge reporting must include the next milestone automatically.

A merge does not require rerunning a broad suite merely because a merge occurred
when the exact resulting source tree was already certified. If the resulting
tree differs from the certified source tree, use the appropriate final
certification gate before accepting the milestone.

### Source-gate branch bootstrap

A new feature branch must not rely on its own first commit to add itself to an
explicit GitHub Actions `push.branches` allowlist. GitHub may evaluate the push
against the workflow trigger state that existed before that branch was admitted,
leaving the first checkpoint with no push-triggered source gate.

Before the first checkpoint push on a new branch, prove one of these is already
true on the integration/default workflow:

- the new branch matches an existing stable reviewed branch-family pattern; or
- a separate intentional workflow-registration checkpoint has already admitted
  the branch/pattern.

Prefer stable narrowly scoped family patterns (for example
`feature/robinhood-*`) over repeatedly self-registering each new milestone
branch. Do not broaden to all feature branches unless that CI-cost decision is
explicitly reviewed.

If a first push produces no workflow run, never treat silence as PASS. Classify
the bootstrap gap, preserve the branch state, make any required workflow
registration as a distinct reviewed checkpoint, and require a real source-gate
run on the resulting exact tree before source/design acceptance.

## Atomic ChatGPT-direct multi-file commits

For one logical ChatGPT-direct checkpoint, all known repository changes must be
published atomically. When two or more files belong to the same checkpoint,
closeout, workflow repair, or acceptance transition, compose them from one exact
remote parent and publish them as **one Git commit, one branch-ref update/push,
and therefore one push-triggered source-gate CI run**.

This is a strict workflow invariant:

- do not use sequential GitHub Contents-API `update_file`/`create_file`
  operations that each advance the branch for files that belong to the same
  logical checkpoint;
- status + handoff + architecture/validation + workflow documentation for one
  accepted milestone are one logical docs closeout by default;
- if a connector/API cannot atomically create the multi-file commit, STOP and
  switch to a supported Git-object tree/commit/ref path or one local exact-file
  commit/push; tool convenience does not authorize intermediate remote states;
- create blobs/tree/commit first while the branch remains unchanged, then move
  the branch ref exactly once with an expected-parent/lease check;
- verify the resulting commit's exact changed-file set, final HEAD/tree, and
  clean ancestry before treating the write as accepted;
- a separate `pull_request` workflow run caused by opening or updating a PR is
  legitimate and does not violate the rule; the invariant is one
  **push-triggered** CI run for the logical ChatGPT-direct checkpoint;
- GitHub CI is an admission gate, not the edit/test loop: complete all intended
  files and reasonable focused/local verification before the one branch advance;
- multiple branch-advancing commits/pushes are prohibited inside one logical
  checkpoint. A later push after terminal failure is a separately declared
  corrective checkpoint, not a continuation of the original attempt. A connector
  limitation, cosmetic cleanup, forgotten docs, or "try until green" is never a
  sufficient reason.

If an atomic operation fails before the branch ref moves, discard/reuse the
unreferenced Git objects as needed and retry by a supported atomic path. If the
branch has already moved unexpectedly or a partial remote state exists, STOP,
review that state explicitly, and reconcile it before any further update. Never
continue by serially appending the remaining files.

## Default startup integration reference and retired history mirror

Current remote `develop` is the sole primary/default reference for bounded
new-chat reconstruction. Read its standing rules and bounded status/handoff in
the order above, then relevant architecture/validation documents. Executable-
source authority always comes from the separately verified active product branch
and exact executable HEAD/tree. Immutable legacy megafiles remain targeted-
retrieval only.

The former `feature/project-history-storage-foundation` compatibility/history
mirror is retired. Before retirement it was fast-forwarded exactly to accepted
integration commit:

```text
HEAD  19e5859fa83656cc50dbe69f89f3badd57841165
TREE  419262d709beabdd969efa1dc7a78403af5eedcd
```

That tip was byte-identical to `develop`, had zero unique commits and no open
pull request dependency. The remote branch is deleted as part of the retirement
checkpoint and must not be recreated, synchronized, or treated as a second
integration lineage. Historical documents may name the former branch only as
historical context.

## ChatGPT-direct bounded-commit local catch-up

When ChatGPT directly creates an accepted, tightly scoped commit on the active
remote feature branch, the local worktree may intentionally be one or more
reviewed commits behind. This includes routine docs/status/handoff closeout and
tiny mechanical source/test/workflow corrections whose exact diff ChatGPT has
reviewed directly. That expected state is not treated as a generic mismatch to
repair.

Before any next local or Codex work:

1. enter the exact intended worktree and prove the tracked worktree/index is
   clean;
2. prove the current local branch is the expected branch;
3. fetch the exact remote branch;
4. prove the remote HEAD is the exact reviewed ChatGPT-direct commit HEAD;
5. prove the local HEAD is either already that HEAD or the exact known
   pre-direct-change accepted HEAD and an ancestor of the reviewed remote HEAD;
6. only in that known-behind case, fast-forward with `git merge --ff-only`
   (or equivalently `git pull --ff-only` when the same exact remote/branch has
   already been proven);
7. verify final local HEAD/tree equal the expected remote HEAD/tree and the
   tracked worktree/index remains clean; and
8. continue automatically into the next safe checkpoint when no protected or
   repository-control approval boundary is crossed.

Any other branch, HEAD, ancestry, remote, tracked/index, or fast-forward result
is a STOP condition. Do not reset, rebase, normal-merge, force-update, switch,
clean, delete artifacts, or otherwise manufacture the expected state.

This is the narrow exception that reconciles the startup STOP rule with reviewed
ChatGPT-direct remote commits: fast-forward synchronization is allowed only
after the exact known-behind state has itself been proven. It is not a generic
pull/repair mechanism.

## Testing and certification

### Normative verification and certification rules — 2026-10-11

Verification is fail-fast before longer pytest/certification execution.
These rules are normative and preserve Architecture 132's reviewed profile
ownership, required baselines, lane topology and protected boundaries.

#### 1. Cheap deterministic gates first

Before longer pytest/certification execution, complete applicable source/
admission/topology checks, `git diff --check`, Ruff check, Ruff format check and
cheap static/authority checks. If a cheap gate fails, STOP before the longer
test scope. Retain the combined Ruff diagnostic rule: both non-mutating Ruff
phases run and failed phases emit `--diff` diagnostics before the Ruff gate
stops. Required final/post-test identity and static checks remain required;
this ordering rule does not remove them or modify the runner.

#### 2. Do not run the same tests twice

For the same exact HEAD/tree and unchanged environment/evidence validity, do
not ask the human operator to rerun a scope already satisfactorily covered by
Codex and/or terminal-green GitHub Actions. Codex normally performs focused
verification during implementation; reviewed source-gate CI follows its
bounded commit/push. The human operator must not repeat those tests merely for
confidence.

A separate user-run test is justified only when it supplies materially
different required coverage/certification evidence, the source changed after
prior evidence, prior evidence was invalid/incomplete, or ChatGPT identifies
a distinct required gate not already covered. Independent required coverage
is not duplicate execution. A docs-only closeout does not change already
certified executable/test source and must not manufacture a repeat test event.

#### 2a. One logical checkpoint means one atomic push and one planned CI run

For one logical checkpoint, consolidate all foreseeable source, test, workflow,
documentation, status/handoff, formatting, diff-check and cleanup edits
**before** the ordinary push. The normal and required path is:

```text
pre-edit exact base/branch/origin/cleanliness checks
-> implementation and focused/local verification
-> one atomic unpublished commit
-> PRE-PUBLICATION ops.ps1 admit on the clean committed candidate
-> one ordinary push/ref advance
-> one push-triggered source-gate CI admission run
-> terminal PASS or terminal failed checkpoint attempt
```

GitHub CI is not the implementation loop. Do not split predictable source fixes,
formatting, documentation, handoff, pin updates, or mechanical cleanup into
additional pushes that merely create more CI runs for the same logical
checkpoint.

If the single pushed attempt fails, preserve its evidence and classify the
failure. Do not immediately fix-forward on the same logical checkpoint until
green. Any later push must be declared and treated as a **new corrective
checkpoint** with its own complete focused/local verification and atomic commit.
Do not rerun an unchanged successful workflow merely for confidence.

When a certification result must be recorded after source acceptance, prefer
batching the status/handoff/workflow documentation into the single planned
post-certification docs closeout rather than creating multiple docs-only pushes.

#### 2aa. CI-efficiency guardrails for mutable current docs and shared runner dispatch

The two bounded current-state files, `docs/PROJECT_STATUS.md` and
`docs/AI_TRADING_BOT_HANDOFF.md`, are intentionally mutable coordination
surfaces. Do not introduce or refresh executable checkpoint authority solely to
pin their exact current blob hashes. In particular, an ordinary acceptance or
post-certification status/handoff closeout must not require a Python/test edit
merely to keep mutable current-doc blob pins synchronized. If legacy authority
maps still couple those current docs to executable pins, preserve the already
accepted executable source and remove/replace that coupling only in the next
already-required runner-touch source checkpoint unless it blocks a safety gate.
Do not create a standalone broad/canonical certification cycle solely to refresh
mutable current-doc hashes.

A closeout that changes only current/narrative documentation must remain under
`docs/**` and use the reviewed docs-only CI classifier. If a proposed
"docs-only" closeout would require `scripts/checkpoint_runner.py`, tests or
other executable-source edits only because a current-doc hash changed, STOP and
classify that as checkpoint-authority design debt rather than silently turning
the closeout into a broad source CI run.

When ChatGPT accepts a checkpoint and, in the same review turn, also fully
determines the immediately following design-only milestone before any branch ref
has advanced, compose the acceptance closeout plus that next architecture/
validation freeze into one planned docs-only atomic publication. Do not first
publish a status/handoff closeout and then immediately publish a second design
commit that could have been composed against the same parent.

Any change to shared runner dispatch or common checkpoint functions (including
`_checkpoint_specs`, `preflight_checkpoint`, `execute_checkpoint`, source
routing, profile routing, or shared AST/pin registries) requires a pre-publication
impact audit of every current AST/blob-pin consumer and every test that freezes
the changed function/registry. Add those affected tests to focused verification
before the first push. Canonical ROBINHOOD/FULL is an admission gate, not the
mechanism for discovering predictable stale shared-runner pins.

#### 2b. Behavior-change cleanup is part of the feature change

**Behavioral replacement/removal non-regression:** When a feature, behavior,
API, workflow, or supported path is changed, replaced, retired, or removed,
update or remove every current test, fixture, fake, validation assertion,
operator instruction, and documentation reference that depends on the old
behavior. This includes README/help text and checkpoint inventory or expected
test topology. Do not preserve stale current-product assertions merely for
backward compatibility unless the old behavior is intentionally retained as a
reviewed LEGACY contract. Historical architecture/evidence documents should
remain historical rather than being rewritten, but they must not be presented
as current authority. Before closing the checkpoint, search the affected
source/tests/docs surface for stale references to the retired behavior.

When a task changes, replaces, retires, or removes existing behavior, end the
implementation instructions with exactly:

> Also remove or update any tests and docs that referenced the old behavior.

ChatGPT's exact-diff review must verify that behavioral removals/replacements
did not leave stale current-product tests or documentation behind.

Do not keep a stale test by weakening its assertion until it passes. Update it
to assert the replacement contract, or delete it when the covered behavior is
intentionally removed and replacement coverage makes it obsolete. Search also
examples, comments, snapshots, mocks and compatibility exports when they
describe callable behavior or authority.

This stale-reference cleanup is part of the feature checkpoint, not a later
cosmetic follow-up, so include it before the checkpoint's planned push/CI run.

#### 3. FULL is rare and is not an iteration loop

FULL is a consequential/current-product certification boundary, not a debugging
suite or a routine post-checkpoint confidence run. Preserve a failed FULL as
diagnostic evidence; do not immediately rerun it. Diagnose from that evidence,
make the bounded correction, pass cheap gates before focused tests, and run
only affected focused tests while iterating. Then exact-file commit/push,
obtain terminal-green source-gate CI, and obtain ChatGPT exact GitHub review/
source acceptance. Only then run one fresh FULL if the consequential boundary
still requires it.

After a passing FULL, do not rerun it on unchanged executable/test source while
its environment/evidence validity remains intact. Adjacent source-only
checkpoints may explicitly batch a pending FULL obligation until the next
genuine consequential boundary under the existing Architecture-132 conditions.
This does not permit crossing a protected effect, merge, major integration,
release or readiness boundary with an unsatisfied certification obligation.

#### 4. Select certification tiers; do not stack them blindly

FOCUSED -> SOURCE-GATE CI is routine. ChatGPT selects ROBINHOOD or FULL according
to the required boundary; they are not cumulative confidence runs. When FULL
is selected for unchanged source at a boundary where ROBINHOOD would otherwise
also apply, FULL's strict superset coverage satisfies that narrower Robinhood
source-certification obligation. Do not run ROBINHOOD and then FULL merely
because both trigger descriptions apply. LEGACY/EXHAUSTIVE remain exceptional
compatibility gates. PROTECTED requires reviewed bounded authorization under the standing rule;
no source certification grants it.

#### 5. Latest audited current-product certification topology

Do not resurrect the older all-repository three-lane FULL layout for routine
current-product testing. That topology predates the Architecture-132 current/
legacy ownership split.

The latest reviewed current-product certification contract is the
Architecture-132-R3L FULL / R3K ROBINHOOD selected-profile topology implemented by
`scripts/run_test_certification.py`:

- `--profile full` selects all CURRENTLY SUPPORTED modules and runs exactly
  six deterministic nonempty whole-module timing-aware lanes,
  `broad-1` through `broad-6`, with **no serial lane**;
- `--profile robinhood` selects the reviewed Robinhood/current-product subset
  and runs exactly four deterministic timing-aware lanes,
  `robinhood-1` through `robinhood-4`, with the accepted R3K model
  and **no serial lane**;
- the historical five-module Windows/global-state-sensitive `serial` lane is
  retained only by `LEGACY` and `EXHAUSTIVE`, which are exceptional
  compatibility/repository-archaeology profiles rather than normal
  current-product verification.

When the human operator must run broad current-product certification, use the
reviewed selected-profile runner rather than a raw monolithic
`python -m pytest` command and rather than reconstructing the pre-R1
three-lane suite manually. Focused one/few-module verification remains focused.

Audit chronology is normative provenance, not a timing threshold:

- the earlier all-repository Architecture-132 topology used two broad lanes plus
  the five-module serial safety lane;
- Architecture 132-R1 moved current-supported FULL and ROBINHOOD to their
  selected two-lane profiles; its accepted 113-module FULL completed in
  **201.655 s**;
- Architecture 132-R2 retained that selected-profile topology while
  rationalizing ownership and collection; its accepted 136-module FULL completed
  in **259.314 s**, while the corresponding routine source-gate workflow was
  restored to roughly **250 s**;
- later R2-B3/R2-B4 optimized routine source CI further and explicitly did
  **not** change certification-profile topology.

The current 134-C FULL contains more supported modules/cases than the R2 audit,
so a larger observed wall time does not by itself authorize falling back to an
older topology. If performance again becomes materially problematic, open a
separate measured Architecture-132 performance/topology checkpoint; do not
silently change lane semantics.

Changing FULL/ROBINHOOD ownership or lane topology requires a separately
reviewed certification-topology checkpoint.

#### 6. Bounded Codex commit/push and direct ChatGPT GitHub review

For an authorized bounded implementation/correction, Codex stages only the
exact intended files after proving the index is clean, verifies the staged
filename set and `git diff --cached --check`, creates one normal commit, and
ordinary-pushes only the existing feature branch. That authority includes no
merge, rebase, amend, force-push or PR metadata change. ChatGPT retrieves the
exact GitHub commit/diff/CI directly; do not require pasted GitHub diffs when
retrieval tools can obtain them.

#### 7. Docs-only closeout preserves accepted test evidence

Keep ordinary docs-only closeout strictly under `docs/**` so the existing
classifier uses its cheap validation path. A separately reviewed history-
storage cutover may include the explicitly scoped standing-rule update to
`AGENTS.md`; do not broaden that exception to unrelated repository rules.
Current-state documents record only current consequences and state. Closed
detail belongs once in the relevant architecture, validation, or history
record; do not append the same long milestone narrative to both current-state
files. Docs-only verification uses appropriate source/docs checks, including
exact admission, exact changed-file review, `git diff --check` and staged diff
check; it does not rerun pytest, FULL/ROBINHOOD or Ruff over unchanged Python.

### Tier selection and evidence contract

During iteration:

- Codex runs focused tests/checks for changed behavior;
- do not repeatedly run the complete repository suite;
- do not run long integration/E2E or production acceptance gates unless they are
  part of the explicitly requested checkpoint;
- if a broad local run fails, diagnose the affected area and rerun only focused
  tests after the bounded fix.

Architecture 132-R1 separates current-supported certification from legacy
compatibility. The routine flow and selected certification gates are:

```text
FOCUSED -> SOURCE-GATE CI
-> ChatGPT selects ROBINHOOD or FULL for the required boundary
   (FULL covers the narrower ROBINHOOD source obligation)
-> LEGACY/EXHAUSTIVE only for explicitly relevant compatibility
PROTECTED authorized within the exact reviewed bounds under the standing rule
```

| Level | Trigger and responsibility |
| --- | --- |
| FOCUSED | Every implementation/correction; Codex runs affected tests and focused checks. |
| SOURCE-GATE CI | Every pushed registered checkpoint; existing registered GitHub source-gate batching remains accepted. |
| ROBINHOOD | ChatGPT-declared coherent Architecture 131 integration boundary; before protected Robinhood qualification; after material changes to shared domain/execution/ledger/risk foundations used by Architecture 131. |
| FULL | Comprehensive CURRENTLY SUPPORTED product certification: after certification-topology changes; at coherent current-product boundaries; before major develop/release integration or consequential production/live-readiness transitions; after sufficiently broad supported shared-core changes; or when ChatGPT determines accumulated checkpoints warrant current-product regression. |
| LEGACY / EXHAUSTIVE | Only when explicitly relevant: legacy architecture changes, interpreter/dependency migrations spanning both eras, broad repository restructuring, deliberate legacy removal, or explicit backward compatibility investigation. |
| PROTECTED | Fresh approval at the exact reviewed effect boundary; user execution of the reviewed bounded command supplies that approval under the standing rule. All interlocks and STOP conditions remain mandatory. |

FULL remains the default and is not mechanically tied to every accepted source
checkpoint or Architecture 131 letter. FULL now means all CURRENTLY SUPPORTED
functionality, replacing the original Architecture 132 meaning. EXHAUSTIVE
preserves that earlier all-repository behavior. Normal current-product
certification does not require LEGACY or EXHAUSTIVE.

A certification-topology change creates a pending FULL obligation. Adjacent
source-only checkpoints may deliberately accumulate that obligation and run one
FULL at the next coherent current-product/readiness boundary when every
intermediate checkpoint has focused verification plus terminal-green source-gate
CI and no protected effect, merge, major integration or release boundary occurs
between them. This batching decision must be explicit; it is not permission to
carry uncertified source across a protected or consequential boundary.

ChatGPT chooses the appropriate tier after exact GitHub code review and source
acceptance. The normal handoff remains:

```text
implementation + focused checks
-> exact-file commit/push
-> ChatGPT exact GitHub code review
-> source acceptance
-> appropriate certification tier
-> docs closeout (PROJECT_STATUS + HANDOFF after certification acceptance)
```

At a declared certification boundary:

- ChatGPT supplies exact local commands and frozen source identities;
- every local certification attempt uses a fresh unique external evidence
  directory (normally purpose + GUID suffix); an existing/ambiguous evidence
  path is preserved and never deleted/reused merely to retry;
- the user runs the selected profile and required source/artifact checks;
- review-driven source corrections return to focused verification first;
- if the environment invalidates the run, repair it before interpreting failures
  as source defects;
- after clean certification, do not repeat covered scope without changed
  source, invalid/incomplete evidence, or materially different required coverage;
- a merge needs no second run when its resulting tree exactly equals the
  already-certified tree.

The runner accepts these profiles (counts at the accepted 132-R1 startup tree):

| Profile | Modules | Exact lanes |
| --- | ---: | --- |
| full (default) | 113 supported | broad-1, broad-2 |
| robinhood | 40 supported subset | robinhood-1, robinhood-2 |
| legacy | 204 retired architecture | legacy-1, legacy-2, serial |
| exhaustive | 317 complete repository | broad-1, broad-2, serial |

[Architecture 132](architecture/132-tiered-certification-profiles.md) freezes
ownership and required baselines. Whole supported directories admit new tests
automatically; mixed CLI/market-data/scripts ownership is exact and new files
require review. Root `tests/test_robinhood_*.py` tests enter automatically.
Missing/renamed FULL or Robinhood baseline modules fail closed. Every repository
module must have reviewed support status, including for EXHAUSTIVE; unfamiliar
namespaces must never silently enter LEGACY. Robinhood is contained in FULL;
FULL and LEGACY are disjoint and their union equals EXHAUSTIVE, which equals
the complete discovered repository inventory.

D10/Windows/Paper-v2/Alpaca operational paths are retained historical
compatibility, not current product requirements. The existing pre-Robinhood GUI
is legacy because it uses the retired operational artifact/runtime model. GUI
remains a future product goal; a Robinhood-integrated GUI milestone must
explicitly reclassify or replace it.

Only LEGACY and EXHAUSTIVE retain the historical five-module serial safety
lane. Current-product FULL/ROBINHOOD never add that serial lane; operator-run
broad current-product certification uses the reviewed selected profile instead:

```text
tests/runtime/test_windows_transactional_capture_authority.py
tests/runtime/test_windows_authority_schema.py
tests/runtime/test_windows_authority.py
tests/runtime/test_windows_effectful_capture_native_acceptance.py
tests/acceptance/test_windows_authority_provisioning_acceptance.py
```

Architecture-77 remains serial; unrestricted parallel safety has not been
established. Current FULL has six deterministic nonempty whole-module
timing-aware lanes under R3L; Robinhood retains four deterministic timing-aware
lanes under accepted R3K. Both have no serial lane. LEGACY/EXHAUSTIVE retain their
historical two-broad-plus-serial topology. Never launch pytest with an empty
module list.

All profiles retain exact clean source/local-tracking/live-origin admission,
post-test/final verification, protected-opt-in rejection, external temp-root and
JUnit/evidence validation, and whole-repository `ruff check --no-cache .`,
`ruff format --check --no-cache .`, and `git diff --check`. Evidence records the
profile, repository/selected/excluded inventories, support classification and
exact lanes. `inventory.json` retains `all` as the complete repository inventory;
only EXHAUSTIVE selects all of it. `--plan` saves topology/evidence without
launching pytest or static checks for any profile.

No profile grants native Windows acceptance opt-ins, provider access, Robinhood
calls, OAuth interaction, broker effects, or production effects. PROTECTED
remains separate and needs reviewed bounded authorization under the standing rule. Architecture 132-R1
implementation runs only focused checks; actual certification requires the
subsequent exact GitHub review and ChatGPT's gate decision.


### Windows operator command transport and serialization

Repeated project incidents have shown that Windows PowerShell/native-process
argument transport is an authority and evidence risk, not merely a shell-style
preference. Operator commands must use this order of preference:

1. an existing reviewed source-owned CLI or the Architecture-129 `ops.ps1`
   runner;
2. a reviewed version-controlled `.py` / `.ps1` helper with focused tests;
3. only when no reviewed entry point exists, a short read-only diagnostic whose
   payload is transported through a file path or stdin rather than complex
   command-line quoting.

Never pass structured JSON or other structured payloads as a raw native command
argument when a file path or stdin can carry the bytes. **Hard rule: from
PowerShell, never transport multiline Python through `python -c`.** This
includes `python -c $Code`, `& $Python -c $Code`, `python -c $hereString`,
and equivalent variable-expanded forms, even for temporary/read-only
diagnostics. PowerShell/native argument parsing can strip or reinterpret quoting
before Python sees the program. For a tiny diagnostic, use a single-quoted
PowerShell here-string and pipe it to `python -B -`. For anything more than a
tiny diagnostic, write UTF-8 source to an approved temporary `.py` file and
invoke that file; reusable or protected logic belongs in reviewed repository
source. Never pass a here-string as the `-c` argument. A `SyntaxError` caused
by shell transport is a workflow regression, not diagnostic evidence, and must
not be worked around by trying alternate `-c` quoting.

This serialization rule does not override a protected operator contract that
explicitly requires real interactive terminal stdin. In that case, do not pipe
or redirect the human authorization input and do not automate the terminal gate;
use stdin/file transport only for the surrounding diagnostic data that the
reviewed contract permits.

PowerShell/operator blocks must also preserve these established Windows rules:

- normalize filesystem identities with `Resolve-Path` (and case-insensitive
  comparison where appropriate) instead of comparing Git's slash-normalized
  path text directly to a backslash literal;
- under StrictMode, force potentially singleton pipelines to arrays with
  `@(...)` before using `.Count`;
- treat empty `Get-Content -Raw` results as possibly `$null` and use null-safe
  string checks;
- when native stderr can be expected, use a reviewed wrapper or
  `Start-Process -Wait -PassThru` with redirected stdout/stderr instead of
  allowing `$ErrorActionPreference = 'Stop'` to reinterpret diagnostic stderr
  before the native exit code is handled;
- serialize multi-step copy/paste operator commands inside one invoked
  scriptblock (`& { ... }`) or reviewed script, and emit the terminal PASS
  marker only inside that same guarded scope after every prerequisite succeeds.
  Never provide a detached PASS line that can still be pasted/executed after an
  earlier `throw` or native failure.

Generated giant PowerShell blocks are not a normal workflow. If a diagnostic is
likely to be reused, crosses a protected boundary, carries structured data, or
requires more than a short admission/invocation wrapper, promote it to a tested
reviewed script/checkpoint before use.

### Local Git compatibility rule

The Windows development machine currently uses an older Git version where
`git switch` is unavailable. Repository/operator instructions must use
`git checkout` for branch changes and `git checkout -b <branch> --track
origin/<branch>` when creating a local tracking branch. Do not assume
`git switch` support unless a later environment check explicitly proves it.

### Windows pytest temporary-directory rule

On John's Windows development account, pytest commands that may use `tmp_path`
or `tmpdir` must use a fresh explicit `--basetemp` outside
`C:\Users\John\AppData\Local\Temp\pytest-of-John`. The default pytest temp root
has previously produced `WinError 5` while pytest was only setting up fixtures;
that is an environment/setup failure, not a source regression.

Use the existing external test-temp convention:

```powershell
$BaseTemp = "F:\AI\temp\pytest\<purpose>-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null
& $Python -m pytest ... --basetemp="$BaseTemp" -p no:cacheprovider
```

Rules:

- use a fresh unique basetemp for each controlled run;
- do not globally change `TEMP` or `TMP` to work around pytest permissions;
- do not persistently set `PYTHONPATH` for normal pytest collection;
- `pyproject.toml`'s `pythonpath = ["src"]` owns normal pytest imports;
- when a certification command is generated for this host, explicit basetemp is
  part of the command, not an optional troubleshooting fallback.

Milestone, verification, merge, and post-merge reports must always include the
next actionable step and concrete execution material when known.

## Canonical worktree location

The main checkout remains at `F:\\AI\\ai-trading-bot`. Every auxiliary
Trading Bot Git worktree must be created under:

```text
F:\\AI\\worktrees\\<explicit-project-worktree-name>
```

Do not create or adopt Trading Bot worktrees under the user profile, including
Codex-managed defaults such as:

```text
C:\\Users\\John\\.codex\\worktrees\\...
```

Every task that creates or selects a worktree must name the exact
`F:\\AI\\worktrees\\...` path in its startup gate. If a tool proposes or
creates a worktree outside that root, stop before edits and recreate/select the
worktree at the canonical F: location. Do not silently treat a noncanonical
path as equivalent.

A noncanonical worktree that already contains generated/untracked artifacts is
not force-removed or cleaned merely to satisfy this convention. Preserve the
artifacts, classify the worktree state, and use a separate reviewed
reconciliation/removal step. A dirty-worktree STOP remains a STOP.

When an interactive PowerShell block throws a STOP, commands appearing later in
the pasted block are not authorized to continue just because PowerShell accepts
subsequent input. Re-establish the exact worktree/branch/HEAD/tree/status gate
before any further Git operation.

## Worktree source provenance

When a virtual environment belongs to one checkout but is used to run code from
a different worktree, the editable installation inside that environment may
otherwise resolve `trading_bot` from the wrong checkout. Pytest's configured
`pythonpath = ["src"]` protects normal pytest collection, but it does not protect
standalone `python -c`, module, script, Ruff, or operator invocations.

For a standalone provenance probe, bind the expected source root only inside
that one Python process instead of exporting persistent `PYTHONPATH`. Nontrivial
Python under PowerShell must be delivered through a single-quoted here-string on
stdin rather than `python -c`. For the current personal-desktop worktree:

```powershell
Set-Location 'F:\AI\worktrees\ai-trading-bot-personal-desktop'

@'
import sys
from pathlib import Path

root = Path(
    r'F:\AI\worktrees\ai-trading-bot-personal-desktop\src'
).resolve()

sys.path.insert(0, str(root))

import trading_bot

module = Path(trading_bot.__file__).resolve()
assert root in module.parents, (root, module)
print(module)
'@ | & 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -
```

The printed module path must be under the expected worktree `src` tree. An
assertion failure is an environment/provenance STOP: do not continue tests,
operator commands, or certification against an ambiguous import source.

Apply the same pattern to other worktrees by changing only the explicitly
selected worktree path. Do not mutate the shared virtual environment or rely on
its editable-install target as source authority for another worktree.

## PowerShell and Git checkpoint style

Routine bounded checkpoints performed by Codex should stay simple and explicit.
The task prompt should name the exact worktree, branch, expected HEAD/tree,
intended remote ref, intended paths, and whether commit/push is authorized. A
typical authorized sequence is:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git rev-parse origin/<feature-branch>
git diff --cached --name-only
git add -- path/to/one.py path/to/test.py
git diff --cached --name-only
git diff --cached --check
git commit -m "..."
git push origin <feature-branch>
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git rev-parse origin/<feature-branch>
git status --short
```

The initial staged-file check must prove the index is empty before Codex adds
files. If branch/worktree/HEAD/tree/origin/index state differs from the frozen
startup gate, Codex stops instead of self-correcting.

Use larger defensive scripts only when a security-sensitive deployment,
production authority gate, or unusually fragile operator operation genuinely
requires them.

### Windows/PowerShell command robustness

Windows operator commands are part of the reviewed control surface. Keep their
syntax deliberately boring and parser-stable:

- nontrivial Python under PowerShell uses a single-quoted here-string piped to
  `python -B -`; do not use `python -c` for multiline, quote-heavy, path-heavy,
  or security-sensitive probes;
- inline Python text containing Windows paths must use raw string literals or
  escaped backslashes so diagnostic commands do not emit invalid-escape
  warnings that can hide real output;
- PowerShell .NET calls should use simple intermediate assignments instead of
  parser-fragile multiline type/cast expressions;
- after any PowerShell parser error, do not treat later commands in the pasted
  block as having passed the failed prerequisite; restart from a clean,
  explicitly fenced checkpoint;
- protected-effect commands and their read-only preflights remain separate, and
  the preflight must prove its own Administrator/source/host admission rather
  than relying on a prior shell variable that may not have been assigned;
- structured diagnostic or operator logic belongs in a reviewed `.ps1`/`.py`
  file or a stdin Python block; PowerShell should remain a short launcher and
  exact-state fence.

These rules are mandatory for generated ChatGPT/Codex operator instructions,
not just repository scripts.

## Parallel worktrees

Separate feature worktrees may remain active simultaneously. Every task must
operate only in the explicitly named worktree and branch. Do not switch, clean,
reset, delete generated artifacts from, or otherwise disturb another active
worktree as part of a scoped task.

## Safety and prohibited operations without explicit approval

The following remain prohibited unless the current task explicitly authorizes
them:

- merge;
- rebase;
- amend;
- force-push;
- PR metadata changes;
- review-thread resolution;
- unrelated file edits/deletions;
- production/provider external effects;
- credential-store reads/writes outside an approved gate;
- production authority database mutation outside an approved gate;
- deployment outside an approved deployment checkpoint.

Routine exact-file staging, normal commit, and ordinary feature-branch push are
permitted when the current bounded task explicitly authorizes that checkpoint.
They do not imply authorization for any operation in the prohibited list above.

External-effect prerequisites and no-effect preflight must remain separate from
any command that can cross an effect fence. A consumed `CONFIRMED` or
`MAY_HAVE_OCCURRED` lineage is never retried by manufacturing a new execution of
the same consumed authority.


## Combined Ruff diagnostic rule

When ChatGPT supplies an operator verification gate that checks both Ruff lint
and Ruff formatting, the gate must collect both results before failing. The
canonical pattern is:

```powershell
& $Python -m ruff check --no-cache @Files
$RuffCheckExit = $LASTEXITCODE
if ($RuffCheckExit -ne 0) {
    & $Python -m ruff check --diff --no-cache @Files
}

& $Python -m ruff format --check --no-cache @Files
$RuffFormatExit = $LASTEXITCODE
if ($RuffFormatExit -ne 0) {
    & $Python -m ruff format --diff --no-cache @Files
}

if ($RuffCheckExit -ne 0 -or $RuffFormatExit -ne 0) {
    throw 'STOP: Ruff verification failed'
}
```

Both diagnostics are non-mutating. A lint failure must not prevent the formatter
check from running, because `ruff check` and `ruff format --check` validate
different contracts. Do not use `--fix` or run an in-place formatter merely to
diagnose an operator gate failure.

## Unified checkpoint runner

Architecture 129 replaces routine one-off verification scripts with the
checked-in repository launcher and runner. The following examples are
non-exhaustive; the live `_checkpoint_specs()` registry surfaced by
`.\ops.ps1 status` is authoritative:

```powershell
.\ops.ps1 status
.\ops.ps1 verify arch134-f1r1-d1s4-fresh-successor-source
.\ops.ps1 verify arch128-parent-acl-repair
.\ops.ps1 verify arch128-r4
.\ops.ps1 preflight arch128-parent-acl-repair
.\ops.ps1 preflight arch128-r4
.\ops.ps1 execute arch128-parent-acl-repair
.\ops.ps1 execute arch128-r4
.\ops.ps1 preflight arch128-r5-substrate
.\ops.ps1 preflight arch128-r5-trading
.\ops.ps1 verify arch128-r6
.\ops.ps1 verify arch128-r7
.\ops.ps1 preflight arch128-r7
```

The current post-R1 successor is SOURCE ONLY and has no preflight/execute
dispatch. Historical D1S4/R1 host registrations retain predecessor meaning;
they are not fresh-successor deployment authority. ChatGPT must review the new
exact source and later deployment-admission boundary before real-host work.

`ops.ps1` is intentionally a thin launcher. Source-gate orchestration,
combined Ruff diagnostics, evidence capture, and checkpoint authority checks
belong in `scripts/checkpoint_runner.py`.

For registered checkpoints, this runner is the default source-verification
surface. New generated PowerShell verification scripts are fallback-only and
must not be used merely because a checkpoint needs another lint, formatting,
AST, or read-only diagnostic pass.

GitHub Actions runs the same launcher on Windows/Python 3.14. Source-only gates
should normally be satisfied by CI rather than asking the user to rerun the
same pytest/Ruff/diff checks locally.

Local Windows work remains necessary for host-specific qualification such as
ACLs, Task Scheduler, real account tokens, and protected filesystem state. Those
operations use the runner's registered `preflight` layer and, only where
separately source-reviewed, checkpoint-specific protected `execute` dispatches.
The live `_checkpoint_specs()` registry and `.\ops.ps1 status` output are the
authoritative current inventory; prose/example lists are non-exhaustive. A
registered preflight owns its own Administrator/source/host admission and
evidence capture, so do not add an external pre-screen that can abort before
the runner records the attempt. A source or preflight PASS never grants
protected production authority; approval within the exact reviewed bounds under
the standing rule and the exact reviewed authorization interlock remains
mandatory. For a reviewed bounded local command, the user's decision to execute
supplies that approval; all effect gates and STOP conditions remain.

Checkpoint evidence is external to the repository. The preferred development
host root is `F:\AI\temp\ai-trading-bot-checkpoints`; CI uses its runner
temporary directory and uploads the evidence artifact.

When a registered gate fails, improve the checked-in runner/observer so the
same failure class produces useful structured diagnostics on the next run.
Do not create a chain of temporary diagnostic scripts for behavior that belongs
in the reusable checkpoint implementation.



A checkpoint may pin a live remote branch for host preflight. In that case the
runner permits a clean detached operator worktree and uses read-only
`git ls-remote` to prove the local HEAD equals the exact live remote branch
HEAD. This is preferred when preserving an older dirty or failed development
worktree is safer than reconciling it merely to run host qualification.
