#!/usr/bin/env python3
"""Read only fixed public HTTPS HEAD metadata; never print cookie/error values."""
import argparse
import json
import os
from pathlib import Path
import ssl
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import (HTTPRedirectHandler, HTTPSHandler, ProxyHandler,
                            Request, build_opener)

ORIGIN = "https://www.3dkanadvertising.store"
POLICY = "public, max-age=300, must-revalidate"
TARGETS = (
    "/assets/ui/brief.js", "/assets/ui/brief.css",
    "/assets/ui/frontend.js", "/assets/ui/frontend.css", "/assets/ui/theme.css",
    "/assets/branding/logo-3dkan-original.jpg",
    "/assets/branding/logo-3dkan-688.webp",
    "/assets/portfolio-real/responsive/cimb-niaga-signage-atm-480.webp",
    "/assets/portfolio-real/responsive/cimb-niaga-signage-atm-768.webp",
)
CONTROLS = ("/", "/projects.html", "/layanan/neon-box",
            "/assets/portfolio-real/clean/cimb-niaga-signage-atm.webp")
MISSING = "/assets/ui/cache-header-missing.js"
ALLOWED = frozenset(TARGETS + CONTROLS + (MISSING,))
HEADER_FIELDS = {
    "cache_control": "Cache-Control", "content_type": "Content-Type",
    "etag": "ETag", "last_modified": "Last-Modified", "age": "Age",
    "date": "Date", "vary": "Vary",
}
CONDITIONAL_TARGETS = ("/assets/ui/frontend.js",
                       "/assets/branding/logo-3dkan-688.webp")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_opener():
    # No implicit proxy credentials, cookie jar, authentication or redirect.
    return build_opener(ProxyHandler({}), NoRedirect(),
                        HTTPSHandler(context=ssl.create_default_context()))


def snapshot(path, status, headers):
    result = {"path": path, "status": status}
    for key, name in HEADER_FIELDS.items():
        result[key] = headers.get_all(name) or []
    result["set_cookie"] = bool(headers.get_all("Set-Cookie"))
    server = headers.get("Server", "")
    result["server"] = "".join(char for char in server if 32 <= ord(char) < 127)[:256]
    return result


def safe_validator(value):
    return (isinstance(value, str) and 0 < len(value) <= 1024
            and all(ord(char) >= 32 and ord(char) != 127 for char in value))


def head(path, conditional=None, opener=None):
    if path not in ALLOWED:
        raise ValueError("path_not_allowed")
    headers = {"User-Agent": "3dkan-public-cache-header-probe/1",
               "Accept": "*/*"}
    if conditional:
        name, value = conditional
        if (name not in ("If-None-Match", "If-Modified-Since")
                or not safe_validator(value)):
            raise ValueError("invalid_validator")
        headers[name] = value
    request = Request(ORIGIN + path, method="HEAD", headers=headers)
    try:
        response = (opener or make_opener()).open(request, timeout=10)
        with response:
            return snapshot(path, response.status, response.headers)
    except HTTPError as error:
        try:
            return snapshot(path, error.code, error.headers)
        finally:
            error.close()
    except ssl.SSLError:
        return {"path": path, "status": None, "error": "tls_error"}
    except (TimeoutError, URLError, OSError):
        return {"path": path, "status": None, "error": "request_failed"}


def issue(path, category):
    return {"path": path, "category": category}


def policy_issues(row):
    path = row["path"]
    if row.get("status") not in (200, 206, 304):
        return [issue(path, row.get("error", "target_status"))]
    errors = []
    if row.get("cache_control") != [POLICY]:
        errors.append(issue(path, "target_policy"))
    if row.get("set_cookie"):
        errors.append(issue(path, "target_sets_cookie"))
    return errors


def compare_controls(observations, baseline):
    if (not isinstance(baseline, dict) or baseline.get("schema_version") != 1
            or baseline.get("origin") != ORIGIN):
        return [issue("/", "invalid_control_baseline")]
    prior_rows = baseline.get("observations")
    if not isinstance(prior_rows, list):
        return [issue("/", "invalid_control_baseline")]
    prior = {row.get("path"): row for row in prior_rows if isinstance(row, dict)}
    current = {row["path"]: row for row in observations}
    if not all(path in prior for path in CONTROLS):
        return [issue("/", "incomplete_control_baseline")]
    return [issue(path, "control_changed") for path in CONTROLS
            if (current[path].get("status"), current[path].get("cache_control"))
            != (prior[path].get("status"), prior[path].get("cache_control"))]


def run_probe(mode="observe", baseline=None, request=head):
    if mode not in ("observe", "enforce"):
        raise ValueError("invalid_mode")
    observations = [request(path) for path in TARGETS + CONTROLS + (MISSING,)]
    by_path = {row["path"]: row for row in observations}
    errors = [issue(row["path"], row["error"]) for row in observations
              if row.get("error")]
    for path in CONTROLS:
        if by_path[path].get("status") != 200 and not by_path[path].get("error"):
            errors.append(issue(path, "control_status"))
    if by_path[MISSING].get("status") != 404:
        errors.append(issue(MISSING, "missing_not_404"))
    if POLICY in by_path[MISSING].get("cache_control", []):
        errors.append(issue(MISSING, "missing_received_new_policy"))
    missing = [path for path in TARGETS if not by_path[path].get("cache_control")]
    if mode == "enforce":
        for path in TARGETS:
            errors.extend(policy_issues(by_path[path]))
    else:
        for path in TARGETS:
            if (by_path[path].get("status") != 200
                    and not by_path[path].get("error")):
                errors.append(issue(path, "target_status"))
    conditional = []
    for path in CONDITIONAL_TARGETS:
        row = by_path[path]
        selected = None
        for key, name in (("etag", "If-None-Match"),
                          ("last_modified", "If-Modified-Since")):
            values = row.get(key, [])
            if len(values) == 1 and safe_validator(values[0]):
                selected = (name, values[0])
                break
        if selected is None:
            conditional.append({"path": path, "status": None,
                                "category": "validator_not_advertised"})
            continue
        result = request(path, conditional=selected)
        conditional.append(result)
        if result.get("status") != 304:
            errors.append(issue(path, result.get("error", "conditional_not_304")))
        elif mode == "enforce":
            errors.extend(policy_issues(result))
    if baseline is not None:
        errors.extend(compare_controls(observations, baseline))
    return {"schema_version": 1, "origin": ORIGIN, "mode": mode,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "observations": observations, "conditional": conditional,
            "missing_cache_control": missing, "issues": errors,
            "limitations": ["HEAD does not prove body delivery or live 206.",
                            "No validator means conditional HEAD was not run."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("observe", "enforce"), default="observe")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path,
                        default=os.getenv("CACHE_HEADERS_RESULT_PATH"))
    args = parser.parse_args()
    try:
        baseline = json.loads(args.baseline.read_text("utf-8")) if args.baseline else None
        report = run_probe(args.mode, baseline)
    except Exception:
        report = {"schema_version": 1, "origin": ORIGIN,
                  "issues": [issue("/", "probe_setup_failed")]}
    rendered = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        try:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        except OSError:
            report["issues"].append(issue("/", "report_write_failed"))
            rendered = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    print(rendered, end="")
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
