param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$BaseDeviceName = "Output A1 Voicemeeter",
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CaptureScript = Join-Path $PSScriptRoot "run_eapo_baseline.ps1"
$SelectorPath = Join-Path $RepoRoot "JBL M2 Binaural Convolution\Bass Crossover Selector.txt"
$ExpectedSelection = "Include: main - A 100-sample advance.txt"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "measurements\minimum-latency\a100-reference\raw\precision-branches"
}

$ActiveSelections = @(
    Get-Content $SelectorPath |
        Where-Object { $_ -match "^\s*Include:" }
)
if (($ActiveSelections.Count -eq 0) -or ($ActiveSelections[-1].Trim() -ne $ExpectedSelection)) {
    throw "A100 must be the normal playback renderer. Expected the last active include to be '$ExpectedSelection' in $SelectorPath."
}

$Captures = @(
    @{
        Name = "convolved"
        Suffix = "PhantomDSP Precision Convolution"
        OutputGainDb = 24.0
    },
    @{
        Name = "clean"
        Suffix = "PhantomDSP Precision CleanLow"
        OutputGainDb = 48.0
    }
)

foreach ($Capture in $Captures) {
    $OutputDirectory = Join-Path $OutputRoot $Capture.Name
    $DeviceName = "$BaseDeviceName $($Capture.Suffix)"

    Write-Host ""
    Write-Host "Capturing $($Capture.Name) at +$($Capture.OutputGainDb) dB: $DeviceName"
    & $CaptureScript `
        -BenchmarkPath $BenchmarkPath `
        -DeviceName $DeviceName `
        -ProbeAmplitudeDbfs -6.0 `
        -OutputDirectory $OutputDirectory `
        -CaptureLabel "minimum-latency reference: A100 precision $($Capture.Name)" `
        -RecordedOutputGainDb $Capture.OutputGainDb `
        -SkipHeadroomSweep

    $LogPath = Join-Path $OutputDirectory "benchmark.log"
    if (Select-String -Path $LogPath -Pattern "samples clipped!" -Quiet) {
        throw "$($Capture.Name) precision capture clipped. Do not commit the result."
    }
}

Write-Host ""
Write-Host "Precision branch capture complete: $OutputRoot"
Write-Host "Commit the raw directory and push it before running the macOS analysis."
