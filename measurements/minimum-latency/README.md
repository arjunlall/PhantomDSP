# Minimum-Latency 2×2 Renderer

The production `Speaker Virtualization.txt` chain replaces the room-limited JBL LSR305 bass and delayed parallel bass branch with one causal 2×2 renderer. It passed digital and controlled listening validation. `Legacy Parallel Bass Reference.txt` remains the frozen design reference and known-good fallback.

## Design

- Preserve `LL`, `LR`, `RL`, and `RR` as separate speaker-to-ear paths.
- Retain the measured BRIR through upper bass and above.
- Replace low-frequency room resonances with smooth extension through 20 Hz.
- Preserve direct/cross timing and interaural relationships.
- Use causal minimum-/mixed-phase synthesis with no runtime bass crossover or explicit bass delay.
- Remove 200 samples of common BRIR leading time without changing relative path timing.

The 200-sample value describes the locked implementation; it is not part of the production name. Earlier reports call the accepted design “D200 A-matched.”

## Production Renderer Capture

Normal playback must directly include `JBL M2 Binaural Convolution\Speaker Virtualization.txt`. On Windows:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\measurement\run_eapo_active_renderer.ps1
```

The command captures the production output and a correlated full-scale headroom/CPU sweep under `measurements\minimum-latency\accepted-renderer\raw`. See [`docs/windows-active-renderer-runbook.md`](../../docs/windows-active-renderer-runbook.md) for the reproducible PC handoff.

After pulling the capture, regenerate the runtime comparison with:

```bash
python3 tools/measurement/analyze_active_renderer.py
```

The checked-in capture passes with zero clipping, −5.44 dBFS correlated-sweep headroom, 0.67% maximum CPU, 0.32–0.41 dB RMS error from 20–80 Hz, and 0.83–1.17 dB from 80–200 Hz. The worst smoothed transition point is 2.47 dB.

## Frozen Legacy Reference

The de-embedded reference is retained to reproduce the production IRs, not as the normal playback state. Reference capture requires the measurement-only `tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt` because the downstream bypass and isolated bass branches should not exist in production routing.

Temporarily comment the production include in `config - personalized.txt`, uncomment the benchmark selector include, and run:

```powershell
.\tools\measurement\run_eapo_renderer_reference.ps1
.\tools\measurement\run_eapo_precision_branches.ps1
```

Restore `Speaker Virtualization.txt` immediately after capture. The runners reject an incorrect include state. See [`docs/windows-minimum-latency-reference-runbook.md`](../../docs/windows-minimum-latency-reference-runbook.md) and [`docs/windows-precision-branch-runbook.md`](../../docs/windows-precision-branch-runbook.md).

The analyzer removes downstream target, headphone, and personal EQ; verifies branch closure; substitutes the calibrated precision captures; and writes the speaker-renderer-only target to `measurements/minimum-latency/legacy-reference/analysis`:

```bash
python3 tools/measurement/analyze_renderer_reference.py
```

## Historical Labels

Old captures and Git history use development shorthand:

- **A100:** the retained legacy parallel-bass reference.
- **D200 v1:** a removed steep-handoff experiment that lost 7.22–8.91 dB RMS from 80–200 Hz.
- **D200 A-matched:** the accepted design now named Speaker Virtualization.

Rejected runnable experiments have been removed from the current tree; their measured conclusions remain in project documentation and their complete assets remain available in Git history.
