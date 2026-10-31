# Build dist\SkillWheel.exe (onefile, no console)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".build-venv\Scripts\python.exe")) {
    if (Get-Command uv -ErrorAction SilentlyContinue) { uv venv --python 3.12 .build-venv }
    else { python -m venv .build-venv }
}
$py = ".build-venv\Scripts\python.exe"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv pip install --python $py -r requirements.txt pyinstaller
} else {
    & $py -m pip install -r requirements.txt pyinstaller
}

& ".build-venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --windowed `
    --name SkillWheel --icon assets\skillwheel.ico --paths overlay `
    --exclude-module tkinter overlay\main.py
Write-Host "Built dist\SkillWheel.exe"
