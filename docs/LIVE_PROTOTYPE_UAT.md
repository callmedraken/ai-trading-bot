# Live Prototype — Native Windows UAT

## Purpose and current boundary

This checklist prepares separate native Windows evidence for the five-page
synthetic desktop: Dashboard, Research, Strategy, Live Session, and
Activity / Health. The desktop uses cached snapshots and an isolated synthetic
service. Start and Stop manage synthetic workers only. They do not arm, place,
cancel, or exit orders.

This source-only checkpoint does **not** grant **READY_FOR_HOST_UAT** or
**READY_FOR_BOUNDED_LIVE_TEST**; both labels remain **NOT GRANTED** until their
separate acceptance gates are met. Offscreen Qt tests and a synthetic desktop
run are not provider, broker, data-parity, or live-readiness evidence.

The later live-readiness rows remain blocked by missing genuine data parity,
verified full owned-exit capability, restart/recovery evidence, and a fresh
official-close provider observation. No real provider, credential, brokerage,
production, or FINAL_HOLDOUT operation belongs in this UAT. Do not run a paper
soak as a substitute.

## Source and dependency gate

Run from the exact accepted, integrated, terminal-certified source checkout.
Compare the HEAD and tree output with the exact identities from the independent
source review. Stop if either differs, or if any tracked, staged, or untracked
change is present.

~~~powershell
Set-Location F:\AI\worktrees\ai-trading-bot-live-prototype-current

git rev-parse --verify HEAD
git rev-parse --verify 'HEAD^{tree}'
git diff --quiet
if ($LASTEXITCODE -ne 0) { throw 'Tracked worktree changes are present' }
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { throw 'Index changes are present' }
if (git ls-files --others --exclude-standard) { throw 'Untracked files are present' }

$python = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
& $python -c 'import PySide6'
if ($LASTEXITCODE -ne 0) {
    throw 'GUI dependency is missing. Stop; use a separately approved isolated environment. Do not install into the shared editable environment.'
}
~~~

Use the accepted GitHub source-gate and canonical FULL result as recorded
evidence. GitHub owns the mapped FULL certification; do not rerun that same
profile locally. This checklist adds materially distinct native-host evidence.

Optional focused failure reproduction can use the launcher and application
acceptance tests below. It is not a prerequisite to repeat when the exact source
already has passing test evidence. The existing launcher tests cover effect-free
help, rejected live mode, and fresh/no-reuse state roots; the application tests
exercise GUI Start/Stop, close while workers are active, and delayed or failed
report reads.

~~~powershell
$runId = [guid]::NewGuid().ToString('N')
$testBase = "F:\AI\temp\pytest\prototype-uat-$runId"
$testTemp = "F:\AI\temp\pytest\prototype-uat-tmp-$runId"
if (Test-Path -LiteralPath $testBase) { throw 'Choose another fresh test root' }
if (Test-Path -LiteralPath $testTemp) { throw 'Choose another fresh temp root' }
New-Item -ItemType Directory -Force -Path $testTemp | Out-Null
$env:TEMP = $testTemp
$env:TMP = $testTemp
& $python -B -m pytest -q -p no:cacheprovider tests/live_prototype/test_launcher.py tests/live_prototype/test_application_acceptance.py --basetemp $testBase
if ($LASTEXITCODE -ne 0) { throw 'Focused prototype acceptance tests failed' }
~~~

## Effect-free launcher checks

Check help before creating a state root. It must return without creating state.
The CLI has no live mode; a --live attempt must fail before opening a window or
creating a state root.

~~~powershell
& $python scripts/run_live_prototype.py --help
if ($LASTEXITCODE -ne 0) { throw 'Effect-free help failed' }

& $python scripts/run_live_prototype.py --live
if ($LASTEXITCODE -eq 0) { throw 'Unexpectedly accepted a live option' }
~~~

## Fresh synthetic launch

Use a new absolute directory below F:\AI\temp for every launch. Never reuse,
delete, or repair an existing synthetic marker or state directory. Preserve
prior state for review.

~~~powershell
$runId = [guid]::NewGuid().ToString('N')
$stateRoot = "F:\AI\temp\live-prototype-uat-$runId"
if (Test-Path -LiteralPath $stateRoot) { throw 'Choose another fresh state root' }

& $python scripts/run_live_prototype.py --synthetic --state-root $stateRoot
~~~

The command runs until the window closes. A synthetic workspace marker is
created under the supplied state root. There is no default state creation from
imports, construction, or --help.

Optional report-reader smoke is permitted only with an explicitly selected,
existing synthetic comparison-bundle fixture under an external F: temp path.
Do not use production, provider, credential-bearing, or FINAL_HOLDOUT reports.
Give this launch its own fresh state root:

~~~powershell
$reportPath = Read-Host 'Absolute path to an existing synthetic comparison fixture'
if (-not [System.IO.Path]::IsPathRooted($reportPath)) { throw 'Report path must be absolute' }
if (-not $reportPath.StartsWith('F:\AI\temp\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Use an external F: temp fixture' }
if (-not (Test-Path -LiteralPath $reportPath)) { throw 'Synthetic fixture is missing' }
$runId = [guid]::NewGuid().ToString('N')
$reportStateRoot = "F:\AI\temp\live-prototype-report-uat-$runId"
if (Test-Path -LiteralPath $reportStateRoot) { throw 'Choose another fresh state root' }

& $python scripts/run_live_prototype.py --synthetic --state-root $reportStateRoot --comparison-report $reportPath
~~~

The report is read on a worker. A report selection is descriptive; it must not
change the active strategy binding or live readiness. Invalid input should
produce the fixed **Comparison report unavailable** message without exposing a
path, parser exception, or report contents.

## Native-host checklist

Record evidence for the exact source HEAD/tree, Windows version, display
resolution and DPI, run ID, and fresh state-root path. Use synthetic-only state
and values.

- At 1366x768, check all five pages, vertical scrolling, and no horizontal
  clipping. Repeat at 1920x1080 and the host's normal DPI scaling.
- Navigate by mouse and keyboard. Check tab order, visible focus, and that
  cached labels remain selectable and readable.
- On Live Session, use **Start synthetic workers** and confirm the UI remains
  explicitly synthetic and not ready for trading. Use **Stop synthetic
  workers** and wait for the stopped status.
- While synthetic work is active, close the window. Confirm it remains open
  during shutdown and exits only after workers are confirmed stopped. If a
  synthetic report fixture is loaded, also confirm shutdown waits for its reader.
- Open a synthetic comparison fixture from the report menu. Confirm research
  status may update while active strategy, binding digest, and live readiness
  remain unchanged. Try an invalid fixture and confirm the fixed unavailable
  display contains no raw path or content.
- After the process exits, confirm it returned control without an orphan
  prototype worker. Relaunch with a second fresh state root; preserve the first.
- Stop the application before any manual source update. Update only from the
  separately approved checkout, perform the reviewed checks or migration while
  stopped, and start the application manually afterward. The app never updates
  or hot-reloads its own source.

Capture concise screenshots and a checklist result for each row. Do not include
credentials, real account data, provider responses, private report contents, or
secrets in evidence. A synthetic pass records presentation and lifecycle
behavior only; it cannot satisfy the blocked data-parity, full-exit, recovery,
or provider-observation gates.