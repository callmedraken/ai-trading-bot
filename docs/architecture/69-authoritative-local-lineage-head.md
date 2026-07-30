# Authoritative local lineage head

## Milestone-A boundary

Milestone A defines one local, explicit, path-safe authority chain from a narrow
mutable pointer through immutable head records and complete lineage manifests.
It adds strict models, canonical encodings, complete read-only verification,
genesis publication, and manually invoked one-edge completed-operation
advancement.

It does not add a scheduler, lock, lease, provider, capture, readiness policy,
target generation, strategy, paper-cycle execution, receipt recovery, network,
broker, credential, notification, clock, background process, or implicit
artifact discovery.

One caller must already hold exclusive publication authority. Concurrent
publication is unsupported until the later single-writer milestone.

## Fixed layout and explicit resolution

```text
<authority-root>/
  lineage-manifests/
    paper-account-lineage-manifest-<evidence-id>-<sha256>.json
  lineage-head-records/
    paper-account-lineage-head-record-<record-id>.json
  current-lineage-head.json
```

The authority root must already be a real safe directory. The two fixed child
directories are created only by initialization or publication helpers.

The verifier reads only:

1. `current-lineage-head.json`;
2. the head-record filename derived from its exact record UUID;
3. predecessor filenames derived from explicit predecessor references;
4. manifest filenames derived from each record's exact evidence;
5. artifacts explicitly listed by those manifests.

Safety enumeration is bounded and used only to reject case-fold collisions. It
never nominates authority. Unlisted transitions, receipts, manifests,
checkpoints, or higher-sequence files are ignored.

## Immutable head-record schema

Schema 1 is one canonical UTF-8 JSON object with exactly:

```text
schema_version
record_id
authority_epoch_id
generation
previous_head_record
lineage_manifest
verified_lineage_evidence_id
terminal_checkpoint
advancement_cause
```

`previous_head_record` is either:

```json
{"kind":"GENESIS"}
```

or:

```json
{
  "kind": "HEAD_RECORD",
  "head_record_id": "<uuid>",
  "sha256": "<lowercase-sha256>",
  "byte_length": 1
}
```

`lineage_manifest` contains exactly `artifact_id`, `sha256`, and `byte_length`.
Its artifact ID must equal `verified_lineage_evidence_id`.

`terminal_checkpoint` contains exactly `checkpoint_id`, `sha256`,
`byte_length`, and `sequence`.

`advancement_cause` contains exactly `kind`, `artifact_id`, `sha256`, and
`byte_length`. Kinds are `GENESIS`, `COMPLETED_OPERATION`, and
`APPROVED_MANUAL_RECOVERY`.

Generation zero requires the explicit genesis predecessor marker, terminal
sequence zero, and exact genesis-checkpoint cause evidence. Every later
generation requires a predecessor and a non-genesis cause.

Manual-recovery records are parseable and chain-verifiable, but publication of
that cause remains unavailable until a separately approved recovery-artifact
and approval contract exists.

## Identity and canonical bytes

The record namespace is:

```text
2be0b50b-d4d7-587f-bd3e-69a4970dd0f4
```

Material version is:

```text
paper-account-lineage-head-record-v1
```

UUID5 material is UTF-8 byte-length framed and binds, in order:

1. material version;
2. authority epoch;
3. generation;
4. genesis marker or predecessor record UUID/hash/length;
5. manifest artifact UUID/hash/length;
6. verified lineage evidence UUID;
7. terminal checkpoint UUID/hash/length/sequence;
8. cause kind and cause artifact UUID/hash/length.

Paths, source manifest location, authority-root location, clocks, PIDs,
hostnames, diagnostic text, filesystem metadata, and mutable services are not
direct identity inputs. Manifest hash and length are explicit approved artifact
evidence.

Canonical JSON uses sorted keys, compact separators, ASCII escaping, no floats
or non-finite constants, and one final newline. Parsing rejects BOMs, invalid
UTF-8, duplicate/missing/unknown fields, noncanonical UUID or hash text,
unbounded integers, trailing data, and bytes unequal to canonical
reserialization.

The reviewed genesis vector has record UUID
`cf2712b4-0ba3-5b12-ae6e-aa0cdc9f0ca9`, 799 canonical bytes, and SHA-256
`b0935a1f64f8be1bde1825c87d43a66dfe48871599feeedc93fa7927fe7e9afa`.

## Mutable current-head reference

The canonical pointer contains exactly:

```text
schema_version
authority_epoch_id
generation
head_record_id
head_record_sha256
head_record_byte_length
```

It contains no path, checkpoint sequence, manifest claim, timestamp, process,
machine, diagnostic, or discovery hint.

Initialization creates it only when absent. Advancement uses a compare-and-swap
against exact expected canonical pointer bytes.

## Read-only authority verification

Verification:

1. validates the authority root and pointer;
2. checks exact pointer evidence for the named current record;
3. strictly parses and recomputes every record UUID;
4. follows explicit predecessor evidence until genesis;
5. rejects cycles, missing predecessors, altered predecessor evidence, epoch
   mismatch, and noncontiguous generations;
6. evidence-checks and fully verifies every explicitly named lineage manifest;
7. requires exact manifest evidence UUID and terminal checkpoint UUID/hash/
   length/sequence;
8. requires record generation to equal verified terminal sequence;
9. requires every adjacent lineage to add exactly one edge while retaining
   every earlier ordered identity and artifact evidence;
10. derives the public `VerifiedPriorCheckpoint` from the complete current
    lineage;
11. rereads the pointer and confirms stable authority-root identity.

PASS exposes a frozen `VerifiedAuthoritativeLineageHead` containing the pointer,
ordered record chain, exact record bytes, explicit manifests, complete lineage
verification results, and verified current prior.

The verifier performs no writes, clock reads, operation execution, provider,
network, broker, scheduler, subprocess, or candidate discovery.

## Genesis publication

Initialization requires:

- existing safe authority root;
- canonical authority epoch UUID;
- an explicit genesis-only lineage manifest whose full verification passes;
- terminal checkpoint sequence zero;
- absolute artifact paths in the published schema-1 manifest.

Absolute paths are required because the exact source manifest bytes are copied
under `lineage-manifests/`; changing the manifest base must not retarget
relative dependencies.

Manifest and record files are staged, flushed, bounded-reread, and finalized by
same-directory no-clobber hard link. Exact existing immutable bytes may be
reused after explicit retry; conflicting bytes fail closed.

The initial pointer is exclusively staged and no-clobber linked into place.
Nothing is overwritten or inferred. Complete authority verification must pass
after publication.

## Completed-operation advancement

Advancement accepts only explicit paths for:

- expected pointer copy;
- new complete lineage manifest;
- prior checkpoint;
- transition report;
- completed snapshot;
- successor checkpoint;
- completed receipt;
- cycle configuration.

The cycle configuration is an additional mandatory explicit dependency because
the existing schema-1 receipt verifier cannot return PASS without its exact
bytes.

Advancement requires:

1. current authority PASS;
2. byte-identical expected and installed pointers;
3. the new lineage to equal the old lineage plus exactly one edge;
4. exact prior terminal bytes;
5. exact supplied report, snapshot, and successor evidence;
6. successor-edge PASS using the current verified prior;
7. full completed-receipt PASS with the existing offline verifier;
8. exact receipt reconciliation with prior/successor lineage, operation,
   application, result, report, snapshot, and checkpoint evidence;
9. generation and terminal sequence increment by one;
10. immutable manifest and record finalization before pointer replacement;
11. atomic pointer compare-and-swap;
12. complete reread verification after replacement.

A failed receipt returns `MANUAL_REVIEW_REQUIRED` and never advances.

A stale proposal identical to an already installed child is
`STALE_EXPECTED_HEAD`. A stale explicitly supplied proposal that diverges from
the installed child is `CONFLICTING/FORK`.

## Windows pointer replacement

`AtomicPointerReplacer` isolates mutable-pointer replacement. The production
implementation:

- requires Windows;
- writes and `fsync`s fixed same-directory staging exclusively;
- bounded-rereads and parses canonical replacement bytes;
- checks exact installed expected bytes before and after staging;
- retains stable authority-root identity;
- calls `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING` and
  `MOVEFILE_WRITE_THROUGH`;
- rereads and compares the installed pointer.

There is no delete-then-rename, overwrite-in-place, cross-volume move, copy
fallback, or automatic repair. Replacement failure retains immutable manifest
and record files and leaves staging for review. It does not claim advancement.

The subsystem relies on the documented same-volume Windows rename primitive and
the external single-caller assumption. Power-loss guarantees beyond file flush
and `MOVEFILE_WRITE_THROUGH` require continued platform validation.

## Authority between commits

The finalized paper-account transition remains authoritative account-state
evidence immediately after transition commit. It does not become the selected
head merely by existing.

Before explicit successful head advancement, `current-lineage-head.json`
continues to select the prior terminal. Later operations must remain blocked by
the future readiness layer. This subsystem never scans for or automatically
repairs that state.

## Rollback, fork, and manual recovery limitations

Advancement detects a stale expected pointer, a caller-supplied rollback, and a
divergent explicitly supplied proposal. Chain verification detects backward or
skipped generations within the selected chain.

A pointer replaced together with deletion of all newer local evidence is
indistinguishable from an older legitimate authority using only the permitted
non-discovering inputs. Strong detection of that wholesale rollback requires a
separately retained expected pointer, backup, or external audit anchor.

Manual recovery publication remains deferred. No raw checkpoint, highest
sequence, only candidate, directory, timestamp, or filename can substitute for
complete verified authority.
