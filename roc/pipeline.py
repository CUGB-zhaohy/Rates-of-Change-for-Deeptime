"""
Pipeline controller for the RoC workflow.

This module controls the calculation order of different RoC-related methods.

Important method-specific workflows:

IBR:
    raw data
    -> time-bin mean
    -> interpolate missing mean values
    -> calculate inter-bin rate

TS:
    raw data
    -> calculate Theil-Sen slope within each time bin
    -> interpolate missing TS values

IQR:
    raw data
    -> calculate IQR within each time bin
    -> interpolate missing IQR values

Current full workflow:
    1. Run IBR / TS / IQR
    2. Merge multi-timescale rate tables
    3. Run LRI regression
    4. Generate time-scale-corrected relative RoC tables
    5. Calculate nTV and Gini metrics
    6. Run PWLF breakpoint detection
    7. Run method-specific KDE consensus breakpoint detection
    8. Calculate method-specific phase statistics
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .timebin import generate_age_nodes, compute_timebin_tables_for_widths
from .interpolation import interpolate_tables_for_widths
from .methods import (
    calculate_ibr_from_interpolated_mean,
    standardize_rate_series,
)
from .merge import merge_all_methods_rate_tables
from .lri import run_lri_for_all_methods, extract_normalized_tables
from .metrics import run_metrics_analysis
from .breakpoint import run_pwlf_analysis, get_breakpoint_settings
from .kde import run_kde_analysis
from .phase import run_phase_analysis


def _get_nested(config: dict[str, Any], section: str, key: str, default=None):
    """
    Safely get a nested config value.

    Example
    -------
    _get_nested(config, "timebin", "start_age_kyr", 67000)
    """
    return config.get(section, {}).get(key, default)

def _report_progress(progress_callback, percent: float, message: str):
    """
    Report progress to the GUI if a progress callback is provided.
    """
    if progress_callback is not None:
        progress_callback(percent, message)

def get_input_columns(config: dict[str, Any]) -> tuple[str, str]:
    """
    Get age and value column names from config.
    """
    age_col = _get_nested(config, "input", "age_column", "Age")
    value_col = _get_nested(config, "input", "value_column", "Value")

    return age_col, value_col


def get_timebin_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get time-bin settings from config.
    """
    start_age = _get_nested(config, "timebin", "start_age_kyr", 67000)
    end_age = _get_nested(config, "timebin", "end_age_kyr", 0)
    resolution = _get_nested(config, "timebin", "resolution_kyr", 10)
    widths = _get_nested(
        config,
        "timebin",
        "widths_kyr",
        list(range(50, 1001, 50)),
    )

    return {
        "start_age_kyr": float(start_age),
        "end_age_kyr": float(end_age),
        "resolution_kyr": float(resolution),
        "widths_kyr": [float(width) for width in widths],
    }


def get_interpolation_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get interpolation settings from config.

    Supported interpolation methods:
    - none
    - linear
    - weighted

    The default weighted method uses the nearest valid bin on each side of an
    internal missing target.
    """
    method = _get_nested(config, "interpolation", "method", "weighted")
    count_alpha = _get_nested(config, "interpolation", "count_weight_alpha", 1.0)
    distance_beta = _get_nested(config, "interpolation", "distance_weight_beta", 1.0)
    edge_mode = _get_nested(config, "interpolation", "edge_mode", "nearest")

    return {
        "method": str(method).strip().lower(),
        "count_alpha": float(count_alpha),
        "distance_beta": float(distance_beta),
        "edge_mode": edge_mode,
    }


def get_theilsen_alpha(config: dict[str, Any]) -> float:
    """
    Get Theil-Sen confidence level from config.
    """
    return float(_get_nested(config, "methods", "theilsen_alpha", 0.90))

def get_iqr_quartile_method(config: dict[str, Any]) -> str:
    """
    Get IQR quartile calculation method from config.

    Supported values:
    - exc: Excel QUARTILE.EXC / PERCENTILE.EXC
    - inc: Excel QUARTILE.INC / PERCENTILE.INC
    """
    method = _get_nested(config, "methods", "iqr_quartile_method", "exc")
    method = str(method).strip().lower()

    if method in {"exc", "exclusive", "quartile.exc", "percentile.exc"}:
        return "exc"

    if method in {"inc", "inclusive", "quartile.inc", "percentile.inc"}:
        return "inc"

    raise ValueError(
        "Unsupported methods.iqr_quartile_method. "
        "Please use 'exc' or 'inc'."
    )


def get_iqr_min_count(config: dict[str, Any]) -> int:
    """
    Get the minimum number of finite values required to calculate IQR.

    If a time bin contains fewer than this number of finite values,
    IQR will be returned as NaN.
    """
    min_count = int(_get_nested(config, "methods", "iqr_min_count", 5))

    if min_count < 1:
        raise ValueError(
            "methods.iqr_min_count must be an integer greater than or equal to 1."
        )

    return min_count

def should_run_method(config: dict[str, Any], method: str) -> bool:
    """
    Check whether a method should be run.

    Supported method values:
    - "ibr"
    - "ts"
    - "iqr"
    """
    method = method.strip().lower()

    default_map = {
        "ibr": True,
        "ts": True,
        "iqr": True,
    }

    key_map = {
        "ibr": "run_ibr",
        "ts": "run_ts",
        "iqr": "run_iqr",
    }

    if method not in key_map:
        raise ValueError(f"Unsupported method: {method}")

    return bool(
        _get_nested(
            config,
            "methods",
            key_map[method],
            default_map[method],
        )
    )


def should_run_analysis(
    config: dict[str, Any],
    analysis_key: str,
    default: bool = True,
) -> bool:
    """
    Check whether an analysis step should be run.

    Example
    -------
    should_run_analysis(config, "run_lri", default=True)
    """
    return bool(
        _get_nested(
            config,
            "analysis",
            analysis_key,
            default,
        )
    )


def build_age_nodes(config: dict[str, Any]):
    """
    Generate age nodes according to config.
    """
    settings = get_timebin_settings(config)

    return generate_age_nodes(
        start_age_kyr=settings["start_age_kyr"],
        end_age_kyr=settings["end_age_kyr"],
        resolution_kyr=settings["resolution_kyr"],
    )


def run_ibr_workflow(
    data: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, dict[float, pd.DataFrame]]:
    """
    Run the IBR workflow.

    Workflow
    --------
    raw data
        -> time-bin mean
        -> interpolate missing mean values
        -> calculate IBR

    Returns
    -------
    dict
        {
            "timebin": {width: mean_table},
            "interpolated": {width: interpolated_mean_table},
            "rate": {width: ibr_table}
        }
    """
    age_col, value_col = get_input_columns(config)
    timebin_settings = get_timebin_settings(config)
    interpolation_settings = get_interpolation_settings(config)
    iqr_quartile_method = get_iqr_quartile_method(config)
    iqr_min_count = get_iqr_min_count(config)

    age_nodes = build_age_nodes(config)
    widths = timebin_settings["widths_kyr"]

    mean_tables = compute_timebin_tables_for_widths(
        data=data,
        age_nodes=age_nodes,
        timebin_widths=widths,
        metric="mean",
        age_col=age_col,
        value_col=value_col,
        theilsen_alpha=get_theilsen_alpha(config),
    )

    interpolated_mean_tables = interpolate_tables_for_widths(
        tables_by_width=mean_tables,
        target_col="Mean_origin",
        output_col="Mean_interp",
        age_col="Age_node",
        counts_col="Counts",
        method=interpolation_settings["method"],
        count_alpha=interpolation_settings["count_alpha"],
        distance_beta=interpolation_settings["distance_beta"],
        edge_mode=interpolation_settings["edge_mode"],
    )

    ibr_tables = {}

    for width, table in interpolated_mean_tables.items():
        ibr_tables[float(width)] = calculate_ibr_from_interpolated_mean(
            df=table,
            age_col="Age_node",
            mean_col="Mean_interp",
            timebin_width=float(width),
            out_age_col="Age_kyr",
            out_rate_col="Rate",
        )

    return {
        "timebin": mean_tables,
        "interpolated": interpolated_mean_tables,
        "rate": ibr_tables,
    }


def run_ts_workflow(
    data: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, dict[float, pd.DataFrame]]:
    """
    Run the Theil-Sen workflow.

    Workflow
    --------
    raw data
        -> calculate Theil-Sen slope within each time bin
        -> interpolate missing TS values

    Returns
    -------
    dict
        {
            "timebin": {width: ts_table},
            "interpolated": {width: interpolated_ts_table},
            "rate": {width: standardized_ts_rate_table}
        }
    """
    age_col, value_col = get_input_columns(config)
    timebin_settings = get_timebin_settings(config)
    interpolation_settings = get_interpolation_settings(config)

    age_nodes = build_age_nodes(config)
    widths = timebin_settings["widths_kyr"]

    ts_tables = compute_timebin_tables_for_widths(
        data=data,
        age_nodes=age_nodes,
        timebin_widths=widths,
        metric="ts",
        age_col=age_col,
        value_col=value_col,
        theilsen_alpha=get_theilsen_alpha(config),
    )

    interpolated_ts_tables = interpolate_tables_for_widths(
        tables_by_width=ts_tables,
        target_col="Rate_origin",
        output_col="Rate_interp",
        age_col="Age_node",
        counts_col="Counts",
        method=interpolation_settings["method"],
        count_alpha=interpolation_settings["count_alpha"],
        distance_beta=interpolation_settings["distance_beta"],
        edge_mode=interpolation_settings["edge_mode"],
    )

    ts_rate_tables = {}

    for width, table in interpolated_ts_tables.items():
        ts_rate_tables[float(width)] = standardize_rate_series(
            df=table,
            age_col="Age_node",
            value_col="Rate_interp",
            output_age_col="Age_kyr",
            output_value_col="Rate",
            take_absolute=True,
        )

    return {
        "timebin": ts_tables,
        "interpolated": interpolated_ts_tables,
        "rate": ts_rate_tables,
    }


def run_iqr_workflow(
    data: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, dict[float, pd.DataFrame]]:
    """
    Run the IQR workflow.

    Workflow
    --------
    raw data
        -> calculate IQR within each time bin
        -> interpolate missing IQR values

    IQR is a within-bin variability metric rather than a direct rate estimator.

    Returns
    -------
    dict
        {
            "timebin": {width: iqr_table},
            "interpolated": {width: interpolated_iqr_table},
            "rate": {width: standardized_iqr_table}
        }
    """
    age_col, value_col = get_input_columns(config)
    timebin_settings = get_timebin_settings(config)
    interpolation_settings = get_interpolation_settings(config)

    iqr_quartile_method = get_iqr_quartile_method(config)
    iqr_min_count = get_iqr_min_count(config)

    age_nodes = build_age_nodes(config)
    widths = timebin_settings["widths_kyr"]

    iqr_tables = compute_timebin_tables_for_widths(
        data=data,
        age_nodes=age_nodes,
        timebin_widths=widths,
        metric="iqr",
        age_col=age_col,
        value_col=value_col,
        theilsen_alpha=get_theilsen_alpha(config),
        iqr_quartile_method=iqr_quartile_method,
        iqr_min_count=iqr_min_count,
    )

    interpolated_iqr_tables = interpolate_tables_for_widths(
        tables_by_width=iqr_tables,
        target_col="Rate_origin",
        output_col="Rate_interp",
        age_col="Age_node",
        counts_col="Counts",
        method=interpolation_settings["method"],
        count_alpha=interpolation_settings["count_alpha"],
        distance_beta=interpolation_settings["distance_beta"],
        edge_mode=interpolation_settings["edge_mode"],
    )

    interpolated_iqr_tables = interpolate_tables_for_widths(
        tables_by_width=interpolated_iqr_tables,
        target_col="Quartile_1_origin",
        output_col="Quartile_1_interp",
        age_col="Age_node",
        counts_col="Counts",
        method=interpolation_settings["method"],
        count_alpha=interpolation_settings["count_alpha"],
        distance_beta=interpolation_settings["distance_beta"],
        edge_mode=interpolation_settings["edge_mode"],
    )

    interpolated_iqr_tables = interpolate_tables_for_widths(
        tables_by_width=interpolated_iqr_tables,
        target_col="Quartile_3_origin",
        output_col="Quartile_3_interp",
        age_col="Age_node",
        counts_col="Counts",
        method=interpolation_settings["method"],
        count_alpha=interpolation_settings["count_alpha"],
        distance_beta=interpolation_settings["distance_beta"],
        edge_mode=interpolation_settings["edge_mode"],
    )

    iqr_rate_tables = {}

    iqr_rate_tables = {}

    for width, table in interpolated_iqr_tables.items():
        rate_table = table[
            [
                "Age_node",
                "Rate_interp",
                "Quartile_1_interp",
                "Quartile_3_interp",
            ]
        ].copy()

        rate_table = rate_table.rename(
            columns={
                "Age_node": "Age_kyr",
                "Rate_interp": "Rate",
                "Quartile_1_interp": "Quartile 1",
                "Quartile_3_interp": "Quartile 3",
            }
        )

        numeric_columns = [
            "Age_kyr",
            "Rate",
            "Quartile 1",
            "Quartile 3",
        ]

        for column in numeric_columns:
            rate_table[column] = pd.to_numeric(
                rate_table[column],
                errors="coerce",
            )

        # Preserve the established behavior: Rate uses absolute values.
        # Q1 and Q3 retain their original signs.
        rate_table["Rate"] = rate_table["Rate"].abs()

        rate_table = (
            rate_table
            .dropna(subset=["Age_kyr", "Rate"])
            .sort_values("Age_kyr", ascending=True)
            .reset_index(drop=True)
        )

        rate_table = rate_table[
            [
                "Age_kyr",
                "Rate",
                "Quartile 1",
                "Quartile 3",
            ]
        ]

        iqr_rate_tables[float(width)] = rate_table

    return {
        "timebin": iqr_tables,
        "interpolated": interpolated_iqr_tables,
        "rate": iqr_rate_tables,
    }


def run_all_roc_methods(
    data: pd.DataFrame,
    config: dict[str, Any],
    progress_callback=None,
) -> dict[str, dict[str, dict[float, pd.DataFrame]]]:
    """
    Run IBR, TS, and IQR workflows according to config.

    Returns
    -------
    dict
        {
            "IBR": {...},
            "TS": {...},
            "IQR": {...}
        }
    """
    results = {}

    if should_run_method(config, "ibr"):
        _report_progress(progress_callback, 24, "Calculating IBR time-bin means and rates...")
        results["IBR"] = run_ibr_workflow(data=data, config=config)
        _report_progress(progress_callback, 34, "IBR calculation completed.")

    if should_run_method(config, "ts"):
        _report_progress(progress_callback, 36, "Calculating Theil-Sen time-bin slopes...")
        results["TS"] = run_ts_workflow(data=data, config=config)
        _report_progress(progress_callback, 46, "Theil-Sen calculation completed.")

    if should_run_method(config, "iqr"):
        _report_progress(progress_callback, 48, "Calculating IQR time-bin variability...")
        results["IQR"] = run_iqr_workflow(data=data, config=config)
        _report_progress(progress_callback, 58, "IQR calculation completed.")

    if len(results) == 0:
        raise RuntimeError("No RoC method is enabled in config.")

    return results


def extract_rate_tables(
    all_results: dict[str, dict[str, dict[float, pd.DataFrame]]],
) -> dict[str, dict[float, pd.DataFrame]]:
    """
    Extract only final rate tables from full workflow results.

    Parameters
    ----------
    all_results : dict
        Output from run_all_roc_methods().

    Returns
    -------
    dict
        {
            "IBR": {width: rate_table},
            "TS": {width: rate_table},
            "IQR": {width: rate_table}
        }
    """
    output = {}

    for method_name, method_result in all_results.items():
        if "rate" not in method_result:
            continue

        output[method_name] = method_result["rate"]

    return output


def run_full_workflow(
    data: pd.DataFrame,
    config: dict[str, Any],
    progress_callback=None,
) -> dict[str, Any]:
    """
    Run the full RoC workflow.

    Workflow:
    - IBR / TS / IQR calculation routes
    - merged multi-timescale tables
    - LRI regression
    - time-scale-corrected relative RoC tables
    - nTV / Gini metrics
    - PWLF breakpoint detection
    - method-specific KDE consensus breakpoint detection
    - method-specific phase statistics
    """
    _report_progress(progress_callback, 22, "Starting RoC method calculations...")

    roc_results = run_all_roc_methods(
        data=data,
        config=config,
        progress_callback=progress_callback,
    )

    _report_progress(progress_callback, 60, "Extracting and merging multi-timescale rate tables...")
    rate_tables = extract_rate_tables(roc_results)

    merged_rate_tables = merge_all_methods_rate_tables(
        rate_tables_by_method=rate_tables,
        age_col="Age_kyr",
        value_col="Rate",
        output_age_col="Age_kyr",
        column_prefix="Timescale_",
    )
    _report_progress(progress_callback, 64, "Merged multi-timescale rate tables completed.")

    lri_results = {}
    normalized_rate_tables = {}

    if should_run_analysis(config, "run_lri", default=True):
        _report_progress(progress_callback, 66, "Running LRI time-scale correction...")
        lri_results = run_lri_for_all_methods(
            merged_tables_by_method=merged_rate_tables,
            config=config,
            age_col="Age_kyr",
            column_prefix="Timescale_",
        )

        normalized_rate_tables = extract_normalized_tables(lri_results)
        _report_progress(progress_callback, 72, "LRI correction completed.")

    metrics_results = {}

    if should_run_analysis(config, "run_metrics", default=True):
        _report_progress(progress_callback, 74, "Calculating nTV and Gini metrics...")

        metrics_results = run_metrics_analysis(
            merged_rate_tables=merged_rate_tables,
            corrected_rate_tables=normalized_rate_tables,
            config=config,
            age_col="Age_kyr",
            column_prefix="Timescale_",
        )

        _report_progress(progress_callback, 78, "nTV and Gini metrics completed.")

    pwlf_results = {}

    if should_run_analysis(config, "run_pwlf", default=True):
        _report_progress(progress_callback, 80, "Running PWLF breakpoint detection...")
        breakpoint_settings = get_breakpoint_settings(config)
        breakpoint_data_type = breakpoint_settings["data_type"]

        if (
            breakpoint_data_type == "time_scale_corrected_relative"
            and normalized_rate_tables
        ):
            pwlf_input_tables = normalized_rate_tables
            pwlf_data_type = "time_scale_corrected_relative"
        else:
            pwlf_input_tables = merged_rate_tables
            pwlf_data_type = "raw"

        pwlf_results = run_pwlf_analysis(
            rate_tables=pwlf_input_tables,
            config=config,
            data_type=pwlf_data_type,
            age_col="Age_kyr",
            column_prefix="Timescale_",
        )
        _report_progress(progress_callback, 84, "PWLF breakpoint detection completed.")

    kde_results = {}

    if (
            should_run_analysis(config, "run_kde", default=True)
            and pwlf_results
            and "breakpoints" in pwlf_results
            and not pwlf_results["breakpoints"].empty
    ):
        _report_progress(
            progress_callback,
            85,
            "Running KDE consensus breakpoint detection...",
        )

        kde_results = run_kde_analysis(
            pwlf_breakpoint_table=pwlf_results["breakpoints"],
            config=config,
        )

        _report_progress(
            progress_callback,
            86,
            "KDE consensus breakpoint detection completed.",
        )

    phase_results = {}

    if (
        should_run_analysis(config, "run_phase", default=True)
        and kde_results
        and "peaks" in kde_results
        and not kde_results["peaks"].empty
    ):
        _report_progress(progress_callback, 87, "Calculating phase statistics...")
        breakpoint_settings = get_breakpoint_settings(config)
        phase_data_type = breakpoint_settings["data_type"]

        if (
            phase_data_type == "time_scale_corrected_relative"
            and normalized_rate_tables
        ):
            phase_input_tables = normalized_rate_tables
            phase_data_type = "time_scale_corrected_relative"
        else:
            phase_input_tables = merged_rate_tables
            phase_data_type = "raw"

        phase_results = run_phase_analysis(
            rate_tables=phase_input_tables,
            kde_peak_table=kde_results["peaks"],
            config=config,
            data_type=phase_data_type,
            age_col="Age_kyr",
            column_prefix="Timescale_",
        )
        _report_progress(progress_callback, 88, "Phase statistics completed.")

    return {
        "roc_results": roc_results,
        "rate_tables": rate_tables,
        "merged_rate_tables": merged_rate_tables,
        "lri_results": lri_results,
        "normalized_rate_tables": normalized_rate_tables,
        "metrics_results": metrics_results,
        "pwlf_results": pwlf_results,
        "kde_results": kde_results,
        "phase_results": phase_results,
    }
