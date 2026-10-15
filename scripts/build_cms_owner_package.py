"""Build only reviewed CMS Owner code into an isolated package; never deploy it."""
import argparse
import hashlib
import json
from pathlib import Path

SOURCES = {
    "cms/owner-request-guard.php": {
        "target": "includes/cms-owner/owner-request-guard.php",
        "sha256": "6f3522030e156cfdaa354e1d7bbd5d79ae199ca811ed207982e3afee7285e5ad"
    },
    "cms/neon_box_pilot.php": {
        "target": "includes/cms-owner/neon_box_pilot.php",
        "sha256": "15dbaf6bfe53ff5ea521d97e288788fb07f4c1e4a9f32e1ef1667d9bacad6ab2"
    },
    "cms/neon_box_draft_adapter.php": {
        "target": "includes/cms-owner/neon_box_draft_adapter.php",
        "sha256": "7a6a15bf0d3c87ab26be8fe396b8217f463d57b503d942f11c599bd797f1752b"
    },
    "cms/owner-gateway.php": {
        "target": "includes/cms-owner/owner-gateway.php",
        "sha256": "4905106fc54b1add90d831212619426463ee563309fdf141e1cef5ab0eddaa21"
    },
    "cms/owner-entry.php": {
        "target": "includes/cms-owner/owner-entry.php",
        "sha256": "fbf3f2a7485e645169d81b80c87a1e2c3950dfac087149e7c29be83bf181fbd7"
    },
    "cms/owner-index.php": {
        "target": "cms-owner/index.php",
        "sha256": "79b83d06476560eacb5bf1396dcb4832f3ae866617a371609f36b2df6932d284"
    },
    "cms/owner-endpoint.php": {
        "target": "cms-owner/endpoint.php",
        "sha256": "3503ab894a82248cce0649625afd59615abe09cb4daa3e79c858593cc87ff635"
    },
    "cms/owner-ui.html": {
        "target": "cms-owner/owner-ui.html",
        "sha256": "7b1311d722a41d13501b4433aaec8ec65886556a61e2696e1ecefb8b08006bd2"
    },
    "cms/owner-ui.css": {
        "target": "cms-owner/owner-ui.css",
        "sha256": "29537b40b240895527a37d5bff1390e3c4b4818e3a38b79dd62da75e54df7404"
    },
    "cms/owner-ui.js": {
        "target": "cms-owner/owner-ui.js",
        "sha256": "96e236f70dd4cbd43f133ba99411f93684fe560362ac9408210258fbf6b74c15"
    }
}
parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
out = args.output.absolute()
if out != out.resolve() or out == repo or repo in out.parents or out in repo.parents:
    raise SystemExit("Output must be a separate canonical package directory")
if out.exists() and (not out.is_dir() or any(out.iterdir())):
    raise SystemExit("Package destination must be empty")
for parent in [out, *out.parents]:
    if parent.is_symlink():
        raise SystemExit("Package destination is unsafe")
rule = "RewriteRule ^includes(?:/|$) - [F,L,NC]"
if rule not in (repo / "public_html/.htaccess").read_text():
    raise SystemExit("Existing library URL denial is missing")
out.mkdir(parents=True, exist_ok=True)
rows = []
for name, expected in SOURCES.items():
    source = repo / name
    if not source.is_file() or source.is_symlink():
        raise SystemExit("Unsafe package source")
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected["sha256"]:
        raise SystemExit("Package source identity mismatch")
    target = out / expected["target"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    target.chmod(0o644)
    if target.read_bytes() != payload:
        raise SystemExit("Package copy mismatch")
    rows.append({"source": name, "path": expected["target"], "bytes": len(payload), "sha256": expected["sha256"]})
actual = {file.relative_to(out).as_posix() for file in out.rglob("*") if file.is_file()}
if actual != {row["path"] for row in rows} or any(file.is_symlink() for file in out.rglob("*")):
    raise SystemExit("Unexpected package member")
manifest = {"schemaVersion": 1, "status": "code-package-only", "files": rows}
(out / "package-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"files": len(rows), "sourceIdentitiesVerified": True, "privateRuntimeFiles": 0, "deployed": False}))
