# Current DSP Work

This file is the short resume point for active experiments. Detailed measurements remain in the linked reports; the active configuration selects the accepted A100 renderer by default.

## Bass Crossover Listening Decision

- **A — legacy topology:** preferred reference. It places bass with the phantom speakers and sounds less muddy or bloated; A100 retains this topology as the current default.
- **B — LR4 75 Hz:** sounds clearer, slightly louder, and wider, but moves bass toward the headphones and weakens the frontal phantom speakers. Keep only as a diagnostic reference.
- **C — LR4 65 Hz:** measures better through the transition, but also loses A's spatial bass placement and sounds muddier or more bloated. Keep only as a diagnostic reference.

The [measured comparison](../measurements/candidates/bass-crossover-comparison.md) shows that clean-path dominance does not explain B's weaker externalization: A contains more clean energy yet externalizes better. Frequency-dependent group delay and changed interaural response around 100–120 Hz are the stronger suspects.

Decision: stop iterating the parallel LR4 crossover. Preserve A's bass topology unless a future design can retain its spatial presentation and quantity.

## Latency Experiment

The offline BRIR work is complete. Parent hashes, derived hashes, and channel timing are fixed in the [IR manifest](ir-manifest.md); detailed errors are in the [advance analysis](../measurements/ir-advance/report.md). Never overwrite or independently align the four parent channels.

Three exact asset sets now exist under `JBL M2 Binaural Convolution/IRs/advanced/`:

- **100 samples / 2.08 ms:** preferred transparency candidate; removing A's 100-sample clean-bass delay advances both branches equally.
- **160 samples / 3.33 ms:** conservative control; preserves every channel's −60 dB onset.
- **200 samples / 4.17 ms:** research target; removed IR content is small, but the current clean-bass branch cannot share the full advance.

`JBL M2 Binaural Convolution/Bass Crossover Selector.txt` exposes three A-based versions with A100 as the default:

- **A0:** original reference, unchanged.
- **A100:** accepted default. BRIR and clean bass both advance 100 samples, producing an easy 2.08 ms win without an audible bass or spatial regression.
- **A200:** failed diagnostic. BRIR advances 200 samples while clean bass advances only 100; listening confirms that the resulting phase mismatch completely ruins the bass.

Select exactly one uncommented `Include:` line and lower playback volume before switching. B and C remain available as historical diagnostics.

Resume sequence:

1. Keep A100 as the daily renderer and A0 as the reference fallback.
2. Use the checked-in de-embedded A100 renderer reference under `measurements/minimum-latency/a100-reference/analysis`; do not infer the target from headphone-compensated output.
3. Build a single 2×2 hybrid BRIR: clean room-regularized extension below the transition, original BRIR spatial information through upper bass and above, and a common 200-sample advance with no parallel clean branch.
4. Benchmark the complete candidate before comparing bass placement, extension, resonance, phantom-speaker stability, and finger-drumming latency against A100.

The accepted 2.08 ms saving is only the BRIR direct-arrival contribution. It does not reduce application, driver, convolution-engine, or device-buffer latency.
