# Directional HRTF Reproduction

Candidate K uses public ARI Loudspeaker Array Studio directional transfer functions to estimate how the personal ±30° direct response should change for lateral, floor, and ceiling arrivals. Raw third-party SOFA files are intentionally not committed: the full local screen is large, independently licensed, and reproducible from authoritative sources. The repository instead keeps exact source metadata, hashes, analysis code, plots, and the compact derived model.

## Sources and Attribution

- [ARI HRTF Database](https://www.oeaw.ac.at/en/ari/outreach/software/hrtf-database)
- [ARI LAS SOFA directory](https://sofacoustics.org/data/database/ari%20%28las%29/)
- [SOFA database catalog](https://www.sofaconventions.org/mediawiki/index.php/Files)
- License recorded in the SOFA files: [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)

The exact five selected files, direct download URLs, byte sizes, SHA-256 hashes, frequency scales, and match errors are pinned in [`selected-ari-las-sources.json`](../measurements/synthetic-reference-room/directional-hrtf/selected-ari-las-sources.json). Do not treat the subject identifiers as personal data from this repository; they are ARI dataset identifiers.

## Full Screening Reproduction

Install the measurement dependencies, fetch the official directory, and rerun the screen:

```bash
python3 -m venv .venv
.venv/bin/pip install -r tools/measurement/requirements.txt
PYTHONPATH=tools/measurement .venv/bin/python tools/measurement/fetch_ari_directional_subset.py --variant las --all
PYTHONPATH=tools/measurement .venv/bin/python tools/measurement/analyze_directional_hrtf.py --input measurements/hrtf-datasets/ari-las --output measurements/synthetic-reference-room/directional-hrtf/analysis/ari-las
```

On the 2026-07-15 retrieval, the official directory supplied 160 files. The analyzer used 150 full-resolution subjects and skipped ten 91-direction files. It matched direction-centered `LL/LR/RL/RR` responses from 4–12 kHz after 1/6-octave smoothing and searched frequency scales from 0.85–1.15 in 0.005 steps.

## Fast Final-Model Rebuild

To reproduce only the selected ensemble rather than repeat the population screen:

```bash
PYTHONPATH=tools/measurement .venv/bin/python tools/measurement/fetch_ari_directional_subset.py --variant las --subjects 965,1124,948,1145,1123 --output measurements/hrtf-datasets/ari-las-selected --expected-manifest measurements/synthetic-reference-room/directional-hrtf/selected-ari-las-sources.json
PYTHONPATH=tools/measurement .venv/bin/python tools/measurement/analyze_directional_hrtf.py --input measurements/hrtf-datasets/ari-las-selected --output /tmp/phantomdsp-selected-hrtf
shasum -a 256 /tmp/phantomdsp-selected-hrtf/directional-model.json
```

Expected model SHA-256:

```text
6675b7cb0b9f06b9661e0e6ad53f91860ba2415af81bd38f5c53bf578f4091c9
```

The checked-in model is [`analysis/ari-las/directional-model.json`](../measurements/synthetic-reference-room/directional-hrtf/analysis/ari-las/directional-model.json). It contains the five-subject median directional deltas on a compact 3–16 kHz grid; candidate K does not load SOFA files at runtime.

## Coordinate and Modeling Notes

- PhantomDSP room azimuth is negative-left/positive-right; SOFA azimuth is positive-left, so the analyzer reverses the sign.
- Requested directions are ±30° direct, approximately ±51–68° side walls, −40° floor, and +48° ceiling. The selected LAS grid is within about 1–3° except ceiling, which is 7.15° low.
- Public HRTFs supply directional ratios, not the absolute personal response. The personal four-path direct measurement remains the anchor.
- K redistributes existing microcluster energy between ears. Multiplying raw public ratios onto the branch would double-count head shadow and change fused tonality.
- The selected-subject set is a pragmatic spectral match, not proof that those listeners share the user's anatomy or elevation perception. Preserve J as the control.

Rerender K with:

```bash
PYTHONPATH=tools/measurement .venv/bin/python tools/measurement/render_directional_diffuse_room.py
```

The expected K WAV hashes are recorded in the [Candidate K analysis](../measurements/synthetic-reference-room/directional-diffuse/analysis/summary.json) and verified by the unit tests.
