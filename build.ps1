$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required on the build machine; end users do not need Python or uv."
}

uv sync --dev
uv run pyinstaller --noconfirm --clean printer_desktop.spec
Write-Host "Build complete: $PSScriptRoot\dist\PrinterDesktop.exe"
