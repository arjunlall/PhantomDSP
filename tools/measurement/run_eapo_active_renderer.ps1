param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$BaseDeviceName = "Output A1 Voicemeeter",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CaptureScript = Join-Path $PSScriptRoot "run_eapo_baseline.ps1"
$PersonalizedConfig = Join-Path $RepoRoot "config - personalized.txt"
$ExpectedRenderer = "Include: JBL M2 Binaural Convolution\Speaker Virtualization.txt"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "measurements\minimum-latency\accepted-renderer\raw"
}

$RendererSelections = @(
    Get-Content $PersonalizedConfig |
        Where-Object { $_ -match "^\s*Include:\s+(JBL M2 Binaural Convolution|tools\\measurement\\equalizerapo)\\" }
)
if (($RendererSelections.Count -ne 1) -or
    ($RendererSelections[0].Trim() -ne $ExpectedRenderer)) {
    throw "Expected the condition-free production renderer '$ExpectedRenderer' in $PersonalizedConfig."
}

$DeviceName = $BaseDeviceName
Write-Host "Capturing the accepted Speaker Virtualization renderer: $DeviceName"
& $CaptureScript `
    -BenchmarkPath $BenchmarkPath `
    -DeviceName $DeviceName `
    -ProbeAmplitudeDbfs 0.0 `
    -OutputDirectory $OutputDirectory `
    -CaptureLabel "accepted speaker virtualization renderer"

$LogPath = Join-Path $OutputDirectory "benchmark.log"
$Log = Get-Content $LogPath -Raw
if ($Log -notmatch [regex]::Escape("Speaker Virtualization.txt")) {
    throw "Benchmark did not load the accepted Speaker Virtualization renderer."
}
if ($Log -notmatch [regex]::Escape("Left Speaker to Both Ears.wav") -or
    $Log -notmatch [regex]::Escape("Right Speaker to Both Ears.wav")) {
    throw "Benchmark did not load both accepted speaker-to-ear IRs."
}
if ($Log -match [regex]::Escape("Legacy Parallel Bass Reference.txt")) {
    throw "Benchmark unexpectedly loaded the legacy reference renderer."
}
if ($Log -match "samples clipped!") {
    throw "Accepted renderer Benchmark capture clipped. Do not commit the result."
}

Write-Host ""
Write-Host "Accepted renderer capture complete: $OutputDirectory"
Write-Host "Commit the raw directory and push it before running the macOS comparison."
