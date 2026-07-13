param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$BaseDeviceName = "Output A1 Voicemeeter",
    [double]$ProbeAmplitudeDbfs = 0.0,
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CaptureScript = Join-Path $PSScriptRoot "run_eapo_baseline.ps1"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "measurements\bass-branches\raw"
}

$Captures = @(
    @{ Name = "combined"; Suffix = "PhantomDSP Bass Combined" },
    @{ Name = "convolved"; Suffix = "PhantomDSP Bass Convolved" },
    @{ Name = "clean"; Suffix = "PhantomDSP Bass Clean" }
)

foreach ($Capture in $Captures) {
    $OutputDirectory = Join-Path $OutputRoot $Capture.Name
    $DeviceName = "$BaseDeviceName $($Capture.Suffix)"

    Write-Host ""
    Write-Host "Capturing $($Capture.Name) branch with device name: $DeviceName"
    & $CaptureScript `
        -BenchmarkPath $BenchmarkPath `
        -DeviceName $DeviceName `
        -ProbeAmplitudeDbfs $ProbeAmplitudeDbfs `
        -OutputDirectory $OutputDirectory `
        -SkipHeadroomSweep
}

$BaselineDirectory = Join-Path $RepoRoot "measurements\digital-baseline\raw"
$CombinedDirectory = Join-Path $OutputRoot "combined"
$BaselineCompared = $true
foreach ($OutputFile in @("left-output.wav", "right-output.wav")) {
    $BaselineFile = Join-Path $BaselineDirectory $OutputFile
    $CombinedFile = Join-Path $CombinedDirectory $OutputFile
    if ((Test-Path $BaselineFile -PathType Leaf) -and (Test-Path $CombinedFile -PathType Leaf)) {
        $BaselineHash = (Get-FileHash $BaselineFile -Algorithm SHA256).Hash
        $CombinedHash = (Get-FileHash $CombinedFile -Algorithm SHA256).Hash
        if ($BaselineHash -ne $CombinedHash) {
            throw "Combined $OutputFile does not match the checked-in digital baseline. Do not commit this capture until the configuration difference is understood."
        }
    } else {
        $BaselineCompared = $false
    }
}

Write-Host ""
Write-Host "Bass branch capture complete: $OutputRoot"
if ($BaselineCompared) {
    Write-Host "The combined capture matches the checked-in digital baseline."
} else {
    Write-Warning "The checked-in digital baseline was unavailable, so the combined capture was not compared."
}
Write-Host "Commit the raw directory, then run analyze_bass_branches.py on macOS."
