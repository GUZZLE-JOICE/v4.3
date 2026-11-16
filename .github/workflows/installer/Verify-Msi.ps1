[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $MsiPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $ExpectedPayloadPath
)

$ErrorActionPreference = 'Stop'

function Get-FileSha256([string] $Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

$msi = Get-Item -LiteralPath $MsiPath
$payload = Get-Item -LiteralPath $ExpectedPayloadPath
if ($msi.Length -lt 1MB) {
    throw "MSI is unexpectedly small: $($msi.FullName) ($($msi.Length) bytes)."
}

# An MSI is an OLE Compound File. This detects a ZIP or error response
# mislabeled as an MSI before it is uploaded as a release artifact.
$stream = [System.IO.File]::OpenRead($msi.FullName)
try {
    $header = New-Object byte[] 8
    if ($stream.Read($header, 0, $header.Length) -ne 8 -or
        ([BitConverter]::ToString($header) -ne 'D0-CF-11-E0-A1-B1-1A-E1')) {
        throw "MSI does not have the required Compound File signature: $([BitConverter]::ToString($header))"
    }
}
finally {
    $stream.Dispose()
}

# Open the MSI database and read a real table.
$installer = $null
$database = $null
$view = $null
$record = $null
try {
    $installerType = [Type]::GetTypeFromProgID('WindowsInstaller.Installer')
    if ($null -eq $installerType) {
        throw 'Windows Installer automation is unavailable on this runner.'
    }
    $installer = [Activator]::CreateInstance($installerType)
    $database = $installer.OpenDatabase($msi.FullName, 0)
    $view = $database.OpenView("SELECT `Value` FROM `Property` WHERE `Property` = 'ProductCode'")
    $view.Execute()
    $record = $view.Fetch()
    if ($null -eq $record -or [string]::IsNullOrWhiteSpace($record.StringData(1))) {
        throw 'MSI database has no ProductCode property.'
    }
}
finally {
    foreach ($comObject in @($record, $view, $database, $installer)) {
        if ($null -ne $comObject -and [System.Runtime.InteropServices.Marshal]::IsComObject($comObject)) {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($comObject)
        }
    }
}

# Extract the MSI administrative image without installing the product.
$adminTarget = Join-Path ([System.IO.Path]::GetTempPath()) ("jarvis-msi-verify-" + [guid]::NewGuid())
$adminLog = Join-Path ([System.IO.Path]::GetTempPath()) ("jarvis-msi-admin-" + [guid]::NewGuid() + ".log")
try {
    New-Item -ItemType Directory -Path $adminTarget | Out-Null

    # Capture Process.ExitCode directly; $LASTEXITCODE was unset in the failed run.
    $msiexecPath = Join-Path $env:SystemRoot 'System32\msiexec.exe'
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $msiexecPath
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true

    foreach ($argument in @('/a', $msi.FullName, '/qn', '/l*v', $adminLog, "TARGETDIR=$adminTarget")) {
        [void]$startInfo.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::Start($startInfo)
    $process.WaitForExit()
    $adminExitCode = $process.ExitCode
    $process.Dispose()

    if ($adminExitCode -ne 0) {
        $logExcerpt = if (Test-Path -LiteralPath $adminLog) {
            (Get-Content -LiteralPath $adminLog -Tail 80 | Out-String).Trim()
        } else {
            "Windows Installer did not create its verbose log at: $adminLog"
        }
        throw "Windows Installer administrative extraction failed with exit code $adminExitCode.`nMSI log: $adminLog`n$logExcerpt"
    }

    $extracted = Get-ChildItem -LiteralPath $adminTarget -Filter JARVIS.exe -File -Recurse |
        Select-Object -First 1
    if ($null -eq $extracted) {
        throw 'Administrative extraction completed but did not contain JARVIS.exe.'
    }
    if ((Get-FileSha256 $extracted.FullName) -ne (Get-FileSha256 $payload.FullName)) {
        throw 'The JARVIS.exe extracted from the MSI does not match dist/JARVIS.exe.'
    }
}
finally {
    if (Test-Path -LiteralPath $adminTarget) {
        Remove-Item -LiteralPath $adminTarget -Recurse -Force
    }
}

[pscustomobject]@{
    MsiPath       = $msi.FullName
    MsiSha256     = Get-FileSha256 $msi.FullName
    MsiBytes      = $msi.Length
    PayloadSha256 = Get-FileSha256 $payload.FullName
}
