# Digital Baseline Analysis

This report describes the complete Equalizer APO digital renderer. It does not include the physical headphone-to-ear transfer function and therefore is not a closed-loop acoustic validation.

## Path Timing and Level

| Path | −50 dB onset | −40 dB onset | Peak sample | Peak time | Normalized peak | Output peak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `LL` | 195 | 220 | 242 | 5.042 ms | -27.48 dB | -27.48 dBFS |
| `LR` | 158 | 206 | 251 | 5.229 ms | -41.59 dB | -41.59 dBFS |
| `RL` | 106 | 214 | 254 | 5.292 ms | -40.68 dB | -40.68 dBFS |
| `RR` | 201 | 224 | 235 | 4.896 ms | -28.34 dB | -28.34 dBFS |

## Spatial Timing Summary

- Direct-path peak spread: 7 samples.
- Cross-path peak spread: 3 samples.
- Mean cross-minus-direct peak offset: 14.00 samples (0.292 ms).

## Benchmark Runs

| Run | Maximum output | Clipped samples | One-core CPU |
| --- | ---: | ---: | ---: |
| left impulse | -27.48 dBFS | 0 | 3.22% |
| right impulse | -28.33 dBFS | 0 | 3.23% |
| correlated stereo sweep | -5.44 dBFS | 0 | 3.13% |

## Plots

- [Impulse response](impulse-response.svg)
- [Magnitude response](magnitude-response.svg)
- [Wrapped phase response](phase-response.svg)
- [Group delay](group-delay.svg)
- [Energy decay](energy-decay.svg)

Equalizer APO Benchmark writes 16-bit output. Low-level onsets and decay near the quantization limit—especially on quieter cross paths—should not be treated as exact. Use the original 24-bit IRs when selecting a sample-trim boundary.

The machine-readable frequency samples, path metrics, hashes, and Benchmark results are stored in [`summary.json`](summary.json).
