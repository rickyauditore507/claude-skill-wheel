# Skill Wheel installer (Windows)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv venv --python 3.12 .venv
        uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    } else {
        python -m venv .venv
        & .venv\Scripts\python.exe -m pip install --upgrade pip
        & .venv\Scripts\python.exe -m pip install -r requirements.txt
    }
}

$extVersion = (Get-Content extension\package.json -Raw | ConvertFrom-Json)
$target = Join-Path $env:USERPROFILE ".vscode\extensions\ricky.skill-wheel-$($extVersion.version)"
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item extension\package.json, extension\extension.js, extension\README.md,
          extension\CHANGELOG.md, extension\LICENSE, extension\.vscodeignore `
          -Destination $target -Force
Write-Host "Extension installed to $target"
Write-Host "Run 'Developer: Reload Window' in VS Code, then hold Ctrl+Alt+Space."
