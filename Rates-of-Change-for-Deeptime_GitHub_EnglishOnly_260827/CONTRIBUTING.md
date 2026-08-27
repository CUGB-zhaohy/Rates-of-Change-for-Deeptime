# Contributing

Thank you for improving Deeptime RoC Analysis.

## Before opening an issue

1. Run `python main.py --config config_test.yaml --dry-run`.
2. Confirm that the input uses numeric age and value columns.
3. Check the latest run summary and log.
4. Search existing issues for the same problem.

## Development setup

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py --config config_test.yaml --dry-run
```

## Pull requests

- Keep changes focused and explain the scientific or software motivation.
- Add or update tests for behavioural changes.
- Update README, methods notes, and changelog when user-visible behaviour changes.
- Do not commit generated `outputs/`, virtual environments, build folders, or release binaries.
- Preserve the distinction between time-explicit RoC estimators and within-bin variability metrics.

## Data and privacy

Use small, redistributable examples. Do not commit confidential, licensed, or
personally identifiable data.
