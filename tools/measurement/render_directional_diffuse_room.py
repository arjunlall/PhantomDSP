#!/usr/bin/env python3
"""Render candidate K: J with directional-HRTF-shaped microclusters."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, sha256, write_svg_plot
from analyze_directional_hrtf import smoothed_response
from explore_minimum_latency_renderer import minimum_phase_spectrum
from render_active_renderer import write_pcm24
from render_idealized_treated_room import (
    ANALYSIS_DIRECTORY as H_ANALYSIS_DIRECTORY,
    C_FILES,
    DESIGN as H_DESIGN,
    E_FILES,
    OUTPUT_DIRECTORY as H_OUTPUT_DIRECTORY,
    OUTPUT_FILES as H_OUTPUT_FILES,
)
from render_soffit_mastering_room import (
    DESIGN as G_DESIGN,
    build_microcluster_components,
    center_metrics,
    compose_microclusters,
    equalize_center_energy,
    measured_early_targets,
    render_specular_paths,
    scale_branch_to_energy,
)
from render_synthetic_direct import PATH_ORDER, REPOSITORY, load_stereo_paths
from render_synthetic_early_room import DIRECT_ANALYSIS, DIRECT_FILES, smoothed_db
from render_synthetic_late_room import pad_to
from render_theoretical_early_room import array_sha256, load_verified_inputs
from render_tonally_normalized_room import (
    PROFILES,
    smooth_db_values,
    speaker_energy_db,
    speaker_ratio_db,
)


H_FILES = {
    side: H_OUTPUT_DIRECTORY / filename
    for side, filename in H_OUTPUT_FILES.items()
}
J_PROFILE = PROFILES["J"]
J_FILES = {
    side: J_PROFILE["ir_output"] / filename
    for side, filename in J_PROFILE["output_files"].items()
}
DIRECTIONAL_MODEL = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "directional-hrtf"
    / "analysis"
    / "ari-las"
    / "directional-model.json"
)
OUTPUT_DIRECTORY = (
    REPOSITORY / "Synthetic Reference Room" / "IRs" / "directional-diffuse"
)
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "directional-diffuse"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Directional Diffuse Room Left Speaker.wav",
    "right": "Directional Diffuse Room Right Speaker.wav",
}
SPEAKER_PATHS = {"left": ("LL", "LR"), "right": ("RL", "RR")}
PATH_EAR = {"LL": "left", "LR": "right", "RL": "left", "RR": "right"}
DESIGN = {
    "sample_rate_hz": H_DESIGN["sample_rate_hz"],
    "output_length_samples": H_DESIGN["output_length_samples"],
    "nfft": H_DESIGN["nfft"],
    "base_candidate": "J midrange-normalized mastering room",
    "changed_branch": "G/H deterministic microclusters only",
    "unchanged_branches": [
        "personal direct and bass",
        "H treated specular reflections",
        "E synthetic late field",
        "I/J 200 Hz-1.8 kHz tonal normalization",
    ],
    "directional_model": "median of five public HRTFs best matching the personal ±30° direct contrast",
    "direction_energy_weights": {
        "left_wall": 0.40,
        "right_wall": 0.40,
        "floor": 0.10,
        "ceiling": 0.10,
    },
    "correction_support_hz": [3000.0, 14000.0],
    "correction_full_strength_hz": [4000.0, 12000.0],
    "maximum_absolute_requested_gain_db": 6.0,
    "filter_samples": 4096,
    "filter_fade_samples": 512,
    "filter_calibration_iterations": 2,
    "bulk_delay_samples": 0,
    "binaural_energy_contract": "preserve each speaker's smoothed microcluster power while redistributing it between ears",
}


def display_path(path):
    try:
        return str(path.relative_to(REPOSITORY))
    except ValueError:
        return str(path)


def db20(values):
    return 20.0 * np.log10(np.maximum(np.abs(values), 1e-30))


def correction_window(frequencies):
    low, high = DESIGN["correction_support_hz"]
    full_low, full_high = DESIGN["correction_full_strength_hz"]
    window = np.zeros_like(frequencies, dtype=np.float64)
    middle = (frequencies >= full_low) & (frequencies <= full_high)
    window[middle] = 1.0
    rise = (frequencies > low) & (frequencies < full_low)
    phase = (frequencies[rise] - low) / (full_low - low)
    window[rise] = 0.5 - 0.5 * np.cos(math.pi * phase)
    fall = (frequencies > full_high) & (frequencies < high)
    phase = (frequencies[fall] - full_high) / (high - full_high)
    window[fall] = 0.5 + 0.5 * np.cos(math.pi * phase)
    return window


def smooth_magnitude_db(values, sample_rate, frequencies):
    source_frequencies, curve = smoothed_response(values, sample_rate)
    return np.interp(frequencies, source_frequencies, curve)


def reconstruct_microclusters(
    direct,
    candidate_c,
    accepted_e,
    direct_summary,
    h_summary,
    sample_rate,
):
    output_length = DESIGN["output_length_samples"]
    direct_padded = {
        path: pad_to(values, output_length) for path, values in direct.items()
    }
    c_padded = {
        path: pad_to(values, output_length) for path, values in candidate_c.items()
    }
    measured_early = {
        path: c_padded[path] - direct_padded[path] for path in PATH_ORDER
    }
    direct_peaks = {
        path: int(direct_summary["paths"][path]["peak_sample"])
        for path in PATH_ORDER
    }
    targets = measured_early_targets(measured_early, sample_rate)
    specular_raw, _, _ = render_specular_paths(direct, direct_peaks, sample_rate)
    micro_components = build_microcluster_components(
        targets, direct_peaks, sample_rate
    )
    micro_raw = compose_microclusters(
        micro_components, targets, direct_peaks, sample_rate
    )
    direct_energy = sum(
        float(np.sum(np.square(values))) for values in direct_padded.values()
    )
    desired_early_energy = direct_energy * 10.0 ** (
        G_DESIGN["target_combined_early_to_direct_energy_db"] / 10.0
    )
    specular, specular_scale = scale_branch_to_energy(
        specular_raw,
        desired_early_energy * G_DESIGN["specular_energy_fraction"],
    )
    microclusters, micro_scale = scale_branch_to_energy(
        micro_raw,
        desired_early_energy * G_DESIGN["microcluster_energy_fraction"],
    )
    microclusters, right_scale = equalize_center_energy(
        specular, microclusters, sample_rate
    )
    early = {
        path: specular[path] + microclusters[path] for path in PATH_ORDER
    }
    _, final_scale = scale_branch_to_energy(early, desired_early_energy)
    microclusters = {
        path: values * final_scale for path, values in microclusters.items()
    }
    hashes = {path: array_sha256(values) for path, values in microclusters.items()}
    expected = h_summary["shared_branch_hashes"]["G_microclusters"]
    if hashes != expected:
        raise ValueError("Reconstructed microcluster branch no longer matches H")
    return microclusters, {
        "specular_scale": specular_scale,
        "microcluster_scale": micro_scale,
        "right_ear_balance_scale": right_scale,
        "final_early_scale": final_scale,
        "hashes": hashes,
    }


def requested_directional_corrections(
    model, direct, microclusters, sample_rate, frequencies
):
    model_frequencies = np.asarray(model["frequencies_hz"], dtype=np.float64)
    weights = DESIGN["direction_energy_weights"]
    direct_db = {
        path: smooth_magnitude_db(values, sample_rate, model_frequencies)
        for path, values in direct.items()
    }
    micro_db = {
        path: smooth_magnitude_db(values, sample_rate, model_frequencies)
        for path, values in microclusters.items()
    }
    requested = {}
    allocation = {}
    for speaker, paths in SPEAKER_PATHS.items():
        desired_directional_power = {}
        for path in paths:
            ear = PATH_EAR[path]
            directional = model["directional_delta_db"][speaker]
            diffuse_power_ratio = sum(
                weight
                * np.power(
                    10.0,
                    np.asarray(directional[surface][ear], dtype=np.float64)
                    / 10.0,
                )
                for surface, weight in weights.items()
            )
            desired_directional_power[path] = (
                np.power(10.0, direct_db[path] / 10.0) * diffuse_power_ratio
            )
        desired_total = sum(desired_directional_power.values())
        current_power = {
            path: np.power(10.0, micro_db[path] / 10.0) for path in paths
        }
        current_total = sum(current_power.values())
        for path in paths:
            desired_path_power = (
                current_total
                * desired_directional_power[path]
                / np.maximum(desired_total, 1e-30)
            )
            model_correction = 10.0 * np.log10(
                np.maximum(desired_path_power, 1e-30)
                / np.maximum(current_power[path], 1e-30)
            )
            interpolated = np.interp(
                frequencies,
                model_frequencies,
                model_correction,
                left=float(model_correction[0]),
                right=float(model_correction[-1]),
            )
            requested[path] = np.clip(
                interpolated * correction_window(frequencies),
                -DESIGN["maximum_absolute_requested_gain_db"],
                DESIGN["maximum_absolute_requested_gain_db"],
            )
            allocation[path] = {
                "model_correction_db": model_correction,
                "model_frequencies_hz": model_frequencies,
            }
    return requested, allocation


def build_minimum_phase_filter(requested_db):
    nfft = DESIGN["nfft"]
    support = correction_window(np.fft.rfftfreq(nfft, 1.0 / DESIGN["sample_rate_hz"]))
    design_db = np.asarray(requested_db, dtype=np.float64).copy()
    impulse = None
    spectrum = None
    for _ in range(DESIGN["filter_calibration_iterations"] + 1):
        spectrum = minimum_phase_spectrum(np.power(10.0, design_db / 20.0), nfft)
        impulse = np.fft.irfft(spectrum, nfft)[: DESIGN["filter_samples"]]
        fade = DESIGN["filter_fade_samples"]
        impulse[-fade:] *= np.linspace(1.0, 0.0, fade, endpoint=True)
        spectrum = np.fft.rfft(impulse, nfft)
        residual = (requested_db - db20(spectrum)) * support
        design_db = np.clip(
            design_db + residual,
            -DESIGN["maximum_absolute_requested_gain_db"] * 1.5,
            DESIGN["maximum_absolute_requested_gain_db"] * 1.5,
        )
    return impulse, spectrum


def band_delta(frequencies, candidate_db, reference_db, low, high):
    selected = (frequencies >= low) & (frequencies <= high)
    delta = candidate_db[selected] - reference_db[selected]
    return {
        "rms_delta_db": finite_float(np.sqrt(np.mean(np.square(delta))), 6),
        "maximum_absolute_delta_db": finite_float(np.max(np.abs(delta)), 6),
        "mean_delta_db": finite_float(np.mean(delta), 6),
    }


def write_plots(
    output,
    frequencies,
    requested,
    actual,
    j_spectra,
    k_spectra,
    direct_spectra,
    component_spectra,
):
    plots = []
    selected = (frequencies >= 3000.0) & (frequencies <= 14000.0)
    colors = {"LL": COLORS["LL"], "LR": "#7c3aed", "RL": "#dc2626", "RR": "#059669"}
    write_svg_plot(
        output / "directional-microcluster-filters.svg",
        "Candidate K Directional Microcluster Filters",
        [
            (
                f"{path} actual",
                frequencies[selected],
                db20(actual[path])[selected],
                colors[path],
            )
            for path in PATH_ORDER
        ],
        "Frequency (Hz)",
        "Filter gain (dB)",
        3000.0,
        14000.0,
        -7.0,
        7.0,
        [3000, 4000, 5000, 7000, 8000, 10000, 12000, 14000],
        x_scale="log",
    )
    plots.append("directional-microcluster-filters.svg")
    series = []
    for speaker, paths, before_color, after_color in (
        ("left", ("LL", "LR"), "#93c5fd", "#2563eb"),
        ("right", ("RL", "RR"), "#86efac", "#059669"),
    ):
        for label, spectra, color in (
            ("J", j_spectra, before_color),
            ("K", k_spectra, after_color),
        ):
            power = sum(np.square(np.abs(spectra[path])) for path in paths)
            response = smooth_db_values(
                frequencies, 10.0 * np.log10(np.maximum(power, 1e-30))
            )
            series.append(
                (
                    f"{label} {speaker}",
                    frequencies[selected],
                    response[selected],
                    color,
                )
            )
    y_values = np.concatenate([values for _, _, values, _ in series])
    low = math.floor(float(np.min(y_values)) / 5.0) * 5.0
    high = math.ceil(float(np.max(y_values)) / 5.0) * 5.0
    write_svg_plot(
        output / "j-k-binaural-speaker-response.svg",
        "Binaural Per-Speaker Response: J versus K",
        series,
        "Frequency (Hz)",
        "1/6-octave binaural energy (dB)",
        3000.0,
        14000.0,
        low,
        high,
        [3000, 4000, 5000, 7000, 8000, 10000, 12000, 14000],
        x_scale="log",
    )
    plots.append("j-k-binaural-speaker-response.svg")

    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    display_frequencies = np.geomspace(20.0, 20000.0, 1200)
    room_ratio = {
        name: {
            speaker: smooth_db_values(
                frequencies,
                speaker_ratio_db(spectra, direct_spectra, paths),
            )
            for speaker, paths in SPEAKER_PATHS.items()
        }
        for name, spectra in (("J", j_spectra), ("K", k_spectra))
    }
    write_svg_plot(
        output / "k-left-right-full-spectrum.svg",
        "Candidate K Full-Spectrum Per-Speaker Room Coloration",
        [
            (
                f"K {speaker} speaker",
                display_frequencies,
                np.interp(
                    display_frequencies,
                    frequencies[audible],
                    room_ratio["K"][speaker][audible],
                ),
                color,
            )
            for speaker, color in (("left", "#2563eb"), ("right", "#059669"))
        ],
        "Frequency (Hz)",
        "1/6-octave complete-to-direct ratio (dB)",
        20.0,
        20000.0,
        -2.0,
        12.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    plots.append("k-left-right-full-spectrum.svg")

    write_svg_plot(
        output / "j-k-room-coloration-full-spectrum.svg",
        "Full-Spectrum Per-Speaker Room Coloration: J versus K",
        [
            (
                f"{candidate} {speaker}",
                display_frequencies,
                np.interp(
                    display_frequencies,
                    frequencies[audible],
                    room_ratio[candidate][speaker][audible],
                ),
                color,
            )
            for candidate, speaker, color in (
                ("J", "left", "#93c5fd"),
                ("K", "left", "#2563eb"),
                ("J", "right", "#86efac"),
                ("K", "right", "#059669"),
            )
        ],
        "Frequency (Hz)",
        "1/6-octave complete-to-direct ratio (dB)",
        20.0,
        20000.0,
        -2.0,
        12.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    plots.append("j-k-room-coloration-full-spectrum.svg")

    write_svg_plot(
        output / "k-minus-j-fused-delta-full-spectrum.svg",
        "Candidate K Minus J: Fused Per-Speaker Response",
        [
            (
                f"{speaker} speaker",
                display_frequencies,
                np.interp(
                    display_frequencies,
                    frequencies[audible],
                    (room_ratio["K"][speaker] - room_ratio["J"][speaker])[audible],
                ),
                color,
            )
            for speaker, color in (("left", "#2563eb"), ("right", "#059669"))
        ],
        "Frequency (Hz)",
        "1/6-octave K minus J (dB)",
        20.0,
        20000.0,
        -0.5,
        0.5,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    plots.append("k-minus-j-fused-delta-full-spectrum.svg")

    component_colors = {
        "direct": "#6b7280",
        "early": "#2563eb",
        "late": "#d97706",
        "complete": "#059669",
    }
    for speaker, paths in SPEAKER_PATHS.items():
        curves = {
            name: smooth_db_values(
                frequencies, speaker_energy_db(spectra, paths)
            )
            for name, spectra in component_spectra.items()
        }
        reference = float(np.interp(1000.0, frequencies, curves["direct"]))
        for name in curves:
            curves[name] -= reference
        filename = f"k-{speaker}-components-full-spectrum.svg"
        write_svg_plot(
            output / filename,
            f"Candidate K {speaker.title()} Speaker Components",
            [
                (
                    label,
                    display_frequencies,
                    np.maximum(
                        np.interp(
                            display_frequencies,
                            frequencies[audible],
                            curves[name][audible],
                        ),
                        -40.0,
                    ),
                    component_colors[name],
                )
                for name, label in (
                    ("direct", "personal direct"),
                    ("early", "synthetic early"),
                    ("late", "synthetic late"),
                    ("complete", "complete K"),
                )
            ],
            "Frequency (Hz)",
            "Energy relative to K-filtered direct at 1 kHz (dB)",
            20.0,
            20000.0,
            -40.0,
            25.0,
            [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
            x_scale="log",
        )
        plots.append(filename)
    return plots


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir-output", type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument("--analysis-output", type=Path, default=ANALYSIS_DIRECTORY)
    return parser.parse_args()


def main():
    args = parse_args()
    direct_summary = load_verified_inputs(DIRECT_FILES, DIRECT_ANALYSIS.parent)
    h_summary = load_verified_inputs(H_FILES, H_ANALYSIS_DIRECTORY)
    j_summary = load_verified_inputs(J_FILES, J_PROFILE["analysis_output"])
    direct, sample_rate, direct_metadata = load_stereo_paths(DIRECT_FILES)
    candidate_c, c_rate, _ = load_stereo_paths(C_FILES)
    accepted_e, e_rate, _ = load_stereo_paths(E_FILES)
    accepted_h, h_rate, _ = load_stereo_paths(H_FILES)
    accepted_j, j_rate, j_metadata = load_stereo_paths(J_FILES)
    if len(
        {sample_rate, c_rate, e_rate, h_rate, j_rate, DESIGN["sample_rate_hz"]}
    ) != 1:
        raise ValueError(f"Expected all inputs at {DESIGN['sample_rate_hz']} Hz")
    model = json.loads(DIRECTIONAL_MODEL.read_text(encoding="utf-8"))
    if len(model.get("matched_subjects", [])) != 5:
        raise ValueError("Directional model must contain five matched subjects")

    microclusters, reconstruction = reconstruct_microclusters(
        direct,
        candidate_c,
        accepted_e,
        direct_summary,
        h_summary,
        sample_rate,
    )
    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    requested, allocation = requested_directional_corrections(
        model, direct, microclusters, sample_rate, frequencies
    )
    filters = {}
    modified_microclusters = {}
    for path in PATH_ORDER:
        impulse, spectrum = build_minimum_phase_filter(requested[path])
        full = np.convolve(microclusters[path], impulse)
        modified_microclusters[path] = full[: DESIGN["output_length_samples"]]
        filters[path] = {"impulse": impulse, "spectrum": spectrum}

    candidate = {
        path: accepted_j[path]
        + modified_microclusters[path]
        - microclusters[path]
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
        {side: args.ir_output / name for side, name in OUTPUT_FILES.items()}
    )
    if rendered_rate != sample_rate:
        raise ValueError("Rendered K sample rate changed unexpectedly")

    spectra = {
        "J": {path: np.fft.rfft(values, nfft) for path, values in accepted_j.items()},
        "K": {path: np.fft.rfft(values, nfft) for path, values in rendered.items()},
        "micro_J": {path: np.fft.rfft(values, nfft) for path, values in microclusters.items()},
        "micro_K": {path: np.fft.rfft(values, nfft) for path, values in modified_microclusters.items()},
    }
    output_length = DESIGN["output_length_samples"]
    direct_padded = {
        path: pad_to(values, output_length) for path, values in direct.items()
    }
    c_padded = {
        path: pad_to(values, output_length) for path, values in candidate_c.items()
    }
    e_padded = {
        path: pad_to(values, output_length) for path, values in accepted_e.items()
    }
    late = {path: e_padded[path] - c_padded[path] for path in PATH_ORDER}
    h_early = {
        path: accepted_h[path] - direct_padded[path] - late[path]
        for path in PATH_ORDER
    }
    direct_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in direct_padded.items()
    }
    h_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in accepted_h.items()
    }
    late_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in late.items()
    }
    h_early_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in h_early.items()
    }
    shared_j_filter = {}
    for speaker, paths in SPEAKER_PATHS.items():
        numerator = sum(
            np.conj(h_spectra[path]) * spectra["J"][path] for path in paths
        )
        denominator = sum(np.square(np.abs(h_spectra[path])) for path in paths)
        shared_j_filter[speaker] = numerator / np.maximum(denominator, 1e-30)
    component_spectra = {
        "direct": {},
        "early": {},
        "late": {},
        "complete": spectra["K"],
    }
    for speaker, paths in SPEAKER_PATHS.items():
        common = shared_j_filter[speaker]
        for path in paths:
            component_spectra["direct"][path] = direct_spectra[path] * common
            component_spectra["early"][path] = (
                h_early_spectra[path] * common
                + spectra["micro_K"][path]
                - spectra["micro_J"][path]
            )
            component_spectra["late"][path] = late_spectra[path] * common
    smoothed = {
        name: {
            path: smoothed_db(values, frequencies)
            for path, values in path_spectra.items()
        }
        for name, path_spectra in spectra.items()
    }
    speaker_energy = {}
    for speaker, paths in SPEAKER_PATHS.items():
        speaker_energy[speaker] = {}
        for name in ("J", "K", "micro_J", "micro_K"):
            power = sum(np.square(np.abs(spectra[name][path])) for path in paths)
            speaker_energy[speaker][name] = smooth_db_values(
                frequencies,
                10.0 * np.log10(np.maximum(power, 1e-30)),
            )

    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    correlated = (
        spectra["K"]["LL"] + spectra["K"]["RL"],
        spectra["K"]["LR"] + spectra["K"]["RR"],
    )
    maximum_correlated = max(
        float(np.max(np.abs(values[audible]))) for values in correlated
    )
    args.analysis_output.mkdir(parents=True, exist_ok=True)
    plots = write_plots(
        args.analysis_output,
        frequencies,
        requested,
        {path: filters[path]["spectrum"] for path in PATH_ORDER},
        spectra["J"],
        spectra["K"],
        direct_spectra,
        component_spectra,
    )
    sampled_filter_response = {
        path: {
            str(frequency): finite_float(
                np.interp(frequency, frequencies, db20(filters[path]["spectrum"])),
                6,
            )
            for frequency in (3000, 4000, 5000, 7000, 8000, 10000, 12000, 14000)
        }
        for path in PATH_ORDER
    }
    summary = {
        "schema_version": 1,
        "status": "opt-in candidate K directional diffuse mastering room",
        "design": DESIGN,
        "directional_model_path": display_path(DIRECTIONAL_MODEL),
        "directional_model": model,
        "direct_files": direct_metadata,
        "direct_peak_samples": {
            path: int(direct_summary["paths"][path]["peak_sample"])
            for path in PATH_ORDER
        },
        "candidate_j_files": j_metadata,
        "candidate_j_rendered_hashes": {
            side: j_summary["rendered_files"][side]["sha256"] for side in J_FILES
        },
        "reconstructed_microclusters": reconstruction,
        "modified_microcluster_hashes": {
            path: array_sha256(values)
            for path, values in modified_microclusters.items()
        },
        "filter_response_db": sampled_filter_response,
        "filter_impulse_first_nonzero_sample": {
            path: int(np.flatnonzero(np.abs(filters[path]["impulse"]) > 1e-15)[0])
            for path in PATH_ORDER
        },
        "microcluster_center_metrics_before": center_metrics(
            microclusters, sample_rate
        ),
        "microcluster_center_metrics_after": center_metrics(
            modified_microclusters, sample_rate
        ),
        "microcluster_binaural_energy_preservation": {
            speaker: band_delta(
                frequencies,
                speaker_energy[speaker]["micro_K"],
                speaker_energy[speaker]["micro_J"],
                4000.0,
                12000.0,
            )
            for speaker in SPEAKER_PATHS
        },
        "response_delta_K_minus_J": {
            "bass_20_80_hz": band_delta(
                frequencies,
                np.mean([smoothed["K"][path] for path in PATH_ORDER], axis=0),
                np.mean([smoothed["J"][path] for path in PATH_ORDER], axis=0),
                20.0,
                80.0,
            ),
            "protected_200_1800_hz": band_delta(
                frequencies,
                np.mean([smoothed["K"][path] for path in PATH_ORDER], axis=0),
                np.mean([smoothed["J"][path] for path in PATH_ORDER], axis=0),
                200.0,
                1800.0,
            ),
            "directional_4000_12000_hz": {
                speaker: band_delta(
                    frequencies,
                    speaker_energy[speaker]["K"],
                    speaker_energy[speaker]["J"],
                    4000.0,
                    12000.0,
                )
                for speaker in SPEAKER_PATHS
            },
        },
        "modeled_correlated_renderer_gain_db": finite_float(
            20.0 * math.log10(max(maximum_correlated, 1e-30)), 6
        ),
        "rendered_files": rendered_files,
        "plots": plots,
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Candidate K Directional Diffuse Mastering Room",
        "",
        "K keeps candidate J intact except for the dominant deterministic microcluster branch. It uses a five-subject public-HRTF ensemble to give that branch a plausible directional ear distribution while preserving each virtual speaker's fused microcluster power.",
        "",
        "## Scope",
        "",
        "- 80% of diffuse directional energy is lateral and horizontal; floor and ceiling each contribute 10%.",
        "- The directional correction fades in from 3-4 kHz, is fully active from 4-12 kHz, and fades out by 14 kHz.",
        "- Personal direct sound, bass, treated specular paths, accepted synthetic late field, and J's midrange normalization are unchanged.",
        "- Filters are causal minimum phase and add no bulk delay.",
        "",
        "## Offline Result",
        "",
        f"- Protected 200 Hz-1.8 kHz RMS change from J: {summary['response_delta_K_minus_J']['protected_200_1800_hz']['rms_delta_db']:.4f} dB.",
        f"- Left/right fused microcluster-power RMS changes from 4-12 kHz: {summary['microcluster_binaural_energy_preservation']['left']['rms_delta_db']:.3f}/{summary['microcluster_binaural_energy_preservation']['right']['rms_delta_db']:.3f} dB.",
        f"- Modeled maximum correlated gain: {summary['modeled_correlated_renderer_gain_db']:+.2f} dB.",
        "",
        "## Plots and Reproduction",
        "",
        "- `k-left-right-full-spectrum.svg` shows K's complete-to-direct coloration for both virtual speakers.",
        "- `j-k-room-coloration-full-spectrum.svg` overlays J and K; `k-minus-j-fused-delta-full-spectrum.svg` expands their small fused-response difference.",
        "- `k-left-components-full-spectrum.svg` and `k-right-components-full-spectrum.svg` separate the analytical direct, early, late, and complete spectra.",
        "- `directional-microcluster-filters.svg` shows the four ear-path filters that implement the HRTF-derived redistribution.",
        "- Exact public inputs, hashes, coordinate conventions, and rebuild commands are in [`docs/hrtf-reproduction.md`](../../../../docs/hrtf-reproduction.md).",
        "",
        "K is an opt-in listening candidate. J and all earlier candidates remain byte-identical; A remains the production default.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
