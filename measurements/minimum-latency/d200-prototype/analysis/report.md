# D200 Unified Renderer Prototype

This is an offline, opt-in prototype. A100 remains the active renderer.

## Locked Design

- Advance the de-embedded A100 convolved paths by another 100 samples, for a common 200-sample BRIR advance from the original assets.
- Preserve all four measured paths and their direct/cross peak spacing.
- Generate flat per-ear deep bass from the smoothed A100 20–45 Hz level, calibrated −0.75 dB so the complete 20–80 Hz response retains A100 quantity.
- Use a causal second-order 5 Hz protective high-pass and sixth-order 80 Hz Butterworth low-pass.
- Preserve the legacy 15-sample cross-path bass offset; no runtime parallel bass branch remains.

## Offline Results

- Mean smoothed 20–80 Hz deltas by path range from -0.16 to 0.25 dB versus A100.
- Synthetic bass is at least 21.99 dB below the advanced BRIR at 200 Hz.
- Low-frequency interaural phase differs from A100 by 2.63° RMS; 120–250 Hz differs from the advanced BRIR by 9.75° RMS.
- Low-model energy beyond the 32,768-sample output is below -136.60 dB relative to total energy.

| Path | −60 dB onset | −40 dB onset | Peak | Peak time |
| --- | ---: | ---: | ---: | ---: |
| `LL` | 6 | 25 | 42 | 0.875 ms |
| `LR` | 2 | 38 | 54 | 1.125 ms |
| `RL` | 5 | 42 | 55 | 1.146 ms |
| `RR` | 9 | 28 | 41 | 0.854 ms |

Next gate: capture the complete prototype through Equalizer APO Benchmark, then compare it with A100 before listening.
