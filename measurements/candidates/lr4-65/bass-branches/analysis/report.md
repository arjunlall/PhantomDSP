# Bass Branch Analysis

This report compares the isolated convolved and clean-low branches after the exact shared Equalizer APO downstream processing. The measured combined capture validates their complex vector sum.

## Capture Validation

| Capture | Commit | Benchmark device | Impulse clipping |
| --- | --- | --- | ---: |
| combined | `f597334c69cb` | `Output A1 Voicemeeter PhantomDSP Bass Combined` | 0 |
| convolved | `f597334c69cb` | `Output A1 Voicemeeter PhantomDSP Bass Convolved` | 0 |
| clean | `f597334c69cb` | `Output A1 Voicemeeter PhantomDSP Bass Clean` | 0 |

## Transition Summary (50–200 Hz)

Interference compares the complex sum with the sum of branch magnitudes; 0 dB is perfectly in phase and increasingly negative values indicate cancellation. Closure RMS is normalized to the scalar branch energy so genuine cancellation does not make the routing check look artificially worse.

| Path | Deepest interference | Frequency | Clean/convolved there | Phase there | Minimum sum vs convolved | Closure RMS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `LL` | -5.35 dB | 111.7 Hz | -9.50 dB | -179.1° | -2.84 dB at 111.7 Hz | -36.2 dB |
| `LR` | -3.92 dB | 115.7 Hz | -10.49 dB | 159.6° | -1.63 dB at 115.7 Hz | -34.8 dB |
| `RL` | -4.68 dB | 200.0 Hz | -10.74 dB | -167.1° | -2.42 dB at 200.0 Hz | -35.1 dB |
| `RR` | -5.39 dB | 123.0 Hz | -5.58 dB | 131.3° | -2.01 dB at 122.7 Hz | -35.9 dB |

## Interpretation

- 4 of 4 paths exceed the planned 3 dB cancellation limit in the transition band, so the measured bass blend does not meet the acceptance criterion.
- The strongest cancellation is `RR` at 123.0 Hz: the clean branch is 5.58 dB below the convolved branch and their phase difference is 131.3°.
- Vector-sum closure is -36.2 to -34.8 dB RMS, which supports the branch routing and cancellation diagnosis at the available 16-bit precision.

## Closest Branch-Level Points

| Path | Closest-level frequency | Remaining mismatch | Phase difference | Interference |
| --- | ---: | ---: | ---: | ---: |
| `LL` | 80.9 Hz | -0.40 dB | -49.4° | -0.85 dB |
| `LR` | 98.5 Hz | -0.07 dB | 7.3° | -0.12 dB |
| `RL` | 112.8 Hz | -0.07 dB | 36.1° | -1.55 dB |
| `RR` | 88.3 Hz | -0.47 dB | -75.8° | -2.05 dB |

## Existing EQ Region

These samples cover the current narrow 118–135 Hz corrections. Values use 1/24-octave smoothing by default.

| Path | Frequency | Clean/convolved | Phase difference | Interference | Sum vs convolved |
| --- | ---: | ---: | ---: | ---: | ---: |
| `LL` | 117.9 Hz | -15.25 dB | -12.7° | -0.09 dB | 1.30 dB |
| `LL` | 120.8 Hz | -16.68 dB | 28.2° | -0.13 dB | 1.06 dB |
| `LL` | 124.1 Hz | -19.43 dB | 74.6° | -0.62 dB | 0.26 dB |
| `LL` | 135.1 Hz | -17.12 dB | 69.0° | -0.62 dB | 0.53 dB |
| `LR` | 117.9 Hz | -10.66 dB | -52.7° | -1.61 dB | 0.65 dB |
| `LR` | 120.8 Hz | -11.60 dB | 25.6° | -0.16 dB | 1.88 dB |
| `LR` | 124.1 Hz | -14.85 dB | 64.4° | -0.79 dB | 0.66 dB |
| `LR` | 135.1 Hz | -16.22 dB | 71.6° | -0.73 dB | 0.52 dB |
| `RL` | 117.9 Hz | -13.26 dB | 87.5° | -1.47 dB | 0.24 dB |
| `RL` | 120.8 Hz | -12.76 dB | 136.1° | -3.21 dB | -1.41 dB |
| `RL` | 124.1 Hz | -13.07 dB | -136.3° | -2.92 dB | -1.18 dB |
| `RL` | 135.1 Hz | -15.54 dB | 48.6° | -0.37 dB | 0.99 dB |
| `RR` | 117.9 Hz | -16.25 dB | 93.7° | -1.28 dB | -0.03 dB |
| `RR` | 120.8 Hz | -12.43 dB | 122.0° | -2.96 dB | -1.07 dB |
| `RR` | 124.1 Hz | -2.37 dB | 109.3° | -4.24 dB | 0.92 dB |
| `RR` | 135.1 Hz | -17.23 dB | 78.4° | -0.79 dB | 0.34 dB |

## Plots

- [Combined magnitude](combined-magnitude.svg), [convolved magnitude](convolved-magnitude.svg), and [clean magnitude](clean-magnitude.svg)
- [Combined group delay](combined-group-delay.svg), [convolved group delay](convolved-group-delay.svg), and [clean group delay](clean-group-delay.svg)
- [Clean-to-convolved level](clean-to-convolved.svg) and [phase difference](phase-difference.svg)
- [Vector-sum interference](interference.svg) and [combined relative to convolved](sum-vs-convolved.svg)
- [Measured vector-sum closure error](vector-sum-closure.svg)

The captures are 16-bit Benchmark outputs. The closure measurement distinguishes real branch interaction from routing or analysis errors, but extremely deep nulls remain quantization-sensitive.

Machine-readable samples, hashes, and metrics are stored in [`summary.json`](summary.json).
