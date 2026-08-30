"""Random-subsampling sensitivity analysis for deep-time RoC estimates.

The analysis reproduces the sampling-density experiment associated with the
manuscript.  It evaluates IBR, TS, and IQR at 100 and 1000 kyr analytical
windows after retaining one randomly selected observation in each 20, 50, or
100 kyr subsampling interval.  Each configuration uses 200 iterations with a
fixed random seed and reports MAE, MAPE, ensemble means, and empirical 95%
intervals relative to the full-data estimate.

This module is intentionally separate from the v1.0.1 graphical workflow.
Run it from the repository root with::

    python run_sampling_density_analysis.py

The complete analysis can take a substantial amount of time and disk space.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as sts
from matplotlib.ticker import FixedLocator, MaxNLocator, ScalarFormatter


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INFILE = REPOSITORY_ROOT / "data" / "CENOGRID_benthic_d18O_sampling_density.xlsx"
INPUT_SHEET = "All"
OUT_DIR = REPOSITORY_ROOT / "outputs" / "sampling_density"
OUT_PREFIX = "O_RandomSubsampling"

COL_AGE = "Age"
COL_VALUE = "Value"

TIMEBIN_WIDTHS = [100, 1000]
RANDOM_SUBSAMPLING_WIDTHS = [20, 50, 100]
METHODS = ["IBR", "TS", "IQR"]

N_ITER = 200
RANDOM_SEED = 42

START_AGE = 67000
END_AGE = 0
AGE_INTERVAL = 10

COUNT_WEIGHT_ALPHA = 1.0
DISTANCE_WEIGHT_BETA = 1.0
EDGE_MODE = "nearest"

THEILSEN_ALPHA = 0.90

EMPIRICAL_LOWER = 0.025
EMPIRICAL_UPPER = 0.975

FIG_WIDTH = 8.27
FIG_HEIGHT = 5.85

FONT_SIZE = 6
TITLE_SIZE = 7
LABEL_SIZE = 6
TICK_SIZE = 5
LEGEND_SIZE = 5

LINE_WIDTH = 0.45
LINE_ALPHA = 0.72
REFERENCE_LINE_WIDTH = 0.5
REFERENCE_LINE_ALPHA = 0.8
FILL_ALPHA = 0.1
YLIM_FACTOR = 1.12

X_TICK_STEP = 10000
Y_NBINS = 4

USE_MANUAL_Y_LIMITS = True

METHOD_Y_LIMITS = {
    100: {
        "IBR": (0.0, 0.015),
        "TS": (0.0, 0.020),
        "IQR": (0.0, 1.8),
    },
    1000: {
        "IBR": (0.0, 0.001),
        "TS": (0.0, 0.002),
        "IQR": (0.0, 1.2),
    },
}

FIXED_COLOR_MAP = {
    10: "#56B4E9",
    20: "#0072B2",
    30: "#E69F00",
    50: "#009E73",
    100: "#D55E00",
    200: "#CC79A7",
    500: "#6A3D9A",
    1000: "#666666",
}

FALLBACK_COLORS = [
    "#1B9E77",
    "#D95F02",
    "#7570B3",
    "#E7298A",
    "#66A61E",
    "#E6AB02",
    "#A6761D",
    "#666666",
]

SAVE_ALL_ITERATIONS = True
SAVE_METRICS = True
SAVE_SUMMARY_CURVES = True
SAVE_COMBINED_METRICS = True
VERBOSE = True


def load_input_data():
    if not INFILE.is_file():
        raise FileNotFoundError(f"Input file not found: {INFILE}")

    data = pd.read_excel(INFILE, sheet_name=INPUT_SHEET, usecols=[COL_AGE, COL_VALUE])
    data[COL_AGE] = pd.to_numeric(data[COL_AGE], errors="coerce")
    data[COL_VALUE] = pd.to_numeric(data[COL_VALUE], errors="coerce")
    data = data.dropna(subset=[COL_AGE, COL_VALUE])
    data = data.groupby(COL_AGE, as_index=False, sort=False)[COL_VALUE].mean()
    data = data.sort_values(COL_AGE).reset_index(drop=True)

    return data


def random_subsample_once(data, subsampling_width, rng):
    bins = np.arange(END_AGE, START_AGE + subsampling_width, subsampling_width)
    sampled_rows = []

    for i in range(len(bins) - 1):
        bin_start = bins[i]
        bin_end = bins[i + 1]
        bin_data = data[(data[COL_AGE] >= bin_start) & (data[COL_AGE] < bin_end)]

        if len(bin_data) > 0:
            random_state = int(rng.integers(0, 2**32 - 1))
            sampled_rows.append(bin_data.sample(n=1, random_state=random_state))

    if sampled_rows:
        return pd.concat(sampled_rows, ignore_index=True)

    return pd.DataFrame(columns=[COL_AGE, COL_VALUE])


def calculate_iqr(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]

    if values.size < 2:
        return np.nan

    try:
        q1, q3 = np.percentile(values, [25, 75], method="linear")
    except TypeError:
        q1, q3 = np.percentile(values, [25, 75], interpolation="linear")

    return float(q3 - q1)


def calculate_theilsen_slope(x, y):
    x_values = np.asarray(x, dtype=float)
    y_values = np.asarray(y, dtype=float)
    valid_mask = np.isfinite(x_values) & np.isfinite(y_values)
    x_values = x_values[valid_mask]
    y_values = y_values[valid_mask]

    if np.unique(x_values).size < 2:
        return np.nan

    slope, *_ = sts.theilslopes(y_values, x_values, alpha=THEILSEN_ALPHA)

    return float(slope)


def compute_timebin_table(data, age_nodes, timebin_width, method):
    half_width = timebin_width / 2.0
    rows = []

    for i, center_age in enumerate(age_nodes):
        bin_start = center_age - half_width
        bin_end = center_age + half_width
        bin_data = data[(data[COL_AGE] >= bin_start) & (data[COL_AGE] < bin_end)]
        counts = len(bin_data)
        unique_age_count = bin_data[COL_AGE].nunique()

        if method == "MEAN":
            result_value = bin_data[COL_VALUE].mean() if counts > 0 else np.nan
            result_col = "Mean_origin"
        elif method == "TS":
            if unique_age_count >= 2:
                slope = calculate_theilsen_slope(bin_data[COL_AGE], bin_data[COL_VALUE])
                result_value = abs(slope) if np.isfinite(slope) else np.nan
            else:
                result_value = np.nan
            result_col = "Rate_origin"
        elif method == "IQR":
            result_value = calculate_iqr(bin_data[COL_VALUE])
            result_col = "Rate_origin"
        else:
            raise ValueError(f"Unsupported method: {method}")

        rows.append({
            "Time_bin": f"TimeBin{i + 1}",
            "Age_node": center_age,
            "Counts": counts,
            "Age_unique": unique_age_count,
            result_col: result_value,
        })

    return pd.DataFrame(rows)


def get_edge_fill_value(edge):
    edge_text = str(edge).strip().lower()

    if edge_text in ("nan", "none", ""):
        return np.nan

    if edge_text == "0":
        return 0.0

    return None


def interpolate_two_point(
    df,
    age_col,
    counts_col,
    target_col,
    output_col,
    count_alpha=1.0,
    distance_beta=1.0,
    edge="nearest"
):
    required_columns = {age_col, counts_col, target_col}

    if not required_columns.issubset(df.columns):
        missing_columns = sorted(required_columns - set(df.columns))
        raise KeyError(f"Missing required columns: {missing_columns}")

    local_df = df.copy()
    local_df[age_col] = pd.to_numeric(local_df[age_col], errors="coerce")
    local_df[counts_col] = pd.to_numeric(local_df[counts_col], errors="coerce").fillna(0.0)
    local_df[target_col] = pd.to_numeric(local_df[target_col], errors="coerce")
    local_df = local_df.sort_values(age_col).reset_index(drop=True)

    ages = local_df[age_col].to_numpy(dtype=float)
    counts = local_df[counts_col].to_numpy(dtype=float)
    values = local_df[target_col].to_numpy(dtype=float)

    known_mask = np.isfinite(ages) & np.isfinite(values) & (counts > 0)
    known_indices = np.where(known_mask)[0]
    interpolated_values = np.full(len(local_df), np.nan, dtype=float)

    if known_indices.size == 0:
        fill_value = get_edge_fill_value(edge)
        if fill_value is not None:
            interpolated_values[:] = fill_value
        local_df[output_col] = interpolated_values
        return local_df

    edge_text = str(edge).strip().lower()
    fill_value = get_edge_fill_value(edge)

    for i in range(len(local_df)):
        if known_mask[i]:
            interpolated_values[i] = values[i]
            continue

        age = ages[i]

        if not np.isfinite(age):
            interpolated_values[i] = np.nan
            continue

        position = np.searchsorted(known_indices, i)
        left_index = known_indices[position - 1] if position > 0 else None
        right_index = known_indices[position] if position < known_indices.size else None

        if left_index is None and right_index is None:
            interpolated_values[i] = fill_value if fill_value is not None else np.nan
            continue

        if left_index is None or right_index is None:
            if edge_text == "nearest":
                nearest_index = right_index if left_index is None else left_index
                interpolated_values[i] = values[nearest_index]
            else:
                interpolated_values[i] = fill_value if fill_value is not None else np.nan
            continue

        left_distance = abs(age - ages[left_index])
        right_distance = abs(age - ages[right_index])

        if left_distance == 0:
            interpolated_values[i] = values[left_index]
            continue

        if right_distance == 0:
            interpolated_values[i] = values[right_index]
            continue

        left_weight = (counts[left_index] ** count_alpha) / (left_distance ** distance_beta)
        right_weight = (counts[right_index] ** count_alpha) / (right_distance ** distance_beta)
        weight_sum = left_weight + right_weight

        if weight_sum == 0 or not np.isfinite(weight_sum):
            interpolated_values[i] = np.nan
        else:
            interpolated_values[i] = (
                left_weight * values[left_index] + right_weight * values[right_index]
            ) / weight_sum

    local_df[output_col] = interpolated_values

    return local_df


def compute_ibr_from_interpolated_mean(df, timebin_width):
    series = df.set_index("Age_node")["Mean_interp"]
    result = pd.DataFrame({"Age_node": series.index})
    result["Age_node_next"] = result["Age_node"] + timebin_width
    result["Mean"] = series.reindex(result["Age_node"]).values
    result["Mean_next"] = series.reindex(result["Age_node_next"]).values
    result = result.dropna(subset=["Mean", "Mean_next"])
    result["Age_kyr"] = (result["Age_node"] + result["Age_node_next"]) / 2.0
    result["Rate"] = (result["Mean_next"] - result["Mean"]).abs() / float(timebin_width)

    return result[["Age_kyr", "Rate"]].reset_index(drop=True)


def compute_method_rate_series(data, age_nodes, method, timebin_width):
    method = method.upper()

    if method == "IBR":
        timebin_table = compute_timebin_table(
            data=data,
            age_nodes=age_nodes,
            timebin_width=timebin_width,
            method="MEAN",
        )

        interpolated_table = interpolate_two_point(
            df=timebin_table,
            age_col="Age_node",
            counts_col="Counts",
            target_col="Mean_origin",
            output_col="Mean_interp",
            count_alpha=COUNT_WEIGHT_ALPHA,
            distance_beta=DISTANCE_WEIGHT_BETA,
            edge=EDGE_MODE,
        )

        rate_table = compute_ibr_from_interpolated_mean(interpolated_table, timebin_width)

    elif method in ("TS", "IQR"):
        timebin_table = compute_timebin_table(
            data=data,
            age_nodes=age_nodes,
            timebin_width=timebin_width,
            method=method,
        )

        interpolated_table = interpolate_two_point(
            df=timebin_table,
            age_col="Age_node",
            counts_col="Counts",
            target_col="Rate_origin",
            output_col="Rate_interp",
            count_alpha=COUNT_WEIGHT_ALPHA,
            distance_beta=DISTANCE_WEIGHT_BETA,
            edge=EDGE_MODE,
        )

        rate_table = interpolated_table[["Age_node", "Rate_interp"]].copy()
        rate_table = rate_table.rename(columns={"Age_node": "Age_kyr", "Rate_interp": "Rate"})

    else:
        raise ValueError(f"Unsupported method: {method}")

    series = rate_table.set_index("Age_kyr")["Rate"].sort_index()
    series.name = method
    series.index.name = "Age_kyr"

    return series


def compute_mae_mape(prediction_series, reference_series):
    comparison = pd.concat(
        [reference_series.rename("reference"), prediction_series.rename("prediction")],
        axis=1,
        join="inner",
    ).dropna()

    if comparison.empty:
        return np.nan, np.nan

    absolute_error = (comparison["prediction"] - comparison["reference"]).abs()
    mae = float(absolute_error.mean())
    nonzero_mask = comparison["reference"] != 0

    if nonzero_mask.any():
        mape = float(
            (
                absolute_error[nonzero_mask]
                / comparison.loc[nonzero_mask, "reference"].abs()
            ).mean()
            * 100.0
        )
    else:
        mape = np.nan

    return mae, mape


def compute_random_subsampling_statistics(
    data,
    age_nodes,
    method,
    subsampling_width,
    n_iter,
    reference_rate,
    rng,
    timebin_width
):
    iteration_series = []
    mae_list = []
    mape_list = []

    for i in range(n_iter):
        subsampled_data = random_subsample_once(
            data=data,
            subsampling_width=subsampling_width,
            rng=rng,
        )

        rate_series = compute_method_rate_series(
            data=subsampled_data,
            age_nodes=age_nodes,
            method=method,
            timebin_width=timebin_width,
        )

        iteration_series.append(rate_series)
        mae, mape = compute_mae_mape(rate_series, reference_rate)
        mae_list.append(mae)
        mape_list.append(mape)

        if VERBOSE:
            print(
                f"Timebin={timebin_width} kyr | Method={method} | "
                f"Subsampling={subsampling_width} kyr | "
                f"Iteration {i + 1}/{n_iter}: MAE={mae:.2e}, MAPE={mape:.2f}%"
            )

    all_iterations = pd.concat(iteration_series, axis=1).sort_index()
    all_iterations.columns = [
        f"Random_subsampling_run_{i + 1}"
        for i in range(len(iteration_series))
    ]

    ensemble_mean = all_iterations.mean(axis=1)
    empirical_lower = all_iterations.quantile(EMPIRICAL_LOWER, axis=1)
    empirical_upper = all_iterations.quantile(EMPIRICAL_UPPER, axis=1)

    mae_mean = float(np.nanmean(mae_list)) if len(mae_list) > 0 else np.nan
    mape_mean = float(np.nanmean(mape_list)) if len(mape_list) > 0 else np.nan

    metrics = pd.DataFrame({
        "Timebin_width_kyr": timebin_width,
        "Method": method,
        "Random_subsampling_width_kyr": subsampling_width,
        "Iteration": np.arange(1, len(mae_list) + 1),
        "MAE": mae_list,
        "MAPE_percent": mape_list,
    })

    return ensemble_mean, empirical_lower, empirical_upper, mae_mean, mape_mean, all_iterations, metrics


def make_color_map(widths):
    color_map = {}
    fallback_index = 0

    for width in sorted(widths):
        if width in FIXED_COLOR_MAP:
            color_map[width] = FIXED_COLOR_MAP[width]
        else:
            color_map[width] = FALLBACK_COLORS[fallback_index % len(FALLBACK_COLORS)]
            fallback_index += 1

    return color_map


def save_method_summary_curves(method, reference_rate, results, timebin_width):
    summary = pd.DataFrame(index=reference_rate.index)
    summary[f"{method}_Full_dataset"] = reference_rate

    for width in sorted(results.keys()):
        summary[f"{method}_{width}kyr_ensemble_mean"] = results[width]["ensemble_mean"]
        summary[f"{method}_{width}kyr_empirical_lower_95"] = results[width]["empirical_lower"]
        summary[f"{method}_{width}kyr_empirical_upper_95"] = results[width]["empirical_upper"]

    summary = summary.sort_index().reset_index()
    out_path = OUT_DIR / f"{OUT_PREFIX}_{method}_{timebin_width}kyr_summary_curves.csv"
    summary.to_csv(out_path, index=False)

    return out_path


def get_method_title(method):
    method = method.upper()

    if method == "IBR":
        return "a. IBR: inter-bin rate"

    if method == "TS":
        return "b. TS: Theil-Sen slope"

    if method == "IQR":
        return "c. IQR: interquartile range"

    return method


def format_scientific(value, digits=2):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "nan"

    if not np.isfinite(value):
        return "nan"

    return f"{value:.{digits}e}"


def get_y_limits(method, timebin_width, reference_rate, results):
    if USE_MANUAL_Y_LIMITS:
        method_limits = METHOD_Y_LIMITS.get(timebin_width, {})
        if method in method_limits:
            return method_limits[method]

    max_values = [reference_rate.max()]

    for width in results:
        max_values.append(results[width]["empirical_upper"].max())

    y_max = np.nanmax(max_values)

    if np.isfinite(y_max) and y_max > 0:
        return 0.0, y_max * YLIM_FACTOR

    return 0.0, 1.0


def plot_all_methods(all_method_results, timebin_width):
    method_order = [
        method.upper()
        for method in METHODS
        if method.upper() in all_method_results
    ]

    if len(method_order) == 0:
        raise RuntimeError("No method results are available for plotting.")

    color_map = make_color_map(RANDOM_SUBSAMPLING_WIDTHS)
    x_ticks = np.arange(END_AGE, START_AGE + X_TICK_STEP, X_TICK_STEP)

    rc_params = {
        "font.size": FONT_SIZE,
        "axes.titlesize": TITLE_SIZE,
        "axes.labelsize": LABEL_SIZE,
        "xtick.labelsize": TICK_SIZE,
        "ytick.labelsize": TICK_SIZE,
        "lines.linewidth": LINE_WIDTH,
        "svg.fonttype": "none",
        "axes.linewidth": 0.5,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
    }

    with plt.rc_context(rc_params):
        fig, axes = plt.subplots(
            nrows=len(method_order),
            ncols=1,
            figsize=(FIG_WIDTH, FIG_HEIGHT),
            sharex=True,
            constrained_layout=False,
        )

        axes = np.atleast_1d(axes)
        x_formatter = ScalarFormatter(useOffset=False)
        x_formatter.set_scientific(False)
        y_formatter = ScalarFormatter(useOffset=False)
        y_formatter.set_scientific(False)

        for ax_index, method in enumerate(method_order):
            ax = axes[ax_index]
            reference_rate = all_method_results[method]["reference_rate"]
            results = all_method_results[method]["results"]

            for width in sorted(RANDOM_SUBSAMPLING_WIDTHS, reverse=True):
                if width not in results:
                    continue

                ensemble_mean = results[width]["ensemble_mean"]
                empirical_lower = results[width]["empirical_lower"]
                empirical_upper = results[width]["empirical_upper"]

                plot_data = pd.concat(
                    [
                        ensemble_mean.rename("ensemble_mean"),
                        empirical_lower.rename("empirical_lower"),
                        empirical_upper.rename("empirical_upper"),
                    ],
                    axis=1,
                ).dropna()

                if plot_data.empty:
                    continue

                x_values = plot_data.index.to_numpy(dtype=float)
                mean_values = plot_data["ensemble_mean"].to_numpy(dtype=float)
                lower_values = plot_data["empirical_lower"].to_numpy(dtype=float)
                upper_values = plot_data["empirical_upper"].to_numpy(dtype=float)
                color = color_map[width]

                ax.fill_between(
                    x_values,
                    lower_values,
                    upper_values,
                    color=color,
                    alpha=FILL_ALPHA,
                    linewidth=0,
                    label="_nolegend_",
                    zorder=1,
                )

                mae_mean = results[width].get("mae_mean", np.nan)
                mape_mean = results[width].get("mape_mean", np.nan)
                legend_label = (
                    f"{width} kyr | "
                    f"MAE={format_scientific(mae_mean)}, "
                    f"MAPE={format_scientific(mape_mean)}%"
                )

                ax.plot(
                    x_values,
                    mean_values,
                    color=color,
                    alpha=LINE_ALPHA,
                    linewidth=LINE_WIDTH,
                    label=legend_label,
                    zorder=2,
                )

            reference_data = reference_rate.dropna().sort_index()

            ax.plot(
                reference_data.index.to_numpy(dtype=float),
                reference_data.to_numpy(dtype=float),
                color="black",
                alpha=REFERENCE_LINE_ALPHA,
                linewidth=REFERENCE_LINE_WIDTH,
                label="Full dataset",
                zorder=10,
            )

            y_min, y_max = get_y_limits(method, timebin_width, reference_rate, results)
            ax.set_ylim(y_min, y_max)
            ax.set_xlim(START_AGE, END_AGE)
            ax.set_title(get_method_title(method), loc="left", pad=2)
            ax.set_ylabel("RoC estimate")
            ax.yaxis.set_major_locator(MaxNLocator(nbins=Y_NBINS, prune=None))
            ax.xaxis.set_major_locator(FixedLocator(x_ticks))
            ax.xaxis.set_major_formatter(x_formatter)
            ax.yaxis.set_major_formatter(y_formatter)
            ax.tick_params(axis="both", which="major", length=2.2, width=0.5)

            for spine in ax.spines.values():
                spine.set_linewidth(0.5)

            ax.legend(
                loc="upper right",
                frameon=True,
                framealpha=0.72,
                facecolor="white",
                edgecolor="none",
                fontsize=LEGEND_SIZE,
                handlelength=1.5,
                handletextpad=0.45,
                borderpad=0.25,
                labelspacing=0.25,
                borderaxespad=0.25,
            )

            if ax_index < len(method_order) - 1:
                ax.tick_params(labelbottom=False)

        axes[-1].set_xlabel("Age (kyr)")
        plt.tight_layout(rect=[0.055, 0.065, 0.99, 0.985])

        out_svg = OUT_DIR / f"{OUT_PREFIX}_RoC_sampling_density_sensitivity_{timebin_width}kyr.svg"
        fig.savefig(out_svg, format="svg")
        plt.close(fig)

    return out_svg


def run_one_timebin_width(data, timebin_width, rng):
    age_nodes = np.arange(END_AGE, START_AGE + AGE_INTERVAL, AGE_INTERVAL)
    all_method_results = {}
    combined_metrics = []

    for method in METHODS:
        method = method.upper()

        if VERBOSE:
            print("=" * 80)
            print(f"Processing timebin width: {timebin_width} kyr")
            print(f"Processing method: {method}")

        reference_rate = compute_method_rate_series(
            data=data,
            age_nodes=age_nodes,
            method=method,
            timebin_width=timebin_width,
        )

        results = {}

        for subsampling_width in RANDOM_SUBSAMPLING_WIDTHS:
            (
                ensemble_mean,
                empirical_lower,
                empirical_upper,
                mae_mean,
                mape_mean,
                all_iterations,
                metrics,
            ) = compute_random_subsampling_statistics(
                data=data,
                age_nodes=age_nodes,
                method=method,
                subsampling_width=subsampling_width,
                n_iter=N_ITER,
                reference_rate=reference_rate,
                rng=rng,
                timebin_width=timebin_width,
            )

            results[subsampling_width] = {
                "ensemble_mean": ensemble_mean,
                "empirical_lower": empirical_lower,
                "empirical_upper": empirical_upper,
                "mae_mean": mae_mean,
                "mape_mean": mape_mean,
                "all_iterations": all_iterations,
            }

            combined_metrics.append(metrics)

            if SAVE_METRICS:
                metrics_path = (
                    OUT_DIR
                    / f"{OUT_PREFIX}_{method}_{timebin_width}kyr_{subsampling_width}kyr_metrics.csv"
                )
                metrics.to_csv(metrics_path, index=False)

            if SAVE_ALL_ITERATIONS:
                iterations_path = (
                    OUT_DIR
                    / f"{OUT_PREFIX}_{method}_{timebin_width}kyr_{subsampling_width}kyr_all_iterations.csv"
                )
                all_iterations.to_csv(iterations_path, index=True, index_label="Age_kyr")

        if SAVE_SUMMARY_CURVES:
            save_method_summary_curves(method, reference_rate, results, timebin_width)

        all_method_results[method] = {
            "reference_rate": reference_rate,
            "results": results,
        }

    out_svg = plot_all_methods(all_method_results, timebin_width)

    if SAVE_COMBINED_METRICS and combined_metrics:
        combined_metrics_table = pd.concat(combined_metrics, ignore_index=True)
        metrics_summary = (
            combined_metrics_table
            .groupby(["Timebin_width_kyr", "Method", "Random_subsampling_width_kyr"], as_index=False)
            .agg(
                MAE_mean=("MAE", "mean"),
                MAE_sd=("MAE", "std"),
                MAPE_mean=("MAPE_percent", "mean"),
                MAPE_sd=("MAPE_percent", "std"),
            )
        )

        combined_metrics_path = OUT_DIR / f"{OUT_PREFIX}_{timebin_width}kyr_combined_metrics.csv"
        metrics_summary_path = OUT_DIR / f"{OUT_PREFIX}_{timebin_width}kyr_metrics_summary.csv"
        combined_metrics_table.to_csv(combined_metrics_path, index=False)
        metrics_summary.to_csv(metrics_summary_path, index=False)

    return out_svg


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)
    data = load_input_data()

    if VERBOSE:
        print(f"Input data points: {len(data)}")
        print(f"Output directory: {OUT_DIR}")

    for timebin_width in TIMEBIN_WIDTHS:
        out_svg = run_one_timebin_width(data, timebin_width, rng)

        if VERBOSE:
            print(f"Saved combined SVG: {out_svg}")

    print("Processing completed.")


if __name__ == "__main__":
    main()
