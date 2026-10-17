# Architecture 134-D1R9 — arbitrary-time one-session D1 supervisor validation

Status: DESIGN FROZEN; implementation pending.

Acceptance objective: prove that one top-level D1R9 authorization can be issued
at an arbitrary time while the PC is ON and safely carry one session across
closed-market/weekend/holiday/premarket waits and process restarts, while
preserving accepted D1R7/D1R8 one-shot safety.

Required classes:

1. Session resolution: Friday after close, Saturday, Sunday and holiday select the
   next published session; current premarket/admitted select current; after
   close-minus-five selects next; cover DST and early close.
2. Durable waits/restart: reconcile NEXT_SESSION_WAIT, PREMARKET_WAIT and
   D1R8_WAIT from current time + durable state; bounded <=60s wait quantum; no old
   sleep duration authority; backward clock safe.
3. D1R7 delegation: durable intent before child entry; accepted source pinned and
   re-admitted; complete READY artifact independently reread/parsed/hashed;
   partial/invalid/ambiguous evidence never retries.
4. D1R8 delegation: separate import/process boundary; ReviewedProof only from
   validated D1R7 bytes; no run before open+5; durable intent before entry;
   complete terminal reconciliation; ambiguity never invokes a second attempt.
5. Effect containment: preserve all accepted D1R8 ceilings; credential
   writes/deletes/OAuth renewal/broker/options/crypto/ACL/D2/live stay zero;
   scheduler plumbing never grants market/session authority.
6. Operator surface: one top-level interactive authorization; noninteractive
   resume requires durable authorization; status/reconcile read-only; no
   date/session/provider/account/price/quantity/evidence/order selectors.

Use a new isolated D1R9 branch/worktree. Keep D1R7/D1R8 and historical evidence
frozen. Focused tests, retained overlay checks, Ruff and diff checks precede one
atomic commit/push. GitHub owns mapped canonical certification. Source acceptance
grants no real operational effects.
