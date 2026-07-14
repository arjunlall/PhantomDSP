# Active IR Manifest

This manifest identifies the two BRIR files loaded by the active renderer. It provides a stable parent record for bass experiments and sample-advance variants without publishing additional raw measurement material.

## Files and Channel Mapping

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
| 160 samples | `JBL LSR305 LL 4_LR 4 5-500.wav` | `7ecca2ebe74e9fc038216cceb36cd8f2d1f9abf3c6d9c910d358858f3500447f` |
| 160 samples | `JBL LSR305 RL 4_RR 4 5-500.wav` | `db30a3c4b6e5f5ade18e4ce5f23684b0857f4b0eac797621943ebd55f61137f6` |
| 200 samples | `JBL LSR305 LL 4_LR 4 5-500.wav` | `9a901597f5e704479899ca0903eeed2e4f3ca55476204e11164171e6159d2480` |
| 200 samples | `JBL LSR305 RL 4_RR 4 5-500.wav` | `9045fd83647956e76122967050860fedb190b90ce57462ed9d3147b9a0bf8dd9` |

All four files are stereo 48 kHz, 24-bit PCM with 32,768 frames. They reside in `IRs/advanced/`. See the [BRIR advance analysis](../measurements/ir-advance/report.md) for prefix loss, transfer error, and the clean-bass integration blocker.
