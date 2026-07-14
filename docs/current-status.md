# Current DSP Work

This file is the short resume point for active experiments. Detailed measurements remain in the linked reports; the active public configuration continues to select the legacy renderer by default.

## Bass Crossover Listening Decision

- **A — legacy:** preferred reference and current default. It places bass with the phantom speakers and sounds less muddy or bloated.
- **B — LR4 75 Hz:** sounds clearer, slightly louder, and wider, but moves bass toward the headphones and weakens the frontal phantom speakers. Keep only as a diagnostic reference.
- **C — LR4 65 Hz:** measures better through the transition, but also loses A's spatial bass placement and sounds muddier or more bloated. Keep only as a diagnostic reference.

The [measured comparison](../measurements/candidates/bass-crossover-comparison.md) shows that clean-path dominance does not explain B's weaker externalization: A contains more clean energy yet externalizes better. Frequency-dependent group delay and changed interaural response around 100–120 Hz are the stronger suspects.

Decision: stop iterating the parallel LR4 crossover. Preserve A's bass topology unless a future design can retain its spatial presentation and quantity.

## Latency Experiment

The offline BRIR work is complete. Parent hashes, derived hashes, and channel timing are fixed in the [IR manifest](ir-manifest.md); detailed errors are in the [advance analysis](../measurements/ir-advance/report.md). Never overwrite or independently align the four parent channels.

Three exact asset sets now exist under `JBL M2 Binaural Convolution/IRs/advanced/`:

- **100 samples / 2.08 ms:** preferred transparency candidate; removing A's 100-sample clean-bass delay advances both branches equally.
- **160 samples / 3.33 ms:** conservative control; preserves every channel's −60 dB onset.
- **200 samples / 4.17 ms:** preferred latency target; removed content peaks at −55.65 dB or lower relative to its channel peak.

`JBL M2 Binaural Convolution/Bass Crossover Selector.txt` now exposes three A-based listening versions while retaining original A as the default:

- **A0:** original renderer, unchanged.
- **A100:** BRIR and clean bass both advanced 100 samples. This should preserve A apart from the very low-level discarded IR prefix.
- **A200:** BRIR advanced 200 samples while clean bass advances only 100. This intentionally exposes the larger direct-sound latency reduction with a known bass phase mismatch.

Select exactly one uncommented `Include:` line and lower playback volume before switching. B and C remain available as historical diagnostics.

Resume sequence:

1. Confirm all three presets load without errors on Windows.
2. Compare A0 with A100 for tonal, spatial, and bass transparency.
3. Compare A100 with A200 using a real-time reference such as instrument monitoring, video, or game input; ordinary music playback alone does not reveal absolute latency reliably.
4. Capture A100 and A200 through Equalizer APO Benchmark and re-run bass, timing, headroom, and channel-routing checks.
5. If A200's additional latency improvement matters perceptually, design an equally advanced short 2×2 low-frequency renderer. Otherwise adopt A100 and keep A's bass implementation unchanged.

The saved 3.33 or 4.17 ms is only the BRIR direct-arrival contribution. It does not reduce application, driver, convolution-engine, or device-buffer latency.
