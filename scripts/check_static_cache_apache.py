#!/usr/bin/env python3
"""Cloud-only integration of the exact scoped Header block on isolated Apache."""
import argparse
import grp
import hashlib
import http.client
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import subprocess
import tempfile
import time

POLICY = "public, max-age=300, must-revalidate"
BEGIN = "# BEGIN 3DKan scoped static cache"
END = "# END 3DKan scoped static cache"
SCOPE = r"^/assets/(ui/(brief|frontend)\.(js|css)|ui/theme\.css|branding/logo-3dkan-(original\.jpg|688\.webp)|portfolio-real/responsive/cimb-niaga-signage-atm-(480|768)\.webp)$"
STATUS = r"^(200|206|304)$"
EXPR = f"expr=%{{REQUEST_STATUS}} =~ m#{STATUS}# && %{{REQUEST_URI}} =~ m#{SCOPE}#"
BLOCK = "\n".join([BEGIN, "<IfModule mod_headers.c>",
    f'  Header onsuccess unset Cache-Control "{EXPR}"',
    f'  Header always set Cache-Control "{POLICY}" "{EXPR}"',
    "</IfModule>", END]) + "\n"
TARGETS = (
    "/assets/ui/brief.js", "/assets/ui/brief.css",
    "/assets/ui/frontend.js", "/assets/ui/frontend.css", "/assets/ui/theme.css",
    "/assets/branding/logo-3dkan-original.jpg", "/assets/branding/logo-3dkan-688.webp",
    "/assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp",
    "/assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp",
)
DYNAMIC = '<FilesMatch "\\.(?:html|php)$">\n  Header set Cache-Control "no-cache"\n</FilesMatch>\n'


def extract_block(candidate, base):
    """Fail closed on any existing-prefix or unapproved appended-byte change."""
    if len(base) != 2399 or hashlib.sha256(base).hexdigest() != "3ea113bad3488ffd60e5b760a9522166e6f0dbc3a1a19ef944c96c1549396b73":
        raise ValueError("Unexpected pinned base fixture")
    if candidate != base + b"\n" + BLOCK.encode("ascii"):
        raise ValueError("Candidate must equal the pinned prefix plus the exact append")
    text = candidate.decode("ascii")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("Ambiguous block markers")
    return BLOCK


def request(port, target, method="GET", headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, target, headers=headers or {})
        response = connection.getresponse()
        body = response.read(16384)
        return response.status, response.getheaders(), body
    finally:
        connection.close()


def values(headers, name):
    return [value for key, value in headers if key.lower() == name.lower()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default="public_html/.htaccess")
    parser.add_argument("--base", default="tests/fixtures/static_cache_htaccess_base.txt")
    parser.add_argument("--out", default="artifacts/cache-headers/apache-results.json")
    parser.add_argument("--apache", default=shutil.which("apache2") or shutil.which("httpd"))
    parser.add_argument("--module-dir", default="/usr/lib/apache2/modules")
    args = parser.parse_args()
    results, version, server = [], None, None
    stage = "pinned candidate"
    report = {"candidateSha": os.environ.get("QA_CANDIDATE_SHA") or os.environ.get("GITHUB_SHA", "UNKNOWN"), "results": results}
    def checked(name, condition):
        results.append({"name": name, "status": "PASS" if condition else "FAIL"})
    try:
        candidate = Path(args.candidate).read_bytes()
        block = extract_block(candidate, Path(args.base).read_bytes())
        report["htaccessSha256"] = hashlib.sha256(candidate).hexdigest()
        checked("Pinned prefix and exact scoped append", True)
        if not args.apache or os.getuid() == 0:
            raise RuntimeError("A non-root runner and installed Apache are required")
        raw_version = subprocess.run([args.apache, "-v"], capture_output=True, timeout=5, check=True)
        match = re.search(r"Apache/[0-9.]+", raw_version.stdout.decode("ascii", "ignore"))
        version = match.group(0) if match else "Apache version unavailable"
        runtime = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
        if not runtime.is_dir() or runtime.is_symlink():
            raise RuntimeError("RUNNER_TEMP must be an existing real directory")
        with tempfile.TemporaryDirectory(prefix="3dkan-cache-apache-", dir=runtime) as temp:
            work = Path(temp)
            docroot = work / "www"
            docroot.mkdir()
            negatives = ("/", "/index.html", "/dynamic.php", "/assets/other.js",
                "/assets/ui/theme.css.bak", "/assets/ui/frontend.jsX",
                "/assets/ui/briefx.js", "/assets/ui/BRIEF.js",
                "/assets/branding/logo-3dkan-689.webp",
                "/assets/portfolio-real/responsive/cimb-niaga-signage-atm-4800.webp",
                "/prefix/assets/ui/brief.js", "/assets/ui/foo/frontend.css")
            content = b"cloud-synthetic-static-content\n" * 64
            for target in TARGETS + negatives:
                if target == "/":
                    continue
                item = docroot / target.lstrip("/")
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_bytes(content)
            (docroot / "404.html").write_text("synthetic-internal-error-page", encoding="ascii")
            (docroot / ".htaccess").write_text(DYNAMIC + block, encoding="ascii")
            with socket.socket() as reserve:
                reserve.bind(("127.0.0.1", 0))
                port = reserve.getsockname()[1]
            modules = [("mpm_event", "mpm_event"), ("authz_core", "authz_core"),
                ("headers", "headers"), ("dir", "dir"), ("mime", "mime")]
            loads = []
            for name, file_name in modules:
                module = Path(args.module_dir) / ("mod_" + file_name + ".so")
                if not module.is_file():
                    raise RuntimeError("Required Apache module unavailable")
                loads.append(f'LoadModule {name}_module "{module}"')
            config = "\n".join([
                f'ServerRoot "{work}"', f'PidFile "{work / "httpd.pid"}"',
                f'DefaultRuntimeDir "{work}"', f'ErrorLog "{work / "error.log"}"',
                "LogLevel warn", "ServerName 127.0.0.1", f"Listen 127.0.0.1:{port}",
                *loads, f"User {pwd.getpwuid(os.getuid()).pw_name}",
                f"Group {grp.getgrgid(os.getgid()).gr_name}", f'DocumentRoot "{docroot}"',
                "DirectoryIndex index.html", "FileETag MTime Size",
                "TypesConfig /etc/mime.types", 'ErrorDocument 404 "/404.html"',
                "<Directory />", "Require all denied", "</Directory>",
                f'<Directory "{docroot}">', "Require all granted", "AllowOverride FileInfo",
                'Header onsuccess set Cache-Control "old-success"',
                'Header always set Cache-Control "old-always"', "</Directory>", "",
            ])
            config_path = work / "httpd.conf"
            config_path.write_text(config, encoding="ascii")
            stage = "Apache configuration"
            subprocess.run([args.apache, "-t", "-f", str(config_path)],
                capture_output=True, timeout=10, check=True)
            checked("Apache parses isolated configuration", True)
            stage = "Apache startup"
            server = subprocess.Popen([args.apache, "-f", str(config_path), "-DFOREGROUND"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 10
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Apache exited during startup")
                try:
                    request(port, "/index.html", "HEAD")
                    break
                except (OSError, http.client.HTTPException):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Apache did not become ready")
                    time.sleep(0.05)
            stage = "real response matrix"
            for target in TARGETS:
                for method, suffix in (("GET", ""), ("HEAD", ""), ("GET", "?v=synthetic")):
                    status, headers, _ = request(port, target + suffix, method)
                    checked(method + " " + target + suffix,
                        status == 200 and values(headers, "Cache-Control") == [POLICY])
            target = TARGETS[0]
            status, headers, body = request(port, target, headers={"Range": "bytes=0-9"})
            checked("Range GET 206 replaces both old header tables",
                status == 206 and len(body) == 10 and values(headers, "Cache-Control") == [POLICY])
            _, initial, _ = request(port, target)
            for method, header, response_header in (("GET", "If-None-Match", "ETag"), ("GET", "If-Modified-Since", "Last-Modified"), ("HEAD", "If-None-Match", "ETag")):
                validator = values(initial, response_header)
                if len(validator) != 1:
                    raise RuntimeError("Apache static validator unavailable")
                status, headers, _ = request(port, target, method, headers={header: validator[0]})
                checked(method + " " + header + " produces scoped 304",
                    status == 304 and values(headers, "Cache-Control") == [POLICY])
            for target in negatives:
                status, headers, _ = request(port, target)
                old_success = "no-cache" if target == "/" or target.endswith((".html", ".php")) else "old-success"
                checked("Negative scope " + target,
                    status == 200 and sorted(values(headers, "Cache-Control")) == sorted([old_success, "old-always"]))
            absent = docroot / TARGETS[0].lstrip("/")
            absent.unlink()
            try:
                for target in (TARGETS[0], "/assets/ui/missing.js"):
                    status, headers, body = request(port, target)
                    checked("404 internal ErrorDocument " + target,
                        status == 404 and POLICY not in values(headers, "Cache-Control")
                        and body == b"synthetic-internal-error-page")
            finally:
                absent.write_bytes(content)
            status, headers, _ = request(port, TARGETS[0], headers={"Range": "bytes=999999-"})
            checked("416 is not given the scoped policy",
                status == 416 and POLICY not in values(headers, "Cache-Control"))
            stage = "Apache cleanup"
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            server = None
    except Exception as error:
        results.append({"name": stage, "status": "FAIL", "detail": type(error).__name__})
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        report.update({"apacheVersion": version, "passed": sum(r["status"] == "PASS" for r in results),
            "failed": sum(r["status"] == "FAIL" for r in results),
            "limitations": ["Apache loopback fixture only; production rewrites are not executed.",
                "The .php negative fixture is static text, not a PHP runtime test."]})
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"passed": report["passed"], "failed": report["failed"],
            "apacheVersion": version, "failures": [r for r in results if r["status"] == "FAIL"]}))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
