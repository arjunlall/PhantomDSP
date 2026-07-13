param(
    [string]$BenchmarkPath = "$env:ProgramFiles\EqualizerAPO\Benchmark.exe",
    [string]$DeviceName = "Output A1 Voicemeeter",
    [double]$ProbeAmplitudeDbfs = 0.0,
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Generator = Join-Path $PSScriptRoot "generate_probes.py"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "measurements\digital-baseline\raw"
}

if (-not (Test-Path $BenchmarkPath -PathType Leaf)) {
    throw "Equalizer APO Benchmark was not found at: $BenchmarkPath"
}

$Python = Get-Command py -ErrorAction SilentlyContinue
$PythonArgs = @("-3")
if ($null -eq $Python) {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    $PythonArgs = @()
}
if ($null -eq $Python) {
    throw "Python 3 was not found. Install Python or run generate_probes.py on another machine first."
}
$PythonPath = $Python.Source

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
& $PythonPath @PythonArgs $Generator --output-dir $OutputDirectory --amplitude-dbfs $ProbeAmplitudeDbfs
if ($LASTEXITCODE -ne 0) {
    throw "Probe generation failed with exit code $LASTEXITCODE"
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

$LogPath = Join-Path $OutputDirectory "benchmark.log"
$Commit = & git -C $RepoRoot rev-parse HEAD 2>$null
if ($LASTEXITCODE -ne 0) {
    $Commit = "unknown"
}

@(
    "PhantomDSP commit: $Commit"
    "Benchmark: $BenchmarkPath"
    "Device name: $DeviceName"
    "Installed config: $InstalledConfig"
    ""
) | Set-Content -Path $LogPath -Encoding UTF8

function Invoke-EapoBenchmark {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    "=== $Name ===" | Tee-Object -FilePath $LogPath -Append
    & $BenchmarkPath --devicename $DeviceName --nopause --verbose @Arguments 2>&1 |
        Tee-Object -FilePath $LogPath -Append
    $ExitCode = $LASTEXITCODE
    "" | Add-Content -Path $LogPath
    if ($ExitCode -ne 0) {
        throw "$Name failed with exit code $ExitCode"
    }
}

$LeftInput = Join-Path $OutputDirectory "left-input.wav"
$RightInput = Join-Path $OutputDirectory "right-input.wav"
$LeftOutput = Join-Path $OutputDirectory "left-output.wav"
$RightOutput = Join-Path $OutputDirectory "right-output.wav"
$HeadroomOutput = Join-Path $env:TEMP "phantomdsp-headroom-output.wav"

Invoke-EapoBenchmark -Name "left impulse" -Arguments @(
    "--input", $LeftInput,
    "--output", $LeftOutput
)
Invoke-EapoBenchmark -Name "right impulse" -Arguments @(
    "--input", $RightInput,
    "--output", $RightOutput
)
Invoke-EapoBenchmark -Name "correlated stereo sweep" -Arguments @(
    "--rate", "48000",
    "--channels", "2",
    "--length", "10",
    "--from", "20",
    "--to", "20000",
    "--output", $HeadroomOutput
)

Remove-Item $HeadroomOutput -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Baseline capture complete: $OutputDirectory"
Write-Host "Commit the raw directory, then run analyze_baseline.py on macOS."
