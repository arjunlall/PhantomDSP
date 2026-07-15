#!/usr/bin/env python3
"""Analyze public directional HRTF deltas at PhantomDSP reflection angles."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

from analyze_baseline import finite_float, write_svg_plot
from analyze_bass_branches import log_smooth
from render_synthetic_direct import REPOSITORY, load_stereo_paths
from render_synthetic_early_room import DIRECT_FILES


DEFAULT_INPUT = REPOSITORY / "measurements" / "hrtf-datasets" / "ari"
DEFAULT_OUTPUT = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "directional-hrtf"
    / "analysis"
)
NFFT = 8192
MATCH_BAND_HZ = (4000.0, 12000.0)
PLOT_BAND_HZ = (3500.0, 14000.0)
SCALE_GRID = np.linspace(0.85, 1.15, 61)
MODEL_FREQUENCIES_HZ = np.geomspace(3000.0, 16000.0, 193)

# Room azimuth uses negative-left/positive-right. SOFA uses positive-left.
ROOM_DIRECTIONS = {
    "left": {
        "direct": (-30.0, 0.0),
        "left_wall": (-52.145209, 0.0),
        "right_wall": (67.323641, 0.0),
        "floor": (-30.0, -39.739606),
        "ceiling": (-30.0, 47.946072),
    },
    "right": {
        "direct": (30.0, 0.0),
        "left_wall": (-67.725533, 0.0),
        "right_wall": (51.084996, 0.0),
        "floor": (30.0, -39.739606),
        "ceiling": (30.0, 47.946072),
    },
}
PATHS = {
    ("left", "left"): "LL",
    ("left", "right"): "LR",
    ("right", "left"): "RL",
    ("right", "right"): "RR",
}
EAR_INDEX = {"left": 0, "right": 1}
COLORS = {
    "floor_left": "#2563eb",
    "ceiling_left": "#dc2626",
    "floor_right": "#7c3aed",
    "ceiling_right": "#d97706",
    "left_wall_left": "#2563eb",
    "right_wall_left": "#059669",
    "left_wall_right": "#7c3aed",
    "right_wall_right": "#d97706",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def room_to_sofa(azimuth, elevation):
    return (-azimuth) % 360.0, elevation


def direction_vector(azimuth, elevation):
    azimuth = math.radians(azimuth)
    elevation = math.radians(elevation)
    cosine = math.cos(elevation)
    return np.array(
        [cosine * math.cos(azimuth), cosine * math.sin(azimuth), math.sin(elevation)]
    )


def angular_distances(positions, target):
    azimuth = np.radians(positions[:, 0])
    elevation = np.radians(positions[:, 1])
    vectors = np.column_stack(
        (
            np.cos(elevation) * np.cos(azimuth),
            np.cos(elevation) * np.sin(azimuth),
            np.sin(elevation),
        )
    )
    target_vector = direction_vector(*target)
    return np.degrees(np.arccos(np.clip(vectors @ target_vector, -1.0, 1.0)))


def nearest_direction(positions, target):
    distances = angular_distances(positions, target)
    index = int(np.argmin(distances))
    return index, float(distances[index])


def smoothed_response(values, sample_rate, nfft=NFFT):
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    spectrum = np.fft.rfft(values, nfft)
    raw = 20.0 * np.log10(np.maximum(np.abs(spectrum), 1e-12))
    smooth = np.empty_like(raw)
    smooth[1:] = np.asarray(
        log_smooth(frequencies[1:], raw[1:], fraction=6), dtype=np.float64
    )
    smooth[0] = smooth[1]
    return frequencies, smooth


def load_sofa(path):
    try:
        import h5py
    except ImportError as error:
        raise RuntimeError(
            "Directional HRTF analysis requires h5py; install tools/measurement/requirements.txt"
        ) from error
    with h5py.File(path, "r") as handle:
        positions = np.asarray(handle["SourcePosition"], dtype=np.float64)
        impulses = np.asarray(handle["Data.IR"], dtype=np.float64)
        sample_rate = float(np.asarray(handle["Data.SamplingRate"])[0])
        listener = handle.attrs.get("ListenerShortName", path.stem)
        if isinstance(listener, bytes):
            listener = listener.decode("utf-8")
        license_name = handle.attrs.get("License", b"")
        if isinstance(license_name, bytes):
            license_name = license_name.decode("utf-8")
    return str(listener), positions, impulses, sample_rate, str(license_name)


def analyze_subject(path, minimum_directions=400):
    listener, positions, impulses, sample_rate, license_name = load_sofa(path)
    if len(positions) < minimum_directions:
        raise ValueError(
            f"{path.name} has only {len(positions)} directions; need {minimum_directions}"
        )
    if round(sample_rate) != 48000:
        raise ValueError(f"Expected 48 kHz ARI DTF input: {path}")
    responses = {speaker: {} for speaker in ROOM_DIRECTIONS}
    selections = {speaker: {} for speaker in ROOM_DIRECTIONS}
    frequencies = None
    for speaker, directions in ROOM_DIRECTIONS.items():
        for name, room_direction in directions.items():
            target = room_to_sofa(*room_direction)
            index, error = nearest_direction(positions, target)
            responses[speaker][name] = {}
            for ear, ear_index in EAR_INDEX.items():
                frequencies, curve = smoothed_response(
                    impulses[index, ear_index], sample_rate
                )
                responses[speaker][name][ear] = curve
            selections[speaker][name] = {
                "requested_room_degrees": list(room_direction),
                "requested_sofa_degrees": [finite_float(value, 6) for value in target],
                "selected_sofa_degrees": [
                    finite_float(value, 6) for value in positions[index, :2]
                ],
                "angular_error_degrees": finite_float(error, 6),
            }
    deltas = {speaker: {} for speaker in ROOM_DIRECTIONS}
    for speaker in ROOM_DIRECTIONS:
        for surface in ("left_wall", "right_wall", "floor", "ceiling"):
            deltas[speaker][surface] = {
                ear: responses[speaker][surface][ear]
                - responses[speaker]["direct"][ear]
                for ear in EAR_INDEX
            }
    direct = {
        PATHS[(speaker, ear)]: responses[speaker]["direct"][ear]
        for speaker in ROOM_DIRECTIONS
        for ear in EAR_INDEX
    }
    return {
        "listener": listener,
        "path": path,
        "sha256": sha256(path),
        "license": license_name,
        "frequencies": frequencies,
        "direct": direct,
        "deltas": deltas,
        "selections": selections,
    }


def direction_centered_profiles(curves):
    output = {}
    for ear, first, second in (
        ("left", "LL", "RL"),
        ("right", "LR", "RR"),
    ):
        center = 0.5 * (curves[first] + curves[second])
        output[first] = curves[first] - center
        output[second] = curves[second] - center
    return output


def normalize_match_profile(values, band):
    return values - float(np.mean(values[band]))


def warp_curve(frequencies, values, scale):
    return np.interp(
        frequencies / scale,
        frequencies,
        values,
        left=float(values[0]),
        right=float(values[-1]),
    )


def match_scale(frequencies, personal, candidate, scales=SCALE_GRID):
    band = (frequencies >= MATCH_BAND_HZ[0]) & (frequencies <= MATCH_BAND_HZ[1])
    personal_normalized = {
        path: normalize_match_profile(values, band) for path, values in personal.items()
    }
    best = None
    for scale in scales:
        errors = []
        for path, values in candidate.items():
            warped = warp_curve(frequencies, values, float(scale))
            warped = normalize_match_profile(warped, band)
            errors.append(warped[band] - personal_normalized[path][band])
        score = float(np.sqrt(np.mean(np.square(np.concatenate(errors)))))
        if best is None or score < best["score_db"]:
            best = {"scale": float(scale), "score_db": score}
    return best


def load_personal_profiles(frequencies):
    paths, sample_rate, metadata = load_stereo_paths(DIRECT_FILES)
    if sample_rate != 48000:
        raise ValueError("Personal direct renderer must be 48 kHz")
    curves = {}
    for path, values in paths.items():
        source_frequencies, curve = smoothed_response(values, sample_rate)
        curves[path] = np.interp(frequencies, source_frequencies, curve)
    return direction_centered_profiles(curves), metadata


def nested_curves(subject, scale=1.0):
    frequencies = subject["frequencies"]
    return {
        speaker: {
            surface: {
                ear: warp_curve(frequencies, subject["deltas"][speaker][surface][ear], scale)
                for ear in EAR_INDEX
            }
            for surface in ("left_wall", "right_wall", "floor", "ceiling")
        }
        for speaker in ROOM_DIRECTIONS
    }


def median_curves(subjects, scaled):
    output = {speaker: {} for speaker in ROOM_DIRECTIONS}
    for speaker in ROOM_DIRECTIONS:
        for surface in ("left_wall", "right_wall", "floor", "ceiling"):
            output[speaker][surface] = {}
            for ear in EAR_INDEX:
                values = []
                for subject in subjects:
                    scale = subject["match"]["scale"] if scaled else 1.0
                    values.append(
                        warp_curve(
                            subject["frequencies"],
                            subject["deltas"][speaker][surface][ear],
                            scale,
                        )
                    )
                output[speaker][surface][ear] = np.median(np.stack(values), axis=0)
    return output


def plot_limits(series, band):
    maximum = max(float(np.max(np.abs(values[band]))) for _, values, _ in series)
    limit = min(30.0, max(10.0, math.ceil(maximum / 5.0) * 5.0))
    return -limit, limit


def write_delta_plot(output, filename, title, frequencies, curves, surfaces):
    band = (frequencies >= PLOT_BAND_HZ[0]) & (frequencies <= PLOT_BAND_HZ[1])
    items = []
    for surface in surfaces:
        for ear in ("left", "right"):
            label = f"{surface.replace('_', ' ')} → {ear} ear"
            color = COLORS[f"{surface}_{ear}"]
            items.append((label, curves[surface][ear], color))
    y_min, y_max = plot_limits(items, band)
    write_svg_plot(
        output / filename,
        title,
        [(label, frequencies[band], values[band], color) for label, values, color in items],
        "Frequency (Hz)",
        "Directional delta from ±30° direct (dB)",
        PLOT_BAND_HZ[0],
        PLOT_BAND_HZ[1],
        y_min,
        y_max,
        [4000, 5000, 6000, 7000, 8000, 10000, 12000, 14000],
        x_scale="log",
    )


def write_match_plot(output, frequencies, personal, best):
    band = (frequencies >= PLOT_BAND_HZ[0]) & (frequencies <= PLOT_BAND_HZ[1])
    colors = {"left": "#2563eb", "right": "#059669"}
    series = []
    for ear, ipsi, contra in (
        ("left", "LL", "RL"),
        ("right", "RR", "LR"),
    ):
        personal_contrast = personal[ipsi] - personal[contra]
        candidate_contrast = best[ipsi] - best[contra]
        series.extend(
            [
                (f"personal {ear}", personal_contrast, colors[ear]),
                (f"best ARI {ear}", candidate_contrast, "#6b7280" if ear == "left" else "#d97706"),
            ]
        )
    y_min, y_max = plot_limits(series, band)
    write_svg_plot(
        output / "personal-direct-match.svg",
        "Personal ±30° Directional Contrast versus Best ARI Match",
        [(label, frequencies[band], values[band], color) for label, values, color in series],
        "Frequency (Hz)",
        "Ipsilateral minus contralateral response (dB)",
        PLOT_BAND_HZ[0],
        PLOT_BAND_HZ[1],
        y_min,
        y_max,
        [4000, 5000, 6000, 7000, 8000, 10000, 12000, 14000],
        x_scale="log",
    )


def write_model_comparison(output, filename, title, frequencies, models, surface):
    band = (frequencies >= PLOT_BAND_HZ[0]) & (frequencies <= PLOT_BAND_HZ[1])
    styles = {
        "population": ("#6b7280", "population median"),
        "top_five": ("#2563eb", "top-five matched median"),
        "best": ("#d97706", "best single match"),
    }
    series = []
    for model_name, curves in models.items():
        color, label = styles[model_name]
        for speaker, ear, path_label in (
            ("left", "left", "LL"),
            ("right", "right", "RR"),
        ):
            series.append(
                (
                    f"{label} {path_label}",
                    curves[speaker][surface][ear],
                    color if path_label == "LL" else (
                        "#059669" if model_name == "top_five" else
                        "#a1a1aa" if model_name == "population" else
                        "#dc2626"
                    ),
                )
            )
    y_min, y_max = plot_limits(series, band)
    write_svg_plot(
        output / filename,
        title,
        [(label, frequencies[band], values[band], color) for label, values, color in series],
        "Frequency (Hz)",
        "Directional delta from ±30° direct (dB)",
        PLOT_BAND_HZ[0],
        PLOT_BAND_HZ[1],
        y_min,
        y_max,
        [4000, 5000, 6000, 7000, 8000, 10000, 12000, 14000],
        x_scale="log",
    )


def sampled_metrics(frequencies, curves):
    result = {}
    for speaker in ROOM_DIRECTIONS:
        result[speaker] = {}
        for surface in ("left_wall", "right_wall", "floor", "ceiling"):
            result[speaker][surface] = {}
            for ear in EAR_INDEX:
                result[speaker][surface][ear] = {
                    str(frequency): finite_float(
                        np.interp(frequency, frequencies, curves[speaker][surface][ear]), 6
                    )
                    for frequency in (5000, 7000, 8000, 10000, 12000)
                }
    return result


def serialized_directional_model(frequencies, curves, subjects, input_manifest):
    return {
        "schema_version": 1,
        "model": "median of five best personal-direct matches",
        "source_dataset": input_manifest.get("dataset", "ARI in-the-ear DTF"),
        "source": input_manifest.get(
            "source", "https://sofacoustics.org/data/database/ari/"
        ),
        "personal_match_band_hz": list(MATCH_BAND_HZ),
        "smoothing_fractional_octave": 6,
        "frequencies_hz": [
            finite_float(value, 6) for value in MODEL_FREQUENCIES_HZ
        ],
        "matched_subjects": [
            {
                "listener": subject["listener"],
                "filename": subject["path"].name,
                "sha256": subject["sha256"],
                "frequency_scale": finite_float(subject["match"]["scale"], 6),
                "match_rms_db": finite_float(subject["match"]["score_db"], 6),
            }
            for subject in subjects[:5]
        ],
        "directional_delta_db": {
            speaker: {
                surface: {
                    ear: [
                        finite_float(value, 6)
                        for value in np.interp(
                            MODEL_FREQUENCIES_HZ,
                            frequencies,
                            curves[speaker][surface][ear],
                        )
                    ]
                    for ear in EAR_INDEX
                }
                for surface in ("left_wall", "right_wall", "floor", "ceiling")
            }
            for speaker in ROOM_DIRECTIONS
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--minimum-directions", type=int, default=400)
    arguments = parser.parse_args()
    files = sorted(arguments.input.glob("*.sofa"))
    if len(files) < 4:
        raise SystemExit(f"Need at least four ARI DTF files under {arguments.input}")
    arguments.output.mkdir(parents=True, exist_ok=True)

    subjects = []
    for index, path in enumerate(files, start=1):
        print(f"Analyzing {path.name} ({index}/{len(files)})", file=sys.stderr)
        try:
            subjects.append(analyze_subject(path, arguments.minimum_directions))
        except ValueError as error:
            print(f"Skipping: {error}", file=sys.stderr)
    if len(subjects) < 4:
        raise SystemExit("Fewer than four full-resolution ARI subjects remained")
    frequencies = subjects[0]["frequencies"]
    personal, personal_metadata = load_personal_profiles(frequencies)
    for subject in subjects:
        subject_profiles = direction_centered_profiles(subject["direct"])
        subject["match"] = match_scale(frequencies, personal, subject_profiles)
    subjects.sort(key=lambda item: item["match"]["score_db"])
    best = subjects[0]

    median_unscaled = median_curves(subjects, scaled=False)
    median_scaled = median_curves(subjects, scaled=True)
    top_five_scaled = median_curves(subjects[:5], scaled=True)
    best_curves = nested_curves(best, best["match"]["scale"])
    best_profiles = direction_centered_profiles(best["direct"])
    best_profiles = {
        path: warp_curve(frequencies, values, best["match"]["scale"])
        for path, values in best_profiles.items()
    }

    write_match_plot(arguments.output, frequencies, personal, best_profiles)
    for speaker in ("left", "right"):
        write_delta_plot(
            arguments.output,
            f"{speaker}-speaker-elevation-deltas.svg",
            f"{speaker.title()} Speaker: Personal-Scaled Median Elevation Deltas",
            frequencies,
            median_scaled[speaker],
            ("floor", "ceiling"),
        )
        write_delta_plot(
            arguments.output,
            f"{speaker}-speaker-wall-deltas.svg",
            f"{speaker.title()} Speaker: Personal-Scaled Median Wall Deltas",
            frequencies,
            median_scaled[speaker],
            ("left_wall", "right_wall"),
        )
    comparison_models = {
        "population": median_scaled,
        "top_five": top_five_scaled,
        "best": best_curves,
    }
    write_model_comparison(
        arguments.output,
        "ceiling-model-comparison.svg",
        "Ipsilateral Ceiling Delta: Population versus Personal Matches",
        frequencies,
        comparison_models,
        "ceiling",
    )
    write_model_comparison(
        arguments.output,
        "floor-model-comparison.svg",
        "Ipsilateral Floor Delta: Population versus Personal Matches",
        frequencies,
        comparison_models,
        "floor",
    )

    manifest_path = arguments.input / "manifest.json"
    input_manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    directional_model = serialized_directional_model(
        frequencies, top_five_scaled, subjects, input_manifest
    )
    (arguments.output / "directional-model.json").write_text(
        json.dumps(directional_model, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "schema_version": 1,
        "status": "directional-HRTF screening analysis; no candidate K rendered",
        "dataset": {
            "name": input_manifest.get("dataset", "ARI in-the-ear DTF"),
            "source": input_manifest.get(
                "source", "https://sofacoustics.org/data/database/ari/"
            ),
            "subjects_analyzed": len(subjects),
            "selection_boundary": input_manifest.get(
                "selection",
                "deterministic local screening subset, not a population sample",
            ),
            "files": [
                {
                    "listener": subject["listener"],
                    "filename": subject["path"].name,
                    "sha256": subject["sha256"],
                    "license": subject["license"],
                    "match_scale": finite_float(subject["match"]["scale"], 6),
                    "match_rms_db": finite_float(subject["match"]["score_db"], 6),
                }
                for subject in subjects
            ],
        },
        "method": {
            "personal_anchor": "four personal ±30° direct paths, direction-centered per ear",
            "match_band_hz": list(MATCH_BAND_HZ),
            "smoothing_fractional_octave": 6,
            "frequency_scale_range": [
                finite_float(SCALE_GRID[0], 6),
                finite_float(SCALE_GRID[-1], 6),
            ],
            "directional_model": "H_personal(Ω0) × H_ARI(Ω) / H_ARI(Ω0)",
            "phase_or_hrir_rendering_performed": False,
        },
        "best_match": {
            "listener": best["listener"],
            "frequency_scale": finite_float(best["match"]["scale"], 6),
            "match_rms_db": finite_float(best["match"]["score_db"], 6),
        },
        "personal_direct_files": personal_metadata,
        "selected_directions": best["selections"],
        "directional_delta_db": {
            "population_median_unscaled": sampled_metrics(
                frequencies, median_unscaled
            ),
            "population_median_personal_scaled": sampled_metrics(
                frequencies, median_scaled
            ),
            "top_five_matches_personal_scaled": sampled_metrics(
                frequencies, top_five_scaled
            ),
            "best_match_personal_scaled": sampled_metrics(
                frequencies, best_curves
            ),
        },
        "plots": [
            "personal-direct-match.svg",
            "left-speaker-elevation-deltas.svg",
            "right-speaker-elevation-deltas.svg",
            "left-speaker-wall-deltas.svg",
            "right-speaker-wall-deltas.svg",
            "ceiling-model-comparison.svg",
            "floor-model-comparison.svg",
        ],
        "rendering_model": "directional-model.json",
    }
    (arguments.output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
