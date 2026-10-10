"""Independent read-only image reconstruction; no installer/mutation imports."""

from __future__ import annotations

import hashlib
from pathlib import PureWindowsPath

from trading_bot.arch133_acl.read_only import ADMINISTRATORS_SID
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    MAX_BUNDLE_BYTES,
    MAX_FILE_BYTES,
    MAX_FILES,
    ReleaseBundle,
    ReleaseFile,
    VerifiedRelease,
    verify_release_bundle,
)
from trading_bot.supervised_release.installation_contract import (
    ANCESTORS,
    IMAGE_ACES,
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstalledEvidence,
    ObjectFacts,
    ObserverNative,
    ReadSession,
    ReleasePaths,
)
from trading_bot.supervised_release.model import DURABLE_DATA_ROOT, PRODUCTION_PYTHON


def replay_inputs(release: VerifiedRelease, binding: RuntimeBinding) -> ReleasePaths:
    """Replay even constructed/tampered evidence before touching the host."""
    if type(release) is not VerifiedRelease or type(binding) is not RuntimeBinding:
        raise ValueError("exact accepted inputs required")
    replay = verify_release_bundle(
        release.bundle,
        expected_manifest_sha256=release.expected_manifest_sha256,
        expected_source_head=release.expected_source_head,
        expected_source_tree=release.expected_source_tree,
        expected_source_paths=release.expected_source_paths,
    )
    if replay != release or binding.verified_release != release:
        raise ValueError("accepted release mismatch")
    RuntimeBinding.from_json(binding.to_json(), verified_release=replay)
    manifest = replay.manifest
    if (manifest.production_python_version, manifest.production_python_sha256) != (
        PYTHON_VERSION,
        PYTHON_SHA256,
    ):
        raise ValueError("production Python declaration mismatch")
    paths = ReleasePaths(manifest.release_id)
    files = {item.relative_path for item in replay.bundle.files}
    directories = {
        str(parent).replace("\\", "/")
        for name in files
        for parent in PureWindowsPath(name).parents
        if str(parent) != "."
    }
    if files & directories or len(files) + len(directories) > MAX_FILES * 2:
        raise ValueError("bounded disjoint file/directory namespace required")
    for name in files | directories:
        if len(paths.child(paths.staging, name)) >= 1000:
            raise ValueError("native path budget exceeded")
    durable = PureWindowsPath(DURABLE_DATA_ROOT)
    for root in (paths.final, paths.staging):
        lexical = PureWindowsPath(paths.admit(root))
        if (
            lexical == durable
            or durable in lexical.parents
            or lexical in durable.parents
        ):
            raise ValueError("durable and release roots must be separate")
    return paths


def check_object(
    fact: ObjectFacts | None,
    path: str,
    *,
    directory: bool,
    volume: int | None = None,
    image_policy: bool = True,
) -> ObjectFacts:
    if (
        type(fact) is not ObjectFacts
        or fact.path != path
        or fact.kind != ("directory" if directory else "file")
        or fact.reparse
        or fact.links != 1
        or fact.filesystem != "NTFS"
        or fact.local is not True
        or fact.persistent_acls is not True
        or type(fact.identity) is not tuple
        or len(fact.identity) != 2
        or any(type(value) is not int or value <= 0 for value in fact.identity)
        or (volume is not None and fact.identity[0] != volume)
        or (
            image_policy
            and (
                fact.owner != ADMINISTRATORS_SID
                or fact.protected is not True
                or fact.aces != IMAGE_ACES
            )
        )
    ):
        raise ValueError("object identity/security rejected")
    return fact


def observe_parent(session: ReadSession) -> ObjectFacts:
    """Pin each ancestor independently; require exact policy on releases parent."""
    volume = None
    for index, path in enumerate(ANCESTORS):
        fact = check_object(
            session.object(path, directory=True),
            path,
            directory=True,
            volume=volume,
            image_policy=index == len(ANCESTORS) - 1,
        )
        volume = fact.identity[0]
        if index < len(ANCESTORS) - 1:
            # Ancestors need not have the image ACL, but must not grant any
            # non-admin principal write/delete/child-delete/owner/DACL rights.
            if fact.owner != ADMINISTRATORS_SID:
                raise ValueError("ancestor owner rejected")
            for sid, mask, kind, flags in fact.aces:
                if kind != 0 or flags & ~0x13:
                    raise ValueError("ancestor ACL shape rejected")
                if sid not in {IMAGE_ACES[0][0], IMAGE_ACES[1][0]} and mask & ~0x1200A9:
                    raise ValueError("ancestor writable by runtime principal")
    return fact


def _observe_image(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    native: ObserverNative,
    *,
    staging: bool,
) -> InstalledEvidence:
    paths = replay_inputs(release, binding)
    root = paths.staging if staging else paths.final
    with native.read_session(paths) as session:
        parent = observe_parent(session)
        image = check_object(
            session.object(root, directory=True),
            root,
            directory=True,
            volume=parent.identity[0],
        )
        expected_files = {item.relative_path: item for item in release.bundle.files}
        expected_directories = {
            str(parent).replace("\\", "/")
            for name in expected_files
            for parent in PureWindowsPath(name).parents
            if str(parent) != "."
        }
        observed_files = {}
        observed_directories = set()
        identities = {parent.identity, image.identity}
        observed_names = {}
        observed_facts = {root: image}
        pending = [(root, "")]
        visited, total = 0, 0
        while pending:
            path, prefix = pending.pop()
            names = session.names(path)
            observed_names[path] = names
            if type(names) is not tuple or len(names) > MAX_FILES * 2:
                raise ValueError("bounded namespace required")
            if any(type(name) is not str for name in names) or len(
                {name.casefold() for name in names}
            ) != len(names):
                raise ValueError("namespace aliases rejected")
            for name in names:
                visited += 1
                if visited > MAX_FILES * 2:
                    raise ValueError("namespace budget exceeded")
                if not name or "/" in name or "\\" in name:
                    raise ValueError("noncanonical directory entry")
                relative = prefix + name
                directory = relative in expected_directories
                if not directory and relative not in expected_files:
                    raise ValueError("extra or noncanonical namespace")
                child = paths.child(root, relative)
                facts = check_object(
                    session.object(child, directory=directory),
                    child,
                    directory=directory,
                    volume=parent.identity[0],
                )
                if facts.identity in identities:
                    raise ValueError("object alias rejected")
                identities.add(facts.identity)
                if directory:
                    observed_facts[child] = facts
                    observed_directories.add(relative)
                    pending.append((child, relative + "/"))
                else:
                    if not 0 <= facts.size <= MAX_FILE_BYTES:
                        raise ValueError("file budget exceeded")
                    data = session.read(child, MAX_FILE_BYTES)
                    total += len(data)
                    if total > MAX_BUNDLE_BYTES or len(data) != facts.size:
                        raise ValueError("image byte budget/size rejected")
                    expected = expected_files[relative]
                    if (
                        data != expected.data
                        or hashlib.sha256(data).hexdigest() != expected.sha256
                    ):
                        raise ValueError("image bytes/hash mismatch")
                    observed_files[relative] = ReleaseFile(relative, data)
        if (
            set(observed_files) != set(expected_files)
            or observed_directories != expected_directories
        ):
            raise ValueError("incomplete image namespace")
        reconstructed = verify_release_bundle(
            ReleaseBundle(
                tuple(observed_files[name] for name in sorted(observed_files))
            ),
            expected_manifest_sha256=release.expected_manifest_sha256,
            expected_source_head=release.expected_source_head,
            expected_source_tree=release.expected_source_tree,
            expected_source_paths=release.expected_source_paths,
        )
        if reconstructed != release:
            raise ValueError("verified release replay mismatch")
        RuntimeBinding.from_json(binding.to_json(), verified_release=reconstructed)
        # This is an independent host observation, never a manifest inference.
        runtime = r"F:\AITradingBot\runtime"
        check_object(
            session.object(runtime, directory=True),
            runtime,
            directory=True,
            volume=parent.identity[0],
            image_policy=False,
        )
        python = check_object(
            session.object(PRODUCTION_PYTHON, directory=False),
            PRODUCTION_PYTHON,
            directory=False,
            volume=parent.identity[0],
            image_policy=False,
        )
        for path in (runtime, PRODUCTION_PYTHON):
            facts = session.object(path, directory=path == runtime)
            if facts is None or facts.owner != ADMINISTRATORS_SID:
                raise ValueError("runtime owner rejected")
            for sid, mask, kind, flags in facts.aces:
                if (
                    kind != 0
                    or flags & ~0x13
                    or (
                        sid not in {IMAGE_ACES[0][0], IMAGE_ACES[1][0]}
                        and mask & ~0x1200A9
                    )
                ):
                    raise ValueError("runtime security rejected")
        python_bytes = session.read(PRODUCTION_PYTHON, MAX_FILE_BYTES)
        if (
            len(python_bytes) != python.size
            or hashlib.sha256(python_bytes).hexdigest() != PYTHON_SHA256
            or session.python_version() != PYTHON_VERSION
        ):
            raise ValueError("production Python host mismatch")
        for path, facts in observed_facts.items():
            if session.object(path, directory=True) != facts or set(
                session.names(path)
            ) != set(observed_names[path]):
                raise ValueError("directory observation drift")
        if observe_parent(session) != parent:
            raise ValueError("parent observation drift")
        result = InstalledEvidence(
            paths.release_id,
            release.expected_manifest_sha256,
            binding.sha256,
            parent.identity,
            image.identity,
            python.identity,
        )
    return result


def observe_installed_release(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    *,
    native: ObserverNative | None = None,
) -> InstalledEvidence:
    """Reopen only the exact derived FINAL; no cached installer facts are admitted."""
    if native is None:
        from trading_bot.supervised_release.native_read import WindowsObserver

        native = WindowsObserver()
    return _observe_image(release, binding, native, staging=False)


def observe_staging_release(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    *,
    native: ObserverNative,
) -> InstalledEvidence:
    """The identical independent replay at the source-derived staging location."""
    return _observe_image(release, binding, native, staging=True)
