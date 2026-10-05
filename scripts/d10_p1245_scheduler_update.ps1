# Fixed TASK_UPDATE transport. Password arrives only over the operator's private
# anonymous pipe after interactive console acquisition. No credential argv/env,
# persistence, stdout/stderr, retry, rollback, task creation, or Run exists.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$callAttempted = $false
$disposition = 'NOT_CALLED'
$exitCode = 1
$request = $null
$password = $null
try {
    if ($args.Count -ne 0) { throw 'arguments forbidden' }
    [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false, $true)
    $inputRecord = [Console]::In.ReadLine()
    if ($null -eq $inputRecord -or $inputRecord.Length -gt 16384 -or [Console]::In.Read() -ne -1) {
        throw 'private transport invalid'
    }
    $request = $inputRecord | ConvertFrom-Json
    $inputRecord = $null
    $names = @($request.PSObject.Properties.Name | Sort-Object)
    if (($names -join ',') -cne 'activation_utc,password' -or
        $request.activation_utc -isnot [string] -or $request.password -isnot [string] -or
        [string]::IsNullOrEmpty($request.password)) { throw 'private transport invalid' }
    # Both boundaries are independently derived from the single operator instant.
    $activation = [DateTimeOffset]::ParseExact(
        $request.activation_utc, "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal)
    if ($activation.Offset -ne [TimeSpan]::Zero -or
        [DateTimeOffset]::UtcNow -lt $activation -or
        [DateTimeOffset]::UtcNow -ge $activation.AddDays(7)) { throw 'window invalid' }
    $password = $request.password
    $request.password = $null
    $timezone = [TimeZoneInfo]::FindSystemTimeZoneById('Pacific Standard Time')
    if ([TimeZoneInfo]::Local.Id -cne 'Pacific Standard Time') { throw 'timezone drift' }
    $local = [TimeZoneInfo]::ConvertTime($activation, $timezone)
    $candidates = @()
    foreach ($day in 0..2) {
        $wall = [DateTime]::SpecifyKind($local.Date.AddDays($day).AddHours(1).AddMinutes(30), [DateTimeKind]::Unspecified)
        if ($timezone.IsInvalidTime($wall)) { continue }
        $offsets = if ($timezone.IsAmbiguousTime($wall)) { $timezone.GetAmbiguousTimeOffsets($wall) } else { @($timezone.GetUtcOffset($wall)) }
        foreach ($offset in $offsets) {
            $candidate = [DateTimeOffset]::new($wall, $offset)
            if ($candidate -gt $activation) { $candidates += $candidate }
        }
    }
    $start = $candidates | Sort-Object UtcTicks | Select-Object -First 1
    if ($null -eq $start -or $start -ge $activation.AddDays(7)) { throw 'start invalid' }
    $end = [TimeZoneInfo]::ConvertTime($activation.AddDays(7), $timezone)
    . (Join-Path $PSScriptRoot 'd10_p1245_scheduler_observe.ps1')
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')
    $first = Read-FixedTask $folder
    $second = Read-FixedTask $folder
    if (($first | ConvertTo-Json -Compress) -cne ($second | ConvertTo-Json -Compress)) { throw 'predecessor unstable' }
    $expected = [ordered]@{
        task_path = '\AITradingBot-PD4-UnattendedPaper-v1'
        principal_sid = 'S-1-5-21-1397534616-3988210162-180023805-1009'
        logon_type = 1; run_level = 0; action_count = 1; action_type = 0
        action_path = 'F:\AITradingBot\runtime\python.exe'
        action_arguments = '-I "F:\AI\worktrees\ai-trading-bot-personal-desktop\scripts\run_personal_desktop_unattended_capture_warmup.py"'
        action_working_directory = 'F:\AI\worktrees\ai-trading-bot-personal-desktop'
        trigger_count = 1; trigger_type = 2; trigger_enabled = $true
        trigger_start_boundary = '2026-09-15T01:30:00'; trigger_end_boundary = ''
        host_timezone = 'Pacific Standard Time'; trigger_days_interval = 1
        trigger_random_delay = ''; repetition_interval = ''; repetition_duration = ''
        repetition_stop_at_duration_end = $false; multiple_instances = 2
        disallow_start_if_on_batteries = $false; stop_if_going_on_batteries = $false
        allow_demand_start = $true; start_when_available = $true
        run_only_if_network_available = $false; run_only_if_idle = $false
        enabled = $true; hidden = $false; wake_to_run = $true
        execution_time_limit = 'PT1H'; priority = 7; restart_count = 0; restart_interval = ''
    }
    foreach ($key in $expected.Keys) {
        if ($first[$key].GetType() -ne $expected[$key].GetType() -or $first[$key] -cne $expected[$key]) {
            throw 'predecessor drift'
        }
    }
    # GetTask must already succeed. TASK_UPDATE=4 excludes TASK_CREATE=2.
    $definition = $null
    # The third projection and the edited definition come from the same GetTask.
    $third = Read-FixedTask $folder ([ref]$definition)
    if (($second | ConvertTo-Json -Compress) -cne ($third | ConvertTo-Json -Compress)) { throw 'predecessor drift' }
    $definition.Principal.UserId = 'S-1-5-21-1397534616-3988210162-180023805-1009'
    $definition.Principal.LogonType = 1
    $definition.Principal.RunLevel = 0
    $action = $definition.Actions.Item(1)
    $action.Path = 'F:\AITradingBot\runtime\python.exe'
    $action.Arguments = '-I -S -B -X pycache_prefix=F:\AITradingBot\D10\no-pycache F:\AITradingBot\D10\launch-guard.py'
    $action.WorkingDirectory = 'F:\AITradingBot\D10'
    $trigger = $definition.Triggers.Item(1)
    $trigger.StartBoundary = $start.ToString('yyyy-MM-ddTHH:mm:sszzz', [Globalization.CultureInfo]::InvariantCulture)
    $endFormat = if (($end.Ticks % 10000000) -eq 0) { 'yyyy-MM-ddTHH:mm:sszzz' } else { 'yyyy-MM-ddTHH:mm:ss.ffffffzzz' }
    $trigger.EndBoundary = $end.ToString($endFormat, [Globalization.CultureInfo]::InvariantCulture)
    if ([DateTimeOffset]::UtcNow -ge $activation.AddDays(7)) { throw 'window expired' }
    $callAttempted = $true
    $null = $folder.RegisterTaskDefinition('AITradingBot-PD4-UnattendedPaper-v1', $definition, 4,
        'S-1-5-21-1397534616-3988210162-180023805-1009', $password, 1, $null)
    $disposition = 'CALL_RETURNED'
    $exitCode = 0
} catch {
    if ($callAttempted) { $disposition = 'INDETERMINATE'; $exitCode = 2 }
} finally {
    $password = $null
    $request = $null
    $inputRecord = $null
}
[Console]::Out.WriteLine(([ordered]@{schema='p1245-task-scheduler-update/v1'; disposition=$disposition} | ConvertTo-Json -Compress))
exit $exitCode
