from pathlib import Path
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from roc import __version__
from roc.io import load_config


class RepositorySmokeTest(unittest.TestCase):
    def test_public_version(self):
        self.assertEqual(__version__, "1.0.1")

    def test_example_files_exist(self):
        self.assertTrue((ROOT / "data" / "O.xlsx").is_file())
        self.assertTrue((ROOT / "config_test.yaml").is_file())

    def test_test_configuration_loads(self):
        config = load_config(ROOT / "config_test.yaml")
        self.assertIn("input", config)
        self.assertIn("timebin", config)
        self.assertIn("methods", config)

    def test_repository_yaml_files_parse(self):
        metadata_files = [
            ROOT / "CITATION.cff",
            ROOT / ".github" / "dependabot.yml",
            ROOT / ".github" / "workflows" / "smoke-test.yml",
            ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
            ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
            ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml",
        ]
        for path in metadata_files:
            with self.subTest(path=path.relative_to(ROOT)):
                with path.open("r", encoding="utf-8") as stream:
                    self.assertIsNotNone(yaml.safe_load(stream))

    def test_citation_matches_release(self):
        with (ROOT / "CITATION.cff").open("r", encoding="utf-8") as stream:
            citation = yaml.safe_load(stream)
        self.assertEqual(str(citation["version"]), "1.0.1")
        self.assertEqual(citation["license"], "MIT")


if __name__ == "__main__":
    unittest.main()
