# Active IR Manifest

This manifest records both the original BRIR parents and the generated files loaded by `Speaker Virtualization.txt`. It preserves asset lineage without using experimental names as production identifiers.

## Original BRIR Parents

Both files are stereo 48 kHz, 24-bit PCM WAVs containing 32,768 frames (0.682667 seconds) and occupying 196,652 bytes.

| File | Channel 1 | Channel 2 | SHA-256 |
| --- | --- | --- | --- |
| `JBL LSR305 LL 4_LR 4 5-500.wav` | `LL`: left speaker to left ear | `LR`: left speaker to right ear | `4f6aa5b21cd94a075904573f56d7b4ade24ebf6737405984a34d41a956aa386b` |
| `JBL LSR305 RL 4_RR 4 5-500.wav` | `RL`: right speaker to left ear | `RR`: right speaker to right ear | `f733870e8ff87c578d57a30d5f898fea6f1d1cefe4aa15962fbe8912b1125efb` |

The files reside in `JBL M2 Binaural Convolution/IRs/`. Equalizer APO assigns their stereo channels to the selected virtual paths in order.

## Timing Landmarks

Onsets are the first samples reaching the stated level relative to that channel's absolute peak. Effective peak positions include the explicit delays in the active configuration.

| Path | −60 dB onset | −40 dB onset | Raw peak | Runtime delay | Effective peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `LL` | 206 | 225 | 242 | 0 | 242 |
| `LR` | 164 | 215 | 231 | 23 | 254 |
| `RL` | 176 | 232 | 245 | 10 | 255 |
| `RR` | 210 | 227 | 240 | 1 | 241 |

The runtime direct peaks are therefore aligned within one sample, while the cross-ear peaks arrive approximately 13 samples later. A 200-sample advance would preserve all content within 40 dB of each peak but would remove lower-level pre-peak energy in some paths. Candidate files must be inspected and compared rather than trimmed solely from the peak positions.

## Derived-File Requirements

Never overwrite the parent WAVs. For every processed variant, record:

- Parent filename and SHA-256.
- Operation and parameters, such as `non-circular advance: 196 samples`.
- Whether the tail was zero-padded and whether gain or normalization changed.
- Output sample rate, bit depth, channel order, frame count, and SHA-256.
- The tool or script version used to create it.

The planned advance experiment must apply the same sample shift to all four paths. Per-channel peak alignment would destroy the measured interaural timing.

## Advanced Candidates

The checked-in script `tools/measurement/render_ir_advances.py` verifies the parent hashes, removes complete stereo frames from the beginning, retains every later sample exactly, and appends zero frames to preserve length. It performs no normalization, resampling, or per-channel alignment.

| Advance | Parent speaker file | Derived SHA-256 |
| ---: | --- | --- |
| 100 samples | `JBL LSR305 LL 4_LR 4 5-500.wav` | `30c2c9918bf3b870bae5c37521ebf4cb0ca98989a41630d4fb69743d1fcbbea3` |
| 100 samples | `JBL LSR305 RL 4_RR 4 5-500.wav` | `7c339d76b3f03c540c8faf6f2766ba1ab8480f4cb3bbe55015569336d32d48f0` |
| 160 samples | `JBL LSR305 LL 4_LR 4 5-500.wav` | `7ecca2ebe74e9fc038216cceb36cd8f2d1f9abf3c6d9c910d358858f3500447f` |
| 160 samples | `JBL LSR305 RL 4_RR 4 5-500.wav` | `db30a3c4b6e5f5ade18e4ce5f23684b0857f4b0eac797621943ebd55f61137f6` |
| 200 samples | `JBL LSR305 LL 4_LR 4 5-500.wav` | `9a901597f5e704479899ca0903eeed2e4f3ca55476204e11164171e6159d2480` |
| 200 samples | `JBL LSR305 RL 4_RR 4 5-500.wav` | `9045fd83647956e76122967050860fedb190b90ce57462ed9d3147b9a0bf8dd9` |

All six files are stereo 48 kHz, 24-bit PCM with 32,768 frames. They reside in `IRs/advanced/`. See the [BRIR advance analysis](../measurements/ir-advance/report.md) for prefix loss, transfer error, and the clean-bass integration constraint.

## Active Generated Renderer

The active renderer uses a first-order 90 Hz clean model, +0.75 dB calibration, a 15-sample cross offset, one common −5 dB peaking correction at 350 Hz, Q 2, and a common 200-sample BRIR advance. The common correction cannot change interaural ratios.

| File | Channel 1 | Channel 2 | SHA-256 |
| --- | --- | --- | --- |
| `IRs/active/Left Speaker to Both Ears.wav` | `LL`: left speaker to left ear | `LR`: left speaker to right ear | `a87f182328216360bf7f0455bd4948f1d0b104c39a49b1ad25e31b59acb7eef6` |
| `IRs/active/Right Speaker to Both Ears.wav` | `RL`: right speaker to left ear | `RR`: right speaker to right ear | `6d21739c7885588f0f9bd9b7f2e575cd550462e83417f68cda35f3f4c0e21da5` |

These files are derived from `measurements/minimum-latency/legacy-reference/analysis/deembedded-reference.npz` with SHA-256 `2b4bf21d35a27e6a837017ecabada11a4330efd5101e4b82b74397c5fb8a3616`. They are stereo 48 kHz, 24-bit PCM with 32,768 frames, are not normalized, and are reproduced by `tools/measurement/render_active_renderer.py`. The [offline report](../measurements/minimum-latency/accepted-renderer/analysis/report.md) and [Windows runtime comparison](../measurements/minimum-latency/accepted-renderer/analysis/runtime-report.md) agree closely. Controlled listening found no readily audible tonal or spatial regression from the legacy reference while confirming the latency improvement.

## Synthetic Candidate I

`tools/measurement/render_tonally_normalized_room.py` verifies Candidate H as its parent, derives separate 1/6-octave-smoothed 200 Hz–1 kHz binaural tonal corrections for the left and right virtual speakers, and applies each correction identically to both ear paths from that speaker. The corrections are causal minimum phase, unity outside tapered 160 Hz–1.25 kHz boundaries, and preserve the 32,768-frame length without normalization.

| File | Parent SHA-256 | Derived SHA-256 |
| --- | --- | --- |
| `IRs/tonally-normalized/Tonally Normalized Room Left Speaker.wav` | `1b6c8b00b2eed642265114caf26e85f57decb26f54e1a530f4ff1fb63987a58d` | `3c7694241bf69a5d57759d3c3896d40533bb2b9f04ba6be7150f8f7b02fae882` |
| `IRs/tonally-normalized/Tonally Normalized Room Right Speaker.wav` | `f00cc29c8767513f636089cd45f59e7997214e558d44e002ed64f4b5d9cad854` | `06faacc6675991279232a2a1ac8cf57376e0a02a0eb5fc13c1d770dd98bf42a1` |

Both outputs are stereo 48 kHz, 24-bit PCM. Windows Benchmark verified the exact assets and routing with no clipping or configuration errors, 5.54 dB correlated-sweep headroom, and 0.60–0.67% single-core CPU. Exact response targets, filter behavior, spatial-preservation metrics, and plots are recorded in the [Candidate I analysis](../measurements/synthetic-reference-room/tonally-normalized/analysis/report.md).

## Synthetic Candidate J

`tools/measurement/render_tonally_normalized_room.py --candidate J` verifies Candidate I as its direct parent and adds separate broad 1–1.5 kHz complete-to-direct corrections for the left and right speakers. Each filter is shared by both ear paths, fades in from 900 Hz, uses a frequency-shaped release to unity by 1.8 kHz, and is generated without iterative narrow-band calibration.

| File | Parent I SHA-256 | Derived J SHA-256 |
| --- | --- | --- |
| `IRs/midrange-normalized/Midrange Normalized Room Left Speaker.wav` | `3c7694241bf69a5d57759d3c3896d40533bb2b9f04ba6be7150f8f7b02fae882` | `8b7e9015b2675a9e3b21b5f42c5a3eba56a3ceffb84d9f6cb8cc859eea3728d1` |
| `IRs/midrange-normalized/Midrange Normalized Room Right Speaker.wav` | `06faacc6675991279232a2a1ac8cf57376e0a02a0eb5fc13c1d770dd98bf42a1` | `ee42a346edee554f4de4388fdb4f25caec13b9d244a7b303098f5b6fa400f538` |

Both outputs are stereo 48 kHz, 24-bit PCM with 32,768 frames. The new filter starts at sample zero, adds no bulk delay, and leaves discarded convolution-tail energy below −113 dB. J has passed offline validation; Windows runtime validation remains pending. Exact filters, response deltas, and I/J plots are recorded in the [Candidate J analysis](../measurements/synthetic-reference-room/midrange-normalized/analysis/report.md).

## Synthetic Candidate K

`tools/measurement/render_directional_diffuse_room.py` verifies Candidate J and changes only the deterministic microcluster branch. It redistributes existing 4–12 kHz diffuse power between ears using the matched five-subject directional HRTF ensemble while preserving fused per-speaker power.

| File | Parent J SHA-256 | Derived K SHA-256 |
| --- | --- | --- |
| `IRs/directional-diffuse/Directional Diffuse Room Left Speaker.wav` | `8b7e9015b2675a9e3b21b5f42c5a3eba56a3ceffb84d9f6cb8cc859eea3728d1` | `fb414138f79df16065f6b152f14bf046eaba7f2e785355c9628c6d38f38034ab` |
| `IRs/directional-diffuse/Directional Diffuse Room Right Speaker.wav` | `ee42a346edee554f4de4388fdb4f25caec13b9d244a7b303098f5b6fa400f538` | `6bd9026e3f99f45caeb262818b6b2a7288975546c17471d7e9f96a27eefdc08a` |

Both outputs are stereo 48 kHz, 24-bit PCM with 32,768 frames. K has passed offline validation and informal listening; Windows runtime validation remains pending. Exact directional inputs, filters, and hashes are recorded in the [Candidate K analysis](../measurements/synthetic-reference-room/directional-diffuse/analysis/report.md).

## Treatment-Aware Timbre Candidate

`tools/measurement/render_timbre_balanced_room.py` verifies Candidate K and the independent auditory-band [timbre audit](../measurements/synthetic-reference-room/directional-diffuse/timbre-analysis/report.md). It applies one common attenuation-only microcluster filter per speaker, preserving both ear paths' directional ratio and all other branches.

| File | Parent K SHA-256 | Derived SHA-256 |
| --- | --- | --- |
| `IRs/timbre-balanced/Timbre Balanced Room Left Speaker.wav` | `fb414138f79df16065f6b152f14bf046eaba7f2e785355c9628c6d38f38034ab` | `c6e58e93b8f4c72c18cb9e1eb57120d71c34f8fdfea79d7ad2043fc89eec9fa0` |
| `IRs/timbre-balanced/Timbre Balanced Room Right Speaker.wav` | `6bd9026e3f99f45caeb262818b6b2a7288975546c17471d7e9f96a27eefdc08a` | `3b454023a56eb9d050a3a326cefbe40d6e2c4b1f8367bcb1c840d3a5c4074efd` |

Both outputs are stereo 48 kHz, 24-bit PCM with 32,768 frames. The minimum-phase filters begin at sample zero but add no bulk delay; direct sound and every non-microcluster branch remain inherited from K. Offline validation passes with +2.62 dB modeled maximum correlated gain. Windows runtime validation and K/L listening remain pending. Exact filters, response deltas, and plots are in the [timbre-balanced analysis](../measurements/synthetic-reference-room/timbre-balanced/analysis/report.md).
