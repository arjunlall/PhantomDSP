# Synthetic Mastering Room Plan

Status: Candidate G is generated and offline-validated; Windows Benchmark and listening remain pending.

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

Listening will compare only E and G for center distance, center stability, focused left/right placement, tonal and bass consistency, audible echoes, and perceived room naturalness.

## Offline Result

The deterministic render passes the offline contract. Its four early paths are distinct; center-ear energy differs by less than 0.001 dB, center early energy is within 0.43 dB of E, and maximum broadband early correlation is 0.168 rather than F's 1.000. Every discrete 1–8 kHz specular path is at least 13.36 dB below direct sound. The 20–80 Hz difference from E is 0.0248 dB RMS, modeled maximum correlated gain is +2.64 dB, and the accepted E-minus-C late-field hashes are unchanged. Exact geometry, path timing, response deltas, hashes, and plots are in the [Candidate G analysis](../measurements/synthetic-reference-room/soffit-mastering/analysis/report.md).
