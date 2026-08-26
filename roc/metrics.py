"""
Metrics for evaluating RoC time series.

This module calculates:
- nTV: mean absolute step-to-step variation
- Gini coefficient: inequality of RoC magnitudes

Input:
    Wide-format table:
        Age_kyr | Timescale_100 | Timescale_200 | ... | Timescale_1000
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .lri import identify_timescale_columns, parse_timescale_from_column


def calculate_ntv(values) -> float:
    """
    Calculate nTV as mean absolute step-to-step variation.

    Formula:
        nTV = sum(|x[i+1] - x[i]|) / (N - 1)

    Parameters
    ----------
    values : array-like
        Input time series values.

    Returns
    -------
    float
        nTV value.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size < 2:
        return np.nan

    return float(np.sum(np.abs(np.diff(arr))) / (arr.size - 1))


def calculate_gini(values) -> float:
    """
    Calculate the Gini coefficient of a non-negative RoC series.

    Parameters
    ----------
    values : array-like
        Input values.

    Returns
    -------
    float
        Gini coefficient.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]

    n = arr.size

    if n == 0:
        return np.nan

    mean_abs = np.mean(np.abs(arr))

    if mean_abs == 0:
        return 0.0

    diff_matrix = np.abs(arr[:, None] - arr[None, :])
    gini = diff_matrix.sum() / (2.0 * (n ** 2) * mean_abs)

    return float(gini)


def check_age_spacing(age_values) -> tuple[float, float]:
    """
    Check whether the age spacing is approximately uniform.

    Returns
    -------
    tuple
        (median_spacing, max_relative_error)
    """
    arr = np.asarray(age_values, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size < 2:
        return np.nan, np.nan

    diffs = np.diff(arr)
    median_dt = np.median(diffs)

    if median_dt == 0 or not np.isfinite(median_dt):
        return np.nan, np.nan

    relative_error = np.max(np.abs(diffs - median_dt) / np.abs(median_dt))

    return float(median_dt), float(relative_error)


def calculate_metrics_for_merged_table(
    merged_table: pd.DataFrame,
    method_name: str,
    data_type: str = "raw",
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
    age_tolerance_relative: float = 1e-3,
) -> pd.DataFrame:
    """
    Calculate nTV and Gini for all timescale columns in one merged table.

    Parameters
    ----------
    merged_table : pandas.DataFrame
        Wide-format merged RoC table.
    method_name : str
        Method name, such as IBR, TS, or IQR.
    data_type : str, default "raw"
        Data type label, such as raw or time_scale_corrected_relative.
    age_col : str, default "Age_kyr"
        Age column name.
    column_prefix : str, default "Timescale_"
        Prefix of timescale columns.
    age_tolerance_relative : float, default 1e-3
        Tolerance for age-spacing check.

    Returns
    -------
    pandas.DataFrame
        Metrics table.
    """
    if age_col not in merged_table.columns:
        raise KeyError(f"Missing age column: {age_col}")

    table = merged_table.copy()
    table[age_col] = pd.to_numeric(table[age_col], errors="coerce")
    table = table.dropna(subset=[age_col])
    table = table.sort_values(age_col, ascending=True).reset_index(drop=True)

    median_dt, age_spacing_relative_error = check_age_spacing(
        table[age_col].to_numpy(dtype=float)
    )

    age_spacing_warning = False
    if np.isfinite(age_spacing_relative_error):
        age_spacing_warning = bool(age_spacing_relative_error > age_tolerance_relative)

    timescale_columns = identify_timescale_columns(
        table=table,
        column_prefix=column_prefix,
    )

    if not timescale_columns:
        raise ValueError("No timescale columns were found for metric calculation.")

    rows = []

    for column in timescale_columns:
        timescale = parse_timescale_from_column(
            column_name=column,
            column_prefix=column_prefix,
        )

        if timescale is None:
            continue

        values = pd.to_numeric(table[column], errors="coerce").to_numpy(dtype=float)
        values = values[np.isfinite(values)]

        ntv = calculate_ntv(values)
        gini = calculate_gini(values)

        rows.append(
            {
                "Method": method_name,
                "Data_type": data_type,
                "Timescale_kyr": float(timescale),
                "Column": column,
                "nTV": ntv,
                "Gini": gini,
                "N_points": int(values.size),
                "Median_age_spacing_kyr": median_dt,
                "Age_spacing_relative_error": age_spacing_relative_error,
                "Age_spacing_warning": age_spacing_warning,
            }
        )

    result = (
        pd.DataFrame(rows)
        .sort_values(["Method", "Data_type", "Timescale_kyr"], ascending=True)
        .reset_index(drop=True)
    )

    return result


def calculate_metrics_for_all_methods(
    merged_tables_by_method: dict[str, pd.DataFrame],
    data_type: str = "raw",
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
    age_tolerance_relative: float = 1e-3,
) -> pd.DataFrame:
    """
    Calculate metrics for all methods.

    Parameters
    ----------
    merged_tables_by_method : dict
        Dictionary of merged tables by method.
    data_type : str, default "raw"
        Data type label.

    Returns
    -------
    pandas.DataFrame
        Combined metrics table.
    """
    tables = []

    for method_name, merged_table in merged_tables_by_method.items():
        metrics_table = calculate_metrics_for_merged_table(
            merged_table=merged_table,
            method_name=method_name,
            data_type=data_type,
            age_col=age_col,
            column_prefix=column_prefix,
            age_tolerance_relative=age_tolerance_relative,
        )

        tables.append(metrics_table)

    if not tables:
        return pd.DataFrame(
            columns=[
                "Method",
                "Data_type",
                "Timescale_kyr",
                "Column",
                "nTV",
                "Gini",
                "N_points",
            ]
        )

    return pd.concat(tables, ignore_index=True)


def combine_metric_tables(*metric_tables: pd.DataFrame) -> pd.DataFrame:
    """
    Combine multiple metric tables.
    """
    valid_tables = [
        table for table in metric_tables
        if table is not None and not table.empty
    ]

    if not valid_tables:
        return pd.DataFrame()

    combined = pd.concat(valid_tables, ignore_index=True)

    sort_columns = [
        column for column in ["Data_type", "Method", "Timescale_kyr"]
        if column in combined.columns
    ]

    if sort_columns:
        combined = combined.sort_values(sort_columns).reset_index(drop=True)

    return combined


def get_metrics_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get metric settings from config.
    """
    metrics_config = config.get("metrics", {})

    return {
        "age_tolerance_relative": float(
            metrics_config.get("age_tolerance_relative", 1e-3)
        ),
    }


def run_metrics_analysis(
    merged_rate_tables: dict[str, pd.DataFrame],
    corrected_rate_tables: dict[str, pd.DataFrame] | None,
    config: dict[str, Any],
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> dict[str, pd.DataFrame]:
    """
    Run metric analysis for raw and corrected RoC tables.

    Returns
    -------
    dict
        {
            "raw": raw metric table,
            "time_scale_corrected_relative": corrected metric table,
            "combined": combined metric table
        }
    """
    settings = get_metrics_settings(config)

    raw_metrics = calculate_metrics_for_all_methods(
        merged_tables_by_method=merged_rate_tables,
        data_type="raw",
        age_col=age_col,
        column_prefix=column_prefix,
        age_tolerance_relative=settings["age_tolerance_relative"],
    )

    corrected_metrics = pd.DataFrame()

    if corrected_rate_tables:
        corrected_metrics = calculate_metrics_for_all_methods(
            merged_tables_by_method=corrected_rate_tables,
            data_type="time_scale_corrected_relative",
            age_col=age_col,
            column_prefix=column_prefix,
            age_tolerance_relative=settings["age_tolerance_relative"],
        )

    combined = combine_metric_tables(raw_metrics, corrected_metrics)

    return {
        "raw": raw_metrics,
        "time_scale_corrected_relative": corrected_metrics,
        "combined": combined,
    }