# Architecture 134-F1R1-D1S4 — Rename-Free Direct Immutable Release Installation

Status: IMPLEMENTED; source-only checkpoint. Terminal feature CI and ChatGPT
exact-source review remain pending. This document describes the direct-install
implementation after the accepted rename-free pivot. It does not create a production release, consume a production attempt, provision the
successor store, start runtime, read credentials, contact a provider, mutate
paper/broker state, or authorize live trading.

## Exact predecessor

D1S4 starts from current `develop`:

    HEAD  1e9b6a0638f00ddb009bdb7934039b7a9047e678
    TREE  1ef95f954cfce509a6b90639b8bb9599e2e9206f

The rename-free pivot is normative in `AGENTS.md`,
`docs/AI_DEVELOPMENT_WORKFLOW.md`, and
`docs/architecture/134-f1r1-rename-free-immutable-release-pivot.md`.
Post-integration develop CI #705 / run `40083293598`, attempt 1 is terminal
SUCCESS with source-static, all four broad shards, and source-gates green.

D1S3 installation and D1S3-R5 preserved-image publication remain consumed,
preserved incident history. Their protected operators are never retried and
their exact `.installing` object is not an input to D1S4.

## Decision

D1S4 keeps the existing deterministic Architecture-133 release identity and
runtime-binding model but removes filesystem publication entirely.

For one accepted source checkpoint:

    accepted VerifiedRelease / RuntimeBinding
      -> derive existing release_id
      -> derive exact final path F:\AITradingBot\releases\<release-id>
      -> prove that exact final path absent
      -> consume a new D1S4 one-shot attempt
      -> create the final directory directly
      -> create/write only its exact verified release contents
      -> flush and close materialization handles
      -> independently reconstruct and verify that same final image twice
      -> return DIRECT_INSTALL_VERIFIED

The directory name never changes. There is no staging path in the D1S4 state
machine and no publish/promote operation.

The existing `ReleaseManifest.release_id` remains the deployment identity. A
source correction changes source HEAD/TREE and therefore the manifest/release ID,
providing a new unique final path. An ambiguous/partial D1S4 attempt permanently
consumes that exact source/release/path. It is preserved inert and never repaired,
renamed, cleaned, promoted, or retried. Forward progress after such an incident
requires a separately reviewed successor source identity with a different
release ID.

## Reused immutable verification contract

D1S4 may reuse pure/read-only reviewed foundations where their semantics remain
correct:

- `VerifiedRelease`, release bundle verification and complete source inventory;
- `ReleaseManifest.release_id` and `release_root(release_id)`;
- `RuntimeBinding` and its exact release-root binding;
- `IMAGE_ACES`, production Python version/hash and release-parent policy;
- pure replay of accepted release/binding inputs;
- independent final-image reconstruction equivalent to
  `observe_installed_release`;
- later runtime-admission/F1R1 host composition that already binds the exact
  `release_root(release_id)`.

D1S4 must not weaken those checks merely to support direct materialization.

The existing staging installer, staging writer and publication/recovery modules
are historical/retired for this forward path. New D1S4 code must not call them.

## New one-shot attempt authority

The direct-install attempt is independent of both consumed D1S3 and R5 latches.

Freeze the source-owned attempt schema:

    arch134-f1r1-d1s4-rename-free-direct-install-attempt/v1

The path is derived from the exact release ID beneath the external temporary
authority root, with no caller-selected component:

    F:\AI\temp\arch134-f1r1-d1s4-direct-install-attempt-<release-id>.json

The canonical payload binds at least:

- schema;
- release_id;
- source HEAD;
- source TREE;
- status = CONSUMED;
- automatic_retry = NOT_AUTHORIZED.

The file is created with exclusive-create semantics, flushed, fsynced/closed as
supported by the accepted attempt primitive, and read back exactly before the
first production release-directory create is attempted. Any existing object at
that exact latch path consumes or makes authority indeterminate; it never grants
a new attempt.

Freeze source interlocks:

    AI_TRADING_BOT_ARCH134_F1R1_D1S4_ACCEPTED_HEAD
    AI_TRADING_BOT_ARCH134_F1R1_D1S4_ACCEPTED_TREE

Freeze protected execute interlock:

    AI_TRADING_BOT_ARCH134_F1R1_D1S4_DIRECT_INSTALL_AUTHORIZATION
      =
    ARCH134_F1R1_D1S4_ONE_RENAME_FREE_IMMUTABLE_RELEASE_INSTALL_AUTHORIZED

Source work never sets the execute interlock.

## Read-only preflight and reconciliation

D1S4 preflight is registered and read-only with respect to production. It may
write only normal external checkpoint evidence through the unified runner.

It independently proves:

1. exact current D1S4 source/worktree/branch/HEAD/TREE/origin/remote admission;
2. exact accepted release bundle, manifest, source inventory and RuntimeBinding;
3. Administrator admission for any future execute eligibility;
4. exact release-parent identity/security and production Python identity;
5. exact D1S4 latch state;
6. exact direct FINAL path state;
7. repeated stable observation;
8. no dependency on D1S3/R5/historical publication state.

The closed table is:

| D1S4 latch | exact FINAL state | Result | Execute eligible |
| --- | --- | --- | --- |
| AVAILABLE | absent | PASS / READY_FOR_RENAME_FREE_MATERIALIZATION | true |
| CONSUMED | exact verified final | PASS / DIRECT_INSTALL_VERIFIED | false |
| CONSUMED | absent | BLOCKED / CONSUMED_ATTEMPT_NO_IMAGE | false |
| CONSUMED | present but partial/conflicting/unprovable | BLOCKED or INDETERMINATE / PARTIAL_OR_CONFLICTING_DEPLOYMENT | false |
| AVAILABLE | any present final | BLOCKED / UNOWNED_FINAL_PRESENT | false |
| either | source/parent/runtime/latch observation drift | BLOCKED or INDETERMINATE | false |

No result renews authority. A consumed attempt is never retried.

The serialized runner report must include enough closed information to diagnose
the exact latch classification, final path/identity when observed, release ID,
manifest/inventory/binding digests, source HEAD/TREE, parent identity, Python
identity, and repeated-observation stability without requiring an ad-hoc
diagnostic script.

## Protected execute order

A future protected execute may be reviewed only after exact source acceptance and
a fresh PASS preflight. Its code must enforce this order:

1. exact D1S4 source admission;
2. construct/replay exact `VerifiedRelease` and `RuntimeBinding`;
3. require the derived release ID/path and reject the consumed R5 incident
   release ID as predecessor history, never as a reusable destination;
4. require Administrator;
5. prove exact releases-parent and production Python admission;
6. prove exact FINAL absent;
7. prove D1S4 attempt AVAILABLE;
8. repeat source/parent/final/latch admission;
9. exclusively create and durably read back the D1S4 attempt latch;
10. only then lazy-import the new rename-free native writer;
11. create exact FINAL directly with the reviewed immutable image security;
12. create exact release subdirectories directly beneath FINAL;
13. CREATE_NEW/write-through each exact release file; flush each file;
14. close/release all materialization handles;
15. independently reconstruct the exact FINAL image at least twice;
16. require identical image identity/evidence and exact manifest/binding/source
    replay;
17. repeat source and latch admission;
18. return PASS / DIRECT_INSTALL_VERIFIED / CONFIRMED.

The mutation fence is crossed before the first FINAL create. Any exception,
false/ambiguous native result, close ambiguity, verification failure,
KeyboardInterrupt/SystemExit, or post-fence source/identity drift is terminal:

    INDETERMINATE
    MAY_HAVE_OCCURRED
    PRESERVE_DIRECT_INSTALLATION_EVIDENCE_NO_RETRY
    automatic_retry = NOT_AUTHORIZED

A later registered preflight is the only reconciliation path.

## Narrow native writer

`successor_native_direct_write.py` implements the separate D1S4 native
capability. The retired staging writer is unchanged.

It may:

- require the exact Administrator host;
- open/pin the exact existing release ancestors;
- create exactly one derived FINAL root;
- create only derived child directories beneath that FINAL;
- create only exact release-inventory files beneath that FINAL;
- apply the exact reviewed immutable-image security at creation;
- perform bounded writes, flushes and closes;
- expose read-only observation needed for exact post-materialization verification.

It must not expose or invoke:

- `publish`, `rename`, `move`, `promote`, `replace`, `delete`,
  `cleanup`, rollback or arbitrary-destination APIs;
- `SetFileInformationByHandle(FileRenameInfo)`;
- `MoveFile*`;
- `os.rename`, `os.replace`, `Path.rename`, `Path.replace`;
- symlink/junction/hard-link alias publication;
- caller-selected release paths;
- overwrite/open-existing file creation for materialization.

No production object outside the one exact D1S4 final tree is mutable.

## Machine-enforced rename-free non-regression

D1S4 is the first implementation checkpoint required by the pivot to make the
rule executable.

Source authority/tests must fail closed if the forward D1S4 deployment surface:

- imports/calls `installer.py`, `native_write.py`,
  `successor_installation_operator.py`,
  `successor_publication_recovery.py`, or
  `successor_native_publication.py` as an installation shortcut;
- imports/calls historical Architecture-125/133 rename/publication operators;
- contains any forbidden rename/move/replace/promotion primitive listed above;
- exposes a native publication/delete/cleanup capability;
- allows the registered forward D1S4 dispatcher to route to D1S3/R5 execute;
- treats the preserved R5 `.installing` sibling as a prerequisite, conflict to
  repair, or source of reusable bytes/authority;
- admits runtime before exact complete final-image verification.

Historical modules stay frozen as incident/legacy evidence. Their existence is
not itself a failure; only current forward-path reachability is forbidden.

## Compatibility with the existing runtime stack

The goal is deliberately to avoid a second architecture migration after direct
materialization succeeds.

Because current `RuntimeBinding`, runtime admission and host composition already
bind `release_root(release_id)`, a successfully verified D1S4 final image should
feed the existing immutable runtime/host evidence model without renaming the
release or inventing a `current` alias.

If implementation discovery finds that a current runtime consumer depends
semantically on staging/publication rather than merely on the exact final
`InstalledEvidence`, STOP and report the dependency for ChatGPT architecture
review. Do not hide it behind a compatibility rename or alias.

## Excluded boundaries

D1S4 source and its future direct installation do not authorize:

- successor-store/root provisioning;
- scheduler/service/startup changes;
- runtime/process start;
- credential reads;
- provider/network requests;
- paper/broker mutation;
- D1/D2 operational effects;
- live trading;
- deletion/cleanup/repair of D1S3/R5 incident evidence.

The successor-root Trading write-authority/ACL question remains a separate
architecture review after rename-free release installation/admission succeeds.

## Verification and publication workflow

Implementation uses the isolated feature worktree/branch rooted exactly at
the predecessor identity above. Run focused tests and combined Ruff/check-format/diff
verification during implementation.

Register D1S4 in the unified checkpoint runner and map its one ordinary feature
push to canonical `ROBINHOOD` certification. Do not duplicate the canonical
profile locally when CI owns it. Preserve any red run. Do not immediately correct/push: ChatGPT must classify
any mechanical C1 request before a separate corrective checkpoint.

The implementation should be one atomic logical source checkpoint and must not
perform any real D1S4 production preflight or execute. After terminal CI, ChatGPT
reviews the exact GitHub source/diff/certification before any local host action.


## Implemented source and exact publication boundary

Branch:
`feature/robinhood-production-paper-134f1r1-d1s4-rename-free-direct-install-current`

Worktree:
`F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-d1s4-rename-free-direct-install-current`

The required base/direct parent is
`1e9b6a0638f00ddb009bdb7934039b7a9047e678`, tree
`1ef95f954cfce509a6b90639b8bb9599e2e9206f`. Publication requires exactly one
normal implementation commit above that base and exactly one ordinary first
push; the superseded planning branch remains unchanged. The two planning blobs
were imported without cherry-picking or making a design commit.

Implemented modules:

- `src/trading_bot/supervised_release/successor_direct_installation.py` owns exact
  live source admission, complete release reconstruction, the release-derived
  latch, repeated read-only reconciliation, and the fenced one-shot dispatcher.
- `src/trading_bot/supervised_release/successor_native_direct_write.py` owns only
  internally derived final/child creation and create-new verified bytes. Exact
  `IMAGE_ACES` are applied at creation, each file is flushed, all materialization
  handles close before verification, and no namespace transition exists.
- `tests/review_paper/test_arch134_f1r1_d1s4_rename_free_direct_installation.py`
  supplies disposable fake-host, latch, native-binding and graph-mutation tests.
- `scripts/checkpoint_runner.py` registers
  `arch134-f1r1-d1s4-rename-free-direct-installation`, maps its exact branch to
  canonical ROBINHOOD, and owns predecessor-preserving blob/AST/inventory
  overlays plus the machine-enforced forward deployment import-graph check.

The graph walker traverses local imports, lazy imports and package initializers.
It rejects retired writers, historical operators, operational provider/broker/
runtime modules and forbidden namespace primitives in the forward write modules.
Existing pure strategy/config/model imports transitively load broker-independent
in-memory execution/ledger declarations; D1S4 never instantiates their engines or
mutates their state. Forward calls to those engine constructors are also rejected.
The shared observer's unused lexical staging path is not a deployment operation:
D1S4 never observes or materializes a staging tree. R5's preserved sibling may
appear only as an unrelated release-parent directory entry.

Exact verification and changed-path evidence is recorded in the companion
validation record. No real D1S4 production preflight or execute ran, and D1S3/R5
latches, namespace and incident reports were untouched. Historical behavioral
modules remain byte-for-byte unchanged.

Final HEAD/TREE, direct-parent verification, clean final index/worktree, remote
identity and terminal CI facts are necessarily post-commit observations. Per the
user's explicit resolution, those are supplied in the final post-CI handoff;
this atomic committed document does not predict its own identity or future CI.
No source acceptance is asserted here. The intended handoff state is
`IMPLEMENTED / ONE ATOMIC COMMIT / ONE PUSH / PENDING CHATGPT EXACT-SOURCE REVIEW`.

Also remove or update any tests and docs that referenced the old behavior.
