# Architecture 134-F1R1-C2 external qualification â€” operator plan only

Do not execute during C1 source implementation. ChatGPT must first review/accept
the exact C1 source and the C2 operator boundary. This exercise proves only
process isolation; no result grants production or successor-soak authority.
Use ordinary independent PowerShell windows. Do not reboot Windows, kill Python,
use Task Scheduler/services, or access production/F1 evidence.

## Phase 1 â€” prepare

At C2 review, obtain the exact accepted develop HEAD/TREE. The following block
reads them interactively to avoid embedding a self-referential future commit ID.
It fetches develop and creates a NEW disposable source worktree at that exact
accepted identity. Any mismatch is STOP; preserve existing worktrees/artifacts.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'F:\AI\ai-trading-bot'
    $AcceptedHead = Read-Host 'Exact accepted develop HEAD supplied by C2 review'
    $AcceptedTree = Read-Host 'Exact accepted develop TREE supplied by C2 review'
    git fetch origin develop
    if ($LASTEXITCODE -ne 0) { throw 'STOP: fetch failed' }
    $RemoteHead = (git rev-parse origin/develop).Trim()
    $RemoteTree = (git rev-parse 'origin/develop^{tree}').Trim()
    if ($RemoteHead -cne $AcceptedHead -or $RemoteTree -cne $AcceptedTree) {
        throw 'STOP: accepted source mismatch'
    }
    $Source = 'F:\AI\worktrees\ai-trading-bot-f1r1-c2-qualification-source'
    if (Test-Path -LiteralPath $Source) { throw 'STOP: source worktree already exists' }
    git worktree add --detach $Source $AcceptedHead
    if ($LASTEXITCODE -ne 0) { throw 'STOP: worktree creation failed' }
    Set-Location $Source
    .\ops.ps1 status
    if ($LASTEXITCODE -ne 0) { throw 'STOP: source status failed' }
    $Python = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
    $PreparedText = & $Python -I -S -B .\scripts\run_arch134_f1r1_qualification.py prepare
    if ($LASTEXITCODE -ne 0) { throw 'STOP: prepare rejected; preserve artifacts' }
    $Prepared = $PreparedText | ConvertFrom-Json
    if ($Prepared.QUALIFICATION_STATUS -cne 'READY_FOR_F1R1_C2_EXTERNAL_QUALIFICATION') {
        throw 'STOP: qualification not ready'
    }
    if (@($Prepared.PROTECTED_EFFECT_COUNTERS.PSObject.Properties | Where-Object Value -ne 0).Count) {
        throw 'STOP: protected counter nonzero'
    }
    if ($Prepared.QUALIFICATION_INTERPRETER.executable -ine 'C:\Program Files\Python314\python.exe') {
        throw 'STOP: observed interpreter differs from this reviewed host command'
    }
    $Prepared | ConvertTo-Json -Depth 10
}
```

This host uses the observed global C:\Program Files\Python314\python.exe image.
C2 review revalidates its exact path/version/hash. Never execute a path taken
unvalidated from a mutable manifest; a different observed interpreter is STOP.

C2 review must independently establish source-gate acceptance before this block;
ops status itself is not source acceptance. prepare creates only the disposable
fixed-root fixture. It never installs Architecture-133. Existing partial or
consumed state stops the exercise; never delete it to manufacture a new attempt.

## Phase 2 â€” start in independent PowerShell

Open an ordinary PowerShell window outside Codex/IDE terminals. Run:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $Fixture = 'F:\AI\temp\qualification\arch134-f1r1-host-isolation\fixture'
    & 'C:\Program Files\Python314\python.exe' -I -S -B "$Fixture\run_arch134_f1r1_qualification.py" run
    if ($LASTEXITCODE -ne 0) { throw 'STOP: qualification host failed; preserve evidence' }
}
```

Leave this window and process running after SAFE_WAITING appears. It executes
only the prepared fixture and standard library. Never start a second host.

## Phase 3 â€” baseline observation in a second independent PowerShell

Keep this second window open through phases 4â€“7. Define the bounded read-only
helper and retain the baseline in that same independent PowerShell:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $script:Fixture = 'F:\AI\temp\qualification\arch134-f1r1-host-isolation\fixture'
    $script:QualificationPython = 'C:\Program Files\Python314\python.exe'
    function global:Read-Qualification {
        $Text = & $script:QualificationPython -I -S -B "$script:Fixture\run_arch134_f1r1_qualification.py" verify
        if ($LASTEXITCODE -ne 0) { throw 'STOP: qualification replay rejected' }
        $Value = $Text | ConvertFrom-Json
        if (@($Value.PROTECTED_EFFECT_COUNTERS.PSObject.Properties | Where-Object Value -ne 0).Count) {
            throw 'STOP: protected effects nonzero'
        }
        return $Value
    }
    $script:Baseline = Read-Qualification
    if ($Baseline.QUALIFICATION_STATUS -cne 'HOST_QUALIFICATION_RUNNING_SAFE' -or
        $Baseline.PROCESS_STATE -cne 'ALIVE_EXACT' -or
        $Baseline.LEASE_STATE -cne 'HELD' -or $Baseline.HOST_LEASE_AUTHORITIES -ne 1) {
        throw 'STOP: exact waiting process and one lease required'
    }
    $Baseline | ConvertTo-Json -Depth 10
}
```

verify performs canonical journal replay; record the qualification runtime ID,
process PID+creation identity, interpreter identity and one lease authority.
A file or PID alone is insufficient. UNPROVEN/transition/failure is not PASS.

## Phase 4 â€” development disturbance

While the independent host stays running, launch/use Codex normally. Perform
ordinary harmless development operations in separate disposable development
resources: git status, git fetch, create/use a feature worktree, run focused
harmless tests, edit unrelated disposable files, and remove that disposable
worktree after confirming it is clean. Use F:\AI\worktrees for any worktree.
Never modify the qualification fixture or preserved production/F1 evidence.
C2 review scopes the disposable development worktree separately; this document
never authorizes force removal, dirty-worktree cleanup or production operations.

Use this bounded disturbance block from the second independent PowerShell;
leave Codex open for ordinary development use during it. It creates exactly one
new disposable feature worktree, edits/removes one new scratch file, runs one
harmless source-preservation test, and removes only that clean worktree. Any
failure preserves the worktree and is STOP; no force cleanup or retry exists.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $Source = 'F:\AI\worktrees\ai-trading-bot-f1r1-c2-qualification-source'
    $Disturbance = 'F:\AI\worktrees\ai-trading-bot-f1r1-c2-development-disturbance'
    if (Test-Path -LiteralPath $Disturbance) { throw 'STOP: disturbance worktree exists' }
    git -C $Source status --short
    if ($LASTEXITCODE -ne 0) { throw 'STOP: development status failed' }
    git -C $Source fetch origin develop
    if ($LASTEXITCODE -ne 0) { throw 'STOP: development fetch failed' }
    $Base = (git -C $Source rev-parse HEAD).Trim()
    git -C $Source worktree add -b feature/robinhood-f1r1-c2-development-disturbance $Disturbance $Base
    if ($LASTEXITCODE -ne 0) { throw 'STOP: disturbance creation failed' }
    Set-Location $Disturbance
    $Scratch = Join-Path $Disturbance 'c2-disposable-edit.txt'
    if (Test-Path -LiteralPath $Scratch) { throw 'STOP: scratch file exists' }
    Set-Content -LiteralPath $Scratch -Value 'Harmless qualification development edit' -Encoding UTF8
    Get-Content -LiteralPath $Scratch
    Remove-Item -LiteralPath $Scratch
    $BaseTemp = "F:\AI\temp\pytest\f1r1-c2-development-$([guid]::NewGuid().ToString('N'))"
    & 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -m pytest tests/review_paper/test_arch134_f1r1_c1_qualification_operator.py -k production_runtime_contracts_and_a_b_blobs_unchanged -q --basetemp=$BaseTemp -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw 'STOP: harmless development test failed' }
    $Dirty = git status --porcelain
    if ($LASTEXITCODE -ne 0 -or -not [string]::IsNullOrWhiteSpace(($Dirty -join "`n"))) {
        throw 'STOP: disturbance worktree is not clean'
    }
    Set-Location $Source
    git worktree remove $Disturbance
    if ($LASTEXITCODE -ne 0) { throw 'STOP: clean worktree removal failed' }
    $script:DevelopmentDisturbanceCompleted = $true
    'DEVELOPMENT_DISTURBANCE_COMPLETED=YES'
}
```

In the second independent PowerShell, capture the read-only observation:

```powershell
& {
    if ($script:DevelopmentDisturbanceCompleted -ne $true) { throw 'STOP: disturbance not completed' }
    $script:AfterDevelopment = Read-Qualification
    if ($AfterDevelopment.QUALIFICATION_STATUS -cne 'HOST_QUALIFICATION_RUNNING_SAFE' -or
        $AfterDevelopment.RUNTIME_ID -cne $Baseline.RUNTIME_ID -or
        ($AfterDevelopment.PROCESS_IDENTITY | ConvertTo-Json -Compress) -cne
        ($Baseline.PROCESS_IDENTITY | ConvertTo-Json -Compress) -or
        $AfterDevelopment.LEASE_STATE -cne 'HELD' -or
        $AfterDevelopment.HOST_LEASE_AUTHORITIES -ne 1) { throw 'STOP: continuity failed' }
    $AfterDevelopment | ConvertTo-Json -Depth 10
}
```

## Phase 5 â€” Codex restart

Keep both independent PowerShell windows open and the qualification process
running. Close/reopen or restart Codex using the normal user mechanism. Do not
reboot Windows, kill Python or touch scheduler/service control.

After Codex returns, in the second independent PowerShell:

```powershell
& {
    $script:AfterCodex = Read-Qualification
    if ($AfterCodex.QUALIFICATION_STATUS -cne 'HOST_QUALIFICATION_RUNNING_SAFE' -or
        $AfterCodex.RUNTIME_ID -cne $Baseline.RUNTIME_ID -or
        ($AfterCodex.PROCESS_IDENTITY | ConvertTo-Json -Compress) -cne
        ($Baseline.PROCESS_IDENTITY | ConvertTo-Json -Compress) -or
        $AfterCodex.LEASE_STATE -cne 'HELD' -or $AfterCodex.HOST_LEASE_AUTHORITIES -ne 1) {
        throw 'STOP: Codex-restart continuity failed'
    }
    $AfterCodex | ConvertTo-Json -Depth 10
}
```

## Phase 6 â€” controlled stop

From the second independent PowerShell:

```powershell
& {
    & $QualificationPython -I -S -B "$Fixture\run_arch134_f1r1_qualification.py" stop
    if ($LASTEXITCODE -ne 0) { throw 'STOP: cooperative signal rejected' }
    $script:Final = $null
    for ($i = 0; $i -lt 50; $i++) {
        $StatusText = & $QualificationPython -I -S -B "$Fixture\run_arch134_f1r1_qualification.py" status
        if ($LASTEXITCODE -ne 0) { throw 'STOP: status rejected' }
        $Observed = $StatusText | ConvertFrom-Json
        if ($Observed.QUALIFICATION_STATUS -ceq 'HOST_QUALIFICATION_COMPLETED' -and
            $Observed.PROCESS_STATE -ceq 'GONE') { $script:Final = Read-Qualification; break }
        Start-Sleep -Milliseconds 100
    }
    if ($null -eq $Final -or $Final.LAST_LIFECYCLE_EVENT -cne 'NORMAL_RETURN' -or
        $Final.LEASE_STATE -cne 'FREE' -or $Final.HOST_LEASE_AUTHORITIES -ne 1) {
        throw 'STOP: normal terminal replay and released lease not proven'
    }
    $Final | ConvertTo-Json -Depth 10
}
```

NORMAL_RETURN is durably committed before release; final result evidence binds
that terminal journal. Confirm the first independent window returned normally.
If disappearance is abrupt, preserve evidence and STOP. Never relaunch/retry,
repair, truncate, overwrite, delete stale lock files, or reuse this consumed root.

## Phase 7 â€” classification

Only after all preceding phases were actually performed, in the same second
PowerShell with all observations retained:

```powershell
& {
    if ($null -eq $Baseline -or $null -eq $AfterDevelopment -or
        $null -eq $AfterCodex -or $null -eq $Final) { throw 'STOP: missing phase evidence' }
    foreach ($Value in @($AfterDevelopment, $AfterCodex, $Final)) {
        if ($Value.RUNTIME_ID -cne $Baseline.RUNTIME_ID -or
            ($Value.PROCESS_IDENTITY | ConvertTo-Json -Compress) -cne
            ($Baseline.PROCESS_IDENTITY | ConvertTo-Json -Compress) -or
            $Value.HOST_LEASE_AUTHORITIES -ne 1 -or
            @($Value.PROTECTED_EFFECT_COUNTERS.PSObject.Properties | Where-Object Value -ne 0).Count) {
            throw 'STOP: qualification continuity/effects mismatch'
        }
    }
    if ($AfterDevelopment.QUALIFICATION_STATUS -cne 'HOST_QUALIFICATION_RUNNING_SAFE' -or
        $AfterCodex.QUALIFICATION_STATUS -cne 'HOST_QUALIFICATION_RUNNING_SAFE' -or
        $Final.QUALIFICATION_STATUS -cne 'HOST_QUALIFICATION_COMPLETED' -or
        $Final.LAST_LIFECYCLE_EVENT -cne 'NORMAL_RETURN') { throw 'STOP: terminal phase mismatch' }
    'RUNTIME_ID_UNCHANGED=YES'
    'SURVIVED_DEVELOPMENT_ACTIVITY=YES'
    'SURVIVED_CODEX_RESTART=YES'
    'DUPLICATE_HOST=NO'
    'LIFECYCLE_REPLAY_VALID=YES'
    'TERMINAL_NORMAL_RETURN=YES'
    'PROTECTED_EFFECTS=ZERO'
    'F1R1_EXTERNAL_HOST_QUALIFICATION=PASS'
}
```

Return all four observation JSON summaries, original host terminal output and
classification lines to ChatGPT. A failure preserves all evidence and never
auto-retries. Even PASS grants no successor-soak or production admission authority.
