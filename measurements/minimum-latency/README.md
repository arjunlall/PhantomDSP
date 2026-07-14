# Minimum-Latency 2×2 Renderer

This experiment replaces the room-limited JBL LSR305 bass and the parallel delayed clean-bass branch with one causal 2×2 renderer. D200 A-matched passed digital and controlled listening validation and is now the accepted default. A100 remains the frozen design reference and known-good fallback.

## Design Target

- Preserve the four `LL`, `LR`, `RL`, and `RR` speaker-to-ear paths separately.
- Retain the original BRIR through the upper-bass spatial transition and above.
- Replace low-frequency room resonances with smooth extension to 20 Hz or lower.
- Preserve direct/cross timing and interaural relationships instead of using identical bass at both ears.
- Use minimum-phase/mixed-phase synthesis with no explicit clean-bass delay.
- Target the common 200-sample BRIR advance; do not overwrite any parent or A100 asset.

The first reference capture adds a downstream-only matrix to the existing combined, convolved, and clean branch captures. The reserved device bypasses the complete speaker renderer at `Bass Crossover Selector.txt`, but still passes through target, headphone, and personal EQ. This allows the analysis to remove those filters mathematically and recover the speaker-renderer-only A100 matrix—including its post-sum speaker correction—without reimplementing the Equalizer APO filter cascade.

## Windows Reference Capture

This is a reproducibility procedure for the frozen A100 target, not the normal playback state. Temporarily comment the D200 A-matched normal-playback line and uncomment A100 in `JBL M2 Binaural Convolution\Bass Crossover Selector.txt`; leave reserved measurement routes intact. From PowerShell at the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\measurement\run_eapo_renderer_reference.ps1
```

The command captures the complete renderer plus `combined`, `convolved`, `clean`, and `downstream` matrices under `measurements\minimum-latency\a100-reference\raw`. It does not require Python. Confirm every impulse capture reports zero clipped samples, then restore D200 A-matched as the only normal-playback renderer before committing.

For a ready-to-paste PC Codex prompt, use [`docs/windows-minimum-latency-reference-runbook.md`](../../docs/windows-minimum-latency-reference-runbook.md).

## macOS Analysis

After pulling the Windows capture:

```bash
python3 -m pip install -r tools/measurement/requirements.txt
python3 tools/measurement/analyze_renderer_reference.py
```

The analyzer rejects unexpected downstream crosstalk, verifies de-embedded branch closure, and writes the speaker-renderer target to `measurements/minimum-latency/a100-reference/analysis`.

## Precision Branch Recapture

Equalizer APO Benchmark writes 16-bit PCM. The original isolated clean branch peaks near −65 dBFS, which is sufficient to identify the target but too quantized to use as the source for a production IR. Temporarily select A100 as described above, then capture only the two source branches again at calibrated gains:

```powershell
.\tools\measurement\run_eapo_precision_branches.ps1
```

The measurement-only routes apply +24 dB to the convolved branch and +48 dB to the clean branch while using the −6 dBFS probe. They do not match normal playback devices. The analyzer automatically substitutes both precision captures when present and removes the recorded gains before de-embedding. Never use only one precision branch, and restore D200 A-matched after capture.

For a ready-to-paste PC Codex prompt, use [`docs/windows-precision-branch-runbook.md`](../../docs/windows-precision-branch-runbook.md).

## D200 Runtime Captures

The first locked prototype replaces the parallel clean branch with two generated stereo IRs, preserves the 15-sample cross-path bass offset, and advances the BRIR portion another 100 samples. Its Windows capture validated exact routing, 41–55-sample peaks, −5.51 dBFS correlated-sweep headroom, zero clipping, and 0.67% maximum single-core CPU. It failed the tonal gate: the steep low-pass left a 7.22–8.91 dB RMS mismatch from 80–200 Hz versus A100. Keep it only as a reproducible diagnostic.

The A-matched revision preserves the one-convolution topology and exact 200-sample BRIR advance, but uses a first-order 90 Hz low-pass whose sample-1 direct peak recreates A100's clean-before-convolved timing. A common 350 Hz correction removes the resulting shared lower-mid excess without changing interaural ratios. Its Windows capture passes the digital gate: zero clipping, −5.44 dBFS full-scale correlated-sweep headroom, 0.67% maximum CPU, 0.32–0.41 dB RMS error from 20–80 Hz, and 0.83–1.17 dB from 80–200 Hz. The worst smoothed transition point is 2.47 dB.

After pulling the A-matched revision on Windows, run:

```powershell
.\tools\measurement\run_eapo_d200_a_matched.ps1
```

The command captures the accepted output and a correlated full-scale headroom/CPU sweep under `measurements\minimum-latency\d200-a-matched\raw`. D200 A-matched must remain the normal playback default. See [`docs/windows-d200-a-matched-runbook.md`](../../docs/windows-d200-a-matched-runbook.md) for the reproducible PC handoff.

After pulling the capture on macOS, run:

```bash
python3 tools/measurement/analyze_d200_prototype.py --variant d200-a-matched
```
