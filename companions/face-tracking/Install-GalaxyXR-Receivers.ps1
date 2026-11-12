# Installs the official compdoge receivers; leaves exactly one provider discoverable.
param([string]$DownloadDirectory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$Data = Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'VRCFaceTracking'
$Modules = Join-Path $Data 'CustomLibs'
$Profiles = Join-Path $Data 'GalaxyXR-Providers'
$Backup = Join-Path $Profiles ('Backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$Releases = @(
    @{ File='GalaxyXR-SteamLink-VRCFT-Module-v1.0.1.zip'; Hash='e7813a8f27d2c78819858cf5f749909deb30d90fc4fb29fc955b61ffd1f8dc55'; Url='https://github.com/compdoge/LinkFT/releases/download/gxr-facebridge-v1.0.1/GalaxyXR-SteamLink-VRCFT-Module-v1.0.1.zip'; Id='8dca1f59-17df-4a27-9e12-46f8fdc332c5' },
    @{ File='ALVRModule-v1.4.0.zip'; Hash='63e453f06315a7ab3c917e9ca5e5912b4b42966fbcc348588454daac94bb2179'; Url='https://github.com/compdoge/VRCFT-ALVR-UE/releases/download/v1.4.0/ALVRModule.zip'; Id='699750bf-e217-4bd8-8039-3d5f97ee80ba' }
)
$Stage = Join-Path $env:TEMP ('GalaxyXR-VRCFT-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Stage -Force | Out-Null
try {
    foreach ($Release in $Releases) {
        $Archive = Join-Path $DownloadDirectory $Release.File
        if (-not (Test-Path -LiteralPath $Archive)) {
            $Archive = Join-Path $Stage $Release.File
            Invoke-WebRequest -UseBasicParsing -Uri $Release.Url -OutFile $Archive
        }
        if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Release.Hash) { throw ('Checksum mismatch: ' + $Release.File) }
        Expand-Archive -LiteralPath $Archive -DestinationPath (Join-Path $Stage $Release.Id)
    }
    $Link = Join-Path $Stage $Releases[0].Id
    $Metadata = Get-Content (Join-Path $Link 'module.json') -Raw | ConvertFrom-Json
    if ($Metadata.ModuleId -ne $Releases[0].Id -or -not (Test-Path (Join-Path $Link 'SteamLinkVRCFTModule.dll'))) { throw 'Invalid LinkFT release layout' }
    $Metadata | Add-Member -NotePropertyName IsLocal -NotePropertyValue $true -Force
    $Metadata | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $Link 'module.json') -Encoding UTF8
    $RootRelay = Join-Path $Stage $Releases[1].Id
    if (-not (Test-Path (Join-Path $RootRelay 'ALVRModule.dll'))) { throw 'Invalid root receiver release layout' }
    @{
        ModuleId=$Releases[1].Id; ModuleName='Galaxy XR Root Relay (compdoge)'; Version='1.4.0';
        AuthorName='zmerp, curoviyxru; Galaxy XR adaptation by compdoge'; DllFileName='ALVRModule.dll'; IsLocal=$true;
        ModuleDescription='Receives UniExpr eye and face data from gxr-root-ft; no ALVR streamer needed.';
        ModulePageUrl='https://github.com/compdoge/VRCFT-ALVR-UE'; DownloadUrl=$Releases[1].Url;
        UsageInstructions='Select the RootRelay profile and start the headset relay. UDP 41463.'
    } | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $RootRelay 'module.json.disabled') -Encoding UTF8
    New-Item -ItemType Directory -Path $Backup,$Modules -Force | Out-Null
    Copy-Item -LiteralPath $Modules -Destination (Join-Path $Backup 'CustomLibs') -Recurse
    $Settings = Join-Path $Data 'VRCFaceTracking'
    if (Test-Path $Settings) { Copy-Item -LiteralPath $Settings -Destination (Join-Path $Backup 'Settings') -Recurse }
    Get-Process VRCFaceTracking* -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2
    foreach ($Release in $Releases) {
        $Destination = Join-Path $Modules $Release.Id
        if (Test-Path $Destination) { Remove-Item -LiteralPath $Destination -Recurse -Force }
        Move-Item -LiteralPath (Join-Path $Stage $Release.Id) -Destination $Destination
    }
    # The current VRCFT loader has no persisted provider-disable setting. A missing
    # module.json keeps a folder installed but undiscoverable across app restarts.
    foreach ($Id in @('2a8c8080-2a76-46af-bf76-1da7c0127ef8','91a90618-b020-4064-8832-809b2ca2b3bc')) {
        $Json = Join-Path (Join-Path $Modules $Id) 'module.json'
        if (Test-Path $Json) {
            if (Test-Path ($Json+'.disabled')) { throw ('Conflicting saved metadata: '+$Json) }
            Move-Item -LiteralPath $Json -Destination ($Json+'.disabled')
        }
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Select-GalaxyXR-Provider.ps1') -Destination $Profiles -Force
    foreach ($Provider in @('SteamLink','RootRelay','VirtualDesktop','StockSteamLink')) {
        $Command = '@echo off' + "`r`n" + 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Profiles 'Select-GalaxyXR-Provider.ps1') + '" -Provider ' + $Provider + "`r`npause`r`n"
        Set-Content -LiteralPath (Join-Path $Profiles ('Use-'+$Provider+'.cmd')) -Value $Command -Encoding ASCII
    }
    $Desktop = [Environment]::GetFolderPath('Desktop')
    foreach ($Provider in @('SteamLink','RootRelay')) {
        Copy-Item (Join-Path $Profiles ('Use-'+$Provider+'.cmd')) -Destination $Desktop -Force
    }
    Write-Output ('Backup='+$Backup)
    Write-Output ('Profiles='+$Profiles)
    Write-Output 'Installed LinkFT 1.0.1 (active) and ALVR-UE 1.4.0 (standby). Existing receivers preserved.'
} finally { Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue }
