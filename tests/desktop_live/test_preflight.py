import json
from pathlib import Path

import pytest

import trading_bot.desktop_live.preflight as preflight

HEAD = "7ff86d06a99bcdf349d5e20846d139a554d8be46"
TREE = "095c51cedc1c656616123c3acf88148b16b71aa2"


def _write_report(
    root: Path,
    name: str,
    *,
    status: str = "PASS",
    source_head: str = HEAD,
    source_tree: str = TREE,
    mutation_call_count: int = 0,
    order_review_count: int = 0,
    order_preview_count: int = 0,
    order_placement_count: int = 0,
    order_cancel_count: int = 0,
    p5_financial_state_mutation_count: int = 0,
    production_state_unchanged: bool = True,
) -> Path:
    report = root / name / "report.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "status": status,
                "source_head": source_head,
                "source_tree": source_tree,
                "result": {
                    "mutation_call_count": mutation_call_count,
                    "order_review_count": order_review_count,
                    "order_preview_count": order_preview_count,
                    "order_placement_count": order_placement_count,
                    "order_cancel_count": order_cancel_count,
                    "p5_financial_state_mutation_count": (
                        p5_financial_state_mutation_count
                    ),
                    "production_state_unchanged": production_state_unchanged,
                    "observation": {
                        "account_fingerprint": "a" * 64,
                        "position_count": 0,
                        "order_count": 0,
                        "local_expected_broker_effect_count": 0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return report


def test_p5b_evidence_discovery_blocks_zero_matches(tmp_path):
    with pytest.raises(preflight.LivePreflightError, match="MATCH_COUNT"):
        preflight.load_p5b_baseline_evidence(
            tmp_path, expected_source_head=HEAD, expected_source_tree=TREE
        )


def test_p5b_evidence_discovery_accepts_one_exact_match(tmp_path):
    report = _write_report(tmp_path, "preflight-one")

    evidence = preflight.load_p5b_baseline_evidence(
        tmp_path, expected_source_head=HEAD, expected_source_tree=TREE
    )

    assert evidence.source_head == HEAD
    assert evidence.source_tree == TREE
    assert evidence.account_fingerprint == "a" * 64
    assert report.is_file()


def test_p5b_evidence_discovery_blocks_multiple_exact_matches(tmp_path):
    _write_report(tmp_path, "preflight-one")
    _write_report(tmp_path, "preflight-two")

    with pytest.raises(preflight.LivePreflightError, match="MATCH_COUNT"):
        preflight.load_p5b_baseline_evidence(
            tmp_path, expected_source_head=HEAD, expected_source_tree=TREE
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "BLOCKED"},
        {"source_head": "b" * 40},
        {"source_tree": "c" * 40},
        {"mutation_call_count": 1},
        {"order_review_count": 1},
        {"order_preview_count": 1},
        {"order_placement_count": 1},
        {"order_cancel_count": 1},
        {"p5_financial_state_mutation_count": 1},
        {"production_state_unchanged": False},
    ],
)
def test_p5b_evidence_discovery_filters_nonmatching_reports(tmp_path, changes):
    _write_report(tmp_path, "preflight-rejected", **changes)
    _write_report(tmp_path, "preflight-accepted")

    evidence = preflight.load_p5b_baseline_evidence(
        tmp_path, expected_source_head=HEAD, expected_source_tree=TREE
    )

    assert evidence.account_fingerprint == "a" * 64
