# Signal-Chain Architecture

## Purpose

PhantomDSP is a personalized binaural renderer for ordinary stereo recordings. Its target is not a flat electrical output from the DSP. Its target is the complex sound pressure—magnitude and time behavior—that two physical speakers produced near the listener's eardrums.

The system intentionally preserves speaker propagation delay, interaural time and level differences, pinna and head filtering, early reflections, and some room decay. These features help externalize the virtual speakers. Long or uneven room decay can still be undesirable; intentional time behavior and measurement artifacts must be evaluated separately.

## Transfer-Function Model

Let the desired speaker-to-ear matrix be:

```text
        input speaker
          L       R
ear L   B_LL    B_RL
ear R   B_LR    B_RR
```

`B_LL` is the left speaker measured at the left ear, while `B_LR` is the left speaker measured at the right ear. The other two paths follow the same convention.

Let the physical headphone-to-ear response be a diagonal matrix:

```text
P = diag(P_L, P_R)
```

The desired digital renderer is approximately:

```text
C = inverse(P) × B
```

During playback, the physical headphone completes the chain:

```text
ear output = P × C × stereo input ≈ B × stereo input
```

This distinction is important when reviewing the configuration. The DSP output alone may look highly colored because the physical headphone response that it is designed to cancel is not present in an offline digital plot.

## Measurement Method and Assumptions

Speaker and headphone responses were captured with small microphones placed consistently in the listener's ear canals, close to the desired measurement plane. Using the same microphones and placement for both measurements allows microphone sensitivity and some shared ear-canal behavior to cancel in the transfer-function ratio.

The approximation is imperfect:

- The microphones were near, but not exactly at, the eardrums and may have perturbed the canal acoustics.
- A headphone changes the acoustic boundary around the ear, so speaker and headphone measurements do not share every downstream transfer characteristic.
- Headphone fit and reseating can produce narrow response changes.
- The room was not extensively treated, so the BRIR contains both useful spatial information and room-specific coloration.
- The measurements represent one seat and fixed head orientation.

These limitations favor smoothed, regularized headphone compensation over exact inversion of every narrow peak or null. Harman's loudspeaker-derived headphone-target work used a related structure: headphones were first equalized toward a common measured baseline and then given an in-room loudspeaker target. Their method also averaged multiple headphone reseats and did not force narrow placement-dependent deviations perfectly flat. See [Olive, Welti, and McMullin (AES 2013)](https://www.researchgate.net/publication/287536305_Listener_preference_for_different_headphone_target_response_curves).

The active BRIR files, channel assignments, hashes, and timing landmarks are recorded in the [Active IR Manifest](ir-manifest.md).

## Active Processing Stages

The active include order begins in `config.txt` and `config - personalized.txt`:

1. **Load the production renderer.** `config - personalized.txt` directly includes `Speaker Virtualization.txt`; normal playback contains no experiment selector or benchmark branch.
2. **Create virtual paths.** Stereo inputs are copied into `LL`, `LR`, `RIL`, and `RIR`.
3. **Apply the unified convolution.** `Left Speaker to Both Ears.wav` and `Right Speaker to Both Ears.wav` provide all four paths. They bake in the minimized BRIR arrival, smooth extended bass, speaker-renderer EQ, and measured direct/cross timing relationships.
4. **Sum to headphone channels.** `LL + RIL` produces the left output; `LR + RIR` produces the right output.
5. **Apply target and headphone compensation.** Macro preference adjustments, Elex flattening, and personal left/right balance complete the active digital chain.

Because all stages are linear and time invariant, common filters can commute mathematically. Their semantic roles should nevertheless remain distinct so that measurements, experiments, and future simplification remain understandable.

### Measurement-Only Branch Routing

The legacy parallel-bass chain includes `tools/measurement/equalizerapo/bass-branch-output.txt` immediately before post-sum processing. Its `Device:` selectors match only reserved Benchmark names. For reference measurement runs it can replace the normal L/R sum with either the convolved or clean-low branch; post-sum, target, headphone, and personal-balance filters then remain identical across isolated and combined captures. This made `combined ≈ convolved + clean` directly testable while deriving the production target.

The historical `legacy-renderer-benchmark-selector.txt` can instead route the reserved `PhantomDSP Bass Downstream` device around the whole speaker renderer while retaining root-level target, headphone, and personal EQ. Dividing the other captures by this diagonal response recovered the legacy speaker renderer, including its post-sum speaker correction, without reimplementing the Equalizer APO filters. This selector must temporarily replace the production include and is never active during normal playback.

Benchmark writes 16-bit PCM, so the very quiet isolated clean branch is too coarsely quantized to use directly when synthesizing new IR assets. Two additional reserved routes raise the convolved and clean branches by recorded calibration gains before capture. The analyzer removes those gains mathematically; these precision routes remain measurement-only and do not alter the active renderer.

## Physical Versus Synthetic Corrections

A tonal correction representing a real loudspeaker prefilter should affect both ear paths from that speaker. An ear-side headphone correction should affect every virtual-speaker contribution sent to that ear.

Filters applied only to direct or cross paths instead modify the synthesized binaural cues themselves. The direct-only 2.7 kHz boost and cross-only 2.5 kHz cut are therefore best considered experimental spatial shaping, not generic Harman or ear-canal correction. They may improve externalization, but require complete through-headphone measurements or controlled listening to validate.

## Legacy Hybrid Bass Path

The clean-bass branch was introduced to reduce undesirable low-frequency behavior in the measured speaker/room response while retaining the BRIR above the crossover region. The legacy implementation uses a 90 Hz low-pass, gain reduction, and explicit delay, but does not high-pass the convolved branch. It is therefore an overlapping parallel blend rather than a complementary crossover. Measured digital captures show destructive summation in its transition region; downstream headphone compensation cannot change that relative branch phase.

The A100 fallback preserves the preferred legacy bass topology while advancing both the BRIR and clean branch by 100 samples. Historical bass candidate B uses a 75 Hz fourth-order Linkwitz-Riley handoff; historical bass candidate C lowers it to 65 Hz. These labels predate and are unrelated to the synthetic-room listening conditions. Both measured more coherently than the legacy overlap, but listening found weaker frontal externalization and muddier or more bloated bass. They remain historical diagnostics. See the [candidate comparison](../measurements/candidates/bass-crossover-comparison.md).

A diagnostic 200-sample BRIR advance failed because the clean branch could advance only 100 samples, producing the predicted severe bass phase error. A100 therefore remains the reference for the replacement below, not the active default.

## Minimum-Latency 2×2 Bass Redesign

The active design removes the parallel clean-bass branch and renders the full speaker-to-ear matrix in two stereo convolutions:

```text
left output  = H_LL × left input + H_RL × right input
right output = H_LR × left input + H_RR × right input
```

Each path combines room-regularized, extended low bass with the original BRIR through upper bass and above. The low-frequency model preserves smoothed interaural level and timing relationships while rejecting narrow room resonances. Its broad complex transition retains the spatial and transient information carried by approximately 80–200 Hz content. Preference bass level remains a separate common minimum-phase shelf so it can be adjusted without regenerating spatial IRs.

The target is a common 200-sample advance, minimum-phase or mixed-phase low-frequency synthesis, no explicit bass delay, and no runtime branch crossover. A causal renderer cannot have absolute zero latency; this design minimizes the IR direct-arrival contribution while retaining the measured direct/cross relationships. See [Minimum-Latency 2×2 Renderer](../measurements/minimum-latency/README.md).

The first unified experiment—historically labeled D200 v1—used two generated 24-bit stereo IRs. Its sixth-order 80 Hz synthetic low-pass retained deep-bass quantity, but the Windows capture found a 7.22–8.91 dB RMS loss from 80–200 Hz versus the legacy reference. The filter's low-model peak also arrived about 8.5 ms after sample zero. Its runnable files were removed after rejection and remain available in Git history.

The production revision—historically labeled D200 A-matched—keeps the common 200-sample BRIR advance but changes the synthetic branch to a first-order 90 Hz low-pass, +0.75 dB calibration, and the same 15-sample cross offset. Its direct low-model peak is sample 1, close to the legacy clean-before-convolved timing after the additional advance. A common −5 dB correction at 350 Hz, Q 2 is applied to all four paths after summation; because it is identical on every path, it corrects shared magnitude without changing ILD or IPD. Speaker-renderer EQ remains baked into the generated IRs; root target, headphone, and personal-balance stages remain separate.

The first version is digitally rejected and retained only as a historical diagnostic. The production Speaker Virtualization renderer passes its Windows Benchmark capture, including a 0.83–1.17 dB RMS difference from the legacy reference at 80–200 Hz, a 2.47 dB worst smoothed point, zero clipping, and 0.67% maximum single-core CPU. Controlled listening found no readily audible tonal or spatial regression, while finger drumming revealed the latency improvement.

## Synthetic Reference Room Experiment

The opt-in [Synthetic Reference Room](synthetic-reference-room.md) is a parallel research renderer, not a revision of the production BRIR. Direct-only control B uses symmetrized personal magnitude cues from a 4 ms BRIR window, causal minimum-phase reconstruction, and a theoretical contralateral delay. It deliberately discards measured propagation time, measured left/right asymmetry, and all measured room decay.

Candidate C keeps B's direct sound and adds four distinct personal early-reflection residuals from +4 to +30 ms. Each residual is aligned relative to B's theoretical direct peak, preserving measured reflection spacing without restoring old absolute latency. A reflection-only fourth-order high-pass at 250 Hz protects the synthetic low bass; measured late energy remains excluded. C is an empirical control for identifying the binaural room cues that B lacks, not the proposed final room.

Below 300 Hz, B uses only the active renderer's broad magnitude as a bass-quantity calibration; the resulting bass phase and impulse are synthesized anew. Root target, headphone compensation, and personal balance remain downstream exactly as in production. If C externalizes successfully, future stages will replace its measured residual with theoretical early reflections and add a shared synthetic late field without changing this separation of responsibilities.

## Validation Boundary

The definitive validation is a closed-loop acoustic measurement:

1. Measure left-only and right-only speaker playback at both ear microphones.
2. Measure left-only and right-only headphone playback through the complete DSP at the same positions.
3. Compare all four achieved headphone responses with the four speaker targets after removing unrelated device latency.

Until that measurement is available, offline analysis can validate routing, relative timing, mathematical stability, headroom, branch summation, and expected sensitivity. It cannot prove the final eardrum response because the physical headphone transfer is absent.

## Related Research

- [Listener Preference for Different Headphone Target Response Curves](https://www.researchgate.net/publication/287536305_Listener_preference_for_different_headphone_target_response_curves), Olive, Welti, and McMullin, AES 2013.
- [Perceptual Evaluation of Personalized BRIRs and Headphone Compensation](https://secure.aes.org/forum/pubs/conferences/?elib=20501), Davis et al., AES 2019.
- [Auditory-Based Smoothing for Equalization of Headphone-to-Eardrum Transfer Function](https://secure.aes.org/forum/pubs/conventions/?elib=19273), Li et al., AES 2017.
- [Equalizer APO Configuration Reference](https://sourceforge.net/p/equalizerapo/wiki/Configuration%20reference/).
