# Digital Baseline Capture

This workflow captures the complete Equalizer APO configuration as a 2×2 digital transfer matrix. It uses Equalizer APO's own filter engine, so the result includes the active BRIRs, virtual-channel routing, bass blend, target shaping, and headphone compensation without reimplementing those stages.

The result is digital-only. It does not include the physical headphone-to-ear response and is not a substitute for closed-loop acoustic measurements.

## 1. Capture on Windows

Use the checkout installed at `C:\Program Files\EqualizerAPO\config`, select a 48 kHz stereo endpoint, and check out the exact commit being measured. From PowerShell at the repository root, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\measurement\run_eapo_baseline.ps1
```

The runner:

1. Copies checked-in deterministic 24-bit left-only and right-only impulse probes.
2. Passes both probes through `Benchmark.exe` using the device name `Output A1 Voicemeeter`.
3. Runs a full-scale correlated-stereo sweep for a practical clipping and CPU check.
4. Writes the retained artifacts under `measurements\digital-baseline\raw`.

The Windows capture step does not require Python or a system-wide Git command. GitHub Desktop is sufficient for updating the checkout; the runner reads the commit ID from the checkout metadata when Git CLI is unavailable.

Override local details when necessary:

```powershell
.\tools\measurement\run_eapo_baseline.ps1 `
  -DeviceName "Output A1 Voicemeeter" `
  -BenchmarkPath "C:\Program Files\EqualizerAPO\Benchmark.exe"
```

The default probe is effectively 0 dBFS to maximize signal-to-noise ratio in Benchmark's 16-bit output. This is offline processing and is not played through the audio device. If either impulse run reports clipped samples, repeat the capture with `-ProbeAmplitudeDbfs -6` to select the included fallback probe. The runner accepts only the checked-in 0 and -6 dBFS sets.

If the repository is not the installed Equalizer APO configuration, the script warns which `config.txt` Benchmark will actually process. Do not commit a capture until that path and the commit recorded in `benchmark.log` are correct.

Commit and push the generated `raw/` directory. It contains the two inputs, two processed outputs, probe metadata, and Benchmark log. The temporary sweep output is deleted because only its peak, clipping, and CPU results are needed.

## 2. Analyze on macOS or Windows

Install the single analysis dependency and run:

```bash
python3 -m pip install -r tools/measurement/requirements.txt
python3 tools/measurement/analyze_baseline.py
```

The analyzer writes `measurements/digital-baseline/analysis/` containing:

- `report.md` and machine-readable `summary.json`.
- Impulse, magnitude, wrapped-phase, group-delay, and energy-decay SVGs.
- Per-path onset, peak timing, peak level, and spatial-offset measurements.
- Parsed headroom, clipping, and CPU results from `benchmark.log`.

The four paths are `LL` and `LR` from the left-input capture, plus `RL` and `RR` from the right-input capture. All timing is reported relative to the known probe impulse at sample 1024.

Equalizer APO Benchmark writes 16-bit output. The analyzer therefore reports −40 and −50 dB relative onsets; deeper low-level timing and decay can be quantization-limited on the quieter cross paths. Use the original 24-bit WAV analysis in `docs/ir-manifest.md` when deciding how much leading BRIR content can be removed.

`tools/measurement/generate_probes.py` is retained for reproducibly rebuilding the checked-in probe assets during development; it is not needed for capture.

## Candidate Captures

The runner and analyzer accept alternate directories, allowing bass and latency candidates to be recorded without overwriting the baseline:

```powershell
.\tools\measurement\run_eapo_baseline.ps1 `
  -OutputDirectory ".\measurements\candidates\advance-196\raw" `
  -CaptureLabel "advance-196"
```

```bash
python3 tools/measurement/analyze_baseline.py \
  --input-dir measurements/candidates/advance-196/raw \
  --output-dir measurements/candidates/advance-196/analysis
```

When present, the runner copies the active `Bass Crossover Selector.txt` into the raw directory and records its SHA-256 hash in `benchmark.log`. This preserves the exact temporary A/B/C selection even when the selector is restored before committing the capture.
