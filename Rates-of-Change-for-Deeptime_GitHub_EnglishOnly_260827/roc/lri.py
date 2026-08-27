"""
Log-Rate-Interval regression utilities.

This module calculates the relationship between RoC magnitude and analytical
time scale using log-log regression.

Input:
    Wide-format merged RoC table:
        Age_kyr | Timescale_100 | Timescale_200 | ... | Timescale_1000

Outputs:
    - flattened LRI point table
    - regression summary table
    - quantile regression point table
    - time-scale-corrected relative RoC table

Correction logic:
    Each analytical time scale has its own baseline RoC predicted by the
    LRI regression curve.

    log10(Baseline_RoC) = slope * log10(timescale) + intercept

    Corrected_RoC = Observed_RoC / Baseline_RoC

This is not a normalization to a fixed reference time scale.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def parse_timescale_from_column(
    column_name: str,
    column_prefix: str = "Timescale_",
) -> float | None:
    """
    Parse time scale from a column name.

    Examples
    --------
    Timescale_100 -> 100.0
    Timescale_12p5 -> 12.5
    """
    column_name = str(column_name)

    if not column_name.startswith(column_prefix):
        return None

    value_text = column_name.replace(column_prefix, "", 1)
    value_text = value_text.replace("kyr", "")
    value_text = value_text.replace("p", ".")

    try:
        return float(value_text)
    except ValueError:
        return None


def identify_timescale_columns(
    table: pd.DataFrame,
    column_prefix: str = "Timescale_",
) -> list[str]:
    """
    Identify and sort time-scale columns in a merged RoC table.
    """
    columns_with_timescale = []

    for column in table.columns:
        timescale = parse_timescale_from_column(
            column_name=column,
            column_prefix=column_prefix,
        )

        if timescale is not None:
            columns_with_timescale.append((timescale, column))

    columns_with_timescale = sorted(columns_with_timescale, key=lambda item: item[0])

    return [column for _, column in columns_with_timescale]


def fit_linear_regression(
    x,
    y,
) -> dict[str, float]:
    """
    Fit a simple linear regression y = slope * x + intercept.

    Parameters
    ----------
    x : array-like
        Predictor values.
    y : array-like
        Response values.

    Returns
    -------
    dict
        Regression parameters and diagnostics.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    valid_mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr = x_arr[valid_mask]
    y_arr = y_arr[valid_mask]

    if x_arr.size < 2:
        raise ValueError("At least two valid points are required for regression.")

    slope, intercept = np.polyfit(x_arr, y_arr, deg=1)
    prediction = slope * x_arr + intercept

    ss_res = np.sum((y_arr - prediction) ** 2)
    ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)

    if ss_tot == 0:
        r2 = 1.0 if ss_res == 0 else np.nan
    else:
        r2 = 1.0 - ss_res / ss_tot

    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": float(r2),
        "n": int(x_arr.size),
    }


def flatten_lri_data(
    merged_table: pd.DataFrame,
    method_name: str,
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> pd.DataFrame:
    """
    Flatten a merged multi-timescale RoC table for LRI regression.

    Parameters
    ----------
    merged_table : pandas.DataFrame
        Wide-format merged RoC table.
    method_name : str
        Method name, such as IBR, TS, or IQR.
    age_col : str, default "Age_kyr"
        Age column name.
    column_prefix : str, default "Timescale_"
        Prefix of time-scale columns.

    Returns
    -------
    pandas.DataFrame
        Flattened LRI point table.
    """
    if age_col not in merged_table.columns:
        raise KeyError(f"Missing age column: {age_col}")

    timescale_columns = identify_timescale_columns(
        table=merged_table,
        column_prefix=column_prefix,
    )

    if not timescale_columns:
        raise ValueError("No timescale columns were found for LRI regression.")

    rows = []

    for column in timescale_columns:
        timescale = parse_timescale_from_column(
            column_name=column,
            column_prefix=column_prefix,
        )

        if timescale is None or timescale <= 0:
            continue

        local = merged_table[[age_col, column]].copy()
        local[age_col] = pd.to_numeric(local[age_col], errors="coerce")
        local[column] = pd.to_numeric(local[column], errors="coerce")
        local = local.dropna(subset=[age_col, column])

        local = local[local[column] > 0]

        for _, row in local.iterrows():
            rows.append(
                {
                    "Method": method_name,
                    "Age_kyr": float(row[age_col]),
                    "Timescale_kyr": float(timescale),
                    "RoC": float(row[column]),
                    "Log10_timescale": float(np.log10(timescale)),
                    "Log10_RoC": float(np.log10(row[column])),
                }
            )

    flattened = pd.DataFrame(rows)

    if flattened.empty:
        raise ValueError(
            f"No positive RoC values are available for LRI regression: {method_name}"
        )

    return flattened


def calculate_quantile_series(
    flattened_table: pd.DataFrame,
    quantile_levels: list[float],
) -> pd.DataFrame:
    """
    Calculate quantile series of log10(RoC) at each time scale.
    """
    rows = []

    grouped = flattened_table.groupby(
        ["Timescale_kyr", "Log10_timescale"],
        as_index=False,
        sort=True,
    )

    for _, group in grouped:
        timescale = float(group["Timescale_kyr"].iloc[0])
        log_timescale = float(group["Log10_timescale"].iloc[0])
        values = group["Log10_RoC"].to_numpy(dtype=float)

        for q in quantile_levels:
            rows.append(
                {
                    "Timescale_kyr": timescale,
                    "Log10_timescale": log_timescale,
                    "Percentile": float(q),
                    "Log10_RoC_quantile": float(np.percentile(values, q)),
                    "N": int(len(values)),
                }
            )

    return pd.DataFrame(rows)


def get_quantile_label(percentile: float) -> str:
    """
    Convert percentile to a readable label.
    """
    percentile = float(percentile)

    if percentile == 25:
        return "Q1"

    if percentile == 50:
        return "Q2"

    if percentile == 75:
        return "Q3"

    if percentile.is_integer():
        return f"P{int(percentile)}"

    return f"P{percentile}"


def normalize_merged_roc_table(
    merged_table: pd.DataFrame,
    slope: float,
    intercept: float,
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> pd.DataFrame:
    """
    Correct RoC values for analytical time-scale effects.

    The LRI model is:
        log10(Baseline_RoC) = slope * log10(timescale) + intercept

    The corrected RoC is:
        Corrected_RoC = Observed_RoC / Baseline_RoC

    This correction does not normalize all values to a fixed reference time scale.
    Each analytical time scale has its own baseline RoC predicted by the
    regression curve.

    Parameters
    ----------
    merged_table : pandas.DataFrame
        Wide-format merged RoC table.
    slope : float
        LRI slope from all-data regression.
    intercept : float
        LRI intercept from all-data regression.
    age_col : str, default "Age_kyr"
        Age column name.
    column_prefix : str, default "Timescale_"
        Prefix of time-scale columns.

    Returns
    -------
    pandas.DataFrame
        Time-scale-corrected relative RoC table.
    """
    if age_col not in merged_table.columns:
        raise KeyError(f"Missing age column: {age_col}")

    corrected = merged_table.copy()

    timescale_columns = identify_timescale_columns(
        table=corrected,
        column_prefix=column_prefix,
    )

    for column in timescale_columns:
        timescale = parse_timescale_from_column(
            column_name=column,
            column_prefix=column_prefix,
        )

        if timescale is None or timescale <= 0:
            continue

        baseline_roc = 10 ** (
            float(slope) * np.log10(float(timescale)) + float(intercept)
        )

        corrected[column] = pd.to_numeric(
            corrected[column],
            errors="coerce",
        ) / baseline_roc

    return corrected


def run_lri_regression_for_one_method(
    merged_table: pd.DataFrame,
    method_name: str,
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
    quantile_levels: list[float] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Run LRI regression for one method.

    Returns
    -------
    dict
        {
            "points": flattened LRI point table,
            "summary": regression summary table,
            "quantiles": quantile regression point table,
            "normalized_table": time-scale-corrected relative RoC table
        }
    """
    if quantile_levels is None:
        quantile_levels = [25.0, 50.0, 75.0]

    flattened = flatten_lri_data(
        merged_table=merged_table,
        method_name=method_name,
        age_col=age_col,
        column_prefix=column_prefix,
    )

    all_fit = fit_linear_regression(
        x=flattened["Log10_timescale"],
        y=flattened["Log10_RoC"],
    )

    summary_rows = [
        {
            "Method": method_name,
            "Regression": "All data",
            "Percentile": np.nan,
            "Slope": all_fit["slope"],
            "Intercept": all_fit["intercept"],
            "R2": all_fit["r2"],
            "N": all_fit["n"],
            "Correction": "Observed_RoC / baseline_RoC_at_same_timescale",
        }
    ]

    quantile_points = calculate_quantile_series(
        flattened_table=flattened,
        quantile_levels=quantile_levels,
    )

    for percentile in quantile_levels:
        subset = quantile_points[
            quantile_points["Percentile"] == float(percentile)
        ].copy()

        fit = fit_linear_regression(
            x=subset["Log10_timescale"],
            y=subset["Log10_RoC_quantile"],
        )

        summary_rows.append(
            {
                "Method": method_name,
                "Regression": get_quantile_label(percentile),
                "Percentile": float(percentile),
                "Slope": fit["slope"],
                "Intercept": fit["intercept"],
                "R2": fit["r2"],
                "N": fit["n"],
                "Correction": "Not used for correction",
            }
        )

    summary = pd.DataFrame(summary_rows)

    normalized_table = normalize_merged_roc_table(
        merged_table=merged_table,
        slope=all_fit["slope"],
        intercept=all_fit["intercept"],
        age_col=age_col,
        column_prefix=column_prefix,
    )

    return {
        "points": flattened,
        "summary": summary,
        "quantiles": quantile_points,
        "normalized_table": normalized_table,
    }


def get_lri_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get LRI settings from config.
    """
    lri_config = config.get("lri", {})

    return {
        "quantile_levels": [
            float(value)
            for value in lri_config.get("quantile_levels", [25, 50, 75])
        ],
    }


def run_lri_for_all_methods(
    merged_tables_by_method: dict[str, pd.DataFrame],
    config: dict[str, Any],
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> dict[str, dict[str, pd.DataFrame]]:
    """
    Run LRI regression for all methods.
    """
    settings = get_lri_settings(config)
    results = {}

    for method_name, merged_table in merged_tables_by_method.items():
        results[method_name] = run_lri_regression_for_one_method(
            merged_table=merged_table,
            method_name=method_name,
            age_col=age_col,
            column_prefix=column_prefix,
            quantile_levels=settings["quantile_levels"],
        )

    return results


def extract_normalized_tables(
    lri_results: dict[str, dict[str, pd.DataFrame]],
) -> dict[str, pd.DataFrame]:
    """
    Extract time-scale-corrected relative RoC tables from LRI results.
    """
    output = {}

    for method_name, result in lri_results.items():
        if "normalized_table" in result:
            output[method_name] = result["normalized_table"]

    return output