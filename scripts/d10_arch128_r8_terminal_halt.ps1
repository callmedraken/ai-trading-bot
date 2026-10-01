# R8I-H1: fixed COM halt. Registration grants no execution authorization.
# Only task.Enabled = false may mutate external state. Never retry or roll back.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$callAttempted = $false
$disposition = 'NOT_CALLED'
$before = $null
$after = $null
$xmlUnchanged = $false
$exitCode = 1

try {
    if ($args.Count -ne 1 -or $args[0] -cne '--execute-reviewed-r8-terminal-halt' -or
        $env:AI_TRADING_BOT_ARCH128_R8_HALT_AUTHORIZATION -cne 'ARCH128_R8_TERMINAL_HALT_AUTHORIZED') {
        throw 'exact halt authorization required'
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
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
            enabled = $Enabled
            task_state = if ($Enabled) { 3 } else { 1 }
        }
        if ($Observed.Count -ne $expected.Count + 2) { throw 'scheduler field set drift' }
        foreach ($key in $expected.Keys) {
            if (-not $Observed.Contains($key) -or $null -eq $Observed[$key] -or
                $Observed[$key].GetType() -ne $expected[$key].GetType() -or
                $Observed[$key] -cne $expected[$key]) { throw 'scheduler semantic drift' }
        }
        if ($Observed.xml_byte_length -le 0 -or $Observed.xml_byte_length -gt 1048576 -or
            $Observed.xml_sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'scheduler XML invalid' }
    }

    function Read-ExactTask {
        param($FixedFolder)
        $observed = Read-FixedTask $FixedFolder
        $independent = $FixedFolder.GetTask('AITradingBot-PD4-UnattendedPaper-v1')
        if ($independent.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1') { throw 'task path drift' }
        $observed['task_state'] = [int]$independent.State
        return $observed
    }

    function Normalize-EnabledXml {
        param([string]$Text, [string]$ExpectedEnabled)
        $document = [System.Xml.XmlDocument]::new()
        $document.XmlResolver = $null
        $document.PreserveWhitespace = $true
        $document.LoadXml($Text)
        $manager = [System.Xml.XmlNamespaceManager]::new($document.NameTable)
        $manager.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task')
        $nodes = $document.SelectNodes('/t:Task/t:Settings/t:Enabled', $manager)
        if ($nodes.Count -ne 1 -or $nodes[0].InnerText -cne $ExpectedEnabled) { throw 'XML enabled drift' }
        # This mutates only an in-memory XML copy, never a scheduler definition.
        $nodes[0].InnerText = 'false'
        return $document.OuterXml
    }

    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')
    $first = Read-ExactTask $folder
    $second = Read-ExactTask $folder
    if (($first | ConvertTo-Json -Compress) -cne ($second | ConvertTo-Json -Compress)) {
        throw 'scheduler two-read drift'
    }
    Require-ExactSemantics $second $true
    $before = $second
    $task = $folder.GetTask('AITradingBot-PD4-UnattendedPaper-v1')
    if ($task.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1' -or
        -not [bool]$task.Enabled -or [int]$task.State -eq 4) { throw 'task target drift' }
    $beforeXml = [string]$task.Xml
    $xmlBytes = ([System.Text.UTF8Encoding]::new($false)).GetBytes($beforeXml)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = [BitConverter]::ToString($sha.ComputeHash($xmlBytes)).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
    if ($digest -cne $before.xml_sha256 -or $xmlBytes.Length -ne $before.xml_byte_length) {
        throw 'immediate task XML drift'
    }
    $normalizedBefore = Normalize-EnabledXml $beforeXml 'true'

    $callAttempted = $true
    $task.Enabled = $false
    $disposition = 'CALL_RETURNED'

    # Independently reacquire the task and compare all XML except Enabled.
    $postTask = $folder.GetTask('AITradingBot-PD4-UnattendedPaper-v1')
    if ($postTask.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1' -or
        [bool]$postTask.Enabled -or [int]$postTask.State -eq 4) { throw 'post task drift' }
    $postXml = [string]$postTask.Xml
    if ($normalizedBefore -cne (Normalize-EnabledXml $postXml 'false')) {
        throw 'unrelated scheduler XML drift'
    }
    $third = Read-ExactTask $folder
    $fourth = Read-ExactTask $folder
    if (($third | ConvertTo-Json -Compress) -cne ($fourth | ConvertTo-Json -Compress)) {
        throw 'post scheduler two-read drift'
    }
    Require-ExactSemantics $fourth $false
    $xmlBytes = ([System.Text.UTF8Encoding]::new($false)).GetBytes($postXml)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = [BitConverter]::ToString($sha.ComputeHash($xmlBytes)).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
    if ($digest -cne $fourth.xml_sha256 -or $xmlBytes.Length -ne $fourth.xml_byte_length) {
        throw 'post full XML readback drift'
    }
    $after = $fourth
    $xmlUnchanged = $true
    $exitCode = 0
} catch {
    if ($callAttempted) {
        $disposition = 'INDETERMINATE'
        $exitCode = 2
    }
}
$record = [ordered]@{
    schema = 'arch128-r8-terminal-halt-com/v1'
    call_attempted = $callAttempted
    disposition = $disposition
    before = $before
    after = $after
    xml_unchanged = $xmlUnchanged
}
[Console]::Out.WriteLine(($record | ConvertTo-Json -Compress -Depth 6))
exit $exitCode
