"""
KDE consensus breakpoint detection for the RoC workflow.

This module detects consensus breakpoints from PWLF breakpoint tables.

Input:
    PWLF breakpoint table with at least:
        Breakpoint_kyr
        Confidence
        Significant

Main logic:
    1. Select valid breakpoint ages.
    2. Optionally keep only statistically significant breakpoints.
    3. Weight breakpoint ages by confidence.
    4. Build a Gaussian KDE density curve.
    5. Detect density peaks as consensus breakpoints.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

try:
    from scipy.signal import find_peaks

    SCIPY_SIGNAL_AVAILABLE = True
except Exception:
    find_peaks = None
    SCIPY_SIGNAL_AVAILABLE = False


def weighted_mean_std(values, weights) -> tuple[float, float]:
    """
    Calculate weighted mean and weighted standard deviation.
    """
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)

    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x = x[mask]
    w = w[mask]

    if x.size == 0:
        return np.nan, np.nan

    w_sum = np.sum(w)

    if w_sum <= 0:
        return np.nan, np.nan

    mean = np.sum(w * x) / w_sum
    variance = np.sum(w * (x - mean) ** 2) / w_sum

    return float(mean), float(np.sqrt(max(variance, 0.0)))


def weighted_quantile(values, weights, quantiles) -> np.ndarray:
    """
    Calculate weighted quantiles.

    Parameters
    ----------
    values : array-like
        Input values.
    weights : array-like
        Non-negative weights.
    quantiles : array-like
        Quantiles between 0 and 1.

    Returns
    -------
    numpy.ndarray
        Weighted quantile values.
    """
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    q = np.asarray(quantiles, dtype=float)

    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x = x[mask]
    w = w[mask]

    if x.size == 0:
        return np.full_like(q, np.nan, dtype=float)

    sorter = np.argsort(x)
    x = x[sorter]
    w = w[sorter]

    cumulative_weight = np.cumsum(w)
    cumulative_weight = cumulative_weight / cumulative_weight[-1]

    return np.interp(q, cumulative_weight, x)


def silverman_bandwidth(values, weights) -> float:
    """
    Estimate a weighted Silverman bandwidth.
    """
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)

    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x = x[mask]
    w = w[mask]

    if x.size < 2:
        return np.nan

    _, weighted_std = weighted_mean_std(x, w)
    q25, q75 = weighted_quantile(x, w, [0.25, 0.75])
    iqr = q75 - q25

    scale = min(weighted_std, iqr / 1.349) if np.isfinite(iqr) and iqr > 0 else weighted_std

    if not np.isfinite(scale) or scale <= 0:
        scale = np.std(x)

    if not np.isfinite(scale) or scale <= 0:
        return np.nan

    effective_n = (np.sum(w) ** 2) / np.sum(w ** 2)

    if effective_n <= 1:
        effective_n = float(x.size)

    bandwidth = 0.9 * scale * (effective_n ** (-1.0 / 5.0))

    return float(bandwidth)


def get_kde_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get KDE settings from config.
    """
    kde_config = config.get("kde", {})

    return {
        "age_col": str(kde_config.get("age_col", "Breakpoint_kyr")),
        "confidence_col": str(kde_config.get("confidence_col", "Confidence")),
        "significant_col": str(kde_config.get("significant_col", "Significant")),
        "significant_only": bool(kde_config.get("significant_only", True)),
        "fallback_to_all_if_empty": bool(kde_config.get("fallback_to_all_if_empty", True)),
        "use_confidence_weight": bool(kde_config.get("use_confidence_weight", True)),
        "age_min_kyr": float(kde_config.get("age_min_kyr", 0.0)),
        "age_max_kyr": float(kde_config.get("age_max_kyr", 67100.0)),
        "grid_step_kyr": float(kde_config.get("grid_step_kyr", 10.0)),
        "bandwidth_kyr": kde_config.get("bandwidth_kyr", 1000.0),
        "min_prominence_fraction": float(kde_config.get("min_prominence_fraction", 0.05)),
        "min_distance_kyr": float(kde_config.get("min_distance_kyr", 1000.0)),
        "top_n_peaks": int(kde_config.get("top_n_peaks", 20)),
    }


def validate_breakpoint_table(
    breakpoint_table: pd.DataFrame,
    age_col: str,
    confidence_col: str,
) -> pd.DataFrame:
    """
    Validate and clean input breakpoint table.
    """
    required_columns = {age_col}

    if not required_columns.issubset(breakpoint_table.columns):
        missing = sorted(required_columns - set(breakpoint_table.columns))
        raise KeyError(f"Missing required columns in breakpoint table: {missing}")

    clean = breakpoint_table.copy()
    clean[age_col] = pd.to_numeric(clean[age_col], errors="coerce")

    if confidence_col in clean.columns:
        clean[confidence_col] = pd.to_numeric(clean[confidence_col], errors="coerce")
    else:
        clean[confidence_col] = 1.0

    clean = clean.dropna(subset=[age_col])
    clean = clean[np.isfinite(clean[age_col])].copy()

    return clean.reset_index(drop=True)


def select_breakpoints(
    breakpoint_table: pd.DataFrame,
    settings: dict[str, Any],
) -> pd.DataFrame:
    """
    Select breakpoint rows for KDE.
    """
    age_col = settings["age_col"]
    confidence_col = settings["confidence_col"]
    significant_col = settings["significant_col"]

    clean = validate_breakpoint_table(
        breakpoint_table=breakpoint_table,
        age_col=age_col,
        confidence_col=confidence_col,
    )

    clean = clean[
        (clean[age_col] >= settings["age_min_kyr"])
        & (clean[age_col] <= settings["age_max_kyr"])
    ].copy()

    selected = clean.copy()

    if settings["significant_only"] and significant_col in selected.columns:
        significant_mask = selected[significant_col].astype(str).str.lower().isin(
            ["true", "1", "yes"]
        )

        selected_significant = selected[significant_mask].copy()

        if not selected_significant.empty:
            selected = selected_significant
        elif not settings["fallback_to_all_if_empty"]:
            selected = selected_significant

    selected = selected.reset_index(drop=True)

    if selected.empty:
        return selected

    if settings["use_confidence_weight"]:
        weights = pd.to_numeric(selected[confidence_col], errors="coerce")
        weights = weights.fillna(0.0)
        weights = weights.clip(lower=0.0)
        selected["KDE_weight"] = weights
    else:
        selected["KDE_weight"] = 1.0

    selected.loc[~np.isfinite(selected["KDE_weight"]), "KDE_weight"] = 0.0

    if selected["KDE_weight"].sum() <= 0:
        selected["KDE_weight"] = 1.0

    return selected


def get_bandwidth(values, weights, bandwidth_setting) -> float:
    """
    Get KDE bandwidth from setting or Silverman rule.
    """
    if bandwidth_setting is None:
        bandwidth = silverman_bandwidth(values, weights)
    elif isinstance(bandwidth_setting, str) and bandwidth_setting.lower() in {
        "auto",
        "silverman",
    }:
        bandwidth = silverman_bandwidth(values, weights)
    else:
        bandwidth = float(bandwidth_setting)

    if not np.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError(f"Invalid KDE bandwidth: {bandwidth}")

    return float(bandwidth)


def build_density_grid(
    age_min_kyr: float,
    age_max_kyr: float,
    grid_step_kyr: float,
) -> np.ndarray:
    """
    Build KDE evaluation grid.
    """
    if grid_step_kyr <= 0:
        raise ValueError("grid_step_kyr must be greater than 0.")

    if age_max_kyr <= age_min_kyr:
        raise ValueError("age_max_kyr must be greater than age_min_kyr.")

    return np.arange(
        float(age_min_kyr),
        float(age_max_kyr) + float(grid_step_kyr) * 0.5,
        float(grid_step_kyr),
        dtype=float,
    )


def weighted_kde_density(
    grid,
    values,
    weights,
    bandwidth: float,
) -> np.ndarray:
    """
    Calculate weighted Gaussian KDE density.
    """
    grid_arr = np.asarray(grid, dtype=float)
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)

    mask = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x = x[mask]
    w = w[mask]

    if x.size == 0:
        return np.zeros_like(grid_arr, dtype=float)

    w_sum = np.sum(w)

    if w_sum <= 0:
        return np.zeros_like(grid_arr, dtype=float)

    density = np.zeros_like(grid_arr, dtype=float)

    norm_const = bandwidth * np.sqrt(2.0 * np.pi)

    for value, weight in zip(x, w):
        z = (grid_arr - value) / bandwidth
        density += weight * np.exp(-0.5 * z**2) / norm_const

    density = density / w_sum

    return density


def simple_peak_detection(density: np.ndarray) -> np.ndarray:
    """
    Fallback peak detection without scipy.
    """
    if density.size < 3:
        return np.array([], dtype=int)

    peaks = []

    for i in range(1, density.size - 1):
        if density[i] > density[i - 1] and density[i] >= density[i + 1]:
            peaks.append(i)

    return np.asarray(peaks, dtype=int)


def detect_density_peaks(
    grid: np.ndarray,
    density: np.ndarray,
    min_prominence_fraction: float,
    min_distance_kyr: float,
    top_n_peaks: int,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """
    Detect KDE density peaks.
    """
    if density.size == 0 or np.nanmax(density) <= 0:
        return np.array([], dtype=int), {}

    grid_step = np.median(np.diff(grid)) if grid.size > 1 else 1.0

    if not np.isfinite(grid_step) or grid_step <= 0:
        grid_step = 1.0

    distance_points = max(1, int(round(min_distance_kyr / grid_step)))
    prominence = float(min_prominence_fraction) * float(np.nanmax(density))

    if SCIPY_SIGNAL_AVAILABLE:
        peak_indices, properties = find_peaks(
            density,
            prominence=prominence,
            distance=distance_points,
        )
    else:
        peak_indices = simple_peak_detection(density)
        properties = {
            "prominences": density[peak_indices],
        }

    if peak_indices.size == 0:
        return peak_indices, properties

    peak_density = density[peak_indices]
    order = np.argsort(peak_density)[::-1]

    if top_n_peaks > 0:
        order = order[:top_n_peaks]

    peak_indices = peak_indices[order]

    if "prominences" in properties:
        properties["prominences"] = np.asarray(properties["prominences"])[order]

    age_order = np.argsort(grid[peak_indices])
    peak_indices = peak_indices[age_order]

    if "prominences" in properties:
        properties["prominences"] = np.asarray(properties["prominences"])[age_order]

    return peak_indices, properties


def calculate_peak_width_information(
    grid: np.ndarray,
    density: np.ndarray,
    peak_index: int,
    relative_height: float = 0.5,
) -> dict[str, float]:
    """
    Estimate peak width at a relative density height.
    """
    peak_density = float(density[peak_index])
    threshold = peak_density * float(relative_height)

    left_index = peak_index
    while left_index > 0 and density[left_index] >= threshold:
        left_index -= 1

    right_index = peak_index
    while right_index < density.size - 1 and density[right_index] >= threshold:
        right_index += 1

    left_age = float(grid[left_index])
    right_age = float(grid[right_index])
    width = right_age - left_age

    return {
        "Width_left_kyr": left_age,
        "Width_right_kyr": right_age,
        "Width_kyr": float(width),
        "Width_left_Ma": left_age / 1000.0,
        "Width_right_Ma": right_age / 1000.0,
        "Width_Ma": width / 1000.0,
    }


def build_peak_table(
    selected_breakpoints: pd.DataFrame,
    grid: np.ndarray,
    density: np.ndarray,
    peak_indices: np.ndarray,
    properties: dict[str, np.ndarray],
    settings: dict[str, Any],
    bandwidth: float,
) -> pd.DataFrame:
    """
    Build consensus peak table.
    """
    age_col = settings["age_col"]

    rows = []

    breakpoint_ages = selected_breakpoints[age_col].to_numpy(dtype=float)
    breakpoint_weights = selected_breakpoints["KDE_weight"].to_numpy(dtype=float)

    prominences = properties.get("prominences", np.full(peak_indices.size, np.nan))

    for rank, peak_index in enumerate(peak_indices, start=1):
        peak_age = float(grid[peak_index])
        peak_density = float(density[peak_index])
        prominence = float(prominences[rank - 1]) if rank - 1 < len(prominences) else np.nan

        within_bandwidth = np.abs(breakpoint_ages - peak_age) <= bandwidth
        n_within_bandwidth = int(np.sum(within_bandwidth))
        weight_within_bandwidth = float(np.sum(breakpoint_weights[within_bandwidth]))

        width_info = calculate_peak_width_information(
            grid=grid,
            density=density,
            peak_index=int(peak_index),
            relative_height=0.5,
        )

        row = {
            "Peak_rank_by_age": int(rank),
            "Consensus_breakpoint_kyr": peak_age,
            "Consensus_breakpoint_Ma": peak_age / 1000.0,
            "Density": peak_density,
            "Prominence": prominence,
            "Bandwidth_kyr": float(bandwidth),
            "N_breakpoints_within_bandwidth": n_within_bandwidth,
            "Weight_within_bandwidth": weight_within_bandwidth,
            "Grid_step_kyr": settings["grid_step_kyr"],
            "Significant_only": settings["significant_only"],
            "Use_confidence_weight": settings["use_confidence_weight"],
        }

        row.update(width_info)

        rows.append(row)

    return pd.DataFrame(rows)


def run_consensus_kde(
    breakpoint_table: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """
    Run weighted KDE consensus breakpoint detection.
    """
    settings = get_kde_settings(config)

    selected = select_breakpoints(
        breakpoint_table=breakpoint_table,
        settings=settings,
    )

    if selected.empty:
        empty_summary = pd.DataFrame(
            [
                {
                    "Status": "empty",
                    "Reason": "No selected breakpoints are available for KDE.",
                }
            ]
        )

        return {
            "input_breakpoints": selected,
            "density": pd.DataFrame(),
            "peaks": pd.DataFrame(),
            "summary": empty_summary,
        }

    values = selected[settings["age_col"]].to_numpy(dtype=float)
    weights = selected["KDE_weight"].to_numpy(dtype=float)

    bandwidth = get_bandwidth(
        values=values,
        weights=weights,
        bandwidth_setting=settings["bandwidth_kyr"],
    )

    grid = build_density_grid(
        age_min_kyr=settings["age_min_kyr"],
        age_max_kyr=settings["age_max_kyr"],
        grid_step_kyr=settings["grid_step_kyr"],
    )

    density = weighted_kde_density(
        grid=grid,
        values=values,
        weights=weights,
        bandwidth=bandwidth,
    )

    peak_indices, properties = detect_density_peaks(
        grid=grid,
        density=density,
        min_prominence_fraction=settings["min_prominence_fraction"],
        min_distance_kyr=settings["min_distance_kyr"],
        top_n_peaks=settings["top_n_peaks"],
    )

    density_table = pd.DataFrame(
        {
            "Age_kyr": grid,
            "Age_Ma": grid / 1000.0,
            "KDE_density": density,
        }
    )

    peak_table = build_peak_table(
        selected_breakpoints=selected,
        grid=grid,
        density=density,
        peak_indices=peak_indices,
        properties=properties,
        settings=settings,
        bandwidth=bandwidth,
    )

    summary = pd.DataFrame(
        [
            {
                "Status": "success",
                "N_selected_breakpoints": int(len(selected)),
                "N_consensus_peaks": int(len(peak_table)),
                "Bandwidth_kyr": float(bandwidth),
                "Age_min_kyr": settings["age_min_kyr"],
                "Age_max_kyr": settings["age_max_kyr"],
                "Grid_step_kyr": settings["grid_step_kyr"],
                "Significant_only": settings["significant_only"],
                "Fallback_to_all_if_empty": settings["fallback_to_all_if_empty"],
                "Use_confidence_weight": settings["use_confidence_weight"],
                "Min_prominence_fraction": settings["min_prominence_fraction"],
                "Min_distance_kyr": settings["min_distance_kyr"],
                "SciPy_signal_available": SCIPY_SIGNAL_AVAILABLE,
            }
        ]
    )

    return {
        "input_breakpoints": selected,
        "density": density_table,
        "peaks": peak_table,
        "summary": summary,
    }


def run_kde_analysis(
    pwlf_breakpoint_table: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """
    Run KDE analysis from PWLF breakpoint table.

    Important:
    KDE is performed separately for each RoC method.

    Workflow:
        PWLF breakpoints
            -> group by Method
            -> KDE for IBR
            -> KDE for TS
            -> KDE for IQR

    Returns
    -------
    dict
        {
            "input_breakpoints": combined selected breakpoint table with Method column,
            "density": combined KDE density table with Method column,
            "peaks": combined KDE peak table with Method column,
            "summary": combined KDE summary table with Method column
        }
    """
    if pwlf_breakpoint_table is None or pwlf_breakpoint_table.empty:
        return {
            "input_breakpoints": pd.DataFrame(),
            "density": pd.DataFrame(),
            "peaks": pd.DataFrame(),
            "summary": pd.DataFrame(
                [
                    {
                        "Method": "NA",
                        "Status": "empty",
                        "Reason": "No PWLF breakpoints are available for KDE.",
                    }
                ]
            ),
        }

    if "Method" not in pwlf_breakpoint_table.columns:
        result = run_consensus_kde(
            breakpoint_table=pwlf_breakpoint_table,
            config=config,
        )

        output = {}

        for key, table in result.items():
            if table is None or table.empty:
                output[key] = table
                continue

            table = table.copy()
            table.insert(0, "Method", "ALL")
            output[key] = table

        return output

    output_tables = {
        "input_breakpoints": [],
        "density": [],
        "peaks": [],
        "summary": [],
    }

    method_names = (
        pwlf_breakpoint_table["Method"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    method_names = sorted(method_names)

    for method_name in method_names:
        method_table = pwlf_breakpoint_table[
            pwlf_breakpoint_table["Method"].astype(str) == method_name
        ].copy()

        if method_table.empty:
            continue

        result = run_consensus_kde(
            breakpoint_table=method_table,
            config=config,
        )

        for key, table in result.items():
            if table is None or table.empty:
                continue

            table = table.copy()

            if "Method" not in table.columns:
                table.insert(0, "Method", method_name)
            else:
                table["Method"] = method_name

            output_tables[key].append(table)

    combined_output = {}

    for key, tables in output_tables.items():
        if tables:
            combined_output[key] = pd.concat(tables, ignore_index=True)
        else:
            combined_output[key] = pd.DataFrame()

    return combined_output