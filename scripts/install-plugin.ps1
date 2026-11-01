#requires -Version 7.0
[CmdletBinding()]
param(
    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$CodexCommand = 'codex',
    [string]$PythonCommand = 'python'
)

# Run from an ordinary user PowerShell. Uses only Codex's native installer;
# never edits config/cache directly or changes the current CODEX_HOME.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$stage = 'source-validation'
$registration = 'NOT_VERIFIED'

function Invoke-CodexJson {
    param([string[]]$Arguments)
    $global:LASTEXITCODE = $null
    $raw = & $CodexCommand @Arguments
    if ($null -eq $LASTEXITCODE -or $LASTEXITCODE -ne 0) {
        throw "Codex command failed during $stage (exit $LASTEXITCODE)."
    }
    return (($raw -join "`n") | ConvertFrom-Json -ErrorAction Stop)
}

function Canonical-Root {
    param([string]$Path)
    return ((Resolve-Path -LiteralPath $Path -ErrorAction Stop).ProviderPath).TrimEnd([char[]]'\/')
}

function Same-Root {
    param([string]$Left, [string]$Right)
    $comparison = [StringComparison]::Ordinal
    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
        $comparison = [StringComparison]::OrdinalIgnoreCase
    }
    return [string]::Equals((Canonical-Root $Left), (Canonical-Root $Right), $comparison)
}

try {
    $SourceRoot = Canonical-Root $SourceRoot
    # Reuse the package's scoped YAML parser, version and resource validation.
    # This path performs validation only, not build/install or GitNexus execution.
    $validation = @'
from pathlib import Path
import importlib.util, json, sys
sys.stdout.reconfigure(encoding="utf-8")
if sys.version_info < (3, 11):
    raise RuntimeError("Python 3.11 or newer is required")
root = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location("open_project_builder", root / "scripts/build-plugin.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
info, resources = module.source_files(root)
manifest = json.loads(resources["plugin.json"])
if info["edition"] != "codex" or manifest["name"] != "open-project-codex":
    raise ValueError("Expected the open-project-codex edition")
catalog = json.loads((root / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
if catalog["name"] != "open-project-codex":
    raise ValueError("Unexpected marketplace name")
matches = [p for p in catalog["plugins"] if p.get("name") == manifest["name"]]
if len(matches) != 1:
    raise ValueError("Expected exactly one matching catalog plugin")
source = matches[0]["source"]
if source.get("source") != "local" or (root / source["path"]).resolve() != root:
    raise ValueError("Catalog must install this exact local source root")
print(json.dumps({"name": manifest["name"], "version": manifest["version"]}))
'@
    $global:LASTEXITCODE = $null
    $sourceJson = & $PythonCommand -c $validation $SourceRoot
    if ($null -eq $LASTEXITCODE -or $LASTEXITCODE -ne 0) {
        throw 'Source validation failed; no Codex installation command was run.'
    }
    $source = ($sourceJson -join "`n") | ConvertFrom-Json -ErrorAction Stop
    $name = [string]$source.name

    $stage = 'marketplace-inspection'
    $catalogs = Invoke-CodexJson @('plugin', 'marketplace', 'list', '--json')
    $existing = @($catalogs.marketplaces | Where-Object { $_.name -ceq $name })
    if ($existing.Count -gt 1) { throw 'Ambiguous existing marketplace identity.' }
    if ($existing.Count -eq 1) {
        if (-not (Same-Root ([string]$existing[0].root) $SourceRoot)) {
            throw 'An existing same-name marketplace uses another source; it was not replaced.'
        }
        $registration = 'EXISTING'
    } else {
        $stage = 'marketplace-registration'
        $null = Invoke-CodexJson @('plugin', 'marketplace', 'add', $SourceRoot, '--json')
        $registration = 'REGISTERED'
    }

    $stage = 'plugin-installation'
    $null = Invoke-CodexJson @('plugin', 'add', "$name@$name", '--json')

    $stage = 'installation-verification'
    $state = Invoke-CodexJson @('plugin', 'list', '--marketplace', $name, '--available', '--json')
    $installed = @($state.installed | Where-Object { $_.pluginId -ceq "$name@$name" })
    if ($installed.Count -ne 1) { throw 'Expected exactly one installed plugin identity.' }
    $plugin = $installed[0]
    if ($plugin.installed -isnot [bool] -or -not $plugin.installed -or
        $plugin.enabled -isnot [bool] -or -not $plugin.enabled -or
        $plugin.version -cne $source.version -or $plugin.name -cne $name -or
        $plugin.marketplaceName -cne $name -or $plugin.source.source -cne 'local' -or
        -not (Same-Root ([string]$plugin.source.path) $SourceRoot)) {
        throw 'Installed version, enabled state or source identity did not match.'
    }
    [ordered]@{
        status = 'INSTALL_VERIFIED'
        plugin_id = "$name@$name"
        version = $source.version
        marketplace_registration = $registration
        enabled = $true
        allow_implicit_invocation = $false
        invocation_behavior_verified = $false
        note = 'Native installation and source policy verified; no model turn or GitNexus onboarding was run.'
    } | ConvertTo-Json
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    [ordered]@{
        status = 'INSTALL_NOT_VERIFIED'
        stage = $stage
        marketplace_registration = $registration
        installation_verified = $false
        note = 'No automatic rollback/removal was attempted; inspect native state before retrying a partial operation.'
    } | ConvertTo-Json
    exit 1
}
