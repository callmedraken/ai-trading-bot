# S2C1B source acceptance does not authorize observe() or helper execution.
# Fixed read-only Event Log projection; operational invocation is a later checkpoint.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    if ($args.Count -ne 0) { throw 'blocked' }
    $channel = 'Microsoft-Windows-TaskScheduler/Operational'
    $provider = 'Microsoft-Windows-TaskScheduler'
    $task = '\AITradingBot-PD4-UnattendedPaper-v1'
    $activationText = '2026-09-30T22:07:24.000000Z'
    $endText = '2026-10-07T22:07:24.000000Z'
    $MAX_CANDIDATE_RECORDS = 100000
    $MAX_TARGET_EVENTS = 256
    $culture = [Globalization.CultureInfo]::InvariantCulture
    $utcStyle = [Globalization.DateTimeStyles]::AdjustToUniversal -bor
        [Globalization.DateTimeStyles]::AssumeUniversal
    $activation = [datetime]::ParseExact($activationText, "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'", $culture, $utcStyle)
    $end = [datetime]::ParseExact($endText, "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'", $culture, $utcStyle)

    function Convert-HistoryUtc {
        param([string]$Text)
        # Parse ticks, then truncate the seventh (100-ns) digit, never round forward.
        if ($Text -cnotmatch '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,7})?Z$') {
            throw 'blocked'
        }
        $instant = [datetime]::Parse($Text, $culture, $utcStyle)
        $ticks = $instant.Ticks - ($instant.Ticks % 10)
        $canonical = [datetime]::new($ticks, [DateTimeKind]::Utc)
        return $canonical.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'", $culture)
    }

    function Read-HistoryXml {
        param($Record)
        # Disable DTD/entity resolution. Rendered messages are never read.
        $settings = [System.Xml.XmlReaderSettings]::new()
        $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
        $settings.XmlResolver = $null
        $reader = [System.Xml.XmlReader]::Create([System.IO.StringReader]::new($Record.ToXml()), $settings)
        try {
            $xml = [System.Xml.XmlDocument]::new()
            $xml.XmlResolver = $null
            $xml.Load($reader)
        } finally {
            $reader.Dispose()
        }
        $ns = [System.Xml.XmlNamespaceManager]::new($xml.NameTable)
        $ns.AddNamespace('e', 'http://schemas.microsoft.com/win/2004/08/events/event')
        return ,@($xml, $ns)
    }

    function Read-OneNode {
        param($Xml, $Ns, [string]$Query)
        $nodes = $Xml.SelectNodes($Query, $Ns)
        if ($nodes.Count -ne 1) { throw 'blocked' }
        return ,$nodes[0]
    }

    $logs = @(Get-WinEvent -ListLog $channel)
    if ($logs.Count -ne 1 -or $logs[0].LogName -cne $channel -or
        $logs[0].IsEnabled -isnot [bool]) { throw 'blocked' }
    $enabled = $logs[0].IsEnabled
    $oldest = $null
    $events = [System.Collections.Generic.List[object]]::new()
    # A disabled channel is reported without any enabling or query attempt.
    if ($enabled) {
        try {
            $retained = @(Get-WinEvent -LogName $channel -Oldest -MaxEvents 1)
        } catch {
            if ($_.FullyQualifiedErrorId -cne 'NoMatchingEventsFound,Microsoft.PowerShell.Commands.GetWinEventCommand') { throw }
            $retained = @()
        }
        if ($retained.Count -gt 1) { throw 'blocked' }
        if ($retained.Count -eq 1) {
            $parsed = Read-HistoryXml $retained[0]
            $retainedChannel = Read-OneNode $parsed[0] $parsed[1] '/e:Event/e:System/e:Channel'
            if ($retainedChannel.InnerText -cne $channel) { throw 'blocked' }
            $time = Read-OneNode $parsed[0] $parsed[1] '/e:Event/e:System/e:TimeCreated'
            $oldest = Convert-HistoryUtc $time.GetAttribute('SystemTime')
        }
        $filter = @{
            LogName = $channel
            Id = @(100, 102, 107, 110)
            StartTime = $activation
            EndTime = $end
        }
        $count = 0
        try {
            # The extra record detects overflow; never truncate and claim completeness.
            Get-WinEvent -FilterHashtable $filter -Oldest -MaxEvents ($MAX_CANDIDATE_RECORDS + 1) | ForEach-Object {
                $count += 1
                if ($count -gt $MAX_CANDIDATE_RECORDS) { throw 'blocked' }
                $parsed = Read-HistoryXml $_
                $xml = $parsed[0]
                $ns = $parsed[1]
                $providerNode = Read-OneNode $xml $ns '/e:Event/e:System/e:Provider'
                $channelNode = Read-OneNode $xml $ns '/e:Event/e:System/e:Channel'
                if ($providerNode.GetAttribute('Name') -cne $provider -or
                    $channelNode.InnerText -cne $channel) { throw 'blocked' }
                $data = [System.Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
                foreach ($node in $xml.SelectNodes('/e:Event/e:EventData/e:Data', $ns)) {
                    $name = $node.GetAttribute('Name')
                    if ($name -ceq 'TaskName' -or $name -ceq 'InstanceId') {
                        if ($data.ContainsKey($name)) { throw 'blocked' }
                        $data.Add($name, $node.InnerText)
                    }
                }
                if (-not $data.ContainsKey('TaskName')) { throw 'blocked' }
                if ($data['TaskName'] -cne $task) { return }
                if (-not $data.ContainsKey('InstanceId')) { throw 'blocked' }
                $idNode = Read-OneNode $xml $ns '/e:Event/e:System/e:EventID'
                $recordNode = Read-OneNode $xml $ns '/e:Event/e:System/e:EventRecordID'
                $timeNode = Read-OneNode $xml $ns '/e:Event/e:System/e:TimeCreated'
                $id = [int]::Parse($idNode.InnerText, $culture)
                if ($id -notin @(100, 102, 107, 110)) { throw 'blocked' }
                $recordId = [ulong]::Parse($recordNode.InnerText, $culture)
                if ($recordId -eq 0) { throw 'blocked' }
                $instant = Convert-HistoryUtc $timeNode.GetAttribute('SystemTime')
                $eventTime = [datetime]::ParseExact($instant, "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'", $culture, $utcStyle)
                # Get-WinEvent EndTime is inclusive; the accepted soak is half-open.
                if ($eventTime -lt $activation) { throw 'blocked' }
                if ($eventTime -ge $end) {
                    if ($eventTime -ne $end) { throw 'blocked' }
                    return
                }
                $instance = [guid]::Parse($data['InstanceId']).ToString('D').ToLowerInvariant()
                if ($events.Count -ge $MAX_TARGET_EVENTS) { throw 'blocked' }
                $events.Add([ordered]@{
                    event_id = $id
                    record_id = $recordId
                    observed_at_utc = $instant
                    task_name = $task
                    instance_id = $instance
                })
            }
        } catch {
            if ($count -ne 0 -or $_.FullyQualifiedErrorId -cne 'NoMatchingEventsFound,Microsoft.PowerShell.Commands.GetWinEventCommand') { throw }
        }
    }
    $result = [ordered]@{
        schema = 'd10-scheduler-history-windows-observation/v1'
        status = 'OBSERVED'
        channel = $channel
        provider = $provider
        channel_enabled = $enabled
        oldest_retained_event_utc = $oldest
        collected_at_utc = [datetime]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'", $culture)
        events = @($events.ToArray())
    }
    $json = $result | ConvertTo-Json -Compress -Depth 6
    if ([Text.Encoding]::UTF8.GetByteCount($json) -gt (256 * 1024 - 2)) { throw 'blocked' }
    [Console]::Out.WriteLine($json)
    exit 0
} catch {
    [Console]::Error.WriteLine('d10_scheduler_history_observation_blocked')
    exit 1
}
