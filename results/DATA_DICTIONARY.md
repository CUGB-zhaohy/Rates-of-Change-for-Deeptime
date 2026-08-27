# Result data dictionary

## Core abbreviations

| Abbreviation | Meaning |
|---|---|
| RoC | Rate of change |
| IBR | Inter-bin Rate, calculated between time bins separated by the analytical time scale |
| TS | Theil-Sen regression slope within a time bin |
| IQR | Interquartile Range within a time bin; a variability metric rather than a direct temporal rate |
| LRI | Log-Rate-Interval analysis used to quantify and correct first-order interval dependence |
| PWLF | Piecewise linear fitting of the cumulative corrected RoC series |
| KDE | Kernel density estimation used to integrate candidate breakpoint ages |
| kyr | Thousand years |
| Ma | Million years before present |

## Naming conventions

- `O_` identifies outputs derived from the example/manuscript input workbook
  `O.xlsx`.
- A number such as `_100_` or `Timescale_100` denotes a 100 kyr analytical
  window; scales run from 50 to 1000 kyr in 50 kyr increments.
- `_interp` denotes a series placed on the common 10 kyr output grid after the
  workflow's interpolation step.
- `_all` denotes a merged table containing multiple analytical time scales.
- `_5to10` denotes PWLF candidate models containing 5-10 segments.
- `with_significance` denotes breakpoint tables that include local slope-change
  support and significance diagnostics.

## Common table fields

The exact columns vary by processing stage. Common fields include:

| Field or pattern | Interpretation |
|---|---|
| `Age-point`, `central_age_point`, `Age_kyr` | Central age coordinate in kyr |
| `Timescale_<n>` | Result for analytical time scale `<n>` kyr |
| `RoC_Mean` | Mean proxy value used in time-bin processing; not a phase-mean RoC unless explicitly stated |
| `IBR` | Inter-bin rate estimate |
| `breakpoint` or `breakpoint_age` | PWLF candidate breakpoint age |
| `confidence` | Composite breakpoint-support score based on slope contrast and local fit quality; not a confidence interval |
| `p_value` or `significance` | Local slope-change test result |
| `consensus_age` | KDE consensus breakpoint age, normally in kyr unless a `_Ma` field is provided |
| `density_height`, `prominence`, `FWHM` | KDE peak diagnostics |
| `SD`, `SE`, `95%CI` | Descriptive phase-summary statistics where present |

## Interpretation cautions

1. IBR and TS are time-explicit estimators; IQR summarizes within-bin
   dispersion and should not be interpreted as a conventional temporal rate.
2. Phase colors in Fig. 6 represent rankings of phase means separately within
   the 100 and 1000 kyr series.
3. Breakpoint `confidence` is a dimensionless support score and is not a
   frequentist probability or confidence interval.
4. Excel workbooks are preserved as calculation records; the manifest and SVG
   files provide browser-readable navigation and previews.

