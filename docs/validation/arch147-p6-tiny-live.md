# Architecture 147 P6 — Validation contract

The P6 source checkpoint uses synthetic provider-shaped payloads only. It must
prove the following before publication:

1. P5B evidence is PASS, bound to source `7ff86d06a99bcdf349d5e20846d139a554d8be46`
   and tree `095c51cedc1c656616123c3acf88148b16b71aa2`, and its account
   fingerprint is loaded rather than hard-coded.
2. The P5B transport remains mutation-free and the P6 transport owns the only
   current Architecture 147 live mutation methods.
3. Tool discovery fails closed when any required tool or dollar-order schema is
   absent; no share-quantity fallback or generic dispatch exists.
4. Strategy evaluation uses only the accepted SPY 35/50 BASE_MA signal over at
   least 60 completed raw regular daily bars and never uses FINAL_HOLDOUT or
   Alpaca data.
5. Risk rejects non-SPY, short, leveraged, unsupported, over-$10 or over-$10
   gross exposure intents and proves cash/equity coverage before a BUY.
6. Plans are immutable, source- and digest-bound, sanitized, and preserve
   `PAPER_EVALUATION` as a separate non-live-eligible contract.
7. Preflight performs no place or cancel; execution is disarmed without both
   exact environment interlocks; create-only markers prevent retry after a
   possibly consumed placement; post-trade reconciliation is finite.
8. GUI state contains no raw account number and has no arm/place/cancel button.
9. P6 state is absent after imports, tests, source admission and CI.

Focused verification covers the new policy, strategy, plan, execution,
transport, GUI and checkpoint-authority tests. Ruff check/format and the
repository source-authority evaluator are also required. GitHub owns the
registered canonical FULL certification; no local provider preflight or
execute run is part of the source checkpoint.
