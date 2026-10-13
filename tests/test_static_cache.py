"""Offline cache contract tests. Importing this module never starts Apache or HTTP."""
import importlib.util
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("scoped_static_cache_apache", ROOT / "scripts/check_static_cache_apache.py")
CACHE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CACHE)


class StaticCacheContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "tests/fixtures/static_cache_htaccess_base.txt").read_bytes()
        cls.candidate = (ROOT / "public_html/.htaccess").read_bytes()

    def test_candidate_retains_every_original_byte(self):
        self.assertEqual(len(self.base), 2399)
        self.assertTrue(self.candidate.startswith(self.base))
        self.assertEqual(CACHE.extract_block(self.candidate, self.base), CACHE.BLOCK)

    def test_one_module_block_and_two_table_operations(self):
        block = CACHE.extract_block(self.candidate, self.base)
        self.assertEqual(block.count(CACHE.BEGIN), 1)
        self.assertEqual(block.count(CACHE.END), 1)
        self.assertEqual(block.count("<IfModule mod_headers.c>"), 1)
        self.assertEqual(block.count("</IfModule>"), 1)
        lines = [line.strip() for line in block.splitlines() if line.strip().startswith("Header ")]
        self.assertEqual(lines, [
            f'Header onsuccess unset Cache-Control "{CACHE.EXPR}"',
            f'Header always set Cache-Control "{CACHE.POLICY}" "{CACHE.EXPR}"',
        ])

    def test_conservative_mutable_url_policy(self):
        self.assertEqual(CACHE.POLICY, "public, max-age=300, must-revalidate")
        self.assertNotIn("immutable", CACHE.BLOCK)
        self.assertNotIn("Expires", CACHE.BLOCK)
        self.assertNotIn("FilesMatch", CACHE.BLOCK)

    def test_all_nine_exact_asset_urls_match(self):
        self.assertEqual(len(CACHE.TARGETS), 9)
        self.assertEqual(len(set(CACHE.TARGETS)), 9)
        for path in CACHE.TARGETS:
            with self.subTest(path=path):
                self.assertIsNotNone(re.fullmatch(CACHE.SCOPE, path))

    def test_query_changes_do_not_broaden_path_scope(self):
        for path in CACHE.TARGETS:
            with self.subTest(path=path):
                request_path = urlsplit(path + "?v=synthetic&next=/index.html").path
                self.assertIsNotNone(re.fullmatch(CACHE.SCOPE, request_path))
        self.assertIsNone(re.fullmatch(CACHE.SCOPE, urlsplit("/index.html?next=" + CACHE.TARGETS[0]).path))

    def test_only_success_partial_and_not_modified_statuses_match(self):
        for status in ("200", "206", "304"):
            with self.subTest(status=status):
                self.assertIsNotNone(re.fullmatch(CACHE.STATUS, status))
        for status in ("100", "201", "204", "301", "302", "400", "401", "403", "404", "416", "500", "2000", "200x"):
            with self.subTest(status=status):
                self.assertIsNone(re.fullmatch(CACHE.STATUS, status))

    def test_near_names_prefixes_and_dynamic_routes_do_not_match(self):
        negatives = (
            "/", "/index.html", "/projects.html", "/seo.php", "/dynamic.php",
            "/assets/other.js", "/assets/ui/theme.css.bak", "/assets/ui/frontend.jsX",
            "/assets/ui/briefx.js", "/assets/ui/BRIEF.js", "/assets/ui/brief.js/",
            "/assets/ui/foo/frontend.css", "/prefix/assets/ui/brief.js",
            "/assets/branding/logo-3dkan-689.webp",
            "/assets/branding/logo-3dkan-original.jpg.old",
            "/assets/portfolio-real/responsive/cimb-niaga-signage-atm-4800.webp",
            "/assets/portfolio-real/clean/cimb-niaga-signage-atm.webp",
            "/assets/marketing-20261006/site.js",
        )
        for path in negatives:
            with self.subTest(path=path):
                self.assertIsNone(re.fullmatch(CACHE.SCOPE, path))

    def test_original_html_php_no_cache_directive_is_preserved(self):
        self.assertIn(b'<FilesMatch "\\.(?:html|php)$">\n    Header set Cache-Control "no-cache"\n  </FilesMatch>', self.base)
        original = self.base[self.base.index(b'<IfModule mod_headers.c>'):self.base.index(b'<IfModule mod_deflate.c>')]
        self.assertEqual(self.candidate[self.candidate.index(b'<IfModule mod_headers.c>'):self.candidate.index(b'<IfModule mod_deflate.c>')], original)

    def test_original_prefix_mutation_is_rejected(self):
        changed = self.candidate.replace(b"Options -Indexes", b"Options +Indexes", 1)
        with self.assertRaises(ValueError):
            CACHE.extract_block(changed, self.base)

    def test_unapproved_extra_directive_is_rejected(self):
        with self.assertRaises(ValueError):
            CACHE.extract_block(self.candidate + b'Header set Cache-Control "public"\n', self.base)

    def test_unapproved_scope_and_status_mutations_are_rejected(self):
        for changed in (
            self.candidate.replace(CACHE.SCOPE.encode("ascii"), b"^/assets/", 1),
            self.candidate.replace(CACHE.STATUS.encode("ascii"), b"^(200|206|304|404)$", 1),
            self.candidate.replace(CACHE.POLICY.encode("ascii"), b"public, max-age=31536000, immutable", 1),
            self.candidate.replace(b"Header onsuccess unset", b"Header always unset", 1),
        ):
            with self.subTest(kind="unapproved append"):
                with self.assertRaises(ValueError):
                    CACHE.extract_block(changed, self.base)

    def test_missing_or_duplicate_markers_are_rejected(self):
        for changed in (
            self.candidate.replace(CACHE.BEGIN.encode("ascii"), b"# absent", 1),
            self.candidate + CACHE.BLOCK.encode("ascii"),
        ):
            with self.assertRaises(ValueError):
                CACHE.extract_block(changed, self.base)

    def test_unpinned_base_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            CACHE.extract_block(self.candidate, self.base[:-1])

    def test_header_lookup_preserves_duplicate_table_values(self):
        headers = [("Cache-Control", "old-success"), ("cache-control", "old-always"), ("ETag", '"synthetic"')]
        self.assertEqual(CACHE.values(headers, "Cache-Control"), ["old-success", "old-always"])
        self.assertEqual(CACHE.values([("CACHE-CONTROL", CACHE.POLICY)], "Cache-Control"), [CACHE.POLICY])


if __name__ == "__main__":
    unittest.main()
