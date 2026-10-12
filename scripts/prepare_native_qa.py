#!/usr/bin/env python3
"""Prepare a read-only, integrity-pinned dependency fixture for loopback browser QA."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

ORIGIN = "https://www.3dkanadvertising.store"
MIMES = {"image/svg+xml": {"image/svg+xml"}, "image/webp": {"image/webp"},
         "text/css": {"text/css"}, "javascript": {"text/javascript", "application/javascript"}}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Redirect refused for public QA dependency")


def safe_path(value):
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        raise ValueError("Invalid QA dependency path")
    if any(char in value for char in ("\\", ":", "?", "#", "%")):
        raise ValueError("Invalid QA dependency path")
    parts = value[1:].split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Invalid QA dependency path")
    return PurePosixPath(*parts)


def validate_entry(entry):
    relative = safe_path(entry.get("path"))
    if not isinstance(entry.get("bytes"), int) or not 0 < entry["bytes"] <= 2_000_000:
        raise ValueError("Invalid QA dependency byte limit")
    if not isinstance(entry.get("sha256"), str) or not re.fullmatch("[0-9a-f]{64}", entry["sha256"]):
        raise ValueError("Invalid QA dependency digest")
    if entry.get("mime") not in MIMES:
        raise ValueError("Invalid QA dependency MIME")
    source = entry.get("checkoutSource")
    if source is not None:
        if not isinstance(source, str) or source.startswith("/"):
            raise ValueError("Invalid QA checkout source")
        safe_path("/" + source)
    return relative


def verify_data(entry, data, mime=None):
    if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise RuntimeError("Dependency integrity failed: " + entry["path"])
    if mime is not None and mime.split(";", 1)[0].strip().lower() not in MIMES[entry["mime"]]:
        raise RuntimeError("Dependency MIME failed: " + entry["path"])
    if entry["mime"] == "image/webp" and (data[:4] != b"RIFF" or data[8:12] != b"WEBP"):
        raise RuntimeError("Dependency WebP signature failed: " + entry["path"])


def read_public(entry, opener):
    for attempt in range(3):
        try:
            request = Request(ORIGIN + entry["path"], headers={"User-Agent": "3DKan-Candidate-QA/1.0"})
            with opener.open(request, timeout=30) as response:
                if response.status != 200 or response.geturl() != ORIGIN + entry["path"]:
                    raise RuntimeError("Unexpected public QA response: " + entry["path"])
                data = response.read(entry["bytes"] + 1)
                mime = response.headers.get("Content-Type", "")
            verify_data(entry, data, mime)
            return data, mime
        except HTTPError as error:
            if error.code < 500 or attempt == 2:
                raise RuntimeError("Public QA HTTP failure: " + entry["path"]) from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("Public QA connection failure: " + entry["path"]) from None
        time.sleep(attempt + 1)


def prepare(root, manifest_file, output):
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1 or manifest.get("origin") != ORIGIN:
        raise ValueError("Invalid public QA manifest origin")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries or len(entries) > 50:
        raise ValueError("Invalid public QA manifest")
    paths = [validate_entry(entry) for entry in entries]
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate public QA dependency")
    root = root.resolve()
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    opener = build_opener(NoRedirect(), HTTPSHandler(context=context))
    records = []
    candidate_records = []
    fixture = output.parent / "fixture"
    output.parent.mkdir(parents=True, exist_ok=True)
    for entry, relative in zip(entries, paths):
        source = entry.get("checkoutSource")
        target = root.joinpath(*relative.parts)
        if source is not None:
            source_file = Path(source)
            if source_file.is_symlink() or not source_file.is_file():
                raise RuntimeError("Missing immutable QA checkout dependency: " + entry["path"])
            with source_file.open("rb") as stream:
                data = stream.read(entry["bytes"] + 1)
            verify_data(entry, data)
            mime, kind = entry["mime"], "reviewed Git checkout bytes"
        else:
            data, mime = read_public(entry, opener)
            kind = "public HTTPS GET (default verified TLS; redirects refused)"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        artifact_file = fixture.joinpath(*relative.parts)
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_bytes(data)
        records.append({"path": entry["path"], "source": kind, "status": 200 if source is None else None,
                        "mime": mime, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                        "obtainedAt": datetime.now(timezone.utc).isoformat()})
        output.write_text(json.dumps({"manifestObservation": manifest.get("observedAt"),
                          "provenance": manifest.get("provenance"), "records": records}, indent=2) + "\n", encoding="utf-8")
    # Derivatives are a separate reviewed inventory; original 17 inputs stay exact.
    derivative_manifest = json.loads(Path("tests/homepage-image-manifest.json").read_text(encoding="utf-8"))
    expected_derivatives = {
        "/assets/branding/logo-3dkan-688.webp",
        "/assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp",
        "/assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp",
    }
    derivative_entries = derivative_manifest.get("files")
    if (derivative_manifest.get("schemaVersion") != 1 or not isinstance(derivative_entries, list)
            or len(derivative_entries) != 3
            or {entry.get("path") for entry in derivative_entries} != expected_derivatives):
        raise ValueError("Invalid reviewed derivative inventory")
    for entry in derivative_entries:
        relative = validate_entry(entry)
        if entry.get("mime") != "image/webp" or entry.get("checkoutSource") != "public_html/" + str(relative):
            raise ValueError("Invalid reviewed derivative source")
        source_file = root.joinpath(*relative.parts)
        if source_file.is_symlink() or not source_file.is_file():
            raise RuntimeError("Missing reviewed derivative: " + entry["path"])
        with source_file.open("rb") as stream:
            data = stream.read(entry["bytes"] + 1)
        verify_data(entry, data, "image/webp")
    candidate_paths = ("index.html", "projects.html", "assets/ui/brief.js", "assets/ui/brief.css",
                       "assets/ui/frontend.js", "assets/ui/frontend.css", "assets/ui/theme.css",
                       "assets/branding/logo-3dkan-original.jpg",
                       "assets/branding/logo-3dkan-688.webp",
                       "assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp",
                       "assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp")
    for relative in candidate_paths:
        file = root / relative
        if file.is_symlink() or not file.is_file():
            raise RuntimeError("Missing reviewed QA candidate: " + relative)
        data = file.read_bytes()
        artifact_file = fixture / relative
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_bytes(data)
        candidate_records.append({"path": "/" + relative, "source": "reviewed Git candidate checkout",
                                  "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    output.write_text(json.dumps({"manifestObservation": manifest.get("observedAt"),
                      "provenance": manifest.get("provenance"), "records": records,
                      "candidateFiles": candidate_records}, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(records)} verified dependencies and {len(candidate_records)} reviewed candidate files for isolated loopback QA.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("public_html"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/native-dependencies.json"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/native-qa/dependencies.json"))
    args = parser.parse_args()
    prepare(args.root, args.manifest, args.out)
