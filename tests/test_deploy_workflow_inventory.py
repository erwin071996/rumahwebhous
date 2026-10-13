"""Regression gate: legacy production paths are inert and retain exact reviewed bytes."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVED = {
    "crawl-live-portfolio.yml": "136c199610f3ea2660890f793cf6617e0d69dbbb",
    "deploy-clean-portfolio-assets.yml": "fb7af8b2dd64a56b4c22d5d8710883d5356ae322",
    "deploy-homepage.yml": "75c33f4fca6fabd16a8c08b49af3b0c94a6caea9",
    "deploy-portfolio-page.yml": "2b890708454487397509b4f057df6d886c009ecd",
    "fetch-live-portfolio.yml": "a9723af2cafc86c47e651024bb8d9c99c6169e7e",
    "import-from-rumahweb.yml": "f29e91facc529d632425f2c0891319e0500d3cde",
    "import-source-snapshot.yml": "0706e47d8b9e26219413c4302c4e8cccc36cc085",
    "probe-portfolio-routes.yml": "892f984ac5c1808f2ac94200f6fb6aa722d34b29",
    "quick-portfolio-locate.yml": "6b42632e58fda7b92ffd769b0a6ce7100672dd12",
    "rebuild-portfolio-images.yml": "3f0d1dc7cedf7541bee2913d850b8b40fabec6d4",
    "scan-portfolio-source.yml": "4b18692785fee4c93a7c4031487932852e979e37"
}

def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

class WorkflowInventoryTests(unittest.TestCase):
    def test_legacy_yaml_is_inert_and_byte_preserved(self):
        for name, expected in ARCHIVED.items():
            with self.subTest(name=name):
                self.assertFalse((ROOT / ".github" / "workflows" / name).exists())
                archive = ROOT / "docs" / "legacy-workflows" / (name + ".txt")
                self.assertTrue(archive.is_file())
                self.assertEqual(blob_sha(archive.read_bytes()), expected)
    def test_guarded_deploy_and_validator_preserved(self):
        expected = {
            "deploy.yml": "a9b8a4c1d342056f137db427278ad25b666d1469",
            "validate.yml": "da53910abd90d7c91782aa68c994d02f6873f968",
        }
        for name, sha in expected.items():
            with self.subTest(name=name):
                self.assertEqual(blob_sha((ROOT / ".github" / "workflows" / name).read_bytes()), sha)
    def test_completed_capture_is_inert(self):
        self.assertFalse((ROOT / ".github" / "workflows" / "capture-live-baseline.yml").exists())
        self.assertTrue((ROOT / ".site-source-ready").is_file())

if __name__ == "__main__":
    unittest.main()
