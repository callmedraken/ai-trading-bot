# Zero-argument, local fixed-task COM observer. No mutation capability.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    if ($args.Count -ne 0) { throw 'arguments forbidden' }
    . (Join-Path $PSScriptRoot 'arch133_scheduler_definition.ps1')
    $first = Read-FixedTask
    $second = Read-FixedTask
    [Console]::Out.WriteLine(([ordered]@{schema='arch133p-scheduler-observation/v1';first=$first;second=$second} | ConvertTo-Json -Compress -Depth 5))
    exit 0
} catch {
    [Console]::Out.WriteLine('{"schema":"arch133p-scheduler-observation/v1","status":"BLOCKED"}')
    exit 1
}
