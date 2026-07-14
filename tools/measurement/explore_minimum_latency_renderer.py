#!/usr/bin/env python3
"""Explore causal low-frequency models for the unified D200 2x2 renderer."""

import argparse
import json
import math
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise SystemExit(
        "NumPy is required. Install it with: "
        "python3 -m pip install -r tools/measurement/requirements.txt"
    )

from analyze_baseline import PATHS, finite_float
from analyze_bass_branches import log_smooth


REPOSITORY = Path(__file__).resolve().parents[2]
REFERENCE = (
    REPOSITORY
    / "measurements"
    / "minimum-latency"
    / "legacy-reference"
    / "analysis"
    / "deembedded-reference.npz"
)
PATH_ORDER = ("LL", "LR", "RL", "RR")
EAR_PATHS = {
    "left": ("LL", "RL"),
    "right": ("LR", "RR"),
}
SPATIAL_PAIRS = {
    "left_speaker": ("LL", "LR"),
    "right_speaker": ("RR", "RL"),
}


def db20_array(values, floor=-180.0):
    return np.maximum(floor, 20.0 * np.log10(np.maximum(np.abs(values), 1e-12)))


def rms(values):
    return float(np.sqrt(np.mean(np.square(values))))


def advance_non_circular(values, samples):
    result = np.zeros_like(values)
    result[:-samples] = values[samples:]
    return result


def delay_non_circular(values, samples):
    if samples == 0:
        return values.copy()
    result = np.zeros_like(values)
    result[samples:] = values[:-samples]
    return result


def rbj_highpass_response(frequencies, sample_rate, cutoff, q):
    omega = 2.0 * np.pi * cutoff / sample_rate
    cosine = math.cos(omega)
    alpha = math.sin(omega) / (2.0 * q)
    b0 = (1.0 + cosine) / 2.0
    b1 = -(1.0 + cosine)
    b2 = b0
    a0 = 1.0 + alpha
    a1 = -2.0 * cosine
    a2 = 1.0 - alpha
    z_inverse = np.exp(-2j * np.pi * frequencies / sample_rate)
    numerator = b0 + b1 * z_inverse + b2 * np.square(z_inverse)
    denominator = a0 + a1 * z_inverse + a2 * np.square(z_inverse)
    return numerator / denominator


def rbj_peaking_response(frequencies, sample_rate, center, gain_db, q):
    """Return the RBJ peaking-EQ response used for broad common correction."""
    amplitude = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * np.pi * center / sample_rate
    cosine = math.cos(omega)
    alpha = math.sin(omega) / (2.0 * q)
    b0 = 1.0 + alpha * amplitude
    b1 = -2.0 * cosine
    b2 = 1.0 - alpha * amplitude
    a0 = 1.0 + alpha / amplitude
    a1 = -2.0 * cosine
    a2 = 1.0 - alpha / amplitude
    z_inverse = np.exp(-2j * np.pi * frequencies / sample_rate)
    numerator = b0 + b1 * z_inverse + b2 * np.square(z_inverse)
    denominator = a0 + a1 * z_inverse + a2 * np.square(z_inverse)
    return numerator / denominator


def butterworth_lowpass_response(frequencies, sample_rate, cutoff, order):
    """Digital Butterworth response made causal with the bilinear transform."""
    if order < 1:
        raise ValueError("Butterworth order must be positive")
    prewarped_cutoff = 2.0 * sample_rate * math.tan(
        math.pi * cutoff / sample_rate
    )
    analog_poles = np.array(
        [
            prewarped_cutoff
            * np.exp(1j * math.pi * (2 * index + 1 + order) / (2 * order))
            for index in range(order)
        ]
    )
    digital_poles = (2.0 * sample_rate + analog_poles) / (
        2.0 * sample_rate - analog_poles
    )
    digital_zeros = np.full(order, -1.0 + 0.0j)
    z = np.exp(2j * np.pi * frequencies / sample_rate)
    response = np.ones(len(frequencies), dtype=np.complex128)
    for zero, pole in zip(digital_zeros, digital_poles):
        response *= (z - zero) / (z - pole)
    dc_gain = np.prod((1.0 - digital_zeros) / (1.0 - digital_poles))
    return response / dc_gain


def minimum_phase_spectrum(magnitude, nfft):
    """Return the causal minimum-phase spectrum for a one-sided magnitude."""
    log_magnitude = np.log(np.maximum(magnitude, 1e-9))
    cepstrum = np.fft.irfft(log_magnitude, nfft)
    minimum_phase_cepstrum = np.zeros(nfft, dtype=np.float64)
    minimum_phase_cepstrum[0] = cepstrum[0]
    minimum_phase_cepstrum[1 : nfft // 2] = 2.0 * cepstrum[1 : nfft // 2]
    minimum_phase_cepstrum[nfft // 2] = cepstrum[nfft // 2]
    return np.exp(np.fft.rfft(minimum_phase_cepstrum, nfft))


def smoothed_db(frequencies, spectrum, low=10.0, high=300.0, fraction=6):
    band = (frequencies >= low) & (frequencies <= high)
    return (
        frequencies[band],
        np.asarray(
            log_smooth(
                frequencies[band],
                db20_array(spectrum[band]),
                fraction=fraction,
            ),
            dtype=np.float64,
        ),
    )


def build_ear_target_db(reference, ear, design_frequencies):
    source_frequencies = reference["frequency_hz"]
    source_band = (source_frequencies >= 5.0) & (source_frequencies <= 300.0)
    ear_db = np.mean(
        [
            db20_array(reference[f"combined_{label}"][source_band])
            for label in EAR_PATHS[ear]
        ],
        axis=0,
    )
    ear_db = np.asarray(
        log_smooth(
            source_frequencies[source_band], ear_db, fraction=6
        ),
        dtype=np.float64,
    )
    source = source_frequencies[source_band]
    deep = (source >= 20.0) & (source <= 45.0)
    deep_level = float(np.mean(ear_db[deep]))
    return np.full(len(design_frequencies), deep_level), deep_level


def load_reference(path, nfft, output_length, high_advance):
    reference = np.load(path)
    reference_nfft = (len(reference["frequency_hz"]) - 1) * 2
    sample_rate = int(reference["sample_rate_hz"])
    if sample_rate != 48000:
        raise ValueError(f"Expected a 48 kHz reference, got {sample_rate}")
    combined = {}
    high = {}
    for label in PATH_ORDER:
        combined_impulse = np.fft.irfft(
            reference[f"combined_{label}"], reference_nfft
        )[:output_length]
        convolved_impulse = np.fft.irfft(
            reference[f"convolved_{label}"], reference_nfft
        )[:output_length]
        combined[label] = np.fft.rfft(combined_impulse, nfft)
        high[label] = np.fft.rfft(
            advance_non_circular(convolved_impulse, high_advance), nfft
        )
    return reference, sample_rate, combined, high


def build_low_paths(
    reference,
    sample_rate,
    frequencies,
    nfft,
    output_length,
    lowpass_cutoff,
    lowpass_order,
    highpass_cutoff,
    highpass_order,
    cross_delay,
    gain_db,
):
    ear_impulses = {}
    tail_energy_db = {}
    deep_levels_db = {}
    for ear in EAR_PATHS:
        target_db, deep_level = build_ear_target_db(
            reference, ear, frequencies
        )
        base_magnitude = 10.0 ** ((target_db + gain_db) / 20.0)
        spectrum = minimum_phase_spectrum(base_magnitude, nfft)
        if highpass_order != 2:
            raise ValueError("The protective high-pass currently supports order 2")
        spectrum *= rbj_highpass_response(
            frequencies,
            sample_rate,
            highpass_cutoff,
            1.0 / math.sqrt(2.0),
        )
        spectrum *= butterworth_lowpass_response(
            frequencies, sample_rate, lowpass_cutoff, lowpass_order
        )
        impulse = np.fft.irfft(spectrum, nfft)
        total_energy = float(np.sum(np.square(impulse)))
        tail_energy = float(np.sum(np.square(impulse[output_length:])))
        tail_energy_db[ear] = 10.0 * math.log10(
            max(tail_energy / max(total_energy, 1e-30), 1e-30)
        )
        ear_impulses[ear] = impulse[:output_length]
        deep_levels_db[ear] = deep_level

    low_impulses = {
        "LL": ear_impulses["left"],
        "RL": delay_non_circular(ear_impulses["left"], cross_delay),
        "RR": ear_impulses["right"],
        "LR": delay_non_circular(ear_impulses["right"], cross_delay),
    }
    low_spectra = {
        label: np.fft.rfft(low_impulses[label], nfft) for label in PATH_ORDER
    }
    return low_spectra, tail_energy_db, deep_levels_db


def band_mask(frequencies, low, high):
    return (frequencies >= low) & (frequencies <= high)


def smoothstep(values, low, high):
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    return normalized * normalized * (3.0 - 2.0 * normalized)


def spatial_error_metrics(frequencies, candidate, target, low, high):
    valid = band_mask(frequencies, low, high)
    result = {}
    for name, (direct, cross) in SPATIAL_PAIRS.items():
        candidate_ratio = candidate[cross] / np.maximum(
            np.abs(candidate[direct]), 1e-12
        ) * np.exp(-1j * np.angle(candidate[direct]))
        target_ratio = target[cross] / np.maximum(
            np.abs(target[direct]), 1e-12
        ) * np.exp(-1j * np.angle(target[direct]))
        relative = candidate_ratio / np.where(
            np.abs(target_ratio) > 1e-12, target_ratio, 1.0
        )
        ild_error = db20_array(candidate_ratio) - db20_array(target_ratio)
        ipd_error = np.degrees(np.angle(relative))
        result[name] = {
            "ild_rms_error_db": finite_float(rms(ild_error[valid]), 5),
            "ipd_rms_error_degrees": finite_float(rms(ipd_error[valid]), 5),
        }
    return result


def evaluate_candidate(
    reference,
    sample_rate,
    frequencies,
    nfft,
    output_length,
    combined,
    high,
    cutoff,
    order,
    highpass_cutoff,
    highpass_order,
    cross_delay,
    gain_db,
):
    low, tail_energy_db, deep_levels_db = build_low_paths(
        reference,
        sample_rate,
        frequencies,
        nfft,
        output_length,
        cutoff,
        order,
        highpass_cutoff,
        highpass_order,
        cross_delay,
        gain_db,
    )
    candidate = {label: high[label] + low[label] for label in PATH_ORDER}
    smoothed_delta = {}
    path_metrics = {}
    for label in PATH_ORDER:
        smooth_frequency, candidate_db = smoothed_db(
            frequencies, candidate[label]
        )
        _, reference_db = smoothed_db(frequencies, combined[label])
        _, high_db = smoothed_db(frequencies, high[label])
        high_weight = smoothstep(smooth_frequency, 80.0, 160.0)
        desired_db = (
            (1.0 - high_weight) * reference_db + high_weight * high_db
        )
        delta = candidate_db - desired_db
        smoothed_delta[label] = (smooth_frequency, delta)
        bass = band_mask(smooth_frequency, 20.0, 80.0)
        transition = band_mask(smooth_frequency, 80.0, 180.0)
        high_band = band_mask(frequencies, 180.0, 250.0)
        high_error = db20_array(candidate[label]) - db20_array(high[label])
        path_metrics[label] = {
            "bass_20_80_rms_magnitude_delta_db": finite_float(
                rms(delta[bass]), 5
            ),
            "bass_20_80_mean_magnitude_delta_db": finite_float(
                float(np.mean(delta[bass])), 5
            ),
            "transition_80_180_rms_vs_blended_target_db": finite_float(
                rms(delta[transition]), 5
            ),
            "transition_80_180_max_abs_vs_blended_target_db": finite_float(
                float(np.max(np.abs(delta[transition]))), 5
            ),
            "candidate_vs_high_180_250_rms_db": finite_float(
                rms(high_error[high_band]), 5
            ),
            "low_to_high_db_at_150_hz": finite_float(
                float(
                    np.interp(
                        150.0,
                        frequencies,
                        db20_array(low[label]) - db20_array(high[label]),
                    )
                ),
                5,
            ),
            "low_to_high_db_at_200_hz": finite_float(
                float(
                    np.interp(
                        200.0,
                        frequencies,
                        db20_array(low[label]) - db20_array(high[label]),
                    )
                ),
                5,
            ),
        }

    low_spatial = spatial_error_metrics(
        frequencies, candidate, combined, 20.0, 80.0
    )
    upper_spatial = spatial_error_metrics(
        frequencies, candidate, high, 120.0, 250.0
    )
    aggregate = {
        "bass_rms_delta_db": finite_float(
            float(
                np.mean(
                    [
                        item["bass_20_80_rms_magnitude_delta_db"]
                        for item in path_metrics.values()
                    ]
                )
            ),
            5,
        ),
        "transition_rms_delta_db": finite_float(
            float(
                np.mean(
                    [
                        item["transition_80_180_rms_vs_blended_target_db"]
                        for item in path_metrics.values()
                    ]
                )
            ),
            5,
        ),
        "worst_low_to_high_at_200_db": finite_float(
            max(item["low_to_high_db_at_200_hz"] for item in path_metrics.values()),
            5,
        ),
        "low_spatial_ipd_rms_degrees": finite_float(
            float(
                np.mean(
                    [item["ipd_rms_error_degrees"] for item in low_spatial.values()]
                )
            ),
            5,
        ),
        "upper_spatial_ipd_rms_degrees": finite_float(
            float(
                np.mean(
                    [
                        item["ipd_rms_error_degrees"]
                        for item in upper_spatial.values()
                    ]
                )
            ),
            5,
        ),
    }
    aggregate["ranking_score"] = finite_float(
        4.0 * aggregate["bass_rms_delta_db"]
        + aggregate["transition_rms_delta_db"]
        + 0.03 * aggregate["low_spatial_ipd_rms_degrees"]
        + 0.02 * aggregate["upper_spatial_ipd_rms_degrees"]
        + max(0.0, aggregate["worst_low_to_high_at_200_db"] + 20.0),
        5,
    )
    return {
        "lowpass_cutoff_hz": cutoff,
        "lowpass_order": order,
        "low_gain_db": gain_db,
        "tail_energy_beyond_output_db": {
            ear: finite_float(value, 5) for ear, value in tail_energy_db.items()
        },
        "deep_target_level_db": {
            ear: finite_float(value, 5) for ear, value in deep_levels_db.items()
        },
        "aggregate": aggregate,
        "paths": path_metrics,
        "low_spatial_error_vs_legacy_reference": low_spatial,
        "upper_spatial_error_vs_advanced_brir": upper_spatial,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--cutoffs", type=float, nargs="+", default=(70, 75, 80, 85, 90, 95, 100)
    )
    parser.add_argument("--orders", type=int, nargs="+", default=(2, 3, 4, 5, 6))
    parser.add_argument(
        "--gains",
        type=float,
        nargs="+",
        default=(-1.0, -0.75, -0.5, -0.25, 0.0),
    )
    parser.add_argument("--highpass-cutoff", type=float, default=5.0)
    parser.add_argument("--highpass-order", type=int, default=2)
    parser.add_argument("--cross-delay", type=int, default=15)
    parser.add_argument("--high-advance", type=int, default=100)
    parser.add_argument("--output-length", type=int, default=32768)
    parser.add_argument("--nfft", type=int, default=65536)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.nfft < 2 * args.output_length or args.nfft & (args.nfft - 1):
        raise SystemExit("nfft must be a power of two at least twice output-length")
    reference, sample_rate, combined, high = load_reference(
        args.reference, args.nfft, args.output_length, args.high_advance
    )
    frequencies = np.fft.rfftfreq(args.nfft, 1.0 / sample_rate)
    candidates = []
    for cutoff in args.cutoffs:
        for order in args.orders:
            for gain in args.gains:
                candidates.append(
                    evaluate_candidate(
                        reference,
                        sample_rate,
                        frequencies,
                        args.nfft,
                        args.output_length,
                        combined,
                        high,
                        cutoff,
                        order,
                        args.highpass_cutoff,
                        args.highpass_order,
                        args.cross_delay,
                        gain,
                    )
                )
    candidates.sort(key=lambda item: item["aggregate"]["ranking_score"])
    result = {
        "schema_version": 1,
        "reference": str(args.reference.relative_to(REPOSITORY)),
        "sample_rate_hz": sample_rate,
        "output_length_samples": args.output_length,
        "high_branch_additional_advance_samples": args.high_advance,
        "low_model": {
            "source": "smoothed legacy-reference 20-45 Hz level averaged by output ear",
            "deep_extension": "constant per-ear target before causal crossover",
            "highpass_cutoff_hz": args.highpass_cutoff,
            "highpass_order": args.highpass_order,
            "cross_path_delay_samples": args.cross_delay,
            "phase": "minimum phase",
        },
        "magnitude_target": (
            "smoothed legacy-reference response through 80 Hz, smooth transition, "
            "200-sample-advanced BRIR from 160 Hz upward"
        ),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
