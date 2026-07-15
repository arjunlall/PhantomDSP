# Synthetic Mastering Room Plan

Status: Candidate G passed Windows Benchmark and listening established it as a strong reference. Candidates H and I passed offline and Windows validation, and listening found I successful. Candidate J is generated, offline-validated, and informally preferred tonally, but its apparent image may be too high. Candidate K is now offline-validated as a microcluster-only directional-HRTF experiment; Windows Benchmark and J/K listening are next.

## Objective

Candidate G models a soffit-mounted mastering system in a treated control room while retaining the low-latency personalized direct sound, clean bass, and accepted E synthetic late field. It copies no measured early- or late-room waveform samples. E remains the listening reference and A remains the repository default.

## Evidence and Design Decision

Candidate F sounded good, but extended listening placed centered material close to the forehead while focused left and right sources remained convincing. Offline analysis explains the difference: F's mono-center ear responses are sample-identical through 25.25 ms and its theoretical 4–30 ms center field has correlation 1.000. E begins producing binaural differences at 4.21 ms and its measured-early center field has maximum broadband correlation 0.280.

The renderer therefore combines the physically motivated geometry and diffusion in one candidate. A geometry-only listening preset is unnecessary; component branches remain separately measurable inside the generator.

## Geometry

- Room: 6.6 m long × 4.6 m wide × 2.8 m high.
- Listener: 2.5 m from the front wall, 4.1 m from the rear wall, ears at 1.2 m.
- Soffit monitors: embedded in the front wall at ±30°, approximately 2.89 m from the listener and 2.89 m apart.
- The complete monitor/listener geometry is translated 3 cm laterally. Relative direct-speaker geometry is unchanged.
- Common physical propagation time is omitted; only interaural and reflection-relative timing is retained.

Soffit mounting removes the front-wall image source and assumes the monitor's half-space response is already voiced flat. No additional boundary-gain bass shelf will be added.

## Early and Late Fields

The direct path remains B's personalized minimum-phase HRTF and bass. Frequency-dependent source directivity and treated-surface absorption attenuate the floor, ceiling, and side-wall specular paths. No strong rear-wall mirror reflection is retained.

Deterministic binaural microclusters begin between 4 and 6 ms and continue sparsely through approximately 15 ms. They represent diffusion: multiple quiet, frequency-shaped arrivals with matched left/right energy but non-identical waveforms. A second diffuse cluster represents the rear field near 23–25 ms. All room-only energy remains fourth-order high-passed at 250 Hz.

The complete early field targets E's broad energy and frequency-dependent center coherence without copying E's exact samples. It transitions into the unchanged E synthetic late branch from 25–30 ms.

## Validation Contract

- Preserve B's direct onset and E's 20–80 Hz bass within 0.03 dB RMS.
- Keep center-ear early energy balanced within 0.2 dB without sample-identical waveforms.
- Move 4–15 ms center correlation materially toward E while avoiding an artificially diffuse center.
- Keep each discrete 1–8 kHz specular arrival at least 10 dB below direct sound.
- Prove the accepted E-minus-C late branch is unchanged.
- Verify deterministic 48 kHz, 24-bit, four-path output; safe correlated headroom; correct Equalizer APO routing; and an error-free Windows Benchmark.

G listening compared E and G for center distance, stability, focused placement, timbre, and room naturalness. H listening will compare only G and H for lower-midrange cleanliness, bass continuity, apparent distance, and spaciousness.

## Offline Result

The deterministic render passes the offline contract. Its four early paths are distinct; center-ear energy differs by less than 0.001 dB, center early energy is within 0.43 dB of E, and maximum broadband early correlation is 0.168 rather than F's 1.000. Every discrete 1–8 kHz specular path is at least 13.36 dB below direct sound. The 20–80 Hz difference from E is 0.0248 dB RMS, modeled maximum correlated gain is +2.64 dB, and the accepted E-minus-C late-field hashes are unchanged. Exact geometry, path timing, response deltas, hashes, and plots are in the [Candidate G analysis](../measurements/synthetic-reference-room/soffit-mastering/analysis/report.md).

## Candidate H Treatment Refinement

G's remaining 200–300 Hz dip is not a room mode. Its coherent floor and near-side-wall arrivals combine out of phase with the direct path near the steep 250 Hz room-branch transition. Room-width and crossover sweeps moved the cancellation but did not remove it consistently.

H keeps G's complete geometry and every non-specular branch fixed. After G's specular-energy calibration, causal low-frequency shelves attenuate both side walls and the ceiling by 9 dB and the floor by 12 dB, with a broad transition centered at 1 kHz. This represents idealized lower-midrange treatment that is difficult to realize physically; no final renormalization restores the removed energy.

Offline, H improves the worst smoothed 200–350 Hz direct-path null by 2.26 dB for LL and 2.15 dB for RR. It changes G by only 0.012 dB RMS at 20–80 Hz and 0.069 dB RMS at 1–8 kHz, retains 0.168 maximum center IACC, and models +2.61 dB maximum correlated gain. Windows Benchmark passed with no clipping or configuration errors, 5.54 dB correlated-sweep headroom, and 0.62–0.70% single-core CPU. Exact treatment response, hashes, plots, and response deltas are in the [Candidate H analysis](../measurements/synthetic-reference-room/idealized-treated/analysis/report.md).

## Candidate I Tonal Normalization

I keeps H's complete 2×2 time-domain renderer and treats its direct-only transfer as the tonal reference. It does not flatten the personal direct HRTF. Instead, for each virtual speaker it measures the complete-to-direct binaural energy ratio:

```text
R_L(f) = 10 log10[(|H_LL|² + |H_LR|²) / (|D_LL|² + |D_LR|²)]
R_R(f) = 10 log10[(|H_RL|² + |H_RR|²) / (|D_RL|² + |D_RR|²)]
```

Each ratio is 1/6-octave smoothed and normalized toward its mean from 200 Hz to 1 kHz, with tapered boundaries and unity response outside the correction region. The left correction is applied identically to LL and LR; the right correction is applied identically to RL and RR. This preserves each virtual speaker's interaural transfer ratio, direct-to-room relationship, timing, and spatial placement while removing only broad fused-response coloration. Raw comb-filter teeth are not inverted. The correction is causal minimum phase, so it adds no bulk delay or pre-ringing.

Offline, left-speaker RMS coloration falls from 1.294 to 0.414 dB and right-speaker coloration falls from 1.282 to 0.341 dB. The corresponding peak-to-peak ranges fall from 5.850 to 2.248 dB and from 6.035 to 1.703 dB. Average band levels remain within 0.003 dB of H; the 20–80 Hz and 1.25–8 kHz changes are 0.0005 and 0.0007 dB RMS. Modeled maximum correlated gain is +2.62 dB. Windows Benchmark passed with no clipping or configuration errors, 5.54 dB correlated-sweep headroom, and 0.60–0.67% single-core CPU. Exact filters and response plots are in the [Candidate I analysis](../measurements/synthetic-reference-room/tonally-normalized/analysis/report.md).

## Candidate J Midrange Extension

J preserves I exactly as its parent and corrects only the remaining broad 1–1.5 kHz complete-to-direct coloration. Its new filters begin a raised-cosine transition at 900 Hz, reach full effect from 1–1.5 kHz, and use a short frequency-shaped release to unity by 1.8 kHz. This removes the inherited 1.1–1.4 kHz jump while allowing the absolute at-ear response to retain the natural personal-HRTF rise above roughly 1.5 kHz. The correction is shared within LL/LR and RL/RR, so it cannot independently alter a speaker's interaural cues.

Unlike I's historical iterative calibration, J does not fit the smoothed target with narrow alternating correction teeth. It applies one broad minimum-phase pass to I. J changes I by only 0.0164 dB RMS from 200 Hz–1 kHz and 0.0013 dB RMS from 1.8–8 kHz. Across the combined 200 Hz–1.5 kHz evaluation band, coloration is 0.437/0.368 dB RMS and 2.294/1.824 dB peak-to-peak for the left/right speakers. Modeled maximum correlated gain is +2.61 dB. Exact filters, hashes, and I/J plots are in the [Candidate J analysis](../measurements/synthetic-reference-room/midrange-normalized/analysis/report.md).

## Candidate K Directional-HRTF Refinement

J's absolute response does not contain a 9 dB upper-treble boost. Its rising complete-to-direct ratio above 5 kHz is caused mainly by synthetic early energy filling the personal direct-path notch near 7–8 kHz. Some filling is physically expected because reflections arrive from different directions, but G's directional model is incomplete: it calculates reflection elevation for metadata while filtering only for azimuthal head shadow. Its floor paths arrive near −40° and ceiling paths near +48°, yet neither receives an elevation-dependent pinna response. The stochastic microclusters likewise have timing and binaural-coherence structure but no explicit arrival-direction HRTF.

The screening analysis estimated personal directional responses from public measured HRTFs without replacing the personal direct path. For ear `e`, measured direct direction `Ω0`, and reflection direction `Ω`, the starting model was:

```text
H_est(e, Ω) = H_personal(e, Ω0) × H_dataset(e, Ω) / H_dataset(e, Ω0)
```

The dataset ratio contributes only the directional change. The personal LL/LR/RL/RR measurements remain the magnitude, asymmetry, and ear-canal anchor at the ±30° direct-speaker positions. A screen of 150 full-resolution ARI laboratory HRTFs compared all four direction-centered personal paths from 4–12 kHz. The five selected subjects match them within 0.88–1.12 dB RMS after frequency scaling.

The analysis covered G's actual geometry: direct sources at ±30°/0°, side-wall arrivals around ±51–68°/0°, floor arrivals at ±30°/−40°, and ceiling arrivals at ±30°/+48°. A branch-energy audit then changed the implementation scope: explicit specular paths are roughly 24–31 dB below direct at 7–8 kHz, while the directionless microclusters are 6–8 dB above it. E's accepted late field is also unchanged between the successful and suspect candidates. K therefore modifies only the controlling microcluster branch.

K treats its diffuse field as 80% horizontal side energy, 10% floor, and 10% ceiling. For each virtual speaker, the matched HRTF ensemble and personal direct paths define a desired two-ear power ratio. The existing smoothed microcluster power is redistributed to that ratio rather than multiplied by the raw dataset delta, which would double-count head shadow and alter tonality. The causal minimum-phase correction fades in from 3–4 kHz, is fully active from 4–12 kHz, and fades out by 14 kHz.

Offline, K changes individual ear paths by up to roughly 3.3 dB in the localization band while retaining left/right fused microcluster power within 0.113/0.112 dB RMS. Bass changes by 0.00004 dB RMS, 200 Hz–1.8 kHz by 0.0074 dB RMS, and modeled correlated gain is +2.59 dB. J remains byte-identical. Acceptance now depends on Windows Benchmark and listening: K should lower the apparent image without pulling the center inward, narrowing the speakers, or weakening externalization.

Research basis: the [CIPIC HRTF Database](https://escholarship.org/uc/item/3d10j9jw), the [ARI HRTF Database](https://www.oeaw.ac.at/en/ari/outreach/software/hrtf-database), and Langendijk and Bronkhorst's study of [spectral localization cues](https://doi.org/10.1121/1.424945).
