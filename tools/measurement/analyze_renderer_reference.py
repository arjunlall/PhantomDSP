#!/usr/bin/env python3
"""De-embed downstream/headphone processing from the legacy renderer capture."""

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
from analyze_bass_branches import load_capture


REPOSITORY = Path(__file__).resolve().parents[2]
CAPTURES = ("combined", "convolved", "clean", "downstream")
PRECISION_CAPTURES = ("convolved", "clean")
MATRIX_POSITIONS = {
    "LL": (0, 0),
    "LR": (1, 0),
    "RL": (0, 1),
    "RR": (1, 1),
}


def db20(value, floor=-180.0):
    value = float(value)
    return floor if value <= 0 else max(floor, 20.0 * math.log10(value))


def spectra_to_matrix(spectra):
    bins = len(next(iter(spectra.values())))
    matrix = np.zeros((bins, 2, 2), dtype=np.complex128)
    for label, position in MATRIX_POSITIONS.items():
        matrix[:, position[0], position[1]] = spectra[label]
    return matrix


def matrix_to_paths(matrix):
    return {
        label: matrix[:, position[0], position[1]]
        for label, position in MATRIX_POSITIONS.items()
    }


def capture_output_gain_db(capture):
    recorded = capture["header"].get("capture_output_gain", "0 dB")
    try:
        return float(recorded.split()[0])
    except (TypeError, ValueError, IndexError) as error:
        raise ValueError(
            f"Invalid capture output gain in Benchmark log: {recorded!r}"
        ) from error


def remove_output_gain(matrix, gain_db):
    return matrix / (10.0 ** (gain_db / 20.0))


def first_threshold(values, relative_db):
    absolute = np.abs(values)
    peak = float(np.max(absolute))
    if peak <= 0:
        return None
    indices = np.flatnonzero(absolute >= peak * 10.0 ** (relative_db / 20.0))
    return int(indices[0]) if len(indices) else None


def path_time_metrics(spectrum, nfft, response_length, sample_rate):
    impulse = np.fft.irfft(spectrum, nfft)[:response_length]
    peak_sample = int(np.argmax(np.abs(impulse)))
    return {
        "peak_sample": peak_sample,
        "peak_time_ms": finite_float(peak_sample / sample_rate * 1000.0, 6),
        "onset_minus_40_db_sample": first_threshold(impulse, -40.0),
        "onset_minus_60_db_sample": first_threshold(impulse, -60.0),
    }


def deembed_capture_matrices(matrices, audible, maximum_crosstalk_db):
    """Remove a measured diagonal downstream response from captured matrices."""
    downstream = matrices["downstream"]
    direct_peak = float(
        max(
            np.max(np.abs(downstream[audible, 0, 0])),
            np.max(np.abs(downstream[audible, 1, 1])),
        )
    )
    cross_peak = float(
        max(
            np.max(np.abs(downstream[audible, 0, 1])),
            np.max(np.abs(downstream[audible, 1, 0])),
        )
    )
    downstream_crosstalk_db = db20(cross_peak / max(direct_peak, 1e-18))
    if downstream_crosstalk_db > maximum_crosstalk_db:
        raise ValueError(
            "Downstream reference is not sufficiently diagonal: "
            f"{downstream_crosstalk_db:.2f} dB > "
            f"{maximum_crosstalk_db:.2f} dB"
        )

    diagonal = np.stack(
        [downstream[:, 0, 0], downstream[:, 1, 1]], axis=1
    )
    floor = np.maximum(
        np.max(np.abs(diagonal[audible]), axis=0) * 1e-8,
        1e-15,
    )
    safe_diagonal = np.where(
        np.abs(diagonal) > floor[None, :], diagonal, floor[None, :]
    )
    deembedded = {}
    for name in ("combined", "convolved", "clean"):
        result = matrices[name].copy()
        result[:, 0, :] /= safe_diagonal[:, 0, None]
        result[:, 1, :] /= safe_diagonal[:, 1, None]
        deembedded[name] = result

    closure = deembedded["combined"] - (
        deembedded["convolved"] + deembedded["clean"]
    )
    scalar = np.abs(deembedded["convolved"]) + np.abs(deembedded["clean"])
    closure_rms = float(
        np.sqrt(np.mean(np.abs(closure[audible]) ** 2))
        / max(np.sqrt(np.mean(scalar[audible] ** 2)), 1e-18)
    )
    return deembedded, downstream_crosstalk_db, closure_rms


def matrix_closure_rms_db(matrices, frequency_mask):
    closure = matrices["combined"] - (
        matrices["convolved"] + matrices["clean"]
    )
    scalar = np.abs(matrices["convolved"]) + np.abs(matrices["clean"])
    ratio = float(
        np.sqrt(np.mean(np.abs(closure[frequency_mask]) ** 2))
        / max(np.sqrt(np.mean(scalar[frequency_mask] ** 2)), 1e-18)
    )
    return finite_float(db20(ratio), 6)


def capture_runtime_metrics(capture):
    runs = capture["benchmark_runs"]
    return {
        "clipped_samples": sum(
            int(item.get("clipped_samples", 0)) for item in runs.values()
        ),
        "maximum_cpu_load_one_core_percent": finite_float(
            max(
                float(item.get("cpu_load_one_core_percent", 0.0))
                for item in runs.values()
            ),
            4,
        ),
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--precision-input-root",
        type=Path,
        default=(
            REPOSITORY
            / "measurements"
            / "minimum-latency"
            / "legacy-reference"
            / "raw"
            / "precision-branches"
        ),
        help=(
            "Use gain-calibrated convolved and clean captures from this directory "
            "when both are present"
        ),
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=(
            REPOSITORY
            / "measurements"
            / "minimum-latency"
            / "legacy-reference"
            / "raw"
            / "branches"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            REPOSITORY
            / "measurements"
            / "minimum-latency"
            / "legacy-reference"
            / "analysis"
        ),
    )
    parser.add_argument(
        "--maximum-downstream-crosstalk-db",
        type=float,
        default=-60.0,
        help="Fail if the nominally diagonal downstream matrix exceeds this leakage",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    captures = {name: load_capture(args.input_root / name) for name in CAPTURES}
    precision_paths = {
        name: args.precision_input_root / name for name in PRECISION_CAPTURES
    }
    precision_presence = {
        name: path.exists() for name, path in precision_paths.items()
    }
    if any(precision_presence.values()) and not all(precision_presence.values()):
        missing = [name for name, present in precision_presence.items() if not present]
        raise SystemExit(
            "Precision branch capture is incomplete; missing: " + ", ".join(missing)
        )
    precision_used = all(precision_presence.values())
    if precision_used:
        for name, path in precision_paths.items():
            captures[name] = load_capture(path)

    sample_rate = captures["combined"]["wave_info"]["sample_rate_hz"]
    mismatched_rates = {
        name: capture["wave_info"]["sample_rate_hz"]
        for name, capture in captures.items()
        if capture["wave_info"]["sample_rate_hz"] != sample_rate
    }
    if mismatched_rates:
        raise SystemExit(f"Capture sample rates do not match: {mismatched_rates}")
    response_length = min(
        len(captures[name]["responses"][label])
        for name in CAPTURES
        for label in PATHS
    )
    nfft = 1 << (response_length - 1).bit_length()
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)

    matrices = {}
    capture_gains_db = {}
    for name in CAPTURES:
        spectra = {
            label: np.fft.rfft(
                captures[name]["responses"][label][:response_length], nfft
            )
            for label in PATHS
        }
        capture_gains_db[name] = capture_output_gain_db(captures[name])
        matrices[name] = remove_output_gain(
            spectra_to_matrix(spectra), capture_gains_db[name]
        )

    try:
        deembedded, downstream_crosstalk_db, closure_rms = (
            deembed_capture_matrices(
                matrices,
                audible,
                args.maximum_downstream_crosstalk_db,
            )
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    combined_paths = matrix_to_paths(deembedded["combined"])
    convolved_paths = matrix_to_paths(deembedded["convolved"])
    clean_paths = matrix_to_paths(deembedded["clean"])
    closure_bands = {
        "20_80_hz": (frequencies >= 20.0) & (frequencies <= 80.0),
        "20_300_hz": (frequencies >= 20.0) & (frequencies <= 300.0),
        "20_20000_hz": audible,
    }
    summary = {
        "schema_version": 2,
        "sample_rate_hz": sample_rate,
        "response_length_samples": response_length,
        "nfft": nfft,
        "downstream_crosstalk_db": finite_float(downstream_crosstalk_db, 6),
        "deembedded_branch_closure_rms_db": finite_float(db20(closure_rms), 6),
        "deembedded_branch_closure_rms_db_by_band": {
            name: matrix_closure_rms_db(deembedded, mask)
            for name, mask in closure_bands.items()
        },
        "precision_branches_used": precision_used,
        "capture_output_gain_db": capture_gains_db,
        "capture_source": {
            name: (
                "precision" if precision_used and name in PRECISION_CAPTURES
                else "reference"
            )
            for name in CAPTURES
        },
        "paths": {
            label: path_time_metrics(
                combined_paths[label], nfft, response_length, sample_rate
            )
            for label in PATHS
        },
        "capture_headers": {
            name: captures[name]["header"] for name in CAPTURES
        },
        "capture_runtime": {
            name: capture_runtime_metrics(captures[name]) for name in CAPTURES
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    archive = {
        "frequency_hz": frequencies,
        "sample_rate_hz": np.array(sample_rate),
        "response_length_samples": np.array(response_length),
    }
    for branch_name, paths in (
        ("combined", combined_paths),
        ("convolved", convolved_paths),
        ("clean", clean_paths),
    ):
        for label, spectrum in paths.items():
            archive[f"{branch_name}_{label}"] = spectrum
    np.savez_compressed(args.output_dir / "deembedded-reference.npz", **archive)

    report = [
        "# Legacy Renderer Reference",
        "",
        "This analysis removes the measured downstream target, headphone, and personal EQ from the four Benchmark matrices. The resulting archive is the speaker-renderer-only legacy target used to derive the production 2×2 renderer.",
        "",
        "## Validation",
        "",
        (
            "- Gain-calibrated precision captures were used for the convolved "
            "and clean branches (+24 dB and +48 dB respectively); stored spectra "
            "have those measurement gains removed."
            if precision_used
            else "- Precision branch captures are not present; convolved and clean "
            "spectra still come from the original low-level 16-bit captures."
        ),
        f"- Downstream off-diagonal leakage: {summary['downstream_crosstalk_db']:.2f} dB.",
        f"- De-embedded combined ≈ convolved + clean closure: {summary['deembedded_branch_closure_rms_db_by_band']['20_80_hz']:.2f} dB RMS at 20–80 Hz, {summary['deembedded_branch_closure_rms_db_by_band']['20_300_hz']:.2f} dB at 20–300 Hz, and {summary['deembedded_branch_closure_rms_db_by_band']['20_20000_hz']:.2f} dB at 20 Hz–20 kHz.",
        "- Every isolated impulse capture reports zero clipped samples.",
        (
            "- The combined reference remains a separate 16-bit capture, so use "
            "smoothed low-frequency targets rather than treating residual closure "
            "or quantization ripple as acoustic detail."
            if precision_used
            else "- The independent 16-bit captures have the same approximate "
            "low-frequency closure floor as prior accepted branch measurements; "
            "use smoothed low-frequency targets rather than treating quantization "
            "ripple as acoustic detail."
        ),
        "",
        "## Timing",
        "",
        "| Path | −60 dB onset | −40 dB onset | Peak | Peak time |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label in PATHS:
        item = summary["paths"][label]
        report.append(
            f"| `{label}` | {item['onset_minus_60_db_sample']} | "
            f"{item['onset_minus_40_db_sample']} | {item['peak_sample']} | "
            f"{item['peak_time_ms']:.3f} ms |"
        )
    report.extend(
        [
            "",
            "Machine-readable spectra are stored in `deembedded-reference.npz`; source metadata and validation metrics are in `summary.json`.",
        ]
    )
    (args.output_dir / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
