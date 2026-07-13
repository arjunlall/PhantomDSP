# Bass Branch Analysis

This report compares the isolated convolved and clean-low branches after the exact shared Equalizer APO downstream processing. The measured combined capture validates their complex vector sum.

## Capture Validation

| Capture | Commit | Benchmark device | Impulse clipping |
| --- | --- | --- | ---: |
| combined | `15a841a22b82` | `Output A1 Voicemeeter PhantomDSP Bass Combined` | 0 |
| convolved | `15a841a22b82` | `Output A1 Voicemeeter PhantomDSP Bass Convolved` | 0 |
| clean | `15a841a22b82` | `Output A1 Voicemeeter PhantomDSP Bass Clean` | 0 |

## Transition Summary (50–200 Hz)

Interference compares the complex sum with the sum of branch magnitudes; 0 dB is perfectly in phase and increasingly negative values indicate cancellation. Closure RMS is normalized to the scalar branch energy so genuine cancellation does not make the routing check look artificially worse.

| Path | Deepest interference | Frequency | Clean/convolved there | Phase there | Minimum sum vs convolved | Closure RMS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `LL` | -9.23 dB | 118.7 Hz | 5.61 dB | -169.8° | 0.05 dB at 118.7 Hz | -36.8 dB |
| `LR` | -5.20 dB | 119.4 Hz | 9.76 dB | -166.0° | 3.90 dB at 161.1 Hz | -34.0 dB |
| `RL` | -6.02 dB | 134.8 Hz | 7.21 dB | -142.0° | 3.72 dB at 136.2 Hz | -35.9 dB |
| `RR` | -6.16 dB | 92.3 Hz | 9.04 dB | -172.5° | 3.76 dB at 114.3 Hz | -33.9 dB |

## Interpretation

- 4 of 4 paths exceed the planned 3 dB cancellation limit in the transition band, so the measured bass blend does not meet the acceptance criterion.
- The strongest cancellation is `LL` at 118.7 Hz: the clean branch is 5.61 dB above the convolved branch and their phase difference is -169.8°.
- Vector-sum closure is -36.8 to -33.9 dB RMS, which supports the branch routing and cancellation diagnosis at the available 16-bit precision.
- After smoothing, the combined output remains above the convolved branch alone across the transition band. The issue is therefore lost and path-dependent boost, not necessarily a net notch below the original convolved response.

## Closest Branch-Level Points

| Path | Closest-level frequency | Remaining mismatch | Phase difference | Interference |
| --- | ---: | ---: | ---: | ---: |
| `LL` | 183.8 Hz | -0.10 dB | -39.2° | -0.53 dB |
| `LR` | 163.7 Hz | 0.35 dB | -61.2° | -1.37 dB |
| `RL` | 190.1 Hz | -0.06 dB | 5.1° | -0.13 dB |
| `RR` | 170.3 Hz | 0.01 dB | -42.1° | -0.63 dB |

## Existing EQ Region

These samples cover the current narrow 118–135 Hz corrections. Values use 1/24-octave smoothing by default.

| Path | Frequency | Clean/convolved | Phase difference | Interference | Sum vs convolved |
| --- | ---: | ---: | ---: | ---: | ---: |
| `LL` | 117.9 Hz | 5.94 dB | 177.7° | -8.96 dB | 0.54 dB |
| `LL` | 120.8 Hz | 5.20 dB | -142.6° | -7.46 dB | 1.55 dB |
| `LL` | 124.1 Hz | 3.03 dB | -100.3° | -3.94 dB | 3.73 dB |
| `LL` | 135.1 Hz | 4.94 dB | -117.6° | -4.86 dB | 4.01 dB |
| `LR` | 117.9 Hz | 10.67 dB | 141.5° | -3.85 dB | 9.07 dB |
| `LR` | 120.8 Hz | 10.20 dB | -143.0° | -4.56 dB | 7.99 dB |
| `LR` | 124.1 Hz | 7.58 dB | -109.5° | -3.61 dB | 7.01 dB |
| `LR` | 135.1 Hz | 6.41 dB | -115.0° | -4.20 dB | 5.63 dB |
| `RL` | 117.9 Hz | 8.31 dB | -80.1° | -1.82 dB | 9.32 dB |
| `RL` | 120.8 Hz | 9.22 dB | -34.8° | -0.37 dB | 11.43 dB |
| `RL` | 124.1 Hz | 9.76 dB | 52.3° | -1.02 dB | 11.18 dB |
| `RL` | 135.1 Hz | 6.78 dB | -138.7° | -5.99 dB | 4.10 dB |
| `RR` | 117.9 Hz | 5.20 dB | -72.3° | -1.69 dB | 7.33 dB |
| `RR` | 120.8 Hz | 9.65 dB | -45.9° | -0.54 dB | 11.63 dB |
| `RR` | 124.1 Hz | 20.39 dB | -66.9° | -0.56 dB | 20.69 dB |
| `RR` | 135.1 Hz | 5.11 dB | -109.6° | -4.11 dB | 4.86 dB |

## Plots

- [Combined magnitude](combined-magnitude.svg), [convolved magnitude](convolved-magnitude.svg), and [clean magnitude](clean-magnitude.svg)
- [Combined group delay](combined-group-delay.svg), [convolved group delay](convolved-group-delay.svg), and [clean group delay](clean-group-delay.svg)
- [Clean-to-convolved level](clean-to-convolved.svg) and [phase difference](phase-difference.svg)
- [Vector-sum interference](interference.svg) and [combined relative to convolved](sum-vs-convolved.svg)
- [Measured vector-sum closure error](vector-sum-closure.svg)

The captures are 16-bit Benchmark outputs. The closure measurement distinguishes real branch interaction from routing or analysis errors, but extremely deep nulls remain quantization-sensitive.

Machine-readable samples, hashes, and metrics are stored in [`summary.json`](summary.json).
