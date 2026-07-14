# D200 A-Matched Runtime Comparison

This report de-embeds the measured downstream target/headphone chain from the Windows D200 A-matched Benchmark capture, verifies the resulting 2×2 matrix against the generated IRs, and compares it with A100.

## Runtime Validation

- Downstream off-diagonal leakage: -180.00 dB.
- Total clipped samples: 0.
- Maximum single-core CPU load: 0.67%.
- Correlated full-scale sweep peak: -5.44 dBFS.

## Measured Response

| Path | Peak sample | Mean / RMS 20–80 Hz delta | RMS / max 80–200 Hz delta | Runtime/WAV error, 20–300 Hz |
| --- | ---: | ---: | ---: | ---: |
| `LL` | 42 | -0.17 / 0.41 dB | 1.17 / 2.47 dB | -36.90 dB |
| `LR` | 54 | -0.06 / 0.32 dB | 0.83 / 1.62 dB | -36.71 dB |
| `RL` | 55 | -0.13 / 0.36 dB | 0.87 / 1.76 dB | -37.02 dB |
| `RR` | 41 | -0.05 / 0.32 dB | 1.17 / 2.12 dB | -35.94 dB |

## Decision

The runtime capture passes the digital gate: routing, timing, headroom, CPU load, generated-asset closure, and the A100 tonal match all validate. The 80–200 Hz RMS error is 0.83–1.17 dB and the worst smoothed point is 2.47 dB. Controlled listening subsequently found no readily audible tonal or spatial regression from A100, while finger drumming confirmed the latency improvement. D200 A-matched is therefore the accepted default; A100 remains the fallback.

See `a100-vs-d200-left-speaker.svg`, `a100-vs-d200-right-speaker.svg`, and `a100-vs-d200-magnitude-delta.svg` for the frequency-response comparison.
