#!/usr/bin/env python3
"""Render the locked causal D200 unified 2x2 prototype as 24-bit WAVs."""

import argparse
import hashlib
import json
import math
import wave
from pathlib import Path

import numpy as np

from analyze_baseline import finite_float
from explore_minimum_latency_renderer import (
    PATH_ORDER,
    REFERENCE,
    build_low_paths,
    evaluate_candidate,
    load_reference,
)


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_IR_OUTPUT = (
    REPOSITORY / "JBL M2 Binaural Convolution" / "IRs" / "minimum-latency"
)
DEFAULT_ANALYSIS_OUTPUT = (
    REPOSITORY / "measurements" / "minimum-latency" / "d200-prototype" / "analysis"
)
OUTPUT_FILES = {
    "left_speaker": "D200 Unified LL_LR.wav",
    "right_speaker": "D200 Unified RL_RR.wav",
}
LOCKED_DESIGN = {
    "lowpass_cutoff_hz": 80.0,
    "lowpass_order": 6,
    "low_gain_db": -0.75,
    "highpass_cutoff_hz": 5.0,
    "highpass_order": 2,
    "cross_delay_samples": 15,
    "additional_high_advance_samples": 100,
    "output_length_samples": 32768,
    "nfft": 65536,
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pcm24_bytes(samples):
    scaled = np.rint(samples * (1 << 23)).astype(np.int64)
    if np.any(scaled < -(1 << 23)) or np.any(scaled > (1 << 23) - 1):
        raise ValueError("Candidate IR exceeds the 24-bit PCM range")
    unsigned = np.where(scaled < 0, scaled + (1 << 24), scaled).astype(np.uint32)
    octets = np.empty((len(unsigned), 3), dtype=np.uint8)
    octets[:, 0] = unsigned & 0xFF
    octets[:, 1] = (unsigned >> 8) & 0xFF
    octets[:, 2] = (unsigned >> 16) & 0xFF
    return octets.tobytes()


def write_pcm24(path, samples, sample_rate):
    if samples.ndim != 2 or samples.shape[1] != 2:
        raise ValueError("A stereo samples x 2 array is required")
    raw = pcm24_bytes(samples.reshape(-1))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(3)
        target.setframerate(sample_rate)
        target.writeframes(raw)

    with wave.open(str(path), "rb") as check:
        if (
            check.getnchannels() != 2
            or check.getsampwidth() != 3
            or check.getframerate() != sample_rate
            or check.getnframes() != len(samples)
            or check.readframes(check.getnframes()) != raw
        ):
            raise RuntimeError(f"Written WAV failed verification: {path}")


def first_threshold(values, relative_db):
    peak = float(np.max(np.abs(values)))
    indices = np.flatnonzero(
        np.abs(values) >= peak * 10.0 ** (relative_db / 20.0)
    )
    return int(indices[0]) if len(indices) else None


def timing_metrics(values, sample_rate):
    peak = int(np.argmax(np.abs(values)))
    return {
        "onset_minus_60_db_sample": first_threshold(values, -60.0),
        "onset_minus_40_db_sample": first_threshold(values, -40.0),
        "peak_sample": peak,
        "peak_time_ms": finite_float(peak / sample_rate * 1000.0, 6),
    }


def quantization_error_db(original, quantized):
    error = quantized - original
    return finite_float(
        20.0
        * math.log10(
            max(
                float(np.linalg.norm(error))
                / max(float(np.linalg.norm(original)), 1e-30),
                1e-30,
            )
        ),
        6,
    )


def quantize_float24(values):
    scaled = np.rint(values * (1 << 23))
    return scaled / float(1 << 23)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--ir-output", type=Path, default=DEFAULT_IR_OUTPUT)
    parser.add_argument(
        "--analysis-output", type=Path, default=DEFAULT_ANALYSIS_OUTPUT
    )
    return parser.parse_args()


def main():
    args = parse_args()
    design = LOCKED_DESIGN
    reference, sample_rate, combined, high = load_reference(
        args.reference,
        design["nfft"],
        design["output_length_samples"],
        design["additional_high_advance_samples"],
    )
    frequencies = np.fft.rfftfreq(design["nfft"], 1.0 / sample_rate)
    low, low_tail, deep_levels = build_low_paths(
        reference,
        sample_rate,
        frequencies,
        design["nfft"],
        design["output_length_samples"],
        design["lowpass_cutoff_hz"],
        design["lowpass_order"],
        design["highpass_cutoff_hz"],
        design["highpass_order"],
        design["cross_delay_samples"],
        design["low_gain_db"],
    )
    candidate_spectra = {
        label: high[label] + low[label] for label in PATH_ORDER
    }
    candidate_impulses = {
        label: np.fft.irfft(candidate_spectra[label], design["nfft"])[
            : design["output_length_samples"]
        ]
        for label in PATH_ORDER
    }

    stereo_outputs = {
        "left_speaker": np.column_stack(
            [candidate_impulses["LL"], candidate_impulses["LR"]]
        ),
        "right_speaker": np.column_stack(
            [candidate_impulses["RL"], candidate_impulses["RR"]]
        ),
    }
    files = {}
    for key, samples in stereo_outputs.items():
        output_path = args.ir_output / OUTPUT_FILES[key]
        write_pcm24(output_path, samples, sample_rate)
        quantized = quantize_float24(samples)
        files[key] = {
            "path": str(output_path.relative_to(REPOSITORY)),
            "sha256": sha256(output_path),
            "sample_rate_hz": sample_rate,
            "sample_width_bits": 24,
            "channels": 2,
            "frames": len(samples),
            "peak_linear": finite_float(float(np.max(np.abs(quantized))), 9),
            "quantization_error_rms_db": quantization_error_db(
                samples, quantized
            ),
        }

    evaluation = evaluate_candidate(
        reference,
        sample_rate,
        frequencies,
        design["nfft"],
        design["output_length_samples"],
        combined,
        high,
        design["lowpass_cutoff_hz"],
        design["lowpass_order"],
        design["highpass_cutoff_hz"],
        design["highpass_order"],
        design["cross_delay_samples"],
        design["low_gain_db"],
    )
    summary = {
        "schema_version": 1,
        "status": "offline prototype; not the active renderer",
        "reference": {
            "path": str(args.reference.relative_to(REPOSITORY)),
            "sha256": sha256(args.reference),
            "precision_branches_used": True,
        },
        "design": design,
        "deep_target_level_db_before_calibration": {
            ear: finite_float(value, 6) for ear, value in deep_levels.items()
        },
        "low_tail_energy_beyond_output_db": {
            ear: finite_float(value, 6) for ear, value in low_tail.items()
        },
        "paths": {
            label: timing_metrics(candidate_impulses[label], sample_rate)
            for label in PATH_ORDER
        },
        "evaluation": evaluation,
        "files": files,
    }
    args.analysis_output.mkdir(parents=True, exist_ok=True)
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    report = [
        "# D200 Unified Renderer Prototype",
        "",
        "This first offline revision is retained as a rejected diagnostic. D200 A-matched is the active renderer, and A100 remains its frozen reference.",
        "",
        "## Locked Design",
        "",
        "- Advance the de-embedded A100 convolved paths by another 100 samples, for a common 200-sample BRIR advance from the original assets.",
        "- Preserve all four measured paths and their direct/cross peak spacing.",
        "- Generate flat per-ear deep bass from the smoothed A100 20–45 Hz level, calibrated −0.75 dB so the complete 20–80 Hz response retains A100 quantity.",
        "- Use a causal second-order 5 Hz protective high-pass and sixth-order 80 Hz Butterworth low-pass.",
        "- Preserve the legacy 15-sample cross-path bass offset; no runtime parallel bass branch remains.",
        "",
        "## Offline Results",
        "",
        f"- Mean smoothed 20–80 Hz deltas by path range from {min(item['bass_20_80_mean_magnitude_delta_db'] for item in evaluation['paths'].values()):.2f} to {max(item['bass_20_80_mean_magnitude_delta_db'] for item in evaluation['paths'].values()):.2f} dB versus A100.",
        f"- Synthetic bass is at least {-evaluation['aggregate']['worst_low_to_high_at_200_db']:.2f} dB below the advanced BRIR at 200 Hz.",
        f"- Low-frequency interaural phase differs from A100 by {evaluation['aggregate']['low_spatial_ipd_rms_degrees']:.2f}° RMS; 120–250 Hz differs from the advanced BRIR by {evaluation['aggregate']['upper_spatial_ipd_rms_degrees']:.2f}° RMS.",
        f"- Low-model energy beyond the 32,768-sample output is below {max(low_tail.values()):.2f} dB relative to total energy.",
        "",
        "| Path | −60 dB onset | −40 dB onset | Peak | Peak time |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label in PATH_ORDER:
        item = summary["paths"][label]
        report.append(
            f"| `{label}` | {item['onset_minus_60_db_sample']} | "
            f"{item['onset_minus_40_db_sample']} | {item['peak_sample']} | "
            f"{item['peak_time_ms']:.3f} ms |"
        )
    report.extend(
        [
            "",
            "The Windows runtime capture rejected this revision for its 80–200 Hz mismatch; retain it only as a reproducible diagnostic.",
        ]
    )
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
