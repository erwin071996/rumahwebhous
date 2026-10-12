"""Opt-in uncertain forward STOR tests. Synthetic bytes/transports; no network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deploy_ftps.py"
SPEC = importlib.util.spec_from_file_location("uncertain_stor_under_test", SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)
TIMEOUT = "curl: (28) FTP response timeout"
UNSET = object()

class Case:
    pass

class MemoryTransport:
    def __init__(self, case, role):
        self.case, self.role = case, role

    def read(self, path):
        c = self.case
        c.events.append((self.role, "read", path))
        if self.role == "forward" and path == c.path and c.file_written:
            if c.after_reads:
                value = c.after_reads.pop(0)
                if isinstance(value, Exception):
                    raise value
                return value
        if (self.role == "forward" and path == DEPLOY.STATE_PATH and
                c.state_written and c.state_readback is not UNSET):
            return c.state_readback
        return c.files.get(path)

    def write(self, path, data):
        c = self.case
        c.events.append((self.role, "write", path))
        if self.role == "restore":
            c.files[path] = data
            if c.rollback_error:
                raise c.rollback_error
            return
        if path == c.path:
            if c.use_state:
                plan = json.loads((c.report_dir / "rollback-plan.json").read_text())
                c.test.assertIn(path, plan["touched_paths"])
                c.test.assertEqual(plan["files"][0]["before_existed"], c.old is not None)
            if c.old is not None:
                c.test.assertEqual((c.report_dir / "before" / path).read_bytes(), c.old)
            c.file_written = True
            if c.fault_bytes is None:
                c.files.pop(path, None)
            else:
                c.files[path] = c.fault_bytes
            raise c.write_error
        c.state_written = True
        c.files[path] = data
        if c.state_error:
            raise c.state_error

    def delete_created(self, path):
        c = self.case
        c.events.append((self.role, "delete", path))
        c.files.pop(path, None)

    def close(self):
        self.case.events.append((self.role, "close", ""))

class UncertainPublicStorTests(unittest.TestCase):
    def exercise(self, *, existed=True, enabled=True, message=TIMEOUT,
                 code=28, desired=b"synthetic desired private marker",
                 fault_bytes=UNSET, after_reads=UNSET, use_state=True,
                 http_error=None, state_error=None, state_readback=UNSET,
                 rollback_error=None, state_path=False, target="assets/ui/brief.js"):
        c = Case()
        c.test, c.path = self, DEPLOY.STATE_PATH if state_path else target
        c.old_state = DEPLOY.encode_successful_state("1" * 40)
        c.desired_state = DEPLOY.encode_successful_state("2" * 40)
        c.old = c.old_state if state_path else (b"synthetic old" if existed else None)
        c.desired = c.desired_state if state_path else desired
        c.fault_bytes = c.desired if fault_bytes is UNSET else fault_bytes
        c.after_reads = [c.desired, c.desired] if after_reads is UNSET else list(after_reads)
        c.write_error = DEPLOY.CurlError(code, message)
        c.http_error, c.state_error = http_error, state_error
        c.state_readback, c.rollback_error = state_readback, rollback_error
        c.use_state = use_state and not state_path
        c.file_written = c.state_written = False
        c.events, c.report = [], {"uploaded": [], "already_current": [], "rollback": "not needed"}
        c.files = {DEPLOY.STATE_PATH: c.old_state}
        if c.old is not None:
            c.files[c.path] = c.old
        c.error = None
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder) / "public_html"
            (site / c.path).parent.mkdir(parents=True)
            (site / c.path).write_bytes(c.desired)
            c.report_dir = Path(folder) / "report"
            forward, restore = MemoryTransport(c, "forward"), MemoryTransport(c, "restore")
            def verify():
                c.events.append(("caller", "HTTP", ""))
                if c.http_error:
                    raise c.http_error
                return {"synthetic": True}
            with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "REPORT", c.report_dir):
                with patch.object(DEPLOY, "previous", return_value=c.old):
                    with patch.object(DEPLOY, "Server", return_value=restore) as reconnect:
                        with patch.object(DEPLOY, "verify_live", side_effect=verify):
                            try:
                                options = {"state_update": (c.old_state, c.desired_state) if c.use_state else None}
                                if enabled is not UNSET:
                                    options["allow_uncertain_public_stor"] = enabled
                                DEPLOY.deploy_changes(forward, [c.path], "base", c.report, **options)
                            except Exception as error:
                                c.error = error
                        c.reconnects = reconnect.call_count
        self.assertEqual(c.events.count(("forward", "write", c.path)), 1)
        return c

    def assert_rolled_back(self, c):
        self.assertEqual(c.report["rollback"], "verified")
        self.assertEqual(c.files.get(c.path), c.old)
        self.assertEqual(c.files[DEPLOY.STATE_PATH], c.old_state)
        self.assertNotIn("successful_release_commit", c.report)

    def assert_original_failure(self, c):
        self.assertIs(c.error, c.write_error)
        self.assert_rolled_back(c)
        self.assertNotIn("recovered_stor_response_timeouts", c.report)
        self.assertEqual(c.reconnects, 1)

    def test_diagnostic_allows_exact_one_to_three_lines_only(self):
        for count in (1, 2, 3):
            for trailing in ("", "\n"):
                with self.subTest(count=count, trailing=bool(trailing)):
                    self.assertTrue(DEPLOY.is_stor_response_timeout(
                        DEPLOY.CurlError(28, "\n".join([TIMEOUT] * count) + trailing)))
        bad = [
            "", TIMEOUT + " ", " " + TIMEOUT, TIMEOUT + "\n\n",
            "\n".join([TIMEOUT] * 4), TIMEOUT + "\r\n",
            TIMEOUT + "\ncurl: (28) SSL connection timeout",
            "FTPS curl exceeded the 210-second subprocess deadline",
            "curl: (28) Operation timed out", "server text: " + TIMEOUT,
        ]
        for message in bad:
            with self.subTest(message=message):
                self.assertFalse(DEPLOY.is_stor_response_timeout(DEPLOY.CurlError(28, message)))
        for code in (9, 35, 60):
            self.assertFalse(DEPLOY.is_stor_response_timeout(DEPLOY.CurlError(code, TIMEOUT)))
        self.assertFalse(DEPLOY.is_stor_response_timeout(RuntimeError(TIMEOUT)))

    def test_old_and_new_public_file_exact_read_reconciles_without_new_stor(self):
        for existed in (True, False):
            with self.subTest(existed=existed):
                c = self.exercise(existed=existed, message="\n".join([TIMEOUT] * 3) + "\n")
                self.assertIsNone(c.error)
                self.assertEqual(c.reconnects, 0)
                self.assertEqual(c.files[c.path], c.desired)
                self.assertEqual(c.files[DEPLOY.STATE_PATH], c.desired_state)
                self.assertEqual(c.events.count(("forward", "read", c.path)), 3)
                self.assertEqual(c.report["recovered_stor_response_timeouts"],
                                 [{"path": c.path, "sha256": DEPLOY.digest(c.desired)}])
                self.assertEqual(c.report["successful_release_commit"], "2" * 40)
                self.assertLess(c.events.index(("caller", "HTTP", "")),
                                c.events.index(("forward", "write", DEPLOY.STATE_PATH)))
                self.assertNotIn("synthetic desired private marker", json.dumps(c.report))

    def test_genuine_empty_bytes_can_match_but_missing_never_matches(self):
        for existed in (True, False):
            with self.subTest(existed=existed):
                c = self.exercise(existed=existed, desired=b"")
                self.assertIsNone(c.error)
                self.assertEqual(c.files[c.path], b"")
                c = self.exercise(existed=existed, desired=b"", after_reads=[None])
                self.assert_original_failure(c)

    def test_missing_empty_partial_and_same_size_wrong_bytes_preserve_original(self):
        desired = b"ABC\nDEF"
        for existed in (True, False):
            for data in (None, b"", b"ABC", b"ABC\nDEG", b"ABC\r\nDEF"):
                with self.subTest(existed=existed, data=data):
                    c = self.exercise(existed=existed, desired=desired,
                                      fault_bytes=data, after_reads=[data])
                    self.assert_original_failure(c)
                    self.assertEqual(c.events.count(("forward", "read", c.path)), 2)

    def test_matching_claimed_hash_does_not_replace_exact_bytes(self):
        with patch.object(DEPLOY, "digest", return_value="f" * 64):
            c = self.exercise(desired=b"AA", fault_bytes=b"AB", after_reads=[b"AB"])
        self.assert_original_failure(c)

    def test_fresh_read_failures_preserve_original_not_read_exception(self):
        for read_error in (DEPLOY.CurlError(28, TIMEOUT), DEPLOY.CurlError(60, "synthetic TLS"),
                           DEPLOY.CurlError(9, "synthetic denied"), RuntimeError("synthetic read")):
            c = self.exercise(after_reads=[read_error])
            self.assert_original_failure(c)
            self.assertIsNot(c.error, read_error)
            self.assertEqual(c.events.count(("forward", "read", c.path)), 2)

    def test_default_off_and_other_errors_do_not_attempt_recovery(self):
        c = self.exercise(enabled=False)
        self.assert_original_failure(c)
        self.assertEqual(c.events.count(("forward", "read", c.path)), 1)
        for code, message in [
            (9, TIMEOUT), (35, TIMEOUT), (60, TIMEOUT),
            (28, "FTPS curl exceeded the 210-second subprocess deadline"),
            (28, "curl: (28) Operation timed out"),
            (28, TIMEOUT + "\ncurl: (28) SSL connection timeout"),
        ]:
            with self.subTest(code=code, message=message):
                c = self.exercise(code=code, message=message)
                self.assert_original_failure(c)
                self.assertEqual(c.events.count(("forward", "read", c.path)), 1)

    def test_default_parameter_is_false_without_passing_opt_in(self):
        c = self.exercise(enabled=UNSET)
        self.assert_original_failure(c)
        self.assertEqual(c.events.count(("forward", "read", c.path)), 1)

    def test_only_exact_reviewed_paths_are_eligible(self):
        expected = {
            "assets/branding/logo-3dkan-688.webp", "assets/branding/logo-3dkan-original.jpg",
            "assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp",
            "assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp",
            "assets/ui/brief.css", "assets/ui/brief.js", "assets/ui/frontend.css",
            "assets/ui/frontend.js", "assets/ui/theme.css", "index.html", "projects.html",
        }
        self.assertEqual(set(DEPLOY.RECOVERABLE_PUBLIC_PATHS), expected)
        for path in expected:
            self.assertTrue(DEPLOY.is_recoverable_public_path(path))
        for path in (DEPLOY.STATE_PATH, "includes/config.php", "api.php", "unknown.html",
                     "./index.html", "assets/ui//brief.js", "../index.html",
                     "/index.html", "assets/ui/brief.js\n", None):
            self.assertFalse(DEPLOY.is_recoverable_public_path(path))

    def test_nonreviewed_and_noncanonical_prepared_paths_do_not_reconcile(self):
        for target in ("includes/config.php", "api.php", "unknown.html",
                       "./index.html", "assets/ui//brief.js"):
            with self.subTest(target=target):
                c = self.exercise(target=target)
                self.assert_original_failure(c)
                self.assertEqual(c.events.count(("forward", "read", c.path)), 1)

    def test_manual_prepared_state_path_is_ineligible_even_with_opt_in(self):
        c = self.exercise(state_path=True)
        self.assert_original_failure(c)
        self.assertEqual(c.events.count(("forward", "read", DEPLOY.STATE_PATH)), 1)

    def test_caller_second_readback_mismatch_or_error_still_rolls_back(self):
        for value in (b"synthetic later drift", DEPLOY.CurlError(60, "synthetic later TLS")):
            c = self.exercise(after_reads=[b"synthetic desired private marker", value])
            self.assertIsNotNone(c.error)
            self.assert_rolled_back(c)
            self.assertNotIn(("caller", "HTTP", ""), c.events)

    def test_http_failure_after_recovery_never_publishes_state(self):
        error = RuntimeError("synthetic HTTP")
        c = self.exercise(http_error=error)
        self.assertIs(c.error, error)
        self.assert_rolled_back(c)
        self.assertNotIn(("forward", "write", DEPLOY.STATE_PATH), c.events)

    def test_state_timeout_is_strict_even_when_state_bytes_match(self):
        error = DEPLOY.CurlError(28, TIMEOUT)
        c = self.exercise(state_error=error)
        self.assertIs(c.error, error)
        self.assert_rolled_back(c)
        self.assertEqual(c.events.count(("forward", "read", DEPLOY.STATE_PATH)), 1)

    def test_state_readback_mismatch_still_rolls_back_reconciled_public_file(self):
        c = self.exercise(state_readback=b"synthetic wrong state")
        self.assertIsInstance(c.error, RuntimeError)
        self.assert_rolled_back(c)

    def test_rollback_timeout_is_strict_even_when_old_bytes_are_restored(self):
        error = DEPLOY.CurlError(28, TIMEOUT)
        c = self.exercise(after_reads=[None], rollback_error=error)
        self.assertIs(c.error, error)
        self.assertEqual(c.files[c.path], c.old)
        self.assertTrue(c.report["rollback"].startswith("failed;"))
        self.assertNotIn("successful_release_commit", c.report)

    def test_run_deployment_explicitly_enables_forward_opt_in(self):
        server, report = object(), {"uploaded": [], "already_current": []}
        old = DEPLOY.encode_successful_state("1" * 40)
        desired = DEPLOY.encode_successful_state("2" * 40)
        with patch.object(DEPLOY, "checked_commit", return_value="2" * 40):
            with patch.object(DEPLOY, "git", return_value=b"synthetic"):
                with patch.object(DEPLOY, "read_successful_state", return_value=("1" * 40, old)):
                    with patch.object(DEPLOY, "planned_changes", return_value=["assets/ui/brief.js"]):
                        with patch.object(DEPLOY, "deploy_changes") as transaction:
                            DEPLOY.run_deployment(server, {}, report)
        transaction.assert_called_once_with(
            server, ["assets/ui/brief.js"], "1" * 40, report,
            state_update=(old, desired), allow_uncertain_public_stor=True)

if __name__ == "__main__":
    unittest.main()
