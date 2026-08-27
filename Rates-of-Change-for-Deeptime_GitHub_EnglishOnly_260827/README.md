# Deeptime RoC Analysis

![Deeptime RoC Analysis logo](logo.png)

**Deeptime RoC Analysis** is a reproducible workflow for multi-timescale
rate-of-change (RoC) analysis of irregular deep-time palaeoclimate and
palaeoenvironmental records. It is available as Python source code and as a
standalone Windows application with a stepwise graphical interface.

Current release: **v1.0.1**  
License: **MIT**  
Documentation: [English Windows manual](docs/Deeptime_RoC_Analysis_Windows_User_Manual_v1.0.1.pdf) and [upload guide](UPLOAD_GUIDE.md)

## What the workflow does

The main workflow performs:

1. preprocessing of age-value data;
2. sliding time-bin calculation;
3. distance-count weighted interpolation;
4. RoC estimation with Inter-bin Rate (IBR), Theil-Sen regression (TS), and Interquartile Range (IQR);
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
> associated manuscript are maintained as a separate analysis and are not part
> of the v1.0.1 main GUI workflow.

## Graphical application

The Windows GUI guides users through five pages:

1. **Input Data** — choose an Excel file, sheet, age column, value column, sorting, and optional Z-score normalization.
2. **RoC Settings** — set the age interval, output step, time-bin widths, methods, and interpolation.
3. **Advanced Analysis** — enable LRI, metrics, PWLF, KDE, phase statistics, and figures.
4. **Run & Log** — validate settings, run the workflow, monitor progress, and inspect logs.
5. **Results Preview** — browse tables, logs, and generated PNG figures.

Download the packaged Windows application from the repository's
[Releases page](https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime/releases).
After extracting the archive, keep its folder structure intact and launch
`RoC_Workflow.exe`.

## Run from source

### Requirements

- Python 3.10 or later
- packages listed in `requirements.txt`

### Installation

```bash
git clone https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime.git
cd Rates-of-Change-for-Deeptime
python -m venv .venv
```

Activate the environment and install dependencies:

```bash
python -m pip install -r requirements.txt
```

On Windows, the included launcher can prepare the environment and open the GUI:

```text
start_gui_windows.bat
```

To launch the GUI directly:

```bash
python gui.py
```

## Input data

Input must be an Excel workbook containing at least two numeric columns:

| Column | Meaning | Unit |
|---|---|---|
| `Age` | sample age | kyr |
| `Value` | continuous proxy value | user-defined |

If age is originally expressed in Ma, multiply it by 1000 before analysis.
Invalid age-value rows are removed, duplicate ages are averaged, and records can
be sorted automatically. The included `data/O.xlsx` provides an example input.

## Quick test

Validate the example configuration without running the full workflow:

```bash
python main.py --config config_test.yaml --dry-run
```

Run the short test configuration:

```bash
python main.py --config config_test.yaml
```

Run the full 50-1000 kyr analysis:

```bash
python main.py --config config_full.yaml
```

Use `--debug` with any command to display the full traceback.

## Configuration

The YAML files control input, output, time-bin widths, interpolation, methods,
LRI, metrics, breakpoint detection, KDE, phase statistics, and plotting.

- `config_test.yaml`: quick validation and representative scales.
- `config_full.yaml`: formal analysis from 50 to 1000 kyr in 50 kyr increments.

GUI settings override corresponding YAML values at runtime; advanced parameters
that are not shown in the GUI remain controlled by the selected YAML file.

## Output structure

```text
outputs/
├── 01_timebin/
├── 02_interpolated/
├── 03_rate/
├── 04_merged/
├── 05_lri/
├── 06_normalized/
├── 07_metrics/
├── 08_pwlf/
├── 09_kde/
├── 10_phase/
├── figures/
└── logs/
```

The run summary records the input, configuration, completed methods, and output
files. Generated outputs are intentionally excluded from Git.

## Article result archive

The `results/` directory contains the numerical and graphical outputs used to
support the associated manuscript. These archived results are intentionally
versioned with the software so that the calculations, representative figures,
and phase interpretation can be traced to the same release.

- `results/RoC_raw/`: time-scale-specific IBR, TS, and IQR results;
- `results/RoC_norm/`: merged LRI-corrected relative RoC tables;
- `results/PWLF/`: breakpoint and significance tables for 50-1000 kyr;
- `results/KDE/`: pooled breakpoint tables, KDE peaks, and density figures;
- `results/Phase/`: phase-level figures for IBR, TS, and IQR;
- `results/MANIFEST.csv`: machine-readable inventory with file sizes and hashes;
- `results/DATA_DICTIONARY.md`: definitions of directories, metrics, and fields.

See [results/README.md](results/README.md) for interpretation and citation
guidance. The Windows executable remains a release asset rather than part of
the ordinary Git history because of its archive size.

## Method summary

- **IBR:** time-bin mean → interpolation → inter-bin rate.
- **TS:** robust Theil-Sen slope within each time bin → interpolation.
- **IQR:** within-bin interquartile range → interpolation.
- **LRI correction:** observed RoC divided by the method-specific fitted baseline at each analytical time scale.
- **Phase analysis:** PWLF candidate breakpoints → method-specific KDE consensus → phase statistics.

See [docs/METHODS.md](docs/METHODS.md) for implementation details.

## Repository structure

```text
.
├── main.py
├── gui.py
├── roc/
├── data/
├── results/
├── docs/
├── config_test.yaml
├── config_full.yaml
├── requirements.txt
├── CITATION.cff
├── .github/
├── UPLOAD_GUIDE.md
└── UPLOAD_TO_GITHUB.bat
```

## Citation

Please cite the associated manuscript and the software release. GitHub can
generate a formatted software citation from `CITATION.cff` using the
**Cite this repository** button.

## Contributing and support

- Report reproducible problems with the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml).
- Propose enhancements with the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml).
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.
- For security-sensitive reports, follow [SECURITY.md](SECURITY.md).

## License

This project is released under the [MIT License](LICENSE).
