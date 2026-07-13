# Bass Crossover Candidate Comparison

This comparison uses Equalizer APO Benchmark captures of the legacy renderer (A), the 75 Hz LR4 candidate (B), and the 65 Hz LR4 candidate (C). It is digital-only and does not include the physical headphone transfer.

## Capture Validity

Both candidate selector snapshots contain exactly one intended active include. Each isolated combined capture is byte-identical to its complete-output reference, and no impulse or correlated-stereo sweep clipped.

| Variant | Sweep peak | Direct/cross peak timing | Branch closure RMS |
| --- | ---: | --- | ---: |
| A: legacy | -5.52 dBFS | reference | -36.8 to -33.9 dB |
| B: LR4 75 Hz | -5.36 dBFS | unchanged | -32.8 to -31.2 dB |
| C: LR4 65 Hz | -5.44 dBFS | unchanged | -36.2 to -34.8 dB |

## Broad Tonal Match

Values are binaural-average candidate-minus-A changes after one-third-octave smoothing. The signed mean indicates quantity; RMS includes remaining shape differences.

| Band | B mean | B RMS | C mean | C RMS |
| --- | ---: | ---: | ---: | ---: |
| 25–60 Hz | +0.42 dB | 0.70 dB | +0.03 dB | 0.90 dB |
| 60–110 Hz | +0.02 dB | 0.47 dB | +0.26 dB | 0.72 dB |
| 110–250 Hz | -0.07 dB | 0.58 dB | -0.05 dB | 0.57 dB |
| 25–250 Hz | +0.03 dB | 0.58 dB | +0.03 dB | 0.67 dB |

B's extra deep-bass level is small but consistent with it sounding slightly louder. C removes approximately 0.39 dB of that deep-bass average relative to B while keeping the overall 25–250 Hz mean unchanged.

## Branch Summation

The table reports the worst path in each band. One-third-octave values represent broad perceptual interaction; 1/24-octave values expose narrow cancellation.

| Band | A 1/3 | B 1/3 | C 1/3 | A 1/24 | B 1/24 | C 1/24 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 50–100 Hz | -4.15 dB | -2.64 dB | -3.11 dB | -6.16 dB | -2.35 dB | -3.90 dB |
| 60–110 Hz | -4.32 dB | -3.23 dB | -2.59 dB | -6.16 dB | -7.60 dB | -4.41 dB |
| 110–150 Hz | -3.98 dB | -3.49 dB | -2.30 dB | -9.23 dB | -9.87 dB | -5.39 dB |

B improves the intended region below 100 Hz but shifts deep narrow interactions to approximately 111–123 Hz. C is the strongest measured compromise across the complete 60–150 Hz handoff.

The average clean-to-convolved ratio from 60–110 Hz falls from roughly +17.9 dB in A to +5.9 dB in B and +0.8 dB in C. Because A externalized better despite containing substantially more clean energy, clean-path dominance alone does not explain B's weaker phantom speakers.

## Timing and Interpretation

All three variants retain the same broadband peak samples, seven-sample direct-path spread, and 14-sample mean cross-minus-direct offset. However, transfer-ratio analysis shows that B and C add several milliseconds of frequency-dependent group delay through the low-bass handoff, with larger unstable spikes near cancellation frequencies. The candidates also change left/right magnitude differently around 100–120 Hz even though their binaural-average target is close.

These time and interaural changes are more plausible causes of the perceived bass detachment and reduced frontal externalization than bass quantity alone. C is the only runtime-crossover candidate worth further listening. If C still weakens the phantom speakers, the next experiment should stop refining parallel IIR crossovers and instead build a short 2×2 low-frequency renderer derived from the BRIR, preserving interaural and arrival relationships without the unwanted room tail.

## Detailed Reports

- [A branch analysis](../bass-branches/analysis/report.md) and [A complete-output analysis](../digital-baseline/analysis/report.md)
- [B branch analysis](lr4-75/bass-branches/analysis/report.md) and [B complete-output analysis](lr4-75/digital/analysis/report.md)
- [C branch analysis](lr4-65/bass-branches/analysis/report.md) and [C complete-output analysis](lr4-65/digital/analysis/report.md)
