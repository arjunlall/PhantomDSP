param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$BaseDeviceName = "Output A1 Voicemeeter",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CaptureScript = Join-Path $PSScriptRoot "run_eapo_baseline.ps1"
$SelectorPath = Join-Path $RepoRoot "JBL M2 Binaural Convolution\Bass Crossover Selector.txt"
$ExpectedDefault = "Include: main - D200 A-matched prototype.txt"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "measurements\minimum-latency\d200-a-matched\raw"
}

$ActiveSelections = @(
    Get-Content $SelectorPath |
        Where-Object { $_ -match "^\s*Include:" }
)
if (($ActiveSelections.Count -eq 0) -or
    ($ActiveSelections[-1].Trim() -ne $ExpectedDefault)) {
    throw "Expected D200 A-matched as the accepted playback default in $SelectorPath."
}

$DeviceName = "$BaseDeviceName PhantomDSP D200 A-Matched"
Write-Host "Capturing the accepted D200 A-matched renderer: $DeviceName"
& $CaptureScript `
    -BenchmarkPath $BenchmarkPath `
    -DeviceName $DeviceName `
    -ProbeAmplitudeDbfs 0.0 `
    -OutputDirectory $OutputDirectory `
    -CaptureLabel "minimum-latency accepted renderer: D200 A-matched"

$LogPath = Join-Path $OutputDirectory "benchmark.log"
$Log = Get-Content $LogPath -Raw
if ($Log -notmatch [regex]::Escape("main - D200 A-matched prototype.txt")) {
    throw "Benchmark did not load the accepted D200 A-matched renderer."
}
if ($Log -match [regex]::Escape("main - A 100-sample advance.txt")) {
    throw "Benchmark unexpectedly loaded A100 during the D200 A-matched capture."
}
if ($Log -match [regex]::Escape("main - D200 unified prototype.txt")) {
    throw "Benchmark unexpectedly loaded the rejected D200 v1 renderer."
}
if ($Log -match "samples clipped!") {
    throw "D200 A-matched Benchmark capture clipped. Do not commit the result."
}

Write-Host ""
Write-Host "D200 A-matched capture complete: $OutputDirectory"
Write-Host "Commit the raw directory and push it before running the macOS comparison."
