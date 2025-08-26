Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Install-UvIfMissing {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host 'uv not found. Installing uv...' -ForegroundColor Yellow
        Invoke-WebRequest https://astral.sh/uv/install.ps1 -UseBasicParsing | Invoke-Expression
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'uv installation failed or not on PATH. Restart your shell or ensure $HOME\.local\bin is on PATH.'
    }
}

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
try {
    Set-Location ..
    Install-UvIfMissing
    if (-not (Test-Path 'uv.lock')) {
        Write-Host 'Generating uv.lock from pyproject.toml...' -ForegroundColor Cyan
        uv lock
    }
    Write-Host 'Syncing environment with uv (uses .venv) ...' -ForegroundColor Cyan
    uv sync
    Write-Host 'Done.' -ForegroundColor Green
    Write-Host 'Run the app with:' -ForegroundColor Yellow
    Write-Host '  uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080'
}
finally {
    Pop-Location
}
