# Closed local COM transport. Never invoke against the real machine in source CI.
param([ValidateSet('Principal','Observe','Create')][string]$Mode)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$attempted = $false
function Get-Identity {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    return @{name=[string]$identity.Name;sid=[string]$identity.User.Value}
}
function Get-TaskObservation {
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')
    try { $task = $folder.GetTask('AITradingBot-Arch134-D1R6-OvernightWake-v1') }
    catch {
        $failure = $_.Exception
        while ($null -ne $failure.InnerException) { $failure = $failure.InnerException }
        if ($failure.HResult -eq -2147024894) { return @{status='ABSENT'} }
        throw 'observation unavailable'
    }
    $definition = $task.Definition
    if ($task.Path -cne '\AITradingBot-Arch134-D1R6-OvernightWake-v1' -or $definition.Triggers.Count -ne 1 -or $definition.Actions.Count -ne 1) { throw 'task drift' }
    $trigger = $definition.Triggers.Item(1); $action = $definition.Actions.Item(1)
    $settings = $definition.Settings; $principal = $definition.Principal
    if ($trigger.Type -ne 1 -or $action.Type -ne 0) { throw 'task type drift' }
    $projected = @{
        task_path=[string]$task.Path;trigger_count=[int]$definition.Triggers.Count;trigger_type=[int]$trigger.Type
        start_boundary=[string]$trigger.StartBoundary;end_boundary=[string]$trigger.EndBoundary
        trigger_enabled=[bool]$trigger.Enabled;repetition_interval=[string]$trigger.Repetition.Interval
        repetition_duration=[string]$trigger.Repetition.Duration;repetition_stop=[bool]$trigger.Repetition.StopAtDurationEnd
        random_delay=[string]$trigger.RandomDelay;principal_sid=[string]$principal.UserId
        logon_type=[int]$principal.LogonType;run_level=[int]$principal.RunLevel
        action_count=[int]$definition.Actions.Count;action_type=[int]$action.Type
        command=[string]$action.Path;arguments=[string]$action.Arguments;working_directory=[string]$action.WorkingDirectory
        enabled=([bool]$task.Enabled -and [bool]$settings.Enabled);wake_to_run=[bool]$settings.WakeToRun
        start_when_available=[bool]$settings.StartWhenAvailable;restart_count=[int]$settings.RestartCount
        restart_interval=[string]$settings.RestartInterval;allow_demand_start=[bool]$settings.AllowDemandStart
        run_only_if_idle=[bool]$settings.RunOnlyIfIdle;run_only_if_network_available=[bool]$settings.RunOnlyIfNetworkAvailable
        disallow_start_if_on_batteries=[bool]$settings.DisallowStartIfOnBatteries;stop_if_going_on_batteries=[bool]$settings.StopIfGoingOnBatteries
        hidden=[bool]$settings.Hidden;multiple_instances=[int]$settings.MultipleInstances
        execution_time_limit=[string]$settings.ExecutionTimeLimit;allow_hard_terminate=[bool]$settings.AllowHardTerminate
        idle_stop=[bool]$settings.IdleSettings.StopOnIdleEnd;idle_restart=[bool]$settings.IdleSettings.RestartOnIdle
    }
    # COM may spell an absent duration as zero duration. Both have zero authority.
    foreach ($key in @('random_delay','repetition_interval','repetition_duration','restart_interval')) {
        if ($projected[$key] -ceq 'PT0S') { $projected[$key] = '' }
    }
    return @{status='PRESENT';task=$projected;state=[int]$task.State;last_result=([long]$task.LastTaskResult -band 4294967295)}
}
try {
    if ($args.Count -ne 0 -or [string]::IsNullOrEmpty($Mode)) { throw 'arguments forbidden' }
    [Console]::InputEncoding = [Text.UTF8Encoding]::new($false, $true)
    $builder = [Text.StringBuilder]::new()
    while ($true) {
        $character = [Console]::In.Read()
        if ($character -eq -1 -or $character -eq 10) { break }
        if ($builder.Length -ge 2048) { throw 'input oversized' }
        $null = $builder.Append([char]$character)
    }
    if ($character -ne 10 -or [Console]::In.Read() -ne -1) { throw 'input invalid' }
    $line = $builder.ToString()
    if ($Mode -ceq 'Principal') {
        if ($line -cne '{}') { throw 'input invalid' }
        $result = Get-Identity
    } elseif ($Mode -ceq 'Observe') {
        if ($line -cne '{}') { throw 'input invalid' }
        $result = Get-TaskObservation
    } else {
        # Exact canonical private request, no caller command/XML/task/password.
        $pattern = '^\{"end_boundary":"(?<end>[0-9T:+.-]+)","principal_name":"(?<name>[^"\x00-\x1f]+)","principal_sid":"(?<sid>S-1-5-21-(?:[0-9]{1,10}-){3}[0-9]{1,10})","start_boundary":"(?<start>[0-9T:+.-]+)"\}$'
        if ($line -cnotmatch $pattern) { throw 'request invalid' }
        $startText = $Matches.start; $endText = $Matches.end
        $request = $line | ConvertFrom-Json
        $identity = Get-Identity
        if ($request.principal_name -cne $identity.name -or $request.principal_sid -cne $identity.sid) { throw 'principal drift' }
        $start = [DateTimeOffset]::Parse($startText, [Globalization.CultureInfo]::InvariantCulture)
        $end = [DateTimeOffset]::Parse($endText, [Globalization.CultureInfo]::InvariantCulture)
        $now = [DateTimeOffset]::UtcNow
        if ($now -ge $start -or ($start - $now).TotalHours -gt 18 -or ($end - $start).TotalMinutes -ne 15) { throw 'window stale' }
        $first = Get-TaskObservation; $second = Get-TaskObservation
        if ($first.status -cne 'ABSENT' -or $second.status -cne 'ABSENT') { throw 'task consumed' }
        $service = New-Object -ComObject 'Schedule.Service'
        $service.Connect(); $folder = $service.GetFolder('\'); $definition = $service.NewTask(0)
        $definition.RegistrationInfo.URI = '\AITradingBot-Arch134-D1R6-OvernightWake-v1'
        $definition.Principal.UserId = $identity.sid
        $definition.Principal.LogonType = 3; $definition.Principal.RunLevel = 0
        $trigger = $definition.Triggers.Create(1)
        $trigger.StartBoundary = $startText; $trigger.EndBoundary = $endText; $trigger.Enabled = $true
        $action = $definition.Actions.Create(0)
        $action.Path = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
        $action.Arguments = '-NoProfile -NonInteractive -File "F:\AI\worktrees\ai-trading-bot-production-paper-overnight-wake-arming\scripts\arch134_d1r6_task_launcher.ps1"'
        $action.WorkingDirectory = 'F:\AI\worktrees\ai-trading-bot-production-paper-overnight-wake-arming'
        $settings = $definition.Settings
        $settings.Enabled = $true; $settings.WakeToRun = $true; $settings.StartWhenAvailable = $false
        $settings.RestartCount = 0; $settings.AllowDemandStart = $false; $settings.MultipleInstances = 2
        $settings.RunOnlyIfIdle = $false; $settings.RunOnlyIfNetworkAvailable = $false
        $settings.DisallowStartIfOnBatteries = $false; $settings.StopIfGoingOnBatteries = $false
        $settings.Hidden = $false; $settings.ExecutionTimeLimit = 'PT20M'; $settings.AllowHardTerminate = $true
        $settings.IdleSettings.StopOnIdleEnd = $false; $settings.IdleSettings.RestartOnIdle = $false
        $identityAgain = Get-Identity
        if ($identityAgain.name -cne $identity.name -or $identityAgain.sid -cne $identity.sid -or [DateTimeOffset]::UtcNow -ge $start) { throw 'final admission drift' }
        $attempted = $true
        # TASK_CREATE=2 only; InteractiveToken=3, no password or elevated run level.
        $null = $folder.RegisterTaskDefinition('AITradingBot-Arch134-D1R6-OvernightWake-v1', $definition, 2, $identity.sid, $null, 3, $null)
        $result = @{disposition='CALL_RETURNED';registration_attempts=1}
    }
    [Console]::Out.WriteLine(($result | ConvertTo-Json -Depth 8 -Compress))
    exit 0
} catch {
    $disposition = if ($attempted) { 'INDETERMINATE' } else { 'NOT_CALLED' }
    [Console]::Out.WriteLine((@{disposition=$disposition;registration_attempts=([int]$attempted)} | ConvertTo-Json -Compress))
    exit 2
}
