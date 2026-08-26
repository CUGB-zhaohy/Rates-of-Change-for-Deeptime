"""
Data preprocessing utilities for the RoC workflow.

This module handles:
- validation of user-defined age and value columns
- numeric conversion
- removal of invalid rows
- optional age sorting
- duplicate-age averaging
- optional Z-score normalization
- preparation of the active value column for downstream RoC analysis
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def get_preprocess_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Read preprocessing settings from the workflow configuration.
    """
    preprocess_config = config.get("preprocess", {})

    return {
        "sort_by_age": bool(preprocess_config.get("sort_by_age", True)),
        "use_zscore": bool(preprocess_config.get("use_zscore", False)),
        "zscore_column": str(preprocess_config.get("zscore_column", "Z_score")),
        "save_preprocessed": bool(preprocess_config.get("save_preprocessed", True)),
    }


def preprocess_input_data(
    data: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, str, dict[str, Any]]:
    """
    Preprocess raw input data before RoC calculation.

    Parameters
    ----------
    data : pandas.DataFrame
        Raw dataframe loaded from Excel.
    config : dict
        Workflow configuration dictionary.

    Returns
    -------
    processed_data : pandas.DataFrame
        Preprocessed dataframe. It contains at least Age and Value columns.
        If Z-score is enabled, it also contains the Z-score column.
    active_value_column : str
        Column name used for downstream RoC calculation.
        This is either the original value column or the Z-score column.
    summary : dict
        Summary of preprocessing actions and data counts.
    """
    input_config = config.get("input", {})
    settings = get_preprocess_settings(config)

    age_col = input_config.get("age_column", "Age")
    value_col = input_config.get("value_column", "Value")
    zscore_col = settings["zscore_column"]

    if age_col not in data.columns:
        raise ValueError(
            f"Age column was not found: {age_col}. "
            f"Available columns: {list(data.columns)}"
        )

    if value_col not in data.columns:
        raise ValueError(
            f"Value column was not found: {value_col}. "
            f"Available columns: {list(data.columns)}"
        )

    processed = data[[age_col, value_col]].copy()

    n_original = len(processed)

    processed[age_col] = pd.to_numeric(processed[age_col], errors="coerce")
    processed[value_col] = pd.to_numeric(processed[value_col], errors="coerce")

    processed = processed.dropna(subset=[age_col, value_col]).reset_index(drop=True)

    n_after_dropna = len(processed)

    if processed.empty:
        raise ValueError(
            "No valid numeric age-value pairs were found after preprocessing."
        )

    # Average duplicate ages to keep one value per age.
    processed = (
        processed
        .groupby(age_col, as_index=False, sort=False)[value_col]
        .mean()
    )

    n_after_duplicate_average = len(processed)

    if settings["sort_by_age"]:
        processed = processed.sort_values(age_col, ascending=True).reset_index(drop=True)

    active_value_column = value_col
    zscore_mean = np.nan
    zscore_std = np.nan

    if settings["use_zscore"]:
        values = processed[value_col].to_numpy(dtype=float)

        zscore_mean = float(np.mean(values))
        zscore_std = float(np.std(values, ddof=0))

        if not np.isfinite(zscore_std) or zscore_std == 0:
            raise ValueError(
                "Cannot calculate Z-score because the standard deviation "
                "of the value column is zero or invalid."
            )

        processed[zscore_col] = (processed[value_col] - zscore_mean) / zscore_std
        active_value_column = zscore_col

    summary = {
        "age_column": age_col,
        "original_value_column": value_col,
        "active_value_column": active_value_column,
        "sort_by_age": settings["sort_by_age"],
        "use_zscore": settings["use_zscore"],
        "zscore_column": zscore_col if settings["use_zscore"] else None,
        "n_original_rows": int(n_original),
        "n_valid_rows_after_dropna": int(n_after_dropna),
        "n_rows_after_duplicate_age_average": int(n_after_duplicate_average),
        "n_removed_invalid_rows": int(n_original - n_after_dropna),
        "n_merged_duplicate_age_rows": int(n_after_dropna - n_after_duplicate_average),
        "zscore_mean": zscore_mean,
        "zscore_std": zscore_std,
    }

    return processed, active_value_column, summary