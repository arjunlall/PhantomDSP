param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$BaseDeviceName = "Output A1 Voicemeeter",
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CaptureScript = Join-Path $PSScriptRoot "run_eapo_baseline.ps1"
$PersonalizedConfig = Join-Path $RepoRoot "config - personalized.txt"
$SelectorPath = Join-Path $RepoRoot "tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt"
$ExpectedRouter = "Include: tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt"
$ExpectedReference = "Include: ..\..\..\JBL M2 Binaural Convolution\Legacy Parallel Bass Reference.txt"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "measurements\minimum-latency\legacy-reference\raw\precision-branches"
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
        -CaptureLabel "legacy renderer reference: precision $($Capture.Name)" `
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
