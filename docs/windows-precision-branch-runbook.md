# Windows Precision Branch Handoff

Open Codex at the PhantomDSP repository on the Windows playback PC and give it this prompt:

> Capture the calibrated A100 source branches described under “Precision Branch Recapture” in `measurements/minimum-latency/README.md`. First read `AGENTS.md`, that README, `tools/measurement/run_eapo_precision_branches.ps1`, `tools/measurement/run_eapo_baseline.ps1`, and `tools/measurement/equalizerapo/bass-branch-output.txt`.
>
> Work on `codex/dsp-improvements` with a clean tree and pull the latest remote commit. Confirm this checkout is installed at `C:\Program Files\EqualizerAPO\config`. Temporarily change only the normal-playback selector from D200 A-matched to A100; leave reserved routes intact. Do not alter DSP values, Windows audio settings, or existing captured references.
>
> From the repository root run:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process Bypass
> .\tools\measurement\run_eapo_precision_branches.ps1
> ```
>
> The runner must confirm A100 is the normal playback renderer and create `measurements\minimum-latency\a100-reference\raw\precision-branches\{convolved,clean}`. Verify each directory contains both input WAVs, both output WAVs, probe metadata, and a Benchmark log. The convolved log must show `PhantomDSP Precision Convolution`, a recorded +24 dB capture gain, and the `LL + RIL` / `LR + RIR` output. The clean log must show `PhantomDSP Precision CleanLow`, a recorded +48 dB capture gain, and the `LLLOW + RLLOW` / `LRLOW + RRLOW` output. Confirm both impulse runs in both logs have no clipped samples; expected peaks are roughly −10 dBFS for convolved and −17 dBFS for clean.
>
> Restore D200 A-matched as the only normal-playback renderer. Run `git diff --check`, commit only the new precision raw artifacts plus any strictly necessary tooling fix in a separate commit, and push `codex/dsp-improvements`. Do not run the macOS analyzer. Finish with routing evidence, peak levels, clipping status, output paths, exact commands, and commit hashes.
