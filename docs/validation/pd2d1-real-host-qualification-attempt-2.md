# PD2D1 real-host qualification attempt 2

## Non-diagnostic old-source replay

After F3-R1 was pushed but before the Trading worktree was updated, source
`564fdf822cc7a91939faf61754c8402baa2b131a` was accidentally replayed once. It
returned the old generic result and supplied no new diagnostic evidence:

```json
{"reason":"QUALIFICATION_BLOCKED","schema":"pd2d1-first-paper-qualification-evidence/v1"}
```

The exit code was `6`. No retry of that old source is permitted.

## Meaningful F3-R1 attempt

```text
principal:                 DESKTOP-I4DOKM7\Trading
SID:                       S-1-5-21-1397534616-3988210162-180023805-1009
Administrator membership: False
HEAD:                      94a750978a6f5e0de022a5ca6c56f0f28065eb78
TREE:                      0430e4028d5979b1ba04f3b7787d66b92b89d0c1
status:                    clean
exit:                      6
```

The exact result was:

```json
{"reason":"QUALIFICATION_BLOCKED","schema":"pd2d1-first-paper-qualification-evidence/v1"}
```

The F3-R1 classifier was definitely active, so the failure is outside every
explicitly classified typed boundary. This evidence does not identify the
exact internal stage. B1/the mutex remains a leading hypothesis, and the next
action is the narrower B1 stage-isolation diagnostic.

The qualification harness contains no Architecture-67 execution or writer
path. Do not infer that a Paper-v2 mutation occurred.

```text
PD2D1_REAL_HOST_QUALIFIED = NO
PD2D2_AUTHORIZED          = NO
```
