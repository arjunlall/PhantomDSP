# Synthetic Reference Room

This experiment builds a second speaker renderer without copying the original JBL room response. The production `Speaker Virtualization.txt` remains the default and listening reference.

## Design Boundary

The renderer is divided into three independently testable stages:

1. **Personal direct sound:** broad ear, pinna, and head-shadow magnitude cues from the existing in-ear BRIRs, with measured room timing removed.
2. **Synthetic early reflections:** geometrically generated arrivals filtered for their incident directions.
3. **Shared late field:** diffuse binaural decay with controlled interaural coherence and no copied room modes.

The first prototype implements only stage 1. Its purpose is to test whether the personalized direct anchor and theoretical timing are credible before room energy is added.

## Personal Direct Prototype

`tools/measurement/render_synthetic_direct.py` performs the following deterministic operations:

- Applies a smooth window from −3 ms through +4 ms around each BRIR path's direct peak. The first repeatable measured-room cluster begins after +5 ms.
- Uses only windowed magnitudes; measured peak positions and absolute propagation delay are discarded.
- Averages `LL` with `RR` and `LR` with `RL` in log magnitude. This preserves a personal ipsilateral and contralateral shape without treating one old left/right difference as proven anatomy.
- Uses 1/12-octave regularization through most of the HRTF band and progressively stronger smoothing above 10 kHz.
- Uses the accepted renderer only as a broad sub-300 Hz magnitude calibration. The bass is reconstructed minimum-phase, so old bass timing and room resonances are not retained.
- Reconstructs causal minimum-phase filters and adds a 12.534-sample contralateral delay derived from an 8.75 cm spherical head and ±30° speakers.

The generated 48 kHz, 24-bit IRs contain 8,192 samples and live under `Synthetic Reference Room/IRs/direct/`. Exact inputs, hashes, parameters, plots, and timing metrics are recorded in the [analysis summary](../measurements/synthetic-reference-room/direct-only/analysis/summary.json).

## A/B Listening

In `config - personalized.txt`, disable the production renderer before enabling:

```text
# Include: JBL M2 Binaural Convolution\Speaker Virtualization.txt
Include: Synthetic Reference Room\Personal Direct Renderer.txt
```

Never enable both renderers simultaneously. Keep the target, headphone compensation, and personal balance includes unchanged.

Compare vocal center position, frontal distance, image width, bass quantity, transient response, and treble plausibility. The direct-only version is expected to sound drier and less externalized; that is not yet a rejection. The useful question is whether sources remain tonally credible and directionally anchored enough to justify adding theoretical reflections.

## Next Stages

- Add a direct-only generic-HRTF control to reveal which benefits are actually personal.
- Add sparse image-source reflections with theoretical path lengths and directional filtering.
- Add a shared late reverberation network, tuned only from broad room-decay preferences.
- Validate each stage through Equalizer APO Benchmark and controlled listening before promotion.
