# Requires the reviewed x64 Windows PowerShell 5.1 -NoLogo -NoProfile process.
# Ordinary invocation compiles the pinned source and prints description only.
[CmdletBinding(PositionalBinding = $false)]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($args.Count -ne 0) { throw 'This source-only helper accepts no arguments.' }
if ($PSVersionTable.PSVersion.Major -ne 5 -or
    $PSVersionTable.PSVersion.Minor -ne 1 -or
    -not [Environment]::Is64BitProcess) {
    throw 'The reviewed boundary requires 64-bit Windows PowerShell 5.1.'
}
if ('P3R1OrdinaryPrincipalV1.Launcher' -as [type]) {
    throw 'Helper type already loaded; start a fresh -NoProfile process.'
}

$helperPath = [IO.Path]::Combine($PSScriptRoot, 'p3_r1_ordinary_nonadmin_principal_ceremony.cs')
$helperBytes = [IO.File]::ReadAllBytes($helperPath)
$hasher = [Security.Cryptography.SHA256]::Create()
try {
    $helperHash = [BitConverter]::ToString($hasher.ComputeHash($helperBytes)).Replace('-', '').ToLowerInvariant()
}
finally { $hasher.Dispose() }
$expectedHelperHash = 'ea74bbb2b72869c5e884822333676e522828e1b2c0afb297d6c0559e32c07292'
if ($helperHash -cne $expectedHelperHash) { throw 'Reviewed helper source hash mismatch.' }
$helperText = (New-Object Text.UTF8Encoding($false, $true)).GetString($helperBytes)
$references = @(
    'System.dll',
    'System.Core.dll',
    [System.Management.Automation.PSObject].Assembly.Location
)
$namespaceMarker = 'namespace P3R1OrdinaryPrincipalV1'
if (($helperText.Split(@($namespaceMarker), [StringSplitOptions]::None)).Count -ne 2) {
    throw 'Unexpected helper namespace boundary.'
}
# Bind the already hash-verified input bytes to the compiled assembly. This
# deterministic metadata avoids putting a self-referential source hash in C#.
$sourceStamp = '[assembly: System.Reflection.AssemblyMetadata("P3R1ReviewedHelperSha256", "' + $helperHash + '")]'
$compilationText = $helperText.Replace($namespaceMarker, $sourceStamp + [Environment]::NewLine + $namespaceMarker)
Microsoft.PowerShell.Utility\Add-Type -TypeDefinition $compilationText -Language CSharp -ReferencedAssemblies $references -ErrorAction Stop

if (-not [P3R1OrdinaryPrincipalV1.Launcher]::ACCOUNT_EFFECT_EXECUTION_AUTHORIZED) {
    [P3R1OrdinaryPrincipalV1.Launcher]::Describe()
    return
}

# Future source-reviewed input function: absent from the ordinary disabled path.
# The helper invokes it synchronously in this same runspace. No argument accepts
# a password, identity, path, group, or authorization. The native helper owns the
# returned SecureString and its disposal, including failures after handoff.
function Read-P3R1CeremonySecureInput {
    if (-not [P3R1OrdinaryPrincipalV1.Launcher]::ACCOUNT_EFFECT_EXECUTION_AUTHORIZED) {
        throw 'Password input is not authorized.'
    }
    Microsoft.PowerShell.Utility\Read-Host -Prompt 'Dedicated test account password' -AsSecureString
}
[P3R1OrdinaryPrincipalV1.Launcher]::RunFutureCeremony()
