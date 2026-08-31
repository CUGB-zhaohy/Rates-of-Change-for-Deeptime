# Deeptime RoC Analysis v1.0.1

Final public release date: 2026-08-31

## Download

Windows users should download `RoC_Workflow_Windows_v1.0.1.zip` from this release, extract the archive, and double-click `RoC_Workflow.exe`.

The executable filename remains `RoC_Workflow.exe` in v1.0.1 for compatibility with the previously prepared Windows package. The software name used in the manuscript, manual, interface, and public documentation is **Deeptime RoC Analysis**.

## Highlights

- Provides a graphical Windows workflow and an equivalent Python command-line workflow for deep-time rate-of-change analysis.
- Includes the manuscript parameter configuration (`config_full.yaml`) and a faster installation test (`config_test.yaml`).
- Includes a separate sampling-density sensitivity workflow.
- Standardizes the public-facing software name as **Deeptime RoC Analysis**.
- Removes maintainer-only upload files and an accidentally nested repository copy from the public source tree.
- Corrects the Windows manual, output-directory documentation, release date, and result checksums.
- Adds an exact dependency lock file and automated release-integrity checks.

## Reproducibility

The source tree, bundled example data, configuration files, tests, result archive, and checksums are included in the tagged release. Run `python -m unittest discover -s tests -v` from a source installation to execute the automated checks.

`config_full.yaml` records the analysis settings used for the manuscript. `config_test.yaml` is intentionally smaller and is intended only for installation and workflow verification.

## Platform note

The prebuilt executable is for 64-bit Windows. The Python source and launchers are also available in the repository for Windows and macOS users.

## Asset verification

The Windows archive is accompanied by `RoC_Workflow_Windows_v1.0.1.zip.sha256.txt`. The sampling-density archive already attached to this release has SHA-256:

`9CA3DDE8F59140D65C4A3B36D4322D5C700F93F16F2C37C78153E2FF62DCFD60`
