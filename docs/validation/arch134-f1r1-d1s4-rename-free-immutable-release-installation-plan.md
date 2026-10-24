# Validation plan — Architecture 134-F1R1-D1S4 Rename-Free Direct Immutable Release Installation

## Purpose

Validate the first machine-enforced implementation of the rename-free release
pivot. All tests are source/local-fake only. This checkpoint performs no real
production materialization or other protected effect.

Base:

    develop HEAD 1e9b6a0638f00ddb009bdb7934039b7a9047e678
    develop TREE 1ef95f954cfce509a6b90639b8bb9599e2e9206f
    post-integration CI #705 / 40083293598 / attempt 1 / SUCCESS

## Required focused coverage

The D1S4 test surface must prove at least:

1. exact source/worktree/branch/HEAD/TREE/origin/remote admission;
2. deterministic release ID/path is the existing
   `F:\AITradingBot\releases\<release-id>`;
3. the D1S4 final path is unique to the accepted source identity;
4. preflight AVAILABLE + final absent returns
   `READY_FOR_RENAME_FREE_MATERIALIZATION`;
5. preflight CONSUMED + exact final returns `DIRECT_INSTALL_VERIFIED`;
6. CONSUMED + absent final blocks without retry;
7. CONSUMED + partial/conflicting final blocks or is indeterminate without retry;
8. AVAILABLE + any present final blocks as unowned;
9. repeated namespace/object observation drift becomes INDETERMINATE;
10. exact parent and production-Python admission is preserved;
11. D1S4 latch path/payload are source-derived and caller cannot select them;
12. exclusive latch creation/readback precedes the first final-directory create;
13. no native writer import occurs before durable latch readback;
14. first production create consumes the effect fence even when it raises;
15. FINAL is created directly; no staging directory is created;
16. all child directories/files are derived from the exact verified release;
17. files use create-new/no-overwrite bounded writes and are flushed;
18. exact immutable image security is applied at creation and independently read
    back;
19. all materialization handles close before positive verification;
20. independent final-image reconstruction occurs twice and must match exactly;
21. final image identity, manifest, inventory, binding and Python identities
    agree;
22. a false/exception/KeyboardInterrupt/SystemExit/close ambiguity after the
    fence returns terminal INDETERMINATE / MAY_HAVE_OCCURRED / no retry;
23. later preflight reconciles consumed + exact final without creating a new
    attempt;
24. later preflight never turns consumed + partial/absent final into retry
    authority;
25. old D1S3/R5 latches/reports/staging object are not read as D1S4 authority;
26. preserved R5 `.installing` can exist as an unrelated sibling without
    blocking the new release ID;
27. the forward D1S4 module graph cannot import/call retired D1S3/R5 installers
    or publication writers;
28. it cannot import/call historical Architecture-125/133 rename publication
    operators;
29. no D1S4 forward module contains/calls FileRenameInfo,
    SetFileInformationByHandle for rename, MoveFile*, os.rename/os.replace,
    Path.rename/Path.replace, alias/junction publication, or equivalent;
30. new native writer exposes no publish/rename/move/delete/cleanup/rollback API;
31. unified runner D1S4 preflight is read-only against production and serializes
    closed diagnostic fields;
32. unified runner execute dispatch requires the exact D1S4 authorization
    interlock and cannot dispatch D1S3/R5;
33. every unrelated protected-effect counter remains zero;
34. no successor-root, scheduler, credentials, provider, paper, broker, D1/D2,
    or live capability is reachable;
35. accepted historical R5/D1S3 blobs remain unchanged except unavoidable
    source-owned inventory/pin overlays outside their behavioral bodies.

## Focused commands

Use the repository virtual environment with a fresh external pytest base. Run
the new D1S4 test module plus directly affected retained release/runtime/runner
tests. Include combined:

- `ruff check --no-cache`;
- `ruff format --check --no-cache`;
- `git diff --check`.

Do not use `--fix`.

The implementation handoff must report exact focused counts and paths.

## Canonical source gate

Register the exact D1S4 checkpoint in `CI_CERTIFICATION_PROFILES` as
`robinhood` before the single intended feature push.

The terminal feature push owns canonical ROBINHOOD certification. Do not run an
identical local canonical profile first or afterward.

Expected route:

    source-static
    -> active-tests
    -> certification-tests: ROBINHOOD
    -> source-gates

The 300-second canonical hygiene ceiling remains unchanged.

Any failed CI attempt is preserved. Do not rerun unchanged. Only a bounded C1,
and if necessary C2, may correct a fully classified mechanical pin/inventory/
relocated-fixture/topology issue. Semantic/native/authority uncertainty returns
to ChatGPT instead.

## Handoff evidence

The final implementation handoff must include:

- exact branch/worktree/base;
- final HEAD/TREE/direct parent;
- commit count above base;
- exact changed paths;
- exact new D1S4 module/test/checkpoint names;
- exact attempt schema/path template and execute interlock;
- focused test/Ruff/diff results;
- terminal CI run/attempt and canonical ROBINHOOD totals/wall time/artifact;
- confirmation that no protected D1S4 preflight/execute ran;
- confirmation that D1S3/R5 incident evidence was not mutated;
- clean worktree/index and matching remote branch.

Next owner after implementation is ChatGPT exact GitHub review. Only after
SOURCE ACCEPTED and integration may ChatGPT separately review the registered
real-host read-only D1S4 preflight.

Also remove or update any tests and docs that referenced the old behavior.
