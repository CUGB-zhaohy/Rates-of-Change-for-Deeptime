# Sampling-density result archive

This directory contains the compact numerical and graphical outputs from the
random-subsampling sensitivity experiment described in the associated
manuscript and in `docs/SAMPLING_DENSITY_ANALYSIS.md`.

## Contents

| Directory | Contents |
|---|---|
| `metrics/` | Per-iteration MAE and MAPE tables for 18 experiment configurations |
| `summary_curves/` | Full-data references, ensemble means, and empirical 95% intervals |
| `figures/` | Appendix C vector figures for the 100 and 1000 kyr analytical windows |

The 18 configurations comprise three methods (IBR, TS, and IQR), two
analytical windows (100 and 1000 kyr), and three random-subsampling intervals
(20, 50, and 100 kyr). Each configuration contains 200 iterations.

Complete iteration-by-age tables are supplied separately in the GitHub Release
asset `RoC_sampling_density_full_iterations_v1.0.1.zip` to avoid adding
approximately 470 MB of highly repetitive tables to ordinary Git history.

`MANIFEST.csv` lists every file in this compact archive, and
`checksums.sha256` provides SHA-256 digests for integrity verification.

## Metric caution

MAPE can become extremely large where the full-data reference is close to zero,
especially for time-explicit rate estimators. Evaluate MAPE together with MAE,
the ensemble mean, and the empirical interval. Cross-method comparison also
requires caution because IBR, TS, and IQR do not share a common numerical scale
or interpretation.
