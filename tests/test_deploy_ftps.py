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


class DeployChangesTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
