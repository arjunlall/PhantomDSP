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
$ExpectedPrototype = "Include: main - D200 unified prototype.txt"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "measurements\minimum-latency\d200-prototype\raw"
}

$ActiveSelections = @(
    Get-Content $SelectorPath |
        Where-Object { $_ -match "^\s*Include:" }
)
if (($ActiveSelections -notcontains $ExpectedPrototype) -or
    ($ActiveSelections[-1].Trim() -ne $ExpectedDefault)) {
    throw "Expected the reserved D200 v1 route and accepted D200 A-matched playback default in $SelectorPath."
}

$DeviceName = "$BaseDeviceName PhantomDSP D200 Prototype"
Write-Host "Capturing the rejected D200 v1 diagnostic: $DeviceName"
& $CaptureScript `
    -BenchmarkPath $BenchmarkPath `
    -DeviceName $DeviceName `
    -ProbeAmplitudeDbfs 0.0 `
    -OutputDirectory $OutputDirectory `
    -CaptureLabel "minimum-latency prototype: D200 unified"

$LogPath = Join-Path $OutputDirectory "benchmark.log"
$Log = Get-Content $LogPath -Raw
if ($Log -notmatch [regex]::Escape("main - D200 unified prototype.txt")) {
    throw "Benchmark did not load the D200 prototype."
}
if ($Log -match [regex]::Escape("main - A 100-sample advance.txt")) {
    throw "Benchmark unexpectedly loaded A100 during the D200 capture."
}
if ($Log -match [regex]::Escape("main - D200 A-matched prototype.txt")) {
    throw "Benchmark unexpectedly loaded the accepted D200 A-matched renderer during the v1 capture."
}
if ($Log -match "samples clipped!") {
    throw "D200 Benchmark capture clipped. Do not commit the result."
}

Write-Host ""
Write-Host "D200 prototype capture complete: $OutputDirectory"
Write-Host "Commit the raw directory and push it before running the macOS comparison."
