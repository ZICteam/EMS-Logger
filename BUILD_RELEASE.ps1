$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

python -m PyInstaller --clean "$root\EMS_Screen.spec"

$releaseDir = Join-Path $root "release"
$packageDir = Join-Path $releaseDir "EMS_Logger_v2.0_Windows"
$zipPath = Join-Path $releaseDir "EMS_Logger_v2_0_Windows.zip"

if (Test-Path $packageDir) {
    Remove-Item -LiteralPath $packageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $packageDir | Out-Null

Copy-Item -LiteralPath "$root\dist\EMS_Screen.exe" -Destination "$packageDir\EMS_Screen.exe" -Force
Copy-Item -LiteralPath "$root\README.md" -Destination "$packageDir\README.md" -Force
Copy-Item -LiteralPath "$root\RELEASE_NOTES.md" -Destination "$packageDir\RELEASE_NOTES.md" -Force
Copy-Item -LiteralPath "$root\config.example.json" -Destination "$packageDir\config.example.json" -Force

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($packageDir, $zipPath)

Write-Host "Release package created: $zipPath"
