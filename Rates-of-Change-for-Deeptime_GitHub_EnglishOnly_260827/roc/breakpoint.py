"""
PWLF breakpoint detection for RoC workflow.

This module detects candidate phase boundaries using piecewise linear fitting
on normalized cumulative RoC curves.

Input:
    Wide-format RoC table:
        Age_kyr | Timescale_100 | Timescale_200 | ... | Timescale_1000

Main logic:
    1. Select one timescale column.
    2. Normalize the RoC series by its total sum.
    3. Calculate the cumulative sum.
    4. Fit piecewise linear models with different segment numbers.
    5. Extract internal breakpoints.
    6. Evaluate breakpoint confidence and local slope-change significance.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .lri import identify_timescale_columns, parse_timescale_from_column

try:
    import pwlf

    PWLF_AVAILABLE = True
except Exception:
    pwlf = None
    PWLF_AVAILABLE = False

try:
    from scipy import stats

    SCIPY_AVAILABLE = True
except Exception:
    stats = None
    SCIPY_AVAILABLE = False


def normalize_and_cumsum(values) -> np.ndarray:
    """
    Normalize a RoC series by its total sum and calculate cumulative sum.

    Parameters
    ----------
    values : array-like
        Input RoC values.

    Returns
    -------
    numpy.ndarray
        Normalized cumulative sum.
    """
    arr = np.asarray(values, dtype=float)

    if np.any(~np.isfinite(arr)):
        raise ValueError("Input values contain non-finite values.")

    total = np.sum(arr)

    if not np.isfinite(total) or total <= 0:
        raise ValueError(f"sum(values) must be finite and greater than 0. Got {total}")

    normalized = arr / total
    cumsum = np.cumsum(normalized)

    if np.isfinite(cumsum[-1]) and cumsum[-1] != 0:
        cumsum = cumsum / cumsum[-1]

    return cumsum


def compute_segment_r2(
    x,
    y,
    slope: float,
    intercept: float,
    left_bp: float,
    right_bp: float,
    last_segment: bool = False,
) -> float:
    """
    Calculate local R2 for one PWLF segment.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    if last_segment:
        mask = (x_arr >= left_bp) & (x_arr <= right_bp)
    else:
        mask = (x_arr >= left_bp) & (x_arr < right_bp)

    x_segment = x_arr[mask]
    y_segment = y_arr[mask]

    if x_segment.size < 2:
        return np.nan

    y_pred = slope * x_segment + intercept
    y_mean = np.mean(y_segment)

    ss_res = np.sum((y_segment - y_pred) ** 2)
    ss_tot = np.sum((y_segment - y_mean) ** 2)

    if ss_tot == 0:
        return np.nan

    return float(1.0 - ss_res / ss_tot)


def compute_breakpoint_confidence(slopes, r2_list) -> list[float]:
    """
    Calculate breakpoint confidence from slope contrast and adjacent-segment R2.

    The first and last breakpoints are endpoints and are assigned confidence = 1.
    Internal breakpoint confidence is:
        normalized slope contrast * mean adjacent R2
    """
    slopes = np.asarray(slopes, dtype=float)
    n_segments = len(slopes)

    if n_segments < 2:
        return [1.0, 1.0]

    slope_diffs = [
        abs(slopes[i] - slopes[i - 1])
        for i in range(1, n_segments)
        if np.isfinite(slopes[i]) and np.isfinite(slopes[i - 1])
    ]

    max_diff = max(slope_diffs) if slope_diffs else 1e-12

    if not np.isfinite(max_diff) or max_diff == 0:
        max_diff = 1e-12

    confidence = [0.0] * (n_segments + 1)
    confidence[0] = 1.0
    confidence[-1] = 1.0

    for k in range(1, n_segments):
        if not np.isfinite(slopes[k]) or not np.isfinite(slopes[k - 1]):
            slope_factor = 0.0
        else:
            slope_factor = abs(slopes[k] - slopes[k - 1]) / max_diff

        r2_left = r2_list[k - 1]
        r2_right = r2_list[k]

        if not np.isfinite(r2_left) or not np.isfinite(r2_right):
            mean_r2 = 0.0
        else:
            mean_r2 = 0.5 * (r2_left + r2_right)

        value = slope_factor * mean_r2

        if not np.isfinite(value):
            value = 0.0

        confidence[k] = max(0.0, min(1.0, float(value)))

    return confidence


def fit_pwlf_on_cumsum(
    x,
    y_cumsum,
    n_segments: int,
) -> dict[str, Any]:
    """
    Fit a PWLF model to normalized cumulative RoC.
    """
    if not PWLF_AVAILABLE:
        raise ImportError(
            "The 'pwlf' package is required for breakpoint detection. "
            "Install it with: pip install pwlf"
        )

    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y_cumsum, dtype=float)

    model = pwlf.PiecewiseLinFit(x_arr, y_arr)
    breakpoints = model.fit(n_segments)
    slopes = model.slopes
    intercepts = model.intercepts
    yhat = model.predict(x_arr)

    r2_list = []

    for i in range(n_segments):
        r2_local = compute_segment_r2(
            x=x_arr,
            y=y_arr,
            slope=slopes[i],
            intercept=intercepts[i],
            left_bp=breakpoints[i],
            right_bp=breakpoints[i + 1],
            last_segment=(i == n_segments - 1),
        )
        r2_list.append(r2_local)

    confidence_list = compute_breakpoint_confidence(
        slopes=slopes,
        r2_list=r2_list,
    )

    return {
        "breakpoints": np.asarray(breakpoints, dtype=float),
        "slopes": np.asarray(slopes, dtype=float),
        "intercepts": np.asarray(intercepts, dtype=float),
        "yhat": np.asarray(yhat, dtype=float),
        "r2_list": r2_list,
        "confidence_list": confidence_list,
    }


def ols_slope_se(x, y) -> tuple[float, float, float, int]:
    """
    Estimate OLS slope, intercept, and standard error of the slope.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr = x_arr[mask]
    y_arr = y_arr[mask]

    n = x_arr.size

    if n < 3:
        return np.nan, np.nan, np.nan, int(n)

    x_mean = x_arr.mean()
    y_mean = y_arr.mean()

    sxx = np.sum((x_arr - x_mean) ** 2)

    if sxx == 0:
        return np.nan, np.nan, np.nan, int(n)

    slope = np.sum((x_arr - x_mean) * (y_arr - y_mean)) / sxx
    intercept = y_mean - slope * x_mean

    yhat = intercept + slope * x_arr
    rss = np.sum((y_arr - yhat) ** 2)

    dof = n - 2

    if dof <= 0:
        return float(slope), float(intercept), np.nan, int(n)

    s2 = rss / dof
    slope_se = np.sqrt(s2 / sxx)

    return float(slope), float(intercept), float(slope_se), int(n)


def breakpoint_slope_change_pvalue_fixed_time_window(
    x,
    y_cum,
    bp: float,
    half_window_kyr: float,
    min_points: int,
) -> tuple:
    """
    Test local slope change across a breakpoint using fixed age windows.

    The left window is:
        [bp - half_window_kyr, bp)

    The right window is:
        [bp, bp + half_window_kyr]
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y_cum, dtype=float)

    left_window = (x_arr < bp) & (x_arr >= bp - half_window_kyr)
    right_window = (x_arr >= bp) & (x_arr <= bp + half_window_kyr)

    left_idx = np.where(left_window)[0]
    right_idx = np.where(right_window)[0]

    n_left_window = int(np.sum(left_window))
    n_right_window = int(np.sum(right_window))

    if left_idx.size < min_points or right_idx.size < min_points:
        return (
            np.nan,
            np.nan,
            np.nan,
            (np.nan, np.nan),
            (np.nan, np.nan),
            (int(left_idx.size), int(right_idx.size)),
            (n_left_window, n_right_window),
        )

    x_left = x_arr[left_idx]
    y_left = y_arr[left_idx]
    x_right = x_arr[right_idx]
    y_right = y_arr[right_idx]

    slope_left, _, se_left, n_left = ols_slope_se(x_left, y_left)
    slope_right, _, se_right, n_right = ols_slope_se(x_right, y_right)

    if (
        not np.isfinite(slope_left)
        or not np.isfinite(slope_right)
        or not np.isfinite(se_left)
        or not np.isfinite(se_right)
    ):
        return (
            np.nan,
            np.nan,
            np.nan,
            (slope_left, slope_right),
            (se_left, se_right),
            (int(n_left), int(n_right)),
            (n_left_window, n_right_window),
        )

    denominator = np.sqrt(se_left**2 + se_right**2)

    if denominator == 0 or not np.isfinite(denominator):
        return (
            np.nan,
            np.nan,
            np.nan,
            (slope_left, slope_right),
            (se_left, se_right),
            (int(n_left), int(n_right)),
            (n_left_window, n_right_window),
        )

    t_stat = (slope_right - slope_left) / denominator

    v_left = se_left**2
    v_right = se_right**2

    df_denominator = (v_left**2) / max(n_left - 2, 1) + (v_right**2) / max(
        n_right - 2,
        1,
    )

    if df_denominator <= 0 or not np.isfinite(df_denominator):
        df_value = float(max(n_left + n_right - 4, 1))
    else:
        df_value = float(((v_left + v_right) ** 2) / df_denominator)

    if SCIPY_AVAILABLE:
        p_value = float(2 * stats.t.sf(np.abs(t_stat), df_value))
    else:
        p_value = float(
            2 * (1 - 0.5 * (1 + math.erf(np.abs(t_stat) / np.sqrt(2))))
        )

    return (
        p_value,
        float(t_stat),
        float(df_value),
        (float(slope_left), float(slope_right)),
        (float(se_left), float(se_right)),
        (int(n_left), int(n_right)),
        (n_left_window, n_right_window),
    )


def get_breakpoint_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get PWLF breakpoint settings from config.
    """
    breakpoint_config = config.get("breakpoint", {})

    return {
        "data_type": str(
            breakpoint_config.get("data_type", "time_scale_corrected_relative")
        ),
        "age_min_kyr": float(breakpoint_config.get("age_min_kyr", 0.0)),
        "age_max_kyr": float(breakpoint_config.get("age_max_kyr", 67100.0)),
        "segments": [
            int(value)
            for value in breakpoint_config.get("segments", [5, 6, 7, 8, 9, 10])
        ],
        "half_window_kyr": float(breakpoint_config.get("half_window_kyr", 1000.0)),
        "min_points": int(breakpoint_config.get("min_points", 8)),
        "alpha": float(breakpoint_config.get("alpha", 0.05)),
    }


def prepare_timescale_series(
    table: pd.DataFrame,
    column: str,
    age_col: str,
    age_min_kyr: float,
    age_max_kyr: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Prepare x and y arrays for one timescale column.
    """
    local = table[[age_col, column]].copy()
    local[age_col] = pd.to_numeric(local[age_col], errors="coerce")
    local[column] = pd.to_numeric(local[column], errors="coerce")

    local = local.dropna(subset=[age_col, column])
    local = local[(local[age_col] >= age_min_kyr) & (local[age_col] <= age_max_kyr)]
    local = local[local[column] >= 0]
    local = local.sort_values(age_col, ascending=True).reset_index(drop=True)

    x = local[age_col].to_numpy(dtype=float)
    y = local[column].to_numpy(dtype=float)

    return x, y


def run_pwlf_detection_for_one_method(
    table: pd.DataFrame,
    method_name: str,
    data_type: str,
    config: dict[str, Any],
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> dict[str, pd.DataFrame]:
    """
    Run PWLF breakpoint detection for one method table.
    """
    settings = get_breakpoint_settings(config)

    timescale_columns = identify_timescale_columns(
        table=table,
        column_prefix=column_prefix,
    )

    breakpoint_rows = []
    summary_rows = []

    for column in timescale_columns:
        timescale = parse_timescale_from_column(
            column_name=column,
            column_prefix=column_prefix,
        )

        if timescale is None:
            continue

        x, y = prepare_timescale_series(
            table=table,
            column=column,
            age_col=age_col,
            age_min_kyr=settings["age_min_kyr"],
            age_max_kyr=settings["age_max_kyr"],
        )

        if x.size < 10:
            summary_rows.append(
                {
                    "Method": method_name,
                    "Data_type": data_type,
                    "Timescale_kyr": float(timescale),
                    "Column": column,
                    "Status": "skipped",
                    "Reason": "fewer_than_10_points",
                    "N_points": int(x.size),
                }
            )
            continue

        try:
            y_cumsum = normalize_and_cumsum(y)
        except Exception as error:
            summary_rows.append(
                {
                    "Method": method_name,
                    "Data_type": data_type,
                    "Timescale_kyr": float(timescale),
                    "Column": column,
                    "Status": "skipped",
                    "Reason": str(error),
                    "N_points": int(x.size),
                }
            )
            continue

        for n_segments in settings["segments"]:
            if x.size < n_segments + 1:
                summary_rows.append(
                    {
                        "Method": method_name,
                        "Data_type": data_type,
                        "Timescale_kyr": float(timescale),
                        "Column": column,
                        "Segments": int(n_segments),
                        "Status": "skipped",
                        "Reason": "too_few_points_for_segments",
                        "N_points": int(x.size),
                    }
                )
                continue

            try:
                fit = fit_pwlf_on_cumsum(
                    x=x,
                    y_cumsum=y_cumsum,
                    n_segments=int(n_segments),
                )
            except Exception as error:
                summary_rows.append(
                    {
                        "Method": method_name,
                        "Data_type": data_type,
                        "Timescale_kyr": float(timescale),
                        "Column": column,
                        "Segments": int(n_segments),
                        "Status": "failed",
                        "Reason": str(error),
                        "N_points": int(x.size),
                    }
                )
                continue

            breakpoints = fit["breakpoints"]
            slopes = fit["slopes"]
            r2_list = fit["r2_list"]
            confidence_list = fit["confidence_list"]

            summary_rows.append(
                {
                    "Method": method_name,
                    "Data_type": data_type,
                    "Timescale_kyr": float(timescale),
                    "Column": column,
                    "Segments": int(n_segments),
                    "Status": "success",
                    "Reason": "",
                    "N_points": int(x.size),
                    "N_internal_breakpoints": int(max(n_segments - 1, 0)),
                }
            )

            for k in range(1, n_segments):
                bp = float(breakpoints[k])

                confidence = (
                    float(confidence_list[k])
                    if np.isfinite(confidence_list[k])
                    else np.nan
                )

                left_slope = (
                    float(slopes[k - 1])
                    if np.isfinite(slopes[k - 1])
                    else np.nan
                )

                right_slope = (
                    float(slopes[k])
                    if np.isfinite(slopes[k])
                    else np.nan
                )

                left_r2 = (
                    float(r2_list[k - 1])
                    if np.isfinite(r2_list[k - 1])
                    else np.nan
                )

                right_r2 = (
                    float(r2_list[k])
                    if np.isfinite(r2_list[k])
                    else np.nan
                )

                delta_slope_pwlf = (
                    right_slope - left_slope
                    if np.isfinite(left_slope) and np.isfinite(right_slope)
                    else np.nan
                )

                (
                    p_value,
                    t_stat,
                    df_t,
                    local_slopes,
                    local_se,
                    n_used,
                    n_window,
                ) = breakpoint_slope_change_pvalue_fixed_time_window(
                    x=x,
                    y_cum=y_cumsum,
                    bp=bp,
                    half_window_kyr=settings["half_window_kyr"],
                    min_points=settings["min_points"],
                )

                local_left_slope, local_right_slope = local_slopes
                local_left_se, local_right_se = local_se
                n_left_used, n_right_used = n_used
                n_left_window, n_right_window = n_window

                if np.isfinite(local_left_slope) and np.isfinite(local_right_slope):
                    delta_slope_local = local_right_slope - local_left_slope
                else:
                    delta_slope_local = np.nan

                significant = bool(np.isfinite(p_value) and p_value < settings["alpha"])

                breakpoint_rows.append(
                    {
                        "Method": method_name,
                        "Data_type": data_type,
                        "Timescale_column": column,
                        "Timescale_kyr": float(timescale),
                        "Segments": int(n_segments),
                        "Breakpoint_kyr": bp,
                        "Breakpoint_Ma": bp / 1000.0,
                        "Confidence": confidence,
                        "Left_slope_pwlf": left_slope,
                        "Right_slope_pwlf": right_slope,
                        "Delta_slope_pwlf": delta_slope_pwlf,
                        "Left_R2": left_r2,
                        "Right_R2": right_r2,
                        "P_value": p_value,
                        "Significant": significant,
                        "Local_Left_slope": local_left_slope,
                        "Local_Right_slope": local_right_slope,
                        "Delta_slope_local": delta_slope_local,
                        "Local_Left_SE": local_left_se,
                        "Local_Right_SE": local_right_se,
                        "T_stat": t_stat,
                        "DF": df_t,
                        "N_left_used": n_left_used,
                        "N_right_used": n_right_used,
                        "N_left_in_window": n_left_window,
                        "N_right_in_window": n_right_window,
                        "Half_window_kyr": settings["half_window_kyr"],
                        "Min_points": settings["min_points"],
                        "Alpha": settings["alpha"],
                        "SciPy_available": SCIPY_AVAILABLE,
                    }
                )

    breakpoint_table = pd.DataFrame(breakpoint_rows)
    summary_table = pd.DataFrame(summary_rows)

    if not breakpoint_table.empty:
        breakpoint_table = breakpoint_table.sort_values(
            ["Method", "Timescale_kyr", "Segments", "Breakpoint_kyr"],
            ascending=True,
        ).reset_index(drop=True)

    return {
        "breakpoints": breakpoint_table,
        "fit_summary": summary_table,
    }


def run_pwlf_analysis(
    rate_tables: dict[str, pd.DataFrame],
    config: dict[str, Any],
    data_type: str = "time_scale_corrected_relative",
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> dict[str, pd.DataFrame]:
    """
    Run PWLF breakpoint detection for all methods.
    """
    breakpoint_tables = []
    summary_tables = []

    for method_name, table in rate_tables.items():
        result = run_pwlf_detection_for_one_method(
            table=table,
            method_name=method_name,
            data_type=data_type,
            config=config,
            age_col=age_col,
            column_prefix=column_prefix,
        )

        if not result["breakpoints"].empty:
            breakpoint_tables.append(result["breakpoints"])

        if not result["fit_summary"].empty:
            summary_tables.append(result["fit_summary"])

    if breakpoint_tables:
        combined_breakpoints = pd.concat(breakpoint_tables, ignore_index=True)
    else:
        combined_breakpoints = pd.DataFrame()

    if summary_tables:
        combined_summary = pd.concat(summary_tables, ignore_index=True)
    else:
        combined_summary = pd.DataFrame()

    return {
        "breakpoints": combined_breakpoints,
        "fit_summary": combined_summary,
    }