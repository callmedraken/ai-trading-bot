# GUI-A18 — Research Lifecycle Boundary Map Validation

Status: local implementation validation; stop for ChatGPT exact GitHub source
review after the automatic GUI Source Gates and one Checkpoint Source Gates run
reach terminal success. This record does not declare source acceptance.

## Focused verification

The implementation uses the existing Python 3.14 environment and real PySide6
with `QT_QPA_PLATFORM=offscreen`. Each pytest invocation uses Python `-B`,
`-p no:cacheprovider`, and a fresh external basetemp under
`F:\AI\temp\pytest`.

The focused A18/A17/A16 GUI run passed **190 tests**, with zero failures,
errors, or skips:

```powershell
$A18Temp = Join-Path 'F:\AI\temp\pytest' ('gui-a18-focused-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force 'F:\AI\temp\pytest' | Out-Null
$env:QT_QPA_PLATFORM = 'offscreen'
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m pytest -q --tb=short -p no:cacheprovider --basetemp $A18Temp tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py tests/gui/test_gui_a16_research_candidate_lifecycle_composition.py
```

The run covers exact immutable rows, no acquisition/service access, parser and
verifier exclusion, presentation-only coverage and effects, no inference,
empty unavailable/attention output, real-Qt rendering at 920x620 and 1180x760,
no controls or external effects, repeated purity, frozen A16/A17 digests and
blobs, A17 predecessor-drift rejection, and fail-closed inventory assertions.

The retained A17 page/audit and A16 composition checks also pass, including the
five resolver-site and current inventory assertions updated for the additive
A18 overlay. No complete GUI suite or FULL/ROBINHOOD/LEGACY/EXHAUSTIVE
certification was run locally.

## Static checks and inventory

Both non-mutating Ruff phases are required over the changed Python paths:

```powershell
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m ruff check --no-cache scripts/checkpoint_runner.py src/trading_bot/gui/research_candidate_lifecycle_boundary_map.py src/trading_bot/gui/research_candidate_lifecycle_page.py tests/gui/test_gui_a16_research_candidate_lifecycle_composition.py tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py tests/scripts/certification_runner/test_profiles.py
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m ruff format --check --no-cache scripts/checkpoint_runner.py src/trading_bot/gui/research_candidate_lifecycle_boundary_map.py src/trading_bot/gui/research_candidate_lifecycle_page.py tests/gui/test_gui_a16_research_candidate_lifecycle_composition.py tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py tests/scripts/certification_runner/test_profiles.py
git diff --check
```

The expected final inventory is ACTIVE 64, FULL 179, ROBINHOOD 98, LEGACY 222,
EXHAUSTIVE 401, and `tests/gui` 51. The A16/A17 overlay digests remain
`887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f` and
`dc11d4c1e6099c1eec3346cafb85220e42f495e472d220cf81ac741ccff524c3`; the A18
overlay digest is
`ac7096dc95df837940573ce646cd2143fc4c1d901d8e10fbdc7cb9d69c218328`.

## Publication and CI stop

After focused PASS and static PASS, stage only the exact implementation, test,
and two A18 documentation paths. Verify the staged names and cached diff check,
make one normal commit, and ordinary-push only the isolated A18 branch. The
existing `feature/gui-*` workflow admission is reused; no workflow edit or
manual GUI dispatch is allowed.

Require one automatic GUI Source Gates run on the exact pushed HEAD, attempt 1,
terminal SUCCESS with real PySide6, and then one Checkpoint Source Gates
workflow-dispatch run on the same exact HEAD. The checkpoint route remains the
unmapped broad-shard route: source-static, four broad shards each below 300
seconds, and terminal source-gates SUCCESS. Any failure stops for the smallest
contract-preserving correction and replacement focused verification.

The optional final local GUI command for the user is:

```powershell
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -m pytest -p no:cacheprovider tests/gui
```

No status/handoff acceptance closeout is included; ChatGPT owns exact GitHub
review, source acceptance, and the later bounded docs closeout.
