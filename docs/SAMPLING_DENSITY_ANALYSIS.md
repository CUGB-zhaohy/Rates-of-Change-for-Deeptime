# Sampling-density sensitivity analysis

## Purpose

The main CENOGRID record is unusually densely sampled relative to many
deep-time proxy records. This separate experiment tests how progressively
reduced sampling density affects IBR, TS, and IQR estimates and whether the
principal temporal structure remains recoverable.

The analysis is not part of the Deeptime RoC Analysis v1.0.1 graphical
workflow. It is provided as a reproducible manuscript-specific procedure in
`roc/sensitivity.py` and can be launched from the repository root with:

```bash
python run_sampling_density_analysis.py
```

## Experimental design

- Input: `data/CENOGRID_benthic_d18O_sampling_density.xlsx`
- Age range: 0-67,000 kyr
- Common output step: 10 kyr
- Analytical windows: 100 and 1000 kyr
- Methods: IBR, TS, and IQR
- Subsampling intervals: 20, 50, and 100 kyr
- Sampling rule: retain one randomly selected observation from every occupied
  subsampling interval
- Iterations: 200 for each method-window-subsampling combination
- Random seed: 42
- Uncertainty summary: ensemble mean and empirical 2.5th-97.5th percentiles
- Error metrics: MAE and MAPE relative to the full-data result

Internal missing time-bin values are estimated using distance-count weighted
interpolation from the nearest valid bin on each side. The nearest valid edge
value is used only when a missing target lies outside the valid age range.

## Archived result structure

```text
results/sampling_density/
├── metrics/
├── summary_curves/
├── figures/
├── MANIFEST.csv
├── checksums.sha256
└── README.md
```

The repository contains the compact result set needed to inspect and reproduce
the manuscript analysis:

- `metrics/`: MAE and MAPE for all 200 iterations of each configuration;
- `summary_curves/`: full-data reference series, ensemble means, and empirical
  95% intervals;
- `figures/`: vector versions of Appendix Figs. C1 and C2.

The 18 complete iteration-by-age tables are distributed separately as the
GitHub Release asset `RoC_sampling_density_full_iterations_v1.0.1.zip` because
their uncompressed size is approximately 470 MB.

## Interpretation

Increasing the subsampling interval reduces the retained observation density.
Sensitivity should be assessed from the growth of MAE and MAPE and from changes
in the ensemble curves and empirical intervals. Values from different methods
have different units, numerical ranges, and meanings, so absolute MAE values
should not be ranked across IBR, TS, and IQR without normalization.

MAPE requires additional caution. IBR and TS reference series commonly contain
values close to zero, and division by those values can produce extremely large
percentage errors. MAPE is retained to document the analysis reported in the
manuscript, but it should be interpreted jointly with MAE and the ensemble
curves rather than used as the sole basis for method selection.

## Reuse and citation

Please cite the associated manuscript, the versioned software release, and the
original CENOGRID data source. The repository MIT License covers the software;
third-party source data remain subject to their original citation requirements
and terms.
