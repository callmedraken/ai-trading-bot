"""One-shot staging installation; no retry, cleanup or installed-image repair."""

from __future__ import annotations

from pathlib import PureWindowsPath

from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import VerifiedRelease
from trading_bot.supervised_release.installation_contract import (
    InstallDisposition,
    InstallerNative,
    InstallReason,
    InstallResult,
    InstallStatus,
)
from trading_bot.supervised_release.observer import (
    observe_installed_release,
    observe_parent,
    observe_staging_release,
    replay_inputs,
)


def install_release(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    *,
    native: InstallerNative | None = None,
) -> InstallResult:
    """Derive all destinations internally; any mutation attempt consumes the attempt.

    No production execute registration is supplied by this source checkpoint.
    Exceptions are reduced to closed phase reasons, never exception text.
    """
    mutated = False
    reason = InstallReason.INPUT
    try:
        paths = replay_inputs(release, binding)
        if native is None:
            from trading_bot.supervised_release.native_write import WindowsInstaller

            native = WindowsInstaller()
        reason = InstallReason.HOST
        native.require_administrator_host()
        with native.install_session(paths) as session:
            reason = InstallReason.PARENT
            parent = observe_parent(session)
            reason = InstallReason.FINAL_CONFLICT
            if session.object(paths.final, directory=True) is not None:
                evidence = observe_installed_release(release, binding, native=native)
                if evidence.parent_identity != parent.identity:
                    raise ValueError("parent observation drift")
                status = InstallStatus.ALREADY_INSTALLED_VERIFIED
            else:
                reason = InstallReason.STAGING_EXISTS
                if session.object(paths.staging, directory=True) is not None:
                    raise ValueError("staging already exists")
                reason = InstallReason.MATERIALIZATION
                # Set the fence BEFORE the first native create attempt: failed or
                # ambiguous native completion must never authorize retry/cleanup.
                mutated = True
                session.create_directory(paths.staging)
                directories = sorted(
                    {
                        str(parent).replace("\\", "/")
                        for item in release.bundle.files
                        for parent in PureWindowsPath(item.relative_path).parents
                        if str(parent) != "."
                    },
                    key=lambda name: (name.count("/"), name),
                )
                for name in directories:
                    session.create_directory(paths.child(paths.staging, name))
                for item in release.bundle.files:
                    session.write_file(
                        paths.child(paths.staging, item.relative_path), item.data
                    )
                session.seal_staging()
                reason = InstallReason.STAGING_VERIFICATION
                staging = observe_staging_release(release, binding, native=native)
                if staging.parent_identity != parent.identity:
                    raise ValueError("parent observation drift")
                reason = InstallReason.PUBLICATION
                if session.publish(staging.image_identity) is not True:
                    raise ValueError("publication not acknowledged")
                reason = InstallReason.FINAL_VERIFICATION
                evidence = observe_installed_release(release, binding, native=native)
                if (
                    evidence.image_identity != staging.image_identity
                    or evidence.parent_identity != staging.parent_identity
                ):
                    raise ValueError("publication identity drift")
                status = InstallStatus.INSTALLED_VERIFIED
            reason = InstallReason.SESSION_CLOSE
        return InstallResult(
            status, InstallDisposition.VERIFIED, InstallReason.VERIFIED, evidence
        )
    except (Exception, KeyboardInterrupt):
        return InstallResult(
            InstallStatus.INDETERMINATE if mutated else InstallStatus.BLOCKED,
            InstallDisposition.PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY
            if mutated
            else InstallDisposition.NO_INSTALLATION_EFFECT,
            reason,
        )
