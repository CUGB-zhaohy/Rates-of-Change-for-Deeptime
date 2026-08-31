from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ReleaseIntegrityTest(unittest.TestCase):
    def test_public_tree_has_no_nested_repository_copy(self):
        self.assertFalse(
            (ROOT / "Rates-of-Change-for-Deeptime_GitHub_EnglishOnly_260827").exists()
        )

    def test_maintainer_upload_helpers_are_not_public_payload(self):
        for name in (
            "UPLOAD_GUIDE.md",
            "UPLOAD_TO_GITHUB.bat",
            "UPLOAD_TO_GITHUB.ps1",
        ):
            with self.subTest(name=name):
                self.assertFalse((ROOT / name).exists())

    def test_results_manifest_matches_normalized_repository_files(self):
        manifest_path = RESULTS / "MANIFEST.csv"
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))

        listed = set()
        for row in rows:
            relative_path = row["relative_path"].replace("\\", "/")
            listed.add(relative_path)
            path = RESULTS / relative_path
            with self.subTest(path=relative_path):
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_size, int(row["size_bytes"]))
                self.assertEqual(sha256(path), row["sha256"].lower())

        actual = {
            path.relative_to(RESULTS).as_posix()
            for path in RESULTS.rglob("*")
            if path.is_file()
            and path.relative_to(RESULTS).as_posix()
            not in {"MANIFEST.csv", "checksums.sha256"}
        }
        self.assertEqual(actual, listed)

    def test_plain_checksum_list_matches_manifest(self):
        with (RESULTS / "MANIFEST.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            manifest = {
                row["relative_path"].replace("\\", "/"): row["sha256"].lower()
                for row in csv.DictReader(stream)
            }

        checksums = {}
        with (RESULTS / "checksums.sha256").open("r", encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                digest, relative_path = line.split(None, 1)
                checksums[relative_path.strip().replace("\\", "/")] = digest.lower()

        self.assertEqual(manifest, checksums)


if __name__ == "__main__":
    unittest.main()
