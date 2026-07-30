# Windows Alpaca credential-reference validation

Focused tests cover schema-1 canonical round trips, hostile JSON (duplicate,
float, BOM, extra/missing fields), SID and target-name bounds, path-independent
UUID5 identity, and the approved golden identity/byte vector. Tests assert that
the module imports no credential access and that no secret value is serialized.

Validation is offline: no provider, network, process, environment, or
Credential Manager operation is performed.
