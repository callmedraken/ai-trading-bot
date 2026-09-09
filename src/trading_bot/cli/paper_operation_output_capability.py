"""Optional output hooks for stricter Architecture-67 publication policies."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class PaperOperationOutputCapability(Protocol):
    """Production-strength output operations injected into generic A67 commits."""

    def verify_parent(self, path: Path) -> None: ...

    def create_staging_directory(self, path: Path) -> None: ...

    def write_staged_file(self, path: Path, payload: bytes) -> None: ...

    def verify_staged_directory(self, path: Path) -> None: ...

    def verify_staged_file(self, path: Path) -> None: ...

    def finalize_directory(self, staging: Path, final: Path) -> None: ...

    def verify_finalized_directory(self, path: Path) -> None: ...

    def verify_finalized_file(self, path: Path) -> None: ...


def require_output_capability(
    capability: PaperOperationOutputCapability | None,
) -> PaperOperationOutputCapability | None:
    """Reject incomplete capability objects before any output operation."""

    if capability is not None and not isinstance(
        capability, PaperOperationOutputCapability
    ):
        raise TypeError("paper-operation output capability is invalid")
    return capability
