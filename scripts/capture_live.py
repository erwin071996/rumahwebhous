"""Recover the reviewed public source package, then verify it against live."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from deploy_ftps import Server, safe, baseline_preflight, verify_live

repo = Path.cwd().resolve()
site = repo / "public_html"
site.mkdir(exist_ok=True)
manifest = json.loads(Path("deployment/live-baseline.json").read_text())
package = json.loads(Path("deployment/bootstrap/manifest.json").read_text())
with tempfile.TemporaryDirectory() as folder:
    archive = Path(folder) / "reviewed-public-source.zip"
    with archive.open("wb") as assembled:
        for part in package["parts"]:
            path = repo / safe(part["path"])
            data = path.read_bytes()
            if len(data) != part["size"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise RuntimeError("Source package integrity failure")
            assembled.write(data)
    if archive.stat().st_size != package["archive_bytes"] or hashlib.sha256(archive.read_bytes()).hexdigest() != package["archive_sha256"]:
        raise RuntimeError("Complete source archive differs from the reviewed package")
    with zipfile.ZipFile(archive) as source:
        if len(source.namelist()) != len(manifest["files"]) or set(source.namelist()) != set(manifest["files"]):
            raise RuntimeError("Archive differs from the reviewed public allowlist")
        for relative, expected in manifest["files"].items():
            data = source.read(safe(relative))
            if len(data) != expected["size"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise RuntimeError("Reviewed source hash mismatch: " + relative)
            target = site / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

legacy = repo / "docs/legacy-workflows"
legacy.mkdir(parents=True, exist_ok=True)
for path in (repo / ".github/workflows").glob("*.yml"):
    if path.name not in {"deploy.yml", "validate.yml", "capture-live-baseline.yml"}:
        shutil.copy2(path, legacy / (path.name + ".txt"))
for name in ["index.html", "projects.html"]:
    if (repo / name).exists():
        (repo / name).unlink()
old_assets = (repo / "assets").resolve()
if old_assets.parent != repo or old_assets.name != "assets":
    raise RuntimeError("Unsafe source cleanup target")
if old_assets.exists():
    shutil.rmtree(old_assets)
Path(".site-source-ready").write_text(
    "Verified live source imported from Rumahweb on 2026-10-12; see deployment/live-baseline.json.\n")
subprocess.run(["python", "scripts/check_site.py"], check=True)
subprocess.run(["python", "-m", "unittest", "discover", "-s", "tests", "-v"], check=True)
server = Server()
try:
    baseline_preflight(server, manifest)
    print("Live verification:", verify_live(), flush=True)
finally:
    server.close()

bootstrap = (repo / "deployment/bootstrap").resolve()
if bootstrap.parent != repo / "deployment" or bootstrap.name != "bootstrap":
    raise RuntimeError("Unsafe package cleanup target")
shutil.rmtree(bootstrap)
print("Reviewed public source imported; live baseline confirmed without server writes.", flush=True)
