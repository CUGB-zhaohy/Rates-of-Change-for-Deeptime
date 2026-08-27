# Upload guide

This package contains the Deeptime RoC Analysis source code, configuration
templates, documentation, and the manuscript result archive under `results/`.

## Recommended one-click upload on Windows

1. Extract the complete ZIP archive to a local folder.
2. Keep the internal folder structure unchanged.
3. Double-click `UPLOAD_TO_GITHUB.bat`.
4. Complete GitHub authorization if Windows or GitHub Desktop prompts you.
5. Wait until the window reports `Upload completed successfully`.
6. Open <https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime> and
   confirm that the latest commit contains the `results/` directory.

The script downloads the current private repository into a temporary working
directory, merges this package, removes obsolete non-English repository files,
creates a commit, and pushes it to the `main` branch. It does not modify the
extracted package.

## Requirements

- Windows 10 or Windows 11;
- Git for Windows or GitHub Desktop;
- access to the private `CUGB-zhaohy/Rates-of-Change-for-Deeptime` repository;
- an active internet connection.

The Windows standalone application ZIP remains attached to GitHub Release
`v1.0.1`; it is intentionally not stored in the normal Git history.

## Manual GitHub Desktop alternative

Clone `CUGB-zhaohy/Rates-of-Change-for-Deeptime`, copy the contents of this
package into the cloned repository root, remove obsolete non-English files,
then commit and push the changes through GitHub Desktop.
