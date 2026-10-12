"""Import only the source whose hashes were reviewed against a fresh snapshot."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from deploy_ftps import Server, safe

repo = Path.cwd().resolve()
manifest = json.loads(Path("deployment/live-baseline.json").read_text())
site = repo / "public_html"
site.mkdir(exist_ok=True)
server = Server()


def capture(item):
    relative, expected = item
    data = server.read(safe(relative))
    if data is None or len(data) != expected["size"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise RuntimeError("Live source drift; capture aborted: " + relative)
    target = site / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return relative


try:
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(capture, item) for item in manifest["files"].items()]
        for number, future in enumerate(as_completed(futures), 1):
            future.result()
            if number % 100 == 0 or number == len(futures):
                print(f"Verified source files: {number}/{len(futures)}", flush=True)
finally:
    server.close()

legacy = repo / "docs/legacy-workflows"
legacy.mkdir(parents=True, exist_ok=True)
for path in (repo / ".github/workflows").glob("*.yml"):
    if path.name not in {"deploy.yml", "validate.yml", "capture-live-baseline.yml"}:
        shutil.move(str(path), str(legacy / (path.name + ".txt")))
for name in ["index.html", "projects.html"]:
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
# The one-time importer cannot run after baseline merge.
Path(".github/workflows/capture-live-baseline.yml").unlink()
Path("scripts/capture_live.py").unlink()
print("Fresh live baseline complete and verified; ready for pull request.")
