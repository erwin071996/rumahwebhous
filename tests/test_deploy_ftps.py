"""Exercise deployments against an in-memory remote; never use the network."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deploy_ftps.py"
SPEC = importlib.util.spec_from_file_location("deploy_ftps_under_test", SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class MemoryServer:
    def __init__(self, storage, *, fail_path=None, corrupt_path=None):
        self.storage = storage
        self.fail_path = fail_path
        self.corrupt_path = corrupt_path
        self.writes = []
        self.deletions = []
        self.closed = False

    def read(self, path):
        return self.storage.get(path)

    def write(self, path, data):
        self.writes.append(path)
        if path == self.fail_path:
            # STOR can overwrite/truncate an existing remote file before raising.
            self.storage[path] = data[:2]
            raise OSError("Simulated interrupted transfer")
        if path == self.corrupt_path:
            self.storage[path] = data + b"unexpected transfer bytes"
        else:
            self.storage[path] = data

    def delete_created(self, path):
        self.deletions.append(path)
        del self.storage[path]

    def close(self):
        self.closed = True


class DeploymentFixture(unittest.TestCase):
    def setUp(self):
        workspace = SCRIPT.parents[1]
        self.temp = tempfile.TemporaryDirectory(prefix=".deploy-test-", dir=workspace)
        # Cleanup only the unique test directory created inside this checkout.
        self.assertTrue(Path(self.temp.name).resolve().is_relative_to(workspace))
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name) / "public_html"
        self.site.mkdir()
        self.report_dir = Path(self.temp.name) / "deployment-result"
        self.report = {
            "uploaded": [], "already_current": [], "rollback": "not needed"
        }
        self.old = {}
        self.live_verification = {"sitemaps": 11, "unique_urls": 500}
        self.site_patch = patch.object(DEPLOY, "SITE", self.site)
        self.report_patch = patch.object(DEPLOY, "REPORT", self.report_dir)
        self.previous_patch = patch.object(
            DEPLOY, "previous",
            side_effect=lambda base, path: self.old.get(path.removeprefix("public_html/")),
        )
        self.verify_patch = patch.object(
            DEPLOY, "verify_live", return_value=self.live_verification
        )
        self.site_patch.start()
        self.report_patch.start()
        self.previous_patch.start()
        self.verify = self.verify_patch.start()
        self.addCleanup(self.site_patch.stop)
        self.addCleanup(self.report_patch.stop)
        self.addCleanup(self.previous_patch.stop)
        self.addCleanup(self.verify_patch.stop)

    def prepare(self, path, before, desired):
        local = self.site / path
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(desired)
        self.old[path] = before


class DeployChangesTests(DeploymentFixture):
    def test_drift_refuses_entire_batch_before_any_upload(self):
        self.prepare("index.html", b"old home", b"new home")
        self.prepare("includes/footer.html", b"old footer", b"new footer")
        storage = {"index.html": b"old home", "includes/footer.html": b"external edit"}
        server = MemoryServer(storage)
        with patch.object(DEPLOY, "Server") as reconnect:
            with self.assertRaisesRegex(RuntimeError, "Live file drift"):
                DEPLOY.deploy_changes(server, list(storage), "base", self.report)
        self.assertEqual(server.writes, [])
        self.assertEqual(storage["index.html"], b"old home")
        self.assertEqual(storage["includes/footer.html"], b"external edit")
        self.verify.assert_not_called()
        reconnect.assert_not_called()

    def test_interrupted_upload_restores_truncated_and_completed_files(self):
        self.prepare("index.html", b"old home", b"new home")
        self.prepare("includes/footer.html", b"old footer", b"new footer")
        original = {"index.html": b"old home", "includes/footer.html": b"old footer"}
        storage = original.copy()
        server = MemoryServer(storage, fail_path="includes/footer.html")
        restore = MemoryServer(storage)
        with patch.object(DEPLOY, "Server", return_value=restore):
            with self.assertRaisesRegex(OSError, "interrupted transfer"):
                DEPLOY.deploy_changes(server, list(storage), "base", self.report)
        self.assertEqual(storage, original)
        self.assertEqual(restore.writes, ["includes/footer.html", "index.html"])
        self.assertEqual(self.report["rollback"], "verified")
        self.assertTrue(server.closed)
        self.assertTrue(restore.closed)
        for path, data in original.items():
            self.assertEqual((self.report_dir / "before" / path).read_bytes(), data)
        self.verify.assert_not_called()

    def test_already_current_is_idempotent_and_still_verifies_live(self):
        self.prepare("index.html", b"old home", b"new home")
        storage = {"index.html": b"new home"}
        server = MemoryServer(storage)
        with patch.object(DEPLOY, "Server") as reconnect:
            DEPLOY.deploy_changes(server, ["index.html"], "base", self.report)
        self.assertEqual(storage, {"index.html": b"new home"})
        self.assertEqual(server.writes, [])
        self.assertEqual(self.report["already_current"], ["index.html"])
        self.assertEqual(self.report["uploaded"], [])
        self.assertEqual(self.report["live"], self.live_verification)
        self.verify.assert_called_once_with()
        reconnect.assert_not_called()
        self.assertFalse((self.report_dir / "before").exists())

    def test_readback_mismatch_restores_previous_bytes(self):
        self.prepare("index.html", b"old home", b"new home")
        storage = {"index.html": b"old home"}
        server = MemoryServer(storage, corrupt_path="index.html")
        restore = MemoryServer(storage)
        with patch.object(DEPLOY, "Server", return_value=restore):
            with self.assertRaisesRegex(RuntimeError, "FTPS readback differs"):
                DEPLOY.deploy_changes(server, ["index.html"], "base", self.report)
        self.assertEqual(storage, {"index.html": b"old home"})
        self.assertEqual(self.report["rollback"], "verified")
        self.assertEqual(self.report["uploaded"], [])
        self.assertEqual((self.report_dir / "before/index.html").read_bytes(), b"old home")
        self.verify.assert_not_called()

    def test_interrupted_new_file_is_removed_during_rollback(self):
        self.prepare("assets/new.txt", None, b"new asset")
        storage = {}
        server = MemoryServer(storage, fail_path="assets/new.txt")
        restore = MemoryServer(storage)
        with patch.object(DEPLOY, "Server", return_value=restore):
            with self.assertRaisesRegex(OSError, "interrupted transfer"):
                DEPLOY.deploy_changes(server, ["assets/new.txt"], "base", self.report)
        self.assertEqual(storage, {})
        self.assertEqual(restore.deletions, ["assets/new.txt"])
        self.assertEqual(self.report["rollback"], "verified")

    def test_failed_new_file_transfer_before_creation_needs_no_delete(self):
        self.prepare("assets/new.txt", None, b"new asset")
        storage = {}
        server = MemoryServer(storage)
        restore = MemoryServer(storage)
        with patch.object(server, "write", side_effect=OSError("STOR refused")):
            with patch.object(DEPLOY, "Server", return_value=restore):
                with self.assertRaisesRegex(OSError, "STOR refused"):
                    DEPLOY.deploy_changes(server, ["assets/new.txt"], "base", self.report)
        self.assertEqual(storage, {})
        self.assertEqual(restore.deletions, [])
        self.assertEqual(self.report["rollback"], "verified")

    def test_live_http_failure_restores_successful_upload(self):
        self.prepare("index.html", b"old home", b"new home")
        storage = {"index.html": b"old home"}
        server = MemoryServer(storage)
        restore = MemoryServer(storage)
        self.verify.side_effect = RuntimeError("Live HTTP verification failed")
        with patch.object(DEPLOY, "Server", return_value=restore):
            with self.assertRaisesRegex(RuntimeError, "Live HTTP verification failed"):
                DEPLOY.deploy_changes(server, ["index.html"], "base", self.report)
        self.assertEqual(storage, {"index.html": b"old home"})
        self.assertEqual(self.report["rollback"], "verified")
        self.verify.assert_called_once_with()

    def test_failed_live_verification_without_changes_needs_no_reconnect(self):
        self.prepare("index.html", b"old home", b"new home")
        storage = {"index.html": b"new home"}
        server = MemoryServer(storage)
        self.verify.side_effect = RuntimeError("Live HTTP verification failed")
        with patch.object(DEPLOY, "Server") as reconnect:
            with self.assertRaisesRegex(RuntimeError, "Live HTTP verification failed"):
                DEPLOY.deploy_changes(server, ["index.html"], "base", self.report)
        self.assertEqual(storage, {"index.html": b"new home"})
        self.assertEqual(self.report["rollback"], "no files changed")
        reconnect.assert_not_called()

    def test_rollback_connection_failure_is_reported_and_preserves_backup(self):
        self.prepare("index.html", b"old home", b"new home")
        storage = {"index.html": b"old home"}
        server = MemoryServer(storage, fail_path="index.html")
        with patch.object(DEPLOY, "Server", side_effect=OSError("Cannot reconnect")):
            with self.assertRaisesRegex(OSError, "Cannot reconnect"):
                DEPLOY.deploy_changes(server, ["index.html"], "base", self.report)
        self.assertEqual(self.report["rollback"], "failed; restore the saved before/ files")
        self.assertEqual((self.report_dir / "before/index.html").read_bytes(), b"old home")
        self.assertEqual(storage["index.html"], b"ne")
        self.assertTrue(server.closed)


class SuccessfulReleaseTests(DeploymentFixture):
    BASE = "a" * 40
    FAILED = "b" * 40
    HEAD = "c" * 40

    def git_for(self, head, paths):
        def respond(*args):
            if args == ("rev-parse", "HEAD"):
                return head.encode()
            if args[0] == "cat-file":
                return b"commit\n"
            if args[0] == "merge-base":
                return b""
            if args[0] == "diff":
                self.assertEqual(args[4:6], (self.BASE, head))
                return b"".join(b"M\0public_html/" + path.encode() + b"\0" for path in paths)
            self.fail("Unexpected Git operation: " + args[0])
        return respond

    def report_for_run(self):
        return {"uploaded": [], "already_current": [], "rollback": "not needed"}

    def test_failed_a_then_independent_b_deploys_all_pending_changes(self):
        self.prepare("a.html", b"original A", b"change from commit A")
        self.prepare("b.html", b"original B", b"original B")
        original_state = DEPLOY.encode_successful_state(self.BASE)
        original = {
            "a.html": b"original A", "b.html": b"original B",
            DEPLOY.STATE_PATH: original_state,
        }
        storage = original.copy()
        failed_server = MemoryServer(storage, fail_path="a.html")
        restore = MemoryServer(storage)
        with patch.object(DEPLOY, "git", side_effect=self.git_for(self.FAILED, ["a.html"])):
            with patch.object(DEPLOY, "Server", return_value=restore):
                with self.assertRaisesRegex(OSError, "interrupted transfer"):
                    DEPLOY.run_deployment(failed_server, {}, self.report)
        self.assertEqual(storage, original)
        self.assertEqual(self.report["rollback"], "verified")

        # Commit B changes a different file; push.before points to failed A.
        # The remote success remains BASE, so both source changes must be sent.
        self.prepare("b.html", b"original B", b"independent change from commit B")
        server = MemoryServer(storage)
        report_b = self.report_for_run()
        with patch.dict(DEPLOY.os.environ, {"BEFORE_SHA": self.FAILED}):
            with patch.object(DEPLOY, "git", side_effect=self.git_for(self.HEAD, ["a.html", "b.html"])) as git_mock:
                DEPLOY.run_deployment(server, {}, report_b)
        self.assertEqual(storage["a.html"], b"change from commit A")
        self.assertEqual(storage["b.html"], b"independent change from commit B")
        self.assertEqual(DEPLOY.json.loads(storage[DEPLOY.STATE_PATH])["commit"], self.HEAD)
        self.assertEqual(server.writes, ["a.html", "b.html", DEPLOY.STATE_PATH])
        self.assertEqual(report_b["previous_successful_commit"], self.BASE)
        self.assertEqual(report_b["successful_release_commit"], self.HEAD)
        diff_call = [call for call in git_mock.call_args_list if call.args[0] == "diff"]
        self.assertEqual(len(diff_call), 1)
        self.assertEqual(diff_call[0].args[4], self.BASE)

    def test_failed_state_publication_restores_source_and_old_state(self):
        self.prepare("index.html", b"old home", b"new home")
        old_state = DEPLOY.encode_successful_state(self.BASE)
        original = {"index.html": b"old home", DEPLOY.STATE_PATH: old_state}
        storage = original.copy()
        server = MemoryServer(storage, fail_path=DEPLOY.STATE_PATH)
        restore = MemoryServer(storage)
        with patch.object(DEPLOY, "Server", return_value=restore):
            with self.assertRaisesRegex(OSError, "interrupted transfer"):
                DEPLOY.deploy_changes(server, ["index.html"], self.BASE, self.report,
                    state_update=(old_state, DEPLOY.encode_successful_state(self.HEAD)))
        self.assertEqual(storage, original)
        self.assertEqual(restore.writes, [DEPLOY.STATE_PATH, "index.html"])
        self.assertEqual(self.report["rollback"], "verified")
        self.assertNotIn("successful_release_commit", self.report)
        self.assertEqual((self.report_dir / "before" / DEPLOY.STATE_PATH).read_bytes(), old_state)
        self.verify.assert_called_once_with()

    def test_state_readback_mismatch_restores_source_and_old_state(self):
        self.prepare("index.html", b"old home", b"new home")
        old_state = DEPLOY.encode_successful_state(self.BASE)
        original = {"index.html": b"old home", DEPLOY.STATE_PATH: old_state}
        storage = original.copy()
        server = MemoryServer(storage, corrupt_path=DEPLOY.STATE_PATH)
        restore = MemoryServer(storage)
        with patch.object(DEPLOY, "Server", return_value=restore):
            with self.assertRaisesRegex(RuntimeError, "state readback differs"):
                DEPLOY.deploy_changes(server, ["index.html"], self.BASE, self.report,
                    state_update=(old_state, DEPLOY.encode_successful_state(self.HEAD)))
        self.assertEqual(storage, original)
        self.assertEqual(self.report["rollback"], "verified")

    def test_missing_state_establishes_verified_baseline_before_publication(self):
        storage = {}
        server = MemoryServer(storage)
        self.verify.side_effect = lambda: (
            self.assertNotIn(DEPLOY.STATE_PATH, storage) or self.live_verification
        )
        with patch.object(DEPLOY, "git", side_effect=self.git_for(self.HEAD, [])) as git_mock:
            with patch.object(DEPLOY, "baseline_preflight") as preflight:
                DEPLOY.run_deployment(server, {"files": {}}, self.report)
        preflight.assert_called_once_with(server, {"files": {}})
        self.verify.assert_called_once_with()
        self.assertEqual(server.writes, [DEPLOY.STATE_PATH])
        self.assertEqual(self.report["mode"], "live baseline import")
        self.assertEqual(self.report["successful_release_commit"], self.HEAD)
        self.assertFalse(any(call.args[0] == "diff" for call in git_mock.call_args_list))

    def test_marker_change_without_successful_baseline_is_refused(self):
        self.prepare("index.html", b"imported baseline", b"baseline with release marker")
        storage = {"index.html": b"imported baseline"}
        server = MemoryServer(storage)
        manifest = {"files": {"index.html": {
            "sha256": DEPLOY.digest(b"imported baseline"),
            "size": len(b"imported baseline"), "modify": "20261012000000",
        }}}
        with patch.object(DEPLOY, "git", side_effect=self.git_for(self.HEAD, [])):
            with self.assertRaisesRegex(RuntimeError, "Initial source differs"):
                DEPLOY.run_deployment(server, manifest, self.report)
        self.assertEqual(server.writes, [])
        self.assertNotIn(DEPLOY.STATE_PATH, storage)
        self.verify.assert_not_called()

    def test_state_sha_must_be_valid_and_available_commit_object(self):
        for value in ["HEAD", "0" * 40, "A" * 40, self.BASE + ":index.html"]:
            with self.subTest(value=value):
                storage = {DEPLOY.STATE_PATH: DEPLOY.json.dumps(
                    {"website": DEPLOY.DOMAIN, "commit": value}).encode()}
                with self.assertRaisesRegex(RuntimeError, "invalid commit"):
                    DEPLOY.read_successful_state(MemoryServer(storage))
        storage = {DEPLOY.STATE_PATH: DEPLOY.encode_successful_state(self.BASE)}
        with patch.object(DEPLOY, "git", side_effect=DEPLOY.subprocess.CalledProcessError(1, ["git", "cat-file"])):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                DEPLOY.read_successful_state(MemoryServer(storage))
        with patch.object(DEPLOY, "git", return_value=b"blob\n"):
            with self.assertRaisesRegex(RuntimeError, "Git commit"):
                DEPLOY.read_successful_state(MemoryServer(storage))


if __name__ == "__main__":
    unittest.main()
