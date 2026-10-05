param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Command,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = $PSScriptRoot

$Candidates = @()
if ($env:AI_TRADING_BOT_PYTHON) {
    $Candidates += $env:AI_TRADING_BOT_PYTHON
}
$Candidates += (Join-Path $Repo '.venv\Scripts\python.exe')
$Candidates += 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'

$Python = $null
foreach ($Candidate in $Candidates) {
    if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
        $Python = $Candidate
        break
    }
}

if (-not $Python) {
    $Resolved = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($Resolved) {
        $Python = $Resolved.Source
    }
}

if (-not $Python) {
    throw 'STOP: no approved Python interpreter found for checkpoint runner'
}

Set-Location $Repo

$RunnerArguments = @(
    '-B',
    '-m',
    'scripts.checkpoint_runner',
    $Command
)
if ($RemainingArguments) {
    $RunnerArguments += $RemainingArguments
}

& $Python @RunnerArguments
exit $LASTEXITCODE
