param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$BaseDeviceName = "Output A1 Voicemeeter",
    [double]$ProbeAmplitudeDbfs = 0.0,
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BaselineScript = Join-Path $PSScriptRoot "run_eapo_baseline.ps1"
$BranchScript = Join-Path $PSScriptRoot "run_eapo_bass_branches.ps1"
$SelectorPath = Join-Path $RepoRoot "JBL M2 Binaural Convolution\Bass Crossover Selector.txt"
$ExpectedSelection = "Include: main - A 100-sample advance.txt"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "measurements\minimum-latency\a100-reference\raw"
}

$ActiveSelections = @(
    Get-Content $SelectorPath |
        Where-Object { $_ -match "^\s*Include:" }
)
if (($ActiveSelections.Count -ne 1) -or ($ActiveSelections[0].Trim() -ne $ExpectedSelection)) {
    throw "A100 must be the only active renderer. Expected '$ExpectedSelection' in $SelectorPath."
}

$DigitalDirectory = Join-Path $OutputRoot "digital"
$BranchDirectory = Join-Path $OutputRoot "branches"

Write-Host "Capturing the accepted A100 complete response."
& $BaselineScript `
    -BenchmarkPath $BenchmarkPath `
    -DeviceName $BaseDeviceName `
    -ProbeAmplitudeDbfs $ProbeAmplitudeDbfs `
    -OutputDirectory $DigitalDirectory `
    -CaptureLabel "minimum-latency reference: A100 complete"

Write-Host ""
Write-Host "Capturing A100 combined, convolved, clean, and downstream matrices."
& $BranchScript `
    -BenchmarkPath $BenchmarkPath `
    -BaseDeviceName $BaseDeviceName `
    -ProbeAmplitudeDbfs $ProbeAmplitudeDbfs `
    -OutputRoot $BranchDirectory `
    -CombinedReferenceDirectory $DigitalDirectory `
    -CaptureLabel "minimum-latency reference: A100"

Write-Host ""
Write-Host "A100 renderer-reference capture complete: $OutputRoot"
Write-Host "Commit the raw directory and push it before running the macOS analysis."
