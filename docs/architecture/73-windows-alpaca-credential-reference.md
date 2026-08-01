# Windows Alpaca credential-reference artifact

This milestone defines a schema-1 `WindowsMarketDataCredentialReference` for
the future capture provider boundary. It contains only a Windows account SID,
versioned Credential Manager target names, provider/purpose policy, and
operator-reviewed permission-attestation evidence. It never contains a secret
and no code in this milestone calls `CredReadW`, `CredWriteW`, or any other
credential API. The reference is therefore an identity and policy declaration,
not actual credential authority or cryptographic proof of provider permissions.

The canonical JSON serializer is strict (bounded fields, no duplicate keys,
no floats/constants, canonical UUID/evidence text). Its UUID5 identity uses all
semantic fields with explicit length-framed material and no filesystem paths,
host clocks, or serialized bytes. The artifact is immutable and can be
transported between roots without changing identity.

The fixed values are `WINDOWS_CREDENTIAL_MANAGER_GENERIC`, `LOCAL_MACHINE`,
`ALPACA_MARKET_DATA`, and `MARKET_DATA_CAPTURE_ONLY`. The target names are
versioned and distinct. Actual unattended provider access remains separately
unapproved.

## Milestone-75 implementation clarification

The isolated one-call capture child is now the sole consumer of this reference.
It verifies the exact current-process SID before calling a narrow read-only
`CredReadW` adapter for exactly the two target names. It has no enumeration,
write, rotation, deletion, environment, file, or command-line fallback.
Credential values remain child-only and are never available to the parent
launcher.

The native `CredentialBlobSize` contract is the Windows
`CRED_MAX_CREDENTIAL_BLOB_SIZE` bound of `5 * 512` bytes, not the full unsigned
`DWORD` range. The reader validates the complete pointer-plus-size range
without pointer or `size_t` truncation or overflow before any zeroing. It
copies or accepts at most the separate 1,024-byte application bound, but
cleanup zeroes every valid native range up to 2,560 bytes, including a valid
native blob larger than that bound. Sizes above 2,560 bytes, null nonzero
ranges, and overflowing ranges are never passed to zeroing; `CredFree` is
attempted exactly once and cleanup errors are reduced to a secret-free fixed
diagnostic.

This does not change the reference identity or canonical bytes. It also does
not approve unattended provider use. Python immutable-string zeroization
cannot be guaranteed; the child copies no more than the approved application
bound, retains the original native `CredentialBlobSize` only for cleanup, and
clears the entire reported native blob range before `CredFree`, including
oversized rejected credentials. Scoped Python references are dropped after the
one call and all cleanup paths fail closed without exposing credential
material.
