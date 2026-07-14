# Minimum-Latency 2×2 Renderer

This experiment replaces the room-limited JBL LSR305 bass and the parallel delayed clean-bass branch with one causal 2×2 renderer. A100 remains the accepted default and reference until a complete candidate passes digital and listening validation.

## Design Target

- Preserve the four `LL`, `LR`, `RL`, and `RR` speaker-to-ear paths separately.
- Retain the original BRIR through the upper-bass spatial transition and above.
- Replace low-frequency room resonances with smooth extension to 20 Hz or lower.
- Preserve direct/cross timing and interaural relationships instead of using identical bass at both ears.
- Use minimum-phase/mixed-phase synthesis with no explicit clean-bass delay.
- Target the common 200-sample BRIR advance; do not overwrite any parent or A100 asset.

The first reference capture adds a downstream-only matrix to the existing combined, convolved, and clean branch captures. The reserved device bypasses the complete speaker renderer at `Bass Crossover Selector.txt`, but still passes through target, headphone, and personal EQ. This allows the analysis to remove those filters mathematically and recover the speaker-renderer-only A100 matrix—including its post-sum speaker correction—without reimplementing the Equalizer APO filter cascade.

## Windows Reference Capture

Pull the current `codex/dsp-improvements` branch and confirm A100 is the only active line in `JBL M2 Binaural Convolution\Bass Crossover Selector.txt`. From PowerShell at the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\measurement\run_eapo_renderer_reference.ps1
```

The command captures the complete renderer plus `combined`, `convolved`, `clean`, and `downstream` matrices under `measurements\minimum-latency\a100-reference\raw`. It does not require Python. Confirm every impulse capture reports zero clipped samples, then commit and push the raw directory.

For a ready-to-paste PC Codex prompt, use [`docs/windows-minimum-latency-reference-runbook.md`](../../docs/windows-minimum-latency-reference-runbook.md).

## macOS Analysis

After pulling the Windows capture:

```bash
python3 -m pip install -r tools/measurement/requirements.txt
python3 tools/measurement/analyze_renderer_reference.py
```

The analyzer rejects unexpected downstream crosstalk, verifies de-embedded branch closure, and writes the speaker-renderer target to `measurements/minimum-latency/a100-reference/analysis`.
