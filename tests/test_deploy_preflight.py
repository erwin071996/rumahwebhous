"""Candidate safety tests: all transport and HTTPS responses are in memory."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deploy_ftps.py"
SPEC = importlib.util.spec_from_file_location("deploy_preflight_under_test", SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class ProbeServer(DEPLOY.Server):
    def __init__(self, responses):
        self.responses = responses
        self.requests = []
        self.writes = []
        self.deletions = []

    def request(self, path="", extra=()):
        key = (path, tuple(extra))
        self.requests.append(key)
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response

    def write(self, path, data):
        self.writes.append(path)
        raise AssertionError("Preflight must not reach STOR")

    def delete_created(self, path):
        self.deletions.append(path)
        raise AssertionError("Preflight must not reach DELE")

    def close(self):
        pass


class ConfirmedAbsenceTests(unittest.TestCase):
    def test_denied_retr_never_means_absence(self):
        server = ProbeServer({
            ("assets/ui/new.js", ()): DEPLOY.CurlError(9, "synthetic denied"),
            ("assets/ui/", ('request = "MLSD"',)): b"type=file;size=1; new.js\r\n",
        })
        with self.assertRaises(DEPLOY.CurlError):
            server.read("assets/ui/new.js")
        self.assertEqual(len(server.requests), 2)
        self.assertEqual(server.writes, [])
        self.assertEqual(server.deletions, [])

    def test_missing_file_requires_successful_parent_listing(self):
        server = ProbeServer({
            ("assets/new.js", ()): DEPLOY.CurlError(78, "synthetic absent"),
            ("assets/", ('request = "MLSD"',)): b"type=file;size=1; other.js\r\n",
        })
        self.assertIsNone(server.read("assets/new.js"))
        self.assertEqual(server.writes, [])

    def test_missing_new_directory_is_confirmed_by_existing_ancestor(self):
        server = ProbeServer({
            ("assets/ui/new.js", ()): DEPLOY.CurlError(78, "synthetic absent"),
            ("assets/ui/", ('request = "MLSD"',)): DEPLOY.CurlError(78, "synthetic missing directory"),
            ("assets/", ('request = "MLSD"',)): b"type=dir; other-directory\r\n",
        })
        self.assertIsNone(server.read("assets/ui/new.js"))
        self.assertEqual(len(server.requests), 3)
        self.assertEqual(server.writes, [])
        self.assertEqual(server.deletions, [])

    def test_denied_ancestor_listing_refuses_before_upload(self):
        server = ProbeServer({
            ("assets/ui/new.js", ()): DEPLOY.CurlError(78, "synthetic absent"),
            ("assets/ui/", ('request = "MLSD"',)): DEPLOY.CurlError(78, "synthetic missing directory"),
            ("assets/", ('request = "MLSD"',)): DEPLOY.CurlError(9, "synthetic denied"),
            ("", ('request = "MLSD"',)): b"type=dir; assets\r\n",
        })
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder) / "public_html"
            (site / "assets/ui").mkdir(parents=True)
            (site / "assets/ui/new.js").write_bytes(b"synthetic desired")
            report = {"uploaded": [], "already_current": [], "rollback": "not needed"}
            with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "previous", return_value=None):
                with patch.object(DEPLOY, "Server") as reconnect:
                    with self.assertRaises(DEPLOY.CurlError):
                        DEPLOY.deploy_changes(server, ["assets/ui/new.js"], "base", report)
            reconnect.assert_not_called()
        self.assertEqual(server.writes, [])
        self.assertEqual(server.deletions, [])

    def test_inaccessible_existing_parent_is_not_absent(self):
        server = ProbeServer({
            ("assets/ui/new.js", ()): DEPLOY.CurlError(78, "synthetic inaccessible"),
            ("assets/ui/", ('request = "MLSD"',)): DEPLOY.CurlError(78, "synthetic inaccessible directory"),
            ("assets/", ('request = "MLSD"',)): b"type=dir; ui\r\n",
        })
        with self.assertRaises(DEPLOY.CurlError):
            server.read("assets/ui/new.js")
        self.assertEqual(server.writes, [])

    def test_root_listing_failure_cannot_prove_absence(self):
        server = ProbeServer({
            ("index.html", ()): DEPLOY.CurlError(78, "synthetic absent"),
            ("", ('request = "MLSD"',)): DEPLOY.CurlError(78, "synthetic unavailable"),
        })
        with self.assertRaises(DEPLOY.CurlError):
            server.read("index.html")


    def test_denied_retr_requires_readable_parent_proof(self):
        server = ProbeServer({
            ("assets/new.js", ()): DEPLOY.CurlError(9, "synthetic denied"),
            ("assets/", ('request = "MLSD"',)): b"type=file;size=1; other.js\r\n",
        })
        self.assertIsNone(server.read("assets/new.js"))
        self.assertEqual(len(server.requests), 2)
        self.assertEqual(server.writes, [])
        self.assertEqual(server.deletions, [])

    def test_cwd_denied_missing_ancestors_require_readable_root_proof(self):
        for read_code in (9, 78):
            for ui_code in (9, 78):
                for assets_code in (9, 78):
                    with self.subTest(read_code=read_code, ui_code=ui_code, assets_code=assets_code):
                        server = ProbeServer({
                            ("assets/ui/new.js", ()): DEPLOY.CurlError(read_code, "synthetic candidate"),
                            ("assets/ui/", ('request = "MLSD"',)): DEPLOY.CurlError(ui_code, "synthetic CWD candidate"),
                            ("assets/", ('request = "MLSD"',)): DEPLOY.CurlError(assets_code, "synthetic CWD candidate"),
                            ("", ('request = "MLSD"',)): b"type=dir; existing-directory\r\n",
                        })
                        self.assertIsNone(server.read("assets/ui/new.js"))
                        self.assertEqual(len(server.requests), 4)
                        self.assertEqual(server.writes, [])
                        self.assertEqual(server.deletions, [])

    def test_denied_existing_directory_listed_by_parent_is_not_absent(self):
        for read_code in (9, 78):
            for list_code in (9, 78):
                with self.subTest(read_code=read_code, list_code=list_code):
                    server = ProbeServer({
                        ("assets/ui/new.js", ()): DEPLOY.CurlError(read_code, "synthetic candidate"),
                        ("assets/ui/", ('request = "MLSD"',)): DEPLOY.CurlError(list_code, "synthetic denied existing directory"),
                        ("assets/", ('request = "MLSD"',)): b"type=dir; ui\r\n",
                    })
                    with self.assertRaises(DEPLOY.CurlError) as caught:
                        server.read("assets/ui/new.js")
                    self.assertEqual(caught.exception.code, list_code)
                    self.assertEqual(len(server.requests), 3)
                    self.assertEqual(server.writes, [])
                    self.assertEqual(server.deletions, [])

    def test_denied_root_cannot_prove_absence(self):
        for read_code in (9, 78):
            for root_code in (9, 78):
                with self.subTest(read_code=read_code, root_code=root_code):
                    server = ProbeServer({
                        ("index.html", ()): DEPLOY.CurlError(read_code, "synthetic candidate"),
                        ("", ('request = "MLSD"',)): DEPLOY.CurlError(root_code, "synthetic unreadable root"),
                    })
                    with self.assertRaises(DEPLOY.CurlError) as caught:
                        server.read("index.html")
                    self.assertEqual(caught.exception.code, root_code)
                    self.assertEqual(len(server.requests), 2)
                    self.assertEqual(server.writes, [])
                    self.assertEqual(server.deletions, [])

    def test_network_errors_do_not_attempt_absence_proof(self):
        for code in (6, 7, 28, 35, 60):
            with self.subTest(code=code):
                server = ProbeServer({
                    ("assets/ui/new.js", ()): DEPLOY.CurlError(code, "synthetic transport error"),
                })
                with self.assertRaises(DEPLOY.CurlError) as caught:
                    server.read("assets/ui/new.js")
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(len(server.requests), 1)
                self.assertEqual(server.writes, [])
                self.assertEqual(server.deletions, [])

    def test_network_error_during_ancestor_proof_propagates(self):
        for code in (6, 7, 28, 35, 60):
            with self.subTest(code=code):
                server = ProbeServer({
                    ("assets/ui/new.js", ()): DEPLOY.CurlError(9, "synthetic candidate"),
                    ("assets/ui/", ('request = "MLSD"',)): DEPLOY.CurlError(9, "synthetic CWD candidate"),
                    ("assets/", ('request = "MLSD"',)): DEPLOY.CurlError(code, "synthetic transport error"),
                })
                with self.assertRaises(DEPLOY.CurlError) as caught:
                    server.read("assets/ui/new.js")
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(len(server.requests), 3)
                self.assertEqual(server.writes, [])
                self.assertEqual(server.deletions, [])

    def test_denied_existing_directory_blocks_transaction_before_stor_or_dele(self):
        server = ProbeServer({
            ("assets/ui/new.js", ()): DEPLOY.CurlError(9, "synthetic candidate"),
            ("assets/ui/", ('request = "MLSD"',)): DEPLOY.CurlError(9, "synthetic denied existing directory"),
            ("assets/", ('request = "MLSD"',)): b"type=dir; ui\r\n",
        })
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder) / "public_html"
            (site / "assets/ui").mkdir(parents=True)
            (site / "assets/ui/new.js").write_bytes(b"synthetic desired")
            report = {"uploaded": [], "already_current": [], "rollback": "not needed"}
            with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "previous", return_value=None):
                with patch.object(DEPLOY, "Server") as reconnect:
                    with self.assertRaises(DEPLOY.CurlError):
                        DEPLOY.deploy_changes(server, ["assets/ui/new.js"], "base", report)
            reconnect.assert_not_called()
        self.assertEqual(server.writes, [])
        self.assertEqual(server.deletions, [])
        self.assertEqual(report["uploaded"], [])
        self.assertEqual(report["rollback"], "not needed")



    def test_denied_new_parent_after_preparation_blocks_all_uploads(self):
        server = ProbeServer({
            ("assets/existing.js", ()): b"synthetic old",
            ("assets/ui/new.js", ()): DEPLOY.CurlError(9, "synthetic candidate"),
            ("assets/ui/", ('request = "MLSD"',)): DEPLOY.CurlError(9, "synthetic denied existing directory"),
            ("assets/", ('request = "MLSD"',)): b"type=dir; ui\r\n",
        })
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder) / "public_html"
            (site / "assets/ui").mkdir(parents=True)
            (site / "assets/existing.js").write_bytes(b"synthetic changed")
            (site / "assets/ui/new.js").write_bytes(b"synthetic desired")
            report = {"uploaded": [], "already_current": [], "rollback": "not needed"}
            def before(base, path):
                return b"synthetic old" if path == "public_html/assets/existing.js" else None
            with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "REPORT", Path(folder) / "report"):
                with patch.object(DEPLOY, "previous", side_effect=before):
                    with patch.object(DEPLOY, "Server") as reconnect:
                        with self.assertRaises(DEPLOY.CurlError):
                            DEPLOY.deploy_changes(server, ["assets/existing.js", "assets/ui/new.js"], "base", report)
                reconnect.assert_not_called()
        self.assertEqual(server.writes, [])
        self.assertEqual(server.deletions, [])
        self.assertEqual(report["uploaded"], [])
        self.assertEqual(report["rollback"], "not needed")


class LocalGateTests(unittest.TestCase):
    def test_zero_tests_blocks_validation(self):
        suite = MagicMock()
        suite.countTestCases.return_value = 0
        with patch.object(DEPLOY.unittest.TestLoader, "discover", return_value=suite):
            with patch.object(DEPLOY.subprocess, "run") as validate:
                with self.assertRaisesRegex(RuntimeError, "nonempty"):
                    DEPLOY.require_local_checks()
        validate.assert_not_called()

    def test_failed_tests_blocks_validation(self):
        suite = MagicMock()
        suite.countTestCases.return_value = 1
        result = MagicMock()
        result.wasSuccessful.return_value = False
        with patch.object(DEPLOY.unittest.TestLoader, "discover", return_value=suite):
            with patch.object(DEPLOY.unittest.TextTestRunner, "run", return_value=result):
                with patch.object(DEPLOY.subprocess, "run") as validate:
                    with self.assertRaisesRegex(RuntimeError, "unit tests failed"):
                        DEPLOY.require_local_checks()
        validate.assert_not_called()

    def test_failed_gate_never_constructs_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(DEPLOY, "REPORT", Path(folder)):
                with patch.object(DEPLOY, "require_local_checks", side_effect=RuntimeError("synthetic failed checks")):
                    with patch.object(DEPLOY, "Server") as transport:
                        with self.assertRaises(SystemExit):
                            DEPLOY.main()
            transport.assert_not_called()

    def test_successful_suite_runs_source_validation(self):
        suite = MagicMock()
        suite.countTestCases.return_value = 1
        result = MagicMock()
        result.wasSuccessful.return_value = True
        with patch.object(DEPLOY.unittest.TestLoader, "discover", return_value=suite):
            with patch.object(DEPLOY.unittest.TextTestRunner, "run", return_value=result):
                with patch.object(DEPLOY.subprocess, "run") as validate:
                    DEPLOY.require_local_checks()
        validate.assert_called_once()
        self.assertTrue(validate.call_args.kwargs["check"])


class LiveStaticPageTests(unittest.TestCase):
    def test_static_pages_must_match_even_without_release_markers(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / "includes").mkdir()
            rows = [{"path": "/synthetic/" + str(i)} for i in range(500)]
            (site / "includes/content-index.json").write_text(json.dumps({"groups": {"synthetic": rows}}))
            current = {
                "/": b"<html>Synthetic current home</html>",
                "/projects.html": b"<html>Synthetic current portfolio</html>",
            }
            (site / "index.html").write_bytes(current["/"])
            (site / "projects.html").write_bytes(current["/projects.html"])
            ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
            index = ET.Element("{" + ns + "}sitemapindex")
            responses = {}
            for group in range(10):
                url = DEPLOY.DOMAIN + "/sitemap-qa" + str(group) + ".xml"
                item = ET.SubElement(index, "{" + ns + "}sitemap")
                ET.SubElement(item, "{" + ns + "}loc").text = url
                child = ET.Element("{" + ns + "}urlset")
                for row in rows[group * 50:(group + 1) * 50]:
                    entry = ET.SubElement(child, "{" + ns + "}url")
                    ET.SubElement(entry, "{" + ns + "}loc").text = DEPLOY.DOMAIN + row["path"]
                responses[url.removeprefix(DEPLOY.DOMAIN)] = ET.tostring(child)
            responses["/sitemap.xml"] = ET.tostring(index)
            def respond(path):
                return responses.get(path, current.get(path, b"<html>Synthetic sample</html>"))
            with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "https", side_effect=respond):
                self.assertEqual(DEPLOY.verify_live()["http_samples"], 9)
                for stale in ["/", "/projects.html"]:
                    with self.subTest(stale=stale):
                        original = current[stale]
                        current[stale] = b"<html>Synthetic stale page</html>"
                        with self.assertRaisesRegex(RuntimeError, "Live static page differs"):
                            DEPLOY.verify_live()
                        current[stale] = original


if __name__ == "__main__":
    unittest.main()
