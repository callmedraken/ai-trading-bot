"""FR1 publication-parent regressions: production names are memory keys only."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.runtime import (
    personal_desktop_paper_account_publication as publication,
)
from trading_bot.runtime import (
    personal_desktop_paper_account_publication_native as native,
)
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_provisioning import (
    prepare_personal_desktop_paper_account_bundle_for_test,
)
from trading_bot.runtime.windows_authority import AuthorityObjectError
from trading_bot.runtime.windows_authority_security import SecurityInspection

from .test_manual_paper_selected_c3_snapshot import selected_case as selected_case
from .test_personal_desktop_paper_account_provisioning import inputs as inputs
from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)
from .test_personal_desktop_paper_account_security import MemoryReadApi, Node

State = publication.PaperPublicationState
Status = publication.PaperPublicationStatus
Phase = publication.PaperPublicationPhase


class MemoryPublicationApi(MemoryReadApi):
    """Dictionary-only create/write/ACL/rename model; no native or disk effects."""

    def __init__(self, genesis_id):
        super().__init__()
        self.layout = {
            publication.publication_entry_path(Path(root), entry): entry.spec
            for root in (
                security.PERSONAL_DESKTOP_PAPER_V2_ROOT,
                security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT,
            )
            for entry in publication.paper_publication_layout(genesis_id)
        }
        self.after_create = lambda path: None
        self.renames = 0

    def occupied(self, path):
        assert path in self.layout
        return path in self.nodes

    def create_directory(self, path):
        return self.create(path, None)

    def create_file(self, path):
        return self.create(path, b"")

    def create(self, path, payload):
        assert path in self.layout and path not in self.nodes
        kind = self.layout[path].kind
        self.nodes[path] = Node(
            security.PaperObjectObservation(
                SecurityInspection(
                    path,
                    path,
                    kind,
                    security.ADMINISTRATORS_SID,
                    True,
                    (),
                    False,
                    "F:\\",
                    "NTFS",
                ),
                (7, len(self.nodes) + 100),
                0,
                1,
            ),
            payload,
        )
        self.after_create(path)
        return self.open(path, kind)

    def write(self, handle, payload):
        node = self.handles[handle]
        node.payload = payload
        node.observation = replace(node.observation, byte_length=len(payload))

    def flush(self, handle):
        assert self.handles[handle].payload is not None

    def apply_policy(self, handle, policy):
        node = self.handles[handle]
        node.observation = replace(
            node.observation,
            security=replace(
                node.observation.security, owner_sid=policy.owner_sid, aces=policy.aces
            ),
        )

    def rename_no_clobber(self, staging, final):
        assert not self.handles and not self.renames and final not in self.nodes
        assert staging == security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT
        assert final == security.PERSONAL_DESKTOP_PAPER_V2_ROOT
        for path, node in tuple(self.nodes.items()):
            assert path == staging or path.startswith(staging + "\\")
            new_path = final + path[len(staging) :]
            del self.nodes[path]
            node.observation = replace(
                node.observation,
                security=replace(
                    node.observation.security,
                    expected_path=new_path,
                    final_path=new_path,
                ),
            )
            self.nodes[new_path] = node
        self.renames += 1


def install_memory_publisher(patch, bundle):
    anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    parent = MemoryReadApi()
    parent.put(security.PERSONAL_DESKTOP_PAPER_PARENT)
    api = MemoryPublicationApi(anchor.genesis_checkpoint_id)
    validation = SimpleNamespace(
        bootstrap_verification=SimpleNamespace(
            bootstrap=SimpleNamespace(approved_account_sid=anchor.approved_trading_sid)
        )
    )
    patch.setattr(
        publication, "require_paper_publication_inputs", lambda **kw: validation
    )
    patch.setattr(security, "WindowsPaperReadNativeApi", lambda: parent)
    patch.setattr(native, "WindowsPaperPublicationApi", lambda genesis_id: api)
    # Every native boundary is a deterministic fake before enabling locally.
    patch.setattr(
        security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", True
    )
    return api, parent


@pytest.mark.parametrize("old_guard", [False, True])
@pytest.mark.parametrize("metadata", ["byte_length", "links"])
def test_publication_parent_child_metadata_and_old_failure_flow(
    inputs, monkeypatch, old_guard, metadata
):
    bundle = prepare_personal_desktop_paper_account_bundle_for_test(**inputs)
    old_failures = []
    with monkeypatch.context() as patch:
        api, parent = install_memory_publisher(patch, bundle)
        if old_guard:

            class OldParentGuard(security.PinnedPaperReadSession):
                def __enter__(self):
                    self.pin(security.PERSONAL_DESKTOP_PAPER_PARENT)
                    return self

                def finish(self):
                    try:
                        super().finish()
                    except AuthorityObjectError as error:
                        old_failures.append(str(error))
                        raise

            patch.setattr(security, "PinnedPaperPublicationParent", OldParentGuard)

        def child_created(path):
            if path == security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT:
                node = parent.nodes[security.PERSONAL_DESKTOP_PAPER_PARENT]
                node.observation = replace(
                    node.observation,
                    **{metadata: getattr(node.observation, metadata) + 1},
                )

        api.after_create = child_created
        result = publication.publish_personal_desktop_paper_account(bundle=bundle)
    assert result.status is (
        Status.BLOCKED if old_guard else Status.PUBLISHED_AND_VERIFIED
    )
    assert result.phase is (Phase.STAGED_VERIFY if old_guard else Phase.COMPLETE)
    assert result.state is (
        State.STAGING_REQUIRES_REVIEW if old_guard else State.FINAL_REQUIRES_VALIDATION
    )
    assert result.failure_type == ("AuthorityObjectError" if old_guard else None)
    assert old_failures == (
        ["PD1B pinned identity/security drift"] * 2 if old_guard else []
    )  # Both post-staging revalidation and outer context finalization failed.
    assert (
        result.staging_may_have_begun and result.rename_may_have_begun is not old_guard
    )
    assert api.renames == (0 if old_guard else 1)
    assert all(count >= 3 for count in api.inspections.values())  # Exact tree verified.
    assert not api.handles and not parent.handles


@pytest.mark.parametrize("drift", ["identity", "acl", "path", "named-replacement"])
def test_publication_parent_replacement_blocks_before_rename(
    inputs, monkeypatch, drift
):
    bundle = prepare_personal_desktop_paper_account_bundle_for_test(**inputs)
    with monkeypatch.context() as patch:
        api, parent = install_memory_publisher(patch, bundle)

        def child_created(path):
            if path != security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT:
                return
            name = security.PERSONAL_DESKTOP_PAPER_PARENT
            node = parent.nodes[name]
            if drift in {"identity", "named-replacement"}:
                changed = replace(node.observation, identity=(7, 999))
            else:
                changed = replace(
                    node.observation,
                    security=replace(
                        node.observation.security,
                        **(
                            {"aces": ()}
                            if drift == "acl"
                            else {"final_path": name.lower()}
                        ),
                    ),
                )
            if drift == "named-replacement":
                parent.nodes[name] = replace(node, observation=changed)
            else:
                node.observation = changed

        api.after_create = child_created
        result = publication.publish_personal_desktop_paper_account(bundle=bundle)
    assert result.status is Status.BLOCKED and result.phase is Phase.STAGED_VERIFY
    assert result.state is State.STAGING_REQUIRES_REVIEW
    assert result.staging_may_have_begun and not result.rename_may_have_begun
    assert api.renames == 0 and not api.handles and not parent.handles


@pytest.mark.parametrize("publication_fails", [False, True])
@pytest.mark.parametrize("occupancy_readable", [False, True])
def test_parent_finalization_failure_preserves_prior_occupancy_and_primary_failure(
    inputs, monkeypatch, publication_fails, occupancy_readable
):
    bundle = prepare_personal_desktop_paper_account_bundle_for_test(**inputs)
    publish_algorithm = publication._publish
    with monkeypatch.context() as patch:
        api, parent = install_memory_publisher(patch, bundle)
        if publication_fails:

            def fail_read(node):
                raise ValueError("test publication read failure")

            api.on_read = fail_read
        captured = []

        def publish_then_drift(*args, **kwargs):
            result = publish_algorithm(*args, **kwargs)
            captured.append(result)
            node = parent.nodes[security.PERSONAL_DESKTOP_PAPER_PARENT]
            node.observation = replace(node.observation, identity=(7, 999))

            def forbidden_probe(path):
                raise AssertionError("must not probe occupancy after parent failure")

            api.occupied = forbidden_probe
            return result

        if not occupancy_readable:
            occupied = api.occupied

            def unreadable_after_create(path):
                if api.nodes:
                    raise PermissionError("test occupancy read failure")
                return occupied(path)

            api.occupied = unreadable_after_create
        patch.setattr(publication, "_publish", publish_then_drift)
        result = publication.publish_personal_desktop_paper_account(bundle=bundle)
    prior = captured[0]
    assert result.status is Status.BLOCKED
    assert result.state is prior.state
    assert (result.state is None) is not occupancy_readable
    assert result.failure_type == (prior.failure_type or "AuthorityObjectError")
    assert result.phase is (
        Phase.FINAL_VERIFY if prior.phase is Phase.COMPLETE else prior.phase
    )
    assert result.staging_may_have_begun == prior.staging_may_have_begun
    assert result.rename_may_have_begun == prior.rename_may_have_begun
    assert not api.handles and not parent.handles
