param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$BaseDeviceName = "Output A1 Voicemeeter",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CaptureScript = Join-Path $PSScriptRoot "run_eapo_baseline.ps1"
$PersonalizedConfig = Join-Path $RepoRoot "config - personalized.txt"
$ExpectedRenderer = "Include: Synthetic Reference Room\Presence Balanced Room Renderer.txt"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "measurements\synthetic-reference-room\presence-balanced\raw"
}

$RendererSelections = @(
    Get-Content $PersonalizedConfig |
        Where-Object { $_ -match "^\s*Include:\s+(JBL M2 Binaural Convolution|Synthetic Reference Room|tools\\measurement\\equalizerapo)\\" }
)
if (($RendererSelections.Count -ne 1) -or
    ($RendererSelections[0].Trim() -ne $ExpectedRenderer)) {
    throw "Expected the accepted presence-balanced renderer '$ExpectedRenderer' in $PersonalizedConfig."
}

$DeviceName = $BaseDeviceName
Write-Host "Capturing the accepted Presence Balanced Room renderer: $DeviceName"
& $CaptureScript `
    -BenchmarkPath $BenchmarkPath `
    -DeviceName $DeviceName `
    -ProbeAmplitudeDbfs 0.0 `
    -OutputDirectory $OutputDirectory `
    -CaptureLabel "accepted presence-balanced room renderer"

$LogPath = Join-Path $OutputDirectory "benchmark.log"
$Log = Get-Content $LogPath -Raw
if ($Log -notmatch [regex]::Escape("Presence Balanced Room Renderer.txt")) {
    throw "Benchmark did not load the accepted Presence Balanced Room renderer."
}
if ($Log -notmatch [regex]::Escape("Presence Balanced Room Left Speaker.wav") -or
    $Log -notmatch [regex]::Escape("Presence Balanced Room Right Speaker.wav")) {
    throw "Benchmark did not load both accepted speaker-to-ear IRs."
}
if ($Log -match [regex]::Escape("Legacy Parallel Bass Reference.txt")) {
    throw "Benchmark unexpectedly loaded the legacy reference renderer."
}
if ($Log -match [regex]::Escape("Speaker Virtualization.txt")) {
    throw "Benchmark unexpectedly loaded the prior measured-room production renderer."
}
if ($Log -match "samples clipped!") {
    throw "Accepted renderer Benchmark capture clipped. Do not commit the result."
}

Write-Host ""
Write-Host "Accepted renderer capture complete: $OutputDirectory"
Write-Host "Commit the raw directory and push it before running the macOS comparison."
