#requires -Version 7.0
[CmdletBinding()]
param([string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
      [string]$CodexCommand = 'codex', [string]$PythonCommand = 'python')
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$hostRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
try {
    $global:LASTEXITCODE = $null
    $native = & $CodexCommand plugin list --marketplace open-project-codex --available --json
    if ($null -eq $LASTEXITCODE -or $LASTEXITCODE -ne 0) { throw 'Native plugin inspection failed.' }
    ($native -join "`n") | & $PythonCommand (Join-Path $SourceRoot 'scripts/verify-installation.py') --source-root $SourceRoot --host-root $hostRoot
    exit $LASTEXITCODE
} catch {
    @{status='INSTALLATION_INCOMPLETE';errors=@($_.Exception.Message);invocation_behavior_verified=$false} | ConvertTo-Json
    exit 1
}
