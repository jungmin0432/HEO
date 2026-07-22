param(
    [ValidateSet("auto", "cpu", "cuda")]
    [string]$Device = "auto",
    [switch]$AllowDownload
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$vendorPath = Join-Path $projectRoot "vendor\location_matching_python"
$cachePath = Join-Path $projectRoot "cache\huggingface"

if (-not (Test-Path $vendorPath)) {
    throw "Missing location-matching dependencies. Install requirements-location-matching.txt into vendor\\location_matching_python first."
}

$env:PYTHONPATH = $vendorPath
$env:HF_HOME = $cachePath
$env:TRANSFORMERS_OFFLINE = if ($AllowDownload) { "0" } else { "1" }

$arguments = @("scripts\build_archive_feature_cache.py", "--device", $Device)
if ($AllowDownload) { $arguments += "--allow-download" }

& python @arguments
exit $LASTEXITCODE
