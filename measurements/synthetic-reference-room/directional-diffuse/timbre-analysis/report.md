# Candidate K Timbre Audit

This audit tests whether K's deterministic microclusters add too much broad upper-frequency energy. It evaluates auditory-band power rather than raw comb-filter teeth.

## Method

- Reconstruct K's personal direct, treated specular, directional microcluster, and synthetic late branches.
- Integrate their spectra with symmetric Moore-Glasberg ERB-spaced rounded-exponential filters from 1.5-12 kHz.
- Calculate both K's coherent complete response and a decorrelated energy bound.
- Predict the diffuse envelope from the personal direct paths, matched directional HRTF ratios, modeled monitor directivity, and treated-surface absorption.
- Anchor theoretical and current microcluster power only from 800 Hz-1.25 kHz. No old-room upper-frequency target is used in the theoretical curve.

## Result

Decision: **branch-only correction warranted**.

| Speaker | 6-10 kHz mean K minus theory | RMS | Range |
| --- | ---: | ---: | ---: |
| Left | +11.57 dB | 12.00 dB | +6.21 to +17.13 dB |
| Right | +11.30 dB | 11.84 dB | +4.15 to +16.41 dB |

## Model Sensitivity

| Scenario | Left 6-10 kHz K minus theory | Right 6-10 kHz K minus theory |
| --- | ---: | ---: |
| full treated-room model | +11.57 dB | +11.30 dB |
| half-strength losses | +5.98 dB | +5.76 dB |
| speaker directivity only | +5.44 dB | +5.13 dB |
| surface absorption only | +6.36 dB | +6.26 dB |
| directional HRTF only | +0.21 dB | +0.07 dB |

## Band Detail

| Band | Left K minus theory | Right K minus theory | Left net coherent effect | Right net coherent effect |
| --- | ---: | ---: | ---: | ---: |
| 1.5-3 kHz | -2.85 dB | -4.44 dB | +0.72 dB | +0.71 dB |
| 3-5 kHz | -5.20 dB | -6.99 dB | +0.12 dB | +0.14 dB |
| 5-7 kHz | +4.99 dB | +3.60 dB | +1.15 dB | +1.42 dB |
| 7-10 kHz | +12.72 dB | +13.10 dB | +3.78 dB | +4.22 dB |
| 10-12 kHz | +13.22 dB | +10.59 dB | +2.22 dB | +2.19 dB |

The theoretical envelope is a model of this repository's intended room, not a universal mastering-room target. A correction is justified only when the discrepancy is broad, consistent between speakers, and large enough to survive auditory-band smoothing.

## Research Basis

- [Moore and Glasberg, Suggested formulae for calculating auditory-filter bandwidths and excitation patterns](https://pubmed.ncbi.nlm.nih.gov/6630731/)
- [Olive and Toole, The Detection of Reflections in Typical Rooms](https://secure.aes.org/forum/pubs/journal/?elib=6079)

## Plots

- `microcluster-envelope-vs-theory.svg`
- `microcluster-current-minus-theory.svg`
- `microcluster-model-sensitivity.svg`
- `left-auditory-room-contribution.svg`
- `right-auditory-room-contribution.svg`
