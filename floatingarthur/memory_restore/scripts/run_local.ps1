param(
    [int]$Port = 5050
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Create .venv and install requirements first."
}

Set-Location $projectRoot
& $python -m flask --app app:create_app run --host 127.0.0.1 --port $Port
