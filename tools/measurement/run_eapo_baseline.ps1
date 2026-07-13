param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$DeviceName = "Output A1 Voicemeeter",
    [double]$ProbeAmplitudeDbfs = 0.0,
    [string]$OutputDirectory = "",
    [string]$CaptureLabel = "",
    [switch]$SkipHeadroomSweep
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Get-CheckoutCommit {
    param([string]$RepositoryRoot)

    $GitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($null -ne $GitCommand) {
        $GitCommit = & $GitCommand.Source -C $RepositoryRoot rev-parse HEAD 2>$null
        if (($LASTEXITCODE -eq 0) -and ($GitCommit -match "^[0-9a-fA-F]{40}$")) {
            return $GitCommit.Trim()
        }
    }

    $HeadPath = Join-Path $RepositoryRoot ".git\HEAD"
    if (-not (Test-Path $HeadPath -PathType Leaf)) { return "unknown" }
    $Head = (Get-Content $HeadPath -Raw).Trim()
    if ($Head -match "^[0-9a-fA-F]{40}$") { return $Head }
    if ($Head -match "^ref:\s+(.+)$") { $RefName = $Matches[1] } else { return "unknown" }
    $RefPath = Join-Path (Join-Path $RepositoryRoot ".git") $RefName
    if (Test-Path $RefPath -PathType Leaf) { return (Get-Content $RefPath -Raw).Trim() }
    return "unknown"
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "measurements\digital-baseline\raw"
}

if (-not (Test-Path $BenchmarkPath -PathType Leaf)) {
    throw "Equalizer APO Benchmark was not found at: $BenchmarkPath"
}

if ($ProbeAmplitudeDbfs -eq 0.0) {
    $ProbeSetName = "0dbfs"
} elseif ($ProbeAmplitudeDbfs -eq -6.0) {
    $ProbeSetName = "minus-6dbfs"
} else {
    throw "Checked-in probes support only 0 or -6 dBFS. Use -ProbeAmplitudeDbfs 0 or -ProbeAmplitudeDbfs -6."
}

$ProbeDirectory = Join-Path $PSScriptRoot "probes\$ProbeSetName"
$ProbeFiles = @("left-input.wav", "right-input.wav", "probe-metadata.json")
foreach ($ProbeFile in $ProbeFiles) {
    $ProbePath = Join-Path $ProbeDirectory $ProbeFile
    if (-not (Test-Path $ProbePath -PathType Leaf)) {
        throw "Checked-in probe file was not found: $ProbePath"
    }
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
foreach ($ProbeFile in $ProbeFiles) {
    Copy-Item -Force (Join-Path $ProbeDirectory $ProbeFile) (Join-Path $OutputDirectory $ProbeFile)
}

$InstalledConfig = Join-Path (Split-Path -Parent $BenchmarkPath) "config\config.txt"
$RepoConfig = Join-Path $RepoRoot "config.txt"
if ((Test-Path $InstalledConfig) -and (Test-Path $RepoConfig)) {
    $InstalledConfigPath = (Resolve-Path $InstalledConfig).Path
    $RepoConfigPath = (Resolve-Path $RepoConfig).Path
    if ($InstalledConfigPath -ne $RepoConfigPath) {
        Write-Warning "Benchmark will process $InstalledConfigPath, not this checkout's $RepoConfigPath"
    }
}

$RecordedCaptureLabel = "unspecified"
if (-not [string]::IsNullOrWhiteSpace($CaptureLabel)) {
    $RecordedCaptureLabel = $CaptureLabel
}
$InstalledConfigHash = "missing"
if (Test-Path $InstalledConfig -PathType Leaf) {
    $InstalledConfigHash = (Get-FileHash $InstalledConfig -Algorithm SHA256).Hash
}
$SelectorPath = Join-Path (Split-Path -Parent $InstalledConfig) "JBL M2 Binaural Convolution\Bass Crossover Selector.txt"
$SelectorHash = "missing"
if (Test-Path $SelectorPath -PathType Leaf) {
    $SelectorHash = (Get-FileHash $SelectorPath -Algorithm SHA256).Hash
    Copy-Item -Force $SelectorPath (Join-Path $OutputDirectory "active-bass-selector.txt")
}

$LogPath = Join-Path $OutputDirectory "benchmark.log"
$Commit = Get-CheckoutCommit -RepositoryRoot $RepoRoot

@(
    "PhantomDSP commit: $Commit"
    "Capture label: $RecordedCaptureLabel"
    "Benchmark: $BenchmarkPath"
    "Device name: $DeviceName"
    "Installed config: $InstalledConfig"
    "Installed config SHA256: $InstalledConfigHash"
    "Bass selector: $SelectorPath"
    "Bass selector SHA256: $SelectorHash"
    "Probe set: $ProbeSetName ($ProbeAmplitudeDbfs dBFS)"
    ""
) | Set-Content -Path $LogPath -Encoding UTF8

function Invoke-EapoBenchmark {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    if ($script:BenchmarkSectionCount -gt 0) {
        "" | Add-Content -Path $LogPath -Encoding UTF8
    }
    $script:BenchmarkSectionCount++
    $Header = "=== $Name ==="
    Write-Host $Header
    $Header | Add-Content -Path $LogPath -Encoding UTF8

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $BenchmarkOutput = & $BenchmarkPath --devicename $DeviceName --nopause --verbose @Arguments 2>&1
        $ExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    foreach ($Line in $BenchmarkOutput) {
        $Text = $Line.ToString()
        Write-Host $Text
        $Text | Add-Content -Path $LogPath -Encoding UTF8
    }
    if ($ExitCode -ne 0) {
        throw "$Name failed with exit code $ExitCode"
    }
}

$LeftInput = Join-Path $OutputDirectory "left-input.wav"
$RightInput = Join-Path $OutputDirectory "right-input.wav"
$LeftOutput = Join-Path $OutputDirectory "left-output.wav"
$RightOutput = Join-Path $OutputDirectory "right-output.wav"
$HeadroomOutput = Join-Path $env:TEMP "phantomdsp-headroom-output.wav"
$script:BenchmarkSectionCount = 0

Invoke-EapoBenchmark -Name "left impulse" -Arguments @(
    "--input", $LeftInput,
    "--output", $LeftOutput
)
Invoke-EapoBenchmark -Name "right impulse" -Arguments @(
    "--input", $RightInput,
    "--output", $RightOutput
)
if (-not $SkipHeadroomSweep) {
    Invoke-EapoBenchmark -Name "correlated stereo sweep" -Arguments @(
        "--rate", "48000",
        "--channels", "2",
        "--length", "10",
        "--from", "20",
        "--to", "20000",
        "--output", $HeadroomOutput
    )

    Remove-Item $HeadroomOutput -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Baseline capture complete: $OutputDirectory"
Write-Host "Commit the raw directory, then run analyze_baseline.py on macOS."
