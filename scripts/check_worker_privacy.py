#!/usr/bin/env python3
"""Read-only anonymous header checks; exit 0 verifies only the anonymous gate.

Run only after the approved Directory Privacy setup. No credentials are accepted,
response bodies are never read, and an Owner login still needs a manual check.
"""

from dataclasses import dataclass
import http.client
import json
import re
import sys
from urllib.error import URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPHandler, HTTPSHandler, OpenerDirector, Request


HOSTS = ("3dkanadvertising.store", "www.3dkanadvertising.store")
PATHS = (
    "/pekerja-web/",
    "/pekerja-web/index.html",
    "/pekerja-web/status.json",
    "/pekerja-web/dashboard.css",
    "/pekerja-web/dashboard.js",
)
REDIRECTS = frozenset((301, 302, 303, 307, 308))
MAX_REDIRECTS = 5


@dataclass(frozen=True)
class Headers:
    status: int
    location: str | None = None
    challenges: tuple[str, ...] = ()


def _opener():
    # Only HTTP(S) transport: no proxy environment, automatic redirect, cookie,
    # authentication handler, or error processor that could consume a body.
    opener = OpenerDirector()
    opener.add_handler(HTTPHandler())
    opener.add_handler(HTTPSHandler())
    return opener


def fetch_headers(url):
    request = Request(url, method="GET", headers={"Cache-Control": "no-cache"})
    response = _opener().open(request, timeout=10)
    try:
        locations = response.headers.get_all("Location", [])
        if len(locations) > 1:
            raise ValueError("ambiguous redirect")
        return Headers(
            status=response.status,
            location=locations[0] if locations else None,
            challenges=tuple(response.headers.get_all("WWW-Authenticate", [])),
        )
    finally:
        response.close()


def _has_basic(challenges):
    # Split only outside quoted strings, so a realm containing ', Basic' cannot
    # impersonate a second authentication scheme. Raw headers are never output.
    for header in challenges:
        start, quoted, escaped = 0, False, False
        for index, char in enumerate(header + ","):
            if escaped:
                escaped = False
            elif char == "\\" and quoted:
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif char == "," and not quoted:
                if re.match(r"^\s*Basic(?:\s|$)", header[start:index], re.I):
                    return True
                start = index + 1
    return False


def _redirect(current, location, path):
    if not location or any(char.isspace() for char in location):
        return None
    candidate = urljoin(current, location)
    parsed = urlsplit(candidate)
    try:
        safe = (
            parsed.scheme == "https"
            and parsed.hostname in HOSTS
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and parsed.path == path
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return None
    return candidate if safe else None


def _probe(host, path, scheme, protected, fetch):
    url = f"{scheme}://{host}{path}"
    seen = {url}
    status = None
    redirects = 0
    result = "request_failed"
    while True:
        try:
            response = fetch(url)
        except (URLError, OSError, http.client.HTTPException, ValueError):
            break
        status = response.status
        # The first protected HTTP response must redirect to HTTPS. In
        # particular, a direct HTTP Basic challenge fails before inspecting it.
        if protected and scheme == "http" and redirects == 0 and status not in REDIRECTS:
            result = "http_first_response_not_https_redirect"
            break
        if status in REDIRECTS:
            try:
                next_url = _redirect(url, response.location, path)
            except ValueError:
                next_url = None
            if next_url is None:
                result = "unsafe_redirect"
                break
            if next_url in seen:
                result = "redirect_loop"
                break
            if redirects >= MAX_REDIRECTS:
                result = "redirect_limit"
                break
            seen.add(next_url)
            url = next_url
            redirects += 1
            continue
        if protected:
            result = "401_basic" if status == 401 and _has_basic(response.challenges) else "anonymous_gate_failed"
        else:
            result = "public_200" if status == 200 else "homepage_not_public"
        break
    return {
        "host": host,
        "path": path,
        "status": status,
        "checks": {
            "protocol": scheme,
            "passed": result in ("401_basic", "public_200"),
            "result": result,
        },
    }


def check_privacy(fetch=fetch_headers):
    results = [
        _probe(host, path, scheme, True, fetch)
        for host in HOSTS
        for path in PATHS
        for scheme in ("https", "http")
    ]
    results.extend(_probe(host, "/", "https", False, fetch) for host in HOSTS)
    passed = all(result["checks"]["passed"] for result in results)
    return {
        "status": "anonymous_gate_verified" if passed else "blocked",
        "checks": {
            "anonymous_gate_verified": passed,
            "owner_login_verified": False,
            "manual_owner_login_required": True,
        },
        "results": results,
    }


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args:
        # No destination or credential flags: even error output stays structured.
        print(json.dumps({"status": "blocked", "checks": {"unsupported_arguments": True}}))
        return 2
    report = check_privacy()
    print(json.dumps(report, indent=2))
    return 0 if report["checks"]["anonymous_gate_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
