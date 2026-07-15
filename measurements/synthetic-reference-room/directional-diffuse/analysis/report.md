# Candidate K Directional Diffuse Mastering Room

K keeps candidate J intact except for the dominant deterministic microcluster branch. It uses a five-subject public-HRTF ensemble to give that branch a plausible directional ear distribution while preserving each virtual speaker's fused microcluster power.

## Scope

- 80% of diffuse directional energy is lateral and horizontal; floor and ceiling each contribute 10%.
- The directional correction fades in from 3-4 kHz, is fully active from 4-12 kHz, and fades out by 14 kHz.
- Personal direct sound, bass, treated specular paths, accepted synthetic late field, and J's midrange normalization are unchanged.
- Filters are causal minimum phase and add no bulk delay.

## Offline Result

- Protected 200 Hz-1.8 kHz RMS change from J: 0.0074 dB.
- Left/right fused microcluster-power RMS changes from 4-12 kHz: 0.113/0.112 dB.
- Modeled maximum correlated gain: +2.59 dB.

## Plots and Reproduction

- `k-left-right-full-spectrum.svg` shows K's complete-to-direct coloration for both virtual speakers.
- `j-k-room-coloration-full-spectrum.svg` overlays J and K; `k-minus-j-fused-delta-full-spectrum.svg` expands their small fused-response difference.
- `k-left-components-full-spectrum.svg` and `k-right-components-full-spectrum.svg` separate the analytical direct, early, late, and complete spectra.
- `directional-microcluster-filters.svg` shows the four ear-path filters that implement the HRTF-derived redistribution.
- Exact public inputs, hashes, coordinate conventions, and rebuild commands are in [`docs/hrtf-reproduction.md`](../../../../docs/hrtf-reproduction.md).

K is an opt-in listening candidate. J and all earlier candidates remain byte-identical; A remains the production default.
