"""
Merge utilities for multi-timescale RoC results.

This module merges individual rate tables from multiple analytical time scales
into one wide-format table.

Input example:
    {
        100.0: DataFrame with columns ["Age_kyr", "Rate"],
        200.0: DataFrame with columns ["Age_kyr", "Rate"],
        ...
    }

Output example:
    Age_kyr | Timescale_100 | Timescale_200 | ... | Timescale_1000
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def format_width_label(width: float | int) -> str:
    """
    Convert a time-bin width to a clean column label.

    Examples
    --------
    100.0 -> "100"
    250.0 -> "250"
    12.5 -> "12p5"
    """
    width_float = float(width)

    if width_float.is_integer():
        return str(int(width_float))

    return str(width_float).replace(".", "p")


def make_timescale_column_name(
    width: float | int,
    column_prefix: str = "Timescale_",
) -> str:
    """
    Create a standardized timescale column name.
    """
    return f"{column_prefix}{format_width_label(width)}"


def validate_rate_table(
    table: pd.DataFrame,
    age_col: str = "Age_kyr",
    value_col: str = "Rate",
) -> pd.DataFrame:
    """
    Validate and clean one rate table.

    Parameters
    ----------
    table : pandas.DataFrame
        Input rate table.
    age_col : str, default "Age_kyr"
        Age column name.
    value_col : str, default "Rate"
        Rate column name.

    Returns
    -------
    pandas.DataFrame
        Cleaned table with numeric age and value columns.
    """
    required_columns = {age_col, value_col}

    if not required_columns.issubset(table.columns):
        missing = sorted(required_columns - set(table.columns))
        raise KeyError(f"Missing required columns in rate table: {missing}")

    clean = table[[age_col, value_col]].copy()
    clean[age_col] = pd.to_numeric(clean[age_col], errors="coerce")
    clean[value_col] = pd.to_numeric(clean[value_col], errors="coerce")
    clean = clean.dropna(subset=[age_col, value_col])

    if clean.empty:
        return pd.DataFrame(columns=[age_col, value_col])

    clean = (
        clean
        .groupby(age_col, as_index=False, sort=False)[value_col]
        .mean()
        .sort_values(age_col, ascending=True)
        .reset_index(drop=True)
    )

    return clean


def merge_timescale_roc_tables(
    tables_by_width: dict[float, pd.DataFrame],
    age_col: str = "Age_kyr",
    value_col: str = "Rate",
    output_age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> pd.DataFrame:
    """
    Merge rate tables from multiple analytical time scales.

    Parameters
    ----------
    tables_by_width : dict
        Dictionary whose keys are time-bin widths and values are rate tables.
    age_col : str, default "Age_kyr"
        Age column name in each input table.
    value_col : str, default "Rate"
        Value column name in each input table.
    output_age_col : str, default "Age_kyr"
        Age column name in the merged output table.
    column_prefix : str, default "Timescale_"
        Prefix for timescale columns.

    Returns
    -------
    pandas.DataFrame
        Wide-format merged table.
    """
    if not tables_by_width:
        return pd.DataFrame(columns=[output_age_col])

    merged_table = None

    for width in sorted(tables_by_width.keys(), key=float):
        table = tables_by_width[width]

        clean = validate_rate_table(
            table=table,
            age_col=age_col,
            value_col=value_col,
        )

        timescale_col = make_timescale_column_name(
            width=width,
            column_prefix=column_prefix,
        )

        clean = clean.rename(
            columns={
                age_col: output_age_col,
                value_col: timescale_col,
            }
        )

        if merged_table is None:
            merged_table = clean
        else:
            merged_table = pd.merge(
                merged_table,
                clean,
                on=output_age_col,
                how="outer",
            )

    if merged_table is None:
        return pd.DataFrame(columns=[output_age_col])

    merged_table = (
        merged_table
        .sort_values(output_age_col, ascending=True)
        .reset_index(drop=True)
    )

    return merged_table


def merge_all_methods_rate_tables(
    rate_tables_by_method: dict[str, dict[float, pd.DataFrame]],
    age_col: str = "Age_kyr",
    value_col: str = "Rate",
    output_age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> dict[str, pd.DataFrame]:
    """
    Merge rate tables for all RoC methods.

    Parameters
    ----------
    rate_tables_by_method : dict
        {
            "IBR": {100.0: DataFrame, 200.0: DataFrame, ...},
            "TS":  {100.0: DataFrame, 200.0: DataFrame, ...},
            "IQR": {100.0: DataFrame, 200.0: DataFrame, ...}
        }

    Returns
    -------
    dict
        {
            "IBR": merged DataFrame,
            "TS": merged DataFrame,
            "IQR": merged DataFrame
        }
    """
    merged = {}

    for method_name, tables_by_width in rate_tables_by_method.items():
        merged[method_name] = merge_timescale_roc_tables(
            tables_by_width=tables_by_width,
            age_col=age_col,
            value_col=value_col,
            output_age_col=output_age_col,
            column_prefix=column_prefix,
        )

    return merged


def read_rate_tables_from_directory(
    input_dir: str | Path,
    method_name: str,
    suffix: str = "kyr.xlsx",
    age_col: str = "Age_kyr",
    value_col: str = "Rate",
) -> dict[float, pd.DataFrame]:
    """
    Read saved rate tables from a directory.

    This function is optional and useful when merging existing Excel outputs
    without rerunning the full workflow.

    Expected filename examples:
        IBR_rate_100kyr.xlsx
        TS_rate_200kyr.xlsx
        IQR_rate_1000kyr.xlsx

    Parameters
    ----------
    input_dir : str or pathlib.Path
        Directory containing saved rate tables.
    method_name : str
        Method name, such as "IBR", "TS", or "IQR".
    suffix : str, default "kyr.xlsx"
        Filename suffix.
    age_col : str, default "Age_kyr"
        Age column name.
    value_col : str, default "Rate"
        Rate column name.

    Returns
    -------
    dict
        Dictionary of {width: DataFrame}.
    """
    input_dir = Path(input_dir)

    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory not found: {input_dir}")

    method_name = method_name.upper()
    pattern = f"{method_name}_rate_*{suffix}"

    tables = {}

    for file_path in sorted(input_dir.glob(pattern)):
        stem = file_path.stem
        width_text = stem.replace(f"{method_name}_rate_", "")

        if width_text.endswith("kyr"):
            width_text = width_text[:-3]

        width_text = width_text.replace("p", ".")

        try:
            width = float(width_text)
        except ValueError:
            continue

        table = pd.read_excel(file_path)
        table = validate_rate_table(
            table=table,
            age_col=age_col,
            value_col=value_col,
        )

        tables[width] = table

    return tables


def build_merged_summary_table(
    merged_tables_by_method: dict[str, pd.DataFrame],
    age_col: str = "Age_kyr",
) -> pd.DataFrame:
    """
    Build a simple summary table for merged outputs.

    Parameters
    ----------
    merged_tables_by_method : dict
        Dictionary of merged tables by method.
    age_col : str, default "Age_kyr"
        Age column name.

    Returns
    -------
    pandas.DataFrame
        Summary table.
    """
    rows: list[dict[str, Any]] = []

    for method_name, table in merged_tables_by_method.items():
        timescale_columns = [col for col in table.columns if col != age_col]

        rows.append(
            {
                "Method": method_name,
                "N_age_rows": int(len(table)),
                "N_timescales": int(len(timescale_columns)),
                "Timescale_columns": ", ".join(timescale_columns),
            }
        )

    return pd.DataFrame(rows)