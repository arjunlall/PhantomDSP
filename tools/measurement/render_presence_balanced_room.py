#!/usr/bin/env python3
"""Render candidate M with L's treble treatment and a gentler presence-band onset."""

import copy
import json

import numpy as np

from analyze_baseline import finite_float, sha256, write_svg_plot
from render_synthetic_direct import REPOSITORY, load_stereo_paths
import render_timbre_balanced_room as base


L_OUTPUT_DIRECTORY = base.OUTPUT_DIRECTORY
L_OUTPUT_FILES = dict(base.OUTPUT_FILES)
L_FILES = {
    side: L_OUTPUT_DIRECTORY / filename
    for side, filename in L_OUTPUT_FILES.items()
}
K_FILES = base.K_FILES
SPEAKER_PATHS = base.SPEAKER_PATHS
OUTPUT_DIRECTORY = REPOSITORY / "Synthetic Reference Room" / "IRs" / "presence-balanced"
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "presence-balanced"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Presence Balanced Room Left Speaker.wav",
    "right": "Presence Balanced Room Right Speaker.wav",
}
DESIGN = copy.deepcopy(base.DESIGN)
DESIGN.update(
    {
        "candidate_label": "M",
        "candidate_display_name": "Presence-Balanced Room",
        "plot_prefix": "presence-balanced",
        "status": "opt-in articulation-preserving timbre candidate",
        "base_candidate": "L treatment-aware timbre candidate",
        "correction_support_hz": [5500.0, 14000.0],
        "correction_full_strength_hz": [7500.0, 12000.0],
        "listening_hypothesis": (
            "preserve more 5.5-7.5 kHz reflected articulation while retaining "
            "L's 7.5-12 kHz reduction of K's broad sharpness"
        ),
    }
)

BANDS = (
    (4500.0, 5500.0, "4.5-5.5 kHz"),
    (5500.0, 6500.0, "5.5-6.5 kHz"),
    (6500.0, 7500.0, "6.5-7.5 kHz"),
    (7500.0, 9000.0, "7.5-9 kHz"),
    (9000.0, 11000.0, "9-11 kHz"),
    (11000.0, 14000.0, "11-14 kHz"),
)


def candidate_files(directory, filenames):
    return {side: directory / filename for side, filename in filenames.items()}


def response_deltas(frequencies, candidate, reference):
    return {
        speaker: {
            label: base.response_band_delta(
                frequencies,
                candidate[speaker],
                reference[speaker],
                low,
                high,
            )
            for low, high, label in BANDS
        }
        for speaker in SPEAKER_PATHS
    }


def augment_analysis(args):
    m_files = candidate_files(args.ir_output, OUTPUT_FILES)
    m_paths, sample_rate, _ = load_stereo_paths(m_files)
    l_paths, l_rate, _ = load_stereo_paths(L_FILES)
    k_paths, k_rate, _ = load_stereo_paths(K_FILES)
    if len({sample_rate, l_rate, k_rate, DESIGN["sample_rate_hz"]}) != 1:
        raise ValueError("K, L, and M sample rates differ")

    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    spectra = {
        name: {path: np.fft.rfft(values, nfft) for path, values in paths.items()}
        for name, paths in (("K", k_paths), ("L", l_paths), ("M", m_paths))
    }
    responses = {
        name: {
            speaker: base.speaker_response(path_spectra, paths, frequencies)
            for speaker, paths in SPEAKER_PATHS.items()
        }
        for name, path_spectra in spectra.items()
    }
    m_minus_l = response_deltas(frequencies, responses["M"], responses["L"])
    m_minus_k = response_deltas(frequencies, responses["M"], responses["K"])

    selected = (frequencies >= 4500.0) & (frequencies <= 12000.0)
    plot_name = "k-l-m-presence-region.svg"
    write_svg_plot(
        args.analysis_output / plot_name,
        "Candidates K, L, and M: Presence-Region Change from K",
        [
            (
                f"{candidate} {speaker}",
                frequencies[selected],
                (responses[candidate][speaker] - responses["K"][speaker])[selected],
                color,
            )
            for candidate, speaker, color in (
                ("L", "left", "#93c5fd"),
                ("M", "left", "#2563eb"),
                ("L", "right", "#86efac"),
                ("M", "right", "#059669"),
            )
        ],
        "Frequency (Hz)",
        "Candidate minus K (dB)",
        4500.0,
        12000.0,
        -6.0,
        1.0,
        [4500, 5500, 6500, 7500, 9000, 11000, 12000],
        x_scale="log",
    )

    summary_path = args.analysis_output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["candidate_l_files"] = {
        side: {
            "path": base.display_path(path),
            "sha256": sha256(path),
        }
        for side, path in L_FILES.items()
    }
    summary["response_delta_presence_minus_k"] = summary.pop(
        "response_delta_balanced_minus_k"
    )
    summary["response_delta_presence_minus_l"] = m_minus_l
    summary["diagnostic_band_delta_presence_minus_k"] = m_minus_k
    summary["plots"].append(plot_name)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report_path = args.analysis_output / "report.md"
    report = report_path.read_text(encoding="utf-8").rstrip()
    lines = [
        report,
        "",
        "## Controlled K/L/M Diagnostic",
        "",
        "Informal listening preferred L's overall naturalness to K but found that L reduced some string-pick articulation relative to physical monitor playback. M changes only the low-frequency entrance of L's microcluster attenuation: it begins at 5.5 kHz and reaches full L strength at 7.5 kHz. Above 7.5 kHz, the requested treatment curve remains L's.",
        "",
        "| Band | M minus L, left | M minus L, right | M minus K, left | M minus K, right |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for _, _, label in BANDS:
        lines.append(
            f"| {label} | {m_minus_l['left'][label]['mean_db']:+.2f} dB | "
            f"{m_minus_l['right'][label]['mean_db']:+.2f} dB | "
            f"{m_minus_k['left'][label]['mean_db']:+.2f} dB | "
            f"{m_minus_k['right'][label]['mean_db']:+.2f} dB |"
        )
    lines.extend(
        [
            "",
            f"Modeled maximum correlated gain remains {summary['modeled_correlated_renderer_gain_db']:+.2f} dB.",
            "",
            f"- `{plot_name}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "presence_minus_l": {
                    speaker: {
                        label: finite_float(metrics["mean_db"], 6)
                        for label, metrics in m_minus_l[speaker].items()
                    }
                    for speaker in SPEAKER_PATHS
                },
                "presence_minus_k": {
                    speaker: {
                        label: finite_float(metrics["mean_db"], 6)
                        for label, metrics in m_minus_k[speaker].items()
                    }
                    for speaker in SPEAKER_PATHS
                },
            },
            indent=2,
        )
    )


def main():
    base.DESIGN = DESIGN
    base.OUTPUT_DIRECTORY = OUTPUT_DIRECTORY
    base.ANALYSIS_DIRECTORY = ANALYSIS_DIRECTORY
    base.OUTPUT_FILES = OUTPUT_FILES
    args = base.parse_args()
    base.main(args)
    augment_analysis(args)


if __name__ == "__main__":
    main()
