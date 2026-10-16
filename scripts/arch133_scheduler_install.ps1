# Private one-shot TASK_CREATE transport. No public semantic arguments.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$attempted = $false; $disposition = 'NOT_CALLED'; $exitCode = 1
$request = $null; $password = $null; $line = $null; $builder = $null
$startTokens = $null; $endTokens = $null
try {
    if ($args.Count -ne 0) { throw 'arguments forbidden' }
    [Console]::InputEncoding = [Text.UTF8Encoding]::new($false, $true)
    $builder = [Text.StringBuilder]::new()
    while ($true) {
        $character = [Console]::In.Read()
        if ($character -eq -1 -or $character -eq 10) { break }
        if ($builder.Length -ge 16384) { throw 'request oversized' }
        $null = $builder.Append([char]$character)
    }
    if ($character -ne 10 -or [Console]::In.Read() -ne -1) { throw 'request invalid' }
    $line = $builder.ToString(); $null = $builder.Clear(); $builder = $null
    $request = $line | ConvertFrom-Json
    # Windows JSON parsers differ in automatic ISO date coercion. Preserve the
    # exact UTC text from our canonical private request, never a culture cast.
    $boundaryPattern = '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z'
    $startTokens = [regex]::Matches($line, '"start_boundary":"(' + $boundaryPattern + ')"')
    $endTokens = [regex]::Matches($line, '"end_boundary":"(' + $boundaryPattern + ')"')
    if ($startTokens.Count -ne 1 -or $endTokens.Count -ne 1) { throw 'boundary invalid' }
    $startText = $startTokens[0].Groups[1].Value
    $endText = $endTokens[0].Groups[1].Value
    $startTokens = $null; $endTokens = $null; $line = $null
    if ((@($request.PSObject.Properties.Name | Sort-Object) -join ',') -cne 'activation_sha256,end_boundary,password,start_boundary' -or
        $request.password -isnot [string] -or [string]::IsNullOrEmpty($request.password) -or $request.password.Length -gt 1024 -or $request.password.Contains([char]0) -or
        $request.activation_sha256 -cne '37873b490c3f2ccced53431c599e40ca54fdc008e09e9bfdb38eb61d10f3cab2') { throw 'request invalid' }
    . (Join-Path $PSScriptRoot 'arch133_scheduler_definition.ps1')
    $xml = Get-FixedXml $startText $endText
    $format = "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'"
    $start = [DateTimeOffset]::ParseExact($startText, $format, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal)
    $end = [DateTimeOffset]::ParseExact($endText, $format, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal)
    if ([DateTimeOffset]::UtcNow -ge $start -or $start -ge $end) { throw 'window stale' }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($identity.Name -cne 'DESKTOP-I4DOKM7\Trading' -or $identity.User.Value -cne 'S-1-5-21-1397534616-3988210162-180023805-1009') { throw 'principal drift' }
    $first = Read-FixedTask
    $second = Read-FixedTask
    if ($first.status -cne 'ABSENT' -or $second.status -cne 'ABSENT') { throw 'predecessor not absent' }
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')
    $definition = $service.NewTask(0)
    $definition.XmlText = $xml
    $hash = (Get-FileHash -LiteralPath 'F:\AITradingBot\Arch133\activation.json' -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -cne $request.activation_sha256 -or [DateTimeOffset]::UtcNow -ge $start) { throw 'final admission drift' }
    $password = $request.password; $request.password = $null
    $attempted = $true
    # TASK_CREATE=2, TASK_LOGON_PASSWORD=1. Unknown existing state cannot update.
    $null = $folder.RegisterTaskDefinition('AITradingBot-Arch133-SingleSessionReviewPaper-v1', $definition, 2,
        'S-1-5-21-1397534616-3988210162-180023805-1009', $password, 1, $null)
    $disposition = 'CALL_RETURNED'; $exitCode = 0
} catch {
    if ($attempted) { $disposition = 'INDETERMINATE'; $exitCode = 2 }
} finally {
    $password = $null; $request = $null; $line = $null; $builder = $null
    $startTokens = $null; $endTokens = $null
}
[Console]::Out.WriteLine(([ordered]@{schema='arch133p-scheduler-registration/v1';disposition=$disposition;registration_attempts=([int]$attempted)} | ConvertTo-Json -Compress))
exit $exitCode
