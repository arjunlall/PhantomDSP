#!/usr/bin/env python3
"""Measure prefix loss and transfer error from advancing the active BRIRs."""

import argparse
import hashlib
import json
import math
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise SystemExit(
        "NumPy is required. Install it with: "
        "python3 -m pip install -r tools/measurement/requirements.txt"
    )


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_IR_DIRECTORY = REPOSITORY / "JBL M2 Binaural Convolution" / "IRs"
FILES = {
    "left_speaker": ("JBL LSR305 LL 4_LR 4 5-500.wav", ("LL", "LR")),
    "right_speaker": ("JBL LSR305 RL 4_RR 4 5-500.wav", ("RL", "RR")),
}
BANDS = {
    "20-200_hz": (20.0, 200.0),
    "200-2000_hz": (200.0, 2000.0),
    "2000-20000_hz": (2000.0, 20000.0),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pcm24(path: Path):
    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE" or source.getsampwidth() != 3:
            raise ValueError(f"{path} must be 24-bit PCM")
        channels = source.getnchannels()
        sample_rate = source.getframerate()
        frames = source.getnframes()
        raw = source.readframes(frames)
    octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
    values = (
        octets[:, 0].astype(np.int32)
        | (octets[:, 1].astype(np.int32) << 8)
        | (octets[:, 2].astype(np.int32) << 16)
    )
    values = np.where(values & 0x800000, values - 0x1000000, values)
    return values.reshape(-1, channels).astype(np.float64) / float(1 << 23), sample_rate


def db20(value, floor=-300.0):
    return floor if value <= 0 else max(floor, 20.0 * math.log10(value))


def db10(value, floor=-300.0):
    return floor if value <= 0 else max(floor, 10.0 * math.log10(value))


def onset(values, relative_db):
    peak = np.max(np.abs(values))
    indices = np.flatnonzero(np.abs(values) >= peak * 10.0 ** (relative_db / 20.0))
    return int(indices[0]) if len(indices) else None


def advance(values, samples):
    result = np.zeros_like(values)
    result[:-samples] = values[samples:]
    return result


def error_summary(magnitude_delta, phase_error, valid):
    if not np.any(valid):
        return None
    return {
        "magnitude_rms_db": round(float(np.sqrt(np.mean(magnitude_delta[valid] ** 2))), 6),
        "magnitude_p99_abs_db": round(float(np.percentile(np.abs(magnitude_delta[valid]), 99)), 6),
        "phase_rms_degrees": round(float(np.sqrt(np.mean(phase_error[valid] ** 2))), 6),
        "phase_p99_abs_degrees": round(float(np.percentile(np.abs(phase_error[valid]), 99)), 6),
    }


def transfer_error(original, candidate, sample_rate, samples):
    nfft = 1 << (len(original) - 1).bit_length()
    frequency = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    original_fft = np.fft.rfft(original, nfft)
    candidate_fft = np.fft.rfft(candidate, nfft)
    level = 20.0 * np.log10(np.maximum(np.abs(original_fft), 1e-15))
    strong = level >= np.max(level[(frequency >= 20.0) & (frequency <= 20000.0)]) - 60.0
    magnitude_delta = 20.0 * np.log10(
        np.maximum(np.abs(candidate_fft), 1e-15)
        / np.maximum(np.abs(original_fft), 1e-15)
    )
    ideal_phase = np.exp(2j * np.pi * frequency * samples / sample_rate)
    residual = candidate_fft / np.where(
        np.abs(original_fft) > 1e-15, original_fft * ideal_phase, 1.0
    )
    phase_error = np.degrees(np.angle(residual))
    result = {}
    for name, (low, high) in BANDS.items():
        result[name] = error_summary(
            magnitude_delta, phase_error, strong & (frequency >= low) & (frequency <= high)
        )
    return result


def interchannel_phase_error(original, candidate, sample_rate):
    nfft = 1 << (len(original) - 1).bit_length()
    frequency = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    original_fft = np.fft.rfft(original, nfft, axis=0)
    candidate_fft = np.fft.rfft(candidate, nfft, axis=0)
    levels = 20.0 * np.log10(np.maximum(np.abs(original_fft), 1e-15))
    audible = (frequency >= 20.0) & (frequency <= 20000.0)
    strong = audible.copy()
    for channel in range(2):
        strong &= levels[:, channel] >= np.max(levels[audible, channel]) - 60.0
    original_ratio = original_fft[:, 0] / np.where(
        np.abs(original_fft[:, 1]) > 1e-15, original_fft[:, 1], 1.0
    )
    candidate_ratio = candidate_fft[:, 0] / np.where(
        np.abs(candidate_fft[:, 1]) > 1e-15, candidate_fft[:, 1], 1.0
    )
    error = np.degrees(np.angle(candidate_ratio / original_ratio))
    result = {}
    for name, (low, high) in BANDS.items():
        valid = strong & (frequency >= low) & (frequency <= high)
        result[name] = None if not np.any(valid) else {
            "rms_degrees": round(float(np.sqrt(np.mean(error[valid] ** 2))), 6),
            "p99_abs_degrees": round(float(np.percentile(np.abs(error[valid]), 99)), 6),
        }
    return result


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir-directory", type=Path, default=DEFAULT_IR_DIRECTORY)
    parser.add_argument("--shifts", type=int, nargs="+", default=(160, 192, 196, 200))
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser.parse_args()


def main():
    args = parse_args()
    output = {"advances": args.shifts, "files": {}}
    for file_key, (filename, labels) in FILES.items():
        path = args.ir_directory / filename
        samples, sample_rate = read_pcm24(path)
        file_result = {
            "filename": filename,
            "sha256": sha256(path),
            "sample_rate": sample_rate,
            "frames": len(samples),
            "channels": {},
            "interchannel_phase_error": {},
        }
        for channel, label in enumerate(labels):
            values = samples[:, channel]
            peak = float(np.max(np.abs(values)))
            total_energy = float(np.sum(values**2))
            channel_result = {
                "peak_sample": int(np.argmax(np.abs(values))),
                "onsets": {
                    str(threshold): onset(values, threshold)
                    for threshold in (-90, -80, -70, -60, -50, -40)
                },
                "advances": {},
            }
            for shift in args.shifts:
                prefix = values[:shift]
                rendered = advance(values, shift)
                channel_result["advances"][str(shift)] = {
                    "discarded_peak_relative_db": round(
                        db20(float(np.max(np.abs(prefix))) / peak), 3
                    ),
                    "discarded_energy_relative_db": round(
                        db10(float(np.sum(prefix**2)) / total_energy), 3
                    ),
                    "new_peak_sample": int(np.argmax(np.abs(rendered))),
                    "transfer_error": transfer_error(values, rendered, sample_rate, shift),
                }
            file_result["channels"][label] = channel_result
        for shift in args.shifts:
            file_result["interchannel_phase_error"][str(shift)] = (
                interchannel_phase_error(samples, advance(samples, shift), sample_rate)
            )
        output["files"][file_key] = file_result

    encoded = json.dumps(output, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
