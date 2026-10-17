# D1R9-only fixed COM edge. Source tests never invoke it against Task Scheduler.
param([ValidateSet('Observe','Create','Run')][string]$Mode)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$attempted = $false
$taskName = 'AITradingBot-Arch134-D1R9-OneSessionSupervisor-v1'
$rootPath = 'F:\AI\worktrees\ai-trading-bot-production-paper-d1-arbitrary-time-supervisor'
$pythonPath = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
function Get-Sid([string]$Value) {
    if ($Value -match '^S-') { return [Security.Principal.SecurityIdentifier]::new($Value).Value }
    return [Security.Principal.NTAccount]::new($Value).Translate([Security.Principal.SecurityIdentifier]).Value
}
function Get-Service {
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    return $service
}
function Test-TaskNotFoundException([System.Exception]$Exception) {
    $current = $Exception
    for ($depth = 0; $depth -lt 32 -and $null -ne $current; $depth++) {
        if ($current.HResult -eq -2147024894) { return $true }
        $current = $current.InnerException
    }
    return $false
}
function Get-Observation {
    $service = Get-Service
    $folder = $service.GetFolder('\')
    try { $task = $folder.GetTask($taskName) }
    catch {
        $failure = $_.Exception
        if (Test-TaskNotFoundException $failure) { return @{status='ABSENT'} }
        throw 'scheduler unavailable'
    }
    $definition = $task.Definition
    if ($task.Path -cne ('\' + $taskName) -or $definition.Triggers.Count -ne 1 -or $definition.Actions.Count -ne 1) { throw 'task shape drift' }
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $trigger = $definition.Triggers.Item(1)
    $action = $definition.Actions.Item(1)
    $settings = $definition.Settings
    $principal = $definition.Principal
    if ($trigger.Type -ne 9 -or $action.Type -ne 0) { throw 'trigger/action drift' }
    if ((Get-Sid ([string]$principal.UserId)) -cne $sid -or $principal.LogonType -ne 3 -or $principal.RunLevel -ne 0) { throw 'principal drift' }
    if ((Get-Sid ([string]$trigger.UserId)) -cne $sid -or -not $trigger.Enabled -or -not [string]::IsNullOrEmpty([string]$trigger.StartBoundary) -or -not [string]::IsNullOrEmpty([string]$trigger.EndBoundary)) { throw 'trigger authority drift' }
    foreach ($duration in @([string]$trigger.Delay, [string]$trigger.Repetition.Interval, [string]$trigger.Repetition.Duration)) {
        if ($duration -cne '' -and $duration -cne 'PT0S') { throw 'trigger timing drift' }
    }
    if ($trigger.Repetition.StopAtDurationEnd) { throw 'trigger repetition drift' }
    $expectedArguments = '-I -B "' + $rootPath + '\scripts\run_arch134_d1r9.py" --resume'
    if ($action.Path -cne $pythonPath -or $action.Arguments -cne $expectedArguments -or $action.WorkingDirectory -cne $rootPath) { throw 'action drift' }
    if (-not $task.Enabled -or -not $settings.Enabled -or $settings.WakeToRun -or $settings.StartWhenAvailable -or -not $settings.AllowDemandStart -or $settings.MultipleInstances -ne 2) { throw 'settings drift' }
    if ($settings.RestartCount -ne 3 -or $settings.RestartInterval -cne 'PT1M' -or $settings.ExecutionTimeLimit -cne 'PT0S') { throw 'restart/lifetime drift' }
    if ($settings.RunOnlyIfIdle -or $settings.RunOnlyIfNetworkAvailable -or $settings.DisallowStartIfOnBatteries -or $settings.StopIfGoingOnBatteries -or -not $settings.Hidden -or $settings.AllowHardTerminate -or $settings.IdleSettings.StopOnIdleEnd -or $settings.IdleSettings.RestartOnIdle) { throw 'runtime settings drift' }
    return @{status='MATCH'}
}
try {
    if ($args.Count -ne 0 -or [string]::IsNullOrEmpty($Mode)) { throw 'arguments rejected' }
    if ($Mode -ceq 'Observe') {
        $result = Get-Observation
    } elseif ($Mode -ceq 'Create') {
        if ((Get-Observation).status -cne 'ABSENT') { throw 'existing task is never updated' }
        # Independent durable parent-intent validation plus O_EXCL native-entry
        # claim. This helper cannot create a task without parent authority and
        # cannot retry even after a partially acknowledged native registration.
        $claim = & $pythonPath -I -B ($rootPath + '\scripts\arch134_d1r9_bridge.py')
        if ($LASTEXITCODE -ne 0 -or $claim -cne 'CREATE') { throw 'durable scheduler claim rejected' }
        if ((Get-Observation).status -cne 'ABSENT') { throw 'task absence changed' }
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $service = Get-Service
        $folder = $service.GetFolder('\')
        $definition = $service.NewTask(0)
        $definition.RegistrationInfo.URI = '\' + $taskName
        $definition.Principal.UserId = $sid
        $definition.Principal.LogonType = 3
        $definition.Principal.RunLevel = 0
        $trigger = $definition.Triggers.Create(9)
        $trigger.UserId = $sid
        $trigger.Enabled = $true
        $action = $definition.Actions.Create(0)
        $action.Path = $pythonPath
        $action.Arguments = '-I -B "' + $rootPath + '\scripts\run_arch134_d1r9.py" --resume'
        $action.WorkingDirectory = $rootPath
        $settings = $definition.Settings
        $settings.Enabled = $true
        $settings.WakeToRun = $false
        $settings.StartWhenAvailable = $false
        $settings.AllowDemandStart = $true
        $settings.MultipleInstances = 2
        $settings.RestartCount = 3
        $settings.RestartInterval = 'PT1M'
        $settings.ExecutionTimeLimit = 'PT0S'
        $settings.RunOnlyIfIdle = $false
        $settings.RunOnlyIfNetworkAvailable = $false
        $settings.DisallowStartIfOnBatteries = $false
        $settings.StopIfGoingOnBatteries = $false
        $settings.Hidden = $true
        $settings.AllowHardTerminate = $false
        $settings.IdleSettings.StopOnIdleEnd = $false
        $settings.IdleSettings.RestartOnIdle = $false
        $attempted = $true
        # TASK_CREATE only; no update, deletion, password or elevation.
        $null = $folder.RegisterTaskDefinition($taskName, $definition, 2, $sid, $null, 3, $null)
        if ((Get-Observation).status -cne 'MATCH') { throw 'post-create mismatch' }
        $result = @{status='CREATED'}
    } else {
        if ((Get-Observation).status -cne 'MATCH') { throw 'task binding drift' }
        $service = Get-Service
        $task = $service.GetFolder('\').GetTask($taskName)
        if ($task.GetInstances(0).Count -ne 0) { throw 'task liveness uncertain' }
        $claim = & $pythonPath -I -B ($rootPath + '\scripts\arch134_d1r9_bridge.py')
        if ($LASTEXITCODE -ne 0 -or $claim -cne 'RUN') { throw 'durable demand-start claim rejected' }
        if ((Get-Observation).status -cne 'MATCH' -or $task.GetInstances(0).Count -ne 0) { throw 'final task admission drift' }
        $attempted = $true
        $running = $task.Run($null)
        if ($null -eq $running -or [string]::IsNullOrEmpty([string]$running.InstanceGuid)) { throw 'task entry indeterminate' }
        if ((Get-Observation).status -cne 'MATCH' -or $running.State -notin @(2,4)) { throw 'task entry acknowledgement unavailable' }
        $result = @{status='STARTED'}
    }
    [Console]::Out.WriteLine(($result | ConvertTo-Json -Compress))
    exit 0
} catch {
    [Console]::Out.WriteLine('{"status":"BLOCKED"}')
    exit 2
}
