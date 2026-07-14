# Current DSP Work

This file is the short resume point for active experiments. Detailed measurements remain in the linked reports; the active public configuration continues to select the legacy renderer by default.

## Bass Crossover Listening Decision

- **A — legacy:** reference and current default.
- **B — LR4 75 Hz:** sounds clearer, slightly louder, and wider, but moves bass toward the headphones and weakens the frontal phantom speakers. Keep only as a diagnostic reference.
- **C — LR4 65 Hz:** has the best measured 60–150 Hz branch summation and nearly unchanged broad bass quantity. Listening against A is still in progress.

The [measured comparison](../measurements/candidates/bass-crossover-comparison.md) shows that clean-path dominance does not explain B's weaker externalization: A contains more clean energy yet externalizes better. Frequency-dependent group delay and changed interaural response around 100–120 Hz are the stronger suspects.

Resume decision:

1. If C preserves A's frontal illusion while improving bass clarity, retain C as the leading runtime-crossover candidate and tune only broad level differences.
2. If C also weakens externalization, stop iterating parallel IIR crossovers. Build a short BRIR-derived 2×2 low-frequency renderer that preserves arrival and interaural relationships without the unwanted room tail.

## Latency Experiment

The offline BRIR work is complete. Parent hashes, derived hashes, and channel timing are fixed in the [IR manifest](ir-manifest.md); detailed errors are in the [advance analysis](../measurements/ir-advance/report.md). Never overwrite or independently align the four parent channels.

Two exact opt-in asset sets now exist under `JBL M2 Binaural Convolution/IRs/advanced/`:

- **160 samples / 3.33 ms:** conservative control; preserves every channel's −60 dB onset.
- **200 samples / 4.17 ms:** preferred latency target; removed content peaks at −55.65 dB or lower relative to its channel peak.

The WAVs themselves pass the offline checks, but no playback preset has been added. Even after reducing the clean branch's explicit delay from 100 samples to zero, it would lag the 200-sample BRIR advance by 100 samples. Modeling predicts new transition error and cancellation for both A and C, so wiring the files in now would confound latency with bass changes.

Resume sequence:

1. Finish the A/C externalization decision to choose the listening reference.
2. Build a short BRIR-derived 2×2 low-frequency renderer or complementary spectral replacement whose bass arrival shares the chosen BRIR advance. Prefer the 200-sample asset unless that design exposes a reason to use 160.
3. Add an opt-in full-renderer selector; leave A and both parent WAVs unchanged.
4. Capture the complete candidate through Equalizer APO Benchmark and re-run bass, timing, headroom, and channel-routing checks before listening.

The saved 3.33 or 4.17 ms is only the BRIR direct-arrival contribution. It does not reduce application, driver, convolution-engine, or device-buffer latency.
