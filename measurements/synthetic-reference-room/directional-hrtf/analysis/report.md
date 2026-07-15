# Directional HRTF Screening

This analysis tests whether candidate J's elevated image could result from a missing directional pinna model. It does not render candidate K or alter J.

## Inputs and Method

- Public source: ARI in-ear directional transfer functions in SOFA format.
- Primary screen: 150 full-resolution laboratory-measurement subjects; ten reduced 91-direction files were excluded.
- Personal anchor: the four direction-centered personal direct paths at ±30° (`LL`, `LR`, `RL`, and `RR`).
- Match: 4–12 kHz, 1/6-octave smoothing, with a 0.85–1.15 frequency-scale search.
- Selected ensemble: `nh965`, `nh1124`, `nh948`, `nh1145`, and `nh1123`, matching the personal contrast within 0.880–1.124 dB RMS.

For each ear and room direction, the model uses only the public directional ratio:

```text
H_est(e, Ω) = H_personal(e, Ω0) × H_ARI(e, Ω) / H_ARI(e, Ω0)
```

The checked-in `ari-las/directional-model.json` contains the compact, hash-pinned five-subject median used by the K renderer. The downloaded SOFA files and their local manifest remain ignored. Exact selected-source URLs and hashes plus full and fast reproduction commands are in the [Directional HRTF reproduction guide](../../../../docs/hrtf-reproduction.md).

## Finding

The original renderer computes elevation but filters only for azimuth. However, the explicit floor and ceiling reflections are too quiet to explain the 7–8 kHz complete-to-direct rise: they sit roughly 24–31 dB below direct there. The deterministic microclusters sit roughly 6–8 dB above the notched direct response and dominate the synthetic early field.

Applying raw directional ratios to those already calibrated microclusters would double-count head shadow and strongly boost some cross-ear paths. Candidate K therefore uses the ensemble only to derive a desired two-ear power allocation, while preserving each speaker's existing fused microcluster response. See the [Candidate K report](../../directional-diffuse/analysis/report.md).

Research sources: [ARI HRTF Database](https://www.oeaw.ac.at/en/ari/outreach/software/hrtf-database), [SOFA files](https://www.sofaconventions.org/mediawiki/index.php/Files), and [Langendijk and Bronkhorst](https://doi.org/10.1121/1.424945).
