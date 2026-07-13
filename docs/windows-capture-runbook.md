# Windows Baseline Capture Runbook

This runbook is a handoff for Codex running on the Windows playback PC. Copy the prompt below into a Codex task opened at the PhantomDSP repository.

## Codex Handoff Prompt

> Work autonomously toward a successful Equalizer APO digital-baseline capture on this PC. Start by reading `AGENTS.md`, `measurements/digital-baseline/README.md`, and `tools/measurement/run_eapo_baseline.ps1`.
>
> The repository should be on branch `codex/dsp-improvements` and contain commit `0bdba18` or later. The capture script is intentionally independent of Python and a system-wide Git command. Do not install either merely to run the capture.
>
> First inspect the current checkout, uncommitted changes, PowerShell version, the location of `Benchmark.exe`, and the installed Equalizer APO configuration. The usual benchmark path is `C:\Program Files\EqualizerAPO\Benchmark.exe`; the expected device name is `Output A1 Voicemeeter`. Confirm actual paths and names instead of assuming them.
>
> Run the baseline command from the repository root:
>
> ```powershell
> Set-ExecutionPolicy -Scope Process Bypass
> .\tools\measurement\run_eapo_baseline.ps1
> ```
>
> If it fails, capture the complete command and error, identify the specific cause, make the smallest repository tooling fix needed, and rerun it. Do not change active DSP `.txt` files, routing, EQ values, or convolution WAVs. Preserve unrelated user changes. If success would require overwriting the installed Equalizer APO configuration or changing a Windows audio/device setting, stop and ask before doing so.
>
> Verify that Benchmark is processing the intended `config.txt`. A warning that it is using a different installed checkout must be resolved or explicitly approved; do not produce a misleading baseline. This is an offline Benchmark operation and should not require playing the probes through the headphones.
>
> A successful capture creates these files under `measurements\digital-baseline\raw`:
>
> - `left-input.wav` and `right-input.wav`
> - `left-output.wav` and `right-output.wav`
> - `probe-metadata.json`
> - `benchmark.log`
>
> Confirm every file exists and is nonempty, and inspect `benchmark.log` for the commit, device, installed configuration, probe set, failures, clipping, and CPU results. Clipping in either impulse capture is a problem: rerun with `-ProbeAmplitudeDbfs -6`. The correlated full-scale sweep is a deliberate stress test, so report its clipping result rather than silently treating it as an impulse-capture failure.
>
> Once the capture is valid, run `git diff --check`. If you had to fix the runner, commit that tooling fix separately. Then commit the new `measurements/digital-baseline/raw` artifacts with a short subject such as `Capture Windows digital baseline` and push `codex/dsp-improvements`. Do not include unrelated files.
>
> Finish with a concise report containing the root cause of the original error, any changes made, the exact capture command, impulse clipping status, sweep peak/clipping/CPU results, artifact paths, and commit hash. Do not perform the macOS analysis step; that will be run after the capture commit is pulled onto the Mac.
