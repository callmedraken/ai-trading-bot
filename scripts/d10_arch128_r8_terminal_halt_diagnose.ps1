# R8I-H1a: read-only native pre-call diagnostic for the terminal halt.
# It mirrors the halt's native checks through XML admission and never mutates the task.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$reason = $null
$scheduler = $null

try {
    if ($args.Count -ne 0) {
        throw 'arguments forbidden'
    }
    if (-not [string]::IsNullOrEmpty(
        $env:AI_TRADING_BOT_ARCH128_R8_HALT_AUTHORIZATION
    )) {
        $reason = 'AUTHORIZATION_PRESENT'
        throw 'authorization present during diagnostic'
    }

    $reason = 'ADMINISTRATOR_REQUIRED'
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )) {
        throw 'administrator required'
    }

    $reason = 'OBSERVE_HELPER_LOAD'
    . (Join-Path $PSScriptRoot 'd10_p1245_scheduler_observe.ps1')

    function Require-ExactSemantics {
        param($Observed)
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
            trigger_start_boundary = '2026-10-01T01:30:00-07:00'
            trigger_end_boundary = '2026-10-07T15:07:24-07:00'
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
            hidden = $false
            wake_to_run = $true
            execution_time_limit = 'PT1H'
            priority = 7
            restart_count = 0
            restart_interval = ''
            enabled = $true
            task_state = 3
        }
        if ($Observed.Count -ne $expected.Count + 2) {
            throw 'scheduler field set drift'
        }
        foreach ($key in $expected.Keys) {
            if (-not $Observed.Contains($key) -or $null -eq $Observed[$key] -or
                $Observed[$key].GetType() -ne $expected[$key].GetType() -or
                $Observed[$key] -cne $expected[$key]) {
                throw 'scheduler semantic drift'
            }
        }
        if ($Observed.xml_byte_length -le 0 -or
            $Observed.xml_byte_length -gt 1048576 -or
            $Observed.xml_sha256 -cnotmatch '^[0-9a-f]{64}$') {
            throw 'scheduler XML invalid'
        }
    }

    function Read-ExactTask {
        param($FixedFolder)
        $observed = Read-FixedTask $FixedFolder
        $independent = $FixedFolder.GetTask(
            'AITradingBot-PD4-UnattendedPaper-v1'
        )
        if ($independent.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1') {
            throw 'task path drift'
        }
        $observed['task_state'] = [int]$independent.State
        return $observed
    }

    $reason = 'COM_CONNECT'
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')

    $reason = 'SCHEDULER_READ_FIRST'
    $first = Read-ExactTask $folder

    $reason = 'SCHEDULER_READ_SECOND'
    $second = Read-ExactTask $folder

    $reason = 'SCHEDULER_TWO_READ'
    if (($first | ConvertTo-Json -Compress) -cne
        ($second | ConvertTo-Json -Compress)) {
        throw 'scheduler two-read drift'
    }

    $reason = 'SCHEDULER_SEMANTICS'
    Require-ExactSemantics $second
    $scheduler = $second

    $reason = 'TASK_REACQUIRE'
    $task = $folder.GetTask('AITradingBot-PD4-UnattendedPaper-v1')

    $reason = 'TASK_TARGET'
    if ($task.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1' -or
        -not [bool]$task.Enabled -or [int]$task.State -eq 4) {
        throw 'task target drift'
    }

    $reason = 'IMMEDIATE_XML'
    $beforeXml = [string]$task.Xml
    $xmlBytes = ([System.Text.UTF8Encoding]::new($false)).GetBytes($beforeXml)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = [BitConverter]::ToString(
            $sha.ComputeHash($xmlBytes)
        ).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
    if ($digest -cne $scheduler.xml_sha256 -or
        $xmlBytes.Length -ne $scheduler.xml_byte_length) {
        throw 'immediate task XML drift'
    }

    $reason = 'XML_ENABLED_NODE'
    $document = [System.Xml.XmlDocument]::new()
    $document.XmlResolver = $null
    $document.PreserveWhitespace = $true
    $document.LoadXml($beforeXml)
    $manager = [System.Xml.XmlNamespaceManager]::new($document.NameTable)
    $manager.AddNamespace(
        't',
        'http://schemas.microsoft.com/windows/2004/02/mit/task'
    )
    $nodes = $document.SelectNodes('/t:Task/t:Settings/t:Enabled', $manager)
    # Task Scheduler schema permits omission here and defines the default as
    # true. COM/task-state checks above already prove this exact task is enabled.
    if ($nodes.Count -gt 1) {
        $scheduler['xml_enabled_node_state'] = 'COUNT_DRIFT'
        throw 'XML enabled node count drift'
    }
    if ($nodes.Count -eq 1 -and $nodes[0].InnerText -cne 'true') {
        $scheduler['xml_enabled_node_state'] = 'VALUE_NOT_TRUE'
        throw 'XML enabled value drift'
    }

    $record = [ordered]@{
        schema = 'arch128-r8-terminal-halt-diagnostic/v1'
        status = 'READY'
        reason = $null
        call_attempted = $false
        scheduler_mutation = 'NOT_RUN'
        scheduler = $scheduler
    }
    [Console]::Out.WriteLine(($record | ConvertTo-Json -Compress -Depth 6))
    exit 0
} catch {
    $record = [ordered]@{
        schema = 'arch128-r8-terminal-halt-diagnostic/v1'
        status = 'BLOCKED'
        reason = $reason
        call_attempted = $false
        scheduler_mutation = 'NOT_RUN'
        scheduler = $scheduler
    }
    [Console]::Out.WriteLine(($record | ConvertTo-Json -Compress -Depth 6))
    exit 1
}
