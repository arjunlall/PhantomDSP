#!/usr/bin/env python3
"""Render candidate H: G with idealized lower-midrange specular treatment."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, sha256, write_svg_plot
from render_active_renderer import write_pcm24
from render_soffit_mastering_room import (
    ANALYSIS_DIRECTORY as G_ANALYSIS_DIRECTORY,
    C_ANALYSIS_DIRECTORY,
    C_FILES,
    DESIGN as G_DESIGN,
    E_ANALYSIS_DIRECTORY,
    E_FILES,
    OUTPUT_DIRECTORY as G_OUTPUT_DIRECTORY,
    OUTPUT_FILES as G_OUTPUT_FILES,
    SURFACES,
    band_energy_ratio_db,
    build_microcluster_components,
    center_energy_delta_db,
    center_metrics,
    compose_microclusters,
    early_end_window,
    equalize_center_energy,
    measured_early_targets,
    render_specular_paths,
    scale_branch_to_energy,
)
from render_synthetic_direct import PATH_ORDER, REPOSITORY, load_stereo_paths
from render_synthetic_early_room import (
    DIRECT_ANALYSIS,
    DIRECT_FILES,
    band_metrics,
    smoothed_db,
)
from render_synthetic_late_room import pad_to
from render_theoretical_early_room import (
    array_sha256,
    combined_energy_ratio_db,
    load_verified_inputs,
    one_pole_high_shelf_impulse,
)


G_FILES = {
    side: G_OUTPUT_DIRECTORY / filename
    for side, filename in G_OUTPUT_FILES.items()
}
OUTPUT_DIRECTORY = (
    REPOSITORY / "Synthetic Reference Room" / "IRs" / "idealized-treated"
)
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "idealized-treated"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Idealized Treated Room Left Speaker.wav",
    "right": "Idealized Treated Room Right Speaker.wav",
}
DESIGN = {
    "sample_rate_hz": G_DESIGN["sample_rate_hz"],
    "output_length_samples": G_DESIGN["output_length_samples"],
    "nfft": G_DESIGN["nfft"],
    "base_candidate": "G synthetic soffit mastering room",
    "geometry_changed": False,
    "personal_direct_changed": False,
    "microclusters_changed": False,
    "synthetic_late_field_changed": False,
    "surface_treatment": {
        "type": "causal one-pole low-frequency attenuation shelf",
        "transition_hz": 1000.0,
        "filter_samples": 1024,
        "applied_after_G_specular_energy_calibration": True,
        "low_frequency_attenuation_db": {
            "left_wall": -9.0,
            "right_wall": -9.0,
            "floor": -12.0,
            "ceiling": -9.0,
        },
    },
}


def display_path(path):
    try:
        return str(path.relative_to(REPOSITORY))
    except ValueError:
        return str(path)


def treatment_impulse(surface, sample_rate):
    definition = DESIGN["surface_treatment"]
    attenuation_db = definition["low_frequency_attenuation_db"][surface]
    low_gain = 10.0 ** (attenuation_db / 20.0)
    return (
        one_pole_high_shelf_impulse(
            sample_rate,
            definition["transition_hz"],
            1.0 / low_gain,
            definition["filter_samples"],
        )
        * low_gain
    )


def apply_surface_treatment(values, surface, peak, sample_rate):
    treated = np.convolve(values, treatment_impulse(surface, sample_rate))
    treated = treated[: DESIGN["output_length_samples"]]
    treated *= early_end_window(len(treated), peak, sample_rate)
    return treated


def direct_relative_response_metrics(candidate_spectra, direct_spectra, frequencies):
    notch_band = (frequencies >= 200.0) & (frequencies <= 350.0)
    lower_mid = (frequencies >= 200.0) & (frequencies <= 1000.0)
    output = {}
    for path in ("LL", "RR"):
        delta = smoothed_db(candidate_spectra[path], frequencies) - smoothed_db(
            direct_spectra[path], frequencies
        )
        selected = delta[notch_band]
        selected_frequencies = frequencies[notch_band]
        minimum = int(np.argmin(selected))
        output[path] = {
            "worst_200_350_hz_delta_db": finite_float(selected[minimum], 6),
            "worst_delta_frequency_hz": finite_float(
                selected_frequencies[minimum], 3
            ),
            "peak_to_peak_200_1000_hz_db": finite_float(
                np.ptp(delta[lower_mid]), 6
            ),
        }
    return output


def write_plots(
    output,
    direct_peaks,
    early,
    frequencies,
    direct_spectra,
    g_spectra,
    h_spectra,
):
    limit = round(32e-3 * DESIGN["sample_rate_hz"])
    samples = np.arange(limit)
    peak = max(float(np.max(np.abs(values[:limit]))) for values in early.values())
    colors = {
        "LL": COLORS["LL"],
        "LR": "#7c3aed",
        "RL": "#dc2626",
        "RR": "#059669",
    }
    write_svg_plot(
        output / "idealized-treated-early-impulse.svg",
        "Candidate H Idealized Treated Early Field",
        [
            (
                path,
                (samples - direct_peaks[path])
                / DESIGN["sample_rate_hz"]
                * 1000.0,
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
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    write_svg_plot(
        output / "ll-g-h-magnitude.svg",
        "LL Path: G versus H Idealized Treatment",
        [
            (
                "G soffit room",
                frequencies[audible],
                smoothed_db(g_spectra["LL"], frequencies)[audible],
                "#6b7280",
            ),
            (
                "H idealized treatment",
                frequencies[audible],
                smoothed_db(h_spectra["LL"], frequencies)[audible],
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
    upper_bass = (frequencies >= 100.0) & (frequencies <= 1500.0)
    series = []
    for path, color_g, color_h in (
        ("LL", "#6b7280", "#2563eb"),
        ("RR", "#a1a1aa", "#059669"),
    ):
        direct = smoothed_db(direct_spectra[path], frequencies)
        series.extend(
            [
                (
                    f"G {path}",
                    frequencies[upper_bass],
                    (smoothed_db(g_spectra[path], frequencies) - direct)[upper_bass],
                    color_g,
                ),
                (
                    f"H {path}",
                    frequencies[upper_bass],
                    (smoothed_db(h_spectra[path], frequencies) - direct)[upper_bass],
                    color_h,
                ),
            ]
        )
    write_svg_plot(
        output / "upper-bass-direct-delta.svg",
        "Direct-Relative Upper Bass: G versus H",
        series,
        "Frequency (Hz)",
        "1/6-octave room delta (dB)",
        100.0,
        1500.0,
        -10.0,
        8.0,
        [100, 200, 300, 500, 1000, 1500],
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
    g_summary = load_verified_inputs(G_FILES, G_ANALYSIS_DIRECTORY)
    direct, sample_rate, direct_metadata = load_stereo_paths(DIRECT_FILES)
    candidate_c, c_rate, c_metadata = load_stereo_paths(C_FILES)
    accepted_e, e_rate, e_metadata = load_stereo_paths(E_FILES)
    accepted_g, g_rate, g_metadata = load_stereo_paths(G_FILES)
    if len({sample_rate, c_rate, e_rate, g_rate, DESIGN["sample_rate_hz"]}) != 1:
        raise ValueError(f"Expected all inputs at {DESIGN['sample_rate_hz']} Hz")

    output_length = DESIGN["output_length_samples"]
    direct_padded = {
        path: pad_to(values, output_length) for path, values in direct.items()
    }
    c_padded = {
        path: pad_to(values, output_length) for path, values in candidate_c.items()
    }
    accepted_late = {
        path: accepted_e[path] - c_padded[path] for path in PATH_ORDER
    }
    measured_early = {
        path: c_padded[path] - direct_padded[path] for path in PATH_ORDER
    }
    direct_peaks = {
        path: int(direct_summary["paths"][path]["peak_sample"])
        for path in PATH_ORDER
    }
    targets = measured_early_targets(measured_early, sample_rate)

    specular_raw, specular_components, reflection_metadata = render_specular_paths(
        direct, direct_peaks, sample_rate
    )
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
    microclusters, right_micro_scale = equalize_center_energy(
        specular, microclusters, sample_rate
    )
    g_early = {
        path: specular[path] + microclusters[path] for path in PATH_ORDER
    }
    g_early, final_early_scale = scale_branch_to_energy(
        g_early, desired_early_energy
    )
    specular = {
        path: values * final_early_scale for path, values in specular.items()
    }
    microclusters = {
        path: values * final_early_scale for path, values in microclusters.items()
    }
    scaled_components = {
        path: {
            surface: values * specular_scale * final_early_scale
            for surface, values in specular_components[path].items()
        }
        for path in PATH_ORDER
    }
    shared_hashes = {
        "accepted_E_minus_C_synthetic_late": {
            path: array_sha256(values) for path, values in accepted_late.items()
        },
        "G_specular_before_H_treatment": {
            path: array_sha256(values) for path, values in specular.items()
        },
        "G_microclusters": {
            path: array_sha256(values) for path, values in microclusters.items()
        },
    }
    for key, g_key in (
        ("accepted_E_minus_C_synthetic_late", "accepted_E_minus_C_synthetic_late"),
        ("G_specular_before_H_treatment", "specular"),
        ("G_microclusters", "microclusters"),
    ):
        if shared_hashes[key] != g_summary["branch_hashes"][g_key]:
            raise ValueError(f"Reconstructed branch no longer matches G: {key}")

    treated_components = {
        path: {
            surface: apply_surface_treatment(
                values, surface, direct_peaks[path], sample_rate
            )
            for surface, values in surfaces.items()
        }
        for path, surfaces in scaled_components.items()
    }
    treated_specular = {
        path: sum(treated_components[path].values()) for path in PATH_ORDER
    }
    h_early = {
        path: treated_specular[path] + microclusters[path] for path in PATH_ORDER
    }
    candidate = {
        path: direct_padded[path] + h_early[path] + accepted_late[path]
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
        raise ValueError("Rendered H sample rate changed unexpectedly")
    rendered_early = {
        path: rendered[path] - direct_padded[path] - accepted_late[path]
        for path in PATH_ORDER
    }
    rendered_g_early = {
        path: accepted_g[path] - direct_padded[path] - accepted_late[path]
        for path in PATH_ORDER
    }

    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    direct_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in direct_padded.items()
    }
    e_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in accepted_e.items()
    }
    g_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in accepted_g.items()
    }
    h_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in rendered.items()
    }
    means = {
        name: np.mean(
            [smoothed_db(spectra[path], frequencies) for path in PATH_ORDER],
            axis=0,
        )
        for name, spectra in (("E", e_spectra), ("G", g_spectra), ("H", h_spectra))
    }
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    correlated = (
        h_spectra["LL"] + h_spectra["RL"],
        h_spectra["LR"] + h_spectra["RR"],
    )
    maximum_correlated = max(
        float(np.max(np.abs(values[audible]))) for values in correlated
    )
    surface_filter_response = {}
    for surface in SURFACES:
        impulse = treatment_impulse(surface, sample_rate)
        spectrum = np.fft.rfft(impulse, nfft)
        response = {}
        for frequency in (20.0, 250.0, 500.0, 1000.0, 2000.0, 8000.0):
            index = int(np.argmin(np.abs(frequencies - frequency)))
            response[str(int(frequency))] = finite_float(
                20.0 * math.log10(max(abs(spectrum[index]), 1e-30)), 6
            )
        surface_filter_response[surface] = response

    args.analysis_output.mkdir(parents=True, exist_ok=True)
    write_plots(
        args.analysis_output,
        direct_peaks,
        rendered_early,
        frequencies,
        direct_spectra,
        g_spectra,
        h_spectra,
    )
    achieved_center = center_metrics(rendered_early, sample_rate)
    differences = np.abs(
        (rendered["LL"] + rendered["RL"])
        - (rendered["LR"] + rendered["RR"])
    )
    first_center_difference = np.flatnonzero(differences > 1e-6)
    summary = {
        "schema_version": 1,
        "status": "opt-in candidate H idealized treated mastering room",
        "design": DESIGN,
        "inherited_G_geometry": g_summary["design"]["room"],
        "direct_peak_samples": direct_peaks,
        "direct_files": direct_metadata,
        "candidate_c_files_used_only_to_reconstruct_E_late_and_G_targets": c_metadata,
        "accepted_e_files": e_metadata,
        "candidate_g_files": g_metadata,
        "measured_early_or_late_waveform_samples_copied": False,
        "branch_scales_inherited_from_G": {
            "specular": finite_float(specular_scale, 9),
            "microclusters": finite_float(micro_scale, 9),
            "right_microcluster_energy_balance": finite_float(
                right_micro_scale, 9
            ),
            "final_early": finite_float(final_early_scale, 9),
        },
        "surface_filter_response_db": surface_filter_response,
        "combined_early_to_direct_energy_db": finite_float(
            combined_energy_ratio_db(rendered_early, direct_padded), 6
        ),
        "early_energy_delta_H_minus_G_db": finite_float(
            combined_energy_ratio_db(rendered_early, rendered_g_early), 6
        ),
        "achieved_center_metrics": achieved_center,
        "center_early_energy_delta_H_minus_G_db": center_energy_delta_db(
            rendered_early, rendered_g_early, sample_rate
        ),
        "first_full_center_ear_difference_sample_above_1e_6": int(
            first_center_difference[0]
        )
        if len(first_center_difference)
        else None,
        "first_full_center_ear_difference_ms": finite_float(
            first_center_difference[0] / sample_rate * 1000.0, 6
        )
        if len(first_center_difference)
        else None,
        "direct_relative_response": direct_relative_response_metrics(
            h_spectra, direct_spectra, frequencies
        ),
        "direct_relative_response_G_reference": direct_relative_response_metrics(
            g_spectra, direct_spectra, frequencies
        ),
        "response_delta_H_minus_G": {
            "bass_20_80_hz": band_metrics(
                frequencies, means["H"], means["G"], 20.0, 80.0
            ),
            "handoff_80_200_hz": band_metrics(
                frequencies, means["H"], means["G"], 80.0, 200.0
            ),
            "upper_bass_200_300_hz": band_metrics(
                frequencies, means["H"], means["G"], 200.0, 300.0
            ),
            "lower_mid_300_1000_hz": band_metrics(
                frequencies, means["H"], means["G"], 300.0, 1000.0
            ),
            "spatial_1000_8000_hz": band_metrics(
                frequencies, means["H"], means["G"], 1000.0, 8000.0
            ),
        },
        "response_delta_H_minus_E": {
            "bass_20_80_hz": band_metrics(
                frequencies, means["H"], means["E"], 20.0, 80.0
            ),
            "upper_bass_200_300_hz": band_metrics(
                frequencies, means["H"], means["E"], 200.0, 300.0
            ),
            "room_band_300_10000_hz": band_metrics(
                frequencies, means["H"], means["E"], 300.0, 10000.0
            ),
        },
        "shared_branch_hashes": shared_hashes,
        "treated_branch_hashes": {
            "surface_filters": {
                surface: array_sha256(treatment_impulse(surface, sample_rate))
                for surface in SURFACES
            },
            "treated_specular": {
                path: array_sha256(values)
                for path, values in treated_specular.items()
            },
            "complete_early": {
                path: array_sha256(values) for path, values in h_early.items()
            },
        },
        "modeled_correlated_renderer_gain_db": finite_float(
            20.0 * math.log10(max(maximum_correlated, 1e-30)), 6
        ),
        "rendered_files": rendered_files,
        "plots": [
            "idealized-treated-early-impulse.svg",
            "ll-g-h-magnitude.svg",
            "upper-bass-direct-delta.svg",
        ],
        "reflections": reflection_metadata,
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Candidate H Idealized Treated Mastering Room",
        "",
        "Candidate H preserves G's geometry, personal direct sound, diffuse microclusters, and accepted synthetic late field. It changes one mechanism: coherent specular reflections receive idealized lower-midrange treatment after G's energy calibration, so the reduction is not normalized away.",
        "",
        "## Treatment",
        "",
        "- Side walls and ceiling: −9 dB low-frequency specular shelf.",
        "- Floor: −12 dB low-frequency specular shelf.",
        "- All shelves use a broad transition centered at 1 kHz and are causal; the first reflection onset is not advanced.",
        "- Diffuse microclusters and the E-minus-C late field remain bit-identical to G.",
        "",
        "## Offline Result",
        "",
        f"- Total early energy versus G: {summary['early_energy_delta_H_minus_G_db']:+.3f} dB.",
        f"- Center early energy versus G: {summary['center_early_energy_delta_H_minus_G_db']['left']:+.3f} dB left and {summary['center_early_energy_delta_H_minus_G_db']['right']:+.3f} dB right.",
        f"- Maximum center IACC: {summary['achieved_center_metrics']['maximum_absolute_iacc']:.3f}.",
        f"- H-minus-G bass RMS at 20–80 Hz: {summary['response_delta_H_minus_G']['bass_20_80_hz']['rms_delta_db']:.4f} dB.",
        f"- H-minus-G spatial-band RMS at 1–8 kHz: {summary['response_delta_H_minus_G']['spatial_1000_8000_hz']['rms_delta_db']:.4f} dB.",
        f"- Worst LL 200–350 Hz direct-path null: {summary['direct_relative_response_G_reference']['LL']['worst_200_350_hz_delta_db']:.2f} dB in G and {summary['direct_relative_response']['LL']['worst_200_350_hz_delta_db']:.2f} dB in H.",
        f"- Worst RR 200–350 Hz direct-path null: {summary['direct_relative_response_G_reference']['RR']['worst_200_350_hz_delta_db']:.2f} dB in G and {summary['direct_relative_response']['RR']['worst_200_350_hz_delta_db']:.2f} dB in H.",
        f"- Modeled maximum correlated renderer gain: {summary['modeled_correlated_renderer_gain_db']:+.2f} dB.",
        "",
        "H is an opt-in listening candidate. G remains unchanged and A remains the production default.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
