"""
Main entry point for the RoC workflow.

Current available workflow:
- load configuration file
- load raw input Excel data
- preprocess input data
- optional age sorting
- optional Z-score normalization
- save preprocessed input table
- run IBR / TS / IQR workflows
- save timebin, interpolated, and rate tables
- save merged multi-timescale tables
- run LRI regression
- save time-scale-corrected relative RoC tables
- calculate nTV and Gini metrics
- run PWLF breakpoint detection
- run method-specific KDE consensus breakpoint detection
- calculate method-specific phase statistics
- generate summary figures

Run in terminal:
    python main.py --config config_test.yaml
    python main.py --config config_full.yaml
    python main.py --config config_test.yaml --dry-run
    python main.py --config config_test.yaml --debug
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from roc.io import (
    load_config,
    load_raw_input_data_from_config,
    get_output_root,
    prepare_output_directories,
    save_all_roc_outputs,
    save_excel,
    write_run_summary,
)
from roc.pipeline import run_full_workflow
from roc.plotting import run_plotting
from roc.preprocess import (
    get_preprocess_settings,
    preprocess_input_data,
)
def get_project_root() -> Path:
    """
    Get project root in both source-code mode and frozen exe mode.

    If the backend executable is stored inside _internal, the real project root
    is the parent folder of _internal.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent

        if exe_dir.name.lower() == "_internal":
            return exe_dir.parent

        return exe_dir

    return Path(__file__).resolve().parent

def parse_args():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run the multi-timescale RoC workflow."
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config_test.yaml",
        help="Path to the YAML configuration file. Default: config_test.yaml",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check configuration and input data without running the full workflow.",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full Python traceback if an error occurs.",
    )

    return parser.parse_args()


def print_section(title: str):
    """
    Print a clear section title in terminal.
    """
    print("")
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_step(message: str):
    """
    Print a workflow step message.
    """
    print(f"[RoC] {message}", flush=True)

def emit_progress(percent: float, message: str):
    """
    Emit a machine-readable progress message for the GUI.

    Format:
        __ROC_PROGRESS__|percent|message
    """
    percent = max(0, min(100, int(round(float(percent)))))
    print(f"__ROC_PROGRESS__|{percent}|{message}", flush=True)

def resolve_project_path(project_root: Path, path_text: str) -> Path:
    """
    Resolve a path relative to project root if it is not absolute.
    """
    path = Path(path_text)

    if not path.is_absolute():
        path = project_root / path

    return path.resolve()


def preflight_check(config: dict, project_root: Path):
    """
    Check important files and settings before running the workflow.
    """
    input_config = config.get("input", {})
    input_file_text = input_config.get("file", "data/O.xlsx")

    input_file = resolve_project_path(
        project_root=project_root,
        path_text=input_file_text,
    )

    if not input_file.exists():
        raise FileNotFoundError(
            f"Input file was not found: {input_file}\n"
            "Please check the 'input.file' setting in your config file."
        )

    age_column = input_config.get("age_column", "Age")
    value_column = input_config.get("value_column", "Value")

    timebin_config = config.get("timebin", {})
    widths = timebin_config.get("widths_kyr", [])

    if len(widths) == 0:
        raise ValueError(
            "No time-bin widths were defined. "
            "Please check 'timebin.widths_kyr' in your config file."
        )

    return {
        "input_file": input_file,
        "age_column": age_column,
        "value_column": value_column,
        "n_timescales": len(widths),
        "widths": widths,
    }


def print_config_summary(
    config: dict,
    preflight_info: dict,
    output_root: Path,
):
    """
    Print a concise summary of key configuration settings.
    """
    timebin_config = config.get("timebin", {})
    analysis_config = config.get("analysis", {})
    methods_config = config.get("methods", {})
    preprocess_settings = get_preprocess_settings(config)

    iqr_quartile_method = str(
        methods_config.get("iqr_quartile_method", "exc")
    ).strip().upper()

    iqr_min_count = methods_config.get("iqr_min_count", 5)

    print_step("Configuration summary:")
    print(f"  Input file       : {preflight_info['input_file']}")
    print(f"  Age column       : {preflight_info['age_column']}")
    print(f"  Value column     : {preflight_info['value_column']}")
    print(f"  Output directory : {output_root}")
    print(f"  Timebin step   : {timebin_config.get('resolution_kyr', 'NA')} kyr")
    print(f"  Number of scales : {preflight_info['n_timescales']}")
    print(f"  Sort by age      : {preprocess_settings['sort_by_age']}")
    print(f"  Use Z-score      : {preprocess_settings['use_zscore']}")
    print(f"  IQR quartile     : {iqr_quartile_method}")
    print(f"  IQR min count    : {iqr_min_count}")
    print(f"  Run LRI          : {analysis_config.get('run_lri', True)}")
    print(f"  Run metrics      : {analysis_config.get('run_metrics', True)}")
    print(f"  Run PWLF         : {analysis_config.get('run_pwlf', True)}")
    print(f"  Run KDE          : {analysis_config.get('run_kde', True)}")
    print(f"  Run phase        : {analysis_config.get('run_phase', True)}")
    print(f"  Run plotting     : {analysis_config.get('run_plotting', True)}")


def print_preprocess_summary(preprocess_summary: dict):
    """
    Print preprocessing summary in terminal.
    """
    print_step("Preprocessing summary:")
    print(f"  Age column                 : {preprocess_summary['age_column']}")
    print(f"  Original value column      : {preprocess_summary['original_value_column']}")
    print(f"  Active value column        : {preprocess_summary['active_value_column']}")
    print(f"  Sort by age                : {preprocess_summary['sort_by_age']}")
    print(f"  Use Z-score                : {preprocess_summary['use_zscore']}")
    print(f"  Original rows              : {preprocess_summary['n_original_rows']}")
    print(f"  Valid rows after dropna    : {preprocess_summary['n_valid_rows_after_dropna']}")
    print(
        "  Rows after age averaging   : "
        f"{preprocess_summary['n_rows_after_duplicate_age_average']}"
    )
    print(f"  Removed invalid rows       : {preprocess_summary['n_removed_invalid_rows']}")
    print(
        "  Merged duplicate-age rows  : "
        f"{preprocess_summary['n_merged_duplicate_age_rows']}"
    )

    if preprocess_summary["use_zscore"]:
        print(f"  Z-score column             : {preprocess_summary['zscore_column']}")
        print(f"  Z-score mean               : {preprocess_summary['zscore_mean']}")
        print(f"  Z-score std                : {preprocess_summary['zscore_std']}")


def add_preprocess_summary_lines(
    summary_lines: list[str],
    preprocess_summary: dict,
    preprocessed_path: Path | None,
):
    """
    Add preprocessing information to run summary.
    """
    summary_lines.append("")
    summary_lines.append("Preprocessing:")
    summary_lines.append(f"- Age column: {preprocess_summary['age_column']}")
    summary_lines.append(
        f"- Original value column: {preprocess_summary['original_value_column']}"
    )
    summary_lines.append(
        f"- Active value column: {preprocess_summary['active_value_column']}"
    )
    summary_lines.append(f"- Sort by age: {preprocess_summary['sort_by_age']}")
    summary_lines.append(f"- Use Z-score: {preprocess_summary['use_zscore']}")
    summary_lines.append(f"- Original rows: {preprocess_summary['n_original_rows']}")
    summary_lines.append(
        f"- Valid rows after dropna: "
        f"{preprocess_summary['n_valid_rows_after_dropna']}"
    )
    summary_lines.append(
        f"- Rows after duplicate-age averaging: "
        f"{preprocess_summary['n_rows_after_duplicate_age_average']}"
    )
    summary_lines.append(
        f"- Removed invalid rows: {preprocess_summary['n_removed_invalid_rows']}"
    )
    summary_lines.append(
        f"- Merged duplicate-age rows: "
        f"{preprocess_summary['n_merged_duplicate_age_rows']}"
    )

    if preprocess_summary["use_zscore"]:
        summary_lines.append(f"- Z-score column: {preprocess_summary['zscore_column']}")
        summary_lines.append(f"- Z-score mean: {preprocess_summary['zscore_mean']}")
        summary_lines.append(f"- Z-score std: {preprocess_summary['zscore_std']}")

    if preprocessed_path is not None:
        summary_lines.append(f"- Preprocessed input table: {preprocessed_path}")


def main():
    """
    Run the RoC workflow.
    """
    args = parse_args()

    try:
        project_root = get_project_root()

        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = project_root / config_path

        print_section("RoC workflow started")
        print(f"Project root: {project_root}")
        print(f"Config file : {config_path}")
        emit_progress(0, "Workflow started.")

        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file was not found: {config_path}\n"
                "Please provide a valid YAML config file using --config."
            )

        emit_progress(2, "Loading configuration file...")
        print_step("Loading configuration file...")
        config = load_config(config_path)

        output_root = get_output_root(config, project_root=project_root)

        emit_progress(5, "Checking configuration and input file...")
        print_step("Checking configuration and input file...")
        preflight_info = preflight_check(
            config=config,
            project_root=project_root,
        )

        print_config_summary(
            config=config,
            preflight_info=preflight_info,
            output_root=output_root,
        )

        emit_progress(8, "Loading raw input data...")
        print_step("Loading raw input data...")
        raw_data = load_raw_input_data_from_config(
            config=config,
            project_root=project_root,
        )

        emit_progress(12, "Preprocessing input data...")
        print_step("Preprocessing input data...")
        processed_data, active_value_column, preprocess_summary = preprocess_input_data(
            data=raw_data,
            config=config,
        )

        # Tell all downstream modules which value column should be used.
        # If Z-score is disabled, this remains the original value column.
        # If Z-score is enabled, this becomes the Z-score column.
        config.setdefault("input", {})
        config["input"]["value_column"] = active_value_column

        print_step("Input data preprocessed successfully.")
        print_preprocess_summary(preprocess_summary)

        if args.dry_run:
            emit_progress(100, "Dry run completed successfully.")
            print_section("Dry run completed successfully")
            print("Configuration and input data are valid.")
            print("The full workflow was not executed because --dry-run was used.")
            return

        emit_progress(16, "Preparing output directories...")
        output_dirs = prepare_output_directories(output_root)

        print_step(f"Output root: {output_root}")

        preprocess_settings = get_preprocess_settings(config)
        preprocessed_path = None

        if preprocess_settings["save_preprocessed"]:
            preprocessed_path = output_dirs["preprocessed"] / "preprocessed_input.xlsx"

            save_excel(
                table=processed_data,
                file_path=preprocessed_path,
                sheet_name="preprocessed",
                index=False,
            )

            print_step(f"Preprocessed input table saved to: {preprocessed_path}")

        emit_progress(20, "Starting full RoC workflow...")
        print_step("Running full RoC workflow...")

        workflow_result = run_full_workflow(
            data=processed_data,
            config=config,
            progress_callback=emit_progress,
        )

        roc_results = workflow_result["roc_results"]
        merged_rate_tables = workflow_result["merged_rate_tables"]
        lri_results = workflow_result.get("lri_results", {})
        normalized_rate_tables = workflow_result.get("normalized_rate_tables", {})
        metrics_results = workflow_result.get("metrics_results", {})
        pwlf_results = workflow_result.get("pwlf_results", {})
        kde_results = workflow_result.get("kde_results", {})
        phase_results = workflow_result.get("phase_results", {})

        print_step("RoC methods completed:")
        for method_name in roc_results:
            print(f"  - {method_name}")

        emit_progress(88, "Saving RoC method outputs...")
        print_step("Saving RoC method outputs...")
        saved_paths = save_all_roc_outputs(
            roc_results=roc_results,
            output_dirs=output_dirs,
        )

        emit_progress(90, "Saving merged multi-timescale tables...")
        print_step("Saving merged multi-timescale tables...")
        merged_saved_paths = {}

        for method_name, merged_table in merged_rate_tables.items():
            merged_path = output_dirs["merged"] / f"{method_name}_all_timescales.xlsx"

            save_excel(
                table=merged_table,
                file_path=merged_path,
                sheet_name="merged",
                index=False,
            )

            merged_saved_paths[method_name] = merged_path

        print_step("Saving LRI regression outputs...")
        lri_saved_paths = {}

        for method_name, method_lri_result in lri_results.items():
            method_paths = {}

            summary_path = (
                output_dirs["lri"] / f"{method_name}_lri_regression_summary.xlsx"
            )
            points_path = output_dirs["lri"] / f"{method_name}_lri_points.xlsx"
            quantiles_path = (
                output_dirs["lri"] / f"{method_name}_lri_quantile_points.xlsx"
            )

            save_excel(
                table=method_lri_result["summary"],
                file_path=summary_path,
                sheet_name="summary",
                index=False,
            )

            save_excel(
                table=method_lri_result["points"],
                file_path=points_path,
                sheet_name="points",
                index=False,
            )

            save_excel(
                table=method_lri_result["quantiles"],
                file_path=quantiles_path,
                sheet_name="quantiles",
                index=False,
            )

            method_paths["summary"] = summary_path
            method_paths["points"] = points_path
            method_paths["quantiles"] = quantiles_path

            lri_saved_paths[method_name] = method_paths

        print_step("Saving time-scale-corrected relative RoC tables...")
        corrected_saved_paths = {}

        for method_name, corrected_table in normalized_rate_tables.items():
            corrected_path = (
                output_dirs["normalized"]
                / f"{method_name}_time_scale_corrected_relative_roc.xlsx"
            )

            save_excel(
                table=corrected_table,
                file_path=corrected_path,
                sheet_name="corrected",
                index=False,
            )

            corrected_saved_paths[method_name] = corrected_path

        print_step("Saving nTV and Gini metric outputs...")
        metrics_saved_paths = {}

        for metrics_name, metrics_table in metrics_results.items():
            if metrics_table is None or metrics_table.empty:
                continue

            metrics_path = output_dirs["metrics"] / f"metrics_{metrics_name}.xlsx"

            save_excel(
                table=metrics_table,
                file_path=metrics_path,
                sheet_name="metrics",
                index=False,
            )

            metrics_saved_paths[metrics_name] = metrics_path

        print_step("Saving PWLF breakpoint outputs...")
        pwlf_saved_paths = {}

        for output_name, output_table in pwlf_results.items():
            if output_table is None or output_table.empty:
                continue

            pwlf_path = output_dirs["pwlf"] / f"pwlf_{output_name}.xlsx"

            save_excel(
                table=output_table,
                file_path=pwlf_path,
                sheet_name=output_name[:31],
                index=False,
            )

            pwlf_saved_paths[output_name] = pwlf_path

        print_step("Saving KDE consensus breakpoint outputs...")
        kde_saved_paths = {}

        for output_name, output_table in kde_results.items():
            if output_table is None or output_table.empty:
                continue

            kde_path = output_dirs["kde"] / f"kde_{output_name}.xlsx"

            save_excel(
                table=output_table,
                file_path=kde_path,
                sheet_name=output_name[:31],
                index=False,
            )

            kde_saved_paths[output_name] = kde_path

        print_step("Saving phase analysis outputs...")
        phase_saved_paths = {}

        for output_name, output_table in phase_results.items():
            if output_table is None or output_table.empty:
                continue

            phase_path = output_dirs["phase"] / f"phase_{output_name}.xlsx"

            save_excel(
                table=output_table,
                file_path=phase_path,
                sheet_name=output_name[:31],
                index=False,
            )

            phase_saved_paths[output_name] = phase_path

        emit_progress(96, "Generating summary figures...")
        print_step("Generating summary figures...")
        figure_saved_paths = run_plotting(
            workflow_result=workflow_result,
            config=config,
            output_dir=output_dirs["figures"],
        )

        methods_config = config.get("methods", {})
        iqr_quartile_method = str(
            methods_config.get("iqr_quartile_method", "exc")
        ).strip().lower()
        iqr_min_count = methods_config.get("iqr_min_count", 5)

        summary_lines = [
            "RoC workflow run summary",
            "=" * 40,
            f"Project root: {project_root}",
            f"Config file: {config_path}",
            f"Output root: {output_root}",
            f"Number of valid input points: {len(processed_data)}",
            f"IQR quartile method: {iqr_quartile_method}",
            f"IQR min count: {iqr_min_count}",
        ]

        add_preprocess_summary_lines(
            summary_lines=summary_lines,
            preprocess_summary=preprocess_summary,
            preprocessed_path=preprocessed_path,
        )

        summary_lines.extend(
            [
                "",
                "Completed methods:",
            ]
        )

        for method_name, method_saved in saved_paths.items():
            summary_lines.append(f"- {method_name}")

            for stage_name, paths in method_saved.items():
                summary_lines.append(f"  {stage_name}: {len(paths)} files")

        summary_lines.append("")
        summary_lines.append("Merged tables:")

        for method_name, merged_path in merged_saved_paths.items():
            summary_lines.append(f"- {method_name}: {merged_path}")

        if lri_saved_paths:
            summary_lines.append("")
            summary_lines.append("LRI regression outputs:")

            for method_name, method_paths in lri_saved_paths.items():
                summary_lines.append(f"- {method_name}")

                for output_name, output_path in method_paths.items():
                    summary_lines.append(f"  {output_name}: {output_path}")

        if corrected_saved_paths:
            summary_lines.append("")
            summary_lines.append("Time-scale-corrected relative RoC tables:")

            for method_name, corrected_path in corrected_saved_paths.items():
                summary_lines.append(f"- {method_name}: {corrected_path}")

        if metrics_saved_paths:
            summary_lines.append("")
            summary_lines.append("Metric outputs:")

            for metrics_name, metrics_path in metrics_saved_paths.items():
                summary_lines.append(f"- {metrics_name}: {metrics_path}")

        if pwlf_saved_paths:
            summary_lines.append("")
            summary_lines.append("PWLF breakpoint outputs:")

            for output_name, pwlf_path in pwlf_saved_paths.items():
                summary_lines.append(f"- {output_name}: {pwlf_path}")

        if kde_saved_paths:
            summary_lines.append("")
            summary_lines.append("KDE consensus breakpoint outputs:")

            for output_name, kde_path in kde_saved_paths.items():
                summary_lines.append(f"- {output_name}: {kde_path}")

        if phase_saved_paths:
            summary_lines.append("")
            summary_lines.append("Phase analysis outputs:")

            for output_name, phase_path in phase_saved_paths.items():
                summary_lines.append(f"- {output_name}: {phase_path}")

        if figure_saved_paths:
            summary_lines.append("")
            summary_lines.append("Figure outputs:")

            for figure_name, figure_path in figure_saved_paths.items():
                summary_lines.append(f"- {figure_name}: {figure_path}")

        summary_path = write_run_summary(
            summary_lines=summary_lines,
            output_dirs=output_dirs,
            filename="run_summary.txt",
        )

        emit_progress(100, "Workflow completed successfully.")

        print("")
        print("=" * 80)
        print("RoC workflow completed successfully.")
        print(f"Run summary saved to: {summary_path}")
        print("=" * 80)

    except Exception as exc:
        print("")
        print("=" * 80)
        print("RoC workflow failed")
        print("=" * 80)
        print(f"Error type   : {type(exc).__name__}")
        print(f"Error message: {exc}")

        if args.debug:
            print("")
            print("Debug mode is enabled. Full traceback:")
            raise

        print("")
        print("Tip: run again with --debug to show the full traceback.")
        sys.exit(1)


if __name__ == "__main__":
    main()