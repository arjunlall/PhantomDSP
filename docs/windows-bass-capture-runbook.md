# Windows Bass Capture Handoff

Open Codex at the PhantomDSP repository on the Windows playback PC and give it this prompt:

> Complete the Equalizer APO bass-branch capture described in `measurements/bass-branches/README.md`. First read `AGENTS.md`, that README, `tools/measurement/run_eapo_bass_branches.ps1`, and `tools/measurement/equalizerapo/bass-branch-output.txt`.
>
> Work on `codex/dsp-improvements` with a clean tree and pull the latest remote commit. Confirm this checkout is the configuration installed at `C:\Program Files\EqualizerAPO\config`, and preserve all active DSP values and WAV assets.
>
> Run from the repository root:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process Bypass
> .\tools\measurement\run_eapo_bass_branches.ps1
> ```
>
> Diagnose any failure from its complete output and make only the smallest Windows measurement-tooling fix needed. Do not alter EQ, delays, convolution assets, normal routing, or Windows audio settings. Ask before changing anything outside the repository.
>
> Verify that all four capture directories—`combined`, `convolved`, `clean`, and `downstream`—contain both inputs, both outputs, probe metadata, and a Benchmark log. Each log must show the intended reserved device name. The first three must load `tools\measurement\equalizerapo\bass-branch-output.txt`; the convolved log must show the `LL + RIL` / `LR + RIR` override and the clean log the `LLLOW + RLLOW` / `LRLOW + RRLOW` override. The downstream log must show that `Bass Crossover Selector.txt` bypassed the renderer. No impulse run may clip.
>
> The runner must report that the combined outputs match the checked-in digital baseline. If they do not, stop and identify the configuration difference instead of committing misleading measurements. Do not run the macOS analyzer.
>
> Once valid, run `git diff --check`, commit only `measurements/bass-branches/raw` plus any necessary tooling fix in a separate commit, and push `codex/dsp-improvements`. Finish with the exact commands, routing evidence, clipping status, output paths, and commit hashes.
