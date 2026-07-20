# Bass Branch Measurement

This workflow measures the frozen legacy parallel-bass handoff without reproducing Equalizer APO's filters in another DSP engine. It captures the complete output, the convolved branch alone, the clean-low branch alone, and a downstream-only identity reference. The bass-branch analyzer uses the first three; the downstream capture supports renderer de-embedding. The prior measured-room `Speaker Virtualization.txt` renderer has no separate clean-low branch.

For this historical capture only, make `tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt` the sole renderer include in `config - personalized.txt`. The measurement router activates branch isolation only when Benchmark uses the reserved names `PhantomDSP Bass Convolved` or `PhantomDSP Bass Clean`. The reserved `PhantomDSP Bass Downstream` device bypasses the renderer while retaining root-level target/headphone processing.

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
- `downstream`: renderer bypass for measuring target, headphone, and personal EQ alone.

The base device name remains part of each reserved Benchmark name so the `Device: Output A1 Voicemeeter` selector in `config.txt` still matches. Override it only if the active selector changes:

```powershell
.\tools\measurement\run_eapo_bass_branches.ps1 `
  -BaseDeviceName "Output A1 Voicemeeter"
```

The runner skips redundant stress sweeps and writes `measurements\bass-branches\raw\{combined,convolved,clean,downstream}`. It also requires the new combined outputs to match the checked-in digital baseline byte-for-byte. If an impulse capture clips, rerun all four with `-ProbeAmplitudeDbfs -6`.

After capture, restore `Synthetic Reference Room\Presence Balanced Room Renderer.txt` as the sole renderer include. Do not leave the measurement router enabled for normal playback.

## Analyze on macOS

After the raw captures are committed and pulled, run:

```bash
python3 tools/measurement/analyze_bass_branches.py
```

The analyzer verifies that `combined ≈ convolved + clean`, then evaluates all four paths from 20–300 Hz. The report includes branch magnitude, relative phase, group delay, vector-sum interference, combined response relative to the convolved branch, and focused values around 118–135 Hz. Default plots and metrics use 1/24-octave smoothing; machine-readable samples remain in `analysis/summary.json`.

Closure error is a validity check. If the separately captured branches do not reconstruct the combined output well beyond the 16-bit quantization floor, fix the routing or capture before drawing conclusions about cancellation.

## Optimize Gain, Polarity, and Delay

Run the constrained offline search after generating the branch analysis:

```bash
python3 tools/measurement/optimize_bass_alignment.py
```

The optimizer tests shared and separate direct/cross controls while requiring every path to preserve the modeled 25–70 Hz output within 1 dB RMS. It also reports the tradeoff at progressively looser preservation limits. Results are written to `measurements/bass-branches/optimization`; they are diagnostic candidates, not active Equalizer APO settings.
