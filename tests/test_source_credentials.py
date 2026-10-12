"""Keep credential checks strict without confusing public asset names for keys."""
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_site.py"
SPEC = importlib.util.spec_from_file_location("check_site_under_test", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class CredentialBoundaryTests(unittest.TestCase):
    def test_public_desk_image_slugs_are_not_credentials(self):
        names = [
            b"digital-and-handwritten-brainstorming-tools-on-a-wooden-desk-"
            b"with-notes-and-computer-in-the-workspace-generatedidentifier",
            b"overhead-view-of-a-business-desk-with-documents-and-calculations-"
            b"for-the-annual-financial-budget-generatedidentifier",
        ]
        for name in names:
            with self.subTest(name=name):
                html = b'<meta property="og:image" content="/images/0/123/' + name + b'.jpeg">'
                self.assertIsNone(CHECK.SECRET_PATTERN.search(html))

    def test_standalone_synthetic_provider_keys_still_match(self):
        # Generated placeholders only; no real credentials are used by tests.
        tokens = [
            b"sk-" + b"A" * 40,
            b"sk-proj-" + b"A" * 40,
            b"ghp_" + b"A" * 36,
            b"github_pat_" + b"A" * 50,
            b"AKIA" + b"A" * 16,
        ]
        for token in tokens:
            for surrounding in [b'"%s"', b'Bearer %s\n', b"token=%s;"]:
                with self.subTest(prefix=token[:8], surrounding=surrounding):
                    self.assertIsNotNone(CHECK.SECRET_PATTERN.search(surrounding % token))

    def test_private_key_header_still_matches(self):
        self.assertIsNotNone(CHECK.SECRET_PATTERN.search(
            b"-----BEGIN OPENSSH PRIVATE KEY-----\nplaceholder\n"
        ))


if __name__ == "__main__":
    unittest.main()
