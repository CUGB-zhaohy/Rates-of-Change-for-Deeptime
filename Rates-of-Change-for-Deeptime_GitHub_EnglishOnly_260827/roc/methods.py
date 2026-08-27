"""
Core mathematical methods for RoC calculation.

This module contains only calculation functions.
It does not read files, write files, or make plots.

Main functions:
- calculate_mean
- calculate_iqr
- calculate_theilsen_slope
- calculate_ibr_from_interpolated_mean
- calculate_bin_metric
- standardize_rate_series
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import scipy.stats as sts


def calculate_mean(values) -> float:
    """
    Calculate the arithmetic mean of finite values.

    Parameters
    ----------
    values : array-like
        Input values.

    Returns
    -------
    float
        Mean value. Returns NaN if no finite values are available.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return np.nan

    return float(np.mean(arr))


def normalize_iqr_quartile_method(method: str) -> str:
    """
    Normalize IQR quartile calculation method.

    Supported methods
    -----------------
    inc:
        Inclusive quartile method, equivalent to Excel QUARTILE.INC
        or PERCENTILE.INC. This corresponds to NumPy method="linear".

    exc:
        Exclusive quartile method, equivalent to Excel QUARTILE.EXC
        or PERCENTILE.EXC. This corresponds to NumPy method="weibull".
    """
    method = str(method).strip().lower()

    if method in {"inc", "inclusive", "quartile.inc", "percentile.inc"}:
        return "inc"

    if method in {"exc", "exclusive", "quartile.exc", "percentile.exc"}:
        return "exc"

    raise ValueError(
        "Unsupported IQR quartile method. "
        "Please use 'inc' or 'exc'."
    )


def calculate_iqr_components(
    values,
    quartile_method: str = "exc",
    min_count: int = 5,
) -> tuple[float, float, float]:
    """
    Calculate Q1, Q3, and IQR.

    Returns
    -------
    tuple
        Q1, Q3, and IQR, where IQR = Q3 - Q1.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]

    min_count = int(min_count)

    if min_count < 1:
        raise ValueError("iqr_min_count must be at least 1.")

    if arr.size < min_count:
        return np.nan, np.nan, np.nan

    method = normalize_iqr_quartile_method(quartile_method)

    if method == "inc":
        q1, q3 = np.percentile(
            arr,
            [25, 75],
            method="linear",
        )

    elif method == "exc":
        q1, q3 = np.percentile(
            arr,
            [25, 75],
            method="weibull",
        )

    else:
        raise ValueError(
            f"Unsupported IQR quartile method: {quartile_method}"
        )

    q1 = float(q1)
    q3 = float(q3)
    iqr = float(q3 - q1)

    return q1, q3, iqr


def calculate_iqr(
    values,
    quartile_method: str = "exc",
    min_count: int = 5,
) -> float:
    """
    Calculate interquartile range.

    Returns
    -------
    float
        IQR = Q3 - Q1.
    """
    _, _, iqr = calculate_iqr_components(
        values=values,
        quartile_method=quartile_method,
        min_count=min_count,
    )

    return iqr


def calculate_theilsen_slope(x, y, alpha: float = 0.90) -> float:
    """
    Calculate the Theil-Sen slope within a time bin.

    Parameters
    ----------
    x : array-like
        Age values.
    y : array-like
        Proxy values.
    alpha : float, default 0.90
        Confidence level used by scipy.stats.theilslopes.

    Returns
    -------
    float
        Theil-Sen slope. Returns NaN if fewer than two unique finite age values exist.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    valid_mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr = x_arr[valid_mask]
    y_arr = y_arr[valid_mask]

    if np.unique(x_arr).size < 2:
        return np.nan

    slope, *_ = sts.theilslopes(y_arr, x_arr, alpha=alpha)

    return float(slope)


def calculate_ibr_from_interpolated_mean(
    df: pd.DataFrame,
    age_col: str,
    mean_col: str,
    timebin_width: float,
    out_age_col: str = "Age_kyr",
    out_rate_col: str = "Rate",
) -> pd.DataFrame:
    """
    Calculate Inter-bin Rate (IBR) from interpolated bin means.

    IBR workflow:
    raw data -> time-bin mean -> interpolate missing mean -> calculate IBR

    The IBR is calculated between two non-overlapping bins whose central age points
    are separated by the analytical time scale, namely the time-bin width.

    Parameters
    ----------
    df : pandas.DataFrame
        Table containing interpolated bin means.
    age_col : str
        Column name of bin central age points.
    mean_col : str
        Column name of interpolated mean values.
    timebin_width : float
        Analytical time scale / bin length.
    out_age_col : str, default "Age_kyr"
        Output age column name.
    out_rate_col : str, default "Rate"
        Output RoC column name.

    Returns
    -------
    pandas.DataFrame
        Table with age point and IBR value.
    """
    required_columns = {age_col, mean_col}

    if not required_columns.issubset(df.columns):
        missing = sorted(required_columns - set(df.columns))
        raise KeyError(f"Missing required columns for IBR calculation: {missing}")

    local_df = df[[age_col, mean_col]].copy()
    local_df[age_col] = pd.to_numeric(local_df[age_col], errors="coerce")
    local_df[mean_col] = pd.to_numeric(local_df[mean_col], errors="coerce")
    local_df = local_df.dropna(subset=[age_col, mean_col])

    if local_df.empty:
        return pd.DataFrame(columns=[out_age_col, out_rate_col])

    local_df = (
        local_df
        .groupby(age_col, as_index=False, sort=False)[mean_col]
        .mean()
        .sort_values(age_col, ascending=True)
        .reset_index(drop=True)
    )

    series = local_df.set_index(age_col)[mean_col]

    result = pd.DataFrame({age_col: series.index})
    result["Age_next"] = result[age_col] + float(timebin_width)

    result["Value"] = series.reindex(result[age_col]).values
    result["Value_next"] = series.reindex(result["Age_next"]).values

    result = result.dropna(subset=["Value", "Value_next"])

    result[out_age_col] = (result[age_col] + result["Age_next"]) / 2.0
    result[out_rate_col] = (
        result["Value_next"] - result["Value"]
    ).abs() / float(timebin_width)

    return result[[out_age_col, out_rate_col]].reset_index(drop=True)


def calculate_bin_metric(
    values,
    ages: Optional[object] = None,
    metric: str = "mean",
    theilsen_alpha: float = 0.90,
    iqr_quartile_method: str = "exc",
    iqr_min_count: int = 5,
) -> float:
    """
    Calculate a selected metric within one time bin.

    Parameters
    ----------
    values : array-like
        Proxy values within the time bin.
    ages : array-like, optional
        Age values within the time bin. Required for Theil-Sen slope.
    metric : {"mean", "iqr", "ts"}
        Metric to calculate.
    theilsen_alpha : float, default 0.90
        Confidence level for Theil-Sen slope.

    Returns
    -------
    float
        Calculated metric value.
    """
    metric = str(metric).strip().lower()

    if metric == "mean":
        return calculate_mean(values)

    if metric == "iqr":
        return calculate_iqr(
            values,
            quartile_method=iqr_quartile_method,
            min_count=iqr_min_count,
        )

    if metric in {"ts", "theilsen", "theil-sen", "theil_sen"}:
        if ages is None:
            raise ValueError("ages must be provided when metric='ts'.")
        return calculate_theilsen_slope(ages, values, alpha=theilsen_alpha)

    raise ValueError(
        "Unsupported metric. Expected one of: 'mean', 'iqr', 'ts'. "
        f"Got: {metric}"
    )


def standardize_rate_series(
    df: pd.DataFrame,
    age_col: str,
    value_col: str,
    output_age_col: str = "Age_kyr",
    output_value_col: str = "Rate",
    take_absolute: bool = True,
) -> pd.DataFrame:
    """
    Standardize a RoC or RoC-related table to two columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Input table.
    age_col : str
        Source age column.
    value_col : str
        Source value column.
    output_age_col : str, default "Age_kyr"
        Standardized age column name.
    output_value_col : str, default "Rate"
        Standardized value column name.
    take_absolute : bool, default True
        Whether to convert values to absolute magnitudes.

    Returns
    -------
    pandas.DataFrame
        Standardized table with two columns.
    """
    required_columns = {age_col, value_col}

    if not required_columns.issubset(df.columns):
        missing = sorted(required_columns - set(df.columns))
        raise KeyError(f"Missing required columns: {missing}")

    out = df[[age_col, value_col]].copy()
    out[age_col] = pd.to_numeric(out[age_col], errors="coerce")
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce")
    out = out.dropna(subset=[age_col, value_col])

    if take_absolute:
        out[value_col] = out[value_col].abs()

    out = out.rename(
        columns={
            age_col: output_age_col,
            value_col: output_value_col,
        }
    )

    out = out.sort_values(output_age_col, ascending=True).reset_index(drop=True)

    return out