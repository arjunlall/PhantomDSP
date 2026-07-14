# A100 Renderer Reference

This analysis removes the measured downstream target, headphone, and personal EQ from the four Benchmark matrices. The resulting archive is the speaker-renderer-only A100 target used by the minimum-latency 2×2 redesign.

## Validation

- Gain-calibrated precision captures were used for the convolved and clean branches (+24 dB and +48 dB respectively); stored spectra have those measurement gains removed.
- Downstream off-diagonal leakage: -180.00 dB.
- De-embedded combined ≈ convolved + clean closure: -37.84 dB RMS at 20–80 Hz, -33.39 dB at 20–300 Hz, and -33.72 dB at 20 Hz–20 kHz.
- Every isolated impulse capture reports zero clipped samples.
- The combined reference remains a separate 16-bit capture, so use smoothed low-frequency targets rather than treating residual closure or quantization ripple as acoustic detail.

## Timing

| Path | −60 dB onset | −40 dB onset | Peak | Peak time |
| --- | ---: | ---: | ---: | ---: |
| `LL` | 2 | 34 | 142 | 2.958 ms |
| `LR` | 16 | 21 | 154 | 3.208 ms |
| `RL` | 16 | 21 | 155 | 3.229 ms |
| `RR` | 2 | 32 | 141 | 2.938 ms |

Machine-readable spectra are stored in `deembedded-reference.npz`; source metadata and validation metrics are in `summary.json`.
