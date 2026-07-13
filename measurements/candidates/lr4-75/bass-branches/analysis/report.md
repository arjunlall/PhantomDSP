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
| `LL` | -9.87 dB | 111.3 Hz | -4.23 dB | 173.9° | -5.71 dB at 111.3 Hz | -32.8 dB |
| `LR` | -7.01 dB | 115.7 Hz | -4.90 dB | 163.3° | -3.17 dB at 115.4 Hz | -31.2 dB |
| `RL` | -8.17 dB | 122.7 Hz | -6.29 dB | 176.5° | -4.74 dB at 122.7 Hz | -31.7 dB |
| `RR` | -7.07 dB | 122.7 Hz | -1.48 dB | 132.3° | -2.20 dB at 121.9 Hz | -31.4 dB |

## Interpretation

- 4 of 4 paths exceed the planned 3 dB cancellation limit in the transition band, so the measured bass blend does not meet the acceptance criterion.
- The strongest cancellation is `LL` at 111.3 Hz: the clean branch is 4.23 dB below the convolved branch and their phase difference is 173.9°.
- Vector-sum closure is -32.8 to -31.2 dB RMS, which supports the branch routing and cancellation diagnosis at the available 16-bit precision.

## Closest Branch-Level Points

| Path | Closest-level frequency | Remaining mismatch | Phase difference | Interference |
| --- | ---: | ---: | ---: | ---: |
| `LL` | 94.8 Hz | -0.02 dB | 33.6° | -0.38 dB |
| `LR` | 104.0 Hz | -0.02 dB | 37.2° | -0.47 dB |
| `RL` | 95.2 Hz | -0.04 dB | 15.6° | -0.09 dB |
| `RR` | 89.7 Hz | -0.02 dB | -66.9° | -1.61 dB |

## Existing EQ Region

These samples cover the current narrow 118–135 Hz corrections. Values use 1/24-octave smoothing by default.

| Path | Frequency | Clean/convolved | Phase difference | Interference | Sum vs convolved |
| --- | ---: | ---: | ---: | ---: | ---: |
| `LL` | 117.9 Hz | -9.35 dB | -9.5° | -0.11 dB | 2.44 dB |
| `LL` | 120.8 Hz | -10.50 dB | 29.9° | -0.22 dB | 2.05 dB |
| `LL` | 124.1 Hz | -13.11 dB | 73.3° | -1.09 dB | 0.65 dB |
| `LL` | 135.1 Hz | -12.07 dB | 60.2° | -0.73 dB | 1.22 dB |
| `LR` | 117.9 Hz | -4.91 dB | -50.2° | -2.43 dB | 1.50 dB |
| `LR` | 120.8 Hz | -5.66 dB | 25.4° | -0.21 dB | 3.44 dB |
| `LR` | 124.1 Hz | -9.04 dB | 62.7° | -1.20 dB | 1.44 dB |
| `LR` | 135.1 Hz | -11.66 dB | 65.8° | -0.91 dB | 1.12 dB |
| `RL` | 117.9 Hz | -7.42 dB | 91.4° | -2.55 dB | 0.53 dB |
| `RL` | 120.8 Hz | -6.60 dB | 138.3° | -6.30 dB | -2.97 dB |
| `RL` | 124.1 Hz | -6.57 dB | -136.6° | -6.03 dB | -2.68 dB |
| `RL` | 135.1 Hz | -10.45 dB | 40.4° | -0.38 dB | 1.92 dB |
| `RR` | 117.9 Hz | -10.49 dB | 95.7° | -2.23 dB | 0.05 dB |
| `RR` | 120.8 Hz | -6.61 dB | 122.9° | -5.04 dB | -1.67 dB |
| `RR` | 124.1 Hz | 3.63 dB | 108.4° | -4.62 dB | 3.69 dB |
| `RR` | 135.1 Hz | -12.78 dB | 72.7° | -1.01 dB | 0.79 dB |

## Plots

- [Combined magnitude](combined-magnitude.svg), [convolved magnitude](convolved-magnitude.svg), and [clean magnitude](clean-magnitude.svg)
- [Combined group delay](combined-group-delay.svg), [convolved group delay](convolved-group-delay.svg), and [clean group delay](clean-group-delay.svg)
- [Clean-to-convolved level](clean-to-convolved.svg) and [phase difference](phase-difference.svg)
- [Vector-sum interference](interference.svg) and [combined relative to convolved](sum-vs-convolved.svg)
- [Measured vector-sum closure error](vector-sum-closure.svg)

The captures are 16-bit Benchmark outputs. The closure measurement distinguishes real branch interaction from routing or analysis errors, but extremely deep nulls remain quantization-sensitive.

Machine-readable samples, hashes, and metrics are stored in [`summary.json`](summary.json).
