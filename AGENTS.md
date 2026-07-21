# Repository Guidelines

## Required Project Context

Before changing this repository's Equalizer APO behavior, measurements,
renderer assets, hashes, Windows runtime evidence, or source provenance, read
`PROJECT_CONTEXT.md`. It is a frozen oracle handoff snapshot, not the active
portable-product context.

For current product, runtime, profile, UI, packaging, or platform decisions,
read `/Users/arjun/dev/phantom/PROJECT_CONTEXT.md`. Do not mirror ordinary
Phantom changes into this repository. Update the local snapshot only when an
oracle fact changes.

## Project Structure & Signal Chain

PhantomDSP is an EqualizerAPO configuration repository, not a compiled application. `config.txt` and `config - personalized.txt` are the entry points. Normal playback directly includes `Synthetic Reference Room/Presence Balanced Room Renderer.txt`; its generated assets live under `Synthetic Reference Room/IRs/presence-balanced/`. `JBL M2 Binaural Convolution/Speaker Virtualization.txt` is the prior measured-room production reference and `Legacy Parallel Bass Reference.txt` is the known-good legacy fallback. Measurement-only routing belongs under `tools/measurement/equalizerapo/` and must not be enabled during normal playback.

`docs/architecture.md` defines the intended transfer-function model and measurement assumptions. `docs/ir-manifest.md` fingerprints the active BRIR assets. `docs/roadmap.md` tracks validation, bass, EQ, and latency work. Update these documents when a change alters the signal-chain meaning, IR lineage, or project priorities.

Treat `Include:` order as part of the DSP design: convolution, target-curve adjustment, headphone flattening, and personal balance are not interchangeable stages.

## Build, Test, and Development Commands

There is no build step. Development consists of editing EqualizerAPO filters, running the measurement-tool tests, and auditioning changes on Windows.

- `rg '^Include:' --glob '*.txt'` lists active include relationships for review.
- `PYTHONPATH=tools/measurement python3 -m unittest discover -s tools/measurement -p 'test_*.py'` runs measurement-tool unit tests.
- `git diff -- '*.txt'` inspects numerical and routing changes before testing.
- `git diff --check` catches whitespace errors before a commit.

For runtime testing, place the repository at `C:\Program Files\EqualizerAPO\config` and confirm an error-free load in EqualizerAPO's Configuration Editor. Changes apply immediately, so begin playback at low volume.

## Coding Style & Naming Conventions

Use EqualizerAPO's one-directive-per-line format (`Include:`, `Preamp:`, `Filter:`, `Copy:`). Add short `#` comments for intent or device assumptions. Keep relative paths in Windows form, for example `Include: HD650\Flatten HD650 at DRP.txt`, and preserve path spelling. Retain the existing `v2`, `v3` suffix pattern for experimental revisions. Do not re-encode or rename WAV impulse responses without updating every reference.

## Testing Guidelines

No coverage target applies. For each change, verify an error-free load, compare enabled versus bypassed output, check both channels, and listen for clipping or unexpected gain jumps. For convolution changes, confirm the referenced WAV exists and that channel routing remains correct. Record the headphones, output device, active include chain, and whether validation was measured, listened to, or both.

## Commit & Pull Request Guidelines

History uses short descriptive subjects without Conventional Commit prefixes, such as `Adjust Bass Boost` or `Fixed virtual speaker positioning`. Keep each commit limited to one profile or signal-chain purpose. Pull requests should explain the audible or measured goal, list affected presets and assets, describe validation, and call out gain, routing, or compatibility risks. Include response plots when they clarify tonal changes; link an issue when one exists.
