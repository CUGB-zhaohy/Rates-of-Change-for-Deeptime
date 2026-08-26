"""
Interpolation utilities for the RoC workflow.

This module supports three interpolation modes:

1. none
   No interpolation is performed. The output column is copied directly from
   the original target column.

2. linear
   Missing values are filled by linear interpolation along the age axis.

3. weighted
   Missing values are filled by distance-count weighted interpolation:
       weight = Counts^alpha / Distance^beta

The same interpolation interface is used for:
- IBR mean interpolation
- TS rate interpolation
- IQR value interpolation
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


SUPPORTED_INTERPOLATION_METHODS = {"none", "linear", "weighted"}
SUPPORTED_EDGE_MODES = {"nearest", "nan", "none", "zero", "0"}


def normalize_interpolation_method(method: str | None) -> str:
    """
    Normalize and validate interpolation method name.
    """
    if method is None:
        method = "weighted"

    method = str(method).strip().lower()

    alias_map = {
        "no": "none",
        "no_interpolation": "none",
        "no interpolation": "none",
        "linear_interpolation": "linear",
        "linear interpolation": "linear",
        "weighted_interpolation": "weighted",
        "weighted interpolation": "weighted",
        "distance_count_weighted": "weighted",
        "distance-count weighted": "weighted",
    }

    method = alias_map.get(method, method)

    if method not in SUPPORTED_INTERPOLATION_METHODS:
        raise ValueError(
            f"Unsupported interpolation method: {method}. "
            f"Supported methods are: {sorted(SUPPORTED_INTERPOLATION_METHODS)}"
        )

    return method


def normalize_edge_mode(edge_mode: str | None) -> str:
    """
    Normalize and validate edge handling mode.
    """
    if edge_mode is None:
        edge_mode = "nearest"

    edge_mode = str(edge_mode).strip().lower()

    if edge_mode not in SUPPORTED_EDGE_MODES:
        raise ValueError(
            f"Unsupported edge_mode: {edge_mode}. "
            f"Supported edge modes are: {sorted(SUPPORTED_EDGE_MODES)}"
        )

    if edge_mode == "none":
        edge_mode = "nan"

    if edge_mode == "0":
        edge_mode = "zero"

    return edge_mode


def _validate_required_columns(
    table: pd.DataFrame,
    required_columns: list[str],
):
    """
    Validate that required columns exist in a table.
    """
    missing = [column for column in required_columns if column not in table.columns]

    if missing:
        raise KeyError(
            f"Interpolation table is missing required columns: {missing}. "
            f"Current columns are: {list(table.columns)}"
        )


def _prepare_sorted_table(
    table: pd.DataFrame,
    age_col: str,
) -> tuple[pd.DataFrame, pd.Index]:
    """
    Return a copy sorted by age and the original index order.

    Interpolation is easier and safer on a sorted age axis, but the final
    result is restored to the original row order.
    """
    original_index = table.index.copy()

    sorted_table = (
        table
        .copy()
        .sort_values(age_col, ascending=True)
    )

    return sorted_table, original_index


def _restore_original_order(
    sorted_table: pd.DataFrame,
    original_index: pd.Index,
) -> pd.DataFrame:
    """
    Restore dataframe to the original index order.
    """
    restored = sorted_table.loc[original_index].copy()
    restored = restored.reset_index(drop=True)

    return restored


def _apply_edge_mode(
    values: pd.Series,
    edge_mode: str,
) -> pd.Series:
    """
    Apply edge handling after linear interpolation.
    """
    edge_mode = normalize_edge_mode(edge_mode)

    output = values.copy()

    if edge_mode == "nearest":
        output = output.ffill().bfill()
    elif edge_mode == "zero":
        output = output.fillna(0.0)
    elif edge_mode == "nan":
        pass

    return output


def interpolate_none(
    table: pd.DataFrame,
    target_col: str,
    output_col: str,
) -> pd.DataFrame:
    """
    Copy the target column to the output column without interpolation.
    """
    output = table.copy()
    output[output_col] = pd.to_numeric(output[target_col], errors="coerce")

    return output


def interpolate_linear(
    table: pd.DataFrame,
    target_col: str,
    output_col: str,
    age_col: str = "Age_node",
    edge_mode: str = "nearest",
) -> pd.DataFrame:
    """
    Interpolate missing values linearly along the age axis.

    Internal missing values are filled by linear interpolation. Edge values are
    controlled by edge_mode:
    - nearest: fill leading/trailing NaNs using nearest valid values
    - nan: keep leading/trailing NaNs
    - zero: fill remaining NaNs with zero
    """
    _validate_required_columns(
        table=table,
        required_columns=[age_col, target_col],
    )

    sorted_table, original_index = _prepare_sorted_table(
        table=table,
        age_col=age_col,
    )

    sorted_table[target_col] = pd.to_numeric(
        sorted_table[target_col],
        errors="coerce",
    )

    values = sorted_table[target_col].copy()

    if values.notna().sum() == 0:
        sorted_table[output_col] = np.nan
        return _restore_original_order(sorted_table, original_index)

    if values.notna().sum() == 1:
        if normalize_edge_mode(edge_mode) == "nearest":
            sorted_table[output_col] = values.ffill().bfill()
        elif normalize_edge_mode(edge_mode) == "zero":
            sorted_table[output_col] = values.fillna(0.0)
        else:
            sorted_table[output_col] = values

        return _restore_original_order(sorted_table, original_index)

    interpolated = values.interpolate(
        method="linear",
        limit_area="inside",
    )

    interpolated = _apply_edge_mode(
        values=interpolated,
        edge_mode=edge_mode,
    )

    sorted_table[output_col] = interpolated

    return _restore_original_order(sorted_table, original_index)


def _weighted_value_for_one_age(
    target_age: float,
    valid_ages: np.ndarray,
    valid_values: np.ndarray,
    valid_counts: np.ndarray,
    count_alpha: float,
    distance_beta: float,
    edge_mode: str,
) -> float:
    """
    Calculate one distance-count weighted interpolated value.
    """
    edge_mode = normalize_edge_mode(edge_mode)

    if valid_ages.size == 0:
        return np.nan

    min_valid_age = float(np.min(valid_ages))
    max_valid_age = float(np.max(valid_ages))

    is_outside = target_age < min_valid_age or target_age > max_valid_age

    if is_outside:
        if edge_mode == "nan":
            return np.nan

        if edge_mode == "zero":
            return 0.0

        if edge_mode == "nearest":
            nearest_index = int(np.argmin(np.abs(valid_ages - target_age)))
            return float(valid_values[nearest_index])

    distances = np.abs(valid_ages - target_age)

    exact_match = distances == 0

    if np.any(exact_match):
        return float(valid_values[exact_match][0])

    safe_counts = np.asarray(valid_counts, dtype=float)
    safe_counts = np.where(np.isfinite(safe_counts), safe_counts, 1.0)
    safe_counts = np.where(safe_counts > 0, safe_counts, 1.0)

    safe_distances = np.asarray(distances, dtype=float)
    safe_distances = np.where(safe_distances > 0, safe_distances, np.nan)

    count_weights = safe_counts ** float(count_alpha)

    if float(distance_beta) == 0:
        distance_weights = np.ones_like(safe_distances, dtype=float)
    else:
        distance_weights = 1.0 / (safe_distances ** float(distance_beta))

    weights = count_weights * distance_weights

    valid_weight_mask = np.isfinite(weights) & (weights > 0)

    if not np.any(valid_weight_mask):
        return np.nan

    weights = weights[valid_weight_mask]
    values = valid_values[valid_weight_mask]

    return float(np.sum(weights * values) / np.sum(weights))


def interpolate_weighted(
    table: pd.DataFrame,
    target_col: str,
    output_col: str,
    age_col: str = "Age_node",
    counts_col: str = "Counts",
    count_alpha: float = 1.0,
    distance_beta: float = 1.0,
    edge_mode: str = "nearest",
) -> pd.DataFrame:
    """
    Fill missing values using distance-count weighted interpolation.

    For a missing target value at age t, all valid age nodes contribute with:

        weight = Counts^count_alpha / Distance^distance_beta

    Existing valid values are preserved.
    """
    _validate_required_columns(
        table=table,
        required_columns=[age_col, target_col],
    )

    output = table.copy()

    output[age_col] = pd.to_numeric(output[age_col], errors="coerce")
    output[target_col] = pd.to_numeric(output[target_col], errors="coerce")

    if counts_col not in output.columns:
        output[counts_col] = 1.0

    output[counts_col] = pd.to_numeric(output[counts_col], errors="coerce")

    values = output[target_col].to_numpy(dtype=float)
    ages = output[age_col].to_numpy(dtype=float)
    counts = output[counts_col].to_numpy(dtype=float)

    valid_mask = (
        np.isfinite(ages)
        & np.isfinite(values)
    )

    valid_ages = ages[valid_mask]
    valid_values = values[valid_mask]
    valid_counts = counts[valid_mask]

    interpolated_values = values.copy()

    missing_mask = (
        np.isfinite(ages)
        & ~np.isfinite(values)
    )

    for row_index in np.where(missing_mask)[0]:
        interpolated_values[row_index] = _weighted_value_for_one_age(
            target_age=float(ages[row_index]),
            valid_ages=valid_ages,
            valid_values=valid_values,
            valid_counts=valid_counts,
            count_alpha=count_alpha,
            distance_beta=distance_beta,
            edge_mode=edge_mode,
        )

    output[output_col] = interpolated_values

    return output


def interpolate_table(
    table: pd.DataFrame,
    target_col: str,
    output_col: str,
    age_col: str = "Age_node",
    counts_col: str = "Counts",
    method: str = "weighted",
    count_alpha: float = 1.0,
    distance_beta: float = 1.0,
    edge_mode: str = "nearest",
) -> pd.DataFrame:
    """
    Interpolate one table according to the selected method.
    """
    method = normalize_interpolation_method(method)

    if method == "none":
        _validate_required_columns(
            table=table,
            required_columns=[target_col],
        )

        return interpolate_none(
            table=table,
            target_col=target_col,
            output_col=output_col,
        )

    if method == "linear":
        return interpolate_linear(
            table=table,
            target_col=target_col,
            output_col=output_col,
            age_col=age_col,
            edge_mode=edge_mode,
        )

    if method == "weighted":
        return interpolate_weighted(
            table=table,
            target_col=target_col,
            output_col=output_col,
            age_col=age_col,
            counts_col=counts_col,
            count_alpha=count_alpha,
            distance_beta=distance_beta,
            edge_mode=edge_mode,
        )

    raise ValueError(f"Unsupported interpolation method: {method}")


def interpolate_tables_for_widths(
    tables_by_width: dict[float, pd.DataFrame],
    target_col: str,
    output_col: str,
    age_col: str = "Age_node",
    counts_col: str = "Counts",
    method: str = "weighted",
    count_alpha: float = 1.0,
    distance_beta: float = 1.0,
    edge_mode: str = "nearest",
) -> dict[float, pd.DataFrame]:
    """
    Interpolate multiple time-bin tables.

    Parameters
    ----------
    tables_by_width
        Dictionary of {timebin_width: table}.
    target_col
        Source column to be interpolated.
    output_col
        Output column after interpolation.
    age_col
        Age-node column.
    counts_col
        Count column used by weighted interpolation.
    method
        Interpolation method: "none", "linear", or "weighted".
    count_alpha
        Exponent for count weighting in weighted interpolation.
    distance_beta
        Exponent for distance weighting in weighted interpolation.
    edge_mode
        Edge handling mode: "nearest", "nan", or "zero".

    Returns
    -------
    dict
        Dictionary of {timebin_width: interpolated_table}.
    """
    interpolated_tables = {}

    for width, table in sorted(tables_by_width.items()):
        interpolated_tables[float(width)] = interpolate_table(
            table=table,
            target_col=target_col,
            output_col=output_col,
            age_col=age_col,
            counts_col=counts_col,
            method=method,
            count_alpha=count_alpha,
            distance_beta=distance_beta,
            edge_mode=edge_mode,
        )

    return interpolated_tables