# D10-C fail-safe scheduler halt for the exact armed one-week task.
# This operator only disables the fixed registered task. It never starts,
# deletes, recreates, re-registers, or changes any other scheduler semantics.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$callAttempted = $false
$disposition = 'NOT_CALLED'
$exitCode = 1
$preXmlSha256 = $null
$postXmlSha256 = $null

try {
    if ($args.Count -ne 0) { throw 'arguments forbidden' }

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )) {
        throw 'administrator required'
    }

    . (Join-Path $PSScriptRoot 'd10_p1245_scheduler_observe.ps1')

    function Require-ExactSemantics {
        param($Observed, [bool]$Enabled)

        $expected = [ordered]@{
            task_path = '\AITradingBot-PD4-UnattendedPaper-v1'
            principal_sid = 'S-1-5-21-1397534616-3988210162-180023805-1009'
            logon_type = 1
            run_level = 0
            action_count = 1
            action_type = 0
            action_path = 'F:\AITradingBot\runtime\python.exe'
            action_arguments = '-I -S -B -X pycache_prefix=F:\AITradingBot\D10\no-pycache F:\AITradingBot\D10\launch-guard.py'
            action_working_directory = 'F:\AITradingBot\D10'
            trigger_count = 1
            trigger_type = 2
            trigger_enabled = $true
            trigger_start_boundary = '2026-09-29T01:30:00-07:00'
            trigger_end_boundary = '2026-10-05T17:45:22-07:00'
            host_timezone = 'Pacific Standard Time'
            trigger_days_interval = 1
            trigger_random_delay = ''
            repetition_interval = ''
            repetition_duration = ''
            repetition_stop_at_duration_end = $false
            multiple_instances = 2
            disallow_start_if_on_batteries = $false
            stop_if_going_on_batteries = $false
            allow_demand_start = $true
            start_when_available = $true
            run_only_if_network_available = $false
            run_only_if_idle = $false
            enabled = $Enabled
            hidden = $false
            wake_to_run = $true
            execution_time_limit = 'PT1H'
            priority = 7
            restart_count = 0
            restart_interval = ''
        }

        foreach ($key in $expected.Keys) {
            if (-not $Observed.Contains($key)) { throw 'scheduler field missing' }
            if ($null -eq $Observed[$key] -or
                $Observed[$key].GetType() -ne $expected[$key].GetType() -or
                $Observed[$key] -cne $expected[$key]) {
                throw 'scheduler semantic drift'
            }
        }
    }

    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')

    $first = Read-FixedTask $folder
    $second = Read-FixedTask $folder
    if (($first | ConvertTo-Json -Compress) -cne
        ($second | ConvertTo-Json -Compress)) {
        throw 'scheduler two-read drift'
    }
    Require-ExactSemantics $second $true
    $preXmlSha256 = [string]$second.xml_sha256

    $task = $folder.GetTask('AITradingBot-PD4-UnattendedPaper-v1')
    if ($task.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1' -or
        -not [bool]$task.Enabled -or
        [int]$task.State -eq 4) {
        throw 'task is not exact enabled non-running target'
    }

    $callAttempted = $true
    $task.Enabled = $false
    $disposition = 'CALL_RETURNED'

    $postTask = $folder.GetTask('AITradingBot-PD4-UnattendedPaper-v1')
    if ($postTask.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1' -or
        [bool]$postTask.Enabled -or
        [int]$postTask.State -eq 4) {
        throw 'post-halt registered task state disagrees'
    }

    $third = Read-FixedTask $folder
    $fourth = Read-FixedTask $folder
    if (($third | ConvertTo-Json -Compress) -cne
        ($fourth | ConvertTo-Json -Compress)) {
        throw 'post-halt scheduler two-read drift'
    }
    Require-ExactSemantics $fourth $false
    $postXmlSha256 = [string]$fourth.xml_sha256

    $exitCode = 0
} catch {
    if ($callAttempted) {
        $disposition = 'INDETERMINATE'
        $exitCode = 2
    }
}

$record = [ordered]@{
    schema = 'd10c-task-scheduler-halt/v1'
    disposition = $disposition
    pre_xml_sha256 = $preXmlSha256
    post_xml_sha256 = $postXmlSha256
    scheduler_mutation = if ($disposition -eq 'CALL_RETURNED') {
        'DISABLED_VERIFIED'
    } elseif ($disposition -eq 'INDETERMINATE') {
        'INDETERMINATE'
    } else {
        'NOT_RUN'
    }
    source_launch = 'NOT_RUN'
    provider = 'NOT_RUN'
    'Paper-v2' = 'NOT_RUN'
    broker = 'NOT_RUN'
    live = 'NOT_RUN'
}
[Console]::Out.WriteLine(($record | ConvertTo-Json -Compress -Depth 4))
exit $exitCode
