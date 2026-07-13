# Bass Alignment Optimization

This offline search treats the clean-low branch like a subwoofer integrated with the convolved BRIR branch. It changes only clean-branch gain, polarity, and integer-sample delay in the measured complex responses; no Equalizer APO configuration is changed.

Candidates must keep every path's modeled 25–70 Hz output within 1.00 dB RMS of the current blend. This prevents the optimizer from avoiding cancellation by simply removing the clean bass.

## Model Comparison

| Model | Deepest interference | 10th percentile | Maximum low-bass change | Minimum sum vs convolved |
| --- | ---: | ---: | ---: | ---: |
| Current blend | -9.23 dB | -3.85 dB | 0.00 dB | 0.05 dB |
| Shared adjustment | -4.94 dB | -0.99 dB | 0.98 dB | 3.69 dB |
| Separate direct/cross | -4.85 dB | -1.87 dB | 1.00 dB | 3.68 dB |

## Deep-Bass Preservation Tradeoff

| Allowed 25–70 Hz RMS change | Shared worst interference | Separate direct/cross worst interference |
| ---: | ---: | ---: |
| 1.0 dB | -4.94 dB | -4.85 dB |
| 2.0 dB | -4.30 dB | -4.16 dB |
| 3.0 dB | -3.74 dB | -3.62 dB |
| 4.0 dB | -3.34 dB | -3.23 dB |
| 5.0 dB | -2.99 dB | -2.88 dB |
| 6.0 dB | -2.67 dB | -2.58 dB |

## Candidate Controls

Delays below are resulting clean-branch delays, including the current 100-sample direct and 115-sample cross values.

| Model | Direct paths (`LL`, `RR`) | Cross paths (`LR`, `RL`) |
| --- | --- | --- |
| Current blend | +0.00 dB, normal, 100 samples | +0.00 dB, normal, 115 samples |
| Shared adjustment | -0.25 dB, inverted, 180 samples | -0.25 dB, inverted, 195 samples |
| Separate direct/cross | -0.25 dB, inverted, 170 samples | +0.75 dB, normal, 75 samples |

## Best 1.0 dB-Constrained Direct/Cross Candidate

| Path | Deepest interference | Frequency | Clean/convolved there | Phase there | Low-bass RMS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| `LL` | -4.85 dB | 113.2 Hz | 10.33 dB | -178.7° | 1.00 dB |
| `LR` | -3.98 dB | 118.7 Hz | 10.80 dB | -152.4° | 0.73 dB |
| `RL` | -3.98 dB | 126.3 Hz | 11.83 dB | 177.7° | 0.75 dB |
| `RR` | -2.37 dB | 192.6 Hz | 1.73 dB | 80.9° | 0.97 dB |

## Interpretation

- The strongest tested model is the separate direct/cross candidate, improving worst-case interference from -9.23 to -4.85 dB.
- This does not yet meet the provisional no-cancellation-beyond-3-dB criterion in the 50–200 Hz transition band.
- Separate direct/cross controls improve the constrained worst case by only 0.09 dB versus the shared model, while changing the 10th-percentile result by -0.88 dB. That marginal result does not justify the added control complexity by itself.
- The first tested point that passes −3 dB allows 5.0 dB RMS of deep-bass change and uses +4.25 to +4.75 dB of clean-branch gain. It improves the interference ratio largely by making one branch dominate, not by creating a coherent crossover.
- No gain/polarity/delay-only candidate is recommended from this pass. The next experiment should use complementary filtering or spectral replacement to reduce the overlap itself.

## Plots

- [Worst-path interference comparison](interference-comparison.svg)
- [Best constrained output change by path](best-constrained-output-change.svg)
- [Deep-bass preservation tradeoff](preservation-tradeoff.svg)

Machine-readable controls, metrics, and search bounds are stored in [`summary.json`](summary.json).
