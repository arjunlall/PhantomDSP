# DSP Roadmap

This roadmap prioritizes a reproducible digital baseline before changing the sound. The current renderer should remain available as a reference; experiments should use separate configuration files or generated assets until their behavior is understood.

The active listening decision and exact continuation steps are summarized in [Current DSP Work](current-status.md).

## Priority 0: Baseline and Traceability

- [ ] Add a simple 48 kHz stereo guard only if it does not complicate the active configuration.
- [x] Record checksums, channel mappings, timing landmarks, and format metadata in the [active IR manifest](ir-manifest.md).
- [x] Capture the active 2×2 digital transfer matrix through Equalizer APO Benchmark using checked-in probes.
- [x] Preserve the raw Benchmark outputs and log, then generate [magnitude, phase, impulse-response, energy-decay, and practical headroom results](../measurements/digital-baseline/analysis/report.md).
- [x] Compare the 75 Hz and 65 Hz LR4 bass candidates with the digital baseline in the [candidate comparison](../measurements/candidates/bass-crossover-comparison.md).

Success means the current digital renderer can be reproduced and candidate differences can be measured without reimplementing Equalizer APO. This baseline does not replace closed-loop acoustic validation through the headphones.

## Priority 1: Correctness and Closed-Loop Validation

### Redesign the Bass Blend Mathematically

New in-ear measurements are not required for the first pass. The existing BRIR WAVs and Equalizer APO filters contain the complex responses needed to model the handoff.

### Establish the Current Baseline

- [x] Export the complete active response through Equalizer APO Benchmark at 48 kHz.
- [x] Isolate the convolved and clean-low branches for `LL`, `LR`, `RL`, and `RR`.
- [x] Plot complex magnitude, phase, group delay, and vector sum from 20–300 Hz in the [bass branch analysis](../measurements/bass-branches/analysis/report.md).
- [x] Confirm the preliminary cancellation estimates, including the approximately 118–135 Hz transition problems.

### Evaluate Candidate Designs

- [x] Optimize clean-branch gain, polarity, and delay against all four BRIR paths. The [constrained search](../measurements/bass-branches/optimization/report.md) improves but cannot meet the cancellation criterion without materially changing deep-bass level.
- [x] Model complementary low-pass/high-pass candidates. The 75 Hz and 65 Hz LR4 variants were measured and auditioned, then their runnable configurations were removed after rejection; the conclusions remain in the candidate report and Git history.
- [ ] Test spectral replacement: `new BRIR = high-frequency BRIR + low-frequency clean model` using complementary windows.
- [ ] Compare minimum-phase, mixed-phase, and short-FIR crossover implementations.
- [x] Use one shared bass handoff for the first listening candidate; modeled channel-specific refinements were too small to justify their complexity.

### Acceptance Criteria

- No narrow cancellation deeper than 3 dB in the intended transition band.
- Smooth group-delay transition without disturbing the established direct/cross arrival relationship above the crossover.
- Predictable mono bass and left/right balance.
- Adequate peak headroom for correlated stereo input.
- No material latency increase beyond an explicitly chosen budget.

All candidates should remain offline or opt-in until these criteria are met.

### Advance the BRIR Direct Arrival

The [offline BRIR advance analysis](../measurements/ir-advance/report.md) tests a common advance across all four active BRIR channels. At 48 kHz, 200 samples represents about 4.17 ms. This reduces the IR contribution to direct-sound latency while preserving the measured room response and every relative speaker-to-ear delay closely enough for a controlled candidate, but the low-frequency renderer must be redesigned before runtime use.

- [x] Measure threshold onsets and discarded prefix energy—not only the largest peak—in each raw IR channel.
- [x] Analyze non-circular 100-, 160-, 192-, 196-, and 200-sample advances; render the useful 100-, 160-, and 200-sample endpoints without overwriting the parents.
- [x] Shift every channel by exactly the same amount. Do not independently align or normalize the four peaks.
- [x] Preserve sample rate, bit depth, channel order, polarity, amplitude, frame count, and trailing room decay; zero-pad the vacated tail.
- [x] Bound magnitude and inter-channel phase differences introduced by discarding the nonzero prefix.
- [x] Confirm that direct/cross peak spacing and the approximately 13-sample cross-ear relationship remain intact.
- [x] Model the maximum possible clean-path advance for A and C. The existing topology supports a coherent 100-sample A advance, but not the 160- or 200-sample targets.
- [x] Add A0, A100, and diagnostic A200 playback configurations for controlled comparison.
- [x] Adopt A100 as the default after listening confirmed the original A bass placement and tonality were retained.
- [x] Reject the current A200 topology after listening confirmed the predicted severe bass failure.
- [x] Replace the clean branch offline with a unified causal 2×2 low-frequency renderer for the D200 prototype.
- [x] Capture A100 through Equalizer APO Benchmark as the frozen renderer reference.
- [x] Benchmark D200 v1; retain its latency/CPU evidence but reject its 80–200 Hz response before listening.
- [x] Render a distinct D200 A-matched revision that restores the preferred A100 upper-bass quantity without overwriting v1.
- [x] Benchmark D200 A-matched; its measured response, timing, routing, headroom, and CPU pass the digital gate.
- [x] Compare A100 and D200 A-matched in controlled listening; no tonal or spatial regression was readily audible, while the latency improvement was clear during finger drumming.
- [x] Promote D200 A-matched to the daily default while retaining A100 as the known-good fallback and design reference.
- [x] Replace development labels with functional production names and remove rejected runnable configurations after preserving their conclusions in documentation and Git history.

### Build the Minimum-Latency 2×2 Renderer

- [x] Add a downstream-only Benchmark bypass that is inert during normal playback.
- [x] Add an A100 reference runner and de-embedding analyzer.
- [x] Capture A100 `combined`, `convolved`, `clean`, and `downstream` matrices on Windows.
- [x] Recover the speaker-renderer-only A100 matrix and verify branch closure after de-embedding.
- [x] Recapture the isolated convolved and clean branches at calibrated gains so 16-bit Benchmark quantization is not baked into generated IRs.
- [x] Derive smooth low-frequency interaural level and timing targets without copying room resonances.
- [x] Extend the base response flat through 20 Hz with a protective 5 Hz roll-off; keep overall bass quantity matched to A100.
- [x] Merge synthesized bass into the original BRIR over a causal 80–200 Hz transition that preserves upper-bass harmonics and onset cues.
- [x] Render causal 200-sample-advanced stereo IR pairs and remove the parallel clean branch from the accepted renderer.
- [x] Validate D200 v1 timing, decay, headroom, CPU, routing, and generated-asset closure; reject its response mismatch.
- [x] Validate D200 A-matched response, timing, headroom, CPU, routing, generated-asset closure, and controlled listening.

Success means removing only common leading time: no transient truncation, no change to spatial relationships, and no new bass-transition error. This experiment does not address driver, application, or device-buffer latency.

### Close the Acoustic Loop When Practical

New measurements would strengthen validation but are not a blocker for the bass analysis.

- [ ] Re-measure the complete DSP through the physical headphones at the same ear-microphone positions.
- [ ] Capture left input to both ears and right input to both ears separately.
- [ ] Repeat several headphone reseats to distinguish stable response features from fit-dependent narrow structure.
- [ ] Compare the achieved four-path response directly with the speaker BRIR target.
- [ ] Preserve raw captures, calibration information, and processing notes in a reproducible measurement archive.

## Priority 2: Fidelity and Optimization

### Classify and Simplify Equalization

- [ ] Label filters by role: speaker correction, headphone inverse, personal ear balance, preference target, or spatial experiment.
- [ ] Ensure physical speaker corrections are common to both ear paths from that speaker.
- [ ] Treat direct-only and cross-only filters as explicit spatial rendering choices.
- [ ] Re-evaluate the 2.5–2.7 kHz direct/cross treatment against the closed-loop target rather than the intermediate DSP response.
- [ ] Identify exact and near-redundant cascades, then prove equivalence using the complete complex transfer matrix before consolidating anything.
- [ ] Regularize narrow headphone corrections using smoothing and multiple-reseat data where available.

### Room and Renderer Experiments

- [x] Separate the personal direct window from the first repeatable room reflection cluster; +4 ms is the direct extraction boundary and the first room cluster begins around +5.1 ms.
- [x] Quantify the direct-versus-later energy split. The direct window retains 83–91% of ipsilateral energy but only 44–49% of contralateral energy.
- [x] Build an opt-in symmetric personal direct renderer with minimum-phase reconstruction, theory-derived ITD, and bass-quantity calibration.
- [x] Build an opt-in personal early-reflection control using four distinct +4 to +30 ms residuals, theoretical direct alignment, and reflection-only bass protection.
- [x] Build a one-variable late-field diagnostic that preserves the early control through +25 ms and restores the complementary measured decay.
- [ ] Compare the personal direct control with production and a generic-HRTF direct control.
- [ ] Add theoretical image-source early reflections without copying measured room arrival times.
- [ ] Add a shared binaural late field with controlled decay and interaural coherence.
- [ ] Test windowed BRIR variants that preserve direct and early spatial cues while shortening undesirable late decay.
- [ ] Trim trailing digital silence for CPU/file efficiency; do not count it as acoustic-latency reduction.
- [ ] Compare minimum-phase and hybrid renderers with the measured BRIR baseline.
- [ ] Explore a runtime parametric/no-convolution implementation after the synthetic IR establishes which cues it must reproduce.

Any experiment based on the legacy A renderer must re-run the bass-alignment analysis because its clean branch depends on BRIR timing. The accepted Speaker Virtualization renderer has no parallel runtime bass branch, but generated-asset closure and all four path relationships must still be revalidated after an IR change.

## Priority 3: Public Project Clarity

- [ ] Separate a portable example configuration from personalized device and headphone selections.
- [ ] Mark historical profiles and document their validation status.
- [ ] Add response plots and a measurement manifest without publishing unnecessary personal measurement details.
- [ ] Document how to add a headphone profile, including sample rate, seating repetitions, smoothing, gain, and validation expectations.
- [ ] Keep claims focused on the measured system: personalized speaker virtualization with M2-inspired tonal shaping, not complete physical M2 emulation.
