"""PD1B whole-reader verification against memory-only fixed Windows objects."""

import builtins
import inspect
import socket
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.market_data import serialize_daily_snapshot
from trading_bot.runtime import (
    PaperAccountGenesisRequest,
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
    PaperOperationArtifactEvidence,
    PaperOperationDiagnosticCode,
    PaperOperationOutcome,
    PaperOperationReceipt,
    PaperOperationStatus,
    checkpointed_paper_cycle_report_from_result,
    checkpointed_paper_cycle_report_reference,
    create_genesis_paper_account_checkpoint,
    create_paper_operation_intent,
    create_successor_paper_account_checkpoint,
    derive_checkpointed_verified_snapshot_application_id,
    execute_checkpointed_verified_snapshot_paper_cycle,
    serialize_checkpointed_paper_cycle_report,
    serialize_checkpointed_verified_snapshot_paper_cycle_request,
    serialize_paper_account_checkpoint,
    serialize_paper_operation_receipt,
    serialize_successor_paper_account_checkpoint,
    verified_prior_from_full_lineage,
    verify_paper_account_lineage,
)
from trading_bot.runtime import personal_desktop_paper_account_read_authority as reader
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountAnchor,
    PersonalDesktopPaperAccountError,
    derive_personal_desktop_paper_account_id,
    serialize_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)
from trading_bot.runtime.windows_authority import WindowsAuthorityError
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    ProductionAuthorityEvidence,
)
from trading_bot.runtime.windows_authority_validation import (
    issue_validated_production_authority_for_test,
)

from .test_checkpointed_paper_cycle_successor import _later_cycle_request
from .test_checkpointed_verified_snapshot_execution import (
    _checkpoint_verification,
    _permissive_limits,
    _request,
    _target,
)
from .test_paper_account_lineage_verification import _next_snapshot_verification
from .test_personal_desktop_paper_account_security import (
    ANCHOR,
    OPERATIONS,
    ROOT,
    RUNTIME,
    SID,
    MemoryReadApi,
)
from .test_verified_snapshot_preparation import _policies, _verification, calendar
from .test_windows_authority import _bootstrap

MACHINE = "22222222-2222-5222-8222-222222222222"


class Observer:
    def __init__(self, **changes):
        self.observation = replace(
            TradingTokenObservation(SID, 1, False, False, ()), **changes
        )
        self.calls = 0

    def observe(self):
        self.calls += 1
        return self.observation


def artifact(kind, identity, payload):
    return PaperAccountLineageArtifact(
        kind, identity, payload, sha256(payload).hexdigest(), len(payload)
    )


def evidence(item):
    return PaperAccountLineageArtifactEvidence(
        item.kind, item.artifact_id, item.sha256, item.byte_length
    )


def memory_case(edges=0, *, no_action=False):
    old, _ = _checkpoint_verification()
    genesis_model = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            old.checkpoint.account_state.as_of, Decimal("2000"), (), Decimal("0")
        )
    )
    genesis_bytes = serialize_paper_account_checkpoint(genesis_model)
    genesis = artifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        genesis_model.checkpoint_id,
        genesis_bytes,
    )
    identity = dict(
        machine_authority_id=MACHINE,
        approved_trading_sid=SID,
        genesis_checkpoint_id=str(genesis.artifact_id),
        genesis_sha256=genesis.sha256,
        genesis_byte_length=genesis.byte_length,
    )
    anchor = PersonalDesktopPaperAccountAnchor(
        derive_personal_desktop_paper_account_id(**identity), **identity
    )
    api = MemoryReadApi()
    api.put(ANCHOR, serialize_personal_desktop_paper_account_anchor(anchor))
    genesis_path = (
        ROOT
        + f"\\paper-account-genesis-{genesis.artifact_id}"
        + f"\\paper-account-checkpoint-{genesis.artifact_id}.json"
    )
    api.put(genesis_path, genesis_bytes)
    api.put(OPERATIONS)
    successors, reports, snapshots, receipts, configurations, directories = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    prior = verify_paper_account_lineage(
        genesis, genesis.artifact_id, (), (), (), calendar()
    )
    for index in range(edges):
        verification = _verification() if index == 0 else _next_snapshot_verification()
        request = (
            _request(verification) if index == 0 else _later_cycle_request(verification)
        )
        if no_action:
            request = replace(
                request,
                target=_target("0", "0", "2000"),
                request_id=UUID(int=100 + index),
            )
        result = execute_checkpointed_verified_snapshot_paper_cycle(
            request, verified_prior_from_full_lineage(prior), verification, calendar()
        )
        report = checkpointed_paper_cycle_report_from_result(result)
        report_bytes = serialize_checkpointed_paper_cycle_report(report)
        successor = create_successor_paper_account_checkpoint(
            report.evidence.prior_checkpoint,
            report.evidence.prior_lineage_id,
            result,
            checkpointed_paper_cycle_report_reference(report_bytes),
        )
        successor_bytes = serialize_successor_paper_account_checkpoint(successor)
        snapshot_bytes = serialize_daily_snapshot(verification.snapshot)
        successors.append(
            artifact(
                PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
                successor.checkpoint_id,
                successor_bytes,
            )
        )
        reports.append(
            artifact(
                PaperAccountLineageArtifactKind.CYCLE_REPORT,
                report.report_id,
                report_bytes,
            )
        )
        snapshots.append(
            artifact(
                PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
                verification.snapshot.snapshot_id,
                snapshot_bytes,
            )
        )
        full = verify_paper_account_lineage(
            genesis,
            successor.checkpoint_id,
            tuple(successors),
            tuple(reports),
            tuple(snapshots),
            calendar(),
        )
        assert full.evidence is not None
        config = serialize_checkpointed_verified_snapshot_paper_cycle_request(request)
        configurations.append(config)
        intent = create_paper_operation_intent(
            UUID(int=index + 1),
            prior.evidence,
            prior.evidence.checkpoint_artifacts[-1],
            evidence(snapshots[-1]),
            PaperOperationArtifactEvidence(sha256(config).hexdigest(), len(config)),
            request,
        )
        receipt = PaperOperationReceipt(
            1,
            intent.operation_id,
            intent,
            PaperOperationStatus.COMPLETED,
            PaperOperationOutcome.NO_ACTION
            if result.status.value == "NO_ACTION"
            else PaperOperationOutcome.APPLIED,
            PaperOperationDiagnosticCode.NONE,
            prior.evidence,
            full.evidence,
            evidence(reports[-1]),
            evidence(successors[-1]),
            result.application_id,
            result.result_id,
        )
        receipts.append(receipt)
        directory = RUNTIME + f"\\paper-account-transition-{result.application_id}"
        directories.append(directory)
        api.put(
            directory + f"\\checkpointed-paper-cycle-report-{result.result_id}.json",
            report_bytes,
        )
        api.put(
            directory + f"\\paper-account-checkpoint-{successor.checkpoint_id}.json",
            successor_bytes,
        )
        api.put(
            security.historical_snapshot_path(verification.snapshot.snapshot_id),
            snapshot_bytes,
        )
        operation = OPERATIONS + f"\\paper-operation-{receipt.receipt_id}"
        api.put(
            operation + f"\\paper-operation-receipt-{receipt.receipt_id}.json",
            serialize_paper_operation_receipt(receipt),
        )
        prior = full
    return SimpleNamespace(
        api=api,
        anchor=anchor,
        genesis=genesis,
        genesis_path=genesis_path,
        successors=successors,
        reports=reports,
        snapshots=snapshots,
        receipts=receipts,
        configurations=tuple(configurations),
        directories=directories,
        full=prior,
    )


def read_case(case, *, observer=None, configurations=None):
    return reader._read_account_evidence(
        MACHINE,
        SID,
        api=case.api,
        observer=observer or Observer(),
        calendar=calendar(),
        configurations=case.configurations
        if configurations is None
        else configurations,
    )


def test_genesis_only_exposes_immutable_evidence_after_pins_close():
    case = memory_case()
    observer = Observer()
    result = read_case(case, observer=observer)
    assert result.prior_checkpoint.checkpoint_id == case.genesis.artifact_id
    assert result.lineage == case.full.evidence
    assert result.prior_checkpoint.compact_state.cash == Decimal("2000")
    assert observer.calls == 2
    assert not case.api.handles
    assert all(count >= 3 for count in case.api.inspections.values())
    with pytest.raises(FrozenInstanceError):
        result.anchor = None
    with pytest.raises(PersonalDesktopPaperAccountError):
        reader.require_validated_personal_desktop_paper_account(result)


@pytest.mark.parametrize("edges,no_action", [(1, False), (1, True), (2, True)])
def test_full_lineage_and_receipts_verify_without_order_or_newest_selection(
    edges, no_action
):
    case = memory_case(edges, no_action=no_action)
    first = read_case(case)
    # Reverse all directory enumeration, deliberately disconnecting it from
    # chronology. Object names supply candidates, not the terminal checkpoint.
    for path, node in case.api.nodes.items():
        if node.payload is None:
            case.api.overrides[path] = tuple(reversed(case.api.names(None, path, 1024)))
    second = read_case(case)
    assert first == second
    assert first.lineage == case.full.evidence
    assert first.prior_checkpoint.checkpoint_id == case.successors[-1].artifact_id
    assert first.lineage.edge_count == edges
    assert not case.api.handles


def test_production_requires_genuine_c1_before_token_or_native_api(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid C1 reached native boundary")

    monkeypatch.setattr(reader, "WindowsTradingTokenObserver", forbidden)
    monkeypatch.setattr(reader, "WindowsPaperReadNativeApi", forbidden)
    bootstrap = _bootstrap()
    production = ProductionAuthorityEvidence(
        database_path=bootstrap.database_path,
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="33" * 32,
        migration_id="test/v1",
        release_manifest_digest="44" * 32,
        sqlite_build_manifest_digest="55" * 32,
    )
    test_c1 = issue_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=production,
    )
    for value in (
        None,
        {},
        SimpleNamespace(machine_authority_id=MACHINE, approved_account_sid=SID),
        test_c1,
    ):
        with pytest.raises(WindowsAuthorityError):
            reader.read_personal_desktop_paper_account(value)
    assert "path" not in str(
        inspect.signature(reader.read_personal_desktop_paper_account)
    )
    with pytest.raises(TypeError):
        reader.ValidatedPersonalDesktopPaperAccount()
    forged = object.__new__(reader.ValidatedPersonalDesktopPaperAccount)
    with pytest.raises(PersonalDesktopPaperAccountError):
        reader.require_validated_personal_desktop_paper_account(forged)


def test_production_entrypoint_registers_only_after_success(monkeypatch):
    # Isolate only the already-tested C1/native construction boundaries. This
    # memory test does not manufacture a genuine C1 capability or access disk.
    case = memory_case()
    c1 = SimpleNamespace(machine_authority_id=MACHINE, approved_account_sid=SID)
    monkeypatch.setattr(
        reader,
        "require_validated_production_authority",
        lambda value: c1 if value is c1 else None,
    )
    monkeypatch.setattr(reader, "WindowsTradingTokenObserver", Observer)
    monkeypatch.setattr(reader, "WindowsPaperReadNativeApi", lambda: case.api)
    monkeypatch.setattr(reader, "BoundMarketCalendar", lambda *args: calendar())
    authority = reader.read_personal_desktop_paper_account(c1)
    assert authority.evidence.anchor == case.anchor
    assert authority.operation_root == RUNTIME
    assert not case.api.handles
    case.api.nodes[ANCHOR].payload = b"invalid"
    count = len(reader._REGISTRY)
    with pytest.raises((WindowsAuthorityError, ValueError)):
        reader.read_personal_desktop_paper_account(c1)
    assert len(reader._REGISTRY) == count


@pytest.mark.parametrize(
    "changes",
    [
        {"user_sid": SID + "0"},
        {"elevated": True},
        {"token_type": 2},
        {"thread_token_present": True},
        {"groups": (("S-1-5-32-544", 4),)},
    ],
)
def test_wrong_runtime_token_stops_before_any_file_observation(changes):
    case = memory_case()
    with pytest.raises(WindowsAuthorityError):
        read_case(case, observer=Observer(**changes))
    assert case.api.calls == []


@pytest.mark.parametrize(
    "change",
    [
        "machine",
        "sid",
        "identity",
        "hash",
        "length",
        "noncanonical",
        "unknown",
        "duplicate",
    ],
)
def test_stale_or_malformed_anchor_rejected(change):
    case = memory_case()
    anchor = case.anchor
    identity = dict(
        machine_authority_id=anchor.machine_authority_id,
        approved_trading_sid=anchor.approved_trading_sid,
        genesis_checkpoint_id=anchor.genesis_checkpoint_id,
        genesis_sha256=anchor.genesis_sha256,
        genesis_byte_length=anchor.genesis_byte_length,
    )
    if change in {"machine", "sid", "hash", "length"}:
        field, value = {
            "machine": ("machine_authority_id", str(UUID(int=1))),
            "sid": ("approved_trading_sid", SID + "0"),
            "hash": ("genesis_sha256", "00" * 32),
            "length": ("genesis_byte_length", 1),
        }[change]
        identity[field] = value
        payload = serialize_personal_desktop_paper_account_anchor(
            PersonalDesktopPaperAccountAnchor(
                derive_personal_desktop_paper_account_id(**identity), **identity
            )
        )
    elif change == "identity":
        payload = case.api.nodes[ANCHOR].payload.replace(
            anchor.paper_account_id.encode(), str(UUID(int=1)).encode()
        )
    elif change == "noncanonical":
        payload = case.api.nodes[ANCHOR].payload + b" "
    elif change == "unknown":
        payload = case.api.nodes[ANCHOR].payload.replace(b"{", b'{"unknown":1,', 1)
    else:
        payload = case.api.nodes[ANCHOR].payload.replace(
            b"{", b'{"schema":"duplicate",', 1
        )
    case.api.put(ANCHOR, payload)
    with pytest.raises((WindowsAuthorityError, ValueError)):
        read_case(case)
    assert not case.api.handles


@pytest.mark.parametrize(
    "place,name",
    [
        (ROOT, "unexpected"),
        (ROOT, "Runtime"),
        (RUNTIME, "unexpected"),
        (RUNTIME, ".paper-account-transition-dead.staging"),
        (OPERATIONS, "unexpected"),
        (OPERATIONS, ".paper-operation-dead.staging"),
        (security.PERSONAL_DESKTOP_PAPER_PARENT, ".Paper-v2.provisioning"),
    ],
)
def test_unrecognized_or_staging_layout_blocks(place, name):
    case = memory_case()
    names = case.api.names(None, place, 1024)
    case.api.overrides[place] = (*names, name)
    with pytest.raises((WindowsAuthorityError, ValueError)):
        read_case(case)
    assert not case.api.handles


@pytest.mark.parametrize(
    "kind", ["genesis", "report", "successor", "receipt", "snapshot"]
)
def test_corrupt_installed_artifacts_block_authority(kind):
    case = memory_case(1)
    if kind == "genesis":
        path = case.genesis_path
    elif kind == "snapshot":
        path = security.historical_snapshot_path(case.snapshots[0].artifact_id)
    else:
        prefix = {
            "report": "checkpointed-paper-cycle-report-",
            "successor": "paper-account-checkpoint-",
            "receipt": "paper-operation-receipt-",
        }[kind]
        path = next(
            p
            for p in case.api.nodes
            if p.startswith(RUNTIME + "\\") and p.rsplit("\\", 1)[-1].startswith(prefix)
        )
    case.api.put(path, case.api.nodes[path].payload + b" ")
    with pytest.raises((WindowsAuthorityError, ValueError)):
        read_case(case)
    assert not case.api.handles


def test_conflicting_successor_edges_rejected_without_choosing_one():
    left = memory_case(1)
    right = memory_case(1, no_action=True)
    assert left.genesis == right.genesis
    for path, node in right.api.nodes.items():
        if path.startswith(RUNTIME + "\\") and path not in left.api.nodes:
            left.api.put(path, node.payload)
    with pytest.raises(PersonalDesktopPaperAccountError, match="unique terminal"):
        read_case(left, configurations=left.configurations + right.configurations)


def test_final_transition_without_receipt_blocks_without_recovery():
    case = memory_case(1)
    case.api.overrides[OPERATIONS] = ()
    with pytest.raises(PersonalDesktopPaperAccountError, match="no verified receipt"):
        read_case(case, configurations=())


@pytest.mark.parametrize(
    "configurations",
    [
        (),
        (b"wrong",),
        (r"F:\outside\config.json",),
        (b"x" * (reader.MAX_HISTORICAL_CONFIGURATION_BYTES + 1),),
    ],
)
def test_configuration_dependencies_are_bounded_bytes_and_hash_matched(configurations):
    case = memory_case(1)
    with pytest.raises(PersonalDesktopPaperAccountError):
        read_case(case, configurations=configurations)


def test_reader_rejects_snapshot_dependency_alias_or_acl_drift():
    case = memory_case(1)
    snapshot = security.historical_snapshot_path(case.snapshots[0].artifact_id)
    node = case.api.nodes[snapshot]
    node.observation = replace(
        node.observation,
        security=replace(
            node.observation.security,
            final_path=r"\\?\GLOBALROOT\Device\HarddiskVolume1\snapshot.json",
        ),
    )
    with pytest.raises(WindowsAuthorityError):
        read_case(case)
    assert not case.api.handles


@pytest.mark.parametrize("change", ["acl", "identity", "token"])
def test_completion_drift_never_exposes_evidence(change):
    case = memory_case()
    observer = Observer()

    def drift(path, count, node):
        if path == ANCHOR and count == 2:
            if change == "acl":
                node.observation = replace(
                    node.observation,
                    security=replace(node.observation.security, dacl_protected=False),
                )
            elif change == "identity":
                node.observation = replace(node.observation, identity=(7, 900))
            else:
                observer.observation = replace(observer.observation, elevated=True)

    case.api.on_inspect = drift
    with pytest.raises(WindowsAuthorityError):
        read_case(case, observer=observer)
    assert not case.api.handles


def test_genesis_reader_is_offline_and_never_opens_python_files(monkeypatch):
    case = memory_case()

    def forbidden(*args, **kwargs):
        pytest.fail("read authority reached a filesystem write/network primitive")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    result = read_case(case)
    assert result.prior_checkpoint.checkpoint_id == case.genesis.artifact_id


def install_receipt(case, receipt):
    directory = OPERATIONS + f"\\paper-operation-{receipt.receipt_id}"
    path = directory + f"\\paper-operation-receipt-{receipt.receipt_id}.json"
    case.api.put(path, serialize_paper_operation_receipt(receipt))
    return path


def test_duplicate_successor_operation_receipt_is_rejected():
    case = memory_case(1)
    original = case.receipts[0]
    intent = create_paper_operation_intent(
        UUID(int=999),
        original.prior_lineage_evidence,
        original.intent.terminal_checkpoint_artifact,
        original.intent.completed_snapshot_artifact,
        original.intent.cycle_configuration_artifact,
        original.intent.request,
    )
    install_receipt(
        case, replace(original, receipt_id=intent.operation_id, intent=intent)
    )
    with pytest.raises(
        PersonalDesktopPaperAccountError, match="duplicate/conflicting operation"
    ):
        read_case(case)


def test_canonical_but_wrong_receipt_outcome_fails_existing_a67_verifier():
    case = memory_case(1)
    assert case.receipts[0].outcome is PaperOperationOutcome.APPLIED
    install_receipt(
        case, replace(case.receipts[0], outcome=PaperOperationOutcome.NO_ACTION)
    )
    with pytest.raises(PersonalDesktopPaperAccountError, match="A67 verification"):
        read_case(case)


def test_failed_receipt_is_replayed_offline_and_does_not_move_terminal():
    case = memory_case()
    snapshot_verification = _verification()
    snapshot = snapshot_verification.snapshot
    snapshot_bytes = serialize_daily_snapshot(snapshot)
    references = tuple(
        replace(
            item,
            caller_asserted_open_reference_price=Decimal("300")
            if str(item.symbol) == "QQQ"
            else Decimal("103"),
        )
        for item in _request(snapshot_verification).open_references
    )
    request = _request(
        snapshot_verification,
        target=_target("0", "9", "173"),
        policies=_policies(risk_limits=_permissive_limits()),
        open_references=references,
    )
    config = serialize_checkpointed_verified_snapshot_paper_cycle_request(request)
    snapshot_artifact = artifact(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        snapshot.snapshot_id,
        snapshot_bytes,
    )
    intent = create_paper_operation_intent(
        UUID(int=99),
        case.full.evidence,
        case.full.evidence.checkpoint_artifacts[-1],
        evidence(snapshot_artifact),
        PaperOperationArtifactEvidence(sha256(config).hexdigest(), len(config)),
        request,
    )
    receipt = PaperOperationReceipt(
        1,
        intent.operation_id,
        intent,
        PaperOperationStatus.FAILED,
        None,
        PaperOperationDiagnosticCode.INSUFFICIENT_CASH,
        case.full.evidence,
        None,
        None,
        None,
        derive_checkpointed_verified_snapshot_application_id(
            case.genesis.artifact_id, request.request_id
        ),
        None,
    )
    install_receipt(case, receipt)
    case.api.put(
        security.historical_snapshot_path(snapshot.snapshot_id), snapshot_bytes
    )
    verified = read_case(case, configurations=(config,))
    assert verified.prior_checkpoint.checkpoint_id == case.genesis.artifact_id
    assert verified.receipts == (receipt,)
    install_receipt(
        case,
        replace(
            receipt, diagnostic_code=PaperOperationDiagnosticCode.APPLICATION_FAILURE
        ),
    )
    with pytest.raises(PersonalDesktopPaperAccountError, match="A67 verification"):
        read_case(case, configurations=(config,))


@pytest.mark.parametrize("place", ["transition", "receipt", "genesis"])
def test_recognized_directories_require_exact_file_set(place):
    case = memory_case(1)
    path = {
        "transition": case.directories[0],
        "receipt": OPERATIONS + f"\\paper-operation-{case.receipts[0].receipt_id}",
        "genesis": case.genesis_path.rsplit("\\", 1)[0],
    }[place]
    case.api.overrides[path] = (*case.api.names(None, path, 1024), "extra.json")
    with pytest.raises(PersonalDesktopPaperAccountError):
        read_case(case)


def test_oversized_installed_anchor_never_reaches_pd1a_parser(monkeypatch):
    case = memory_case()
    case.api.nodes[ANCHOR].observation = replace(
        case.api.nodes[ANCHOR].observation,
        byte_length=security.MAX_INSTALLED_PAPER_ANCHOR_BYTES + 1,
    )

    def forbidden(*args):
        pytest.fail("unbounded installed anchor reached PD1A parser")

    monkeypatch.setattr(
        reader, "parse_personal_desktop_paper_account_anchor", forbidden
    )
    with pytest.raises(WindowsAuthorityError):
        read_case(case)
    assert not any(call[0] == "read" for call in case.api.calls)


def test_runtime_security_checked_before_anchor_parse(monkeypatch):
    case = memory_case()
    node = case.api.nodes[RUNTIME]
    node.observation = replace(
        node.observation,
        security=replace(node.observation.security, dacl_protected=False),
    )

    def forbidden(*args):
        pytest.fail("unsafe runtime reached anchor parsing")

    monkeypatch.setattr(
        reader, "parse_personal_desktop_paper_account_anchor", forbidden
    )
    with pytest.raises(WindowsAuthorityError):
        read_case(case)
    assert not any(call[0] == "read" for call in case.api.calls)


def test_read_only_slice_keeps_production_effect_gate_false():
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert not hasattr(reader, "execute_paper_operation_once")
    assert not hasattr(reader, "commit_paper_operation_receipt")


def test_reader_inventory_bounds_and_unused_configuration_block(monkeypatch):
    case = memory_case()
    monkeypatch.setattr(security, "MAX_PAPER_V2_DIRECTORY_ENTRIES", 2)
    with pytest.raises(WindowsAuthorityError, match="inventory"):
        read_case(case)
    monkeypatch.setattr(security, "MAX_PAPER_V2_DIRECTORY_ENTRIES", 1024)
    with pytest.raises(
        PersonalDesktopPaperAccountError, match="unrecognized historical"
    ):
        read_case(case, configurations=(b"unreferenced",))
