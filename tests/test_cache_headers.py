"""Focused offline tests; no live network, private files, or header values logged."""
from email.message import Message
import importlib.util
from pathlib import Path
import ssl
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location(
    "cache_probe", Path(__file__).resolve().parents[1] / "scripts/probe_cache_headers.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def headers(*pairs):
    result = Message()
    for name, value in pairs:
        result[name] = value
    return result


def row(path, status=200, policy=probe.POLICY):
    return probe.snapshot(path, status, headers(
        *([("Cache-Control", policy)] if policy is not None else [])))


class Response:
    def __init__(self, status, values):
        self.status, self.headers, self.closed = status, values, False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


def fake_request(path, conditional=None):
    return row(path, 304 if conditional else 404 if path == probe.MISSING else 200,
               None if path == probe.MISSING else probe.POLICY)


class CacheHeadersTests(unittest.TestCase):
    def test_fixed_inventory(self):
        self.assertEqual(len(probe.TARGETS), 9)
        self.assertEqual(len(probe.CONTROLS), 4)
        self.assertEqual(len(probe.ALLOWED), 14)
        self.assertTrue(all(path.startswith("/") and "?" not in path
                            for path in probe.ALLOWED))

    def test_snapshot_keeps_duplicate_public_values_without_cookie_value(self):
        values = headers(("Cache-Control", "public"), ("Cache-Control", "max-age=5"),
                         ("ETag", '"public-tag"'), ("Set-Cookie", "DO_NOT_REPORT=synthetic"),
                         ("Server", "Apache/2.4"), ("Location", "DO_NOT_REPORT"))
        result = probe.snapshot(probe.TARGETS[0], 200, values)
        self.assertEqual(result["cache_control"], ["public", "max-age=5"])
        self.assertEqual(result["etag"], ['"public-tag"'])
        self.assertTrue(result["set_cookie"])
        self.assertEqual(result["server"], "Apache/2.4")
        self.assertNotIn("DO_NOT_REPORT", repr(result))
        self.assertEqual(set(result), {"path", "status", "set_cookie", "server",
                                     *probe.HEADER_FIELDS})

    def test_server_metadata_is_public_bounded_printable(self):
        result = probe.snapshot("/", 200, headers(("Server", "Apache" + chr(10) + "x" * 400)))
        self.assertLessEqual(len(result["server"]), 256)
        self.assertTrue(all(32 <= ord(char) < 127 for char in result["server"]))

    def test_head_method_tls_origin_timeout_and_no_body_read(self):
        response = Response(200, headers(("Cache-Control", probe.POLICY)))
        opener = Mock()
        opener.open.return_value = response
        result = probe.head(probe.TARGETS[0], opener=opener)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "HEAD")
        self.assertEqual(request.full_url, probe.ORIGIN + probe.TARGETS[0])
        self.assertEqual(opener.open.call_args.kwargs, {"timeout": 10})
        self.assertFalse(request.has_header("Authorization"))
        self.assertFalse(request.has_header("Cookie"))
        self.assertEqual(result["status"], 200)
        self.assertTrue(response.closed)

    def test_scope_rejected_before_network(self):
        opener = Mock()
        for path in ("https://example.invalid/", "//example.invalid/", "/api.php",
                     "/assets/ui/frontend.js?token=synthetic"):
            with self.assertRaisesRegex(ValueError, "path_not_allowed"):
                probe.head(path, opener=opener)
        opener.open.assert_not_called()

    def test_invalid_conditional_header_rejected_before_network(self):
        opener = Mock()
        for value in ("bad\r\nCookie: synthetic", "", "x" * 1025, "bad\x7f"):
            with self.assertRaisesRegex(ValueError, "invalid_validator"):
                probe.head(probe.TARGETS[0], ("If-None-Match", value), opener)
        with self.assertRaisesRegex(ValueError, "invalid_validator"):
            probe.head(probe.TARGETS[0], ("Authorization", "synthetic"), opener)
        opener.open.assert_not_called()

    def test_redirect_not_followed_or_location_reported(self):
        self.assertIsNone(probe.NoRedirect().redirect_request(
            None, None, 302, "Found", headers(), "https://example.invalid/"))
        opener = Mock()
        opener.open.side_effect = HTTPError(probe.ORIGIN, 302, "private text",
                                           headers(("Location", "DO_NOT_REPORT")), None)
        result = probe.head(probe.TARGETS[0], opener=opener)
        self.assertEqual(result["status"], 302)
        self.assertNotIn("DO_NOT_REPORT", repr(result))
        self.assertEqual(opener.open.call_count, 1)

    def test_304_http_error_is_reported_with_policy(self):
        opener = Mock()
        opener.open.side_effect = HTTPError(probe.ORIGIN, 304, "not modified",
                                           headers(("Cache-Control", probe.POLICY)), None)
        result = probe.head(probe.TARGETS[0], ("If-None-Match", '"tag"'), opener)
        self.assertEqual(probe.policy_issues(result), [])

    def test_request_error_never_reports_exception_values(self):
        for error in (URLError("DO_NOT_REPORT"), TimeoutError("DO_NOT_REPORT"),
                      ssl.SSLError("DO_NOT_REPORT")):
            opener = Mock()
            opener.open.side_effect = error
            result = probe.head(probe.TARGETS[0], opener=opener)
            self.assertIsNone(result["status"])
            self.assertNotIn("DO_NOT_REPORT", repr(result))

    def test_exact_policy_for_successful_statuses(self):
        for status in (200, 206, 304):
            self.assertEqual(probe.policy_issues(row(probe.TARGETS[0], status)), [])
        for bad in (None, probe.POLICY + ", immutable", "max-age=300, public"):
            self.assertTrue(probe.policy_issues(row(probe.TARGETS[0], policy=bad)))
        duplicate = row(probe.TARGETS[0])
        duplicate["cache_control"].append(probe.POLICY)
        self.assertTrue(probe.policy_issues(duplicate))
        self.assertTrue(probe.policy_issues(row(probe.TARGETS[0], 302)))

    def test_public_target_cookie_fails(self):
        result = row(probe.TARGETS[0])
        result["set_cookie"] = True
        self.assertEqual(probe.policy_issues(result)[0]["category"], "target_sets_cookie")

    def test_observe_missing_cache_control_is_evidence_not_failure(self):
        def request(path, conditional=None):
            return row(path, 404 if path == probe.MISSING else 200, None)
        report = probe.run_probe(request=request)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["missing_cache_control"], list(probe.TARGETS))
        self.assertTrue(all(item["category"] == "validator_not_advertised"
                            for item in report["conditional"]))

    def test_enforce_requires_canonical_policy_and_missing_404(self):
        self.assertEqual(probe.run_probe("enforce", request=fake_request)["issues"], [])
        def request(path, conditional=None):
            return row(path, policy=None)
        report = probe.run_probe("enforce", request=request)
        self.assertEqual(sum(e["category"] == "target_policy"
                             for e in report["issues"]), 9)
        self.assertIn(probe.issue(probe.MISSING, "missing_not_404"), report["issues"])

    def test_missing_path_must_not_receive_new_policy(self):
        def request(path, conditional=None):
            return row(path, 404 if path == probe.MISSING else 200)
        report = probe.run_probe(request=request)
        self.assertIn(probe.issue(probe.MISSING, "missing_received_new_policy"),
                      report["issues"])

    def test_conditional_prefers_etag_and_checks_304(self):
        calls = []
        def request(path, conditional=None):
            calls.append((path, conditional))
            result = fake_request(path, conditional)
            result["etag"] = ['"tag"']
            result["last_modified"] = ["Tue, 13 Oct 2026 00:00:00 GMT"]
            return result
        report = probe.run_probe("enforce", request=request)
        self.assertEqual(report["issues"], [])
        self.assertEqual([value for _, value in calls if value],
                         [("If-None-Match", '"tag"')] * 2)

    def test_conditional_last_modified_and_duplicate_policy_failure(self):
        def request(path, conditional=None):
            result = fake_request(path, conditional)
            result["last_modified"] = ["Tue, 13 Oct 2026 00:00:00 GMT"]
            if conditional:
                self.assertEqual(conditional[0], "If-Modified-Since")
                result["cache_control"].append(probe.POLICY)
            return result
        report = probe.run_probe("enforce", request=request)
        self.assertEqual(sum(e["category"] == "target_policy"
                             for e in report["issues"]), 2)

    def test_advertised_validator_requires_304(self):
        def request(path, conditional=None):
            result = fake_request(path)
            result["etag"] = ['"tag"']
            return result
        report = probe.run_probe(request=request)
        self.assertEqual(sum(e["category"] == "conditional_not_304"
                             for e in report["issues"]), 2)

    def test_controls_compare_exact_status_and_cache_policy(self):
        baseline = probe.run_probe(request=fake_request)
        report = probe.run_probe("enforce", baseline, fake_request)
        self.assertEqual(report["issues"], [])
        baseline["observations"][len(probe.TARGETS)]["cache_control"] = ["private"]
        report = probe.run_probe("enforce", baseline, fake_request)
        self.assertIn(probe.issue("/", "control_changed"), report["issues"])
        for bad in ({}, {"schema_version": 1, "origin": probe.ORIGIN,
                         "observations": []}):
            self.assertTrue(probe.compare_controls(report["observations"], bad))

    def test_invalid_mode(self):
        with self.assertRaisesRegex(ValueError, "invalid_mode"):
            probe.run_probe("post")


if __name__ == "__main__":
    unittest.main()
