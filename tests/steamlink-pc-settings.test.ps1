# Source-only checks: no SteamVR files or live processes are changed.
[CmdletBinding()]
param([string]$ScriptText)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
if ([string]::IsNullOrEmpty($ScriptText)) {
    $path = Join-Path $PSScriptRoot '..\companions\steamlink\pc-settings\Apply-SteamLink-GalaxyXR-PC-Settings.ps1'
    $ScriptText = [IO.File]::ReadAllText($path)
}
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseInput($ScriptText, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw ($parseErrors | Out-String) }
function Assert-True {
    param([bool]$Value, [string]$Message)
    if (-not $Value) { throw $Message }
}
foreach ($name in @('ConvertFrom-SteamVrJson', 'Set-JsonProperty', 'Assert-SteamVrStopped')) {
    $definition = $ast.Find({ param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true)
    Assert-True ($null -ne $definition) ('Missing function: ' + $name)
    Invoke-Expression $definition.Extent.Text
}
$marker = '__test_infinity__'
$value = ConvertFrom-SteamVrJson '{"positive":1e+9999,"negative":-1e+9999,"literal":"1e+9999","keep":{"enabled":true}}' $marker
Assert-True ($value.positive -eq ($marker + '1e+9999')) 'Positive infinity was lost'
Assert-True ($value.negative -eq ($marker + '-1e+9999')) 'Negative infinity was lost'
Assert-True ($value.literal -eq '1e+9999') 'A quoted string was changed'
Set-JsonProperty $value 'targetBandwidth' 600
Set-JsonProperty $value 'targetBandwidth' 1000
Assert-True ($value.targetBandwidth -eq 1000 -and $value.keep.enabled) 'Property update damaged unrelated data'
$acceptedBadJson = $false
try { $null = ConvertFrom-SteamVrJson '{broken}' $marker; $acceptedBadJson = $true } catch {}
Assert-True (-not $acceptedBadJson) 'Malformed JSON was accepted'
$modeSwitch = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.SwitchStatementAst] -and $node.Condition.Extent.Text -eq '$Mode'
}, $true)
Assert-True ($null -ne $modeSwitch) 'Missing profile selection'
$profiles = @{
    Stable=@(2048,1536,250); Quality=@(2560,1536,300); High=@(3072,1536,300)
    Highest=@(3072,1536,600); Ultra=@(4032,1536,1000)
}
foreach ($mode in $profiles.Keys) {
    $result = & {
        param($Mode, $Code)
        Invoke-Expression $Code
        @($encodeWidth, $streamFormatWidth, $bandwidth)
    } $mode $modeSwitch.Extent.Text
    Assert-True (($result -join ',') -eq ($profiles[$mode] -join ',')) ('Wrong profile: ' + $mode)
}
Assert-True ($ScriptText -match '\[5\].*Highest.*600 Mbit/s') 'Highest menu disagrees with the profile'
Assert-True ($ScriptText -match '\[6\].*Ultra.*1000 Mbit/s') 'Ultra menu disagrees with the profile'
# Replace only this test process's command lookup; the real guard must reject it.
function Get-Process { [CmdletBinding()]param() [pscustomobject]@{ ProcessName='vrserver' } }
$blocked = $false
try { Assert-SteamVrStopped } catch { $blocked = $_.Exception.Message -like '*Close SteamVR*' }
Assert-True $blocked 'The running-SteamVR guard did not refuse a write'
Write-Output 'PASS: PowerShell syntax, JSON parsing, property preservation, five profiles, menu values and process guard'
