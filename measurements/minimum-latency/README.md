# Minimum-Latency 2×2 Renderer

The prior measured-room production chain, `Speaker Virtualization.txt`, replaces the room-limited JBL LSR305 bass and delayed parallel bass branch with one causal 2×2 renderer. It passed digital and controlled listening validation. `Legacy Parallel Bass Reference.txt` remains its frozen design reference and older fallback. Normal playback now uses `Synthetic Reference Room\Presence Balanced Room Renderer.txt`.

## Design

- Preserve `LL`, `LR`, `RL`, and `RR` as separate speaker-to-ear paths.
- Retain the measured BRIR through upper bass and above.
- Replace low-frequency room resonances with smooth extension through 20 Hz.
- Preserve direct/cross timing and interaural relationships.
- Use causal minimum-/mixed-phase synthesis with no runtime bass crossover or explicit bass delay.
- Remove 200 samples of common BRIR leading time without changing relative path timing.

The 200-sample value describes the locked implementation; it is not part of the renderer name. Earlier reports call this accepted measured-room design “D200 A-matched.”

## Prior Measured-Room Renderer Capture

To reproduce the prior renderer's capture, temporarily make `JBL M2 Binaural Convolution\Speaker Virtualization.txt` the sole speaker-renderer include. On Windows, run the generic baseline capture explicitly:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\measurement\run_eapo_baseline.ps1 `
  -DeviceName "Output A1 Voicemeeter" `
  -ProbeAmplitudeDbfs 0.0 `
  -OutputDirectory "measurements\minimum-latency\accepted-renderer\raw" `
  -CaptureLabel "prior measured-room production renderer"
```

The command captures the prior renderer output and a correlated full-scale headroom/CPU sweep under `measurements\minimum-latency\accepted-renderer\raw`. Restore Candidate M as the sole renderer immediately afterward. The active-renderer runner and its [Windows handoff](../../docs/windows-active-renderer-runbook.md) are reserved for Candidate M.

After pulling the capture, regenerate the runtime comparison with:

```bash
python3 tools/measurement/analyze_active_renderer.py
```

The checked-in capture passes with zero clipping, −5.44 dBFS correlated-sweep headroom, 0.67% maximum CPU, 0.32–0.41 dB RMS error from 20–80 Hz, and 0.83–1.17 dB from 80–200 Hz. The worst smoothed transition point is 2.47 dB.

## Frozen Legacy Reference

The de-embedded reference is retained to reproduce the prior measured-room IRs, not as the normal playback state. Reference capture requires the measurement-only `tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt` because the downstream bypass and isolated bass branches should not exist in normal playback routing.

Temporarily comment the active Candidate M include in `config - personalized.txt`, uncomment the benchmark selector include, and run:

```powershell
.\tools\measurement\run_eapo_renderer_reference.ps1
.\tools\measurement\run_eapo_precision_branches.ps1
```

Restore `Synthetic Reference Room\Presence Balanced Room Renderer.txt` immediately after capture. The runners reject an incorrect measurement include state. See [`docs/windows-minimum-latency-reference-runbook.md`](../../docs/windows-minimum-latency-reference-runbook.md) and [`docs/windows-precision-branch-runbook.md`](../../docs/windows-precision-branch-runbook.md).

The analyzer removes downstream target, headphone, and personal EQ; verifies branch closure; substitutes the calibrated precision captures; and writes the speaker-renderer-only target to `measurements/minimum-latency/legacy-reference/analysis`:

```bash
python3 tools/measurement/analyze_renderer_reference.py
```

## Historical Labels

Old captures and Git history use development shorthand:

- **A100:** the retained legacy parallel-bass reference.
- **D200 v1:** a removed steep-handoff experiment that lost 7.22–8.91 dB RMS from 80–200 Hz.
- **D200 A-matched:** the accepted measured-room design now named Speaker Virtualization.

Rejected runnable experiments have been removed from the current tree; their measured conclusions remain in project documentation and their complete assets remain available in Git history.
