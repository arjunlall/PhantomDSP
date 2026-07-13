# Windows Bass-Crossover Capture Handoff

Open Codex at the PhantomDSP repository on the Windows playback PC and provide this prompt:

> Capture candidates B and C through Equalizer APO Benchmark without changing their DSP values. Read `AGENTS.md`, `measurements/digital-baseline/README.md`, `measurements/bass-branches/README.md`, `tools/measurement/run_eapo_baseline.ps1`, and `tools/measurement/run_eapo_bass_branches.ps1` first.
>
> Work on `codex/dsp-improvements` with a clean tree and pull the latest remote commit. Confirm this checkout is the configuration installed at `C:\Program Files\EqualizerAPO\config`. Record the starting contents of `JBL M2 Binaural Convolution\Bass Crossover Selector.txt`; A must be restored before the final commit.
>
> For B, comment A and enable only `main - LR4 bass crossover.txt`. Run:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process Bypass
> .\tools\measurement\run_eapo_baseline.ps1 `
>   -OutputDirectory ".\measurements\candidates\lr4-75\digital\raw" `
>   -CaptureLabel "B: LR4 75 Hz"
> .\tools\measurement\run_eapo_bass_branches.ps1 `
>   -OutputRoot ".\measurements\candidates\lr4-75\bass-branches\raw" `
>   -CombinedReferenceDirectory ".\measurements\candidates\lr4-75\digital\raw" `
>   -CaptureLabel "B: LR4 75 Hz"
> ```
>
> For C, enable only `main - LR4 65 Hz bass crossover.txt` and repeat with `lr4-65` directories and the label `C: LR4 65 Hz`. Do not change EQ, gains, delays, WAVs, routing, or Windows audio settings.
>
> For both candidates, verify that the complete-output and isolated-branch logs contain the intended label, selector hash, selector snapshot, installed config path, and no clipped impulse samples. Each bass-branch runner must report that its combined capture matches its corresponding digital reference. If not, stop and diagnose rather than committing misleading output.
>
> Restore selector A exactly, confirm normal playback loads without error, and run `git diff --check`. Commit only `measurements/candidates/lr4-75` and `measurements/candidates/lr4-65`; do not commit the temporary selector edit. Push `codex/dsp-improvements` and report the commit hash, output paths, selector hashes, clipping status, and reference-match result. Do not run the analyzers unless Python and NumPy are already available.
