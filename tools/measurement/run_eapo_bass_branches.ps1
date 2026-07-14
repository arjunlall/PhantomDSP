param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$BaseDeviceName = "Output A1 Voicemeeter",
    [double]$ProbeAmplitudeDbfs = 0.0,
    [string]$OutputRoot = "",
    [string]$CombinedReferenceDirectory = "",
    [string]$CaptureLabel = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CaptureScript = Join-Path $PSScriptRoot "run_eapo_baseline.ps1"
$ReferenceWasExplicit = -not [string]::IsNullOrWhiteSpace($CombinedReferenceDirectory)
$PersonalizedConfig = Join-Path $RepoRoot "config - personalized.txt"
$SelectorPath = Join-Path $RepoRoot "tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt"
$ExpectedRouter = "Include: tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt"
$ExpectedReference = "Include: ..\..\..\JBL M2 Binaural Convolution\Legacy Parallel Bass Reference.txt"

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
    throw "Bass-branch capture requires the historical benchmark router as the sole renderer include in $PersonalizedConfig."
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "measurements\bass-branches\raw"
}
if ([string]::IsNullOrWhiteSpace($CombinedReferenceDirectory)) {
    $CombinedReferenceDirectory = Join-Path $RepoRoot "measurements\digital-baseline\raw"
}

$Captures = @(
    @{ Name = "combined"; Suffix = "PhantomDSP Bass Combined" },
    @{ Name = "convolved"; Suffix = "PhantomDSP Bass Convolved" },
    @{ Name = "clean"; Suffix = "PhantomDSP Bass Clean" },
    @{ Name = "downstream"; Suffix = "PhantomDSP Bass Downstream" }
)

foreach ($Capture in $Captures) {
    $OutputDirectory = Join-Path $OutputRoot $Capture.Name
    $DeviceName = "$BaseDeviceName $($Capture.Suffix)"
    $BranchCaptureLabel = "bass branches: $($Capture.Name)"
    if (-not [string]::IsNullOrWhiteSpace($CaptureLabel)) {
        $BranchCaptureLabel = "$CaptureLabel / $($Capture.Name)"
    }

    Write-Host ""
    Write-Host "Capturing $($Capture.Name) branch with device name: $DeviceName"
    & $CaptureScript `
        -BenchmarkPath $BenchmarkPath `
        -DeviceName $DeviceName `
        -ProbeAmplitudeDbfs $ProbeAmplitudeDbfs `
        -OutputDirectory $OutputDirectory `
        -CaptureLabel $BranchCaptureLabel `
        -SkipHeadroomSweep
}

$CombinedDirectory = Join-Path $OutputRoot "combined"
$ReferenceCompared = $true
foreach ($OutputFile in @("left-output.wav", "right-output.wav")) {
    $ReferenceFile = Join-Path $CombinedReferenceDirectory $OutputFile
    $CombinedFile = Join-Path $CombinedDirectory $OutputFile
    if ((Test-Path $ReferenceFile -PathType Leaf) -and (Test-Path $CombinedFile -PathType Leaf)) {
        $ReferenceHash = (Get-FileHash $ReferenceFile -Algorithm SHA256).Hash
        $CombinedHash = (Get-FileHash $CombinedFile -Algorithm SHA256).Hash
        if ($ReferenceHash -ne $CombinedHash) {
            throw "Combined $OutputFile does not match the reference capture at $CombinedReferenceDirectory. Do not commit this capture until the configuration difference is understood."
        }
    } else {
        $ReferenceCompared = $false
    }
}

Write-Host ""
Write-Host "Bass branch capture complete: $OutputRoot"
if ($ReferenceCompared) {
    Write-Host "The combined capture matches the reference capture at $CombinedReferenceDirectory."
} elseif ($ReferenceWasExplicit) {
    throw "The explicit reference capture at $CombinedReferenceDirectory is incomplete or unavailable."
} else {
    Write-Warning "The reference capture was unavailable, so the combined capture was not compared."
}
Write-Host "Commit the raw directory, then run analyze_bass_branches.py on macOS."
