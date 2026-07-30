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
