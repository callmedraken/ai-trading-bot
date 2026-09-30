from __future__ import annotations

from types import SimpleNamespace

from scripts import d10_arch128_r4_replacement as r4
from scripts import d10_arch128_r7_readonly as r7


def _scheduler(*, enabled: bool = False, task_state: int = 1):
    return tuple(
        sorted(
            {
                "enabled": enabled,
                "task_state": task_state,
                "xml_byte_length": 1024,
                "xml_sha256": "a" * 64,
            }.items()
        )
    )


def test_preflight_reuses_complete_read_only_observer(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []

    class Reader:
        pass

    class Verifier:
        pass

    monkeypatch.setattr(r7.r4w, "WindowsArch128ReadOnlyReader", Reader)
    monkeypatch.setattr(r7, "WindowsCngVerifier", Verifier)
    monkeypatch.setattr(r7.r3, "_observe_scheduler", object())

    def observe(*args):
        calls.append(args)
        return SimpleNamespace(scheduler=_scheduler())

    monkeypatch.setattr(r7.r4c, "observe_post", observe)

    result = r7.preflight()

    assert result["status"] == "PASS"
    assert result["canonical_deployment_id"] == r4.NEW_DEPLOYMENT_ID
    assert result["evidence_root"] == "EXACT_EMPTY_AND_VERIFIED"
    assert result["activation_lease"] == "FINAL_INSTALLING_TMP_ABSENT_AND_VERIFIED"
    assert result["scheduler"] == "EXACT_DISABLED_NONRUNNING_AND_VERIFIED"
    assert len(calls) == 1
    assert isinstance(calls[0][0], Reader)
    assert isinstance(calls[0][1], Verifier)
    assert calls[0][2] is r7.r3._observe_scheduler
    assert calls[0][3] is r4.NamespaceState.COMPLETE


def test_preflight_keeps_every_effect_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        r7.r4c,
        "observe_post",
        lambda *args: SimpleNamespace(scheduler=_scheduler()),
    )

    result = r7.preflight()

    for field in (
        "production_filesystem_mutation",
        "evidence_provision",
        "scheduler_mutation",
        "lease_publication",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    ):
        assert result[field] == "NOT_RUN"


def test_preflight_blocks_if_scheduler_is_not_inert(monkeypatch) -> None:
    monkeypatch.setattr(
        r7.r4c,
        "observe_post",
        lambda *args: SimpleNamespace(scheduler=_scheduler(enabled=True)),
    )

    result = r7.preflight()

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RuntimeError"
    assert result["detail"] == "arch128_r7_scheduler_not_inert"
