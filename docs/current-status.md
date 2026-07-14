# Current DSP Work

This file is the short resume point for active experiments. Detailed measurements remain in the linked reports; normal playback directly includes the accepted `Speaker Virtualization.txt` renderer with no conditional routing.

## Synthetic Reference Room Experiment

Seven mutually exclusive renderers are now documented in the [synthetic reference-room experiment](synthetic-reference-room.md): A is production; B through F isolate direct, early, and late mechanisms; G is the complete synthetic soffit-mastering-room candidate. Production remains enabled by default.

B was benchmarked cleanly on Windows and sounded like ordinary headphones despite its theoretical ITD and personal direct-HRTF magnitude. C restored four distinct +4 to +30 ms paths and A-like comb density, but sounded perceptually like B: frontal yet immediately in front of the listener. Switching either B or C to A moved the image back several feet. Offline analysis confirms C's early energy is already comparable to A; its decisive difference is the absence of energy after 30 ms.

D preserves C bit-for-bit through 25 ms, adds a complementary 25–30 ms fade into the full measured decay, and keeps C's 250 Hz room high-pass, gain, direct timing, and bass. Its above-250 Hz decay closely follows A and its 20–80 Hz response changes by only 0.005 dB RMS.

Informal sighted listening with unchanged downstream filters found that D restored apparent monitor distance and sounded more spacious and preferable to A. This was not blinded or independently level matched. The result establishes sustained post-30 ms binaural decay—not early frequency-response combing alone—as necessary in this system, and makes D the frozen hybrid reference. D subsequently passed Windows Benchmark with no clipping or configuration errors, 4.84 dB correlated-sweep headroom, and 0.60–0.66% single-core CPU.

D's late field is now characterized as a broad target: 9.16 dB retained-C-to-late energy ratio, approximately 0.565 s decay, nearly equal late energy at both ears, low coherence above 500 Hz, and a smoothed at-ear spectral shape. Candidate E preserves C through the 25 ms boundary and generates a deterministic symmetric tail that matches those targets without copying D's late waveform. Its 20–80 Hz change from C is 0.00010 dB RMS and modeled correlated renderer gain is +3.43 dB.

E passed Windows Benchmark with no clipping or configuration errors, 4.61 dB correlated-sweep headroom, and 0.60–0.67% single-core CPU. Informal sighted comparison found no obvious difference between D and E; E sounded great and preserved the intended ±30° placement, while A sounded narrower at an estimated ±20–25°. E is now the accepted opt-in synthetic-late reference; A remains the production default.

Candidate F replaces C's measured +4 to +30 ms early field with six theoretical first-order image sources per speaker while keeping B's direct/bass stage and E's synthetic late branch fixed. It models a symmetric treated room, removes common propagation delay, matches C's combined early energy at −9.695 dB relative to direct, and copies no measured early- or late-room waveform. Relative to E, its change is 0.015 dB RMS at 20–80 Hz and 0.363 dB RMS at 80–200 Hz; modeled correlated renderer gain is +2.56 dB.

Extended listening found F good but less convincing than E: centered material moved close to the forehead, while focused left and right sources remained similarly placed. F's mono-center responses are sample-identical through 25.25 ms and its theoretical early center field has correlation 1.000 in every analyzed band. E diverges between ears at 4.21 ms and its measured-early center field has maximum broadband correlation 0.280. This identifies early binaural coherence—not speaker angle or late decay—as the next controlled problem.

Candidate G now combines mastering-room-inspired proportions, soffit-mounted ±30° mains, a 3 cm rigid lateral offset, controlled source directivity, attenuated specular paths, and equal-energy binaural diffusion. It keeps B's direct/bass stage and E's synthetic late branch fixed and copies no measured room waveform. Offline validation finds 0.168 maximum broadband center correlation, less than 0.001 dB left/right center-energy mismatch, 0.0248 dB RMS bass change from E, and +2.64 dB modeled maximum correlated gain. Every discrete 1–8 kHz reflection is at least 13.36 dB below direct sound.

Resume by committing and pushing G, switching exactly A to G on Windows, and running the standard three-probe Benchmark. If runtime validation passes, compare only E and G for center distance and stability, focused left/right placement, tonal continuity, audible echoes, and natural room spaciousness. The complete design and acceptance boundary are in the [synthetic mastering-room plan](synthetic-mastering-room-plan.md).

## Historical Bass Crossover Listening Decision

These historical labels belong only to the completed bass experiment; they are unrelated to the synthetic-room A/B/C/D/E conditions above.

- **Legacy topology (historical A):** preferred historical reference. It places bass with the phantom speakers and sounds less muddy or bloated; A100 retains this topology as the fallback.
- **LR4 75 Hz (historical B):** sounded clearer, slightly louder, and wider, but moved bass toward the headphones and weakened the frontal phantom speakers. The runnable candidate was removed.
- **LR4 65 Hz (historical C):** measured better through the transition, but also lost A's spatial bass placement and sounded muddier or more bloated. The runnable candidate was removed.

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
