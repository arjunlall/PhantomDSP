# Digital Baseline Analysis

This report describes the complete Equalizer APO digital renderer. It does not include the physical headphone-to-ear transfer function and therefore is not a closed-loop acoustic validation.

## Path Timing and Level

| Path | −50 dB onset | −40 dB onset | Peak sample | Peak time | Normalized peak | Output peak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `LL` | 190 | 220 | 242 | 5.042 ms | -27.53 dB | -27.53 dBFS |
| `LR` | 154 | 192 | 251 | 5.229 ms | -41.40 dB | -41.40 dBFS |
| `RL` | 106 | 196 | 254 | 5.292 ms | -40.62 dB | -40.62 dBFS |
| `RR` | 181 | 217 | 235 | 4.896 ms | -28.41 dB | -28.41 dBFS |

## Spatial Timing Summary

- Direct-path peak spread: 7 samples.
- Cross-path peak spread: 3 samples.
- Mean cross-minus-direct peak offset: 14.00 samples (0.292 ms).

## Benchmark Runs

| Run | Maximum output | Clipped samples | One-core CPU |
| --- | ---: | ---: | ---: |
| left impulse | -27.53 dBFS | 0 | 3.23% |
| right impulse | -28.40 dBFS | 0 | 3.20% |
| correlated stereo sweep | -5.36 dBFS | 0 | 3.15% |

## Plots

- [Impulse response](impulse-response.svg)
- [Magnitude response](magnitude-response.svg)
- [Wrapped phase response](phase-response.svg)
- [Group delay](group-delay.svg)
- [Energy decay](energy-decay.svg)

Equalizer APO Benchmark writes 16-bit output. Low-level onsets and decay near the quantization limit—especially on quieter cross paths—should not be treated as exact. Use the original 24-bit IRs when selecting a sample-trim boundary.

The machine-readable frequency samples, path metrics, hashes, and Benchmark results are stored in [`summary.json`](summary.json).
