# Deeptime RoC Analysis

![Deeptime RoC Analysis logo](logo.png)

[![Release](https://img.shields.io/badge/release-v1.0.1-blue.svg)](https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime/releases/tag/v1.0.1)
[![Smoke test](https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime/actions/workflows/smoke-test.yml/badge.svg)](https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime/actions/workflows/smoke-test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Deeptime RoC Analysis** is a reproducible workflow for multi-timescale
rate-of-change (RoC) analysis of irregular deep-time palaeoclimate and
palaeoenvironmental records. It is available as Python source code and as a
standalone Windows application with a five-step graphical interface.

- Current release: [v1.0.1](https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime/releases/tag/v1.0.1)
- Release date: 2026-08-31
- License: [MIT](LICENSE)
- Documentation: [English Windows user manual](docs/Deeptime_RoC_Analysis_Windows_User_Manual_v1.0.1.pdf)

## What the workflow does

The main workflow performs:

1. preprocessing of age-value data;
2. sliding time-bin calculation;
3. distance-count weighted interpolation using the nearest valid bin on each
   side of an internal missing target;
4. RoC estimation with Inter-bin Rate (IBR), Theil-Sen regression (TS), and
   Interquartile Range (IQR);
5. multi-timescale result merging;
6. Log-Rate-Interval (LRI) regression and time-scale correction;
7. nTV and Gini evaluation;
8. PWLF breakpoint detection;
9. method-specific KDE consensus breakpoint detection;
10. method-specific phase statistics; and
11. automatic table and figure generation.

IBR and TS are time-explicit RoC estimators. IQR is treated as a within-bin
variability metric rather than a conventional rate estimator.

> **Scope note:** The sampling-density sensitivity experiments reported in the
> associated manuscript are implemented as a separate reproducibility analysis
> in `roc/sensitivity.py`; they are not part of the v1.0.1 graphical workflow.

## Windows application: quick start

1. Download `RoC_Workflow_Windows_v1.0.1.zip` from the
   [v1.0.1 release](https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime/releases/tag/v1.0.1).
2. Verify the accompanying SHA-256 checksum if required.
3. Extract the complete archive into one folder.
4. Keep `_internal` beside `RoC_Workflow.exe`.
5. Double-click `RoC_Workflow.exe`.
6. On **Run & Log**, select **Check settings / Dry run** before the first full
   calculation.

The executable filename remains `RoC_Workflow.exe` for v1.0.1 compatibility;
the software name shown in the interface and documentation is
**Deeptime RoC Analysis**.

The five GUI pages are:

1. **Input Data** - select an Excel file, sheet, age column, value column,
   sorting, and optional Z-score normalization.
2. **RoC Settings** - set the age interval, output step, analytical time-bin
   widths, methods, and interpolation.
3. **Advanced Analysis** - enable LRI, nTV/Gini, PWLF, KDE, phase statistics,
   and figure generation.
4. **Run & Log** - validate settings, run the workflow, monitor progress, and
   inspect diagnostics.
5. **Results Preview** - browse tables, logs, and generated PNG figures.

## Run from source

### Requirements

- Python 3.10 or later
- packages listed in `requirements.txt`

```bash
git clone https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime.git
cd Rates-of-Change-for-Deeptime
python -m venv .venv
```

Activate the environment, then choose one installation route:

```bash
# General compatible environment
python -m pip install -r requirements.txt

# Exact Python 3.12 environment used to finalize v1.0.1
python -m pip install -r requirements-lock.txt
```

Launch the GUI directly:

```bash
python gui.py
```

Windows and macOS launchers are also provided:

```text
start_gui_windows.bat
start_gui_mac.command
```

## Input data

Input must be an Excel workbook containing at least two numeric columns:

| Column | Meaning | Unit |
|---|---|---|
| `Age` | Sample age | kyr |
| `Value` | Continuous proxy value | User-defined |

If age is originally expressed in Ma, multiply it by 1000 before analysis.
Invalid age-value rows are removed, duplicate ages are averaged, and records
can be sorted automatically. The included `data/O.xlsx` is the main example
and manuscript input. The full sampling-density input is archived as
`data/CENOGRID_benthic_d18O_sampling_density.xlsx`.

## Validation and manuscript reproduction

`config_test.yaml` is a short software-validation configuration. It uses three
representative analytical scales and intentionally differs from the manuscript
configuration in resolution, Z-score use, and IQR settings. It must not be used
as the parameter record for the published analysis.

Validate the example input and test configuration:

```bash
python main.py --config config_test.yaml --dry-run
```

Run the short validation workflow:

```bash
python main.py --config config_test.yaml
```

`config_full.yaml` records the exact main-workflow parameters used for the
associated manuscript: a 10 kyr output step, analytical windows from 50 to
1000 kyr in 50 kyr increments, inclusive-linear IQR, and the published PWLF,
KDE, and phase settings.

```bash
python main.py --config config_full.yaml
```

Run the separate sampling-density experiment:

```bash
python run_sampling_density_analysis.py
```

This analysis uses 200 random iterations for every method-window-subsampling
combination and can require substantial time and disk space. See
[docs/SAMPLING_DENSITY_ANALYSIS.md](docs/SAMPLING_DENSITY_ANALYSIS.md) for the
design, fixed random seed, archived outputs, and interpretation of MAE and MAPE.

Use `--debug` with a `main.py` command to display the full traceback.

## Configuration

The YAML files control input, output, time-bin widths, interpolation, methods,
LRI, metrics, breakpoint detection, KDE, phase statistics, and plotting.

For distance-count weighted interpolation, an internal missing target at age
`t` uses only the nearest valid bin on each side. If these bracketing bins are
`prev` and `next`, their weights are
`w_i = Counts_i^alpha / |Age_i - t|^beta`, and the interpolated value is
`(w_prev*x_prev + w_next*x_next) / (w_prev + w_next)`. More distant valid bins
do not contribute. The configured edge mode applies only when a missing target
lies outside the valid age range.

## Output structure

```text
outputs/
|-- 00_preprocessed/
|-- 01_timebin/
|-- 02_interpolated/
|-- 03_rate/
|-- 04_merged/
|-- 05_lri/
|-- 06_normalized/
|-- 07_metrics/
|-- 08_pwlf/
|-- 09_kde/
|-- 10_phase/
|-- figures/
`-- logs/
```

The run summary records the input, configuration, completed methods, and output
files. Ordinary run outputs are excluded from Git; the publication-supporting
subset is deliberately versioned under `results/`.

## Article result archive

The `results/` directory contains the numerical and graphical outputs used to
support the associated manuscript:

- `results/RoC_raw/`: time-scale-specific IBR, TS, and IQR results;
- `results/RoC_norm/`: merged LRI-corrected relative RoC tables;
- `results/PWLF/`: breakpoint and significance tables for 50-1000 kyr;
- `results/KDE/`: pooled breakpoint tables, KDE peaks, and density figures;
- `results/Phase/`: phase-level figures for IBR, TS, and IQR;
- `results/sampling_density/`: compact sensitivity metrics, ensemble summaries,
  and Appendix C vector figures;
- `results/MANIFEST.csv`: machine-readable inventory with normalized file sizes
  and SHA-256 hashes;
- `results/checksums.sha256`: plain-text checksum list; and
- `results/DATA_DICTIONARY.md`: field definitions and interpretation notes.

The complete 200-iteration sampling-density tables are supplied as the separate
release asset `RoC_sampling_density_full_iterations_v1.0.1.zip`.

See [results/README.md](results/README.md) for interpretation and citation
guidance.

## Method summary

- **IBR:** time-bin mean -> interpolation -> inter-bin rate.
- **TS:** robust Theil-Sen slope within each time bin -> interpolation.
- **IQR:** within-bin interquartile range -> interpolation.
- **LRI correction:** observed RoC divided by the method- and scale-specific
  fitted baseline.
- **Phase analysis:** PWLF candidate breakpoints -> method-specific KDE
  consensus -> phase statistics.

See [docs/METHODS.md](docs/METHODS.md) for implementation details.

## Repository structure

```text
.
|-- main.py
|-- gui.py
|-- run_sampling_density_analysis.py
|-- roc/
|-- data/
|-- results/
|-- docs/
|-- tests/
|-- config_test.yaml
|-- config_full.yaml
|-- requirements.txt
|-- requirements-lock.txt
|-- CITATION.cff
`-- .github/
```

## Citation

Please cite the associated manuscript and the exact
[Deeptime RoC Analysis v1.0.1 release](https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime/releases/tag/v1.0.1).
GitHub can generate a formatted software citation from `CITATION.cff` using the
**Cite this repository** button.

## Contributing and support

- Report reproducible problems with the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml).
- Propose enhancements with the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml).
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.
- For security-sensitive reports, follow [SECURITY.md](SECURITY.md).

## License

Deeptime RoC Analysis is released under the [MIT License](LICENSE).
