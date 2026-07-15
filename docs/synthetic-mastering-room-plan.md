# Synthetic Mastering Room Plan

Status: Candidate G passed Windows Benchmark and listening established it as a strong reference. Candidate H passed offline and Windows validation. Candidate I passed offline and Windows validation and is active for H/I listening.

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
