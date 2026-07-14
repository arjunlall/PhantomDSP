# Current DSP Work

This file is the short resume point for active experiments. Detailed measurements remain in the linked reports; normal playback directly includes the accepted `Speaker Virtualization.txt` renderer with no conditional routing.

## Bass Crossover Listening Decision

- **A — legacy topology:** preferred historical reference. It places bass with the phantom speakers and sounds less muddy or bloated; A100 retains this topology as the fallback.
- **B — LR4 75 Hz:** sounded clearer, slightly louder, and wider, but moved bass toward the headphones and weakened the frontal phantom speakers. The runnable candidate was removed.
- **C — LR4 65 Hz:** measured better through the transition, but also lost A's spatial bass placement and sounded muddier or more bloated. The runnable candidate was removed.

The [measured comparison](../measurements/candidates/bass-crossover-comparison.md) shows that clean-path dominance does not explain B's weaker externalization: A contains more clean energy yet externalizes better. Frequency-dependent group delay and changed interaural response around 100–120 Hz are the stronger suspects.

Decision: stop iterating the parallel LR4 crossover. The production Speaker Virtualization renderer replaces it with one unified 2×2 matrix while retaining the legacy reference's bass presentation and quantity closely enough to pass both measurement and listening.

## Latency Experiment

The offline BRIR work is complete. Parent hashes, derived hashes, and channel timing are fixed in the [IR manifest](ir-manifest.md); detailed errors are in the [advance analysis](../measurements/ir-advance/report.md). Never overwrite or independently align the four parent channels.

Three exact asset sets now exist under `JBL M2 Binaural Convolution/IRs/advanced/`:

- **100 samples / 2.08 ms:** preferred transparency candidate; removing A's 100-sample clean-bass delay advances both branches equally.
- **160 samples / 3.33 ms:** conservative control; preserves every channel's −60 dB onset.
- **200 samples / 4.17 ms:** research target; removed IR content is small, but the current clean-bass branch cannot share the full advance.

Historical reports use experiment labels that are no longer production filenames:

| Historical label | Permanent meaning |
| --- | --- |
| A0 | `Original Parallel Bass Renderer.txt`; unadvanced historical baseline |
| A100 | `Legacy Parallel Bass Reference.txt`; known-good fallback with both branches advanced 100 samples |
| A200 | Failed split-timing experiment; the BRIR moved farther than the bass branch |
| D200 v1 | Removed steep-handoff experiment; unified timing but 7.22–8.91 dB RMS loss from 80–200 Hz |
| D200 A-matched | `Speaker Virtualization.txt`; accepted production renderer |

Controlled listening found no readily audible tonal or spatial difference between the legacy reference and Speaker Virtualization, while finger drumming made the latency improvement clear.

Resume sequence:

1. Keep `Speaker Virtualization.txt` as the daily renderer and `Legacy Parallel Bass Reference.txt` as the fallback/reference.
2. Keep the generated WAVs and DSP parameters locked; their hashes and Windows capture now define the accepted version.
3. Use the precision de-embedded archive under `measurements/minimum-latency/legacy-reference/analysis` when reproducing the design target; do not infer it from headphone-compensated output.
4. Treat D200 v1, A200, B, and C as historical findings only; their runnable files were removed after rejection and remain available in Git history.
5. If latency work continues, measure the complete application-to-device path before modifying the accepted IRs. The remaining delay is no longer explained by BRIR direct arrival alone.

To roll back, change only the first renderer include in `config - personalized.txt`: comment `Speaker Virtualization.txt` and uncomment `Legacy Parallel Bass Reference.txt`. Never enable both. Conditional benchmark routing lives separately under `tools/measurement/equalizerapo/` and is not part of normal playback.

Relative to the original renderer, Speaker Virtualization removes 200 samples (4.17 ms) of common BRIR direct-arrival time; it removes another 100 samples (2.08 ms) relative to the legacy fallback. The 200-sample value remains a documented implementation property, not the renderer's identity. These figures do not include application, driver, convolution-engine, mixer, or device-buffer latency.
