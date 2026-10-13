"""Candidate safety tests: all transport and HTTPS responses are in memory."""
from contextlib import redirect_stdout
import importlib.util
import io
import traceback
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



class CurlTransportDeadlineTests(unittest.TestCase):
    def server(self):
        server = object.__new__(DEPLOY.Server)
        server.host = "synthetic.invalid"
        server.user = "synthetic-private-user"
        server.password = "synthetic-private-password"
        server.curl = "/synthetic/curl"
        return server

    def test_fixed_retry_window_fits_outer_deadline(self):
        server = self.server()
        result = MagicMock(returncode=0, stdout=b"synthetic public bytes")
        with patch.object(DEPLOY.subprocess, "run", return_value=result) as run:
            self.assertEqual(server.request("assets/new.js"), b"synthetic public bytes")
        config = run.call_args.kwargs["input"].decode()
        for option in [
            "silent", "show-error", "ssl-reqd", "ipv4", "tlsv1.2",
            'tls-max = "1.2"', 'ftp-method = "singlecwd"',
            "connect-timeout = 12", "max-time = 60", "retry = 2",
            "retry-delay = 1", "retry-max-time = 150",
        ]:
            self.assertIn(option + "\n", config)
        allowed_last_start = 2 * (60 + 1)
        allowed_finish = 3 * 60 + 2 * 1
        self.assertLess(allowed_last_start, 150)
        self.assertEqual(allowed_finish, 182)
        self.assertGreater(allowed_finish, 180)
        self.assertEqual(run.call_args.kwargs["timeout"], 210)
        self.assertGreater(run.call_args.kwargs["timeout"], allowed_finish)

    def test_timeout_is_generic_redacted_curl_28_without_exception_context(self):
        server = self.server()
        config_secret = server.user + ":" + server.password
        payload_secret = "synthetic-private-payload"
        timeout = DEPLOY.subprocess.TimeoutExpired(
            ["synthetic-curl", config_secret], 210,
            output=payload_secret.encode(), stderr=config_secret.encode())
        timeout.input = ("user = " + config_secret).encode()
        output = io.StringIO()
        with redirect_stdout(output), patch.object(DEPLOY.subprocess, "run", side_effect=timeout) as run:
            with self.assertRaises(DEPLOY.CurlError) as caught:
                server.read("assets/new.js")
        error = caught.exception
        self.assertEqual(error.code, 28)
        self.assertTrue(error.__suppress_context__)
        rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        diagnostics = output.getvalue() + str(error) + repr(error) + rendered
        for private in [server.user, server.password, config_secret, payload_secret, "user =", "synthetic-curl"]:
            self.assertNotIn(private, diagnostics)
        self.assertIn("210-second subprocess deadline", str(error))
        self.assertIn("FTPS read: assets/new.js", output.getvalue())
        self.assertEqual(run.call_count, 1)

    def test_operations_trace_safe_target_before_curl_without_payload(self):
        for operation in ("read", "list", "write", "delete"):
            with self.subTest(operation=operation):
                server = self.server()
                output = io.StringIO()
                target = "assets/new.js"
                def respond(*args, **kwargs):
                    self.assertIn("FTPS " + operation + ": " + target, output.getvalue())
                    return MagicMock(returncode=0, stdout=b"type=file;size=1; other.js\r\n")
                with redirect_stdout(output), patch.object(DEPLOY.subprocess, "run", side_effect=respond) as run:
                    if operation == "read":
                        server.read(target)
                    elif operation == "list":
                        server.list(target)
                    elif operation == "write":
                        server.write(target, b"synthetic-private-payload")
                    else:
                        server.delete_created(target)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(output.getvalue(), "FTPS " + operation + ": " + target + "\n")
                for private in [server.user, server.password, "synthetic-private-payload", "upload-file", "user =", "ftp://"]:
                    self.assertNotIn(private, output.getvalue())

    def test_trace_redacts_credentials_even_if_present_in_safe_path(self):
        server = self.server()
        output = io.StringIO()
        with redirect_stdout(output):
            server.trace("read", "assets/" + server.user + "/" + server.password)
            server.trace("list", "")
            server.trace("read", DEPLOY.STATE_PATH)
        self.assertNotIn(server.user, output.getvalue())
        self.assertNotIn(server.password, output.getvalue())
        self.assertIn("FTPS read: assets/[REDACTED]/[REDACTED]", output.getvalue())
        self.assertIn("FTPS list: [site root]", output.getvalue())
        self.assertIn("FTPS read: release-state", output.getvalue())
        self.assertNotIn(DEPLOY.STATE_PATH, output.getvalue())


    def test_trace_escapes_control_characters_without_multiline_output(self):
        server = self.server()
        output = io.StringIO()
        with redirect_stdout(output):
            server.trace("read", "assets/odd\t\x1bfile.js")
        self.assertEqual(output.getvalue(), "FTPS read: assets/odd\\t\\u001bfile.js\n")

    def test_unsafe_trace_target_blocks_subprocess_and_logging(self):
        server = self.server()
        output = io.StringIO()
        with redirect_stdout(output), patch.object(DEPLOY.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                server.read("assets/new\n.js")
        run.assert_not_called()
        self.assertEqual(output.getvalue(), "")

    def test_timeout_during_absence_listing_propagates_before_any_upload(self):
        server = self.server()
        denied = MagicMock(returncode=9, stderr=b"synthetic candidate")
        timeout = DEPLOY.subprocess.TimeoutExpired(["synthetic-curl"], 210)
        output = io.StringIO()
        with redirect_stdout(output), patch.object(DEPLOY.subprocess, "run", side_effect=[denied, timeout]) as run:
            with self.assertRaises(DEPLOY.CurlError) as caught:
                server.read("assets/ui/new.js")
        self.assertEqual(caught.exception.code, 28)
        self.assertEqual(run.call_count, 2)
        self.assertIn("FTPS read: assets/ui/new.js", output.getvalue())
        self.assertIn("FTPS list: assets/ui", output.getvalue())


    def test_partial_stor_timeout_restores_old_new_and_state_transactions(self):
        for scenario in ("old", "new", "state"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as folder:
                path = "assets/new.js" if scenario == "new" else "assets/existing.js"
                old = None if scenario == "new" else b"synthetic old"
                old_state = DEPLOY.encode_successful_state("1" * 40)
                desired_state = DEPLOY.encode_successful_state("2" * 40)
                files = {DEPLOY.STATE_PATH: old_state}
                if old is not None:
                    files[path] = old
                deleted = []
                fail_path = DEPLOY.STATE_PATH if scenario == "state" else path
                class MemoryTransport:
                    def __init__(self, fail=False):
                        self.fail = fail
                    def read(self, target):
                        return files.get(target)
                    def write(self, target, data):
                        if self.fail and target == fail_path:
                            files[target] = b"synthetic partial"
                            raise DEPLOY.CurlError(28, "synthetic timeout after partial STOR")
                        files[target] = data
                    def delete_created(self, target):
                        deleted.append(target)
                        files.pop(target, None)
                    def close(self):
                        pass
                server, restore = MemoryTransport(True), MemoryTransport()
                site = Path(folder) / "public_html"
                (site / "assets").mkdir(parents=True)
                (site / path).write_bytes(b"synthetic desired")
                report = {"uploaded": [], "already_current": [], "rollback": "not needed"}
                update = (old_state, desired_state) if scenario == "state" else None
                with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "REPORT", Path(folder) / "report"):
                    with patch.object(DEPLOY, "previous", return_value=old):
                        with patch.object(DEPLOY, "Server", return_value=restore) as reconnect:
                            with patch.object(DEPLOY, "verify_live", return_value={"synthetic": True}) as verify:
                                with self.assertRaises(DEPLOY.CurlError) as caught:
                                    DEPLOY.deploy_changes(server, [path], "base", report, state_update=update)
                self.assertEqual(caught.exception.code, 28)
                reconnect.assert_called_once_with()
                self.assertEqual(report["rollback"], "verified")
                self.assertEqual(files.get(path), old)
                self.assertEqual(files[DEPLOY.STATE_PATH], old_state)
                self.assertEqual(deleted, [path] if scenario == "new" else [])
                self.assertEqual(len(report["uploaded"]), 1 if scenario == "state" else 0)
                self.assertNotIn("successful_release_commit", report)
                if scenario == "state":
                    verify.assert_called_once_with()
                else:
                    verify.assert_not_called()

    def test_normal_curl_error_keeps_username_and_password_redaction(self):
        server = self.server()
        raw = "synthetic error " + server.user + " " + server.password
        result = MagicMock(returncode=9, stderr=raw.encode())
        with patch.object(DEPLOY.subprocess, "run", return_value=result):
            with self.assertRaises(DEPLOY.CurlError) as caught:
                server.request("assets/new.js")
        self.assertEqual(caught.exception.code, 9)
        self.assertNotIn(server.user, str(caught.exception))
        self.assertNotIn(server.password, str(caught.exception))
        self.assertEqual(str(caught.exception).count("[REDACTED]"), 2)


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
            (site / "includes/refresh-data.json").write_text(json.dumps({"services": {"neon-box": {}}}))
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
