# PD2D1 real-host B1 diagnostic attempt 1

## Reviewed execution facts

The one-shot diagnostic ran as the non-elevated principal
`DESKTOP-I4DOKM7\Trading`, SID
`S-1-5-21-1397534616-3988210162-180023805-1009`, from clean source:

```text
HEAD: 7e0990c8b9b7873a24173eec454c52335033a0e7
TREE: 149e69968787ab6d7bbdbc9f06e3c10e5e324405
exit: 0
```

The exact output was:

```json
{"all_effect_gates_false":true,"authority_epoch_id":"e6f3de5d-1412-40ad-a022-8b33e72a5f6d","machine_authority_id":"223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1","mutex_acquisition_state":"OWNED","operation_root_matches":true,"paper_account_id":"9415cd7b-bf36-5fba-bd58-a0f99119dc21","post_lock_genesis_only":true,"pre_lock_genesis_only":true,"result":"B1_READY","schema":"pd2d1-b1-readonly-diagnostic/v1","terminal_checkpoint_id":"1832a2b5-8b63-501a-8f7d-f1722c32307b"}
```

```text
B1_REAL_HOST_DIAGNOSTIC = PASS
```

This clears as primary suspects the production pre-lock Paper-v2 read; PD2A
native mutex creation/open/security inspection/wait; `OWNED` acquisition; the
post-lock Paper-v2 reread; GENESIS-only reconciliation; and normal mutex
release.

It does not establish that P1 planning/replay, PD2B3 active binding, or
Architecture-67 inspection passed. It grants no execution or mutation
authority.

```text
PD2D1_REAL_HOST_QUALIFIED = NO
PD2D2_AUTHORIZED          = NO
```
