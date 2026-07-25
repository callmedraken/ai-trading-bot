"""Shared coordinated staging for deterministic CLI text artifacts."""

import os
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OutputArtifact:
    destination: Path
    content: str


def normalized_destinations(values: Iterable[Path | None]) -> tuple[Path | None, ...]:
    """Resolve optional output destinations without requiring their existence."""
    return tuple(
        None if value is None else value.resolve(strict=False) for value in values
    )


def preflight_destinations(
    destinations: Iterable[Path],
    *,
    overwrite: bool,
    error_factory: Callable[[str], Exception],
) -> None:
    """Validate every destination before upstream work begins."""
    for destination in destinations:
        if not destination.parent.is_dir():
            raise error_factory(
                f"output parent directory does not exist: {destination.parent}"
            )
        if destination.exists() and not overwrite:
            raise error_factory(f"output already exists: {destination}")


def write_artifacts(
    artifacts: tuple[OutputArtifact, ...],
    *,
    overwrite: bool,
    error_factory: Callable[[str], Exception],
    write_error_prefix: str,
) -> None:
    """Stage all artifacts before individually atomic ordered replacement."""
    staged: list[tuple[Path, Path]] = []
    try:
        for artifact in artifacts:
            destination = artifact.destination
            if destination.exists() and not overwrite:
                raise error_factory(f"output already exists: {destination}")
            descriptor, name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
            )
            temporary = Path(name)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                    stream.write(artifact.content)
                    stream.flush()
                    os.fsync(stream.fileno())
            except (OSError, UnicodeError):
                temporary.unlink(missing_ok=True)
                raise
            staged.append((destination, temporary))
        for destination, temporary in staged:
            if destination.exists() and not overwrite:
                raise error_factory(f"output already exists: {destination}")
            os.replace(temporary, destination)
    except (OSError, UnicodeError) as error:
        raise error_factory(f"{write_error_prefix}: {error}") from error
    finally:
        for _, temporary in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
