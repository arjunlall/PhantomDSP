# BRIR Advance Analysis

This experiment removes common leading time from the two active BRIR files without changing their relative channel timing. It does not change the active Equalizer APO configuration.

## Prefix and Transfer Error

The analyzer evaluated 100, 160, 192, 196, and 200 samples. The 100-sample endpoint permits a coherent advance of legacy renderer A; 160 remains a research control, and 200 exposes the desired maximum. The 192 and 196 variants save within 0.17 ms of 200 and showed no consistent fidelity advantage, so they were not rendered.

| Path | 100 peak | 100 energy | 160 peak | 160 energy | 200 peak | 200 energy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `LL` | -75.32 dB | -72.59 dB | -67.25 dB | -65.99 dB | -61.32 dB | -59.09 dB |
| `LR` | -66.34 dB | -66.80 dB | -61.17 dB | -60.11 dB | -55.65 dB | -55.01 dB |
| `RL` | -65.38 dB | -68.98 dB | -63.84 dB | -62.72 dB | -59.17 dB | -57.52 dB |
| `RR` | -73.59 dB | -73.88 dB | -70.12 dB | -66.28 dB | -65.34 dB | -61.21 dB |

Across individual paths, worst 20–200 Hz RMS magnitude error is 0.085 dB for 100 samples, 0.171 dB for 160, and 0.173 dB for 200. Their worst 99th-percentile magnitude errors are 0.45, 0.91, and 0.76 dB. Worst 99th-percentile interchannel phase errors are 3.22°, 3.62°, and 4.26°. Above 200 Hz, the 100-sample candidate remains below 0.041 dB RMS; every candidate remains below 0.067 dB. These are small listening-candidate errors, not mathematical identity.

All rendered variants retain exact sample values after the cut, apply the same shift to every path, preserve the 48 kHz/24-bit/stereo/32,768-frame format, and zero-pad the tail. Direct peaks remain aligned within one sample; cross-ear peaks retain their approximately 13-sample lag.

## Clean-Bass Coupling

The existing clean branch has a shared 100-sample explicit delay. Reducing it to zero advances that branch by exactly 100 samples. A100 therefore retains the original branch relationship; its only modeled deviation is the small discarded-prefix error above. Larger BRIR advances leave the clean branch behind. The table models those mismatched renderers against an ideal common advance of the current complete response; gain and the 15-sample cross offset are unchanged.

| Renderer | BRIR advance | Remaining clean lag | Worst 25–60 Hz RMS error | Worst 60–150 Hz RMS error | Worst branch interference |
| --- | ---: | ---: | ---: | ---: | ---: |
| A, legacy | 160 | 60 samples | 0.14 dB | 2.75 dB | -12.48 dB |
| A, legacy | 200 | 100 samples | 0.25 dB | 3.79 dB | -12.66 dB |
| C, LR4 65 Hz | 160 | 60 samples | 0.53 dB | 1.41 dB | -5.69 dB |
| C, LR4 65 Hz | 200 | 100 samples | 0.86 dB | 2.40 dB | -9.54 dB |

Neither 160 nor 200 meets the planned −3 dB transition-interference limit with the existing clean-bass topology. A200 is available only as a listening diagnostic; adopting it would require a short BRIR-derived low-frequency renderer or spectral replacement that moves the bass path with the same common advance.

## Listening Outcome

- **A100 accepted:** sounds like the original A renderer while providing the coherent 100-sample advance. It is now the default.
- **A200 rejected:** completely ruins the bass, consistent with the modeled 100-sample relative lag, up to 10.53 dB transition-magnitude error, and −12.66 dB worst branch interference.

A Benchmark capture would quantify the exact Equalizer APO output but is not needed to explain the A200 failure. Any future 200-sample candidate must redesign the low-frequency path before further listening.

## Reproduction

Run from the repository root:

```bash
python tools/measurement/render_ir_advances.py --manifest measurements/ir-advance/render-manifest.json
python tools/measurement/analyze_ir_advances.py --output measurements/ir-advance/analysis.json
python tools/measurement/analyze_latency_bass_coupling.py --output measurements/ir-advance/bass-coupling.json
```

The analysis commands require NumPy. Machine-readable results and asset hashes are stored beside this report.
