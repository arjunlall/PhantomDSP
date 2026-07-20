# Windows Minimum-Latency Reference Handoff

Open Codex at the PhantomDSP repository on the Windows playback PC and give it this prompt:

> Reproduce the frozen legacy parallel-bass design reference described in `measurements/minimum-latency/README.md`. First read `AGENTS.md`, that README, `tools/measurement/run_eapo_renderer_reference.ps1`, and the scripts it invokes.
>
> Work on `codex/dsp-improvements` with a clean tree and pull the latest remote commit. Confirm this checkout is installed at `C:\Program Files\EqualizerAPO\config`. In `config - personalized.txt`, temporarily comment `Presence Balanced Room Renderer.txt` and uncomment only `tools\measurement\equalizerapo\legacy-renderer-benchmark-selector.txt`. Do not alter DSP values, WAV assets, or Windows audio settings.
>
> From the repository root run:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process Bypass
> .\tools\measurement\run_eapo_renderer_reference.ps1
> ```
>
> Diagnose failures from complete output and make only the smallest measurement-tooling fix needed. The runner must confirm the historical benchmark selector is the sole renderer include, its default is the legacy parallel-bass reference, and the branch `combined` outputs match the complete digital capture byte-for-byte.
>
> Verify `digital` plus `branches\combined`, `branches\convolved`, `branches\clean`, and `branches\downstream` contain both inputs, both outputs, probe metadata, and Benchmark logs. Confirm every impulse run reports zero clipped samples. The downstream capture must bypass the renderer while retaining root target/headphone/personal EQ.
>
> Restore `Presence Balanced Room Renderer.txt` as the only renderer include before staging anything. Run `git diff --check`, commit only `measurements/minimum-latency/legacy-reference/raw` plus any strictly necessary tooling fix in a separate commit, and push `codex/dsp-improvements`. Do not run the macOS analyzer. Finish with routing evidence, clipping status, output paths, exact commands, and commit hashes.
