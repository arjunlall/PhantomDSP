# Windows Production Renderer Handoff

Open Codex at the PhantomDSP repository on the Windows playback PC and give it this prompt:

> Reproduce the accepted Speaker Virtualization renderer described in `measurements/minimum-latency/README.md`. First read `AGENTS.md`, that README, `measurements/minimum-latency/accepted-renderer/analysis/report.md`, `tools/measurement/run_eapo_active_renderer.ps1`, and `tools/measurement/run_eapo_baseline.ps1`.
>
> Work on `codex/dsp-improvements` with a clean tree and pull the latest remote commit. Confirm this checkout is installed at `C:\Program Files\EqualizerAPO\config`. Do not alter DSP values or WAV assets, change the accepted default, or change Windows audio settings.
>
> From the repository root run:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process Bypass
> .\tools\measurement\run_eapo_active_renderer.ps1
> ```
>
> Verify the ordinary `Output A1 Voicemeeter` device loads `Speaker Virtualization.txt`, `Left Speaker to Both Ears.wav`, and `Right Speaker to Both Ears.wav`, and does not load the legacy reference. Confirm the left and right impulse runs and correlated sweep have no clipped samples. Report impulse peaks, sweep peak, and single-core CPU load. Verify `config - personalized.txt` contains exactly one active speaker-renderer include and that it is Speaker Virtualization.
>
> Run `git diff --check`, commit only `measurements/minimum-latency/accepted-renderer/raw` plus any strictly necessary tooling fix in a separate commit, and push `codex/dsp-improvements`. Do not run the macOS analyzers. Finish with routing evidence, peak levels, clipping status, CPU load, output paths, exact commands, and commit hashes.
