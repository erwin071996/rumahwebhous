"""Deploy reviewed site changes, fail on live drift, and restore on failure."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import unittest
import tempfile
import time
from urllib.parse import quote
import urllib.request
import xml.etree.ElementTree as ET

SITE = Path("public_html")
DOMAIN = "https://www.3dkanadvertising.store"
REPORT = Path("deployment-result")
MANIFEST = Path("deployment/live-baseline.json")
# Server-owned state lives under the directory already denied by .htaccess.
# It must never be imported into the public source or inferred from push events.
STATE_PATH = "includes/.3dkan-deployment-state.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def previous(base, path):
    result = subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True)
    return result.stdout if result.returncode == 0 else None


def checked_commit(value):
    if (not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value)
            or value == "0" * 40):
        raise RuntimeError("Successful release state has an invalid commit")
    try:
        kind = git("cat-file", "-t", value).decode().strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Successful release commit is unavailable in this checkout") from exc
    if kind != "commit":
        raise RuntimeError("Successful release state does not identify a Git commit")
    return value


def read_successful_state(server):
    raw = server.read(STATE_PATH)
    if raw is None:
        return None, None
    try:
        state = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("Successful release state is invalid; review before deploying") from exc
    if (not isinstance(state, dict) or set(state) != {"website", "commit"}
            or state.get("website") != DOMAIN):
        raise RuntimeError("Successful release state identifies an unexpected website")
    return checked_commit(state.get("commit")), raw


def encode_successful_state(commit):
    return (json.dumps({"website": DOMAIN, "commit": commit}, sort_keys=True) + "\n").encode()


def planned_changes(base, head):
    # A failed commit can be part of HEAD history without ever reaching the
    # server. Compare the whole pending source with the last verified success.
    delta = git("diff", "--name-status", "--no-renames", "-z", base, head,
                "--", "public_html/")
    parts = delta.decode().split("\0")
    changes = []
    for offset in range(0, len(parts) - 1, 2):
        status, repo_path = parts[offset:offset + 2]
        if status == "D":
            raise RuntimeError("Remote deletion requires a separate reviewed cleanup")
        if status not in {"A", "M"} or not repo_path.startswith("public_html/"):
            raise RuntimeError("Unexpected source change requires separate review")
        path = safe(repo_path.removeprefix("public_html/"))
        if path == STATE_PATH:
            raise RuntimeError("Successful release state must remain server-owned")
        changes.append(path)
    return changes


def safe(path):
    if "\\" in path or any(c in path for c in "\r\n\0:"):
        raise ValueError("Unsafe deployment path")
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or ".." in parts or "." in parts:
        raise ValueError("Unsafe deployment path")
    return path


class CurlError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


RECOVERABLE_PUBLIC_PATHS = frozenset({
    "assets/branding/logo-3dkan-688.webp", "assets/branding/logo-3dkan-original.jpg",
    "assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp",
    "assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp",
    "assets/ui/brief.css", "assets/ui/brief.js", "assets/ui/frontend.css",
    "assets/ui/frontend.js", "assets/ui/theme.css", "index.html", "projects.html",
})


def is_recoverable_public_path(path):
    if not isinstance(path, str) or path == STATE_PATH:
        return False
    try:
        return safe(path) == path and path in RECOVERABLE_PUBLIC_PATHS
    except ValueError:
        return False


def is_stor_response_timeout(error):
    """Only the observed natural curl response-timeout diagnostic is eligible."""
    return (isinstance(error, CurlError) and error.code == 28 and
            re.fullmatch(r"curl: \(28\) FTP response timeout(?:\ncurl: \(28\) FTP response timeout){0,2}\n?",
                         str(error)) is not None)


class Server:
    """Strict FTPS using the transport verified by the read-only snapshot."""
    def __init__(self):
        self.host = os.environ["FTP_SERVER"]
        if self.host != "kilimanjaro.iixcp.rumahweb.net":
            raise ValueError("Unexpected Rumahweb host; review the configured target")
        self.user = os.environ["FTP_USERNAME"]
        self.password = os.environ["FTP_PASSWORD"]
        self.curl = (str(Path(os.environ["SystemRoot"]) / "System32/curl.exe")
                     if os.name == "nt" else shutil.which("curl"))
        if not self.curl:
            raise RuntimeError("curl is required for verified FTPS transfers")

    @staticmethod
    def quoted(value):
        return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'

    def trace(self, operation, path=""):
        if operation not in {"read", "list", "write", "delete"}:
            raise ValueError("Unexpected FTPS operation")
        display = safe(path) if path else "[site root]"
        if path == STATE_PATH:
            display = "release-state"
        message = f"FTPS {operation}: {display}"
        for value in (getattr(self, "user", ""), getattr(self, "password", "")):
            if value:
                message = message.replace(value, "[REDACTED]")
        print(json.dumps(message, ensure_ascii=True)[1:-1], flush=True)

    def request(self, path="", extra=()):
        if path:
            safe(path)
        config = [
            "silent", "show-error", "ssl-reqd", "ipv4",
            "tlsv1.2", 'tls-max = "1.2"', 'ftp-method = "singlecwd"',
            "connect-timeout = 12", "max-time = 60",
            "retry = 2", "retry-delay = 1", "retry-max-time = 150",
            "user = " + self.quoted(self.user + ":" + self.password),
            "url = " + self.quoted("ftp://" + self.host + ":21/public_html/" + quote(path, safe="/")),
            *extra,
        ]
        # Three 60-second attempts plus two one-second retry delays can
        # reach 182 seconds. Keep startup margin outside that curl window.
        try:
            result = subprocess.run(
                [self.curl, "-q", "--config", "-"],
                input=("\n".join(config) + "\n").encode(),
                capture_output=True, timeout=210,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            # Never expose TimeoutExpired's command, input or captured streams.
            raise CurlError(28, "FTPS curl exceeded the 210-second subprocess deadline") from None
        if result.returncode:
            error = result.stderr.decode("utf-8", "replace")
            for value in [self.user, self.password]:
                if value:
                    error = error.replace(value, "[REDACTED]")
            raise CurlError(result.returncode, error[:500])
        return result.stdout

    def read_many(self, paths):
        """Read known existing before-images in serial curl batches; never write."""
        paths = list(paths)
        if len(paths) != len(set(paths)):
            raise ValueError("Duplicate before-image path")
        for path in paths:
            safe(path)
            if path == STATE_PATH:
                raise ValueError("Release state must use its individual read guard")
        if not paths:
            return {}
        # Custom request/read adapters retain their existing virtual dispatch.
        # Only this strict curl backend can safely reuse its control connection.
        if type(self).read is not Server.read or type(self).request is not Server.request:
            return {path: self.read(path) for path in paths}
        captured = {}
        for start in range(0, len(paths), 20):
            batch = paths[start:start + 20]
            with tempfile.TemporaryDirectory(prefix="3dkan-before-images-") as folder:
                outputs = [Path(folder) / f"{index:02d}.bin" for index in range(len(batch))]
                config = [
                    "silent", "show-error", "ssl-reqd", "ipv4", "fail-early",
                    "tlsv1.2", 'tls-max = "1.2"', 'ftp-method = "singlecwd"',
                    "connect-timeout = 12", "max-time = 60",
                    "retry = 2", "retry-delay = 1", "retry-max-time = 150",
                    "user = " + self.quoted(self.user + ":" + self.password),
                    "write-out = " + self.quoted("%{exitcode}\\n"),
                ]
                for path, output in zip(batch, outputs):
                    self.trace("read", path)
                    config += [
                        "url = " + self.quoted("ftp://" + self.host + ":21/public_html/" + quote(path, safe="/")),
                        "output = " + self.quoted(output),
                    ]
                # Repeated URL/output options are sequential in one process.
                # Existing per-transfer retry limits remain; a batch is bounded.
                deadline = min(210 * len(batch), 900)
                try:
                    result = subprocess.run(
                        [self.curl, "-q", "--config", "-"],
                        input=("\n".join(config) + "\n").encode(),
                        capture_output=True, timeout=deadline,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except subprocess.TimeoutExpired:
                    raise CurlError(28, f"FTPS before-image batch exceeded the {deadline}-second subprocess deadline") from None
                if result.returncode:
                    # Server-controlled stderr may contain credentials or data.
                    # Keep it captured, but never include any excerpt in reports.
                    raise CurlError(result.returncode, "FTPS before-image read batch failed")
                receipts = result.stdout.splitlines()
                if len(receipts) != len(batch) or any(code != b"0" for code in receipts):
                    raise RuntimeError("FTPS before-image transfer receipt differs")
                for path, output in zip(batch, outputs):
                    if output.is_symlink() or not output.is_file():
                        raise RuntimeError("FTPS before-image batch output missing")
                    captured[path] = output.read_bytes()
            print(f"FTPS before-image batch verified: {len(batch)} existing files", flush=True)
        return captured

    def read(self, path):
        self.trace("read", path)
        try:
            return self.request(safe(path))
        except CurlError as error:
            if error.code not in {9, 78}:
                raise
            if not self.confirmed_absent(path):
                raise
            return None

    def confirmed_absent(self, path):
        """Confirm absence from a successful parent or ancestor listing."""
        safe(path)
        parent = str(PurePosixPath(path).parent)
        parent = "" if parent == "." else parent
        try:
            entries = self.list(parent)
        except CurlError as error:
            # Only a confirmed missing ancestor permits creating a new path.
            # Denied listings and an inaccessible existing directory propagate.
            if error.code in {9, 78} and parent and self.confirmed_absent(parent):
                return True
            raise
        return not any(name == PurePosixPath(path).name for name, _ in entries)

    def write(self, path, data):
        self.trace("write", path)
        with tempfile.TemporaryDirectory() as folder:
            local = Path(folder) / "payload"
            local.write_bytes(data)
            self.request(safe(path), ["ftp-create-dirs", "upload-file = " + self.quoted(local)])

    def delete_created(self, path):
        self.trace("delete", path)
        self.request("", ["list-only", "quote = " + self.quoted("DELE /public_html/" + safe(path))])

    def list(self, directory):
        self.trace("list", directory)
        path = safe(directory).rstrip("/") + "/" if directory else ""
        raw = self.request(path, ['request = "MLSD"']).decode("utf-8")
        entries = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            facts, separator, name = line.partition(" ")
            if not separator or "=" not in facts:
                raise RuntimeError("Invalid remote MLSD response")
            values = dict(pair.split("=", 1) for pair in facts.rstrip(";").split(";") if "=" in pair)
            if values.get("type") not in ("cdir", "pdir") and name not in (".", ".."):
                entries.append((name, values))
        return entries

    def close(self):
        self.password = ""
        self.user = ""


def https(path):
    url = DOMAIN + path
    url += ("&" if "?" in url else "?") + "deployment_check=" + os.environ.get("GITHUB_SHA", "local")
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={
                "Cache-Control": "no-cache", "Connection": "close",
                "User-Agent": "3DKan-Deployment-Verification",
            })
            with urllib.request.urlopen(request, timeout=35) as response:
                if response.status != 200:
                    raise RuntimeError("Unexpected HTTP status")
                return response.read()
        except (OSError, ValueError) as exc:
            last = exc
            time.sleep(attempt + 1)
    raise RuntimeError("Live HTTP verification failed") from last


def verify_live():
    # Static index and all child sitemaps are also generated by sitemap.php.
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    index = ET.fromstring(https("/sitemap.xml"))
    children = [el.text for el in index.findall("s:sitemap/s:loc", ns)]
    if len(children) != 10:
        raise RuntimeError("Live sitemap index does not contain 10 groups")
    found = []
    for url in children:
        if not url.startswith(DOMAIN + "/sitemap-"):
            raise RuntimeError("Unexpected live sitemap target")
        root = ET.fromstring(https(url.removeprefix(DOMAIN)))
        found.extend(el.text for el in root.findall("s:url/s:loc", ns))
    registry = json.loads((SITE / "includes/content-index.json").read_text(encoding="utf-8"))
    expected = {DOMAIN + row["path"] for rows in registry["groups"].values() for row in rows}
    if len(found) != 500 or set(found) != expected:
        raise RuntimeError("Live sitemap URLs differ from the reviewed 500-page source")
    for path in ["/", "/projects.html", "/about.html", "/contact.html",
                 "/toko/toko-1", "/toko/toko-2", "/toko/toko-3",
                 "/alat/hitung-karakter", "/panduan.html"]:
        html = https(path)
        if b"<html" not in html.lower():
            raise RuntimeError("A live page returned an unexpected body")
        if path in {"/", "/projects.html"}:
            local_path = "index.html" if path == "/" else "projects.html"
            if html != (SITE / local_path).read_bytes():
                raise RuntimeError("Live static page differs from the reviewed source: " + local_path)
    samples = 9
    service_check = None
    data = json.loads((SITE / "includes/refresh-data.json").read_text(encoding="utf-8"))
    record = data["services"]["neon-box"]
    if any(key in record for key in ("seo_title", "seo_description", "detail_heading", "detail_sections")):
        try:
            from scripts.service_content_check import verify_service_content
        except ModuleNotFoundError as error:
            if error.name != "scripts":
                raise
            from service_content_check import verify_service_content
        service_check = verify_service_content(https("/layanan/neon-box"), record,
                                               domain=DOMAIN, slug="neon-box")
        samples += 1
    result = {"sitemaps": 11, "unique_urls": 500, "http_samples": samples}
    if service_check is not None:
        result["service_content"] = service_check
    return result


def baseline_preflight(server, manifest):
    entries = manifest["files"]
    local_paths = {path.relative_to(SITE).as_posix() for path in SITE.rglob("*") if path.is_file()}
    if local_paths != set(entries):
        raise RuntimeError("Initial source file set differs from the reviewed live manifest")
    by_dir = {}
    for path, entry in entries.items():
        if digest((SITE / safe(path)).read_bytes()) != entry["sha256"]:
            raise RuntimeError("Initial source differs from the live snapshot: " + path)
        parent = str(PurePosixPath(path).parent)
        by_dir.setdefault("" if parent == "." else parent, []).append((path, entry))
    print(f"Checking {len(by_dir)} baseline folders with four parallel read-only connections...", flush=True)
    # Curl creates an independent verified-TLS subprocess for each request.
    # Collect every listing before any state publication can be considered.
    with ThreadPoolExecutor(max_workers=4) as pool:
        listings = dict(zip(by_dir, pool.map(server.list, by_dir)))
    for directory, files in by_dir.items():
        remote = {name: facts for name, facts in listings[directory]}
        for path, entry in files:
            facts = remote.get(PurePosixPath(path).name, {})
            if (facts.get("type") != "file" or
                    int(facts.get("size", -1)) != entry["size"] or
                    facts.get("modify") != entry["modify"]):
                raise RuntimeError("Live source changed after snapshot; recapture before deploying: " + path)
    # Byte-level checks for routing, registry, shared content and current pages.
    critical = [".htaccess", "index.html", "projects.html", "about.html", "contact.html",
                "content.php", "sitemap.php", "includes/content-index.json",
                "includes/refresh-header.html", "includes/refresh-footer.html"]
    for path in critical:
        if path in entries:
            data = server.read(path)
            if data is None or digest(data) != entries[path]["sha256"]:
                raise RuntimeError("Critical live source drift: " + path)
    print(f"Baseline preflight passed for {len(entries)} files; no upload required.")


def deploy_changes(server, changes, base, report, *, state_update=None,
                   allow_uncertain_public_stor=False):
    # state_update is supplied by run_deployment after validating the remote
    # successful commit; direct transaction tests may omit state publication.
    if state_update is not None:
        old_state, desired_state = state_update
        if server.read(STATE_PATH) != old_state:
            raise RuntimeError("Successful release state changed; refusing to deploy")
        if old_state is not None:
            backup = REPORT / "before" / STATE_PATH
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(old_state)
    old_by_path = {path: previous(base, "public_html/" + safe(path)) for path in changes}
    known_paths = [path for path in changes if old_by_path[path] is not None]
    reader = getattr(server, "read_many", None)
    before_images = reader(known_paths) if callable(reader) else {}
    if callable(reader) and set(before_images) != set(known_paths):
        raise RuntimeError("FTPS before-image batch inventory differs")
    prepared = []
    for path in changes:
        desired = (SITE / safe(path)).read_bytes()
        old = old_by_path[path]
        remote = before_images[path] if path in before_images else server.read(path)
        if remote == desired:
            report["already_current"].append(path)
            continue
        if remote != old:
            raise RuntimeError("Live file drift; refusing to overwrite: " + path)
        prepared.append((path, desired, remote))
        if remote is not None:
            backup = REPORT / "before" / path
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(remote)
    touched = []
    rollback_plan = None
    if state_update is not None:
        rollback_plan = {
            "files": [{"path": path, "before_existed": remote is not None,
                       "before_sha256": digest(remote) if remote is not None else None}
                      for path, _, remote in prepared],
            "state": {"path": STATE_PATH, "before_existed": old_state is not None,
                      "before_commit": json.loads(old_state)["commit"] if old_state is not None else None,
                      "target_commit": json.loads(desired_state)["commit"]},
            "touched_paths": [],
        }

    def save_rollback_plan():
        if rollback_plan is not None:
            REPORT.mkdir(parents=True, exist_ok=True)
            rollback_plan["touched_paths"] = [path for path, _ in touched]
            (REPORT / "rollback-plan.json").write_text(
                json.dumps(rollback_plan, indent=2) + "\n", encoding="utf-8")

    save_rollback_plan()
    try:
        for path, desired, remote in prepared:
            # Record before STOR, because failed transfers can still truncate.
            touched.append((path, remote))
            save_rollback_plan()
            try:
                server.write(path, desired)
            except CurlError as error:
                if (not allow_uncertain_public_stor or path == STATE_PATH or
                        not is_recoverable_public_path(path) or
                        not is_stor_response_timeout(error)):
                    raise
                # Recovery adds only a fresh RETR, never another upload invocation.
                try:
                    matches = server.read(path) == desired
                except Exception:
                    matches = False
                if not matches:
                    raise error from None
                report.setdefault("recovered_stor_response_timeouts", []).append(
                    {"path": path, "sha256": digest(desired)})
            if server.read(path) != desired:
                raise RuntimeError("FTPS readback differs after upload: " + path)
            report["uploaded"].append({"path": path, "sha256": digest(desired)})
        report["live"] = verify_live()
        # Publish success only after both FTPS readback and the HTTP checks.
        # Failed/truncated state writes are included in the same rollback.
        if state_update is not None:
            if old_state != desired_state:
                touched.append((STATE_PATH, old_state))
                save_rollback_plan()
                server.write(STATE_PATH, desired_state)
                if server.read(STATE_PATH) != desired_state:
                    raise RuntimeError("Successful release state readback differs")
            report["successful_release_commit"] = json.loads(desired_state)["commit"]
    except Exception:
        if not touched:
            report["rollback"] = "no files changed"
            raise
        report["rollback"] = "failed; restore the saved before/ files"
        server.close()
        restore = Server()
        try:
            for path, old in reversed(touched):
                if old is None:
                    if restore.read(path) is not None:
                        restore.delete_created(path)
                    if restore.read(path) is not None:
                        raise RuntimeError("New file rollback could not be verified: " + path)
                else:
                    restore.write(path, old)
                    if restore.read(path) != old:
                        raise RuntimeError("Rollback readback differs: " + path)
            if state_update is not None and restore.read(STATE_PATH) != old_state:
                raise RuntimeError("Previous successful release state could not be verified")
            report["rollback"] = "verified" if touched else "no files changed"
        except Exception:
            report["rollback"] = "failed; restore the saved before/ files"
            raise
        finally:
            restore.close()
        raise


def run_deployment(server, manifest, report):
    head = checked_commit(git("rev-parse", "HEAD").decode().strip())
    base, old_state = read_successful_state(server)
    report["head_commit"] = head
    report["previous_successful_commit"] = base
    report["successful_state_path"] = STATE_PATH
    report["successful_state_existed_before"] = old_state is not None
    desired_state = encode_successful_state(head)
    if base is None:
        # No successful state exists: establish the exact imported baseline.
        # A metadata/source change already applied locally fails this preflight.
        baseline_preflight(server, manifest)
        report["mode"] = "live baseline import"
        changes = []
    else:
        try:
            git("merge-base", "--is-ancestor", base, head)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("Successful live commit is not an ancestor of this checkout; review before deploying") from exc
        report["mode"] = "reviewed source changes"
        changes = planned_changes(base, head)
    deploy_changes(server, changes, base, report,
                   state_update=(old_state, desired_state),
                   allow_uncertain_public_stor=True)


def require_local_checks():
    """Do not construct a credential-bearing transport until checks pass."""
    repo = Path(__file__).resolve().parents[1]
    suite = unittest.TestLoader().discover(str(repo / "tests"))
    if suite.countTestCases() == 0:
        raise RuntimeError("Deployment requires a nonempty unittest suite")
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise RuntimeError("Deployment unit tests failed")
    subprocess.run([sys.executable, str(repo / "scripts/check_site.py"),
                    "--repo-root", str(repo)], cwd=repo, check=True)


def main():
    REPORT.mkdir(exist_ok=True)
    report = {"status": "started", "uploaded": [], "already_current": [], "rollback": "not needed"}
    server = None
    try:
        require_local_checks()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        server = Server()
        run_deployment(server, manifest, report)
        report["status"] = "success"
        print(json.dumps(report, indent=2))
    except Exception as exc:
        report["status"] = "failed"
        # Exception strings from FTP can include server-controlled data; keep
        # credentials out of reports even if a server unexpectedly echoes them.
        message = str(exc)
        for key in ["FTP_PASSWORD", "FTP_USERNAME"]:
            value = os.environ.get(key, "")
            if value:
                message = message.replace(value, "[REDACTED]")
        report["error"] = message
        print(json.dumps(report, indent=2))
        raise SystemExit(1)
    finally:
        if server:
            server.close()
        (REPORT / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
