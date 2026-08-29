# Method and implementation notes

This document summarizes how the v1.0.1 source code maps the published
multi-timescale deep-time RoC workflow into executable modules.

## Input and preprocessing

Input is an Excel age-value table. Preprocessing can sort ages, remove invalid
rows, average duplicate ages, and optionally transform values to Z-scores. The
main implementation is in `roc/preprocess.py` and `roc/io.py`.

## Time-bin framework

The workflow places the record on user-defined age nodes and evaluates multiple
time-bin widths. The node spacing is the output step; the bin width is the
analytical time scale. Time-bin construction is implemented in
`roc/timebin.py`.

## Missing-bin interpolation

For an internal missing target at age `t`, the recommended distance-count
method selects exactly two contributors: the nearest valid bin at the lower
age and the nearest valid bin at the higher age. More distant valid bins are
excluded. For each bracketing bin `i`,

```text
w_i = c_i^alpha / |t_i - t|^beta
```

and the interpolated value is

```text
x(t) = (w_prev * x_prev + w_next * x_next) / (w_prev + w_next)
```

where `c_i` is the sample count, `t_i` is the bin age, and `x_i` is the valid
bin value. The exponents are configured as `count_weight_alpha` and
`distance_weight_beta`; both default to 1. Missing targets outside the valid
age range follow `edge_mode` (`nearest`, `nan`, or `zero`). Linear interpolation
and no interpolation are also supported. See `roc/interpolation.py`.

## RoC-related metrics

- **IBR:** bin mean, interpolation, then the rate between appropriately spaced bins.
- **TS:** the median pairwise slope within each bin, followed by interpolation where required.
- **IQR:** the interquartile range within each bin, interpreted as within-bin variability.

Implementations are in `roc/methods.py` and are orchestrated by
`roc/pipeline.py`.

## LRI scaling and correction

For positive values, the software fits

```text
log10(RoC) = slope * log10(timescale) + intercept
```

The fitted value defines the baseline for each method and analytical time
scale. Corrected relative RoC is calculated as observed RoC divided by that
method- and scale-specific baseline. This does not convert all estimates to one
fixed reference scale. See `roc/lri.py`.

## nTV and Gini

Normalized total variation summarizes the mean absolute increment of a corrected
series. The Gini coefficient summarizes the temporal concentration of RoC.
These metrics support method comparison but do not define a universally optimal
method. See `roc/metrics.py`.

## Breakpoints and phases

PWLF is applied to normalized cumulative RoC curves to generate candidate
breakpoints. KDE is then run separately for each calculation method to obtain
method-specific consensus breakpoints. Phase statistics use the boundaries from
the corresponding method. See `roc/breakpoint.py`, `roc/kde.py`, and
`roc/phase.py`.

## Plotting and logs

The workflow exports tables, SVG/PNG figures, and a run summary. The summary
records configuration, completed methods, and generated outputs. See
`roc/plotting.py` and `roc/io.py`.

## Current limitation

The sampling-density sensitivity experiments associated with the manuscript
are not included in the v1.0.1 main GUI pipeline. `roc/sensitivity.py` is
reserved for future integration of this module.
