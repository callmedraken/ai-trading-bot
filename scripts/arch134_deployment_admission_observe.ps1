# Local COM/CIM observation only. No task/process control, credentials or writes.
param([Parameter(Mandatory=$true)][int]$ObserverPid)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    if ($args.Count -ne 0 -or $ObserverPid -le 0 -or $ObserverPid -eq $PID) { throw 'observer invalid' }
    function Get-Hash([string]$Value) {
        $sha = [Security.Cryptography.SHA256]::Create()
        try { return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
    }
    # Same local Schedule.Service read-only COM authority as the accepted
    # arch133_scheduler_observe.ps1. Enumeration also detects other tasks capable
    # of overlapping this production transition; XML never leaves this process.
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $pending = [System.Collections.Generic.Queue[object]]::new()
    $pending.Enqueue($service.GetFolder('\'))
    $folders = 0; $taskCount = 0
    $tasks = [System.Collections.Generic.SortedDictionary[string,string]]::new([StringComparer]::Ordinal)
    while ($pending.Count -gt 0) {
        $folder = $pending.Dequeue(); $folders++
        if ($folders -gt 1024) { throw 'folder bound' }
        foreach ($child in $folder.GetFolders(0)) { $pending.Enqueue($child) }
        foreach ($task in $folder.GetTasks(1)) {
            $taskCount++
            if ($taskCount -gt 4096) { throw 'task bound' }
            $xml = [string]$task.Xml
            if ([Text.Encoding]::UTF8.GetByteCount($xml) -gt 65536) { throw 'XML bound' }
            if ([string]$task.Path -notmatch '(?i)AITradingBot' -and $xml -notmatch '(?i)AITradingBot|ai-trading-bot|run_arch13[34]') { continue }
            if ($tasks.Count -ge 256 -or [bool]$task.Enabled -or [int]$task.State -eq 4) { throw 'task overlap' }
            if ($xml -match '<!DOCTYPE|<!ENTITY') { throw 'XML declarations' }
            $document = [System.Xml.XmlDocument]::new(); $document.XmlResolver = $null
            $document.LoadXml($xml)
            $ns = [System.Xml.XmlNamespaceManager]::new($document.NameTable)
            $ns.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task')
            if ($null -eq $document.SelectSingleNode('/t:Task', $ns)) { throw 'task schema' }
            if (@($document.SelectNodes('//t:BootTrigger|//t:LogonTrigger|//t:RestartOnFailure', $ns)).Count -ne 0) { throw 'automatic resume policy' }
            $enabled = $document.SelectSingleNode('/t:Task/t:Settings/t:Enabled', $ns)
            if ($null -eq $enabled -or $enabled.InnerText -cne 'false') { throw 'disabled unproven' }
            $key = Get-Hash ([string]$task.Path)
            $tasks.Add($key, (Get-Hash $xml))
        }
    }
    $processes = @(Get-CimInstance -ClassName Win32_Process -Property ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate)
    if ($processes.Count -gt 8192) { throw 'process bound' }
    $owner = @($processes | Where-Object { [int]$_.ProcessId -eq $ObserverPid })
    if ($owner.Count -ne 1 -or [string]$owner[0].Name -notmatch '^python(?:w)?(?:3(?:\.\d+)?)?\.exe$') { throw 'observer identity' }
    $relevant = [System.Collections.Generic.List[string]]::new()
    foreach ($process in $processes) {
        if ([int]$process.ProcessId -eq $PID -or [int]$process.ProcessId -eq $ObserverPid) { continue }
        $name = [string]$process.Name
        $command = [string]$process.CommandLine
        $executable = [string]$process.ExecutablePath
        # An unreadable plausible interpreter is indeterminate, never absence.
        if ($name -match '^(?i:python.*|powershell|pwsh|cmd)\.exe$' -and ([string]::IsNullOrEmpty($command) -or [string]::IsNullOrEmpty($executable))) { throw 'process identity unavailable' }
        if ($command.Length -gt 32768 -or $executable.Length -gt 1024) { throw 'process bound' }
        if ($command -match '(?i)AITradingBot|ai-trading-bot|arch13[34]|successor' -or $executable -match '(?i)AITradingBot') {
            $relevant.Add(([string]$process.ProcessId + ':' + [string]$process.CreationDate))
        }
    }
    $rows = @()
    foreach ($key in $tasks.Keys) { $rows += ,@($key, $tasks[$key]) }
    $processMaterial = [string]::Join('|', @($relevant | Sort-Object))
    [Console]::Out.WriteLine(([ordered]@{
        schema='arch134-deployment-quiescence/v1'
        tasks=@($rows)
        process_inventory_sha256=(Get-Hash $processMaterial)
        relevant_process_count=$relevant.Count
        reboot_manual_start=$true
    } | ConvertTo-Json -Compress -Depth 5))
    exit 0
} catch {
    [Console]::Out.WriteLine('{"schema":"arch134-deployment-quiescence/v1","status":"BLOCKED"}')
    exit 1
}
