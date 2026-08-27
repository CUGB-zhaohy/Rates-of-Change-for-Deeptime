"""
Time-bin utilities for RoC workflow.

This module is responsible for:
- generating age nodes
- selecting data within a time-bin window
- computing bin-level mean, Theil-Sen slope, or IQR

Important workflow difference:
- IBR uses time-bin mean first, then interpolation, then IBR calculation.
- TS and IQR calculate RoC-related values inside each time bin first,
  then interpolate missing bin-level values.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .methods import (
    calculate_bin_metric,
    calculate_iqr_components,
)


def generate_age_nodes(
    start_age_kyr: float,
    end_age_kyr: float,
    resolution_kyr: float,
) -> np.ndarray:
    """
    Generate uniformly spaced age nodes.

    Parameters
    ----------
    start_age_kyr : float
        One end of the age range, usually the older age.
    end_age_kyr : float
        The other end of the age range, usually the younger age.
    resolution_kyr : float
        Spacing between adjacent central age points.

    Returns
    -------
    numpy.ndarray
        Age nodes sorted from young to old, for example 0, 10, 20, ...
    """
    if resolution_kyr <= 0:
        raise ValueError("resolution_kyr must be greater than 0.")

    age_min = min(float(start_age_kyr), float(end_age_kyr))
    age_max = max(float(start_age_kyr), float(end_age_kyr))

    nodes = np.arange(
        age_min,
        age_max + float(resolution_kyr) * 0.5,
        float(resolution_kyr),
        dtype=float,
    )

    return nodes


def select_bin_data(
    data: pd.DataFrame,
    center_age: float,
    timebin_width: float,
    age_col: str = "Age",
) -> pd.DataFrame:
    """
    Select observations within one time-bin window.

    The bin interval is:
        [center_age - timebin_width / 2, center_age + timebin_width / 2)

    Parameters
    ----------
    data : pandas.DataFrame
        Input data table.
    center_age : float
        Central age point of the bin.
    timebin_width : float
        Bin length / analytical time scale.
    age_col : str, default "Age"
        Age column name.

    Returns
    -------
    pandas.DataFrame
        Subset of data inside the bin.
    """
    if age_col not in data.columns:
        raise KeyError(f"Missing age column: {age_col}")

    if timebin_width <= 0:
        raise ValueError("timebin_width must be greater than 0.")

    half_width = float(timebin_width) / 2.0
    bin_start = float(center_age) - half_width
    bin_end = float(center_age) + half_width

    return data[(data[age_col] >= bin_start) & (data[age_col] < bin_end)]


def get_result_column_name(metric: str) -> str:
    """
    Return the standard output value column name for a time-bin metric.

    Parameters
    ----------
    metric : {"mean", "ts", "iqr"}
        Metric name.

    Returns
    -------
    str
        Standard output column name.
    """
    metric = str(metric).strip().lower()

    if metric == "mean":
        return "Mean_origin"

    if metric in {"ts", "theilsen", "theil-sen", "theil_sen", "iqr"}:
        return "Rate_origin"

    raise ValueError(
        "Unsupported metric. Expected one of: 'mean', 'ts', 'iqr'. "
        f"Got: {metric}"
    )


def normalize_metric_name(metric: str) -> str:
    """
    Normalize metric name.

    Parameters
    ----------
    metric : str
        Metric name.

    Returns
    -------
    str
        One of "mean", "ts", or "iqr".
    """
    metric = str(metric).strip().lower()

    if metric == "mean":
        return "mean"

    if metric in {"ts", "theilsen", "theil-sen", "theil_sen"}:
        return "ts"

    if metric == "iqr":
        return "iqr"

    raise ValueError(
        "Unsupported metric. Expected one of: 'mean', 'ts', 'iqr'. "
        f"Got: {metric}"
    )


def validate_input_data(
    data: pd.DataFrame,
    age_col: str = "Age",
    value_col: str = "Value",
) -> pd.DataFrame:
    """
    Validate and clean input data for time-bin calculation.

    Parameters
    ----------
    data : pandas.DataFrame
        Input table.
    age_col : str, default "Age"
        Age column name.
    value_col : str, default "Value"
        Value column name.

    Returns
    -------
    pandas.DataFrame
        Cleaned data with numeric age and value columns.
    """
    required_columns = {age_col, value_col}

    if not required_columns.issubset(data.columns):
        missing = sorted(required_columns - set(data.columns))
        raise KeyError(f"Missing required columns: {missing}")

    clean = data[[age_col, value_col]].copy()
    clean[age_col] = pd.to_numeric(clean[age_col], errors="coerce")
    clean[value_col] = pd.to_numeric(clean[value_col], errors="coerce")
    clean = clean.dropna(subset=[age_col, value_col])

    if clean.empty:
        raise ValueError("No valid numeric age-value pairs are available.")

    # If multiple values have exactly the same age, average them.
    clean = (
        clean
        .groupby(age_col, as_index=False, sort=False)[value_col]
        .mean()
        .sort_values(age_col, ascending=True)
        .reset_index(drop=True)
    )

    return clean


def compute_timebin_table(
    data: pd.DataFrame,
    age_nodes: Iterable[float],
    timebin_width: float,
    metric: str,
    age_col: str = "Age",
    value_col: str = "Value",
    theilsen_alpha: float = 0.90,
    iqr_quartile_method: str = "exc",
    iqr_min_count: int = 5,
) -> pd.DataFrame:
    """
    Compute a time-bin table for mean, TS, or IQR.

    Parameters
    ----------
    data : pandas.DataFrame
        Input data table with age and value columns.
    age_nodes : iterable of float
        Central age points of time bins.
    timebin_width : float
        Bin length / analytical time scale.
    metric : {"mean", "ts", "iqr"}
        Metric to calculate inside each bin.
    age_col : str, default "Age"
        Age column name.
    value_col : str, default "Value"
        Value column name.
    theilsen_alpha : float, default 0.90
        Confidence level used by scipy.stats.theilslopes.

    Returns
    -------
    pandas.DataFrame
        Time-bin table.

        For metric="mean", value column is "Mean_origin".
        For metric="ts" or "iqr", value column is "Rate_origin".
    """
    metric = normalize_metric_name(metric)
    result_col = get_result_column_name(metric)

    clean_data = validate_input_data(
        data=data,
        age_col=age_col,
        value_col=value_col,
    )

    rows = []

    for i, center_age in enumerate(age_nodes):
        bin_data = select_bin_data(
            data=clean_data,
            center_age=float(center_age),
            timebin_width=float(timebin_width),
            age_col=age_col,
        )

        counts = int(len(bin_data))
        age_unique = int(bin_data[age_col].nunique())

        q1_value = np.nan
        q3_value = np.nan

        if counts == 0:
            metric_value = np.nan

        elif metric == "iqr":
            q1_value, q3_value, metric_value = calculate_iqr_components(
                values=bin_data[value_col],
                quartile_method=iqr_quartile_method,
                min_count=iqr_min_count,
            )

        else:
            metric_value = calculate_bin_metric(
                values=bin_data[value_col],
                ages=bin_data[age_col],
                metric=metric,
                theilsen_alpha=theilsen_alpha,
                iqr_quartile_method=iqr_quartile_method,
                iqr_min_count=iqr_min_count,
            )

            # For TS, use absolute slope magnitude for RoC comparison.
            if metric == "ts" and np.isfinite(metric_value):
                metric_value = abs(metric_value)

        row = {
            "Time_bin": f"TimeBin{i + 1}",
            "Age_node": float(center_age),
            "Timebin_width_kyr": float(timebin_width),
            "Counts": counts,
            "Age_unique": age_unique,
            "Metric": metric,
            result_col: metric_value,
        }

        if metric == "iqr":
            row["Quartile_1_origin"] = q1_value
            row["Quartile_3_origin"] = q3_value
            row["IQR_quartile_method"] = str(
                iqr_quartile_method
            ).strip().lower()
            row["IQR_min_count"] = int(iqr_min_count)

        rows.append(row)

    return pd.DataFrame(rows)


def compute_timebin_tables_for_widths(
    data: pd.DataFrame,
    age_nodes: Iterable[float],
    timebin_widths: Iterable[float],
    metric: str,
    age_col: str = "Age",
    value_col: str = "Value",
    theilsen_alpha: float = 0.90,
    iqr_quartile_method: str = "exc",
    iqr_min_count: int = 5,
) -> dict[float, pd.DataFrame]:
    """
    Compute time-bin tables for multiple analytical time scales.

    Parameters
    ----------
    data : pandas.DataFrame
        Input data table.
    age_nodes : iterable of float
        Central age points.
    timebin_widths : iterable of float
        Multiple bin lengths.
    metric : {"mean", "ts", "iqr"}
        Metric to calculate.
    age_col : str, default "Age"
        Age column name.
    value_col : str, default "Value"
        Value column name.
    theilsen_alpha : float, default 0.90
        Confidence level used by scipy.stats.theilslopes.

    Returns
    -------
    dict
        Dictionary whose keys are time-bin widths and values are time-bin tables.
    """
    output = {}

    for width in timebin_widths:
        width = float(width)

        output[width] = compute_timebin_table(
            data=data,
            age_nodes=age_nodes,
            timebin_width=width,
            metric=metric,
            age_col=age_col,
            value_col=value_col,
            theilsen_alpha=theilsen_alpha,
            iqr_quartile_method=iqr_quartile_method,
            iqr_min_count=iqr_min_count,
        )

    return output