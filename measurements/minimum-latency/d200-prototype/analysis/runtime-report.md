# D200 v1 Runtime Comparison

This report de-embeds the measured downstream target/headphone chain from the Windows D200 v1 Benchmark capture, verifies the resulting 2×2 matrix against the generated IRs, and compares it with A100.

## Runtime Validation

- Downstream off-diagonal leakage: -180.00 dB.
- Total clipped samples: 0.
- Maximum single-core CPU load: 0.67%.
- Correlated full-scale sweep peak: -5.51 dBFS.

## Measured Response

| Path | Peak sample | Mean / RMS 20–80 Hz delta | RMS 80–200 Hz delta | Runtime/WAV error, 20–300 Hz |
| --- | ---: | ---: | ---: | ---: |
| `LL` | 42 | +0.11 / 0.77 dB | 7.22 dB | -36.54 dB |
| `LR` | 54 | -0.15 / 0.74 dB | 8.91 dB | -34.95 dB |
| `RL` | 55 | -0.06 / 0.66 dB | 8.60 dB | -35.60 dB |
| `RR` | 41 | +0.26 / 0.93 dB | 7.98 dB | -35.83 dB |

## Decision

The runtime capture validates routing, timing, headroom, CPU load, and generated-asset closure. It does not pass the tonal gate: every path differs from A100 by 7.22–8.91 dB RMS from 80–200 Hz. Keep this first prototype as a diagnostic and benchmark the A-matched revision before listening.

See `a100-vs-d200-left-speaker.svg`, `a100-vs-d200-right-speaker.svg`, and `a100-vs-d200-magnitude-delta.svg` for the frequency-response comparison.
