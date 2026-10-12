#!/usr/bin/env python3
"""Validate the imported production source before any Rumahweb upload."""

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


DOMAIN = "https://www.3dkanadvertising.store"
EXPECTED_GROUPS = {
    "utama": 8,
    "layanan": 7,
    "wilayah": 24,
    "produk": 9,
    "panduan": 12,
    "tutorial": 400,
    "topik": 20,
    "alat": 14,
    "toko": 3,
    "informasi": 3,
}
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
FORBIDDEN_NAMES = {
    ".git", ".github", "node_modules", "__pycache__", ".netrc",
    "wp-config.php", "configuration.php", "error_log", "ftps.json",
    "ftps.pass", "credentials.json", "credentials.php",
    ".3dkan-deployment-state.json", ".htpasswd", ".htdigest",
}
FORBIDDEN_SUFFIXES = (
    ".log", ".sql", ".sql.gz", ".zip", ".tar", ".tar.gz", ".bak",
    ".pem", ".key", ".p12", ".pfx", ".pyc",
)
SECRET_PATTERN = re.compile(
    rb"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    # Require whole tokens: public image names containing "desk-..." must not
    # be interpreted as an OpenAI key beginning at the last two letters.
    rb"(?<![A-Za-z0-9_-])(?:"
    rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|"
    rb"sk-(?:proj-)?[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16}"
    rb")(?![A-Za-z0-9_-]))"
)


PUBLIC_TEXT_SUFFIXES = {".php", ".json", ".js", ".html", ".txt", ".xml", ".css", ".svg"}
CREDENTIAL_KEY = (
    rb"(?:password|passwd|pwd|pass|token|secret|"
    rb"(?:db|database|mysql|ftp|smtp)[_-]?(?:password|passwd|pwd|pass)|"
    rb"api[_-]?(?:key|secret)|client[_-]?secret|"
    rb"(?:access|auth|refresh|secret)[_-]?token|"
    rb"(?:aws[_-]?)?secret[_-]?access[_-]?key|private[_-]?key)"
)
_CREDENTIAL_LABEL = rb"""(?P<keyquote>['"]?)""" + CREDENTIAL_KEY + rb"(?P=keyquote)"
_CREDENTIAL_VALUE = rb"""(?P<quote>['"])(?P<value>(?:\\.|(?!(?P=quote)).)*)(?P=quote)"""
CREDENTIAL_ASSIGNMENTS = (
    re.compile(rb"(?<![A-Za-z0-9_])\$?" + _CREDENTIAL_LABEL
               + rb"\s*\]?\s*(?:=>|=|:)\s*" + _CREDENTIAL_VALUE, re.I | re.S),
    re.compile(rb"\bdefine\s*\(\s*" + _CREDENTIAL_LABEL
               + rb"\s*,\s*" + _CREDENTIAL_VALUE, re.I | re.S),
    re.compile(rb"^\s*SetEnv\s+" + _CREDENTIAL_LABEL
               + rb"\s+" + _CREDENTIAL_VALUE, re.I | re.M | re.S),
    re.compile(rb"^\s*SetEnv\s+" + _CREDENTIAL_LABEL
               + rb"\s+(?P<value>[^\s\"'#]+)", re.I | re.M),
)
CREDENTIAL_PLACEHOLDER = re.compile(
    rb"(?:CHANGE[_ -]ME|REPLACE[_ -]ME|YOUR_[A-Z0-9_]+|"
    rb"\$\{[A-Z_][A-Z0-9_]*\}|\{\{\s*[A-Z_][A-Z0-9_.]*\s*\}\}|"
    rb"<[A-Z_][A-Z0-9_ .-]*>|REDACTED|\[REDACTED\]|\*{3,})", re.I
)


_ENV_CREDENTIAL_NAME = rb"[A-Z0-9_]*(?:PASSWORD|PASSWD|PASS|PWD|TOKEN|SECRET|API_?KEY)[A-Z0-9_]*"
ENV_CREDENTIAL_FALLBACKS = (
    re.compile(rb"\b(?:getenv|env)\s*\(\s*['\"]" + _ENV_CREDENTIAL_NAME + rb"['\"]\s*,\s*" + _CREDENTIAL_VALUE, re.I | re.S),
    re.compile(rb"\b(?:getenv|env)\s*\(\s*['\"]" + _ENV_CREDENTIAL_NAME + rb"['\"]\s*\)\s*(?:\?\s*:|\?\?)\s*" + _CREDENTIAL_VALUE, re.I | re.S),
    re.compile(rb"\bprocess\s*\.\s*env\s*\.\s*" + _ENV_CREDENTIAL_NAME + rb"\s*(?:\|\||\?\?)\s*" + _CREDENTIAL_VALUE, re.I | re.S),
    re.compile(rb"(?<![A-Za-z0-9_])(?:\$_(?:ENV|SERVER)|process\s*\.\s*env)\s*\[\s*['\"]"
               + _ENV_CREDENTIAL_NAME + rb"['\"]\s*\]\s*(?:\?\?|\?\s*:|\|\|)\s*"
               + _CREDENTIAL_VALUE, re.I | re.S),
    re.compile(rb"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:(?P<value>[^@\s/]+)@", re.I),
)
AUTH_RUNTIME_DEPENDENCY = re.compile(rb"^\s*AuthUserFile\s+\S", re.I | re.M)


def contains_credential(data):
    """Flag literal candidates without returning their values."""
    if SECRET_PATTERN.search(data):
        return True
    try:
        data.decode("utf-8")
    except UnicodeError:
        return True
    if b"\0" in data or AUTH_RUNTIME_DEPENDENCY.search(data):
        return True
    for pattern in (*CREDENTIAL_ASSIGNMENTS, *ENV_CREDENTIAL_FALLBACKS):
        for match in pattern.finditer(data):
            value = match.group("value").strip()
            if value and not CREDENTIAL_PLACEHOLDER.fullmatch(value):
                return True
    return False


class SiteCheck:
    def __init__(self, repo):
        self.repo = repo.resolve()
        self.site = self.repo / "public_html"
        self.errors = []

    def require(self, condition, message):
        if not condition:
            self.errors.append(message)
        return condition

    def file(self, relative):
        """Reject traversal and symlinks, including on Windows checkouts."""
        if not isinstance(relative, str) or not relative:
            self.errors.append("A source dependency has no valid relative path.")
            return None
        path = PurePosixPath(relative)
        if (path.is_absolute() or "\\" in relative or ":" in relative
                or any(part in ("", ".", "..") for part in relative.split("/"))):
            self.errors.append(f"Unsafe source path: {relative}")
            return None
        candidate = self.site.joinpath(*path.parts)
        if any(parent.is_symlink() for parent in (candidate, *candidate.parents)
               if parent != self.site.parent):
            self.errors.append(f"Symlink is not allowed in deployment source: {relative}")
            return None
        try:
            candidate.resolve().relative_to(self.site.resolve())
        except ValueError:
            self.errors.append(f"Source path escapes public_html: {relative}")
            return None
        if not self.require(candidate.is_file(), f"Missing source dependency: {relative}"):
            return None
        self.require(candidate.stat().st_size > 0, f"Empty source dependency: {relative}")
        return candidate

    def canonical_path(self, value):
        if not isinstance(value, str):
            return False
        parsed = urlsplit(value)
        decoded = unquote(value)
        return (value.startswith("/") and not value.startswith("//")
                and not parsed.scheme and not parsed.netloc and not parsed.query
                and not parsed.fragment and "\\" not in decoded
                and all(part not in (".", "..") for part in decoded.split("/")))

    def xml(self, relative, expected_tag):
        file = self.file(relative)
        if file is None:
            return None
        try:
            root = ET.parse(file).getroot()
        except (ET.ParseError, OSError) as error:
            self.errors.append(f"Cannot parse {relative}: {error}")
            return None
        self.require(root.tag == SM + expected_tag, f"Invalid sitemap root: {relative}")
        return root

    def check_payload(self):
        for file in self.site.rglob("*"):
            relative = file.relative_to(self.site).as_posix()
            lower = relative.lower()
            parts = lower.split("/")
            forbidden = (any(part in FORBIDDEN_NAMES or part.startswith(".env")
                             or part.startswith(".ftp") for part in parts)
                         or lower.endswith(FORBIDDEN_SUFFIXES))
            self.require(not forbidden, f"Credential/runtime file in payload: {relative}")
            self.require(not file.is_symlink(), f"Symlink in payload: {relative}")
            if (file.is_file() and not file.is_symlink()
                    and (file.suffix.lower() in PUBLIC_TEXT_SUFFIXES
                         or file.name.lower() == ".htaccess")):
                self.require(not contains_credential(file.read_bytes()),
                             f"Possible credential in payload: {relative} (value redacted)")

    def check_images(self, groups):
        expected_svgs = set()
        for entry in groups.get("tutorial", []):
            images = entry.get("images", []) if isinstance(entry, dict) else []
            if not self.require(isinstance(images, list) and len(images) == 1,
                                "Each of the 400 tutorials must declare one SVG diagram."):
                continue
            value = images[0]
            if not isinstance(value, str) or not value.startswith(DOMAIN + "/"):
                self.errors.append("Tutorial diagram must use the canonical site domain.")
                continue
            parsed = urlsplit(value)
            relative = parsed.path.lstrip("/")
            if not self.require(relative.startswith("assets/marketing-20261006/panduan/")
                                and relative.endswith(".svg") and not parsed.query
                                and not parsed.fragment,
                                f"Invalid tutorial diagram path: {relative}"):
                continue
            expected_svgs.add(relative)
            self.file(relative)
            preview = self.file(str(PurePosixPath(relative).with_suffix(".jpg")))
            if preview is not None:
                with preview.open("rb") as stream:
                    self.require(stream.read(2) == b"\xff\xd8", f"Invalid JPEG preview: {preview.name}")
        directory = self.site / "assets/marketing-20261006/panduan"
        actual_svgs = {file.relative_to(self.site).as_posix() for file in directory.glob("*.svg")}
        actual_jpgs = {file.relative_to(self.site).as_posix() for file in directory.glob("*.jpg")}
        expected_jpgs = {str(PurePosixPath(path).with_suffix(".jpg")) for path in expected_svgs}
        self.require(len(expected_svgs) == 400, "Tutorial diagrams must have 400 unique SVG paths.")
        self.require(actual_svgs == expected_svgs, "SVG diagram files do not match the 400 tutorials.")
        self.require(actual_jpgs == expected_jpgs, "JPEG previews do not match the 400 tutorials.")

    def run(self):
        marker = self.repo / ".site-source-ready"
        self.require(marker.is_file() and marker.stat().st_size > 0,
                     "Missing .site-source-ready: import the current LIVE source before deploying.")
        if not self.require(self.site.is_dir(), "Missing public_html deployment source."):
            return False
        for dependency in ("index.html", "content.php", ".htaccess", "sitemap.php", "seo.php",
                           "includes/tracking-query.php", "includes/refresh-data.json"):
            self.file(dependency)
        registry_file = self.file("includes/content-index.json")
        if registry_file is None:
            return False
        try:
            registry = json.loads(registry_file.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            self.errors.append(f"Cannot parse content registry: {error}")
            return False
        if not self.require(isinstance(registry, dict), "Content registry must be an object."):
            return False
        self.require(registry.get("domain") == DOMAIN, "Content registry domain changed.")
        groups = registry.get("groups")
        if not self.require(isinstance(groups, dict), "Missing content groups."):
            return False
        self.require(set(groups) == set(EXPECTED_GROUPS), "Content group names changed.")
        records = {}
        group_urls = {}
        for group, expected in EXPECTED_GROUPS.items():
            entries = groups.get(group, [])
            if not self.require(isinstance(entries, list), f"Invalid content group: {group}"):
                continue
            self.require(len(entries) == expected, f"{group}: expected {expected} entries, got {len(entries)}.")
            group_urls[group] = set()
            for entry in entries:
                if not self.require(isinstance(entry, dict), f"Invalid entry in {group}."):
                    continue
                path = entry.get("path")
                if not self.require(self.canonical_path(path), f"Invalid canonical path in {group}: {path}"):
                    continue
                self.require(path not in records, f"Duplicate content URL: {path}")
                records[path] = (group, entry.get("file"))
                group_urls[group].add(DOMAIN + path)
                self.file(entry.get("file"))
                dependencies = entry.get("lastmod_files", [])
                if self.require(isinstance(dependencies, list) and bool(dependencies),
                                f"Missing lastmod dependencies: {path}"):
                    for dependency in dependencies:
                        self.file(dependency)
        self.require(len(records) == 500, f"Expected 500 unique content URLs, got {len(records)}.")
        routes = registry.get("routes", {})
        if self.require(isinstance(routes, dict), "Content routes must be an object."):
            for path, route in routes.items():
                if not self.require(isinstance(route, dict), f"Invalid route record: {path}"):
                    continue
                self.require(path in records and records[path] == (route.get("group"), route.get("file")),
                             f"Route disagrees with content registry: {path}")
                self.file(route.get("file"))
            routed_paths = {path for path, (group, _) in records.items() if group not in ("utama", "layanan")}
            self.require(set(routes) == routed_paths, "Content router is missing or adds registered routes.")
        aliases = registry.get("aliases", {})
        if self.require(isinstance(aliases, dict), "Content aliases must be an object."):
            for alias, target in aliases.items():
                self.require(self.canonical_path(alias) and alias not in records and target in records,
                             f"Invalid content alias: {alias}")

        expected_files = {"sitemap.xml", *[f"sitemap-{group}.xml" for group in EXPECTED_GROUPS]}
        actual_files = {file.name for file in self.site.glob("sitemap*.xml") if file.is_file()}
        self.require(actual_files == expected_files, "Expected sitemap.xml and exactly 10 group XML sitemaps.")
        sitemap_index = self.xml("sitemap.xml", "sitemapindex")
        if sitemap_index is not None:
            indexed = [entry.findtext(SM + "loc", "") for entry in sitemap_index.findall(SM + "sitemap")]
            expected_index = {DOMAIN + "/" + name for name in expected_files if name != "sitemap.xml"}
            self.require(len(indexed) == 10 and set(indexed) == expected_index,
                         "Sitemap index must link the 10 canonical group sitemaps exactly once.")
        urls = []
        for group in EXPECTED_GROUPS:
            sitemap = self.xml(f"sitemap-{group}.xml", "urlset")
            if sitemap is None:
                continue
            locations = [entry.findtext(SM + "loc", "") for entry in sitemap.findall(SM + "url")]
            self.require(set(locations) == group_urls.get(group, set()),
                         f"sitemap-{group}.xml URLs differ from the content registry.")
            urls.extend(locations)
        duplicates = [url for url, count in Counter(urls).items() if count > 1]
        self.require(not duplicates and len(urls) == 500, "XML sitemaps must contain 500 URLs without duplicates.")
        self.require(set(urls) == {DOMAIN + path for path in records},
                     "The combined sitemap URLs do not match all registry URLs.")
        self.check_images(groups)
        self.check_payload()
        return not self.errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    check = SiteCheck(args.repo_root)
    try:
        success = check.run()
    except (OSError, ValueError, TypeError) as error:
        check.errors.append(f"Source validation could not complete: {error}")
        success = False
    if not success:
        print("Deployment source validation FAILED:", file=sys.stderr)
        for error in check.errors[:40]:
            print(f"- {error}", file=sys.stderr)
        if len(check.errors) > 40:
            print(f"- ... {len(check.errors) - 40} additional errors.", file=sys.stderr)
        return 1
    print("Source validated: 500 URLs, 11 sitemaps, 400 SVG/JPEG pairs, 14 tools, 3 stores; no credential/runtime files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
