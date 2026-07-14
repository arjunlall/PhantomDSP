# D200 A-Matched Renderer Prototype

This offline revision keeps A100 as the playback default. It responds to the measured D200 v1 loss in the 80–200 Hz handoff without reintroducing a runtime bass branch.

## Locked Design

- Keep the same common 200-sample BRIR advance and one-convolution 2×2 topology as D200 v1.
- Replace the sixth-order 80 Hz low-pass with a first-order 90 Hz low-pass and +0.75 dB calibration.
- Retain the causal 5 Hz protective high-pass and 15-sample cross-path offset.
- Let the clean model decay gently through upper bass so the complete response stays close to the preferred A100 reference through 200 Hz.
- Apply one common −5 dB, 350 Hz, Q 2 correction after the 2×2 sum to remove the gentle model's shared lower-mid excess without changing interaural ratios.

The first-order low model peaks at sample 1 on direct paths and sample 16 on cross paths. Relative to the advanced BRIR peaks, that closely recreates A100's clean-before-convolved timing while avoiding v1's approximately 8.5 ms low-pass peak delay.

## Offline Response Match

| Path | 20–80 Hz mean / RMS | 80–160 Hz mean / RMS | 160–250 Hz mean / RMS | Total peak |
| --- | ---: | ---: | ---: | ---: |
| `LL` | -0.17 / 0.41 dB | -0.44 / 0.84 dB | -1.49 / 1.55 dB | 42 (0.875 ms) |
| `LR` | -0.06 / 0.32 dB | -0.13 / 0.77 dB | -0.31 / 0.92 dB | 54 (1.125 ms) |
| `RL` | -0.13 / 0.36 dB | +0.03 / 0.60 dB | +0.30 / 1.20 dB | 55 (1.146 ms) |
| `RR` | -0.05 / 0.32 dB | -0.39 / 0.99 dB | -1.08 / 1.26 dB | 41 (0.854 ms) |

Next gate: capture this distinct asset set through Equalizer APO Benchmark, confirm the predicted response and headroom, then expose A100 and D200 A-Matched as a controlled listening pair.
