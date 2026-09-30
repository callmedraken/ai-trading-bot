from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace

from scripts import d10_arch128_r5_trading_child as child


class NativeError(RuntimeError):
    def __init__(self, code: int) -> None:
        super().__init__(str(code))
        self.code = code


@dataclass
class Deployment:
    deployment_id: str
    attestation_sha256: str
    certified_source_head: str
    certified_source_tree: str
    executable_file_count: int
    production_python: str
    production_python_version: str


class Backend:
    def __init__(self, *, evidence: tuple[str, ...] = ()) -> None:
        self.evidence = evidence

    def open(self, path: str, *, directory: bool) -> int:
        if path == r"F:\AITradingBot\D10\activation.lease.json":
            raise NativeError(2)
        assert path == r"F:\AITradingBot\D10\evidence"
        assert directory is True
        return 7

    def close(self, handle: int) -> None:
        assert handle == 7

    def require_absent(self, path: str) -> None:
        assert path in {
            r"F:\AITradingBot\D10\activation.lease.json.installing",
            r"F:\AITradingBot\D10\activation.lease.json.tmp",
            r"F:\AITradingBot\D10\no-pycache",
        }

    def inspect(self, handle: int) -> object:
        assert handle == 7
        return ("facts",)

    def listdir(self, path: str) -> tuple[str, ...]:
        assert path == r"F:\AITradingBot\D10\evidence"
        return self.evidence


def _case(*, evidence: tuple[str, ...] = ()):
    source = b"reviewed-guard-source"
    digest = hashlib.sha256(source).hexdigest()
    identity = SimpleNamespace(
        deployment_id="new-id",
        unsigned_attestation_sha256="a" * 64,
        certified_source_head="b" * 40,
        certified_source_tree="c" * 40,
        executable_file_count=307,
        guard_byte_length=len(source),
        guard_sha256=digest,
    )
    r4 = SimpleNamespace(NEW_IDENTITY=identity)
    backend = Backend(evidence=evidence)
    subprocess = SimpleNamespace(run=lambda *args, **kwargs: None)
    guard = SimpleNamespace(
        __file__=__file__,
        subprocess=subprocess,
        D10_LAUNCH_GUARD=r"F:\AITradingBot\D10\launch-guard.py",
        D10_ACTIVATION_LEASE=r"F:\AITradingBot\D10\activation.lease.json",
        D10_ACTIVATION_LEASE_INSTALLING=(
            r"F:\AITradingBot\D10\activation.lease.json.installing"
        ),
        D10_ACTIVATION_LEASE_TEMP=r"F:\AITradingBot\D10\activation.lease.json.tmp",
        D10_CACHE_PREFIX=r"F:\AITradingBot\D10\no-pycache",
        D10_EVIDENCE_ROOT=r"F:\AITradingBot\D10\evidence",
        D10_PRODUCTION_PYTHON=r"F:\AITradingBot\runtime\python.exe",
        D10_PRODUCTION_PYTHON_VERSION="3.14.3",
        ERROR_FILE_NOT_FOUND=2,
        ERROR_PATH_NOT_FOUND=3,
        _NativeError=NativeError,
        GuardBlocked=RuntimeError,
        _Native=lambda: backend,
        _require_facts=lambda *args, **kwargs: None,
        _stable=lambda *args, **kwargs: None,
    )
    guard._verify_pre_source = lambda: Deployment(
        "new-id",
        "a" * 64,
        "b" * 40,
        "c" * 40,
        307,
        guard.D10_PRODUCTION_PYTHON,
        guard.D10_PRODUCTION_PYTHON_VERSION,
    )
    return guard, r4, source


def test_qualify_accepts_exact_empty_inert_deployment() -> None:
    guard, r4, source = _case()

    result = child._qualify(guard, r4, source)

    assert result["status"] == "PASS"
    assert result["second_stage_launch_trap"] == "NOT_CALLED"
    assert result["activation"] == "NOT_RUN"
    assert result["source_launch"] == "NOT_RUN"
    assert result["scheduler"] == "NOT_RUN"


def test_qualify_rejects_nonempty_evidence_root() -> None:
    guard, r4, source = _case(evidence=("wake-unexpected.jsonl",))

    result = child._qualify(guard, r4, source)

    assert result["status"] == "BLOCKED"
    assert result["source_launch"] == "NOT_RUN"
    assert result["second_stage_launch_trap"] == "NOT_CALLED"
