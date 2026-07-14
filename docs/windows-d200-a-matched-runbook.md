# Windows D200 A-Matched Handoff

Open Codex at the PhantomDSP repository on the Windows playback PC and give it this prompt:

> Reproduce the accepted D200 A-matched renderer described in `measurements/minimum-latency/README.md`. First read `AGENTS.md`, that README, `measurements/minimum-latency/d200-a-matched/analysis/report.md`, `tools/measurement/run_eapo_d200_a_matched.ps1`, and `tools/measurement/run_eapo_baseline.ps1`.
>
> Work on `codex/dsp-improvements` with a clean tree and pull the latest remote commit. Confirm this checkout is installed at `C:\Program Files\EqualizerAPO\config`. Do not alter DSP values or WAV assets, change the accepted default, or change Windows audio settings.
>
> From the repository root run:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process Bypass
> .\tools\measurement\run_eapo_d200_a_matched.ps1
> ```
>
> Verify the log uses `Output A1 Voicemeeter PhantomDSP D200 A-Matched`, loads `main - D200 A-matched prototype.txt` and both A-matched WAVs, and does not load A100 or D200 v1. Confirm the left and right impulse runs and correlated sweep have no clipped samples. Report impulse peaks, sweep peak, and single-core CPU load. Verify D200 A-matched remains the normal playback default.
>
> Run `git diff --check`, commit only `measurements/minimum-latency/d200-a-matched/raw` plus any strictly necessary tooling fix in a separate commit, and push `codex/dsp-improvements`. Do not run the macOS analyzers. Finish with routing evidence, peak levels, clipping status, CPU load, output paths, exact commands, and commit hashes.
