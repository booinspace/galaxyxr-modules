param([Parameter(Mandatory=$true)][ValidateSet('SteamLink','RootRelay','VirtualDesktop','StockSteamLink')][string]$Provider)
$ErrorActionPreference = 'Stop'
$Modules = Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'VRCFaceTracking\CustomLibs'
$Ids = @{
    SteamLink='8dca1f59-17df-4a27-9e12-46f8fdc332c5'; RootRelay='699750bf-e217-4bd8-8039-3d5f97ee80ba';
    VirtualDesktop='91a90618-b020-4064-8832-809b2ca2b3bc'; StockSteamLink='2a8c8080-2a76-46af-bf76-1da7c0127ef8'
}
$Selected = Join-Path (Join-Path $Modules $Ids[$Provider]) 'module.json'
if (-not (Test-Path $Selected) -and -not (Test-Path ($Selected+'.disabled'))) { throw 'Provider is not installed' }
foreach ($Id in $Ids.Values) {
    $Json = Join-Path (Join-Path $Modules $Id) 'module.json'
    if ((Test-Path $Json) -and (Test-Path ($Json+'.disabled'))) { throw ('Conflicting provider metadata: '+$Id) }
}
$App = 'C:\Program Files (x86)\Steam\steamapps\common\VRCFaceTracking\VRCFaceTracking.exe'
if (-not (Test-Path $App)) { throw 'Open VRCFaceTracking from Steam after selecting this provider, or update the app path in this script.' }
Get-Process VRCFaceTracking* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
foreach ($Id in $Ids.Values) {
    $Json = Join-Path (Join-Path $Modules $Id) 'module.json'
    if (Test-Path $Json) { Move-Item -LiteralPath $Json -Destination ($Json+'.disabled') }
}
Move-Item -LiteralPath ($Selected+'.disabled') -Destination $Selected
Start-Process -FilePath $App -WorkingDirectory (Split-Path $App)
Write-Output ('Active face/eye provider: '+$Provider)
