"""Deploy reviewed site changes, fail on live drift, and restore on failure."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import quote
import urllib.request
import xml.etree.ElementTree as ET

SITE = Path("public_html")
DOMAIN = "https://www.3dkanadvertising.store"
REPORT = Path("deployment-result")
MANIFEST = Path("deployment/live-baseline.json")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def previous(base, path):
    result = subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True)
    return result.stdout if result.returncode == 0 else None


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

    def request(self, path="", extra=()):
        if path:
            safe(path)
        config = [
            "silent", "show-error", "ssl-reqd", "ipv4",
            "connect-timeout = 12", "max-time = 60",
            "retry = 2", "retry-delay = 1", "retry-max-time = 150",
            "user = " + self.quoted(self.user + ":" + self.password),
            "url = " + self.quoted("ftp://" + self.host + ":21/public_html/" + quote(path, safe="/")),
            *extra,
        ]
        result = subprocess.run(
            [self.curl, "-q", "--config", "-"],
            input=("\n".join(config) + "\n").encode(),
            capture_output=True, timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            error = result.stderr.decode("utf-8", "replace")
            for value in [self.user, self.password]:
                if value:
                    error = error.replace(value, "[REDACTED]")
            raise CurlError(result.returncode, error[:500])
        return result.stdout

    def read(self, path):
        try:
            return self.request(safe(path))
        except CurlError as error:
            if error.code not in (9, 78):
                raise
            parent = str(PurePosixPath(path).parent)
            entries = self.list("" if parent == "." else parent)
            if any(name == PurePosixPath(path).name for name, _ in entries):
                raise
            return None

    def write(self, path, data):
        with tempfile.TemporaryDirectory() as folder:
            local = Path(folder) / "payload"
            local.write_bytes(data)
            self.request(safe(path), ["ftp-create-dirs", "upload-file = " + self.quoted(local)])

    def delete_created(self, path):
        self.request("", ["list-only", "quote = " + self.quoted("DELE /public_html/" + safe(path))])

    def list(self, directory):
        path = safe(directory).rstrip("/") + "/" if directory else ""
        try:
            raw = self.request(path, ['request = "MLSD"']).decode("utf-8")
        except CurlError as error:
            if error.code in (9, 78):
                return []
            raise
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
    for path in ["/", "/about.html", "/contact.html",
                 "/toko/toko-1", "/toko/toko-2", "/toko/toko-3",
                 "/alat/hitung-karakter", "/panduan.html"]:
        html = https(path)
        if b"<html" not in html.lower():
            raise RuntimeError("A live page returned an unexpected body")
        if path == "/":
            local = (SITE / "index.html").read_bytes()
            marker = re.search(rb'<meta name="3dkan-release" content="([^"]+)">', local)
            live_marker = re.search(rb'<meta name="3dkan-release" content="([^"]+)">', html)
            if (marker.group(0) if marker else None) != (live_marker.group(0) if live_marker else None):
                raise RuntimeError("Live release metadata does not match the repository")
    return {"sitemaps": 11, "unique_urls": 500, "http_samples": 8}


def baseline_preflight(server, manifest):
    entries = manifest["files"]
    by_dir = {}
    for path, entry in entries.items():
        if digest((SITE / safe(path)).read_bytes()) != entry["sha256"]:
            raise RuntimeError("Initial source differs from the live snapshot: " + path)
        parent = str(PurePosixPath(path).parent)
        by_dir.setdefault("" if parent == "." else parent, []).append((path, entry))
    for directory, files in by_dir.items():
        remote = {name: facts for name, facts in server.list(directory)}
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


def deploy_changes(server, changes, base, report):
    prepared = []
    for path in changes:
        desired = (SITE / safe(path)).read_bytes()
        old = previous(base, "public_html/" + path)
        remote = server.read(path)
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
    try:
        for path, desired, remote in prepared:
            # Record before STOR, because failed transfers can still truncate.
            touched.append((path, remote))
            server.write(path, desired)
            if server.read(path) != desired:
                raise RuntimeError("FTPS readback differs after upload: " + path)
            report["uploaded"].append({"path": path, "sha256": digest(desired)})
        report["live"] = verify_live()
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
            report["rollback"] = "verified" if touched else "no files changed"
        except Exception:
            report["rollback"] = "failed; restore the saved before/ files"
            raise
        finally:
            restore.close()
        raise


def main():
    REPORT.mkdir(exist_ok=True)
    report = {"status": "started", "uploaded": [], "already_current": [], "rollback": "not needed"}
    server = None
    try:
        base = os.environ.get("BEFORE_SHA", "")
        if not re.fullmatch(r"[0-9a-f]{40}", base) or base == "0" * 40:
            base = git("rev-parse", "HEAD^").decode().strip()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        server = Server()
        if previous(base, ".site-source-ready") is None:
            baseline_preflight(server, manifest)
            report["mode"] = "live baseline import"
            report["live"] = verify_live()
        else:
            delta = git("diff", "--name-status", "--no-renames", "-z", base, "HEAD", "--", "public_html/")
            parts = delta.decode().split("\0")
            changes = []
            for offset in range(0, len(parts) - 1, 2):
                status, repo_path = parts[offset:offset + 2]
                if status == "D":
                    raise RuntimeError("Remote deletion requires a separate reviewed cleanup")
                changes.append(repo_path.removeprefix("public_html/"))
            report["mode"] = "reviewed source changes"
            deploy_changes(server, changes, base, report)
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
