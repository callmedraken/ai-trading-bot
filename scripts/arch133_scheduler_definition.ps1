# Internal definition helpers only. Dot-source from the two fixed transports.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-FixedXml {
    param([string]$Start, [string]$End)
    $pattern = '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$'
    if ($Start -cnotmatch $pattern -or $End -cnotmatch $pattern) { throw 'boundary invalid' }
    return @'
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<RegistrationInfo>
<URI>\AITradingBot-Arch133-SingleSessionReviewPaper-v1</URI>
</RegistrationInfo>
<Triggers>
<TimeTrigger>
<StartBoundary>$START$</StartBoundary>
<EndBoundary>$END$</EndBoundary>
<Enabled>true</Enabled>
</TimeTrigger>
</Triggers>
<Principals>
<Principal id="Trading">
<UserId>S-1-5-21-1397534616-3988210162-180023805-1009</UserId>
<LogonType>Password</LogonType>
<RunLevel>LeastPrivilege</RunLevel>
</Principal>
</Principals>
<Settings>
<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
<AllowHardTerminate>true</AllowHardTerminate>
<StartWhenAvailable>false</StartWhenAvailable>
<RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
<IdleSettings>
<StopOnIdleEnd>true</StopOnIdleEnd>
<RestartOnIdle>false</RestartOnIdle>
</IdleSettings>
<AllowStartOnDemand>false</AllowStartOnDemand>
<Enabled>false</Enabled>
<Hidden>false</Hidden>
<RunOnlyIfIdle>false</RunOnlyIfIdle>
<WakeToRun>false</WakeToRun>
<ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
<Priority>7</Priority>
</Settings>
<Actions Context="Trading">
<Exec>
<Command>F:\AITradingBot\runtime\python.exe</Command>
<Arguments>-I -B F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133g\scripts\run_arch133_unattended_review_paper.py</Arguments>
<WorkingDirectory>F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133g</WorkingDirectory>
</Exec>
</Actions>
</Task>
'@.Replace('$START$', $Start).Replace('$END$', $End)
}

function Get-Digest {
    param([string]$Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function Get-Frame {
    param([string]$Value)
    return ([string]$Value.Length + ':' + $Value)
}

function Get-TreeMaterial {
    param([System.Xml.XmlElement]$Node)
    $tag = '{' + $Node.NamespaceURI + '}' + $Node.LocalName
    $attributes = [System.Collections.Generic.SortedDictionary[string,string]]::new([StringComparer]::Ordinal)
    foreach ($attribute in $Node.Attributes) {
        if ($attribute.NamespaceURI -ceq 'http://www.w3.org/2000/xmlns/') { continue }
        $name = if ([string]::IsNullOrEmpty($attribute.NamespaceURI)) { $attribute.LocalName } else { '{' + $attribute.NamespaceURI + '}' + $attribute.LocalName }
        $attributes.Add($name, $attribute.Value)
    }
    $attributeMaterial = ''
    foreach ($key in $attributes.Keys) { $attributeMaterial += (Get-Frame $key) + (Get-Frame $attributes[$key]) }
    $text = ''; $children = ''; $seenElement = $false
    foreach ($child in $Node.ChildNodes) {
        if ($child -is [System.Xml.XmlElement]) {
            $seenElement = $true
            $children += Get-TreeMaterial $child
        } elseif ($child -is [System.Xml.XmlText] -or $child -is [System.Xml.XmlWhitespace]) {
            if ($seenElement -and -not [string]::IsNullOrWhiteSpace($child.Value)) { throw 'mixed XML forbidden' }
            if (-not $seenElement) { $text += $child.Value }
        } else { throw 'XML node forbidden' }
    }
    return '(' + (Get-Frame $tag) + (Get-Frame $attributeMaterial) + (Get-Frame $text.Trim()) + $children + ')'
}

function Read-FixedTask {
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')
    try {
        $task = $folder.GetTask('AITradingBot-Arch133-SingleSessionReviewPaper-v1')
    } catch {
        $errorObject = $_.Exception
        while ($null -ne $errorObject.InnerException) { $errorObject = $errorObject.InnerException }
        if ($errorObject.HResult -eq -2147024894) { return [ordered]@{status='ABSENT'} }
        throw 'fixed task unavailable'
    }
    if ($task.Path -cne '\AITradingBot-Arch133-SingleSessionReviewPaper-v1') { throw 'task identity invalid' }
    $xml = [string]$task.Xml
    if ([string]::IsNullOrEmpty($xml) -or [Text.Encoding]::UTF8.GetByteCount($xml) -gt 65536) { throw 'XML bound exceeded' }
    $document = [System.Xml.XmlDocument]::new()
    $document.XmlResolver = $null
    if ($xml -match '<!DOCTYPE|<!ENTITY') { throw 'XML declarations forbidden' }
    $document.LoadXml($xml)
    $material = Get-TreeMaterial $document.DocumentElement
    if ([int]$task.State -eq 4) { throw 'running task inadmissible' }
    return [ordered]@{status='PRESENT'; projection_sha256=(Get-Digest $material); xml_sha256=(Get-Digest $xml)}
}
