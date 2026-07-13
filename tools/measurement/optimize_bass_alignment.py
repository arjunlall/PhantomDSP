#!/usr/bin/env python3
"""Optimize clean-bass gain, polarity, and delay from measured EAPO branches."""

import argparse
import json
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise SystemExit(
        "NumPy is required. Install it with: "
        "python3 -m pip install -r tools/measurement/requirements.txt"
    )

from analyze_baseline import COLORS, PATHS, finite_float, write_svg_plot
from analyze_bass_branches import db20_array, load_capture


SCHEMA_VERSION = 1
GROUPS = {
    "direct": ("LL", "RR"),
    "cross": ("LR", "RL"),
}
PATH_GROUP = {
    label: group
    for group, labels in GROUPS.items()
    for label in labels
}
CURRENT_DELAY_SAMPLES = {
    "direct": 100,
    "cross": 115,
}
PLOT_COLORS = {
    "current": "#64748b",
    "shared": "#2563eb",
    "direct_cross": "#dc2626",
}
FREQUENCY_TICKS = [20, 30, 40, 50, 70, 90, 100, 120, 150, 200, 250, 300]
TRADEOFF_TOLERANCES_DB = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)


def smoothing_windows(frequencies, fraction):
    half_ratio = 2.0 ** (1.0 / (2.0 * fraction))
    starts = np.searchsorted(frequencies, frequencies / half_ratio, side="left")
    stops = np.searchsorted(frequencies, frequencies * half_ratio, side="right")
    return starts, stops


def smooth_rows(values, starts, stops):
    values = np.asarray(values, dtype=np.float64)
    cumulative = np.pad(
        np.cumsum(values, axis=-1),
        [(0, 0)] * (values.ndim - 1) + [(1, 0)],
        mode="constant",
    )
    counts = stops - starts
    return (cumulative[..., stops] - cumulative[..., starts]) / counts


def load_spectra(input_root, low_frequency, high_frequency):
    captures = {
        name: load_capture(input_root / name)
        for name in ("convolved", "clean")
    }
    sample_rate = captures["convolved"]["wave_info"]["sample_rate_hz"]
    response_length = min(
        len(captures[capture]["responses"][label])
        for capture in captures
        for label in PATHS
    )
    nfft = 1 << max(1, (response_length - 1).bit_length())
    all_frequencies = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)
    band = (all_frequencies >= low_frequency) & (all_frequencies <= high_frequency)
    frequencies = all_frequencies[band]
    spectra = {capture: {} for capture in captures}
    for capture in captures:
        for label in PATHS:
            spectrum = np.fft.rfft(
                captures[capture]["responses"][label][:response_length], n=nfft
            )
            spectra[capture][label] = spectrum[band]
    return captures, sample_rate, nfft, frequencies, spectra


def candidate_grid(args):
    delays = np.arange(
        args.minimum_delay_adjustment,
        args.maximum_delay_adjustment + args.delay_step / 2.0,
        args.delay_step,
        dtype=np.float64,
    )
    gains = np.arange(
        args.minimum_gain_adjustment,
        args.maximum_gain_adjustment + args.gain_step / 2.0,
        args.gain_step,
        dtype=np.float64,
    )
    delay_grid, gain_grid, polarity_grid = np.meshgrid(
        delays, gains, np.array([1.0, -1.0]), indexing="ij"
    )
    return {
        "delay_adjustment_samples": delay_grid.ravel(),
        "gain_adjustment_db": gain_grid.ravel(),
        "polarity": polarity_grid.ravel(),
    }


def transformed_clean(clean, frequencies, sample_rate, delay_samples, gain_db, polarity):
    phase = np.exp(
        -2j * np.pi * frequencies * delay_samples / float(sample_rate)
    )
    scale = polarity * (10.0 ** (gain_db / 20.0))
    return clean * scale * phase


def evaluate_grid(
    path_labels,
    grid,
    frequencies,
    spectra,
    sample_rate,
    starts,
    stops,
    transition,
    low_bass,
    batch_size,
):
    candidate_count = len(grid["delay_adjustment_samples"])
    deepest_by_path = {
        label: np.empty(candidate_count, dtype=np.float64)
        for label in path_labels
    }
    percentile_by_path = {
        label: np.empty(candidate_count, dtype=np.float64)
        for label in path_labels
    }
    low_rms_by_path = {
        label: np.empty(candidate_count, dtype=np.float64)
        for label in path_labels
    }

    for offset in range(0, candidate_count, batch_size):
        end = min(candidate_count, offset + batch_size)
        selection = slice(offset, end)
        delays = grid["delay_adjustment_samples"][selection, None]
        gains = grid["gain_adjustment_db"][selection, None]
        polarities = grid["polarity"][selection, None]
        phase = np.exp(
            -2j * np.pi * frequencies[None, :] * delays / float(sample_rate)
        )
        scales = polarities * np.power(10.0, gains / 20.0)

        for label in path_labels:
            convolved = spectra["convolved"][label][None, :]
            clean = spectra["clean"][label][None, :]
            candidate_clean = clean * scales * phase
            candidate_sum = convolved + candidate_clean
            current_sum = convolved + clean

            raw_interference = db20_array(candidate_sum) - db20_array(
                np.abs(convolved) + np.abs(candidate_clean)
            )
            interference = smooth_rows(raw_interference, starts, stops)
            deepest_by_path[label][selection] = np.min(
                interference[:, transition], axis=1
            )
            percentile_by_path[label][selection] = np.percentile(
                interference[:, transition], 10.0, axis=1
            )

            raw_output_change = db20_array(candidate_sum) - db20_array(current_sum)
            output_change = smooth_rows(raw_output_change, starts, stops)
            low_rms_by_path[label][selection] = np.sqrt(
                np.mean(np.square(output_change[:, low_bass]), axis=1)
            )

    deepest = np.min(
        np.column_stack([deepest_by_path[label] for label in path_labels]), axis=1
    )
    percentile = np.min(
        np.column_stack([percentile_by_path[label] for label in path_labels]), axis=1
    )
    maximum_low_rms = np.max(
        np.column_stack([low_rms_by_path[label] for label in path_labels]), axis=1
    )
    return {
        "deepest_interference_db": deepest,
        "tenth_percentile_interference_db": percentile,
        "maximum_low_bass_rms_change_db": maximum_low_rms,
        "deepest_by_path": deepest_by_path,
        "low_rms_by_path": low_rms_by_path,
    }


def select_candidate(grid, evaluation, tolerance):
    eligible = np.flatnonzero(
        evaluation["maximum_low_bass_rms_change_db"] <= tolerance
    )
    if len(eligible) == 0:
        raise ValueError(
            "No candidate preserves the low-bass level within the requested tolerance"
        )
    order = sorted(
        eligible,
        key=lambda index: (
            -evaluation["deepest_interference_db"][index],
            -evaluation["tenth_percentile_interference_db"][index],
            evaluation["maximum_low_bass_rms_change_db"][index],
            abs(grid["gain_adjustment_db"][index]),
            grid["delay_adjustment_samples"][index],
        ),
    )
    index = int(order[0])
    return {
        "delay_adjustment_samples": float(grid["delay_adjustment_samples"][index]),
        "gain_adjustment_db": float(grid["gain_adjustment_db"][index]),
        "polarity": int(grid["polarity"][index]),
        "search_metrics": {
            "deepest_interference_db": finite_float(
                evaluation["deepest_interference_db"][index], 5
            ),
            "tenth_percentile_interference_db": finite_float(
                evaluation["tenth_percentile_interference_db"][index], 5
            ),
            "maximum_low_bass_rms_change_db": finite_float(
                evaluation["maximum_low_bass_rms_change_db"][index], 5
            ),
        },
    }


def evaluate_configuration(
    controls,
    frequencies,
    spectra,
    sample_rate,
    starts,
    stops,
    transition,
    low_bass,
):
    paths = {}
    for label in PATHS:
        group = PATH_GROUP[label]
        control = controls[group]
        convolved = spectra["convolved"][label]
        clean = transformed_clean(
            spectra["clean"][label],
            frequencies,
            sample_rate,
            control["delay_adjustment_samples"],
            control["gain_adjustment_db"],
            control["polarity"],
        )
        candidate_sum = convolved + clean
        current_sum = convolved + spectra["clean"][label]
        interference = smooth_rows(
            (db20_array(candidate_sum) - db20_array(np.abs(convolved) + np.abs(clean)))[None, :],
            starts,
            stops,
        )[0]
        output_change = smooth_rows(
            (db20_array(candidate_sum) - db20_array(current_sum))[None, :],
            starts,
            stops,
        )[0]
        sum_vs_convolved = smooth_rows(
            (db20_array(candidate_sum) - db20_array(convolved))[None, :],
            starts,
            stops,
        )[0]
        clean_to_convolved = smooth_rows(
            (db20_array(clean) - db20_array(convolved))[None, :],
            starts,
            stops,
        )[0]
        relative_phase = np.angle(clean * np.conj(convolved))
        phase_difference = np.degrees(np.angle(smooth_rows_complex_unit(
            relative_phase, np.sqrt(np.abs(clean) * np.abs(convolved)), starts, stops
        )))
        transition_indices = np.flatnonzero(transition)
        worst_index = transition_indices[
            int(np.argmin(interference[transition]))
        ]
        minimum_sum_index = transition_indices[
            int(np.argmin(sum_vs_convolved[transition]))
        ]
        paths[label] = {
            "interference_db": interference,
            "output_change_db": output_change,
            "sum_vs_convolved_db": sum_vs_convolved,
            "deepest_interference_db": finite_float(interference[worst_index], 5),
            "deepest_interference_frequency_hz": finite_float(
                frequencies[worst_index], 5
            ),
            "clean_to_convolved_at_deepest_db": finite_float(
                clean_to_convolved[worst_index], 5
            ),
            "phase_at_deepest_degrees": finite_float(
                phase_difference[worst_index], 5
            ),
            "minimum_sum_vs_convolved_db": finite_float(
                sum_vs_convolved[minimum_sum_index], 5
            ),
            "minimum_sum_vs_convolved_frequency_hz": finite_float(
                frequencies[minimum_sum_index], 5
            ),
            "low_bass_rms_change_db": finite_float(
                np.sqrt(np.mean(np.square(output_change[low_bass]))), 5
            ),
        }

    all_transition = np.concatenate(
        [paths[label]["interference_db"][transition] for label in PATHS]
    )
    return {
        "controls": controls,
        "paths": paths,
        "metrics": {
            "deepest_interference_db": finite_float(np.min(all_transition), 5),
            "tenth_percentile_interference_db": finite_float(
                np.percentile(all_transition, 10.0), 5
            ),
            "maximum_low_bass_rms_change_db": finite_float(
                max(paths[label]["low_bass_rms_change_db"] for label in PATHS), 5
            ),
            "minimum_sum_vs_convolved_db": finite_float(
                min(paths[label]["minimum_sum_vs_convolved_db"] for label in PATHS), 5
            ),
        },
    }


def smooth_rows_complex_unit(phases, weights, starts, stops):
    phasors = np.exp(1j * phases)
    weighted = phasors * weights
    cumulative_values = np.pad(np.cumsum(weighted), (1, 0), mode="constant")
    cumulative_weights = np.pad(np.cumsum(weights), (1, 0), mode="constant")
    numerator = cumulative_values[stops] - cumulative_values[starts]
    denominator = cumulative_weights[stops] - cumulative_weights[starts]
    return numerator / np.maximum(denominator, 1e-18)


def serializable_configuration(configuration):
    return {
        "controls": configuration["controls"],
        "metrics": configuration["metrics"],
        "paths": {
            label: {
                key: value
                for key, value in data.items()
                if not isinstance(value, np.ndarray)
            }
            for label, data in configuration["paths"].items()
        },
    }


def controls_from_candidate(candidate):
    return {
        key: value
        for key, value in candidate.items()
        if key != "search_metrics"
    }


def control_text(control, group):
    polarity = "normal" if control["polarity"] > 0 else "inverted"
    resulting_delay = CURRENT_DELAY_SAMPLES[group] + control["delay_adjustment_samples"]
    return (
        f"{control['gain_adjustment_db']:+.2f} dB, {polarity}, "
        f"{resulting_delay:.0f} samples"
    )


def write_report(path, summary):
    configurations = summary["configurations"]
    tradeoffs = summary["preservation_tradeoff"]
    current = configurations["current"]
    shared = configurations["shared"]
    separate = configurations["direct_cross"]
    lines = [
        "# Bass Alignment Optimization",
        "",
        "This offline search treats the clean-low branch like a subwoofer integrated with the convolved BRIR branch. It changes only clean-branch gain, polarity, and integer-sample delay in the measured complex responses; no Equalizer APO configuration is changed.",
        "",
        "Candidates must keep every path's modeled 25–70 Hz output within "
        f"{summary['search']['low_bass_rms_tolerance_db']:.2f} dB RMS of the current blend. This prevents the optimizer from avoiding cancellation by simply removing the clean bass.",
        "",
        "## Model Comparison",
        "",
        "| Model | Deepest interference | 10th percentile | Maximum low-bass change | Minimum sum vs convolved |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    labels = {
        "current": "Current blend",
        "shared": "Shared adjustment",
        "direct_cross": "Separate direct/cross",
    }
    for name in ("current", "shared", "direct_cross"):
        metrics = configurations[name]["metrics"]
        lines.append(
            f"| {labels[name]} | {metrics['deepest_interference_db']:.2f} dB | "
            f"{metrics['tenth_percentile_interference_db']:.2f} dB | "
            f"{metrics['maximum_low_bass_rms_change_db']:.2f} dB | "
            f"{metrics['minimum_sum_vs_convolved_db']:.2f} dB |"
        )

    lines.extend(
        [
            "",
            "## Deep-Bass Preservation Tradeoff",
            "",
            "| Allowed 25–70 Hz RMS change | Shared worst interference | Separate direct/cross worst interference |",
            "| ---: | ---: | ---: |",
        ]
    )
    for item in tradeoffs:
        lines.append(
            f"| {item['tolerance_db']:.1f} dB | "
            f"{item['shared']['metrics']['deepest_interference_db']:.2f} dB | "
            f"{item['direct_cross']['metrics']['deepest_interference_db']:.2f} dB |"
        )

    lines.extend(
        [
            "",
            "## Candidate Controls",
            "",
            "Delays below are resulting clean-branch delays, including the current 100-sample direct and 115-sample cross values.",
            "",
            "| Model | Direct paths (`LL`, `RR`) | Cross paths (`LR`, `RL`) |",
            "| --- | --- | --- |",
            f"| Current blend | {control_text(current['controls']['direct'], 'direct')} | {control_text(current['controls']['cross'], 'cross')} |",
            f"| Shared adjustment | {control_text(shared['controls']['direct'], 'direct')} | {control_text(shared['controls']['cross'], 'cross')} |",
            f"| Separate direct/cross | {control_text(separate['controls']['direct'], 'direct')} | {control_text(separate['controls']['cross'], 'cross')} |",
            "",
            f"## Best {summary['search']['low_bass_rms_tolerance_db']:.1f} dB-Constrained Direct/Cross Candidate",
            "",
            "| Path | Deepest interference | Frequency | Clean/convolved there | Phase there | Low-bass RMS change |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in PATHS:
        item = separate["paths"][label]
        lines.append(
            f"| `{label}` | {item['deepest_interference_db']:.2f} dB | "
            f"{item['deepest_interference_frequency_hz']:.1f} Hz | "
            f"{item['clean_to_convolved_at_deepest_db']:.2f} dB | "
            f"{item['phase_at_deepest_degrees']:.1f}° | "
            f"{item['low_bass_rms_change_db']:.2f} dB |"
        )

    best = separate if separate["metrics"]["deepest_interference_db"] >= shared["metrics"]["deepest_interference_db"] else shared
    best_name = "separate direct/cross" if best is separate else "shared"
    acceptance = best["metrics"]["deepest_interference_db"] >= -3.0
    first_passing = next(
        (
            item
            for item in tradeoffs
            if max(
                item["shared"]["metrics"]["deepest_interference_db"],
                item["direct_cross"]["metrics"]["deepest_interference_db"],
            )
            >= -3.0
        ),
        None,
    )
    complexity_gain = (
        separate["metrics"]["deepest_interference_db"]
        - shared["metrics"]["deepest_interference_db"]
    )
    typical_change = (
        separate["metrics"]["tenth_percentile_interference_db"]
        - shared["metrics"]["tenth_percentile_interference_db"]
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- The strongest tested model is the {best_name} candidate, improving worst-case interference from {current['metrics']['deepest_interference_db']:.2f} to {best['metrics']['deepest_interference_db']:.2f} dB.",
            f"- This {'meets' if acceptance else 'does not yet meet'} the provisional no-cancellation-beyond-3-dB criterion in the 50–200 Hz transition band.",
            f"- Separate direct/cross controls improve the constrained worst case by only {complexity_gain:.2f} dB versus the shared model, while changing the 10th-percentile result by {typical_change:.2f} dB. That marginal result does not justify the added control complexity by itself.",
        ]
    )
    if first_passing is not None:
        passing = (
            first_passing["direct_cross"]
            if first_passing["direct_cross"]["metrics"]["deepest_interference_db"]
            >= first_passing["shared"]["metrics"]["deepest_interference_db"]
            else first_passing["shared"]
        )
        gains = [
            control["gain_adjustment_db"]
            for control in passing["controls"].values()
        ]
        lines.append(
            f"- The first tested point that passes −3 dB allows {first_passing['tolerance_db']:.1f} dB RMS of deep-bass change and uses {min(gains):+.2f} to {max(gains):+.2f} dB of clean-branch gain. It improves the interference ratio largely by making one branch dominate, not by creating a coherent crossover."
        )
    lines.extend(
        [
            "- No gain/polarity/delay-only candidate is recommended from this pass. The next experiment should use complementary filtering or spectral replacement to reduce the overlap itself.",
            "",
            "## Plots",
            "",
            "- [Worst-path interference comparison](interference-comparison.svg)",
            "- [Best constrained output change by path](best-constrained-output-change.svg)",
            "- [Deep-bass preservation tradeoff](preservation-tradeoff.svg)",
            "",
            "Machine-readable controls, metrics, and search bounds are stored in [`summary.json`](summary.json).",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_results(output_dir, frequencies, configurations, tradeoffs):
    interference_series = []
    for name in ("current", "shared", "direct_cross"):
        envelope = np.min(
            np.vstack(
                [configurations[name]["paths"][label]["interference_db"] for label in PATHS]
            ),
            axis=0,
        )
        interference_series.append(
            (name.replace("_", "/"), frequencies, envelope, PLOT_COLORS[name])
        )
    write_svg_plot(
        output_dir / "interference-comparison.svg",
        "Worst-Path Vector-Sum Interference",
        interference_series,
        "Frequency (Hz)",
        "Sum / scalar magnitude sum (dB)",
        float(frequencies[0]),
        float(frequencies[-1]),
        -15.0,
        0.0,
        FREQUENCY_TICKS,
        x_scale="log",
    )

    best_constrained = configurations["direct_cross"]
    output_series = [
        (
            label,
            frequencies,
            best_constrained["paths"][label]["output_change_db"],
            COLORS[label],
        )
        for label in PATHS
    ]
    write_svg_plot(
        output_dir / "best-constrained-output-change.svg",
        "Best Constrained Direct/Cross Output Change vs Current",
        output_series,
        "Frequency (Hz)",
        "Candidate / current output (dB)",
        float(frequencies[0]),
        float(frequencies[-1]),
        -15.0,
        15.0,
        FREQUENCY_TICKS,
        x_scale="log",
    )

    tolerances = np.array(
        [item["tolerance_db"] for item in tradeoffs], dtype=np.float64
    )
    tradeoff_series = [
        (
            "shared",
            tolerances,
            np.array(
                [
                    item["shared"]["metrics"]["deepest_interference_db"]
                    for item in tradeoffs
                ]
            ),
            PLOT_COLORS["shared"],
        ),
        (
            "direct/cross",
            tolerances,
            np.array(
                [
                    item["direct_cross"]["metrics"]["deepest_interference_db"]
                    for item in tradeoffs
                ]
            ),
            PLOT_COLORS["direct_cross"],
        ),
    ]
    write_svg_plot(
        output_dir / "preservation-tradeoff.svg",
        "Deep-Bass Preservation vs Worst Interference",
        tradeoff_series,
        "Allowed 25–70 Hz RMS change (dB)",
        "Deepest interference (dB)",
        float(tolerances[0]),
        float(tolerances[-1]),
        -10.0,
        0.0,
        [float(value) for value in tolerances],
    )


def parse_args():
    repo_root = Path(__file__).resolve().parents[2]
    measurement_root = repo_root / "measurements" / "bass-branches"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=measurement_root / "raw")
    parser.add_argument("--output-dir", type=Path, default=measurement_root / "optimization")
    parser.add_argument("--low-frequency", type=float, default=20.0)
    parser.add_argument("--high-frequency", type=float, default=300.0)
    parser.add_argument("--transition-low", type=float, default=50.0)
    parser.add_argument("--transition-high", type=float, default=200.0)
    parser.add_argument("--low-bass-low", type=float, default=25.0)
    parser.add_argument("--low-bass-high", type=float, default=70.0)
    parser.add_argument("--low-bass-rms-tolerance", type=float, default=1.0)
    parser.add_argument("--minimum-delay-adjustment", type=float, default=-100.0)
    parser.add_argument("--maximum-delay-adjustment", type=float, default=150.0)
    parser.add_argument("--delay-step", type=float, default=1.0)
    parser.add_argument("--minimum-gain-adjustment", type=float, default=-12.0)
    parser.add_argument("--maximum-gain-adjustment", type=float, default=6.0)
    parser.add_argument("--gain-step", type=float, default=0.25)
    parser.add_argument("--smoothing-fraction", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=512)
    return parser.parse_args()


def main():
    args = parse_args()
    if not (
        0 < args.low_frequency
        <= args.low_bass_low
        < args.low_bass_high
        <= args.transition_high
        <= args.high_frequency
    ):
        raise SystemExit("Frequency bounds are inconsistent")
    if not (
        args.low_frequency
        < args.transition_low
        < args.transition_high
        <= args.high_frequency
    ):
        raise SystemExit("Transition bounds are inconsistent")
    if args.minimum_delay_adjustment < -min(CURRENT_DELAY_SAMPLES.values()):
        raise SystemExit("The delay search would create a negative clean-branch delay")
    if min(
        args.delay_step,
        args.gain_step,
        args.low_bass_rms_tolerance,
        args.smoothing_fraction,
        args.batch_size,
    ) <= 0:
        raise SystemExit("Search steps, tolerance, smoothing, and batch size must be positive")

    input_root = args.input_root.resolve()
    output_dir = args.output_dir.resolve()
    captures, sample_rate, nfft, frequencies, spectra = load_spectra(
        input_root, args.low_frequency, args.high_frequency
    )
    starts, stops = smoothing_windows(frequencies, args.smoothing_fraction)
    transition = (frequencies >= args.transition_low) & (
        frequencies <= args.transition_high
    )
    low_bass = (frequencies >= args.low_bass_low) & (
        frequencies <= args.low_bass_high
    )
    grid = candidate_grid(args)

    shared_evaluation = evaluate_grid(
        tuple(PATHS),
        grid,
        frequencies,
        spectra,
        sample_rate,
        starts,
        stops,
        transition,
        low_bass,
        args.batch_size,
    )
    shared_candidate = select_candidate(
        grid, shared_evaluation, args.low_bass_rms_tolerance
    )
    group_evaluations = {}
    for group, labels in GROUPS.items():
        group_evaluations[group] = evaluate_grid(
            labels,
            grid,
            frequencies,
            spectra,
            sample_rate,
            starts,
            stops,
            transition,
            low_bass,
            args.batch_size,
        )
    group_candidates = {
        group: select_candidate(
            grid, evaluation, args.low_bass_rms_tolerance
        )
        for group, evaluation in group_evaluations.items()
    }

    current_controls = {
        group: {
            "delay_adjustment_samples": 0.0,
            "gain_adjustment_db": 0.0,
            "polarity": 1,
        }
        for group in GROUPS
    }
    shared_controls = {
        group: controls_from_candidate(shared_candidate)
        for group in GROUPS
    }
    separate_controls = {
        group: controls_from_candidate(candidate)
        for group, candidate in group_candidates.items()
    }
    configurations = {
        "current": evaluate_configuration(
            current_controls,
            frequencies,
            spectra,
            sample_rate,
            starts,
            stops,
            transition,
            low_bass,
        ),
        "shared": evaluate_configuration(
            shared_controls,
            frequencies,
            spectra,
            sample_rate,
            starts,
            stops,
            transition,
            low_bass,
        ),
        "direct_cross": evaluate_configuration(
            separate_controls,
            frequencies,
            spectra,
            sample_rate,
            starts,
            stops,
            transition,
            low_bass,
        ),
    }

    tradeoff_tolerances = sorted(
        set(TRADEOFF_TOLERANCES_DB + (float(args.low_bass_rms_tolerance),))
    )
    preservation_tradeoff = []
    for tolerance in tradeoff_tolerances:
        tradeoff_shared_candidate = select_candidate(
            grid, shared_evaluation, tolerance
        )
        tradeoff_shared_controls = {
            group: controls_from_candidate(tradeoff_shared_candidate)
            for group in GROUPS
        }
        tradeoff_group_candidates = {
            group: select_candidate(grid, evaluation, tolerance)
            for group, evaluation in group_evaluations.items()
        }
        tradeoff_separate_controls = {
            group: controls_from_candidate(candidate)
            for group, candidate in tradeoff_group_candidates.items()
        }
        tradeoff_shared = evaluate_configuration(
            tradeoff_shared_controls,
            frequencies,
            spectra,
            sample_rate,
            starts,
            stops,
            transition,
            low_bass,
        )
        tradeoff_separate = evaluate_configuration(
            tradeoff_separate_controls,
            frequencies,
            spectra,
            sample_rate,
            starts,
            stops,
            transition,
            low_bass,
        )
        preservation_tradeoff.append(
            {
                "tolerance_db": tolerance,
                "shared": serializable_configuration(tradeoff_shared),
                "direct_cross": serializable_configuration(tradeoff_separate),
            }
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "sample_rate_hz": sample_rate,
        "nfft": nfft,
        "capture_commits": {
            name: capture["header"].get("commit", "unknown")
            for name, capture in captures.items()
        },
        "search": {
            "frequency_band_hz": [args.low_frequency, args.high_frequency],
            "transition_band_hz": [args.transition_low, args.transition_high],
            "low_bass_preservation_band_hz": [args.low_bass_low, args.low_bass_high],
            "low_bass_rms_tolerance_db": args.low_bass_rms_tolerance,
            "delay_adjustment_samples": [
                args.minimum_delay_adjustment,
                args.maximum_delay_adjustment,
                args.delay_step,
            ],
            "gain_adjustment_db": [
                args.minimum_gain_adjustment,
                args.maximum_gain_adjustment,
                args.gain_step,
            ],
            "polarities": [1, -1],
            "smoothing_fractional_octave": args.smoothing_fraction,
            "candidate_count_per_search": len(grid["delay_adjustment_samples"]),
            "current_delay_samples": CURRENT_DELAY_SAMPLES,
        },
        "configurations": {
            name: serializable_configuration(configuration)
            for name, configuration in configurations.items()
        },
        "preservation_tradeoff": preservation_tradeoff,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    write_report(output_dir / "report.md", summary)
    plot_results(output_dir, frequencies, configurations, preservation_tradeoff)

    print(f"Wrote bass alignment optimization to {output_dir}")
    for name in ("current", "shared", "direct_cross"):
        metrics = summary["configurations"][name]["metrics"]
        print(
            f"{name}: deepest interference={metrics['deepest_interference_db']:.2f} dB; "
            f"max low-bass change={metrics['maximum_low_bass_rms_change_db']:.2f} dB"
        )


if __name__ == "__main__":
    main()
