# Timbre-Balanced Directional Room

This opt-in candidate keeps K's personal direct sound, bass, treated specular field, late field, timing, and directional interaural ratios. It changes only the shared spectral envelope of each virtual speaker's deterministic microcluster branch.

## Design

- The ERB-smoothed K-minus-theoretical excess is converted to attenuation only; no deficient band is boosted.
- Correction fades in from 4.5-6 kHz, remains active through 12 kHz, and fades out by 14 kHz.
- The same causal minimum-phase filter is applied to both ear paths from each speaker, preserving directional ratios and adding no bulk delay.

## Offline Result

| Speaker | Residual microcluster excess, 6-10 kHz | Complete response change, 6-10 kHz |
| --- | ---: | ---: |
| Left | +0.00 dB | -3.10 dB |
| Right | +0.00 dB | -3.33 dB |

Modeled maximum correlated gain: +2.62 dB.

## Plots

- `microcluster-timbre-filters.svg`
- `microcluster-residual-vs-theory.svg`
- `k-versus-timbre-balanced-full-spectrum.svg`
- `timbre-balanced-minus-k.svg`
