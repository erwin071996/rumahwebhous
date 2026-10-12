"""Capture the reviewed allowlist with reused encrypted FTPS connections."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from urllib.parse import quote
from deploy_ftps import Server, safe

repo = Path.cwd().resolve()
manifest = json.loads(Path("deployment/live-baseline.json").read_text())
site = repo / "public_html"
site.mkdir(exist_ok=True)
server = Server()

probe = server.read("index.html")
expected_probe = manifest["files"]["index.html"]
if probe is None or hashlib.sha256(probe).hexdigest() != expected_probe["sha256"]:
    raise RuntimeError("FTPS probe differs from the reviewed live website; no import performed")
print("Verified FTPS target and current homepage before capture.", flush=True)

items = sorted(manifest["files"].items())
try:
    for offset in range(0, len(items), 200):
        batch = items[offset:offset + 200]
        config = [
            "silent", "show-error", "ssl-reqd", "ipv4",
            "tlsv1.2", 'tls-max = "1.2"', 'ftp-method = "singlecwd"',
            "parallel", "parallel-max = 4", "fail-early",
            "connect-timeout = 12", "max-time = 60",
            "retry = 2", "retry-delay = 1", "retry-max-time = 150",
            "user = " + server.quoted(server.user + ":" + server.password),
        ]
        for relative, expected in batch:
            safe(relative)
            target = site / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            config.extend([
                "url = " + server.quoted("ftp://" + server.host + ":21/public_html/" + quote(relative, safe="/")),
                "output = " + server.quoted(target),
            ])
        result = subprocess.run(
            [server.curl, "-q", "--config", "-"], input=("\n".join(config) + "\n").encode(),
            capture_output=True, timeout=900)
        if result.returncode:
            error = result.stderr.decode("utf-8", "replace")
            error = error.replace(server.user, "[REDACTED]").replace(server.password, "[REDACTED]")
            raise RuntimeError("FTPS capture batch failed: " + error[:600])
        for relative, expected in batch:
            target = site / relative
            data = target.read_bytes()
            if len(data) != expected["size"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise RuntimeError("Live source drift; capture aborted: " + relative)
        print(f"Verified source files: {min(offset + len(batch), len(items))}/{len(items)}", flush=True)
finally:
    server.close()

if {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()} != set(manifest["files"]):
    raise RuntimeError("Captured file set differs from the reviewed allowlist")

legacy = repo / "docs/legacy-workflows"
legacy.mkdir(parents=True, exist_ok=True)
for path in (repo / ".github/workflows").glob("*.yml"):
    if path.name not in {"deploy.yml", "validate.yml", "capture-live-baseline.yml"}:
        # Workflow cleanup is performed later by the authenticated connector.
        shutil.copy2(path, legacy / (path.name + ".txt"))
for name in ["index.html", "projects.html"]:
    if (repo / name).exists():
        (repo / name).unlink()
old_assets = (repo / "assets").resolve()
if old_assets.parent != repo or old_assets.name != "assets":
    raise RuntimeError("Unsafe cleanup target")
if old_assets.exists():
    shutil.rmtree(old_assets)
Path(".site-source-ready").write_text(
    "Verified live source imported from Rumahweb on 2026-10-12; see deployment/live-baseline.json.\n")
subprocess.run(["python", "scripts/check_site.py"], check=True)
subprocess.run(["python", "-m", "unittest", "discover", "-s", "tests", "-v"], check=True)
print("Fresh live baseline complete and verified; ready for pull request.")
