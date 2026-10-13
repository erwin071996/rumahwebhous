"""Focused before-image batching tests. Synthetic files and fake curl only."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deploy_ftps.py"
SPEC = importlib.util.spec_from_file_location("deploy_batch_under_test", SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class BeforeImageBatchTests(unittest.TestCase):
    def server(self):
        server = DEPLOY.Server.__new__(DEPLOY.Server)
        server.host = "kilimanjaro.iixcp.rumahweb.net"
        server.user = "synthetic-batch-user"
        server.password = "synthetic-batch-password"
        server.curl = "synthetic-curl"
        return server

    def outputs(self, config):
        return [Path(json.loads(line.split("=", 1)[1].strip()))
                for line in config.decode().splitlines() if line.startswith("output = ")]

    def respond(self, payloads, calls):
        def invoke(argv, **kwargs):
            config = kwargs["input"]
            outputs = self.outputs(config)
            calls.append((argv, kwargs, outputs))
            for output, data in zip(outputs, payloads):
                output.write_bytes(data)
            return SimpleNamespace(returncode=0, stdout=b"0\n" * len(outputs), stderr=b"")
        return invoke

    def test_success_maps_separate_outputs_and_accepts_existing_empty_file(self):
        server = self.server()
        calls = []
        output = io.StringIO()
        with redirect_stdout(output), patch.object(DEPLOY.subprocess, "run",
                side_effect=self.respond([b"first-before", b""], calls)):
            result = server.read_many(["index.html", "assets/empty.css"])
        self.assertEqual(result, {"index.html": b"first-before", "assets/empty.css": b""})
        self.assertEqual(len(calls), 1)
        argv, kwargs, outputs = calls[0]
        self.assertEqual(argv, ["synthetic-curl", "-q", "--config", "-"])
        self.assertEqual(kwargs["timeout"], 420)
        config = kwargs["input"].decode()
        for option in ["ssl-reqd", "ipv4", "fail-early", "tlsv1.2", 'tls-max = "1.2"',
                       'ftp-method = "singlecwd"', "connect-timeout = 12", "max-time = 60",
                       "retry = 2", "retry-delay = 1", "retry-max-time = 150"]:
            self.assertIn(option, config.splitlines())
        for option in ["insecure", "parallel", "next", "upload-file", "ftp-create-dirs", "quote ="]:
            self.assertNotIn(option, config)
        self.assertEqual(config.count("url = "), 2)
        self.assertIn("ftp://" + server.host + ":21/public_html/index.html", config)
        self.assertIn("ftp://" + server.host + ":21/public_html/assets/empty.css", config)
        self.assertIn(server.user + ":" + server.password, config)
        for secret in [server.user, server.password, "first-before"]:
            self.assertNotIn(secret, repr(argv))
            self.assertNotIn(secret, output.getvalue())
        self.assertEqual([path.name for path in outputs], ["00.bin", "01.bin"])
        self.assertTrue(all(not path.exists() for path in outputs))

    def test_real_curl_local_config_output_pairing_and_exitcode_escape(self):
        curl = DEPLOY.shutil.which("curl")
        self.assertIsNotNone(curl, "The cloud publisher requires installed curl")
        with tempfile.TemporaryDirectory(prefix="synthetic-curl-config-") as folder:
            root = Path(folder)
            payloads = [b"first synthetic file\n", b"second synthetic file\n"]
            sources = [root / f"source {index}.txt" for index in range(2)]
            outputs = [root / f"{index:02d} output.bin" for index in range(2)]
            config = ["silent", "show-error", "fail-early",
                      "write-out = " + DEPLOY.Server.quoted("%{exitcode}\\n")]
            for source, output, data in zip(sources, outputs, payloads):
                source.write_bytes(data)
                # Local file URLs only: no network, credential or FTPS options.
                config += ["url = " + DEPLOY.Server.quoted(source.resolve().as_uri()),
                           "output = " + DEPLOY.Server.quoted(output)]
            result = subprocess.run([curl, "-q", "--config", "-"],
                                    input=("\n".join(config) + "\n").encode(),
                                    capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, "Synthetic local curl configuration failed")
            self.assertEqual(result.stdout.splitlines(), [b"0", b"0"])
            self.assertEqual([output.read_bytes() for output in outputs], payloads)

    def test_large_inventory_uses_serial_twenty_url_batches(self):
        server = self.server()
        calls = []
        with redirect_stdout(io.StringIO()), patch.object(DEPLOY.subprocess, "run",
                side_effect=self.respond([b"before"] * 20, calls)):
            result = server.read_many([f"pages/page-{i}.html" for i in range(41)])
        self.assertEqual(len(result), 41)
        self.assertEqual([len(call[2]) for call in calls], [20, 20, 1])
        self.assertEqual([call[1]["timeout"] for call in calls], [900, 900, 210])
        for _, kwargs, _ in calls:
            self.assertNotIn("parallel", kwargs["input"].decode())
            self.assertNotIn("next", kwargs["input"].decode())

    def test_failed_curl_discards_partial_outputs_and_redacts_all_streams(self):
        server = self.server()
        def fail(argv, **kwargs):
            self.outputs(kwargs["input"])[0].write_bytes(b"partial-private-before")
            return SimpleNamespace(returncode=78, stdout=b"private-stdout",
                                   stderr=(server.user + ":" + server.password + " private-stderr").encode())
        output = io.StringIO()
        with redirect_stdout(output), patch.object(DEPLOY.subprocess, "run", side_effect=fail):
            with self.assertRaises(DEPLOY.CurlError) as caught:
                server.read_many(["index.html", "projects.html"])
        self.assertEqual(caught.exception.code, 78)
        self.assertEqual(str(caught.exception), "FTPS before-image read batch failed")
        combined = str(caught.exception) + repr(caught.exception) + output.getvalue()
        for private in [server.user, server.password, "private-stderr", "private-stdout", "partial-private-before"]:
            self.assertNotIn(private, combined)

    def test_success_exit_with_missing_output_still_fails_closed(self):
        server = self.server()
        def missing(argv, **kwargs):
            self.outputs(kwargs["input"])[0].write_bytes(b"first")
            return SimpleNamespace(returncode=0, stdout=b"0\n0\n", stderr=b"")
        with redirect_stdout(io.StringIO()), patch.object(DEPLOY.subprocess, "run", side_effect=missing):
            with self.assertRaisesRegex(RuntimeError, "output missing"):
                server.read_many(["index.html", "projects.html"])

    def test_early_transfer_error_cannot_hide_behind_successful_final_status(self):
        server = self.server()
        def masked(argv, **kwargs):
            outputs = self.outputs(kwargs["input"])
            outputs[0].write_bytes(b"")
            outputs[1].write_bytes(b"last-success")
            return SimpleNamespace(returncode=0, stdout=b"78\n0\n", stderr=b"private-server-diagnostic")
        with redirect_stdout(io.StringIO()), patch.object(DEPLOY.subprocess, "run", side_effect=masked):
            with self.assertRaisesRegex(RuntimeError, "transfer receipt differs"):
                server.read_many(["index.html", "projects.html"])

    def test_symlink_output_is_never_accepted(self):
        server = self.server()
        def symlink(argv, **kwargs):
            output = self.outputs(kwargs["input"])[0]
            actual = output.parent / "unrequested.bin"
            actual.write_bytes(b"synthetic-data")
            output.symlink_to(actual)
            return SimpleNamespace(returncode=0, stdout=b"0\n", stderr=b"")
        with redirect_stdout(io.StringIO()), patch.object(DEPLOY.subprocess, "run", side_effect=symlink):
            with self.assertRaisesRegex(RuntimeError, "output missing"):
                server.read_many(["index.html"])

    def test_later_batch_failure_returns_no_partial_mapping(self):
        server = self.server()
        calls = []
        def later(argv, **kwargs):
            outputs = self.outputs(kwargs["input"])
            calls.append(len(outputs))
            if len(calls) == 2:
                return SimpleNamespace(returncode=28, stdout=b"28\n", stderr=b"private-timeout")
            for output in outputs:
                output.write_bytes(b"before")
            return SimpleNamespace(returncode=0, stdout=b"0\n" * len(outputs), stderr=b"")
        with redirect_stdout(io.StringIO()), patch.object(DEPLOY.subprocess, "run", side_effect=later):
            with self.assertRaises(DEPLOY.CurlError):
                server.read_many([f"page-{i}.html" for i in range(21)])
        self.assertEqual(calls, [20, 1])

    def test_timeout_never_exposes_command_input_or_captured_data(self):
        server = self.server()
        timeout = subprocess.TimeoutExpired(["synthetic-curl", server.password], 420,
                                           output=b"synthetic-private-body",
                                           stderr=(server.user + ":" + server.password).encode())
        timeout.input = ("user = " + server.password).encode()
        output = io.StringIO()
        with redirect_stdout(output), patch.object(DEPLOY.subprocess, "run", side_effect=timeout):
            with self.assertRaises(DEPLOY.CurlError) as caught:
                server.read_many(["index.html", "projects.html"])
        error = caught.exception
        self.assertEqual(error.code, 28)
        self.assertTrue(error.__suppress_context__)
        rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        combined = output.getvalue() + str(error) + repr(error) + rendered
        for private in [server.user, server.password, "synthetic-private-body", "user = "]:
            self.assertNotIn(private, combined)

    def test_state_unsafe_and_duplicate_paths_block_curl(self):
        server = self.server()
        for paths in [[DEPLOY.STATE_PATH], ["../private"], ["index.html", "index.html"]]:
            with self.subTest(paths=paths), patch.object(DEPLOY.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    server.read_many(paths)
                run.assert_not_called()
        with patch.object(DEPLOY.subprocess, "run") as run:
            self.assertEqual(server.read_many([]), {})
            run.assert_not_called()

    def test_custom_request_adapter_retains_its_individual_read_contract(self):
        class Adapter(DEPLOY.Server):
            def __init__(self):
                self.requests = []
            def request(self, path="", extra=()):
                self.requests.append(path)
                return path.encode()
        server = Adapter()
        with redirect_stdout(io.StringIO()), patch.object(DEPLOY.subprocess, "run") as run:
            self.assertEqual(server.read_many(["index.html", "projects.html"]),
                             {"index.html": b"index.html", "projects.html": b"projects.html"})
        self.assertEqual(server.requests, ["index.html", "projects.html"])
        run.assert_not_called()


class BatchPreparationTests(unittest.TestCase):
    class Server:
        def __init__(self, old, state=None, *, batch_error=False, incomplete=False):
            self.files = dict(old)
            if state is not None:
                self.files[DEPLOY.STATE_PATH] = state
            self.reads = []; self.batches = []; self.writes = []
            self.batch_error = batch_error; self.incomplete = incomplete
        def read(self, path):
            self.reads.append(path)
            return self.files.get(path)
        def read_many(self, paths):
            self.batches.append(list(paths))
            if self.batch_error:
                raise DEPLOY.CurlError(28, "synthetic before-image failure")
            result = {path: self.files.get(path) for path in paths}
            if self.incomplete and paths:
                result.pop(paths[-1])
            return result
        def write(self, path, data):
            if len(self.batches) != 1:
                raise AssertionError("Writes must follow exactly one complete before-image cache")
            self.writes.append(path)
            self.files[path] = data
        def close(self):
            pass

    def setup_files(self, root, files):
        site = root / "public_html"
        site.mkdir()
        for path, data in files.items():
            target = site / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return site, root / "report"

    def report(self):
        return {"uploaded": [], "already_current": [], "rollback": "not needed"}

    def test_only_existing_old_files_are_batched_new_and_state_keep_individual_reads(self):
        old = {"a.html": b"old-a", "b.html": b"old-b"}
        desired = {"a.html": b"new-a", "b.html": b"new-b", "new.html": b"new-file"}
        old_state = DEPLOY.encode_successful_state("a" * 40)
        new_state = DEPLOY.encode_successful_state("b" * 40)
        server = self.Server(old, old_state)
        with tempfile.TemporaryDirectory() as folder:
            site, report_path = self.setup_files(Path(folder), desired)
            with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "REPORT", report_path), \
                    patch.object(DEPLOY, "previous", side_effect=lambda base, path: old.get(path.removeprefix("public_html/"))), \
                    patch.object(DEPLOY, "verify_live", return_value={"synthetic": True}):
                result = self.report()
                DEPLOY.deploy_changes(server, list(desired), "a" * 40, result,
                                      state_update=(old_state, new_state))
            self.assertEqual(server.batches, [["a.html", "b.html"]])
            self.assertEqual(server.reads[0], DEPLOY.STATE_PATH)
            self.assertIn("new.html", server.reads)
            self.assertEqual(server.writes, ["a.html", "b.html", "new.html", DEPLOY.STATE_PATH])
            self.assertEqual((report_path / "before/a.html").read_bytes(), b"old-a")
            self.assertEqual((report_path / "before/b.html").read_bytes(), b"old-b")
            self.assertEqual((report_path / "before" / DEPLOY.STATE_PATH).read_bytes(), old_state)
            self.assertEqual(result["successful_release_commit"], "b" * 40)

    def test_failed_or_incomplete_batch_stops_before_any_stor(self):
        old = {"a.html": b"old-a", "b.html": b"old-b"}
        for options in [{"batch_error": True}, {"incomplete": True}]:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                site, report_path = self.setup_files(Path(folder), {"a.html": b"new-a", "b.html": b"new-b"})
                server = self.Server(old, **options)
                with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "REPORT", report_path), \
                        patch.object(DEPLOY, "previous", side_effect=lambda base, path: old.get(path.removeprefix("public_html/"))):
                    with self.assertRaises((DEPLOY.CurlError, RuntimeError)):
                        DEPLOY.deploy_changes(server, list(old), "a" * 40, self.report())
                self.assertEqual(server.writes, [])

    def test_cached_before_image_drift_still_blocks_all_stor(self):
        old = {"a.html": b"old-a"}
        server = self.Server({"a.html": b"unexpected-live"})
        with tempfile.TemporaryDirectory() as folder:
            site, report_path = self.setup_files(Path(folder), {"a.html": b"new-a"})
            with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "REPORT", report_path), \
                    patch.object(DEPLOY, "previous", return_value=old["a.html"]):
                with self.assertRaisesRegex(RuntimeError, "Live file drift"):
                    DEPLOY.deploy_changes(server, ["a.html"], "a" * 40, self.report())
        self.assertEqual(server.writes, [])

    def test_cached_already_current_file_retains_no_write_behavior(self):
        server = self.Server({"a.html": b"desired"})
        with tempfile.TemporaryDirectory() as folder:
            site, report_path = self.setup_files(Path(folder), {"a.html": b"desired"})
            with patch.object(DEPLOY, "SITE", site), patch.object(DEPLOY, "REPORT", report_path), \
                    patch.object(DEPLOY, "previous", return_value=b"old"), patch.object(DEPLOY, "verify_live", return_value={}):
                result = self.report()
                DEPLOY.deploy_changes(server, ["a.html"], "a" * 40, result)
        self.assertEqual(result["already_current"], ["a.html"])
        self.assertEqual(server.writes, [])
        self.assertEqual(server.reads, [])


if __name__ == "__main__":
    unittest.main()
