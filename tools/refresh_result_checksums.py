from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def refresh(directory: Path) -> None:
    manifest_path = directory / "MANIFEST.csv"
    checksum_path = directory / "checksums.sha256"
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise ValueError(f"Missing manifest header: {manifest_path}")

    for row in rows:
        relative_path = row["relative_path"].replace("\\", "/")
        path = directory / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Manifest entry is missing: {path}")
        row["relative_path"] = relative_path
        row["size_bytes"] = str(path.stat().st_size)
        row["sha256"] = sha256(path)

    with manifest_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

    with checksum_path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(f"{row['sha256']}  {row['relative_path']}\n")


def main() -> None:
    refresh(RESULTS / "sampling_density")
    refresh(RESULTS)
    print("Refreshed result manifests and SHA-256 checksum lists.")


if __name__ == "__main__":
    main()
