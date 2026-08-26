"""
Input/output utilities for the RoC workflow.

This module handles:
- loading YAML configuration files
- loading raw or validated Excel input data
- validating required age-value columns
- creating output directories
- saving workflow results to Excel files
- writing run summaries
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load YAML configuration file.

    Parameters
    ----------
    config_path : str or pathlib.Path
        Path to a YAML configuration file.

    Returns
    -------
    dict
        Configuration dictionary.
    """
    config_path = Path(config_path)

    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if config is None:
        raise ValueError(f"Config file is empty: {config_path}")

    if not isinstance(config, dict):
        raise TypeError("Config file must define a YAML dictionary.")

    return config


def resolve_path(path_value: str | Path, base_dir: str | Path | None = None) -> Path:
    """
    Resolve a path.

    Relative paths are resolved relative to base_dir.
    Absolute paths are returned directly.

    Parameters
    ----------
    path_value : str or pathlib.Path
        Input path.
    base_dir : str or pathlib.Path, optional
        Base directory for relative paths.

    Returns
    -------
    pathlib.Path
        Resolved path.
    """
    path = Path(path_value)

    if path.is_absolute():
        return path

    if base_dir is None:
        base_dir = Path.cwd()
    else:
        base_dir = Path(base_dir)

    return (base_dir / path).resolve()


def get_input_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get input settings from config.
    """
    input_config = config.get("input", {})

    return {
        "file": input_config.get("file", "data/O.xlsx"),
        "sheet": input_config.get("sheet", 0),
        "age_column": input_config.get("age_column", "Age"),
        "value_column": input_config.get("value_column", "Value"),
    }


def get_output_root(
    config: dict[str, Any],
    project_root: str | Path | None = None,
) -> Path:
    """
    Get output root directory from config.
    """
    output_config = config.get("output", {})
    output_dir = output_config.get("directory", "outputs")

    return resolve_path(output_dir, base_dir=project_root)


def validate_input_dataframe(
    data: pd.DataFrame,
    age_col: str = "Age",
    value_col: str = "Value",
) -> pd.DataFrame:
    """
    Validate and clean input data table.

    This function keeps only the selected age-value columns, converts them
    to numeric values, removes invalid rows, averages duplicate ages, and
    sorts the result by age.

    Parameters
    ----------
    data : pandas.DataFrame
        Input data.
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
        raise KeyError(
            f"Input file is missing required columns: {missing}. "
            f"Current columns are: {list(data.columns)}"
        )

    clean = data[[age_col, value_col]].copy()
    clean[age_col] = pd.to_numeric(clean[age_col], errors="coerce")
    clean[value_col] = pd.to_numeric(clean[value_col], errors="coerce")
    clean = clean.dropna(subset=[age_col, value_col])

    if clean.empty:
        raise ValueError(
            "No valid numeric age-value pairs were found in the input file."
        )

    clean = (
        clean
        .groupby(age_col, as_index=False, sort=False)[value_col]
        .mean()
        .sort_values(age_col, ascending=True)
        .reset_index(drop=True)
    )

    return clean


def load_raw_input_data(
    file_path: str | Path,
    sheet: int | str = 0,
) -> pd.DataFrame:
    """
    Load raw input Excel data without cleaning or validation.

    This function is used before the preprocessing step, so that optional
    preprocessing operations such as sorting and Z-score normalization can be
    controlled by the workflow configuration.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Excel file path.
    sheet : int or str, default 0
        Excel sheet name or index.

    Returns
    -------
    pandas.DataFrame
        Raw dataframe loaded from Excel.
    """
    file_path = Path(file_path)

    if not file_path.is_file():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    return pd.read_excel(file_path, sheet_name=sheet)


def load_input_data(
    file_path: str | Path,
    sheet: int | str = 0,
    age_col: str = "Age",
    value_col: str = "Value",
) -> pd.DataFrame:
    """
    Load input Excel data and return a validated age-value table.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Excel file path.
    sheet : int or str, default 0
        Excel sheet name or index.
    age_col : str, default "Age"
        Age column name.
    value_col : str, default "Value"
        Value column name.

    Returns
    -------
    pandas.DataFrame
        Cleaned input data.
    """
    raw_data = load_raw_input_data(
        file_path=file_path,
        sheet=sheet,
    )

    return validate_input_dataframe(
        data=raw_data,
        age_col=age_col,
        value_col=value_col,
    )


def load_input_data_from_config(
    config: dict[str, Any],
    project_root: str | Path | None = None,
) -> pd.DataFrame:
    """
    Load validated input data according to the config file.

    This function performs validation, numeric conversion, duplicate-age
    averaging, and age sorting.
    """
    input_settings = get_input_settings(config)

    input_file = resolve_path(
        input_settings["file"],
        base_dir=project_root,
    )

    return load_input_data(
        file_path=input_file,
        sheet=input_settings["sheet"],
        age_col=input_settings["age_column"],
        value_col=input_settings["value_column"],
    )


def load_raw_input_data_from_config(
    config: dict[str, Any],
    project_root: str | Path | None = None,
) -> pd.DataFrame:
    """
    Load raw input data according to the config file.

    Unlike load_input_data_from_config(), this function does not validate,
    clean, group, or sort the input table. It is intended for use before
    the preprocessing step.
    """
    input_settings = get_input_settings(config)

    input_file = resolve_path(
        input_settings["file"],
        base_dir=project_root,
    )

    return load_raw_input_data(
        file_path=input_file,
        sheet=input_settings["sheet"],
    )


def ensure_directory(path: str | Path) -> Path:
    """
    Create a directory if it does not exist.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    return path


def prepare_output_directories(output_root: str | Path) -> dict[str, Path]:
    """
    Prepare standard output directory structure.

    Parameters
    ----------
    output_root : str or pathlib.Path
        Root output directory.

    Returns
    -------
    dict
        Dictionary of output directories.
    """
    output_root = ensure_directory(output_root)

    dirs = {
        "root": output_root,
        "preprocessed": output_root / "00_preprocessed",
        "timebin": output_root / "01_timebin",
        "interpolated": output_root / "02_interpolated",
        "rate": output_root / "03_rate",
        "merged": output_root / "04_merged",
        "lri": output_root / "05_lri",
        "normalized": output_root / "06_normalized",
        "metrics": output_root / "07_metrics",
        "pwlf": output_root / "08_pwlf",
        "kde": output_root / "09_kde",
        "phase": output_root / "10_phase",
        "sensitivity": output_root / "11_sampling_sensitivity",
        "figures": output_root / "figures",
        "logs": output_root / "logs",
    }

    for directory in dirs.values():
        ensure_directory(directory)

    return dirs


def format_width_label(width: float | int) -> str:
    """
    Convert a time-bin width to a clean file-label string.

    Examples
    --------
    50.0 -> "50"
    1000.0 -> "1000"
    """
    width_float = float(width)

    if width_float.is_integer():
        return str(int(width_float))

    return str(width_float).replace(".", "p")


def save_excel(
    table: pd.DataFrame,
    file_path: str | Path,
    sheet_name: str = "Sheet1",
    index: bool = False,
) -> Path:
    """
    Save a DataFrame to Excel.
    """
    file_path = Path(file_path)
    ensure_directory(file_path.parent)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        table.to_excel(writer, index=index, sheet_name=sheet_name)

    return file_path


def save_tables_by_width(
    tables_by_width: dict[float, pd.DataFrame],
    output_dir: str | Path,
    filename_pattern: str,
    sheet_name: str,
) -> list[Path]:
    """
    Save multiple DataFrames whose keys are time-bin widths.

    Parameters
    ----------
    tables_by_width : dict
        {timebin_width: DataFrame}
    output_dir : str or pathlib.Path
        Output directory.
    filename_pattern : str
        Filename pattern containing "{width}", for example:
        "IBR_rate_{width}kyr.xlsx"
    sheet_name : str
        Excel sheet name.

    Returns
    -------
    list[pathlib.Path]
        Saved file paths.
    """
    output_dir = ensure_directory(output_dir)
    saved_paths = []

    for width, table in sorted(tables_by_width.items()):
        width_label = format_width_label(width)
        filename = filename_pattern.format(width=width_label)
        out_path = output_dir / filename

        save_excel(
            table=table,
            file_path=out_path,
            sheet_name=sheet_name,
            index=False,
        )

        saved_paths.append(out_path)

    return saved_paths


def save_method_outputs(
    method_name: str,
    method_result: dict[str, dict[float, pd.DataFrame]],
    output_dirs: dict[str, Path],
) -> dict[str, list[Path]]:
    """
    Save timebin, interpolated, and rate tables for one method.

    Parameters
    ----------
    method_name : str
        Method name, such as "IBR", "TS", or "IQR".
    method_result : dict
        Output from run_ibr_workflow(), run_ts_workflow(), or run_iqr_workflow().
    output_dirs : dict
        Output directory dictionary returned by prepare_output_directories().

    Returns
    -------
    dict
        Saved file paths grouped by stage.
    """
    method_name = method_name.upper()
    saved = {}

    if "timebin" in method_result:
        out_dir = output_dirs["timebin"] / method_name
        saved["timebin"] = save_tables_by_width(
            tables_by_width=method_result["timebin"],
            output_dir=out_dir,
            filename_pattern=f"{method_name}_timebin_{{width}}kyr.xlsx",
            sheet_name="timebin",
        )

    if "interpolated" in method_result:
        out_dir = output_dirs["interpolated"] / method_name
        saved["interpolated"] = save_tables_by_width(
            tables_by_width=method_result["interpolated"],
            output_dir=out_dir,
            filename_pattern=f"{method_name}_interpolated_{{width}}kyr.xlsx",
            sheet_name="interpolated",
        )

    if "rate" in method_result:
        out_dir = output_dirs["rate"] / method_name
        saved["rate"] = save_tables_by_width(
            tables_by_width=method_result["rate"],
            output_dir=out_dir,
            filename_pattern=f"{method_name}_rate_{{width}}kyr.xlsx",
            sheet_name="rate",
        )

    return saved


def save_all_roc_outputs(
    roc_results: dict[str, dict[str, dict[float, pd.DataFrame]]],
    output_dirs: dict[str, Path],
) -> dict[str, dict[str, list[Path]]]:
    """
    Save all IBR, TS, and IQR outputs.
    """
    saved = {}

    for method_name, method_result in roc_results.items():
        saved[method_name] = save_method_outputs(
            method_name=method_name,
            method_result=method_result,
            output_dirs=output_dirs,
        )

    return saved


def write_run_summary(
    summary_lines: list[str],
    output_dirs: dict[str, Path],
    filename: str = "run_summary.txt",
) -> Path:
    """
    Write a simple text run summary.
    """
    log_path = output_dirs["logs"] / filename

    with log_path.open("w", encoding="utf-8") as file:
        for line in summary_lines:
            file.write(str(line) + "\n")

    return log_path