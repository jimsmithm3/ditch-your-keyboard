# Clean onefile build. Run from anywhere:  .\scripts\build_exe.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Missing $Python — create the venv and pip install -r requirements.txt first."
}

foreach ($dir in @("build", "dist")) {
    if (Test-Path $dir) {
        Remove-Item -Recurse -Force $dir
    }
}

& $Python -m PyInstaller --noconfirm --clean (Join-Path $Root "gspraudio.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Built $(Join-Path $Root 'dist\gspraudio.exe')"
