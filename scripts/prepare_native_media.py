"""Copy only five hash-pinned MP4s from the immutable imported Git source."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts/native-qa/fixture"
EXPECTED = {
    "/assets/portfolio-real/videos/cimb-niaga-signage-atm.mp4",
    "/assets/portfolio-real/videos/gadget-solution-neonbox.mp4",
    "/assets/portfolio-real/videos/kementerian-pertanian-brmp.mp4",
    "/assets/portfolio-real/videos/pt-makassar-metro-network.mp4",
    "/assets/portfolio-real/videos/shop-sign-retail-neonbox.mp4",
}

def main():
    expected_commit = os.environ["QA_CANDIDATE_SHA"]
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if actual != expected_commit:
        raise ValueError("Media checkout is not pinned")
    manifest = json.loads((ROOT / "tests/native-media-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1 or manifest.get("origin") != "https://www.3dkanadvertising.store":
        raise ValueError("Media manifest schema/origin mismatch")
    entries = manifest["files"]
    if len(entries) != 5 or {entry["path"] for entry in entries} != EXPECTED:
        raise ValueError("Exactly five approved MP4 paths required")
    if FIXTURE.is_symlink() or not FIXTURE.is_dir():
        raise ValueError("Verified isolated fixture must exist first")
    for entry in entries:
        relative = entry["path"].lstrip("/")
        if entry["checkoutSource"] != "public_html/" + relative or entry["mime"] != "video/mp4":
            raise ValueError("Unexpected media source or MIME")
        source = ROOT / entry["checkoutSource"]
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(ROOT):
            raise ValueError("Unsafe immutable media source")
        data = source.read_bytes()
        git_blob = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        if not 0 < len(data) <= 64_000_000 or len(data) != entry["bytes"]:
            raise ValueError("Media size mismatch: " + relative)
        if data[4:8] != b"ftyp" or hashlib.sha256(data).hexdigest() != entry["sha256"] or git_blob != entry["gitBlob"]:
            raise ValueError("Media container or immutable digest mismatch: " + relative)
        target = FIXTURE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or not target.resolve().is_relative_to(FIXTURE):
            raise ValueError("Unsafe media fixture target")
        target.write_bytes(data)
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Copied media digest mismatch: " + relative)
    (FIXTURE.parent / "verified-media-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Five immutable MP4 fixtures size/Git-blob/SHA256/container PASS; no public download or production write.")

if __name__ == "__main__":
    main()
