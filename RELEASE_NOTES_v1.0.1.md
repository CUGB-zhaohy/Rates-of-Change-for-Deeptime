# Deeptime RoC Analysis v1.0.1

This is the first public Windows release of the multi-timescale deep-time RoC
workflow.

## Download

Attach `RoC_Workflow_Windows_v1.0.1.zip` to the GitHub release. Users should
extract the complete archive, keep `_internal` beside `RoC_Workflow.exe`, and
launch `RoC_Workflow.exe`.

## Highlights

- No Python installation is required for the packaged Windows application.
- Five guided pages cover input, settings, advanced analysis, run/log, and result preview.
- Supports IBR, TS, IQR, LRI correction, nTV/Gini, PWLF, KDE, phase statistics, and figures.
- Includes quick-test and full-resolution configurations.
- Accepts user-supplied Excel age-value records.
- Weighted interpolation uses only the two nearest valid bins that bracket an internal missing target; more distant valid bins do not contribute.

## Known limitation

Sampling-density sensitivity analysis is not included in the v1.0.1 main GUI
workflow and should be run separately when needed.

## Checksums

`RoC_Workflow_Windows_v1.0.1.zip`

```text
SHA-256: 6897147058A1A885FE6A85CDA08438A7BB13F89CDB79DDE69520364146DF8862
```
