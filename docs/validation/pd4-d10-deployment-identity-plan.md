# Architecture 123 — D10 Deployment Identity Validation Plan

Status: frozen source-validation plan. Production signing/provisioning remain protected future checkpoints.

## A. Source checkpoints

### A1 — canonical models

Implement:
- executable manifest entry/model/serializer/parser;
- deployment-attestation model/serializer/parser;
- deterministic deployment ID;
- strict schemas, path rules, digest rules, and exact-field rejection.

Focused tests are pure and non-Windows.

### A2 — certification builder

Implement a build-only boundary that accepts an explicitly expected clean checkout identity and emits:
- canonical executable-manifest bytes;
- executable-manifest SHA-256;
- canonical unsigned deployment-attestation bytes;
- deterministic deployment ID.

Git is permitted only in this certification/build tool, never in the production runtime verifier.

The builder must fail if HEAD/tree/clean state differs from explicit expected inputs.

No private key or signing operation is implemented.

### A3 — fixed native read/security boundary

Add the dedicated fixed `F:\AITradingBot\D10` object/security contract and Trading runtime no-follow read verifier.

Portable/mock tests cover exact path/ACL/type/reparse/final-path/inventory behavior. Native acceptance remains a later protected deployment gate.

Do not alter Architecture 77's fixed Authority root/object set.

### A4 — runtime deployment verifier

Implement a zero-semantic-argument production verifier that:
- acquires current C1/Trading provenance;
- reads only fixed D10 trust files;
- verifies detached signature;
- verifies source-owned identity fields;
- verifies complete governed executable-file manifest against the fixed production source root;
- rejects source drift and returns sanitized same-process provenance.

Production runtime must not invoke Git or trust `.git`.

### A5 — activation lease

Resume the Architecture-122 activation-lease checkpoint only after A4 is accepted.

The lease binds `deployment_id` plus signed-attestation digest plus exact seven-day activation/end interval.

## B. Source review and certification

During A1-A5, use focused tests plus Ruff/format/diff checks only.

After the one-wake D10 controller and all Architecture-122 source work are stable, run the persistent repository certification once. Do not broad-certify every intermediate checkpoint.

## C. Protected deployment checkpoints

These are not authorized by source completion.

### P1 — administrator D10-root provisioning

Create only the fixed D10 root with reviewed owner/DACL and verify real Windows native path/security/reparse behavior.

### P2 — detached signing

Using external non-exportable approved signing material, sign the exact certified deployment-attestation bytes. No private key enters the repository, logs, environment, or Trading account.

### P3 — atomic trust publication

Administrator publishes the exact executable manifest, attestation, and signature through reviewed create-only temporary/final paths, then reopens and verifies all final objects.

### P4 — Trading read-only qualification

Under the dedicated non-admin Trading account, run the zero-effect deployment identity verifier. It must prove the exact certified deployment before an activation lease or scheduler mutation is considered.

### P5 — activation lease and D10 scheduler

Only after separate explicit operator approval and exact review of P4 evidence may the Architecture-122 activation lease be provisioned and the capture-only scheduler be changed to D10.

## D. Stop conditions

Any inability to verify the exact signed deployment identity is BLOCKED.

Do not fall back to `.git`, scheduler state, environment variables, caller HEAD/TREE values, unsigned local manifests, or process memory.


## Architecture-124 prerequisite and A1/A2 revision

A3 stopped at the pre-source circular trust boundary. Architecture 124 now
precedes A3/A4.

Before continuing A3:

- revise the attestation source root to `F:\AITradingBot\D10\source`;
- add exact launch-guard byte length and SHA-256 to the canonical attestation;
- revise the certification builder to bind the tracked guard source separately
  from the sealed second-stage executable manifest;
- revise the scheduler contract to invoke the fixed installed guard using the
  exact isolated/no-site/no-bytecode-cache argument vector.

The existing A1/A2 canonical and HEAD-tree/blob proofs remain required. Broad
certification remains deferred.
