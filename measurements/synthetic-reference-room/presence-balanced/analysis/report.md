# Presence-Balanced Room

This opt-in candidate keeps K's personal direct sound, bass, treated specular field, late field, timing, and directional interaural ratios. It changes only the shared spectral envelope of each virtual speaker's deterministic microcluster branch.

## Design

- The ERB-smoothed K-minus-theoretical excess is converted to attenuation only; no deficient band is boosted.
- Correction fades in from 5.5-7.5 kHz, remains active through 12 kHz, and fades out by 14 kHz.
- The same causal minimum-phase filter is applied to both ear paths from each speaker, preserving directional ratios and adding no bulk delay.

## Offline Result

| Speaker | Residual microcluster excess, 6-10 kHz | Complete response change, 6-10 kHz |
| --- | ---: | ---: |
| Left | +1.46 dB | -3.01 dB |
| Right | +1.14 dB | -3.18 dB |

Modeled maximum correlated gain: +2.63 dB.

## Plots

- `microcluster-timbre-filters.svg`
- `microcluster-residual-vs-theory.svg`
- `k-versus-presence-balanced-full-spectrum.svg`
- `presence-balanced-minus-k.svg`

## Controlled K/L/M Diagnostic

Informal listening preferred L's overall naturalness to K but found that L reduced some string-pick articulation relative to physical monitor playback. M changes only the low-frequency entrance of L's microcluster attenuation: it begins at 5.5 kHz and reaches full L strength at 7.5 kHz. Above 7.5 kHz, the requested treatment curve remains L's.

| Band | M minus L, left | M minus L, right | M minus K, left | M minus K, right |
| --- | ---: | ---: | ---: | ---: |
| 4.5-5.5 kHz | +0.03 dB | +0.03 dB | -0.02 dB | -0.03 dB |
| 5.5-6.5 kHz | +0.44 dB | +0.52 dB | -0.59 dB | -0.42 dB |
| 6.5-7.5 kHz | +0.14 dB | +0.28 dB | -3.29 dB | -3.22 dB |
| 7.5-9 kHz | -0.01 dB | -0.01 dB | -3.93 dB | -4.35 dB |
| 9-11 kHz | -0.00 dB | -0.00 dB | -2.47 dB | -2.58 dB |
| 11-14 kHz | -0.00 dB | -0.00 dB | -0.70 dB | -0.72 dB |

Modeled maximum correlated gain remains +2.63 dB.

- `k-l-m-presence-region.svg`
