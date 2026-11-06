#requires -Version 7.0
[CmdletBinding()]
param([string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
      [string]$CodexCommand = 'codex', [string]$PythonCommand = 'python')
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$hostRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$helper = Join-Path $SourceRoot 'scripts/configure-jev-bypass.py'
$stage = 'source-validation'
$policy = $null
$installed = $null
$verification = $null
function Get-EffectiveInstructions {
    $override = Join-Path $hostRoot 'AGENTS.override.md'
    if ((Test-Path -LiteralPath $override) -and
        -not [string]::IsNullOrWhiteSpace((Get-Content -LiteralPath $override -Raw -Encoding utf8))) {
        return $override
    }
    return (Join-Path $hostRoot 'AGENTS.md')
}
try {
    $installer = Join-Path $SourceRoot 'scripts/install-plugin.ps1'
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'Native installer is missing; no host policy changed.' }
    $validation = @'
from pathlib import Path
import runpy, sys
root = Path(sys.argv[1]).resolve()
module = runpy.run_path(str(root / 'scripts/build-plugin.py'))
info, resources = module['source_files'](root)
if info['edition'] != 'codex':
    raise ValueError('Expected Codex source')
'@
    & $PythonCommand -c $validation $SourceRoot
    if ($LASTEXITCODE -ne 0) { throw 'Source validation failed; no host policy changed.' }
    $stage = 'policy-preflight'
    $instructions = Get-EffectiveInstructions
    $raw = & $PythonCommand $helper --instructions $instructions
    if ($LASTEXITCODE -ne 0) { throw "Policy preflight failed: $raw" }
    $preview = ($raw -join "`n") | ConvertFrom-Json
    # Authorized by choosing this explicitly named update entrypoint.
    $stage = 'policy-apply'
    $raw = & $PythonCommand $helper --instructions $instructions --apply --expected-sha256 $preview.before_sha256
    if ($LASTEXITCODE -ne 0) { throw "Policy update failed: $raw" }
    $policy = ($raw -join "`n") | ConvertFrom-Json
    $stage = 'native-installation'
    $raw = & $installer -SourceRoot $SourceRoot -CodexCommand $CodexCommand -PythonCommand $PythonCommand
    $installExit = $LASTEXITCODE
    $installed = ($raw -join "`n") | ConvertFrom-Json
    $stage = 'policy-verification'
    if ((Get-EffectiveInstructions) -cne $instructions) { throw 'Effective host instruction source changed; inspect before resuming.' }
    $raw = & $PythonCommand $helper --instructions $instructions
    if ($LASTEXITCODE -ne 0) { throw "Policy verification failed: $raw" }
    $current = ($raw -join "`n") | ConvertFrom-Json
    if (-not $current.active -or $current.before_sha256 -cne $policy.after_sha256) {
        throw 'Host policy changed during installation; not verified.'
    }
    $stage = 'installed-source-and-policy-verification'
    $raw = & (Join-Path $SourceRoot 'scripts/verify-installation.ps1') -SourceRoot $SourceRoot -CodexCommand $CodexCommand -PythonCommand $PythonCommand
    $verifyExit = $LASTEXITCODE
    $verification = ($raw -join "`n") | ConvertFrom-Json
    $ok = $installExit -eq 0 -and $verifyExit -eq 0 -and $verification.status -ceq 'SOURCE_AND_POLICY_VERIFIED'
    [ordered]@{status=if ($ok) {'SOURCE_AND_POLICY_VERIFIED'} else {'PARTIAL_INSTALL'};
        policy=$policy; installation=$installed; verification=$verification; invocation_behavior_verified=$false} | ConvertTo-Json -Depth 8
    if ($ok) { exit 0 } else { exit 1 }
} catch {
    [ordered]@{status=if ($null -ne $policy) {'PARTIAL_UPDATE'} else {'UPDATE_BLOCKED'};
        stage=$stage; policy=$policy; installation=$installed; verification=$verification;
        error=$_.Exception.Message; invocation_behavior_verified=$false} | ConvertTo-Json -Depth 8
    exit 1
}
