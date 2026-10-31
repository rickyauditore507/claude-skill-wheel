# Install the standalone app (no VS Code needed)
param([switch]$Autostart)
$ErrorActionPreference = "Stop"
$src = Join-Path $PSScriptRoot "dist\SkillWheel.exe"
if (-not (Test-Path $src)) {
    throw "dist\SkillWheel.exe not found. Run build-standalone.ps1 first."
}
$dir = Join-Path $env:LOCALAPPDATA "SkillWheel"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item $src (Join-Path $dir "SkillWheel.exe") -Force
$exe = Join-Path $dir "SkillWheel.exe"
if ($Autostart) { & $exe --install-autostart | Out-Null }
Start-Process $exe
Write-Host "Installed to $dir"
Write-Host "Tray icon: hold Ctrl+Alt+Space in any app (Claude Code terminal, browser, editor)."
