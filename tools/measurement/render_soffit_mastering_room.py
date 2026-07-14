#!/usr/bin/env python3
"""Render candidate G: a synthetic soffit-mounted mastering room."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, sha256, write_svg_plot
from analyze_synthetic_late_field import maximum_correlation
from render_active_renderer import write_pcm24
from render_synthetic_diffuse_room import normalize_energy, octave_filter
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
    smoothed_db,
)
from render_synthetic_diffuse_room import (
    ANALYSIS_DIRECTORY as E_ANALYSIS_DIRECTORY,
    OUTPUT_DIRECTORY as E_OUTPUT_DIRECTORY,
    OUTPUT_FILES as E_OUTPUT_FILES,
)
from render_synthetic_late_room import (
    DESIGN as LATE_DESIGN,
    apply_reflection_highpass,
    pad_to,
)
from render_theoretical_early_room import (
    add_impulse,
    array_sha256,
    combined_energy_ratio_db,
    common_personal_hrtf,
    distance,
    load_verified_inputs,
    mirror_point,
    one_pole_high_shelf_impulse,
)


C_FILES = {
    side: C_OUTPUT_DIRECTORY / filename for side, filename in C_OUTPUT_FILES.items()
}
E_FILES = {
    side: E_OUTPUT_DIRECTORY / filename for side, filename in E_OUTPUT_FILES.items()
}
OUTPUT_DIRECTORY = REPOSITORY / "Synthetic Reference Room" / "IRs" / "soffit-mastering"
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "soffit-mastering"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Soffit Mastering Room Left Speaker.wav",
    "right": "Soffit Mastering Room Right Speaker.wav",
}
PATH_SOURCE = {"LL": "left", "LR": "left", "RL": "right", "RR": "right"}
PATH_EAR = {"LL": "left", "LR": "right", "RL": "left", "RR": "right"}
BAND_CENTERS_HZ = (250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0)
DESIGN = {
    "sample_rate_hz": 48000,
    "output_length_samples": 32768,
    "nfft": 65536,
    "speed_of_sound_m_s": 343.0,
    "head_radius_m": 0.0875,
    "ear_height_m": 1.2,
    "speaker_azimuth_degrees": 30.0,
    "room": {
        "length_m": 6.6,
        "width_m": 4.6,
        "height_m": 2.8,
        "listener_from_front_wall_m": 2.5,
        "listener_lateral_offset_m": 0.03,
    },
    "soffit_mount": {
        "front_wall_reflection_retained": False,
        "rear_radiation_retained": False,
        "boundary_gain_added": False,
    },
    "fractional_delay_order": 7,
    "directional_shadow": {
        "maximum_high_frequency_attenuation_db": -12.0,
        "fully_shadowed_cutoff_hz": 1500.0,
        "unshadowed_cutoff_hz": 4000.0,
        "filter_samples": 256,
    },
    "source_directivity": {
        "maximum_high_frequency_attenuation_db": -12.0,
        "shelf_cutoff_hz": 2200.0,
        "angle_exponent": 1.6,
        "filter_samples": 256,
    },
    "specular_energy_fraction": 0.20,
    "microcluster_energy_fraction": 0.80,
    "microclusters": {
        "early_start_ms": 4.0,
        "early_end_ms": 15.0,
        "rear_start_ms": 22.0,
        "rear_end_ms": 25.0,
        "rear_amplitude_ratio": 0.55,
        "base_tap_count": 8,
        "tap_count_per_octave": 3,
        "coherence_mix_scale": 0.45,
        "random_seed": 20260715,
    },
    "early_fade_ms": [25.0, 30.0],
    "target_combined_early_to_direct_energy_db": -9.694942,
    "reflection_highpass": dict(LATE_DESIGN["reflection_highpass"]),
    "absolute_direct_propagation_delay_retained": False,
}
SURFACES = {
    "left_wall": {
        "axis": 0,
        "coordinate_m": -DESIGN["room"]["width_m"] / 2.0,
        "reflection_coefficient": 0.20,
        "high_frequency_ratio": 0.38,
        "absorption_cutoff_hz": 2200.0,
    },
    "right_wall": {
        "axis": 0,
        "coordinate_m": DESIGN["room"]["width_m"] / 2.0,
        "reflection_coefficient": 0.20,
        "high_frequency_ratio": 0.38,
        "absorption_cutoff_hz": 2200.0,
    },
    "floor": {
        "axis": 2,
        "coordinate_m": 0.0,
        "reflection_coefficient": 0.16,
        "high_frequency_ratio": 0.48,
        "absorption_cutoff_hz": 3000.0,
    },
    "ceiling": {
        "axis": 2,
        "coordinate_m": DESIGN["room"]["height_m"],
        "reflection_coefficient": 0.14,
        "high_frequency_ratio": 0.35,
        "absorption_cutoff_hz": 2200.0,
    },
}


def display_path(path):
    try:
        return str(path.relative_to(REPOSITORY))
    except ValueError:
        return str(path)


def listener_position():
    return np.array(
        [DESIGN["room"]["listener_lateral_offset_m"], 0.0, DESIGN["ear_height_m"]]
    )


def source_positions():
    listener = listener_position()
    forward = DESIGN["room"]["listener_from_front_wall_m"]
    lateral = forward * math.tan(math.radians(DESIGN["speaker_azimuth_degrees"]))
    return {
        "left": np.array([listener[0] - lateral, forward, DESIGN["ear_height_m"]]),
        "right": np.array([listener[0] + lateral, forward, DESIGN["ear_height_m"]]),
    }


def ear_positions():
    listener = listener_position()
    return {
        "left": listener + np.array([-DESIGN["head_radius_m"], 0.0, 0.0]),
        "right": listener + np.array([DESIGN["head_radius_m"], 0.0, 0.0]),
    }


def front_wall_coordinate():
    return DESIGN["room"]["listener_from_front_wall_m"]


def rear_wall_coordinate():
    return -(
        DESIGN["room"]["length_m"]
        - DESIGN["room"]["listener_from_front_wall_m"]
    )


def early_end_window(length, peak, sample_rate):
    start = peak + round(DESIGN["early_fade_ms"][0] * 1e-3 * sample_rate)
    end = peak + round(DESIGN["early_fade_ms"][1] * 1e-3 * sample_rate)
    window = np.ones(length)
    phase = np.linspace(0.0, math.pi, max(end - start, 1), endpoint=True)
    window[start:end] = 0.5 + 0.5 * np.cos(phase)
    window[end:] = 0.0
    return window


def reflection_point(source, ear, image_source, axis, coordinate):
    denominator = image_source[axis] - ear[axis]
    if abs(denominator) < 1e-12:
        raise ValueError("Image path does not intersect the reflection surface")
    amount = (coordinate - ear[axis]) / denominator
    point = ear + amount * (image_source - ear)
    point[axis] = coordinate
    return point


def vector_angle_degrees(first, second):
    first = np.asarray(first, dtype=np.float64)
    second = np.asarray(second, dtype=np.float64)
    cosine = float(
        np.dot(first, second)
        / max(float(np.linalg.norm(first) * np.linalg.norm(second)), 1e-30)
    )
    return math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))


def arrival_direction(image_source):
    vector = np.asarray(image_source) - listener_position()
    horizontal = math.hypot(vector[0], vector[1])
    return (
        math.degrees(math.atan2(vector[0], vector[1])),
        math.degrees(math.atan2(vector[2], horizontal)),
    )


def head_shadow_filter(sample_rate, azimuth_degrees, ear):
    lateral = math.sin(math.radians(azimuth_degrees))
    ear_side = -1.0 if ear == "left" else 1.0
    shadow = max(0.0, -ear_side * lateral)
    definition = DESIGN["directional_shadow"]
    minimum_gain = 10.0 ** (
        definition["maximum_high_frequency_attenuation_db"] / 20.0
    )
    high_gain = 1.0 - shadow * (1.0 - minimum_gain)
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


def source_directivity_filter(sample_rate, off_axis_degrees):
    definition = DESIGN["source_directivity"]
    fraction = math.sin(math.radians(min(abs(off_axis_degrees), 90.0)))
    attenuation_db = definition["maximum_high_frequency_attenuation_db"] * (
        fraction ** definition["angle_exponent"]
    )
    high_gain = 10.0 ** (attenuation_db / 20.0)
    return (
        one_pole_high_shelf_impulse(
            sample_rate,
            definition["shelf_cutoff_hz"],
            high_gain,
            definition["filter_samples"],
        ),
        attenuation_db,
        high_gain,
    )


def render_specular_paths(direct, direct_peaks, sample_rate):
    sources = source_positions()
    ears = ear_positions()
    listener = listener_position()
    common_hrtf = common_personal_hrtf(direct, sample_rate)
    output_length = DESIGN["output_length_samples"]
    components = {path: {} for path in PATH_ORDER}
    metadata = {path: [] for path in PATH_ORDER}

    for path in PATH_ORDER:
        source = sources[PATH_SOURCE[path]]
        ear = ears[PATH_EAR[path]]
        direct_distance = distance(source, ear)
        speaker_axis = listener - source
        for surface_name, surface in SURFACES.items():
            image = mirror_point(source, surface["axis"], surface["coordinate_m"])
            point = reflection_point(
                source,
                ear,
                image,
                surface["axis"],
                surface["coordinate_m"],
            )
            reflected_distance = distance(image, ear)
            extra_delay_samples = (
                (reflected_distance - direct_distance)
                / DESIGN["speed_of_sound_m_s"]
                * sample_rate
            )
            total_delay = direct_peaks[path] + extra_delay_samples
            off_axis = vector_angle_degrees(speaker_axis, point - source)
            directivity, directivity_db, directivity_gain = source_directivity_filter(
                sample_rate, off_axis
            )
            azimuth, elevation = arrival_direction(image)
            shadow_filter, shadow, shadow_cutoff, shadow_gain = head_shadow_filter(
                sample_rate, azimuth, PATH_EAR[path]
            )
            absorption = one_pole_high_shelf_impulse(
                sample_rate,
                surface["absorption_cutoff_hz"],
                surface["high_frequency_ratio"],
                DESIGN["directional_shadow"]["filter_samples"],
            )
            reflection_filter = np.convolve(common_hrtf, directivity)
            reflection_filter = np.convolve(reflection_filter, absorption)
            reflection_filter = np.convolve(reflection_filter, shadow_filter)
            delayed = lagrange_fractional_delay(
                total_delay, DESIGN["fractional_delay_order"]
            )
            amplitude = (
                surface["reflection_coefficient"]
                * direct_distance
                / reflected_distance
            )
            values = np.convolve(delayed, reflection_filter) * amplitude
            destination = np.zeros(output_length)
            add_impulse(destination, values)
            destination = apply_reflection_highpass(destination, sample_rate)
            destination *= early_end_window(
                output_length, direct_peaks[path], sample_rate
            )
            components[path][surface_name] = destination
            metadata[path].append(
                {
                    "surface": surface_name,
                    "reflection_point_m": [finite_float(value, 6) for value in point],
                    "extra_delay_ms": finite_float(
                        extra_delay_samples / sample_rate * 1000.0, 6
                    ),
                    "extra_delay_samples": finite_float(extra_delay_samples, 6),
                    "arrival_azimuth_degrees": finite_float(azimuth, 6),
                    "arrival_elevation_degrees": finite_float(elevation, 6),
                    "speaker_off_axis_degrees": finite_float(off_axis, 6),
                    "source_directivity_high_frequency_attenuation_db": finite_float(
                        directivity_db, 6
                    ),
                    "source_directivity_high_frequency_gain": finite_float(
                        directivity_gain, 6
                    ),
                    "distance_and_surface_gain": finite_float(amplitude, 9),
                    "head_shadow_fraction": finite_float(shadow, 6),
                    "head_shadow_cutoff_hz": finite_float(shadow_cutoff, 3),
                    "head_shadow_high_frequency_gain": finite_float(shadow_gain, 6),
                }
            )
    return {
        path: sum(components[path].values()) for path in PATH_ORDER
    }, components, metadata


def sparse_offsets(rng, start, end, count):
    population = np.arange(start, end, dtype=np.int64)
    selected = np.sort(rng.choice(population, min(count, len(population)), replace=False))
    position = (selected - start) / max(end - start, 1)
    amplitudes = rng.standard_normal(len(selected)) * np.exp(-1.2 * position)
    return selected, amplitudes


def impulse_train(length, peak, offsets, amplitudes):
    values = np.zeros(length)
    indices = peak + offsets
    valid = (indices >= 0) & (indices < length)
    values[indices[valid]] = amplitudes[valid]
    return values


def measured_early_targets(measured_early, sample_rate):
    start = round(4e-3 * sample_rate)
    end = round(30e-3 * sample_rate)
    center_left = measured_early["LL"] + measured_early["RL"]
    center_right = measured_early["LR"] + measured_early["RR"]
    targets = {"bands": {}}
    band_energy = {}
    for center in BAND_CENTERS_HZ:
        key = str(int(center))
        filtered = {
            path: octave_filter(values, center, sample_rate)
            for path, values in measured_early.items()
        }
        band_energy[key] = float(
            np.mean([np.sum(np.square(values)) for values in filtered.values()])
        )
        left = octave_filter(center_left, center, sample_rate)
        right = octave_filter(center_right, center, sample_rate)
        correlation, lag = maximum_correlation(
            left, right, start, end, round(1e-3 * sample_rate)
        )
        targets["bands"][key] = {
            "maximum_absolute_center_iacc": finite_float(abs(correlation), 6),
            "lag_samples": int(lag),
        }
    reference = band_energy["1000"]
    for key, energy in band_energy.items():
        targets["bands"][key]["energy_relative_to_1khz_db"] = finite_float(
            10.0 * math.log10(max(energy / max(reference, 1e-30), 1e-30)), 6
        )
    correlation, lag = maximum_correlation(
        center_left, center_right, start, end, round(1e-3 * sample_rate)
    )
    targets["broadband"] = {
        "maximum_absolute_center_iacc": finite_float(abs(correlation), 6),
        "lag_samples": int(lag),
    }
    return targets


def build_microcluster_components(targets, direct_peaks, sample_rate):
    length = DESIGN["output_length_samples"]
    definition = DESIGN["microclusters"]
    early_start = round(definition["early_start_ms"] * 1e-3 * sample_rate)
    early_end = round(definition["early_end_ms"] * 1e-3 * sample_rate)
    rear_start = round(definition["rear_start_ms"] * 1e-3 * sample_rate)
    rear_end = round(definition["rear_end_ms"] * 1e-3 * sample_rate)
    components = {path: {} for path in PATH_ORDER}

    for source_index, pair in enumerate((("LL", "LR"), ("RL", "RR"))):
        for band_index, center in enumerate(BAND_CENTERS_HZ):
            key = str(int(center))
            seed = definition["random_seed"] + source_index * 1000 + band_index * 10
            rng_common = np.random.default_rng(seed)
            rng_independent = np.random.default_rng(seed + 1)
            tap_count = definition["base_tap_count"] + band_index * definition[
                "tap_count_per_octave"
            ]
            common_early, common_early_amplitude = sparse_offsets(
                rng_common, early_start, early_end, tap_count
            )
            independent_early, independent_early_amplitude = sparse_offsets(
                rng_independent, early_start, early_end, tap_count
            )
            rear_count = max(4, tap_count // 2)
            common_rear, common_rear_amplitude = sparse_offsets(
                rng_common, rear_start, rear_end, rear_count
            )
            independent_rear, independent_rear_amplitude = sparse_offsets(
                rng_independent, rear_start, rear_end, rear_count
            )
            common_offsets = np.concatenate((common_early, common_rear))
            common_amplitudes = np.concatenate(
                (
                    common_early_amplitude,
                    common_rear_amplitude * definition["rear_amplitude_ratio"],
                )
            )
            independent_offsets = np.concatenate(
                (independent_early, independent_rear)
            )
            independent_amplitudes = np.concatenate(
                (
                    independent_early_amplitude,
                    independent_rear_amplitude * definition["rear_amplitude_ratio"],
                )
            )
            common_first = impulse_train(
                length, direct_peaks[pair[0]], common_offsets, common_amplitudes
            )
            common_second = impulse_train(
                length, direct_peaks[pair[1]], common_offsets, common_amplitudes
            )
            independent_second = impulse_train(
                length,
                direct_peaks[pair[1]],
                independent_offsets,
                independent_amplitudes,
            )
            target_coherence = targets["bands"][key][
                "maximum_absolute_center_iacc"
            ]
            mix = min(
                0.95,
                float(target_coherence) * definition["coherence_mix_scale"],
            )
            first = octave_filter(common_first, center, sample_rate)
            second = octave_filter(
                mix * common_second
                + math.sqrt(max(1.0 - mix**2, 0.0)) * independent_second,
                center,
                sample_rate,
            )
            components[pair[0]][key] = normalize_energy(first)
            components[pair[1]][key] = normalize_energy(second)
    return components


def compose_microclusters(components, targets, direct_peaks, sample_rate):
    sequences = {}
    for path in PATH_ORDER:
        values = np.zeros(DESIGN["output_length_samples"])
        for center in BAND_CENTERS_HZ:
            key = str(int(center))
            gain = 10.0 ** (
                targets["bands"][key]["energy_relative_to_1khz_db"] / 20.0
            )
            values += gain * components[path][key]
        values = apply_reflection_highpass(values, sample_rate)
        values *= early_end_window(len(values), direct_peaks[path], sample_rate)
        sequences[path] = values
    mean_energy = float(
        np.mean([np.sum(np.square(values)) for values in sequences.values()])
    )
    return {
        path: values
        * math.sqrt(mean_energy / max(float(np.sum(np.square(values))), 1e-30))
        for path, values in sequences.items()
    }


def scale_branch_to_energy(branch, target_energy):
    energy = sum(float(np.sum(np.square(values))) for values in branch.values())
    scale = math.sqrt(target_energy / max(energy, 1e-30))
    return {path: values * scale for path, values in branch.items()}, scale


def equalize_center_energy(specular, microclusters, sample_rate):
    start = round(4e-3 * sample_rate)
    end = round(30e-3 * sample_rate)
    left_fixed = specular["LL"] + specular["RL"]
    right_fixed = specular["LR"] + specular["RR"]
    left_adjustable = microclusters["LL"] + microclusters["RL"]
    right_adjustable = microclusters["LR"] + microclusters["RR"]
    left = left_fixed[start:end] + left_adjustable[start:end]
    fixed = right_fixed[start:end]
    adjustable = right_adjustable[start:end]
    target = float(np.sum(np.square(left)))
    a = float(np.sum(np.square(adjustable)))
    b = float(np.dot(fixed, adjustable))
    c = float(np.sum(np.square(fixed))) - target
    discriminant = max(b * b - a * c, 0.0)
    roots = [
        (-b + math.sqrt(discriminant)) / max(a, 1e-30),
        (-b - math.sqrt(discriminant)) / max(a, 1e-30),
    ]
    positive = [root for root in roots if root > 0.0]
    scale = min(positive, key=lambda value: abs(value - 1.0)) if positive else 1.0
    adjusted = dict(microclusters)
    adjusted["LR"] = adjusted["LR"] * scale
    adjusted["RR"] = adjusted["RR"] * scale
    return adjusted, scale


def center_metrics(paths, sample_rate, start_ms=4.0, end_ms=30.0):
    start = round(start_ms * 1e-3 * sample_rate)
    end = round(end_ms * 1e-3 * sample_rate)
    left = paths["LL"] + paths["RL"]
    right = paths["LR"] + paths["RR"]
    left_window = left[start:end]
    right_window = right[start:end]
    zero = float(
        np.dot(left_window, right_window)
        / max(float(np.linalg.norm(left_window) * np.linalg.norm(right_window)), 1e-30)
    )
    correlation, lag = maximum_correlation(
        left, right, start, end, round(1e-3 * sample_rate)
    )
    left_energy = float(np.sum(np.square(left_window)))
    right_energy = float(np.sum(np.square(right_window)))
    metrics = {
        "zero_lag_correlation": finite_float(zero, 6),
        "maximum_absolute_iacc": finite_float(abs(correlation), 6),
        "maximum_iacc_lag_samples": int(lag),
        "left_to_right_energy_db": finite_float(
            10.0 * math.log10(max(left_energy / max(right_energy, 1e-30), 1e-30)),
            6,
        ),
        "bands": {},
    }
    for center in BAND_CENTERS_HZ:
        filtered_left = octave_filter(left, center, sample_rate)
        filtered_right = octave_filter(right, center, sample_rate)
        value, band_lag = maximum_correlation(
            filtered_left,
            filtered_right,
            start,
            end,
            round(1e-3 * sample_rate),
        )
        metrics["bands"][str(int(center))] = {
            "maximum_absolute_iacc": finite_float(abs(value), 6),
            "lag_samples": int(band_lag),
        }
    return metrics


def center_energy_delta_db(candidate, reference, sample_rate):
    start = round(4e-3 * sample_rate)
    end = round(30e-3 * sample_rate)
    output = {}
    for ear, pair in {"left": ("LL", "RL"), "right": ("LR", "RR")}.items():
        candidate_sum = candidate[pair[0]] + candidate[pair[1]]
        reference_sum = reference[pair[0]] + reference[pair[1]]
        candidate_energy = float(np.sum(np.square(candidate_sum[start:end])))
        reference_energy = float(np.sum(np.square(reference_sum[start:end])))
        output[ear] = finite_float(
            10.0
            * math.log10(
                max(candidate_energy / max(reference_energy, 1e-30), 1e-30)
            ),
            6,
        )
    return output


def band_energy_ratio_db(values, reference, sample_rate, low=1000.0, high=8000.0):
    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    selected = (frequencies >= low) & (frequencies <= high)
    numerator = float(np.sum(np.square(np.abs(np.fft.rfft(values, nfft)[selected]))))
    denominator = float(
        np.sum(np.square(np.abs(np.fft.rfft(reference, nfft)[selected])))
    )
    return 10.0 * math.log10(max(numerator / max(denominator, 1e-30), 1e-30))


def write_plots(output, direct_peaks, early, target_metrics, achieved_metrics, frequencies, reference, candidate):
    colors = {"LL": COLORS["LL"], "LR": "#7c3aed", "RL": "#dc2626", "RR": "#059669"}
    limit = round(32e-3 * DESIGN["sample_rate_hz"])
    samples = np.arange(limit)
    peak = max(float(np.max(np.abs(values[:limit]))) for values in early.values())
    write_svg_plot(
        output / "soffit-mastering-early-impulse.svg",
        "Candidate G Synthetic Mastering-Room Early Field",
        [
            (
                path,
                (samples - direct_peaks[path]) / DESIGN["sample_rate_hz"] * 1000.0,
                early[path][:limit] / max(peak, 1e-30),
                colors[path],
            )
            for path in PATH_ORDER
        ],
        "Time after each path's direct peak (ms)",
        "Amplitude (normalized to largest early peak)",
        0.0,
        32.0,
        -1.1,
        1.1,
        [0, 4, 8, 12, 16, 20, 25, 30, 32],
    )
    centers = np.asarray(BAND_CENTERS_HZ)
    write_svg_plot(
        output / "center-coherence-target.svg",
        "Mono-Center Early Coherence: E Target versus G",
        [
            (
                "E measured-early target",
                centers,
                np.asarray([target_metrics["bands"][str(int(center))]["maximum_absolute_center_iacc"] for center in centers]),
                "#6b7280",
            ),
            (
                "G synthetic mastering room",
                centers,
                np.asarray([achieved_metrics["bands"][str(int(center))]["maximum_absolute_iacc"] for center in centers]),
                "#2563eb",
            ),
        ],
        "Octave-band center (Hz)",
        "Maximum absolute correlation",
        250.0,
        8000.0,
        0.0,
        1.0,
        list(centers),
        x_scale="log",
    )
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    write_svg_plot(
        output / "ll-e-g-magnitude.svg",
        "LL Path: E Reference versus G Synthetic Mastering Room",
        [
            ("E reference", frequencies[audible], smoothed_db(reference["LL"], frequencies)[audible], "#6b7280"),
            ("G mastering room", frequencies[audible], smoothed_db(candidate["LL"], frequencies)[audible], "#2563eb"),
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


def main():
    args = parse_args()
    direct_summary = load_verified_inputs(DIRECT_FILES, DIRECT_ANALYSIS.parent)
    load_verified_inputs(C_FILES, C_ANALYSIS_DIRECTORY)
    load_verified_inputs(E_FILES, E_ANALYSIS_DIRECTORY)
    direct, sample_rate, direct_metadata = load_stereo_paths(DIRECT_FILES)
    candidate_c, c_rate, c_metadata = load_stereo_paths(C_FILES)
    accepted_e, e_rate, e_metadata = load_stereo_paths(E_FILES)
    if sample_rate != DESIGN["sample_rate_hz"] or c_rate != sample_rate or e_rate != sample_rate:
        raise ValueError(f"Expected all inputs at {DESIGN['sample_rate_hz']} Hz")

    output_length = DESIGN["output_length_samples"]
    direct_padded = {path: pad_to(values, output_length) for path, values in direct.items()}
    c_padded = {path: pad_to(values, output_length) for path, values in candidate_c.items()}
    accepted_late = {path: accepted_e[path] - c_padded[path] for path in PATH_ORDER}
    measured_early = {path: c_padded[path] - direct_padded[path] for path in PATH_ORDER}
    direct_peaks = {path: int(direct_summary["paths"][path]["peak_sample"]) for path in PATH_ORDER}
    targets = measured_early_targets(measured_early, sample_rate)

    specular_raw, specular_components, reflection_metadata = render_specular_paths(
        direct, direct_peaks, sample_rate
    )
    micro_components = build_microcluster_components(targets, direct_peaks, sample_rate)
    micro_raw = compose_microclusters(
        micro_components, targets, direct_peaks, sample_rate
    )
    direct_energy = sum(float(np.sum(np.square(values))) for values in direct_padded.values())
    desired_early_energy = direct_energy * 10.0 ** (
        DESIGN["target_combined_early_to_direct_energy_db"] / 10.0
    )
    specular, specular_scale = scale_branch_to_energy(
        specular_raw, desired_early_energy * DESIGN["specular_energy_fraction"]
    )
    microclusters, micro_scale = scale_branch_to_energy(
        micro_raw, desired_early_energy * DESIGN["microcluster_energy_fraction"]
    )
    microclusters, right_micro_scale = equalize_center_energy(
        specular, microclusters, sample_rate
    )
    early = {path: specular[path] + microclusters[path] for path in PATH_ORDER}
    early, final_early_scale = scale_branch_to_energy(early, desired_early_energy)
    specular = {path: values * final_early_scale for path, values in specular.items()}
    microclusters = {path: values * final_early_scale for path, values in microclusters.items()}
    scaled_components = {
        path: {
            surface: values * specular_scale * final_early_scale
            for surface, values in specular_components[path].items()
        }
        for path in PATH_ORDER
    }
    candidate = {
        path: direct_padded[path] + early[path] + accepted_late[path]
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
            "path": display_path(path),
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
        raise ValueError("Rendered G sample rate changed unexpectedly")
    rendered_early = {
        path: rendered[path] - direct_padded[path] - accepted_late[path]
        for path in PATH_ORDER
    }
    target_center = center_metrics(measured_early, sample_rate)
    achieved_center = center_metrics(rendered_early, sample_rate)
    differences = np.abs(
        (rendered["LL"] + rendered["RL"])
        - (rendered["LR"] + rendered["RR"])
    )
    first_center_difference = np.flatnonzero(differences > 1e-6)

    reflection_levels = {}
    for path in PATH_ORDER:
        reflection_levels[path] = {}
        for surface, values in scaled_components[path].items():
            reflection_levels[path][surface] = finite_float(
                band_energy_ratio_db(values, direct_padded[path], sample_rate), 6
            )

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
    maximum_correlated = max(float(np.max(np.abs(values[audible]))) for values in correlated)

    args.analysis_output.mkdir(parents=True, exist_ok=True)
    write_plots(
        args.analysis_output,
        direct_peaks,
        rendered_early,
        targets,
        achieved_center,
        frequencies,
        reference_spectra,
        candidate_spectra,
    )
    sources = source_positions()
    ears = ear_positions()
    summary = {
        "schema_version": 1,
        "status": "opt-in synthetic soffit mastering-room candidate G",
        "design": DESIGN,
        "room_ratios_height_width_length": [
            1.0,
            finite_float(DESIGN["room"]["width_m"] / DESIGN["room"]["height_m"], 6),
            finite_float(DESIGN["room"]["length_m"] / DESIGN["room"]["height_m"], 6),
        ],
        "front_wall_coordinate_m": front_wall_coordinate(),
        "rear_wall_coordinate_m": rear_wall_coordinate(),
        "listener_position_m": [finite_float(value, 6) for value in listener_position()],
        "source_positions_m": {key: [finite_float(value, 6) for value in values] for key, values in sources.items()},
        "ear_positions_m": {key: [finite_float(value, 6) for value in values] for key, values in ears.items()},
        "speaker_distances_m": {key: finite_float(distance(values, listener_position()), 6) for key, values in sources.items()},
        "speaker_base_width_m": finite_float(distance(sources["left"], sources["right"]), 6),
        "direct_files": direct_metadata,
        "candidate_c_files_used_only_to_isolate_E_late_and_measure_broad_early_targets": c_metadata,
        "accepted_e_files": e_metadata,
        "measured_early_or_late_waveform_samples_copied": False,
        "absolute_direct_propagation_delay_retained": False,
        "direct_peak_samples": direct_peaks,
        "measured_early_targets": targets,
        "branch_scales": {
            "specular": finite_float(specular_scale, 9),
            "microclusters": finite_float(micro_scale, 9),
            "right_microcluster_energy_balance": finite_float(right_micro_scale, 9),
            "final_early": finite_float(final_early_scale, 9),
        },
        "combined_early_to_direct_energy_db": finite_float(
            combined_energy_ratio_db(rendered_early, direct_padded), 6
        ),
        "component_energy_fraction": {
            "specular": finite_float(
                sum(float(np.sum(np.square(values))) for values in specular.values())
                / max(sum(float(np.sum(np.square(values))) for values in rendered_early.values()), 1e-30),
                6,
            ),
            "microclusters": finite_float(
                sum(float(np.sum(np.square(values))) for values in microclusters.values())
                / max(sum(float(np.sum(np.square(values))) for values in rendered_early.values()), 1e-30),
                6,
            ),
        },
        "target_center_metrics": target_center,
        "achieved_center_metrics": achieved_center,
        "center_early_energy_delta_G_minus_E_db": center_energy_delta_db(
            rendered_early, measured_early, sample_rate
        ),
        "first_full_center_ear_difference_sample_above_1e_6": int(first_center_difference[0]) if len(first_center_difference) else None,
        "first_full_center_ear_difference_ms": finite_float(first_center_difference[0] / sample_rate * 1000.0, 6) if len(first_center_difference) else None,
        "specular_reflection_1_8khz_energy_db_relative_to_direct": reflection_levels,
        "reflections": reflection_metadata,
        "branch_hashes": {
            "accepted_E_minus_C_synthetic_late": {path: array_sha256(values) for path, values in accepted_late.items()},
            "specular": {path: array_sha256(values) for path, values in specular.items()},
            "microclusters": {path: array_sha256(values) for path, values in microclusters.items()},
            "complete_early": {path: array_sha256(values) for path, values in early.items()},
        },
        "response_delta_G_minus_E": {
            "bass_20_80_hz": band_metrics(frequencies, candidate_mean, reference_mean, 20.0, 80.0),
            "handoff_80_200_hz": band_metrics(frequencies, candidate_mean, reference_mean, 80.0, 200.0),
            "upper_bass_200_300_hz": band_metrics(frequencies, candidate_mean, reference_mean, 200.0, 300.0),
            "room_band_300_10000_hz": band_metrics(frequencies, candidate_mean, reference_mean, 300.0, 10000.0),
        },
        "modeled_correlated_renderer_gain_db": finite_float(20.0 * math.log10(max(maximum_correlated, 1e-30)), 6),
        "rendered_files": rendered_files,
        "plots": [
            "soffit-mastering-early-impulse.svg",
            "center-coherence-target.svg",
            "ll-e-g-magnitude.svg",
        ],
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Candidate G Synthetic Soffit Mastering Room",
        "",
        "Candidate G combines B's personalized direct/bass stage, a synthetic treated mastering-room early field, and E's unchanged synthetic late branch. It copies no measured room waveform samples.",
        "",
        "## Geometry and Treatment",
        "",
        f"- Room: {DESIGN['room']['length_m']:.1f} × {DESIGN['room']['width_m']:.1f} × {DESIGN['room']['height_m']:.1f} m.",
        f"- Soffit-mounted ±30° monitors: {summary['speaker_distances_m']['left']:.3f} m listening distance and {summary['speaker_base_width_m']:.3f} m base width.",
        "- The listener and speakers share a 3 cm lateral translation; direct geometry remains centered.",
        "- Front-wall and rear-radiation paths are absent. Controlled source directivity, absorption, and diffusion replace strong mirror reflections.",
        "",
        "## Early-Field Contract",
        "",
        f"- Early/direct energy: {summary['combined_early_to_direct_energy_db']:.3f} dB.",
        f"- Center energy mismatch: {summary['achieved_center_metrics']['left_to_right_energy_db']:+.3f} dB.",
        f"- Center early energy versus E: {summary['center_early_energy_delta_G_minus_E_db']['left']:+.3f} dB left and {summary['center_early_energy_delta_G_minus_E_db']['right']:+.3f} dB right.",
        f"- Maximum broadband center IACC: {summary['achieved_center_metrics']['maximum_absolute_iacc']:.3f} (E target {summary['target_center_metrics']['maximum_absolute_iacc']:.3f}).",
        f"- First full center-ear difference: {summary['first_full_center_ear_difference_ms']:.3f} ms.",
        "- Microclusters are deterministic, fourth-order high-passed at 250 Hz, and transition into E's accepted late branch at 25–30 ms.",
        "",
        "## Boundary",
        "",
        "The room waveform is synthetic, not measurement-free: the direct HRTF remains personal, the clean bass uses broad A calibration, and E/C supply only broad early and late statistical targets.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
