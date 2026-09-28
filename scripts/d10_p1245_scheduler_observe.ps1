# P124-5 independent read-only COM projection, extending Architecture 126.
# Dot-sourcing defines Read-FixedTask only; it performs no host observation.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    if ($args.Count -ne 0) { throw 'arguments forbidden' }

    function Read-FixedTask {
        param($FixedFolder, [ref]$CapturedDefinition = $null)
        $task = $FixedFolder.GetTask('AITradingBot-PD4-UnattendedPaper-v1')
        if ($task.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1') {
            throw 'task identity mismatch'
        }
        $definition = $task.Definition
        if ($null -ne $CapturedDefinition) { $CapturedDefinition.Value = $definition }
        $userId = [string]$definition.Principal.UserId
        if ([string]::IsNullOrEmpty($userId)) { throw 'principal unavailable' }
        if ($userId -match '^S-1-') {
            $sid = [System.Security.Principal.SecurityIdentifier]::new($userId)
            $account = $sid.Translate([System.Security.Principal.NTAccount])
            $sid = $account.Translate([System.Security.Principal.SecurityIdentifier])
        } else {
            $account = [System.Security.Principal.NTAccount]::new($userId)
            $sid = $account.Translate([System.Security.Principal.SecurityIdentifier])
        }
        $resolvedSid = $sid.Value
        if ($resolvedSid -ne 'S-1-5-21-1397534616-3988210162-180023805-1009') {
            throw 'principal mismatch'
        }

        $actions = $definition.Actions
        $triggers = $definition.Triggers
        $action = if ($actions.Count -eq 1) { $actions.Item(1) } else { $null }
        $trigger = if ($triggers.Count -eq 1) { $triggers.Item(1) } else { $null }
        $settings = $definition.Settings
        $xml = [string]$task.Xml
        $xmlBytes = ([System.Text.UTF8Encoding]::new($false)).GetBytes($xml)
        if ($xmlBytes.Length -eq 0 -or $xmlBytes.Length -gt 1048576) {
            throw 'XML unavailable or oversized'
        }
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $xmlDigest = [BitConverter]::ToString($sha.ComputeHash($xmlBytes)).Replace('-', '').ToLowerInvariant()
        } finally {
            $sha.Dispose()
        }
        return [ordered]@{
            task_path = '\AITradingBot-PD4-UnattendedPaper-v1'
            principal_sid = $resolvedSid
            logon_type = [int]$definition.Principal.LogonType
            run_level = [int]$definition.Principal.RunLevel
            action_count = [int]$actions.Count
            action_type = if ($null -ne $action) { [int]$action.Type } else { $null }
            action_path = if ($null -ne $action) { [string]$action.Path } else { $null }
            action_arguments = if ($null -ne $action) { [string]$action.Arguments } else { $null }
            action_working_directory = if ($null -ne $action) { [string]$action.WorkingDirectory } else { $null }
            trigger_count = [int]$triggers.Count
            trigger_type = if ($null -ne $trigger) { [int]$trigger.Type } else { $null }
            trigger_enabled = if ($null -ne $trigger) { [bool]$trigger.Enabled } else { $null }
            trigger_start_boundary = if ($null -ne $trigger) { [string]$trigger.StartBoundary } else { $null }
            trigger_end_boundary = if ($null -ne $trigger) { [string]$trigger.EndBoundary } else { $null }
            host_timezone = [System.TimeZoneInfo]::Local.Id
            trigger_days_interval = if ($null -ne $trigger) { [int]$trigger.DaysInterval } else { $null }
            trigger_random_delay = if ($null -ne $trigger) { [string]$trigger.RandomDelay } else { $null }
            repetition_interval = if ($null -ne $trigger) { [string]$trigger.Repetition.Interval } else { $null }
            repetition_duration = if ($null -ne $trigger) { [string]$trigger.Repetition.Duration } else { $null }
            repetition_stop_at_duration_end = if ($null -ne $trigger) { [bool]$trigger.Repetition.StopAtDurationEnd } else { $null }
            multiple_instances = [int]$settings.MultipleInstances
            disallow_start_if_on_batteries = [bool]$settings.DisallowStartIfOnBatteries
            stop_if_going_on_batteries = [bool]$settings.StopIfGoingOnBatteries
            allow_demand_start = [bool]$settings.AllowDemandStart
            start_when_available = [bool]$settings.StartWhenAvailable
            run_only_if_network_available = [bool]$settings.RunOnlyIfNetworkAvailable
            run_only_if_idle = [bool]$settings.RunOnlyIfIdle
            enabled = [bool]$settings.Enabled
            hidden = [bool]$settings.Hidden
            wake_to_run = [bool]$settings.WakeToRun
            execution_time_limit = [string]$settings.ExecutionTimeLimit
            priority = [int]$settings.Priority
            restart_count = [int]$settings.RestartCount
            restart_interval = [string]$settings.RestartInterval
            xml_byte_length = [int]$xmlBytes.Length
            xml_sha256 = $xmlDigest
        }
    }

    if ($MyInvocation.InvocationName -eq '.') { return }
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')
    $first = Read-FixedTask $folder
    $second = Read-FixedTask $folder
    $record = [ordered]@{
        schema = 'p1245-task-scheduler-com-observation/v1'
        status = 'OBSERVED'
        first = $first
        second = $second
    }
    [Console]::Out.WriteLine(($record | ConvertTo-Json -Compress -Depth 6))
    exit 0
} catch {
    [Console]::Error.WriteLine('scheduler_observation_blocked')
    exit 1
}
