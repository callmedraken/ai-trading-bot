# Architecture 126 — D5 Task Scheduler Read-Only Observation Authority

Status: frozen source-design checkpoint for the Architecture-125 predecessor
qualification. This document authorizes no Task Scheduler mutation, protected
D10 mutation, signing, activation lease, provider effect, Paper-v2 effect,
broker-paper effect, or live effect.

## 1. Scope and decision

Architecture 125 requires a fresh proof that the registered task at

    \AITradingBot-PD4-UnattendedPaper-v1

is still the exact accepted D5 capture-only predecessor before any D10
replacement mutation.

The earlier Architecture-112 D5-A qualification established the correct
observation pattern after several XML-only probes proved brittle:

- Task Scheduler COM is the semantic source of truth for registered task
  behavior;
- XML is supporting evidence, not the semantic authority;
- legal/defaulted XML omission or serialization differences do not themselves
  constitute scheduler-contract drift;
- principal text returned by COM is resolved through Windows to the exact
  frozen Trading SID before identity acceptance.

Architecture 126 freezes that pattern for P125-R1B.

## 2. Frozen observer mechanism

The only admitted semantic observation mechanism for P125-R1B is the Windows
Task Scheduler COM API exposed through one reviewed, zero-argument PowerShell
helper.

The helper must:

1. run under the fixed Windows PowerShell executable selected by the
   implementation;
2. accept no task name, task path, expected SID, executable, arguments,
   working directory, trigger, settings, or other authority-bearing value from
   argv, environment, stdin, configuration, or caller data;
3. instantiate the Task Scheduler COM service using
   `Schedule.Service`;
4. connect locally;
5. open the root folder `\`;
6. obtain exactly the fixed task
   `AITradingBot-PD4-UnattendedPaper-v1`;
7. read the registered task and its `Definition` only;
8. resolve the returned principal identity through Windows to a SID;
9. emit one bounded transport record containing only the source-owned semantic
   projection plus bounded XML evidence;
10. perform no registration, update, delete, enable/disable, run, stop,
    credential, registry, filesystem, or other mutation.

The Python P125 adapter may invoke only this reviewed helper at its exact
source path. It must use a fixed PowerShell executable, `-NoProfile` and
`-NonInteractive`, no caller-selected script path, and no semantic
arguments. Native process exit status is checked before stdout is parsed.
Nonzero exit, empty stdout, malformed output, unexpected stderr disposition,
oversized output, or extra records fail closed.

`Get-ScheduledTask`, `Get-ScheduledTaskInfo`, `schtasks.exe`, direct
registry reads, direct reads of `C:\Windows\System32\Tasks`, WMI/CIM task
objects, and XML-only XPath qualification are not alternate semantic
authorities for P125-R1B.

## 3. Exact D5 semantic projection

The observer must project and the Python adapter must require the following
exact semantics.

Task identity:

    task path:
    \AITradingBot-PD4-UnattendedPaper-v1

Principal:

    resolved SID:
    S-1-5-21-1397534616-3988210162-180023805-1009

    LogonType:
    1  (Password)

    RunLevel:
    0  (LUA / LeastPrivilege)

The COM `UserId` string itself is not authority. It may be the local account
name, qualified account name, or SID form only if Windows resolves it to the
exact frozen SID above. Resolution failure or a different SID blocks.

Actions:

    count:
    1

    action type:
    0  (Exec)

    Path:
    F:\AITradingBot\runtime\python.exe

    Arguments:
    -I F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\run_personal_desktop_unattended_capture_warmup.py

    WorkingDirectory:
    F:\AI\worktrees\ai-trading-bot-personal-desktop

Comparison is ordinal and exact after COM returns the strings. The observer
must not trim, quote-normalize, path-normalize, environment-expand, token-split,
or otherwise repair a different registered action into equality.

Triggers:

    count:
    1

    trigger type:
    2  (Daily / CalendarTrigger)

    Enabled:
    true

    StartBoundary:
    2026-09-15T01:30:00

    DaysInterval:
    1

    RandomDelay:
    empty

    Repetition.Interval:
    empty

    Repetition.Duration:
    empty

    Repetition.StopAtDurationEnd:
    false

Settings:

    MultipleInstances:
    2  (IgnoreNew)

    DisallowStartIfOnBatteries:
    false

    StopIfGoingOnBatteries:
    false

    AllowDemandStart:
    true

    StartWhenAvailable:
    true

    RunOnlyIfNetworkAvailable:
    false

    RunOnlyIfIdle:
    false

    Enabled:
    true

    Hidden:
    false

    WakeToRun:
    true

    ExecutionTimeLimit:
    PT1H

    Priority:
    7

    RestartCount:
    0

    RestartInterval:
    empty

These values are the exact accepted D5 scheduler semantics carried forward from
Architecture 112 and the accepted D5-A/B evidence.

Task state, LastRunTime, LastTaskResult, NextRunTime, trigger occurrence count,
Task Scheduler history, PID/process lifetime, and current overlap state remain
diagnostic/non-authoritative exactly as the frozen scheduler contract already
states. They must not admit or reject P125 replacement.

## 4. Principal resolution

The PowerShell helper must not compare `Principal.UserId` text directly with
one preferred spelling.

It must resolve the returned identity through Windows account/SID translation
and require the resulting SID string to equal the frozen Trading SID exactly.

If COM returns a SID-form `UserId`, constructing a
`SecurityIdentifier` object from that string is not sufficient. The helper
must still prove that the SID resolves through Windows account translation
(for example SID -> NTAccount -> SID) and that the round-tripped SID is exactly
the frozen Trading SID. This prevents a deleted/unresolvable principal SID from
being accepted merely because its text still equals the historical SID.

A missing identity, unresolvable identity, group/service identity, different
SID, ambiguous translation, translation exception, or failed round trip blocks.

The transport record exposes only the resolved SID, not reusable credentials.

## 5. XML evidence and the historical D5 hash

The accepted historical D5 task XML SHA-256 remains:

    8005373fad791c85776b4a35b662d46e06fec4ea40ac9ebfead9f413715da457

That value remains valuable historical evidence, but it is not a P125 machine
authority input.

The original D5 sequence did not freeze one byte-level extraction and
canonicalization protocol for that hash. Earlier D5 probes also demonstrated
that legal Task Scheduler XML may omit fields whose semantic values are
materialized by COM. Architecture 126 therefore forbids treating raw XML byte
identity as a substitute for the semantic COM qualification.

For P125-R1B:

- the helper reads the XML string from the same registered COM task;
- it computes SHA-256 over the exact UTF-8 encoding, without BOM, of the COM
  XML string exactly as returned;
- it records both byte length and digest;
- it does not trim whitespace, normalize newlines, reorder elements, expand
  defaults, or canonicalize XML;
- the raw XML body is not emitted from the helper;
- the historical `8005373f...` value is recorded in source as legacy
  evidence only and is never compared as an admission predicate;
- a current XML digest neither admits nor rejects replacement by itself.

This intentionally separates two questions:

1. "Is this registered task semantically the exact accepted D5 predecessor?"
   — answered only by the frozen COM semantic projection.
2. "What exact XML serialization did Windows expose during this observation?"
   — bounded diagnostic evidence only.

No code may claim that the historical XML hash has been reproduced unless a
separate future architecture explicitly freezes and validates its byte
extraction protocol.

## 6. Stable two-read observation

The observer must detect concurrent or mid-read scheduler drift.

One P125 scheduler observation consists of:

1. first COM read of the fixed task and semantic projection;
2. first COM XML digest/length observation;
3. second fresh COM `GetTask` read of the same fixed task;
4. second semantic projection and XML digest/length observation.

Acceptance requires:

- both semantic projections are byte-for-byte equal after canonical transport
  serialization;
- both individually equal the exact frozen D5 semantics;
- both XML digest/length pairs are equal to each other.

The two current XML hashes need not equal the historical D5 hash.

Any disappearance, COM exception, semantic difference, XML digest/length drift,
or task replacement between reads blocks. The observer does not retry until a
different result appears.

## 7. Transport boundary

The PowerShell helper is observation-only transport, not authority.

Its stdout record must be bounded canonical JSON containing only:

- schema/version;
- task semantic fields listed in this architecture;
- resolved Trading SID;
- XML byte length and SHA-256;
- fixed task identity;
- observer status.

It must not contain:

- task credentials or passwords;
- COM object representations;
- handles;
- security descriptors;
- arbitrary environment values;
- task history;
- process lists;
- raw XML;
- caller-selected paths or strings.

The Python adapter reconstructs a typed observation from the record and
independently validates every field and exact type before setting
`d5_capture_only_scheduler_exact=True`.

A helper-emitted PASS string is never sufficient authority.

## 8. Relationship to Architecture 125 admission

P125-R1B may construct the scheduler part of `AdmissionFacts` only when this
Architecture-126 qualification passes.

The resulting fact is exactly:

    d5_capture_only_scheduler_exact = True

No other fact is implied.

In particular, scheduler qualification does not prove:

- Administrator identity;
- protected D10 parent security;
- old S5-R8 deployment identity;
- new S5-R10 staging identity;
- lease/cache/reserved-path absence;
- same-volume replacement namespace;
- no prior D10 activation evidence.

Those remain independent Architecture-125 proofs and must be fresh before
mutation.

## 9. Read-only implementation boundary

P125-R1B may add:

- a reviewed fixed PowerShell COM observation helper;
- a Python read-only adapter that invokes and validates it;
- pure typed scheduler-observation models if needed;
- fake/mock focused tests.

It must not add or expose:

- `Set-ScheduledTask`;
- `Register-ScheduledTask`;
- COM `RegisterTask` / `RegisterTaskDefinition`;
- task delete/run/stop/enable/disable methods;
- `schtasks /Create`, `/Change`, `/Delete`, `/Run`, or `/End`;
- arbitrary PowerShell command execution;
- arbitrary task-name/path observation;
- D10 staging creation;
- MoveFileW replacement;
- trust/signing publication;
- activation lease or scheduler mutation;
- provider, Paper-v2, broker-paper, or live effect.

## 10. Required focused tests

Before R1B can be accepted, tests must prove at least:

1. helper invocation path/executable/options are fixed and take no semantic
   arguments;
2. malformed/nonzero/empty/oversized helper output blocks before parsing;
3. exact D5 semantic record passes;
4. each principal/action/trigger/settings field independently blocks on drift;
5. account-name spellings are accepted only through exact SID resolution;
6. extra or missing action/trigger blocks;
7. action strings are not normalized into equality;
8. state/history/last-result/next-run values are absent from admission;
9. two-read semantic or XML digest/length drift blocks;
10. historical XML hash is diagnostic only and cannot independently admit or
    reject;
11. raw XML, credentials, handles, arbitrary paths, and reusable authority are
    absent from output;
12. no scheduler mutation API or command is reachable from the R1B observer;
13. no staging, rename, deletion, signing, activation, provider, paper, broker,
    or live effect occurs.

Source tests use fake transport/native boundaries and must not inspect the real
registered task.

## 11. Exit

Architecture 126 closes the R1B scheduler-observation design blocker.

The next safe checkpoint is to resume P125-R1B in the existing
`F:\AI\worktrees\ai-trading-bot-p125-r1b` worktree after fast-forwarding
this docs-only architecture commit.

No real Task Scheduler observation or protected operation is authorized merely
by this design document.
