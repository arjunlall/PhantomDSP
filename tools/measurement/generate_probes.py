#!/usr/bin/env python3
"""Generate deterministic stereo impulse probes for Equalizer APO Benchmark."""

import argparse
import hashlib
import json
import math
import wave
from pathlib import Path


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode_s24(value: int) -> bytes:
    return value.to_bytes(3, byteorder="little", signed=True)


def write_probe(path: Path, active_channel: int, frame_count: int, impulse_sample: int, sample_value: int, sample_rate: int) -> None:
    silence = encode_s24(0)
    impulse = encode_s24(sample_value)
    payload = bytearray()

    for frame in range(frame_count):
        left = impulse if frame == impulse_sample and active_channel == 0 else silence
        right = impulse if frame == impulse_sample and active_channel == 1 else silence
        payload.extend(left)
        payload.extend(right)

    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(3)
        output.setframerate(sample_rate)
        output.writeframes(payload)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    default_output = repo_root / "measurements" / "digital-baseline" / "raw"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=default_output)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--duration", type=float, default=2.0, help="Probe duration in seconds")
    parser.add_argument("--impulse-sample", type=int, default=1024)
    parser.add_argument("--amplitude-dbfs", type=float, default=0.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame_count = round(args.sample_rate * args.duration)
    if args.sample_rate <= 0 or frame_count <= 0:
        raise SystemExit("Sample rate and duration must be positive")
    if not 0 <= args.impulse_sample < frame_count:
        raise SystemExit("Impulse sample must fall within the generated file")
    if args.amplitude_dbfs > 0:
        raise SystemExit("Amplitude must not exceed 0 dBFS")

    full_scale_s24 = 1 << 23
    max_s24 = full_scale_s24 - 1
    nominal_amplitude = 10 ** (args.amplitude_dbfs / 20)
    sample_value = round(nominal_amplitude * max_s24)
    actual_amplitude = sample_value / full_scale_s24
    actual_dbfs = 20 * math.log10(actual_amplitude)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    probes = {
        "left": output_dir / "left-input.wav",
        "right": output_dir / "right-input.wav",
    }

    write_probe(probes["left"], 0, frame_count, args.impulse_sample, sample_value, args.sample_rate)
    write_probe(probes["right"], 1, frame_count, args.impulse_sample, sample_value, args.sample_rate)

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "sample_rate_hz": args.sample_rate,
        "channel_order": ["L", "R"],
        "sample_format": "signed 24-bit PCM little-endian",
        "frame_count": frame_count,
        "duration_seconds": frame_count / args.sample_rate,
        "impulse_sample": args.impulse_sample,
        "nominal_amplitude_dbfs": args.amplitude_dbfs,
        "actual_amplitude_dbfs": actual_dbfs,
        "integer_sample_value": sample_value,
        "normalized_sample_value": actual_amplitude,
        "files": {
            name: {"filename": path.name, "sha256": sha256(path)}
            for name, path in probes.items()
        },
    }
    metadata_path = output_dir / "probe-metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote probes to {output_dir}")
    print(f"Impulse: sample {args.impulse_sample}, {actual_dbfs:.6f} dBFS")
    for name, path in probes.items():
        print(f"{name}: {path.name}  sha256={metadata['files'][name]['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
