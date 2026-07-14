# Current DSP Work

This file is the short resume point for active experiments. Detailed measurements remain in the linked reports; the active configuration selects the accepted D200 A-matched renderer by default.

## Bass Crossover Listening Decision

- **A — legacy topology:** preferred historical reference. It places bass with the phantom speakers and sounds less muddy or bloated; A100 retains this topology as the fallback.
- **B — LR4 75 Hz:** sounds clearer, slightly louder, and wider, but moves bass toward the headphones and weakens the frontal phantom speakers. Keep only as a diagnostic reference.
- **C — LR4 65 Hz:** measures better through the transition, but also loses A's spatial bass placement and sounds muddier or more bloated. Keep only as a diagnostic reference.

The [measured comparison](../measurements/candidates/bass-crossover-comparison.md) shows that clean-path dominance does not explain B's weaker externalization: A contains more clean energy yet externalizes better. Frequency-dependent group delay and changed interaural response around 100–120 Hz are the stronger suspects.

Decision: stop iterating the parallel LR4 crossover. D200 A-matched replaces it with one unified 2×2 renderer while retaining A100's bass presentation and quantity closely enough to pass both measurement and listening.

## Latency Experiment

The offline BRIR work is complete. Parent hashes, derived hashes, and channel timing are fixed in the [IR manifest](ir-manifest.md); detailed errors are in the [advance analysis](../measurements/ir-advance/report.md). Never overwrite or independently align the four parent channels.

Three exact asset sets now exist under `JBL M2 Binaural Convolution/IRs/advanced/`:

- **100 samples / 2.08 ms:** preferred transparency candidate; removing A's 100-sample clean-bass delay advances both branches equally.
- **160 samples / 3.33 ms:** conservative control; preserves every channel's −60 dB onset.
- **200 samples / 4.17 ms:** research target; removed IR content is small, but the current clean-bass branch cannot share the full advance.

The main latency checkpoints are:

- **A0:** original reference, unchanged.
- **A100:** known-good reference and fallback. BRIR and clean bass both advance 100 samples, producing an easy 2.08 ms win without an audible bass or spatial regression.
- **A200:** failed diagnostic. BRIR advances 200 samples while clean bass advances only 100; listening confirms that the resulting phase mismatch completely ruins the bass.
- **D200 v1:** rejected diagnostic. Its unified topology and timing worked, but it lost 7.22–8.91 dB RMS from 80–200 Hz.
- **D200 A-matched:** accepted default. It keeps the unified 2×2 topology and 200-sample BRIR advance while restoring the A100 handoff.

Controlled listening found no readily audible tonal or spatial difference between A100 and D200 A-matched, while finger drumming made the latency improvement clear. D200 A-matched therefore becomes the default; A100 remains the fastest safe rollback.

Resume sequence:

1. Keep D200 A-matched as the daily renderer and A100 as the fallback/reference.
2. Keep the generated WAVs and DSP parameters locked; their hashes and Windows capture now define the accepted version.
3. Use the precision de-embedded A100 archive under `measurements/minimum-latency/a100-reference/analysis` when reproducing the design target; do not infer it from headphone-compensated output.
4. Keep [D200 v1](../measurements/minimum-latency/d200-prototype/analysis/runtime-report.md), A200, B, and C only as documented diagnostics.
5. If latency work continues, measure the complete application-to-device path before modifying the accepted IRs. The remaining delay is no longer explained by BRIR direct arrival alone.

To roll back, change only the normal-playback lines in `JBL M2 Binaural Convolution/Bass Crossover Selector.txt`: comment D200 A-matched and uncomment A100. Never enable both normal renderers together. The reserved D200 v1 Benchmark route is diagnostic and does not affect ordinary playback.

Relative to A0, D200 A-matched removes 200 samples (4.17 ms) of common BRIR direct-arrival time; it removes another 100 samples (2.08 ms) relative to A100. These figures do not include application, driver, convolution-engine, mixer, or device-buffer latency.
