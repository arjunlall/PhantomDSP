# Repository Guidelines

## Project Structure & Signal Chain

PhantomDSP is an EqualizerAPO configuration repository, not a compiled application. Root files such as `config.txt` and `config - personalized.txt` are entry points. Headphone directories (`HD650/`, `Elex/`, `LCD-2.2F 2016/`) contain model-specific equalization and channel-balance presets. `JBL M2 Binaural Convolution/` contains the shared speaker virtualization chain and impulse responses.

Treat `Include:` order as part of the DSP design: convolution, target-curve adjustment, headphone flattening, and personal balance are not interchangeable stages.

## Build, Test, and Development Commands

There is no package manager, build step, or automated test suite. Development consists of editing EqualizerAPO text filters and auditioning them on Windows.

- `rg '^Include:' --glob '*.txt'` lists active include relationships for review.
- `git diff -- '*.txt'` inspects numerical and routing changes before testing.
- `git diff --check` catches whitespace errors before a commit.

For runtime testing, place the contents in `C:\Program Files\EqualizerAPO\config`, select the intended includes in `config.txt`, and confirm an error-free load in EqualizerAPO's Configuration Editor. Changes apply immediately, so begin playback at low volume.

## Coding Style & Naming Conventions

Use EqualizerAPO's one-directive-per-line format (`Include:`, `Preamp:`, `Filter:`, `Copy:`). Add short `#` comments for intent or device assumptions. Keep relative paths in Windows form, for example `Include: HD650\Flatten HD650 at DRP.txt`, and preserve path spelling. Retain the existing `v2`, `v3` suffix pattern for experimental revisions. Do not re-encode or rename WAV impulse responses without updating every reference.

## Testing Guidelines

No coverage target applies. For each change, verify an error-free load, compare enabled versus bypassed output, check both channels, and listen for clipping or unexpected gain jumps. For convolution changes, confirm the referenced WAV exists and that channel routing remains correct. Record the headphones, output device, active include chain, and whether validation was measured, listened to, or both.

## Commit & Pull Request Guidelines

History uses short descriptive subjects without Conventional Commit prefixes, such as `Adjust Bass Boost` or `Fixed virtual speaker positioning`. Keep each commit limited to one profile or signal-chain purpose. Pull requests should explain the audible or measured goal, list affected presets and assets, describe validation, and call out gain, routing, or compatibility risks. Include response plots when they clarify tonal changes; link an issue when one exists.
