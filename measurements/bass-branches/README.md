# Bass Branch Measurement

This workflow measures the current clean-bass handoff without reproducing Equalizer APO's filters in another DSP engine. It captures the complete output, the convolved branch alone, and the clean-low branch alone. All three pass through the same post-sum, target, headphone, and personal-balance filters.

The measurement-only router sits immediately after the normal branch sum. It activates only when Benchmark uses the reserved names `PhantomDSP Bass Convolved` or `PhantomDSP Bass Clean`; normal playback is unchanged.

## Capture on Windows

Use the checkout installed at `C:\Program Files\EqualizerAPO\config`. From PowerShell at the repository root, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\measurement\run_eapo_bass_branches.ps1
```

The runner makes left-only and right-only captures for:

- `combined`: the existing convolved-plus-clean renderer.
- `convolved`: `LL + RIL` and `LR + RIR` before downstream processing.
- `clean`: `LLLOW + RLLOW` and `LRLOW + RRLOW` before downstream processing.

The base device name remains part of each reserved Benchmark name so the `Device: Output A1 Voicemeeter` selector in `config.txt` still matches. Override it only if the active selector changes:

```powershell
.\tools\measurement\run_eapo_bass_branches.ps1 `
  -BaseDeviceName "Output A1 Voicemeeter"
```

The runner skips redundant stress sweeps and writes `measurements\bass-branches\raw\{combined,convolved,clean}`. It also requires the new combined outputs to match the checked-in digital baseline byte-for-byte. If an impulse capture clips, rerun all three with `-ProbeAmplitudeDbfs -6`.

## Analyze on macOS

After the raw captures are committed and pulled, run:

```bash
python3 tools/measurement/analyze_bass_branches.py
```

The analyzer verifies that `combined ≈ convolved + clean`, then evaluates all four paths from 20–300 Hz. The report includes branch magnitude, relative phase, group delay, vector-sum interference, combined response relative to the convolved branch, and focused values around 118–135 Hz. Default plots and metrics use 1/24-octave smoothing; machine-readable samples remain in `analysis/summary.json`.

Closure error is a validity check. If the separately captured branches do not reconstruct the combined output well beyond the 16-bit quantization floor, fix the routing or capture before drawing conclusions about cancellation.
