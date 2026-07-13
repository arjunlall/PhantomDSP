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

1. **Create virtual paths.** Stereo inputs are copied into `LL`, `LR`, `RIL`, and `RIR`, plus four clean-bass paths.
2. **Apply BRIR convolution.** Two stereo WAVs provide the four speaker-to-ear responses.
3. **Align direct and cross arrivals.** Explicit sample delays preserve approximately 13 samples of cross-ear delay while aligning corresponding left/right paths.
4. **Shape convolved paths.** `Channel Balance EQ.txt` and `EQ to JBL M2.txt` contain measured, corrective, and experimental filters.
5. **Blend clean bass.** Low-passed, delayed, non-convolved signals are added in parallel with the convolved paths.
6. **Sum to headphone channels.** `LL + RIL` produces left output; `LR + RIR` produces right output, with corresponding clean-bass contributions.
7. **Apply post-sum correction.** Channel balance and common tonal filters operate on the summed ear signals.
8. **Apply target and headphone compensation.** Macro preference adjustments, headphone flattening, and personal left/right balance complete the digital renderer.

Because all stages are linear and time invariant, common filters can commute mathematically. Their semantic roles should nevertheless remain distinct so that measurements, experiments, and future simplification remain understandable.

### Measurement-Only Branch Routing

The active sum includes `tools/measurement/equalizerapo/bass-branch-output.txt` immediately before post-sum processing. Its `Device:` selectors match only reserved Benchmark names, so it is a no-op during normal playback. For measurement runs it can replace the normal L/R sum with either the convolved or clean-low branch; downstream target, headphone, and personal-balance filters then remain identical across isolated and combined captures. This makes `combined ≈ convolved + clean` a directly testable complex-response identity.

## Physical Versus Synthetic Corrections

A tonal correction representing a real loudspeaker prefilter should affect both ear paths from that speaker. An ear-side headphone correction should affect every virtual-speaker contribution sent to that ear.

Filters applied only to direct or cross paths instead modify the synthesized binaural cues themselves. The direct-only 2.7 kHz boost and cross-only 2.5 kHz cut are therefore best considered experimental spatial shaping, not generic Harman or ear-canal correction. They may improve externalization, but require complete through-headphone measurements or controlled listening to validate.

## Hybrid Bass Path

The clean-bass branch was introduced to reduce undesirable low-frequency behavior in the measured speaker/room response while retaining the BRIR above the crossover region. The legacy implementation uses a 90 Hz low-pass, gain reduction, and explicit delay, but does not high-pass the convolved branch. It is therefore an overlapping parallel blend rather than a complementary crossover. Measured digital captures show destructive summation in its transition region; downstream headphone compensation cannot change that relative branch phase.

`Bass Crossover Selector.txt` keeps the legacy renderer selected by default and exposes two opt-in candidates. Candidate B uses a 75 Hz fourth-order Linkwitz-Riley handoff and prioritizes cancellation reduction. Listening found clearer and wider bass, but weaker frontal externalization. Candidate C lowers the same topology to 65 Hz so more BRIR energy remains through the 60–150 Hz punch region. Both preserve the existing 100/115-sample clean-path delays and use one broad shared post-sum correction to approximate the legacy 25–250 Hz tonal balance. Benchmark measurements show that C has the best overall branch summation, while both candidates introduce frequency-dependent low-bass delay and interaural changes relative to the legacy chain. See the [candidate comparison](../measurements/candidates/bass-crossover-comparison.md).

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
