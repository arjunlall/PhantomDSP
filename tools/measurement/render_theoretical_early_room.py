#!/usr/bin/env python3
"""Render candidate F: personal direct sound plus theoretical early reflections and E's late field."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, sha256, write_svg_plot
from explore_minimum_latency_renderer import minimum_phase_spectrum
from render_active_renderer import write_pcm24
from render_synthetic_diffuse_room import (
    ANALYSIS_DIRECTORY as E_ANALYSIS_DIRECTORY,
    OUTPUT_DIRECTORY as E_OUTPUT_DIRECTORY,
    OUTPUT_FILES as E_OUTPUT_FILES,
)
from render_synthetic_direct import (
    PATH_ORDER,
    REPOSITORY,
    lagrange_fractional_delay,
    load_stereo_paths,
)
from render_synthetic_early_room import (
    ANALYSIS_DIRECTORY as C_ANALYSIS_DIRECTORY,
    DIRECT_ANALYSIS,
    DIRECT_FILES,
    OUTPUT_DIRECTORY as C_OUTPUT_DIRECTORY,
    OUTPUT_FILES as C_OUTPUT_FILES,
    band_metrics,
    early_window,
    smoothed_db,
)
from render_synthetic_late_room import apply_reflection_highpass, pad_to


C_FILES = {
    side: C_OUTPUT_DIRECTORY / filename for side, filename in C_OUTPUT_FILES.items()
}
E_FILES = {
    side: E_OUTPUT_DIRECTORY / filename for side, filename in E_OUTPUT_FILES.items()
}
OUTPUT_DIRECTORY = REPOSITORY / "Synthetic Reference Room" / "IRs" / "theoretical-early"
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "theoretical-early"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Theoretical Early Room Left Speaker.wav",
    "right": "Theoretical Early Room Right Speaker.wav",
}
DESIGN = {
    "sample_rate_hz": 48000,
    "output_length_samples": 32768,
    "nfft": 65536,
    "speed_of_sound_m_s": 343.0,
    "head_radius_m": 0.0875,
    "speaker_distance_m": 1.0,
    "speaker_azimuth_degrees": 30.0,
    "ear_height_m": 1.2,
    "room": {
        "width_m": 4.8,
        "length_m": 5.2,
        "height_m": 2.7,
        "listener_from_rear_wall_m": 2.0,
    },
    "common_hrtf": {
        "fractional_octave_smoothing": 6,
        "impulse_samples": 1024,
        "tail_fade_samples": 128,
    },
    "directional_shadow": {
        "maximum_high_frequency_attenuation_db": -12.0,
        "fully_shadowed_cutoff_hz": 1500.0,
        "unshadowed_cutoff_hz": 4000.0,
        "filter_samples": 256,
    },
    "fractional_delay_order": 7,
    "target_combined_early_to_direct_energy_db": -9.694942,
    "absolute_direct_propagation_delay_retained": False,
    "reflection_orders": 1,
}
SURFACES = {
    "left_wall": {
        "axis": 0,
        "coordinate_m": -DESIGN["room"]["width_m"] / 2.0,
        "reflection_coefficient": 0.30,
        "high_frequency_ratio": 0.45,
        "absorption_cutoff_hz": 2500.0,
    },
    "right_wall": {
        "axis": 0,
        "coordinate_m": DESIGN["room"]["width_m"] / 2.0,
        "reflection_coefficient": 0.30,
        "high_frequency_ratio": 0.45,
        "absorption_cutoff_hz": 2500.0,
    },
    "rear_wall": {
        "axis": 1,
        "coordinate_m": -DESIGN["room"]["listener_from_rear_wall_m"],
        "reflection_coefficient": 0.45,
        "high_frequency_ratio": 0.60,
        "absorption_cutoff_hz": 3500.0,
    },
    "front_wall": {
        "axis": 1,
        "coordinate_m": (
            DESIGN["room"]["length_m"]
            - DESIGN["room"]["listener_from_rear_wall_m"]
        ),
        "reflection_coefficient": 0.35,
        "high_frequency_ratio": 0.55,
        "absorption_cutoff_hz": 3000.0,
    },
    "floor": {
        "axis": 2,
        "coordinate_m": 0.0,
        "reflection_coefficient": 0.55,
        "high_frequency_ratio": 0.55,
        "absorption_cutoff_hz": 3500.0,
    },
    "ceiling": {
        "axis": 2,
        "coordinate_m": DESIGN["room"]["height_m"],
        "reflection_coefficient": 0.32,
        "high_frequency_ratio": 0.45,
        "absorption_cutoff_hz": 2500.0,
    },
}
PATH_SOURCE = {"LL": "left", "LR": "left", "RL": "right", "RR": "right"}
PATH_EAR = {"LL": "left", "LR": "right", "RL": "left", "RR": "right"}


def array_sha256(values):
    canonical = np.asarray(values, dtype="<f8")
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def distance(first, second):
    return float(np.linalg.norm(np.asarray(first) - np.asarray(second)))


def mirror_point(point, axis, coordinate):
    mirrored = np.asarray(point, dtype=np.float64).copy()
    mirrored[axis] = 2.0 * coordinate - mirrored[axis]
    return mirrored


def source_positions():
    angle = math.radians(DESIGN["speaker_azimuth_degrees"])
    radius = DESIGN["speaker_distance_m"]
    height = DESIGN["ear_height_m"]
    lateral = radius * math.sin(angle)
    forward = radius * math.cos(angle)
    return {
        "left": np.array([-lateral, forward, height]),
        "right": np.array([lateral, forward, height]),
    }


def ear_positions():
    height = DESIGN["ear_height_m"]
    radius = DESIGN["head_radius_m"]
    return {
        "left": np.array([-radius, 0.0, height]),
        "right": np.array([radius, 0.0, height]),
    }


def one_pole_high_shelf_impulse(sample_rate, cutoff_hz, high_frequency_gain, length):
    """Return a causal shelf with unity DC and the requested high-frequency gain."""
    alpha = math.exp(-2.0 * math.pi * cutoff_hz / sample_rate)
    lowpass = (1.0 - alpha) * np.power(alpha, np.arange(length))
    nyquist_lowpass = (1.0 - alpha) / (1.0 + alpha)
    normalized_lowpass = lowpass / (1.0 - nyquist_lowpass)
    normalized_lowpass[0] -= nyquist_lowpass / (1.0 - nyquist_lowpass)
    impulse = (1.0 - high_frequency_gain) * normalized_lowpass
    impulse[0] += high_frequency_gain
    return impulse


def direction_from_listener(image_source):
    listener = np.array([0.0, 0.0, DESIGN["ear_height_m"]])
    vector = np.asarray(image_source) - listener
    horizontal = math.hypot(vector[0], vector[1])
    return (
        math.degrees(math.atan2(vector[0], vector[1])),
        math.degrees(math.atan2(vector[2], horizontal)),
    )


def shadow_filter(sample_rate, azimuth_degrees, ear):
    lateral = math.sin(math.radians(azimuth_degrees))
    ear_side = -1.0 if ear == "left" else 1.0
    shadow = max(0.0, -ear_side * lateral)
    definition = DESIGN["directional_shadow"]
    maximum_gain = 10.0 ** (
        definition["maximum_high_frequency_attenuation_db"] / 20.0
    )
    high_gain = 1.0 - shadow * (1.0 - maximum_gain)
    cutoff = definition["unshadowed_cutoff_hz"] - shadow * (
        definition["unshadowed_cutoff_hz"]
        - definition["fully_shadowed_cutoff_hz"]
    )
    return (
        one_pole_high_shelf_impulse(
            sample_rate, cutoff, high_gain, definition["filter_samples"]
        ),
        shadow,
        cutoff,
        high_gain,
    )


def common_personal_hrtf(direct, sample_rate):
    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    spectra = {path: np.fft.rfft(values, nfft) for path, values in direct.items()}
    smoothed = [
        smoothed_db(
            spectrum,
            frequencies,
            fraction=DESIGN["common_hrtf"]["fractional_octave_smoothing"],
        )
        for spectrum in spectra.values()
    ]
    common_db = np.mean(smoothed, axis=0)
    impulse = np.fft.irfft(
        minimum_phase_spectrum(np.power(10.0, common_db / 20.0), nfft), nfft
    )[: DESIGN["common_hrtf"]["impulse_samples"]]
    fade = DESIGN["common_hrtf"]["tail_fade_samples"]
    impulse[-fade:] *= np.linspace(1.0, 0.0, fade, endpoint=True)
    return impulse


def add_impulse(destination, impulse):
    length = min(len(destination), len(impulse))
    destination[:length] += impulse[:length]


def render_early_paths(direct, direct_peaks, sample_rate):
    sources = source_positions()
    ears = ear_positions()
    common_hrtf = common_personal_hrtf(direct, sample_rate)
    output_length = DESIGN["output_length_samples"]
    early = {path: np.zeros(output_length) for path in PATH_ORDER}
    metadata = {path: [] for path in PATH_ORDER}

    for path in PATH_ORDER:
        source = sources[PATH_SOURCE[path]]
        ear = ears[PATH_EAR[path]]
        direct_distance = distance(source, ear)
        for surface_name, surface in SURFACES.items():
            image = mirror_point(
                source, surface["axis"], surface["coordinate_m"]
            )
            reflected_distance = distance(image, ear)
            extra_delay_samples = (
                (reflected_distance - direct_distance)
                / DESIGN["speed_of_sound_m_s"]
                * sample_rate
            )
            total_delay = direct_peaks[path] + extra_delay_samples
            azimuth, elevation = direction_from_listener(image)
            directional, shadow, shadow_cutoff, shadow_gain = shadow_filter(
                sample_rate, azimuth, PATH_EAR[path]
            )
            absorption = one_pole_high_shelf_impulse(
                sample_rate,
                surface["absorption_cutoff_hz"],
                surface["high_frequency_ratio"],
                DESIGN["directional_shadow"]["filter_samples"],
            )
            reflection_filter = np.convolve(common_hrtf, absorption)
            reflection_filter = np.convolve(reflection_filter, directional)
            delay_filter = lagrange_fractional_delay(
                total_delay, DESIGN["fractional_delay_order"]
            )
            amplitude = (
                surface["reflection_coefficient"]
                * direct_distance
                / reflected_distance
            )
            add_impulse(
                early[path], np.convolve(delay_filter, reflection_filter) * amplitude
            )
            metadata[path].append(
                {
                    "surface": surface_name,
                    "image_source_m": [finite_float(value, 6) for value in image],
                    "reflected_distance_m": finite_float(reflected_distance, 6),
                    "extra_delay_samples": finite_float(extra_delay_samples, 6),
                    "extra_delay_ms": finite_float(
                        extra_delay_samples / sample_rate * 1000.0, 6
                    ),
                    "arrival_azimuth_degrees": finite_float(azimuth, 6),
                    "arrival_elevation_degrees": finite_float(elevation, 6),
                    "distance_and_surface_gain": finite_float(amplitude, 9),
                    "head_shadow_fraction": finite_float(shadow, 6),
                    "head_shadow_cutoff_hz": finite_float(shadow_cutoff, 3),
                    "head_shadow_high_frequency_gain": finite_float(
                        shadow_gain, 6
                    ),
                }
            )

    windowed = {}
    for path in PATH_ORDER:
        filtered = apply_reflection_highpass(early[path], sample_rate)
        windowed[path] = filtered * early_window(
            output_length, direct_peaks[path], sample_rate
        )
    return windowed, metadata


def combined_energy_ratio_db(numerator, denominator):
    top = sum(float(np.sum(np.square(values))) for values in numerator.values())
    bottom = sum(float(np.sum(np.square(values))) for values in denominator.values())
    return 10.0 * math.log10(max(top / max(bottom, 1e-30), 1e-30))


def scale_early_to_target(early, direct):
    current = combined_energy_ratio_db(early, direct)
    target = DESIGN["target_combined_early_to_direct_energy_db"]
    scale = 10.0 ** ((target - current) / 20.0)
    return {path: values * scale for path, values in early.items()}, scale


def write_plots(output, direct_peaks, reflections, frequencies, reference, candidate):
    colors = {
        "LL": COLORS["LL"],
        "LR": "#7c3aed",
        "RL": "#dc2626",
        "RR": "#059669",
    }
    limit = round(35e-3 * DESIGN["sample_rate_hz"])
    samples = np.arange(limit)
    peak = max(float(np.max(np.abs(values[:limit]))) for values in reflections.values())
    write_svg_plot(
        output / "theoretical-early-impulse.svg",
        "Candidate F Theoretical Early Field",
        [
            (
                path,
                (samples - direct_peaks[path])
                / DESIGN["sample_rate_hz"]
                * 1000.0,
                reflections[path][:limit] / peak,
                colors[path],
            )
            for path in PATH_ORDER
        ],
        "Time after each path's direct peak (ms)",
        "Amplitude (normalized to largest early peak)",
        0.0,
        35.0,
        -1.1,
        1.1,
        [0, 4, 8, 12, 16, 20, 25, 30, 35],
    )
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    path = "LL"
    write_svg_plot(
        output / "ll-e-f-magnitude.svg",
        "LL Path: E Measured-Early versus F Theoretical-Early Renderer",
        [
            (
                "E accepted reference",
                frequencies[audible],
                smoothed_db(reference[path], frequencies)[audible],
                "#6b7280",
            ),
            (
                "F theoretical early",
                frequencies[audible],
                smoothed_db(candidate[path], frequencies)[audible],
                "#2563eb",
            ),
        ],
        "Frequency (Hz)",
        "1/6-octave magnitude (dB)",
        20.0,
        20000.0,
        -65.0,
        5.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir-output", type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument("--analysis-output", type=Path, default=ANALYSIS_DIRECTORY)
    return parser.parse_args()


def load_verified_inputs(files, analysis_directory):
    summary = json.loads(
        (analysis_directory / "summary.json").read_text(encoding="utf-8")
    )
    for side, path in files.items():
        expected = summary["rendered_files"][side]["sha256"]
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"Input hash mismatch for {path}: {actual} != {expected}")
    return summary


def main():
    args = parse_args()
    direct_summary = load_verified_inputs(DIRECT_FILES, DIRECT_ANALYSIS.parent)
    load_verified_inputs(C_FILES, C_ANALYSIS_DIRECTORY)
    load_verified_inputs(E_FILES, E_ANALYSIS_DIRECTORY)
    direct, sample_rate, direct_metadata = load_stereo_paths(DIRECT_FILES)
    measured_early, c_rate, c_metadata = load_stereo_paths(C_FILES)
    accepted_e, e_rate, e_metadata = load_stereo_paths(E_FILES)
    if sample_rate != DESIGN["sample_rate_hz"] or c_rate != sample_rate or e_rate != sample_rate:
        raise ValueError(f"Expected all inputs at {DESIGN['sample_rate_hz']} Hz")
    output_length = DESIGN["output_length_samples"]
    direct_padded = {path: pad_to(values, output_length) for path, values in direct.items()}
    c_padded = {
        path: pad_to(values, output_length) for path, values in measured_early.items()
    }
    accepted_late = {
        path: accepted_e[path] - c_padded[path] for path in PATH_ORDER
    }
    direct_peaks = {
        path: int(direct_summary["paths"][path]["peak_sample"])
        for path in PATH_ORDER
    }
    theoretical_early, reflection_metadata = render_early_paths(
        direct, direct_peaks, sample_rate
    )
    theoretical_early, early_scale = scale_early_to_target(
        theoretical_early, direct_padded
    )
    candidate = {
        path: direct_padded[path] + theoretical_early[path] + accepted_late[path]
        for path in PATH_ORDER
    }
    maximum = max(float(np.max(np.abs(values))) for values in candidate.values())
    if maximum >= 0.98:
        raise ValueError(f"Candidate IR peak {maximum:.4f} is too close to full scale")

    args.ir_output.mkdir(parents=True, exist_ok=True)
    stereo = {
        "left": np.column_stack([candidate["LL"], candidate["LR"]]),
        "right": np.column_stack([candidate["RL"], candidate["RR"]]),
    }
    rendered_files = {}
    for side, values in stereo.items():
        path = args.ir_output / OUTPUT_FILES[side]
        write_pcm24(path, values, sample_rate)
        rendered_files[side] = {
            "path": str(path.relative_to(REPOSITORY)),
            "sha256": sha256(path),
            "frames": len(values),
            "channels": 2,
            "sample_width_bits": 24,
            "peak_linear": finite_float(np.max(np.abs(values)), 9),
        }

    rendered, rendered_rate, _ = load_stereo_paths(
        {side: args.ir_output / filename for side, filename in OUTPUT_FILES.items()}
    )
    if rendered_rate != sample_rate:
        raise ValueError("Rendered F sample rate changed unexpectedly")

    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    reference_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in accepted_e.items()
    }
    candidate_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in rendered.items()
    }
    reference_mean = np.mean(
        [smoothed_db(values, frequencies) for values in reference_spectra.values()],
        axis=0,
    )
    candidate_mean = np.mean(
        [smoothed_db(values, frequencies) for values in candidate_spectra.values()],
        axis=0,
    )
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    correlated = (
        candidate_spectra["LL"] + candidate_spectra["RL"],
        candidate_spectra["LR"] + candidate_spectra["RR"],
    )
    maximum_correlated = max(
        float(np.max(np.abs(values[audible]))) for values in correlated
    )

    args.analysis_output.mkdir(parents=True, exist_ok=True)
    write_plots(
        args.analysis_output,
        direct_peaks,
        theoretical_early,
        frequencies,
        reference_spectra,
        candidate_spectra,
    )
    measured_c_early = {
        path: c_padded[path] - direct_padded[path] for path in PATH_ORDER
    }
    summary = {
        "schema_version": 1,
        "status": "opt-in theoretical early-reflection candidate F",
        "design": DESIGN,
        "surfaces": SURFACES,
        "source_positions_m": {
            key: [finite_float(value, 6) for value in values]
            for key, values in source_positions().items()
        },
        "ear_positions_m": {
            key: [finite_float(value, 6) for value in values]
            for key, values in ear_positions().items()
        },
        "direct_files": direct_metadata,
        "candidate_c_files_used_only_to_isolate_E_late_and_verify_one_energy_scalar": c_metadata,
        "accepted_e_files": e_metadata,
        "measured_early_waveform_samples_copied": False,
        "absolute_direct_propagation_delay_retained": False,
        "direct_peak_samples": direct_peaks,
        "combined_measured_c_early_to_direct_energy_db": finite_float(
            combined_energy_ratio_db(measured_c_early, direct_padded), 6
        ),
        "combined_theoretical_early_to_direct_energy_db": finite_float(
            combined_energy_ratio_db(theoretical_early, direct_padded), 6
        ),
        "theoretical_early_global_scale": finite_float(early_scale, 9),
        "branch_hashes": {
            "accepted_E_minus_C_synthetic_late": {
                path: array_sha256(values) for path, values in accepted_late.items()
            },
            "theoretical_early": {
                path: array_sha256(values) for path, values in theoretical_early.items()
            },
        },
        "reflections": reflection_metadata,
        "response_delta_F_minus_E": {
            "bass_20_80_hz": band_metrics(
                frequencies, candidate_mean, reference_mean, 20.0, 80.0
            ),
            "handoff_80_200_hz": band_metrics(
                frequencies, candidate_mean, reference_mean, 80.0, 200.0
            ),
            "upper_bass_200_300_hz": band_metrics(
                frequencies, candidate_mean, reference_mean, 200.0, 300.0
            ),
            "room_band_300_10000_hz": band_metrics(
                frequencies, candidate_mean, reference_mean, 300.0, 10000.0
            ),
        },
        "modeled_correlated_renderer_gain_db": finite_float(
            20.0 * math.log10(max(maximum_correlated, 1e-30)), 6
        ),
        "rendered_files": rendered_files,
        "plots": [
            "theoretical-early-impulse.svg",
            "ll-e-f-magnitude.svg",
        ],
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Candidate F Theoretical Early Reflections",
        "",
        "Candidate F removes C's measured 4-30 ms room waveform and replaces it with six first-order image-source reflections per speaker. B's personal direct sound and clean bass remain fixed, and E's accepted synthetic late addition is reused exactly.",
        "",
        "## Geometry",
        "",
        "- Symmetric 1 m nearfield speakers at ±30° and ear height.",
        "- Treated 4.8 × 5.2 × 2.7 m theoretical room with one reflection from each wall, floor, and ceiling.",
        "- Per-ear path lengths determine relative delay and distance attenuation; common speaker propagation time is removed.",
        "- A regularized personal common HRTF supplies broad ear magnitude, while a causal generic head-shadow shelf changes with arrival azimuth.",
        "",
        "## Experimental Control",
        "",
        f"The theoretical branch is globally scaled to {summary['combined_theoretical_early_to_direct_energy_db']:.3f} dB relative to the direct field, matching C's combined early energy but not its waveform, timing, asymmetry, or room modes.",
        "",
        "## Boundary",
        "",
        "This is the first fully synthetic room waveform, not a measurement-free renderer: the direct HRTF remains personal and E's late-field statistics remain calibrated from the preferred D control.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
