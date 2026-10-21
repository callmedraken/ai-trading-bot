# Validation: Architecture 134-F1R1-B

This is a source-only, no-effect validation plan and evidence record for the
exact B branch. It does not run the real qualification host, restart Codex,
create a scheduled task, read credentials, contact a provider, mutate paper or
broker state, or alter the consumed F1 evidence.

## Focused source proof

`tests/review_paper/test_arch134_f1r1_b_host_qualification.py` uses synthetic
Architecture-133 release/binding/runtime evidence, disposable lifecycle
storage, fake effect journals, and harmless disposable development activity.
It verifies:

- accepted Architecture-133 evidence joins only when release ID, manifest SHA,
  binding SHA, source root, launcher, Python, image, dependency, and inventory
  identities agree;
- wrong release, manifest, binding, launcher, source, or Python identity fails
  closed;
- repeated F1R1-A admission remains independent of mutable development state
  and imports no live-Git, provider, credential, broker, or scheduler helper;
- lifecycle JSONL is canonical, append-only, replay-valid, bounded, durable
  through an injected flush/fsync seam, and bound to exactly one runtime ID;
- partial, corrupt, noncanonical, terminal-extension, and over-budget state is
  rejected without truncation or repair;
- pre-entry rejection never enters the injected seam, `ENTRY_ADMITTED` is
  visible before entry, post-entry failure is consumed as `AMBIGUOUS`, retry is
  rejected, and success produces `ACK`;
- the qualification host has only immutable admission, safe waiting, lifecycle
  evidence, deterministic status, and a harmless stop signal;
- disposable directory/file/Git-status/subprocess disturbances do not change
  the admitted runtime identity;
- production reboot remains STOP/manual-start.

The retained F1R1-A focused module and affected Architecture-133 release,
runtime-admission, predecessor, runner, and certification-profile tests remain
in the checkpoint test set.

## External Codex-restart qualification plan — PLAN ONLY

Run this plan only after B source acceptance and a separate ChatGPT review of
the exact operator boundary. Do not execute it in this source run.

1. Prepare a disposable qualification fixture containing one independently
   verified immutable release and the exact accepted 133 host evidence. Do not
   install it or use production state.
2. Launch one harmless qualification host independently from the development
   checkout, using the code-owned lifecycle destination or a separately
   reviewed disposable host destination. Record the exact runtime ID and
   verify the first durable lifecycle rows by read-only replay.
3. Start Codex concurrently. Perform only read-only Git/status operations,
   disposable test execution, disposable file edits, and disposable
   worktree-like directory/repository activity outside the immutable release.
4. Read the qualification status and journal while it remains safely waiting.
   Require unchanged runtime ID, one host authority, no duplicate lifecycle
   owner, and replay-valid canonical evidence.
5. If independent process lifetime is to be proven across a Codex restart,
   use a separately reviewed OS-host boundary. Task Scheduler, service
   control, or another independent host mechanism is an operator-effect
   boundary and must be reviewed and authorized separately. B does not create,
   mutate, delete, or run any such mechanism.
6. Restart Codex under that separate review and use only read-only checks to
   prove the qualification process remains alive, its runtime ID is unchanged,
   its journal remains replay-valid, and no second host authority appeared.
7. Stop the harmless host through its explicit qualification stop signal and
   require a final `NORMAL_RETURN` record. Treat a missing terminal record as
   abrupt disappearance; do not retry or infer authority.
8. Reconcile counters and evidence read-only. Require provider, credential,
   paper, broker, D1, D2, scheduler-mutation, and live counters all remain
   zero.

Expected positive result: `READY_FOR_F1R1_HOST_QUALIFICATION`. This is not
authorization for F1, a successor soak, production installation, scheduler
operation, provider access, or any trading effect. A later soak design, if
needed, is a separate milestone: `READY_FOR_SEPARATE_SUCCESSOR_SOAK_DESIGN`.

## Stop conditions

Stop and return for review on any request for deployment, installation,
scheduler/task control, credential or provider access, paper/broker mutation,
D1/D2 operation, live effects, reboot behavior changes, predecessor semantic
reinterpretation, or consumed-F1 evidence repair. Do not perform the real
Codex-restart qualification in this checkpoint.
