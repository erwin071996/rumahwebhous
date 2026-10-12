"""Denied FTPS reads must never be treated as proof that a file is absent."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from tempfile import TemporaryDirectory

spec = importlib.util.spec_from_file_location(
    "transport_deploy", Path(__file__).resolve().parents[1] / "scripts/deploy_ftps.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeniedAccessTests(unittest.TestCase):
    def server(self):
        return object.__new__(deploy.Server)

    def test_retr_access_denied_is_not_absence(self):
        server = self.server()
        server.request = Mock(side_effect=deploy.CurlError(9, "Access denied"))
        server.list = Mock()
        with self.assertRaises(deploy.CurlError):
            server.read("index.html")
        server.list.assert_not_called()

    def test_denied_directory_listing_is_not_empty(self):
        server = self.server()
        server.request = Mock(side_effect=deploy.CurlError(9, "Access denied"))
        with self.assertRaises(deploy.CurlError):
            server.list("includes")

    def test_failed_retr_and_denied_listing_fail_closed(self):
        server = self.server()
        server.request = Mock(side_effect=deploy.CurlError(78, "Cannot retrieve file"))
        server.list = Mock(side_effect=deploy.CurlError(9, "Access denied"))
        with self.assertRaises(deploy.CurlError) as caught:
            server.read("includes/existing.html")
        self.assertEqual(caught.exception.code, 9)

    def test_unreadable_existing_file_is_not_absence(self):
        server = self.server()
        server.request = Mock(side_effect=deploy.CurlError(78, "Cannot retrieve file"))
        server.list = Mock(return_value=[("index.html", {"type": "file"})])
        with self.assertRaises(deploy.CurlError):
            server.read("index.html")

    def test_successful_listing_can_confirm_a_new_file_is_absent(self):
        server = self.server()
        server.request = Mock(side_effect=deploy.CurlError(78, "Not found"))
        server.list = Mock(return_value=[])
        self.assertIsNone(server.read("new.html"))

    def test_unreviewed_extra_baseline_file_fails_before_network(self):
        workspace = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(prefix=".deploy-test-", dir=workspace) as folder:
            site = Path(folder)
            self.assertTrue(site.resolve().is_relative_to(workspace.resolve()))
            data = b"reviewed page"
            (site / "index.html").write_bytes(data)
            (site / "unexpected.php").write_bytes(b"unreviewed")
            server = Mock()
            manifest = {"files": {"index.html": {"size": len(data), "sha256": deploy.digest(data), "modify": "20261012000000"}}}
            with patch.object(deploy, "SITE", site):
                with self.assertRaises(RuntimeError):
                    deploy.baseline_preflight(server, manifest)
            server.list.assert_not_called()


if __name__ == "__main__":
    unittest.main()
