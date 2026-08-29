"""
Plotting utilities for the RoC workflow.

This module generates summary figures from in-memory workflow results.

Figures:
1. Raw RoC series across all calculated timescales
2. Time-scale-corrected relative RoC series across all calculated timescales
3. LRI regression plots
4. nTV and Gini metric plots
5. Method-specific KDE density plots
6. Method-specific phase-mean barplots

The module supports multiple output formats, for example:
- SVG for publication and vector editing
- PNG for GUI preview and quick viewing
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import re

import numpy as np
import pandas as pd
import matplotlib

# Figure generation runs in the backend process and must not depend on a GUI
# display or Tcl/Tk runtime, especially in the packaged Windows executable.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
# Matplotlib loads vector writers dynamically. Explicit imports ensure that
# PyInstaller includes the SVG and PDF writers used by configured outputs.
from matplotlib.backends import backend_pdf as _backend_pdf  # noqa: F401
from matplotlib.backends import backend_svg as _backend_svg  # noqa: F401


METHOD_ORDER = ["IBR", "TS", "IQR"]


def normalize_figure_formats(plotting_config: dict[str, Any]) -> list[str]:
    """
    Read and normalize figure output formats.

    New config style:
        figure_formats: ["svg", "png"]

    Backward-compatible old style:
        figure_format: "svg"
    """
    if "figure_formats" in plotting_config:
        raw_formats = plotting_config.get("figure_formats", ["svg", "png"])
    else:
        raw_formats = [plotting_config.get("figure_format", "svg")]

    if isinstance(raw_formats, str):
        raw_formats = [raw_formats]

    formats = []

    for item in raw_formats:
        fmt = str(item).strip().lower().lstrip(".")

        if fmt == "":
            continue

        formats.append(fmt)

    if not formats:
        formats = ["svg"]

    unique_formats = []

    for fmt in formats:
        if fmt not in unique_formats:
            unique_formats.append(fmt)

    return unique_formats


def get_plotting_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get plotting settings from config.

    Note
    ----
    representative_timescales_kyr is intentionally not used here.
    All available Timescale_* columns are plotted automatically.
    """
    plotting_config = config.get("plotting", {})

    return {
        "enabled": bool(
            plotting_config.get(
                "enabled",
                config.get("analysis", {}).get("run_plotting", True),
            )
        ),
        "figure_formats": normalize_figure_formats(plotting_config),
        "dpi": int(plotting_config.get("dpi", 600)),
        "age_min_kyr": float(plotting_config.get("age_min_kyr", 0)),
        "age_max_kyr": float(plotting_config.get("age_max_kyr", 67100)),
    }


def safe_filename(text: str) -> str:
    """
    Convert text to a safe file-name component.
    """
    text = str(text).strip()
    text = re.sub(r"[^\w\-.]+", "_", text)
    text = re.sub(r"_+", "_", text)

    return text.strip("_")


def ensure_output_dir(output_dir: Path | str) -> Path:
    """
    Ensure that output directory exists.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    return output_dir


def save_figure_multiple_formats(
    fig: plt.Figure,
    output_dir: Path | str,
    stem: str,
    settings: dict[str, Any],
) -> dict[str, Path]:
    """
    Save one figure in all configured output formats.
    """
    output_dir = ensure_output_dir(output_dir)
    saved_paths = {}

    stem = safe_filename(stem)

    for fmt in settings["figure_formats"]:
        out_path = output_dir / f"{stem}.{fmt}"

        fig.savefig(
            out_path,
            format=fmt,
            dpi=settings["dpi"],
            bbox_inches="tight",
        )

        saved_paths[fmt] = out_path

    return saved_paths


def flatten_figure_paths(
    figure_name: str,
    paths_by_format: dict[str, Path] | None,
) -> dict[str, Path]:
    """
    Convert {format: path} to {figure_name_format: path}.
    """
    if not paths_by_format:
        return {}

    output = {}

    for fmt, path in paths_by_format.items():
        output[f"{figure_name}_{fmt}"] = path

    return output


def parse_timescale_from_column(
    column: str,
    column_prefix: str = "Timescale_",
) -> float | None:
    """
    Parse numerical timescale from a Timescale_* column name.
    """
    column_text = str(column)

    if not column_text.startswith(column_prefix):
        return None

    value_text = column_text.replace(column_prefix, "", 1)
    value_text = value_text.replace("kyr", "")
    value_text = value_text.replace("p", ".")

    try:
        return float(value_text)
    except ValueError:
        return None


def find_timescale_column(
    table: pd.DataFrame,
    target_timescale: float,
    column_prefix: str = "Timescale_",
) -> str | None:
    """
    Find a timescale column by target timescale.

    This helper is kept for backward compatibility, although the main plotting
    functions now plot all available Timescale_* columns automatically.
    """
    exact_column = f"{column_prefix}{int(target_timescale)}"

    if exact_column in table.columns:
        return exact_column

    target = float(target_timescale)
    candidates = []

    for column in table.columns:
        value = parse_timescale_from_column(
            column=column,
            column_prefix=column_prefix,
        )

        if value is None:
            continue

        candidates.append((abs(value - target), column))

    if not candidates:
        return None

    candidates = sorted(candidates, key=lambda item: item[0])

    return candidates[0][1]


def get_all_timescale_columns(
    tables_by_method: dict[str, pd.DataFrame],
    column_prefix: str = "Timescale_",
) -> list[tuple[float, str]]:
    """
    Get all available timescale columns from merged RoC tables.
    """
    timescale_map: dict[float, str] = {}

    for table in tables_by_method.values():
        if table is None or table.empty:
            continue

        for column in table.columns:
            timescale = parse_timescale_from_column(
                column=column,
                column_prefix=column_prefix,
            )

            if timescale is None:
                continue

            timescale_map[timescale] = str(column)

    return [
        (timescale, timescale_map[timescale])
        for timescale in sorted(timescale_map)
    ]


def get_method_names(tables_by_method: dict[str, pd.DataFrame]) -> list[str]:
    """
    Return method names in a stable order.
    """
    names = []

    for method in METHOD_ORDER:
        if method in tables_by_method:
            names.append(method)

    for method in tables_by_method:
        if method not in names:
            names.append(method)

    return names


def format_timescale_label(timescale: float) -> str:
    """
    Format timescale label for subplot titles.
    """
    if float(timescale).is_integer():
        return f"{int(timescale)} kyr"

    return f"{timescale:g} kyr"


def plot_representative_roc_series(
    tables_by_method: dict[str, pd.DataFrame],
    output_dir: Path | str,
    stem: str,
    title: str,
    y_label: str,
    config: dict[str, Any],
    age_col: str = "Age_kyr",
    column_prefix: str = "Timescale_",
) -> dict[str, Path] | None:
    """
    Plot RoC series for all available timescales.

    The function name is kept for backward compatibility. It no longer uses
    representative_timescales_kyr. Instead, it automatically plots all
    Timescale_* columns present in the supplied merged tables.
    """
    if not tables_by_method:
        return None

    settings = get_plotting_settings(config)
    output_dir = ensure_output_dir(output_dir)

    method_names = get_method_names(tables_by_method)
    timescale_columns = get_all_timescale_columns(
        tables_by_method=tables_by_method,
        column_prefix=column_prefix,
    )

    nrows = len(method_names)
    ncols = len(timescale_columns)

    if nrows == 0 or ncols == 0:
        return None

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=(4.2 * ncols, 2.2 * nrows),
        squeeze=False,
    )

    for row_index, method_name in enumerate(method_names):
        table = tables_by_method.get(method_name, pd.DataFrame())

        if table is None or table.empty or age_col not in table.columns:
            for col_index in range(ncols):
                axes[row_index, col_index].axis("off")
            continue

        for col_index, (timescale, value_col) in enumerate(timescale_columns):
            ax = axes[row_index, col_index]

            if value_col not in table.columns:
                ax.axis("off")
                continue

            local = table[[age_col, value_col]].copy()
            local[age_col] = pd.to_numeric(local[age_col], errors="coerce")
            local[value_col] = pd.to_numeric(local[value_col], errors="coerce")
            local = local.dropna(subset=[age_col, value_col])
            local = local.sort_values(age_col, ascending=True)

            if local.empty:
                ax.axis("off")
                continue

            ax.plot(
                local[age_col],
                local[value_col],
                linewidth=0.8,
            )

            ax.set_xlim(settings["age_max_kyr"], settings["age_min_kyr"])
            ax.set_title(
                f"{method_name}, {format_timescale_label(timescale)}",
                fontsize=8,
            )

            if row_index == nrows - 1:
                ax.set_xlabel("Age (kyr)")
            else:
                ax.set_xlabel("")

            if col_index == 0:
                ax.set_ylabel(y_label)
            else:
                ax.set_ylabel("")

            ax.tick_params(labelsize=7)

    fig.suptitle(title, fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    saved_paths = save_figure_multiple_formats(
        fig=fig,
        output_dir=output_dir,
        stem=stem,
        settings=settings,
    )

    plt.close(fig)

    return saved_paths


def plot_lri_regression(
    lri_results: dict[str, dict[str, pd.DataFrame]],
    output_dir: Path | str,
    config: dict[str, Any],
) -> dict[str, Path] | None:
    """
    Plot LRI regression results for all methods.
    """
    if not lri_results:
        return None

    settings = get_plotting_settings(config)
    output_dir = ensure_output_dir(output_dir)

    method_names = get_method_names(
        {
            method: result.get("points", pd.DataFrame())
            for method, result in lri_results.items()
        }
    )

    if not method_names:
        return None

    fig, axes = plt.subplots(
        nrows=len(method_names),
        ncols=1,
        figsize=(6.2, 2.4 * len(method_names)),
        squeeze=False,
    )

    for row_index, method_name in enumerate(method_names):
        ax = axes[row_index, 0]
        result = lri_results.get(method_name, {})

        points = result.get("points", pd.DataFrame())
        summary = result.get("summary", pd.DataFrame())
        quantiles = result.get("quantiles", pd.DataFrame())

        if points.empty or summary.empty:
            ax.axis("off")
            continue

        ax.scatter(
            points["Log10_timescale"],
            points["Log10_RoC"],
            s=4,
            alpha=0.25,
        )

        x_min = float(points["Log10_timescale"].min())
        x_max = float(points["Log10_timescale"].max())
        x_line = np.linspace(x_min, x_max, 100)

        for _, row in summary.iterrows():
            regression_name = str(row.get("Regression", ""))
            slope = float(row["Slope"])
            intercept = float(row["Intercept"])
            r2 = float(row["R2"])

            y_line = slope * x_line + intercept

            if regression_name == "All data":
                ax.plot(
                    x_line,
                    y_line,
                    linewidth=1.2,
                    label=(
                        f"All: y={slope:.3f}x+{intercept:.3f}, "
                        f"R²={r2:.2f}"
                    ),
                )
            else:
                ax.plot(
                    x_line,
                    y_line,
                    linewidth=0.9,
                    linestyle="--",
                    label=(
                        f"{regression_name}: "
                        f"y={slope:.3f}x+{intercept:.3f}, R²={r2:.2f}"
                    ),
                )

        if not quantiles.empty:
            for _, group in quantiles.groupby("Percentile"):
                group = group.sort_values("Log10_timescale")
                ax.scatter(
                    group["Log10_timescale"],
                    group["Log10_RoC_quantile"],
                    s=12,
                    marker="x",
                    alpha=0.8,
                )

        ax.set_title(f"{method_name} LRI regression", fontsize=9)
        ax.set_xlabel("log10(timescale)")
        ax.set_ylabel("log10(RoC)")
        ax.legend(fontsize=6, frameon=False)
        ax.tick_params(labelsize=7)

    fig.tight_layout()

    saved_paths = save_figure_multiple_formats(
        fig=fig,
        output_dir=output_dir,
        stem="lri_regression",
        settings=settings,
    )

    plt.close(fig)

    return saved_paths


def plot_metrics(
    metrics_results: dict[str, pd.DataFrame],
    output_dir: Path | str,
    config: dict[str, Any],
) -> dict[str, Path] | None:
    """
    Plot nTV and Gini metrics.
    """
    if not metrics_results:
        return None

    settings = get_plotting_settings(config)
    output_dir = ensure_output_dir(output_dir)

    metrics_table = metrics_results.get("combined", pd.DataFrame())

    if metrics_table is None or metrics_table.empty:
        return None

    gini_col = "Gini" if "Gini" in metrics_table.columns else "G"

    if "nTV" not in metrics_table.columns or gini_col not in metrics_table.columns:
        return None

    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(6.2, 5.0),
        squeeze=False,
    )

    for data_type, group_data in metrics_table.groupby("Data_type"):
        for method_name, group in group_data.groupby("Method"):
            group = group.sort_values("Timescale_kyr")

            label = f"{method_name} ({data_type})"

            axes[0, 0].plot(
                group["Timescale_kyr"],
                group["nTV"],
                marker="o",
                markersize=3,
                linewidth=0.8,
                label=label,
            )

            axes[1, 0].plot(
                group["Timescale_kyr"],
                group[gini_col],
                marker="o",
                markersize=3,
                linewidth=0.8,
                label=label,
            )

    axes[0, 0].set_ylabel("nTV")
    axes[1, 0].set_ylabel("Gini")
    axes[1, 0].set_xlabel("Analytical timescale (kyr)")

    for ax in axes[:, 0]:
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=6, frameon=False)

    fig.tight_layout()

    saved_paths = save_figure_multiple_formats(
        fig=fig,
        output_dir=output_dir,
        stem="metrics_ntv_gini",
        settings=settings,
    )

    plt.close(fig)

    return saved_paths


def plot_kde_density(
    kde_results: dict[str, pd.DataFrame],
    output_dir: Path | str,
    config: dict[str, Any],
) -> dict[str, Path] | None:
    """
    Plot method-specific KDE density curves and consensus peaks.
    """
    if not kde_results:
        return None

    settings = get_plotting_settings(config)
    output_dir = ensure_output_dir(output_dir)

    density = kde_results.get("density", pd.DataFrame())
    peaks = kde_results.get("peaks", pd.DataFrame())

    if density is None or density.empty:
        return None

    if "Method" in density.columns:
        method_names = get_method_names(
            {
                method: group
                for method, group in density.groupby("Method")
            }
        )
    else:
        method_names = ["ALL"]
        density = density.copy()
        density["Method"] = "ALL"

    if peaks is None:
        peaks = pd.DataFrame()

    if not peaks.empty and "Method" not in peaks.columns:
        peaks = peaks.copy()
        peaks["Method"] = "ALL"

    fig, axes = plt.subplots(
        nrows=len(method_names),
        ncols=1,
        figsize=(7.0, 2.2 * len(method_names)),
        squeeze=False,
    )

    for row_index, method_name in enumerate(method_names):
        ax = axes[row_index, 0]

        local_density = density[
            density["Method"].astype(str) == str(method_name)
        ].copy()
        local_density = local_density.sort_values("Age_kyr")

        ax.plot(
            local_density["Age_kyr"],
            local_density["KDE_density"],
            linewidth=1.0,
        )

        if not peaks.empty:
            local_peaks = peaks[
                peaks["Method"].astype(str) == str(method_name)
            ].copy()

            for _, peak in local_peaks.iterrows():
                peak_age = float(peak["Consensus_breakpoint_kyr"])

                if "Density" in peak:
                    peak_density = float(peak["Density"])
                else:
                    peak_density = float(
                        np.interp(
                            peak_age,
                            local_density["Age_kyr"],
                            local_density["KDE_density"],
                        )
                    )

                ax.scatter(peak_age, peak_density, s=18, zorder=3)
                ax.axvline(peak_age, linestyle=":", linewidth=0.6, alpha=0.7)
                ax.text(
                    peak_age,
                    peak_density,
                    f"{peak_age / 1000:.2f}",
                    fontsize=6,
                    ha="center",
                    va="bottom",
                )

        ax.set_xlim(settings["age_max_kyr"], settings["age_min_kyr"])
        ax.set_title(f"{method_name} KDE consensus breakpoints", fontsize=9)
        ax.set_xlabel("Age (kyr)")
        ax.set_ylabel("KDE density")
        ax.tick_params(labelsize=7)

    fig.tight_layout()

    saved_paths = save_figure_multiple_formats(
        fig=fig,
        output_dir=output_dir,
        stem="kde_density_by_method",
        settings=settings,
    )

    plt.close(fig)

    return saved_paths


def plot_phase_mean_barplots(
    phase_results: dict[str, pd.DataFrame],
    output_dir: Path | str,
    config: dict[str, Any],
) -> dict[str, Path] | None:
    """
    Plot phase-mean RoC barplots for all available timescales.
    """
    if not phase_results:
        return None

    settings = get_plotting_settings(config)
    output_dir = ensure_output_dir(output_dir)

    phase_statistics = phase_results.get("phase_statistics", pd.DataFrame())

    if phase_statistics is None or phase_statistics.empty:
        return None

    if "Timescale_kyr" not in phase_statistics.columns:
        return None

    timescales = sorted(
        float(value)
        for value in phase_statistics["Timescale_kyr"].dropna().unique()
    )

    if not timescales:
        return None

    method_names = get_method_names(
        {
            method: group
            for method, group in phase_statistics.groupby("Method")
        }
    )

    if not method_names:
        return None

    nrows = len(method_names)
    ncols = len(timescales)

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=(4.2 * ncols, 2.4 * nrows),
        squeeze=False,
    )

    for row_index, method_name in enumerate(method_names):
        for col_index, target_timescale in enumerate(timescales):
            ax = axes[row_index, col_index]

            method_data = phase_statistics[
                phase_statistics["Method"].astype(str) == str(method_name)
            ].copy()

            if method_data.empty:
                ax.axis("off")
                continue

            local = method_data[
                method_data["Timescale_kyr"].astype(float) == float(target_timescale)
            ].copy()
            local = local.sort_values("Phase_id")

            if local.empty:
                ax.axis("off")
                continue

            x_left = local["Start_kyr"].to_numpy(dtype=float)
            widths = (local["End_kyr"] - local["Start_kyr"]).to_numpy(dtype=float)
            means = local["Mean"].to_numpy(dtype=float)

            if "SE" in local.columns:
                yerr = 1.96 * local["SE"].to_numpy(dtype=float)
                yerr[~np.isfinite(yerr)] = 0.0
            else:
                yerr = None

            ax.bar(
                x_left,
                means,
                width=widths,
                align="edge",
                alpha=0.75,
                yerr=yerr,
                error_kw={"linewidth": 0.6},
            )

            ax.set_xlim(settings["age_max_kyr"], settings["age_min_kyr"])
            ax.set_title(
                f"{method_name}, {format_timescale_label(target_timescale)}",
                fontsize=8,
            )

            if row_index == nrows - 1:
                ax.set_xlabel("Age (kyr)")
            else:
                ax.set_xlabel("")

            if col_index == 0:
                ax.set_ylabel("Phase mean")
            else:
                ax.set_ylabel("")

            ax.tick_params(labelsize=7)

    fig.suptitle("Method-specific phase-mean RoC across all timescales", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    saved_paths = save_figure_multiple_formats(
        fig=fig,
        output_dir=output_dir,
        stem="phase_mean_barplots_all_timescales",
        settings=settings,
    )

    plt.close(fig)

    return saved_paths


def run_plotting(
    workflow_result: dict[str, Any],
    config: dict[str, Any],
    output_dir: Path | str,
) -> dict[str, Path]:
    """
    Generate all summary figures.
    """
    settings = get_plotting_settings(config)

    if not settings["enabled"]:
        return {}

    output_dir = ensure_output_dir(output_dir)

    figure_paths: dict[str, Path] = {}

    merged_rate_tables = workflow_result.get("merged_rate_tables", {})
    normalized_rate_tables = workflow_result.get("normalized_rate_tables", {})
    lri_results = workflow_result.get("lri_results", {})
    metrics_results = workflow_result.get("metrics_results", {})
    kde_results = workflow_result.get("kde_results", {})
    phase_results = workflow_result.get("phase_results", {})

    raw_paths = plot_representative_roc_series(
        tables_by_method=merged_rate_tables,
        output_dir=output_dir,
        stem="roc_raw_all_timescales",
        title="Raw RoC series across all timescales",
        y_label="Raw RoC",
        config=config,
    )

    figure_paths.update(
        flatten_figure_paths(
            figure_name="raw_all_timescales_roc",
            paths_by_format=raw_paths,
        )
    )

    corrected_paths = plot_representative_roc_series(
        tables_by_method=normalized_rate_tables,
        output_dir=output_dir,
        stem="roc_corrected_all_timescales",
        title="Time-scale-corrected relative RoC series across all timescales",
        y_label="Corrected relative RoC",
        config=config,
    )

    figure_paths.update(
        flatten_figure_paths(
            figure_name="corrected_all_timescales_roc",
            paths_by_format=corrected_paths,
        )
    )

    lri_paths = plot_lri_regression(
        lri_results=lri_results,
        output_dir=output_dir,
        config=config,
    )

    figure_paths.update(
        flatten_figure_paths(
            figure_name="lri_regression",
            paths_by_format=lri_paths,
        )
    )

    metrics_paths = plot_metrics(
        metrics_results=metrics_results,
        output_dir=output_dir,
        config=config,
    )

    figure_paths.update(
        flatten_figure_paths(
            figure_name="metrics",
            paths_by_format=metrics_paths,
        )
    )

    kde_paths = plot_kde_density(
        kde_results=kde_results,
        output_dir=output_dir,
        config=config,
    )

    figure_paths.update(
        flatten_figure_paths(
            figure_name="kde_density",
            paths_by_format=kde_paths,
        )
    )

    phase_paths = plot_phase_mean_barplots(
        phase_results=phase_results,
        output_dir=output_dir,
        config=config,
    )

    figure_paths.update(
        flatten_figure_paths(
            figure_name="phase_mean_barplots_all_timescales",
            paths_by_format=phase_paths,
        )
    )

    return figure_paths
