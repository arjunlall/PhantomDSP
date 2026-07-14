#!/usr/bin/env python3
"""Render the accepted speaker-virtualization 2x2 IRs as 24-bit WAVs."""

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
    load_reference,
    rbj_peaking_response,
    smoothed_db,
    spatial_error_metrics,
)
REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_IR_OUTPUT = (
    REPOSITORY / "JBL M2 Binaural Convolution" / "IRs" / "active"
)
DEFAULT_ANALYSIS_OUTPUT = (
    REPOSITORY
    / "measurements"
    / "minimum-latency"
    / "accepted-renderer"
    / "analysis"
)
OUTPUT_FILES = {
    "left_speaker": "Left Speaker to Both Ears.wav",
    "right_speaker": "Right Speaker to Both Ears.wav",
}
LOCKED_DESIGN = {
    "lowpass_cutoff_hz": 90.0,
    "lowpass_order": 1,
    "low_gain_db": 0.75,
    "highpass_cutoff_hz": 5.0,
    "highpass_order": 2,
    "cross_delay_samples": 15,
    "common_output_eq": {
        "type": "peaking",
        "center_hz": 350.0,
        "gain_db": -5.0,
        "q": 2.0,
    },
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
        raise ValueError("Renderer IR exceeds the 24-bit PCM range")
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


def rms(values):
    return float(np.sqrt(np.mean(np.square(values))))


def band_metrics(frequencies, candidate, reference, low, high):
    mask = (frequencies >= low) & (frequencies <= high)
    delta = candidate[mask] - reference[mask]
    return {
        "mean_delta_db": finite_float(float(np.mean(delta)), 6),
        "rms_delta_db": finite_float(rms(delta), 6),
        "maximum_absolute_delta_db": finite_float(
            float(np.max(np.abs(delta))), 6
        ),
    }


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
    output_eq = design["common_output_eq"]
    common_correction = rbj_peaking_response(
        frequencies,
        sample_rate,
        output_eq["center_hz"],
        output_eq["gain_db"],
        output_eq["q"],
    )
    candidate_spectra = {
        label: (high[label] + low[label]) * common_correction
        for label in PATH_ORDER
    }
    candidate_full_impulses = {
        label: np.fft.irfft(candidate_spectra[label], design["nfft"])
        for label in PATH_ORDER
    }
    candidate_impulses = {
        label: candidate_full_impulses[label][
            : design["output_length_samples"]
        ]
        for label in PATH_ORDER
    }
    low_impulses = {
        label: np.fft.irfft(low[label], design["nfft"])[
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

    comparison = {}
    for label in PATH_ORDER:
        smooth_frequency, candidate_db = smoothed_db(
            frequencies, candidate_spectra[label], high=500.0
        )
        _, reference_db = smoothed_db(
            frequencies, combined[label], high=500.0
        )
        _, high_db = smoothed_db(
            frequencies, high[label], high=500.0
        )
        comparison[label] = {
            "bass_20_80_vs_legacy_reference": band_metrics(
                smooth_frequency, candidate_db, reference_db, 20.0, 80.0
            ),
            "midbass_80_160_vs_legacy_reference": band_metrics(
                smooth_frequency, candidate_db, reference_db, 80.0, 160.0
            ),
            "upper_bass_160_250_vs_legacy_reference": band_metrics(
                smooth_frequency, candidate_db, reference_db, 160.0, 250.0
            ),
            "return_250_500_vs_advanced_brir": band_metrics(
                smooth_frequency, candidate_db, high_db, 250.0, 500.0
            ),
        }

    spatial = {
        "20_80_vs_legacy_reference": spatial_error_metrics(
            frequencies, candidate_spectra, combined, 20.0, 80.0
        ),
        "80_160_vs_legacy_reference": spatial_error_metrics(
            frequencies, candidate_spectra, combined, 80.0, 160.0
        ),
        "160_250_vs_legacy_reference": spatial_error_metrics(
            frequencies, candidate_spectra, combined, 160.0, 250.0
        ),
        "250_500_vs_advanced_brir": spatial_error_metrics(
            frequencies, candidate_spectra, high, 250.0, 500.0
        ),
    }
    summary = {
        "schema_version": 1,
        "status": "accepted active renderer",
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
        "candidate_tail_energy_beyond_output_db": {
            label: finite_float(
                10.0
                * np.log10(
                    max(
                        float(
                            np.sum(
                                np.square(
                                    candidate_full_impulses[label][
                                        design["output_length_samples"] :
                                    ]
                                )
                            )
                        )
                        / max(
                            float(
                                np.sum(
                                    np.square(candidate_full_impulses[label])
                                )
                            ),
                            1e-30,
                        ),
                        1e-30,
                    )
                ),
                6,
            )
            for label in PATH_ORDER
        },
        "paths": {
            label: {
                **timing_metrics(candidate_impulses[label], sample_rate),
                "low_model_peak_sample": int(
                    np.argmax(np.abs(low_impulses[label]))
                ),
                "comparison": comparison[label],
            }
            for label in PATH_ORDER
        },
        "spatial_error": spatial,
        "files": files,
    }
    args.analysis_output.mkdir(parents=True, exist_ok=True)
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    report = [
        "# Accepted Speaker Virtualization Renderer",
        "",
        "This production renderer fixes the 80–200 Hz loss in the rejected steep-handoff experiment without reintroducing a runtime bass branch. The legacy parallel-bass renderer (historically A100) remains the frozen design reference and fallback.",
        "",
        "## Locked Design",
        "",
        "- Use a common 200-sample BRIR advance and one-convolution 2×2 topology.",
        "- Replace the sixth-order 80 Hz low-pass with a first-order 90 Hz low-pass and +0.75 dB calibration.",
        "- Retain the causal 5 Hz protective high-pass and 15-sample cross-path offset.",
        "- Let the clean model decay gently through upper bass so the complete response stays close to the preferred legacy reference through 200 Hz.",
        "- Apply one common −5 dB, 350 Hz, Q 2 correction after the 2×2 sum to remove the gentle model's shared lower-mid excess without changing interaural ratios.",
        "",
        "The first-order low model peaks at sample 1 on direct paths and sample 16 on cross paths. Relative to the advanced BRIR peaks, that closely recreates the legacy clean-before-convolved timing while avoiding the rejected design's approximately 8.5 ms low-pass peak delay.",
        "",
        "## Offline Response Match",
        "",
        "| Path | 20–80 Hz mean / RMS | 80–160 Hz mean / RMS | 160–250 Hz mean / RMS | Total peak |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label in PATH_ORDER:
        item = summary["paths"][label]
        bass = item["comparison"]["bass_20_80_vs_legacy_reference"]
        mid = item["comparison"]["midbass_80_160_vs_legacy_reference"]
        upper = item["comparison"]["upper_bass_160_250_vs_legacy_reference"]
        report.append(
            f"| `{label}` | {bass['mean_delta_db']:+.2f} / {bass['rms_delta_db']:.2f} dB | "
            f"{mid['mean_delta_db']:+.2f} / {mid['rms_delta_db']:.2f} dB | "
            f"{upper['mean_delta_db']:+.2f} / {upper['rms_delta_db']:.2f} dB | "
            f"{item['peak_sample']} ({item['peak_time_ms']:.3f} ms) |"
        )
    report.extend(
        [
            "",
            "Windows runtime validation is recorded in `runtime-report.md`. The digital gate passes, and controlled listening found no readily audible tonal or spatial regression from the legacy reference while confirming the latency improvement. This is the accepted production renderer.",
        ]
    )
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
