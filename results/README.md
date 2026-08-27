# Article result archive

This directory contains intermediate numerical results and vector graphics used
for the associated manuscript on Cenozoic rates of change. The archive is kept
in the same repository as **Deeptime RoC Analysis v1.0.1** so that the software,
configuration, and manuscript results can be accessed through one versioned
location.

## Directory guide

| Directory | Contents |
|---|---|
| `RoC_raw/` | Time-scale-specific IBR, TS, and IQR tables before cross-scale merging |
| `RoC_norm/` | Merged LRI-corrected relative RoC results for all 50-1000 kyr scales |
| `PWLF/` | Piecewise-linear breakpoint and significance results for each metric and time scale |
| `KDE/` | Pooled breakpoint tables, confidence-weighted KDE peaks, and SVG density figures |
| `Phase/` | Phase-summary SVG figures for IBR, TS, and IQR at 50-1000 kyr |

The six IBR consensus boundaries used in the manuscript occur at approximately
55.97, 42.14, 33.76, 24.34, 13.27, and 3.63 Ma. They divide the record into
seven phases. Phase classes in Fig. 6 are assigned independently within each
analytical scale by ranking the arithmetic phase means of LRI-corrected
relative IBR RoC. The labels therefore describe phase-mean rankings, not the
largest individual RoC peak.

## Representative manuscript results

- `Phase/IBR/Hist_Timescale_100kyr.svg`: orbital-scale IBR phase summary.
- `Phase/IBR/Hist_Timescale_1000kyr.svg`: tectonic-scale IBR phase summary.
- `KDE/O_IBR_all_PWLF_breakpoints_50-1000_5to10_W_KDE_density_peaks.svg`:
  confidence-weighted KDE of IBR candidate breakpoints.
- `RoC_norm/O_IBR_all.xlsx`: merged LRI-corrected relative IBR series.

## Inventory and integrity

`MANIFEST.csv` lists every archived result with its relative path, category,
metric, analytical time scale (when encoded in the filename), file size, and
SHA-256 digest. `checksums.sha256` provides the same hashes in a standard
checksum-list format. See `DATA_DICTIONARY.md` for abbreviations and common
fields.

## Reuse and citation

Please cite both the associated manuscript and the software release identified
in the repository-level `CITATION.cff`. The original CENOGRID data source must
also be cited when these derived results are reused. The repository MIT License
applies to the software code; third-party source data remain subject to their
original terms.

Repository: <https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime>

