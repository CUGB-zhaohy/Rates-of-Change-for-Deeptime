"""
Phase statistics for the RoC workflow.

This module uses consensus breakpoints from KDE analysis to divide the record
into RoC phases and calculate phase-level statistics.

Input:
    1. Wide-format RoC table:
        Age_kyr | Timescale_100 | Timescale_200 | ... | Timescale_1000

    2. KDE peak table:
        Consensus_breakpoint_kyr | Consensus_breakpoint_Ma | ...

Outputs:
    - phase boundary table
    - phase statistics table
    - phase ranking and class labels
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .lri import identify_timescale_columns, parse_timescale_from_column


DEFAULT_PHASE_CLASS_LABELS = [
    "Maximum",
    "High",
    "Moderate",
    "Transitional",
    "Reduced",
    "Low",
    "Minimal",
]


def get_phase_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get phase analysis settings from config.
    """
    phase_config = config.get("phase", {})

    return {
        "age_min_kyr": float(phase_config.get("age_min_kyr", 0.0)),
        "age_max_kyr": float(phase_config.get("age_max_kyr", 67100.0)),
        "breakpoint_col": str(
            phase_config.get("breakpoint_col", "Consensus_breakpoint_kyr")
        ),
        "sort_breakpoints": bool(phase_config.get("sort_breakpoints", True)),
        "min_phase_width_kyr": float(phase_config.get("min_phase_width_kyr", 0.0)),
        "classification_labels": phase_config.get(
            "classification_labels",
            DEFAULT_PHASE_CLASS_LABELS,
        ),
    }


def extract_phase_boundaries_from_kde(
    kde_peak_table: pd.DataFrame,
    config: dict[str, Any],
) -> list[float]:
    """
    Extract consensus breakpoint ages from the KDE peak table.

    Parameters
    ----------
    kde_peak_table : pandas.DataFrame
        KDE peak table.
    config : dict
        Configuration dictionary.

    Returns
    -------
    list of float
        Breakpoint ages in kyr.
    """
    settings = get_phase_settings(config)
    breakpoint_col = settings["breakpoint_col"]

    if kde_peak_table is None or kde_peak_table.empty:
        return []

    if breakpoint_col not in kde_peak_table.columns:
        raise KeyError(f"Missing KDE breakpoint column: {breakpoint_col}")

    boundaries = pd.to_numeric(
        kde_peak_table[breakpoint_col],
        errors="coerce",
    ).dropna()

    boundaries = boundaries[
        (boundaries > settings["age_min_kyr"])
        & (boundaries < settings["age_max_kyr"])
    ]

    boundary_values = [float(value) for value in boundaries.to_numpy(dtype=float)]

    if settings["sort_breakpoints"]:
        boundary_values = sorted(boundary_values)

    unique_boundaries = []

    for value in boundary_values:
        if not unique_boundaries or abs(value - unique_boundaries[-1]) > 1e-9:
            unique_boundaries.append(value)

    return unique_boundaries


def build_phase_intervals(
    breakpoints_kyr: list[float],
    age_min_kyr: float,
    age_max_kyr: float,
    min_phase_width_kyr: float = 0.0,
) -> pd.DataFrame:
    """
    Build phase intervals from breakpoint ages.

    Ages are treated as increasing from young to old.

    Example:
        age_min = 0
        breakpoints = [3630, 13270, 24340]
        age_max = 67100

    Phases:
        Phase 1: 0-3630 kyr
        Phase 2: 3630-13270 kyr
        Phase 3: 13270-24340 kyr
        Phase 4: 24340-67100 kyr
    """
    boundaries = [
        float(value)
        for value in breakpoints_kyr
        if np.isfinite(value) and age_min_kyr < value < age_max_kyr
    ]

    boundaries = sorted(boundaries)
    edges = [float(age_min_kyr)] + boundaries + [float(age_max_kyr)]

    rows = []

    for i in range(len(edges) - 1):
        start_kyr = edges[i]
        end_kyr = edges[i + 1]
        width_kyr = end_kyr - start_kyr

        if width_kyr < min_phase_width_kyr:
            continue

        phase_id = i + 1

        rows.append(
            {
                "Phase_id": phase_id,
                "Phase_name": f"Phase_{phase_id}",
                "Start_kyr": start_kyr,
                "End_kyr": end_kyr,
                "Start_Ma": start_kyr / 1000.0,
                "End_Ma": end_kyr / 1000.0,
                "Duration_kyr": width_kyr,
                "Duration_Ma": width_kyr / 1000.0,
                "Interval_label": f"{start_kyr / 1000.0:.2f}-{end_kyr / 1000.0:.2f} Ma",
            }
        )

    return pd.DataFrame(rows)


def safe_std(values) -> float:
    """
    Calculate sample standard deviation safely.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size < 2:
        return np.nan

    return float(np.std(arr, ddof=1))


def calculate_phase_statistics_for_one_table(
    table: pd.DataFrame,
    method_name: str,
    data_type: str,
    phase_intervals: pd.DataFrame,
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> pd.DataFrame:
    """
    Calculate phase statistics for one method table.
    """
    if table is None or table.empty:
        return pd.DataFrame()

    if age_col not in table.columns:
        raise KeyError(f"Missing age column: {age_col}")

    timescale_columns = identify_timescale_columns(
        table=table,
        column_prefix=column_prefix,
    )

    if not timescale_columns:
        raise ValueError("No timescale columns were found for phase statistics.")

    local_table = table.copy()
    local_table[age_col] = pd.to_numeric(local_table[age_col], errors="coerce")
    local_table = local_table.dropna(subset=[age_col])
    local_table = local_table.sort_values(age_col, ascending=True).reset_index(drop=True)

    rows = []

    for column in timescale_columns:
        timescale = parse_timescale_from_column(
            column_name=column,
            column_prefix=column_prefix,
        )

        if timescale is None:
            continue

        values_all = pd.to_numeric(local_table[column], errors="coerce")

        for _, phase in phase_intervals.iterrows():
            start_kyr = float(phase["Start_kyr"])
            end_kyr = float(phase["End_kyr"])

            if phase["Phase_id"] == phase_intervals["Phase_id"].max():
                mask = (
                    (local_table[age_col] >= start_kyr)
                    & (local_table[age_col] <= end_kyr)
                )
            else:
                mask = (
                    (local_table[age_col] >= start_kyr)
                    & (local_table[age_col] < end_kyr)
                )

            values = values_all[mask].to_numpy(dtype=float)
            values = values[np.isfinite(values)]

            n = int(values.size)

            if n == 0:
                mean_value = np.nan
                median_value = np.nan
                std_value = np.nan
                se_value = np.nan
                ci95_low = np.nan
                ci95_high = np.nan
                min_value = np.nan
                max_value = np.nan
            else:
                mean_value = float(np.mean(values))
                median_value = float(np.median(values))
                std_value = safe_std(values)
                se_value = std_value / np.sqrt(n) if n > 1 and np.isfinite(std_value) else np.nan
                ci95_low = mean_value - 1.96 * se_value if np.isfinite(se_value) else np.nan
                ci95_high = mean_value + 1.96 * se_value if np.isfinite(se_value) else np.nan
                min_value = float(np.min(values))
                max_value = float(np.max(values))

            rows.append(
                {
                    "Method": method_name,
                    "Data_type": data_type,
                    "Timescale_kyr": float(timescale),
                    "Column": column,
                    "Phase_id": int(phase["Phase_id"]),
                    "Phase_name": phase["Phase_name"],
                    "Interval_label": phase["Interval_label"],
                    "Start_kyr": float(phase["Start_kyr"]),
                    "End_kyr": float(phase["End_kyr"]),
                    "Start_Ma": float(phase["Start_Ma"]),
                    "End_Ma": float(phase["End_Ma"]),
                    "Duration_kyr": float(phase["Duration_kyr"]),
                    "N_points": n,
                    "Mean": mean_value,
                    "Median": median_value,
                    "Std": std_value,
                    "SE": se_value,
                    "CI95_low": ci95_low,
                    "CI95_high": ci95_high,
                    "Min": min_value,
                    "Max": max_value,
                }
            )

    result = pd.DataFrame(rows)

    if not result.empty:
        result = result.sort_values(
            ["Method", "Data_type", "Timescale_kyr", "Phase_id"],
            ascending=True,
        ).reset_index(drop=True)

    return result


def assign_phase_classes(
    phase_statistics: pd.DataFrame,
    labels: list[str] | None = None,
) -> pd.DataFrame:
    """
    Assign phase classes based on mean RoC within each method and time scale.

    The highest mean receives the first label, for example "Maximum".
    The lowest mean receives the last label, for example "Minimal".
    """
    if labels is None:
        labels = DEFAULT_PHASE_CLASS_LABELS

    if phase_statistics is None or phase_statistics.empty:
        return pd.DataFrame()

    result = phase_statistics.copy()
    result["Phase_rank_within_method_timescale"] = np.nan
    result["Phase_class"] = ""

    group_cols = ["Method", "Data_type", "Timescale_kyr"]

    for _, group in result.groupby(group_cols, dropna=False):
        valid = group[np.isfinite(group["Mean"])].copy()

        if valid.empty:
            continue

        valid = valid.sort_values("Mean", ascending=False)

        n_valid = len(valid)

        for rank_index, row_index in enumerate(valid.index, start=1):
            if n_valid == 1:
                label_index = 0
            elif n_valid <= len(labels):
                label_index = rank_index - 1
            else:
                label_index = int(round((rank_index - 1) * (len(labels) - 1) / (n_valid - 1)))

            label_index = max(0, min(label_index, len(labels) - 1))

            result.loc[row_index, "Phase_rank_within_method_timescale"] = rank_index
            result.loc[row_index, "Phase_class"] = labels[label_index]

    return result


def calculate_phase_statistics_for_all_methods(
    rate_tables: dict[str, pd.DataFrame],
    phase_intervals: pd.DataFrame,
    data_type: str,
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> pd.DataFrame:
    """
    Calculate phase statistics for all method tables.
    """
    tables = []

    for method_name, table in rate_tables.items():
        stats_table = calculate_phase_statistics_for_one_table(
            table=table,
            method_name=method_name,
            data_type=data_type,
            phase_intervals=phase_intervals,
            age_col=age_col,
            column_prefix=column_prefix,
        )

        if not stats_table.empty:
            tables.append(stats_table)

    if not tables:
        return pd.DataFrame()

    return pd.concat(tables, ignore_index=True)


def summarize_phase_classes(phase_statistics: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize phase classes across time scales within each method.

    Because each method has its own KDE-derived breakpoint set, Method must be
    included in the grouping columns.
    """
    if phase_statistics is None or phase_statistics.empty:
        return pd.DataFrame()

    group_cols = [
        "Method",
        "Data_type",
        "Phase_id",
        "Phase_name",
        "Interval_label",
        "Start_Ma",
        "End_Ma",
        "Phase_class",
    ]

    summary = (
        phase_statistics
        .groupby(group_cols, dropna=False)
        .agg(
            N_records=("Mean", "count"),
            Mean_of_phase_means=("Mean", "mean"),
            Median_of_phase_means=("Mean", "median"),
            Min_of_phase_means=("Mean", "min"),
            Max_of_phase_means=("Mean", "max"),
        )
        .reset_index()
    )

    summary = summary.sort_values(
        ["Method", "Data_type", "Phase_id", "Phase_class"],
        ascending=True,
    ).reset_index(drop=True)

    return summary


def run_phase_analysis(
    rate_tables: dict[str, pd.DataFrame],
    kde_peak_table: pd.DataFrame,
    config: dict[str, Any],
    data_type: str = "time_scale_corrected_relative",
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> dict[str, pd.DataFrame]:
    """
    Run phase analysis using method-specific KDE consensus breakpoints.

    Important:
    Each method uses its own KDE-derived breakpoint set.

    Workflow:
        IBR corrected RoC + IBR KDE peaks -> IBR phase statistics
        TS corrected RoC  + TS KDE peaks  -> TS phase statistics
        IQR corrected RoC + IQR KDE peaks -> IQR phase statistics
    """
    settings = get_phase_settings(config)

    all_phase_intervals = []
    all_phase_statistics = []

    for method_name, method_table in rate_tables.items():
        if method_table is None or method_table.empty:
            continue

        if kde_peak_table is None or kde_peak_table.empty:
            method_kde_peaks = pd.DataFrame()
        elif "Method" in kde_peak_table.columns:
            method_kde_peaks = kde_peak_table[
                kde_peak_table["Method"].astype(str) == str(method_name)
            ].copy()
        else:
            method_kde_peaks = kde_peak_table.copy()

        breakpoints = extract_phase_boundaries_from_kde(
            kde_peak_table=method_kde_peaks,
            config=config,
        )

        phase_intervals = build_phase_intervals(
            breakpoints_kyr=breakpoints,
            age_min_kyr=settings["age_min_kyr"],
            age_max_kyr=settings["age_max_kyr"],
            min_phase_width_kyr=settings["min_phase_width_kyr"],
        )

        if phase_intervals.empty:
            continue

        phase_intervals = phase_intervals.copy()
        phase_intervals.insert(0, "Method", method_name)
        phase_intervals.insert(1, "Data_type", data_type)

        all_phase_intervals.append(phase_intervals)

        phase_statistics = calculate_phase_statistics_for_one_table(
            table=method_table,
            method_name=method_name,
            data_type=data_type,
            phase_intervals=phase_intervals,
            age_col=age_col,
            column_prefix=column_prefix,
        )

        if phase_statistics.empty:
            continue

        phase_statistics = assign_phase_classes(
            phase_statistics=phase_statistics,
            labels=settings["classification_labels"],
        )

        all_phase_statistics.append(phase_statistics)

    if all_phase_intervals:
        phase_boundaries = pd.concat(all_phase_intervals, ignore_index=True)
    else:
        phase_boundaries = pd.DataFrame()

    if all_phase_statistics:
        phase_statistics = pd.concat(all_phase_statistics, ignore_index=True)
    else:
        phase_statistics = pd.DataFrame()

    phase_class_summary = summarize_phase_classes(
        phase_statistics=phase_statistics,
    )

    return {
        "phase_boundaries": phase_boundaries,
        "phase_statistics": phase_statistics,
        "phase_class_summary": phase_class_summary,
    }