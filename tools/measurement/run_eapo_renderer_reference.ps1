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
$PersonalizedConfig = Join-Path $RepoRoot "config - personalized.txt"
$SelectorPath = Join-Path $RepoRoot "tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt"
$ExpectedRouter = "Include: tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt"
$ExpectedReference = "Include: ..\..\..\JBL M2 Binaural Convolution\Legacy Parallel Bass Reference.txt"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "measurements\minimum-latency\legacy-reference\raw"
}

$RendererSelections = @(
    Get-Content $PersonalizedConfig |
        Where-Object { $_ -match "^\s*Include:\s+(JBL M2 Binaural Convolution|tools\\measurement\\equalizerapo)\\" }
)
$RouterSelections = @(
    Get-Content $SelectorPath |
        Where-Object { $_ -match "^\s*Include:" }
)
if (($RendererSelections.Count -ne 1) -or
    ($RendererSelections[0].Trim() -ne $ExpectedRouter) -or
    ($RouterSelections.Count -eq 0) -or
    ($RouterSelections[-1].Trim() -ne $ExpectedReference)) {
    throw "Temporarily select the historical benchmark router in $PersonalizedConfig; its default must remain the legacy parallel-bass reference."
}

$DigitalDirectory = Join-Path $OutputRoot "digital"
$BranchDirectory = Join-Path $OutputRoot "branches"

Write-Host "Capturing the frozen legacy renderer reference response."
& $BaselineScript `
    -BenchmarkPath $BenchmarkPath `
    -DeviceName $BaseDeviceName `
    -ProbeAmplitudeDbfs $ProbeAmplitudeDbfs `
    -OutputDirectory $DigitalDirectory `
    -CaptureLabel "legacy renderer reference: complete"

Write-Host ""
Write-Host "Capturing legacy combined, convolved, clean, and downstream matrices."
& $BranchScript `
    -BenchmarkPath $BenchmarkPath `
    -BaseDeviceName $BaseDeviceName `
    -ProbeAmplitudeDbfs $ProbeAmplitudeDbfs `
    -OutputRoot $BranchDirectory `
    -CombinedReferenceDirectory $DigitalDirectory `
    -CaptureLabel "legacy renderer reference"

Write-Host ""
Write-Host "Legacy renderer-reference capture complete: $OutputRoot"
Write-Host "Commit the raw directory and push it before running the macOS analysis."
