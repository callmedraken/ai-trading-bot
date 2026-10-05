# Architecture-128 R3 fixed read-only Task Scheduler observation.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    if ($args.Count -ne 0) { throw 'arguments forbidden' }

    . (Join-Path $PSScriptRoot 'd10_p1245_scheduler_observe.ps1')

    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')

    function Read-R3FixedTask {
        param($FixedFolder)

        $observed = Read-FixedTask $FixedFolder
        $task = $FixedFolder.GetTask('AITradingBot-PD4-UnattendedPaper-v1')
        if ($task.Path -cne '\AITradingBot-PD4-UnattendedPaper-v1') {
            throw 'task identity mismatch'
        }
        $observed['task_state'] = [int]$task.State
        return $observed
    }

    $first = Read-R3FixedTask $folder
    $second = Read-R3FixedTask $folder

    $record = [ordered]@{
        schema = 'arch128-r3-scheduler-observation/v1'
        status = 'OBSERVED'
        first = $first
        second = $second
    }

    [Console]::Out.WriteLine(($record | ConvertTo-Json -Compress -Depth 6))
    exit 0
} catch {
    [Console]::Error.WriteLine('arch128_r3_scheduler_observation_blocked')
    exit 1
}
