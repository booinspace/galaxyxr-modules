param([string]$Output = "")
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Source = Join-Path $RepoRoot 'companions/vd-eye-fix'
$Cache = Join-Path $RepoRoot '.build/vd-eye-fix'
if (-not $Output) { $Output = Join-Path $RepoRoot 'releases/vd-eye-fix' }
New-Item -ItemType Directory -Force -Path $Cache, $Output | Out-Null
$Reference = Join-Path $Cache 'VRCFaceTracking.Core.dll'
$Expected = 'ad64d078fcc8a5772fb84eee69507142acdfe18a48fba7546c0252b638c22796'
if (-not (Test-Path $Reference) -or (Get-FileHash $Reference -Algorithm SHA256).Hash.ToLower() -ne $Expected) {
    Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/SinonVT/GalaxyXR-EyeTracking-Fix-Virtual-Desktop/51a482cc2ce903fc51d238d55f561dbedcae767a/3rdParty/VRCFaceTracking.Core.dll' -OutFile $Reference
}
if ((Get-FileHash $Reference -Algorithm SHA256).Hash.ToLower() -ne $Expected) { throw 'Pinned VRCFaceTracking reference mismatch' }
$Project = Join-Path $Source 'VirtualDesktop.FaceTracking.csproj'
& dotnet build $Project -c Release "-p:GxrCoreReferencePath=$Reference"
if ($LASTEXITCODE -ne 0) { throw 'Face-tracking module build failed' }
$Tests = Join-Path $RepoRoot 'tests/vd-eye-fix/GazeFix.Tests.csproj'
& dotnet build $Tests -c Release "-p:GxrCoreReferencePath=$Reference"
if ($LASTEXITCODE -ne 0) { throw 'Gaze test build failed' }
& dotnet (Join-Path $RepoRoot 'tests/vd-eye-fix/bin/Release/net8.0/GazeFix.Tests.dll')
if ($LASTEXITCODE -ne 0) { throw 'Gaze tests failed' }
Copy-Item (Join-Path $Source 'bin/Release/net7.0-windows/VirtualDesktop.FaceTracking.dll') $Output -Force
foreach ($Name in @('module.json','LICENSE','README.md','UPSTREAM.json')) {
    Copy-Item (Join-Path $Source $Name) $Output -Force
}
$Dll = Join-Path $Output 'VirtualDesktop.FaceTracking.dll'
$Hash = (Get-FileHash $Dll -Algorithm SHA256).Hash.ToLower()
"$Hash  VirtualDesktop.FaceTracking.dll" | Set-Content (Join-Path $Output 'SHA256SUMS') -Encoding ascii
$Package = Join-Path (Split-Path $Output -Parent) 'gxr-vd-eye-fix-0.1.0-windows.zip'
$PackageFiles = @($Dll) + @('module.json','LICENSE','README.md','UPSTREAM.json','SHA256SUMS') | ForEach-Object {
    if ([IO.Path]::IsPathRooted($_)) { $_ } else { Join-Path $Output $_ }
}
Compress-Archive -Path $PackageFiles -DestinationPath $Package -Force
$ZipHash = (Get-FileHash $Package -Algorithm SHA256).Hash.ToLower()
"$ZipHash  $([IO.Path]::GetFileName($Package))" | Set-Content "$Package.sha256" -Encoding ascii
Write-Host "$Package SHA256 $ZipHash"
