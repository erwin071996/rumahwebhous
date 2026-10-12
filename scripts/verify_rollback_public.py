"""Read-only confirmation of the preserved rollback baseline."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

BASE = "f4966d1a0ff7e45090abd152a45a69daecf099c9"
FAILED_RELEASE = "f7a8e321b267f08a2216edc0e3f93d0a5460e3bd"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "rollback-public"
SPEC = importlib.util.spec_from_file_location("public_rollback_http", ROOT / "scripts/deploy_ftps.py")
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)

def main():
    report = {"status": "started", "mode": "rollback baseline public GET only",
              "expected_commit": BASE, "failed_release": FAILED_RELEASE,
              "pages": [], "form_data_sent": False, "whatsapp_navigation": False,
              "live_form_javascript": "NOT RUN"}
    try:
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            for relative in ("index.html", "projects.html", "includes/content-index.json"):
                data = subprocess.run(["git", "show", BASE + ":public_html/" + relative],
                                      check=True, capture_output=True).stdout
                target = site / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            DEPLOY.SITE = site
            for path, relative in (("/", "index.html"), ("/projects.html", "projects.html")):
                public = DEPLOY.https(path)
                if public != (site / relative).read_bytes():
                    raise RuntimeError("Public page differs from preserved baseline: " + relative)
                report["pages"].append({"path": path, "bytes": len(public),
                                        "sha256": hashlib.sha256(public).hexdigest(),
                                        "identity": "PASS",
                                        "whatsapp_link_present": b"https://wa.me/6285340382029" in public,
                                        "phone_link_present": b"tel:+6285340382029" in public})
            report["live"] = DEPLOY.verify_live()
            report["status"] = "success"
    except Exception:
        report["status"] = "failed"
        report["error"] = "Read-only public baseline verification failed; no website changes attempted"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "success" else 1

if __name__ == "__main__":
    raise SystemExit(main())
