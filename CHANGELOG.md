# Changelog

All notable software changes are documented here.

## [1.0.1] - 2026-06-12

### Added

- Standalone Windows executable and five-page graphical interface.
- Excel input selection, validation, sorting, duplicate-age averaging, and optional Z-score normalization.
- Configurable IBR, Theil-Sen, and IQR calculations.
- Distance-count weighted interpolation using the nearest valid bin on each side of a missing target, plus linear and disabled interpolation modes.
- LRI scale analysis and corrected relative RoC output.
- nTV and Gini method evaluation.
- PWLF, method-specific KDE consensus breakpoints, and phase statistics.
- SVG and PNG summary figures, run logs, and in-application result preview.
- Non-interactive figure rendering for reliable execution in the packaged Windows backend.
- English Windows user manual.

### Clarified

- IQR is a within-bin variability metric rather than a conventional rate estimator.
- Sampling-density sensitivity remains a separate analysis outside the main GUI workflow.
