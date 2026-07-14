# BRIR Advance Analysis

This experiment removes common leading time from the two active BRIR files without changing their relative channel timing. It does not change the active Equalizer APO configuration.

## Prefix and Transfer Error

The analyzer evaluated 160, 192, 196, and 200 samples. Only 160 and 200 were rendered: 192 and 196 save within 0.17 ms of 200 and showed no consistent fidelity advantage.

| Path | 160 discarded peak | 160 discarded energy | 200 discarded peak | 200 discarded energy |
| --- | ---: | ---: | ---: | ---: |
| `LL` | -67.25 dB | -65.99 dB | -61.32 dB | -59.09 dB |
| `LR` | -61.17 dB | -60.11 dB | -55.65 dB | -55.01 dB |
| `RL` | -63.84 dB | -62.72 dB | -59.17 dB | -57.52 dB |
| `RR` | -70.12 dB | -66.28 dB | -65.34 dB | -61.21 dB |

Across individual paths, worst 20–200 Hz RMS magnitude error is 0.171 dB for 160 samples and 0.173 dB for 200. Their worst 99th-percentile magnitude errors are 0.91 and 0.76 dB. Worst 99th-percentile interchannel phase errors are 3.62° and 4.26°. Above 200 Hz, RMS magnitude errors remain below 0.067 dB. These are small listening-candidate errors, not mathematical identity.

Both variants retain exact sample values after the cut, apply the same shift to every path, preserve the 48 kHz/24-bit/stereo/32,768-frame format, and zero-pad the tail. Direct peaks remain aligned within one sample; cross-ear peaks retain their approximately 13-sample lag.

## Clean-Bass Coupling

The existing clean branch has a shared 100-sample explicit delay. Reducing it to zero advances that branch by only 100 samples. The table models the resulting renderer against an ideal common advance of its current complete response; gain and the 15-sample cross offset are unchanged.

| Renderer | BRIR advance | Remaining clean lag | Worst 25–60 Hz RMS error | Worst 60–150 Hz RMS error | Worst branch interference |
| --- | ---: | ---: | ---: | ---: | ---: |
| A, legacy | 160 | 60 samples | 0.14 dB | 2.75 dB | -12.48 dB |
| A, legacy | 200 | 100 samples | 0.25 dB | 3.79 dB | -12.66 dB |
| C, LR4 65 Hz | 160 | 60 samples | 0.53 dB | 1.41 dB | -5.69 dB |
| C, LR4 65 Hz | 200 | 100 samples | 0.86 dB | 2.40 dB | -9.54 dB |

None meets the planned −3 dB transition-interference limit. Therefore the advanced WAVs are valid derived assets, but neither should be placed in the full renderer with the current clean-bass topology. A short BRIR-derived low-frequency renderer or spectral replacement must move the bass path with the same common advance.

## Reproduction

Run from the repository root:

```bash
python tools/measurement/render_ir_advances.py --manifest measurements/ir-advance/render-manifest.json
python tools/measurement/analyze_ir_advances.py --output measurements/ir-advance/analysis.json
python tools/measurement/analyze_latency_bass_coupling.py --output measurements/ir-advance/bass-coupling.json
```

The analysis commands require NumPy. Machine-readable results and asset hashes are stored beside this report.
