# Windows D200 Prototype Handoff

Open Codex at the PhantomDSP repository on the Windows playback PC and give it this prompt:

> Capture the opt-in D200 unified renderer described in `measurements/minimum-latency/README.md`. First read `AGENTS.md`, that README, `measurements/minimum-latency/d200-prototype/analysis/report.md`, `tools/measurement/run_eapo_d200_prototype.ps1`, and `tools/measurement/run_eapo_baseline.ps1`.
>
> Work on `codex/dsp-improvements` with a clean tree and pull the latest remote commit. Confirm this checkout is installed at `C:\Program Files\EqualizerAPO\config`. Do not make D200 the normal playback default, alter DSP values or WAV assets, or change Windows audio settings.
>
> From the repository root run:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process Bypass
> .\tools\measurement\run_eapo_d200_prototype.ps1
> ```
>
> Verify the log uses `Output A1 Voicemeeter PhantomDSP D200 Prototype`, loads `main - D200 unified prototype.txt` and both generated D200 WAVs, and does not load A100. Confirm the left and right impulse runs and the correlated sweep have no clipped samples. Report impulse peaks, sweep peak, and single-core CPU load. Verify the selector still contains A100 as the normal playback default.
>
> Run `git diff --check`, commit only `measurements/minimum-latency/d200-prototype/raw` plus any strictly necessary tooling fix in a separate commit, and push `codex/dsp-improvements`. Do not run the macOS analyzers and do not listen to D200 yet. Finish with routing evidence, peak levels, clipping status, CPU load, output paths, exact commands, and commit hashes.
