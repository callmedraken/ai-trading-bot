# Fixed incident COM transport; source tests never execute these statements.
param([ValidateSet('Observe','Delete')][string]$Mode)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$attempted = $false
function Get-Identity {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    return @{name=[string]$identity.Name;sid=[string]$identity.User.Value}
}
function Convert-ObservedBoundary([string]$Value) {
    # Reject offset-less values before parsing; never assume the host time zone.
    if ($Value -cnotmatch '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,7})?(?:Z|[+-][0-9]{2}:[0-9]{2})$') { throw 'boundary unavailable' }
    $instant = [DateTimeOffset]::Parse($Value, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None)
    # Do not silently truncate fractional seconds to a different instant.
    if (($instant.Ticks % [TimeSpan]::TicksPerSecond) -ne 0) { throw 'boundary precision drift' }
    return $instant.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:sszzz", [Globalization.CultureInfo]::InvariantCulture)
}
function Convert-ObservedPrincipalSid([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { throw 'principal unavailable' }
    if ($Value -match '^S-') {
        return [Security.Principal.SecurityIdentifier]::new($Value).Value
    }
    $account = [Security.Principal.NTAccount]::new($Value)
    return $account.Translate([Security.Principal.SecurityIdentifier]).Value
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
        start_boundary=(Convert-ObservedBoundary ([string]$trigger.StartBoundary));end_boundary=(Convert-ObservedBoundary ([string]$trigger.EndBoundary))
        trigger_enabled=[bool]$trigger.Enabled;repetition_interval=[string]$trigger.Repetition.Interval
        repetition_duration=[string]$trigger.Repetition.Duration;repetition_stop=[bool]$trigger.Repetition.StopAtDurationEnd
        random_delay=[string]$trigger.RandomDelay;principal_sid=(Convert-ObservedPrincipalSid ([string]$principal.UserId))
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
    $last = [datetime]$task.LastRunTime
    $next = [datetime]$task.NextRunTime
    if (($last.Ticks % [TimeSpan]::TicksPerSecond) -ne 0) { throw 'last run precision drift' }
    $nextText = if ($next.Ticks -eq ([datetime]'1899-12-30T00:00:00').Ticks) { $null } else { $next.ToString("o", [Globalization.CultureInfo]::InvariantCulture) }
    return @{status='PRESENT';task=$projected;state=[int]$task.State;last_result=([long]$task.LastTaskResult -band 4294967295);last_run=$last.ToString("yyyy-MM-dd'T'HH:mm:ss", [Globalization.CultureInfo]::InvariantCulture);next_run=$nextText}
}

function Get-ConsumedPrincipal {
    # Fixed immutable source evidence, never a caller-provided principal or path.
    $path = 'F:\AI\temp\qualification\arch134-d1r6-2026-10-15-7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343-3cf4284d017e362eee58a2f27526ab4de8f292a2-16a48a12756bb6d810799444859334ce6305001d.jsonl'
    $metadata = Get-Item -LiteralPath $path -Force
    if ($metadata.PSIsContainer -or ($metadata.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or $metadata.Length -ne 16917) { throw 'incident file drift' }
    $stream = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ($stream.Length -ne 16917) { throw 'incident size drift' }
        $bytes = [byte[]]::new(16917)
        $offset = 0
        while ($offset -lt $bytes.Length) {
            $count = $stream.Read($bytes, $offset, $bytes.Length - $offset)
            if ($count -le 0) { throw 'incident truncated' }
            $offset += $count
        }
        if ($stream.ReadByte() -ne -1) { throw 'incident oversized' }
    } finally { $stream.Dispose() }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $hash = [BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    if ($hash -cne 'b62959f9988dcc42e4881e45ed95abcf4abc2b6d2932514c7253165e1223955c') { throw 'incident hash drift' }
    $payload = [Text.UTF8Encoding]::new($false, $true).GetString($bytes)
    $lines = @($payload.Split([char]10))
    if ($lines.Count -ne 8 -or $lines[7] -cne '') { throw 'incident framing drift' }
    $records = @($lines[0..6] | ForEach-Object { $_ | ConvertFrom-Json })
    if ($records[6].event -cne 'FINAL' -or $records[6].classification -cne 'INDETERMINATE' -or $records[4].scheduler_task_create_calls -ne 1 -or $records[5].scheduler_task_create_calls -ne 1) { throw 'incident consumption drift' }
    return @{name=[string]$records[0].facts.principal_name;sid=[string]$records[0].facts.principal_sid}
}

function Assert-FrozenObservation($Value, $Identity) {
    if ([TimeZoneInfo]::Local.Id -cne 'Pacific Standard Time') { throw 'host zone drift' }
    if ($Value.status -cne 'PRESENT' -or $Value.state -ne 3 -or $Value.last_result -ne 2 -or $Value.last_run -cne '2026-10-15T06:20:00' -or $null -ne $Value.next_run) { throw 'incident state drift' }
    $expected = @{
        task_path='\AITradingBot-Arch134-D1R6-OvernightWake-v1'
        trigger_count=1
        trigger_type=1
        start_boundary='2026-10-15T13:20:00+00:00'
        end_boundary='2026-10-15T13:35:00+00:00'
        trigger_enabled=$true
        repetition_interval=''
        repetition_duration=''
        repetition_stop=$false
        random_delay=''
        principal_sid=$Identity.sid
        logon_type=3
        run_level=0
        action_count=1
        action_type=0
        command='C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
        arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "F:\AI\worktrees\ai-trading-bot-production-paper-overnight-wake-arming\scripts\arch134_d1r6_task_launcher.ps1"'
        working_directory='F:\AI\worktrees\ai-trading-bot-production-paper-overnight-wake-arming'
        enabled=$true
        wake_to_run=$true
        start_when_available=$false
        restart_count=0
        restart_interval=''
        allow_demand_start=$false
        run_only_if_idle=$false
        run_only_if_network_available=$false
        disallow_start_if_on_batteries=$false
        stop_if_going_on_batteries=$false
        hidden=$false
        multiple_instances=2
        execution_time_limit='PT20M'
        allow_hard_terminate=$true
        idle_stop=$false
        idle_restart=$false
    }
    if ($Value.task.Count -ne $expected.Count) { throw 'task field drift' }
    foreach ($key in $expected.Keys) {
        if (-not $Value.task.ContainsKey($key)) { throw 'task field missing' }
        $actual = $Value.task[$key]; $wanted = $expected[$key]
        if ($wanted -is [bool]) {
            if ($actual -isnot [bool] -or $actual -ne $wanted) { throw 'task boolean drift' }
        } elseif ($wanted -is [int]) {
            if ($actual -isnot [int] -or $actual -ne $wanted) { throw 'task integer drift' }
        } elseif ($actual -isnot [string] -or $actual -cne $wanted) { throw 'task text drift' }
    }
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
    if ($Mode -ceq 'Observe') {
        if ($line -cne '{}') { throw 'input invalid' }
        $identity = Get-Identity
        $observed = Get-TaskObservation
        $result = @{principal=$identity;observation=$observed}
    } else {
        if ($line -cne '{"interlock":"AUTHORIZE_ARCH134_D1R7_ONE_STALE_WAKE_RETIREMENT"}') { throw 'request invalid' }
        $consumed = Get-ConsumedPrincipal
        $identity = Get-Identity
        if ($consumed.name -cne $identity.name -or $consumed.sid -cne $identity.sid) { throw 'principal drift' }
        $service = New-Object -ComObject 'Schedule.Service'
        $service.Connect()
        $folder = $service.GetFolder('\')
        # Independently rebuild the entire fixed fingerprint at the effect boundary.
        $identityAgain = Get-Identity
        if ($identityAgain.name -cne $identity.name -or $identityAgain.sid -cne $identity.sid) { throw 'principal drift' }
        $consumedAgain = Get-ConsumedPrincipal
        if ($consumedAgain.name -cne $identityAgain.name -or $consumedAgain.sid -cne $identityAgain.sid) { throw 'consumed principal drift' }
        $observed = Get-TaskObservation
        Assert-FrozenObservation $observed $identityAgain
        $attempted = $true
        $null = $folder.DeleteTask('AITradingBot-Arch134-D1R6-OvernightWake-v1', 0)
        $result = @{disposition='CALL_RETURNED';deletion_attempts=1}
    }
    [Console]::Out.WriteLine(($result | ConvertTo-Json -Depth 8 -Compress))
    exit 0
} catch {
    $disposition = if ($attempted) { 'INDETERMINATE' } else { 'NOT_CALLED' }
    [Console]::Out.WriteLine((@{disposition=$disposition;deletion_attempts=([int]$attempted)} | ConvertTo-Json -Compress))
    exit 2
}
