# A100 Renderer Reference

This analysis removes the measured downstream target, headphone, and personal EQ from the four Benchmark matrices. The resulting archive is the speaker-renderer-only A100 target used by the minimum-latency 2×2 redesign.

## Validation

- Downstream off-diagonal leakage: -180.00 dB.
- De-embedded combined ≈ convolved + clean closure: -30.65 dB RMS at 20–80 Hz, -29.79 dB at 20–300 Hz, and -38.94 dB at 20 Hz–20 kHz.
- Every isolated impulse capture reports zero clipped samples.
- The independent 16-bit captures have the same approximate low-frequency closure floor as prior accepted branch measurements; use smoothed low-frequency targets rather than treating quantization ripple as acoustic detail.

## Timing

| Path | −60 dB onset | −40 dB onset | Peak | Peak time |
| --- | ---: | ---: | ---: | ---: |
| `LL` | 2 | 34 | 142 | 2.958 ms |
| `LR` | 16 | 21 | 154 | 3.208 ms |
| `RL` | 16 | 21 | 155 | 3.229 ms |
| `RR` | 2 | 32 | 141 | 2.938 ms |

Machine-readable spectra are stored in `deembedded-reference.npz`; source metadata and validation metrics are in `summary.json`.
