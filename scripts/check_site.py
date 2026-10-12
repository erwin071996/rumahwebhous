#!/usr/bin/env python3
"""Validate the imported production source before any Rumahweb upload."""

import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import parse_qsl, unquote, urlsplit
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
    ".3dkan-deployment-state.json",
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
TEXT_SUFFIXES = {".php", ".json", ".js", ".html", ".txt", ".xml", ".css", ".svg",
                 ".ini", ".conf", ".config", ".yaml", ".yml"}
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_-]*"
QUOTED_VALUE = r"(?P<quote>['\"`])(?P<value>(?:\\.|(?!(?P=quote))[\s\S])*?)(?P=quote)"
LITERAL_ASSIGNMENT = re.compile(
    r"(?<![A-Za-z0-9_])(?:\$?(?P<bare>" + IDENTIFIER + r")|"
    r"(?P<name_quote>['\"])(?P<key>" + IDENTIFIER + r")(?P=name_quote))\s*\]?\s*(?:=>|:(?!=)|=(?!=))\s*"
    + QUOTED_VALUE
)
DEFINED_LITERAL = re.compile(
    r"\bdefine\s*\(\s*(?P<name_quote>['\"])(?P<key>" + IDENTIFIER + r")(?P=name_quote)\s*,\s*"
    + QUOTED_VALUE, re.IGNORECASE
)
CONFIG_ASSIGNMENT = re.compile(
    r"^[ \t]*(?:(?:export|SetEnv)[ \t]+)?(?P<key>" + IDENTIFIER + r")"
    r"[ \t]*(?:=[ \t]*|[ \t]+)(?P<value>[^\r\n#;]+)", re.MULTILINE
)
XML_LITERAL = re.compile(
    r"<(?P<key>" + IDENTIFIER + r")\b[^>]*>(?P<value>[^<]+)</(?P=key)\s*>"
)
URL_LITERAL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>`]+")
# These two existing Sitejet constants are intentionally sent to Google Maps
# Embed/JavaScript by the browser. Review preserves exact live source, not an
# exemption for arbitrary API keys: field, fingerprint and source path must all
# match. This does not claim that Google Cloud referrer restrictions were read.
# https://developers.google.com/maps/api-security-best-practices
REVIEWED_BROWSER_KEYS = {
    "googleMapsEmbedApiKey": {
        "sha256": "916414a7fc9374e3dd3d7ce9a738ea847c441ec714c1a287b232e6012a3ea103",
        "paths": frozenset({
            "blog-single-page-layout/blog-post-1/index.html",
            "blog-single-page-layout/blog-post-2/index.html",
            "blog-single-page-layout/blog-post-3/index.html",
            "blog-single-page-layout/blog-post-4/index.html",
            "blog-single-page-layout/blog-post-5/index.html",
            "blog-single-page-layout/blog-post-6/index.html",
            "jobs-1-item/1-accountant-tech/index.html",
            "jobs-1-item/2-developer-sales/index.html",
            "jobs-1-item/3-analyst-sales/index.html",
            "jobs-1-item/4-accountant-human-resources/index.html",
            "jobs-1-item/5-engineer-sales/index.html",
            "jobs-1-item/6-analyst-sales/index.html",
            "legal-notice/index.html",
            "modules-1-item/coding/index.html",
            "modules-1-item/data-science/index.html",
            "modules-1-item/digital-marketing/index.html",
            "modules-1-item/finances/index.html",
            "modules-1-item/photography/index.html",
            "modules-1-item/public-speaking/index.html",
            "privacy/index.html",
            "real-estate-single-page-layout/2-bedroom-apartment-in-chicago/index.html",
            "real-estate-single-page-layout/apartment-in-denver/index.html",
            "real-estate-single-page-layout/beautiful-house-in-anaheim/index.html",
            "real-estate-single-page-layout/executive-office-in-anaheim/index.html",
            "real-estate-single-page-layout/luxury-house-in-newton/index.html",
            "real-estate-single-page-layout/modern-house-in-denver/index.html",
            "real-estate-single-page-layout/office-space-in-chicago/index.html",
            "real-estate-single-page-layout/serviced-office-in-denver/index.html",
            "real-estate-single-page-layout/studio-loft-in-chicago/index.html",
            "subpage/index.html",
        }),
    },
    "GOOGLE_MAPS_TOKEN": {
        "sha256": "592f1cac55a5c1d705635904475e5266c72a6159223d56df84ae8e724718c433",
        "paths": frozenset({"webcard/static/app.bundle.1765894263.js"}),
    },
}


def credential_category(name):
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized).lower().replace("-", "_")
    compact_service = r"(?:ftp|ftps|smtp|db|database|mysql|postgres|pgsql)"
    if (re.search(r"(?:^|_)(?:password|passwd|pwd|pass)(?:_hash)?$", normalized)
            or re.fullmatch(compact_service + r"(?:password|passwd|pwd|pass)", normalized)):
        return "literal-password"
    if (normalized in {"authorization", "authentication", "apikey"}
            or re.search(r"(?:^|_)(?:secret|token)$|(?:^|_)(?:api_key|access_key|private_key|secret_key|auth_key)$", normalized)):
        return "literal-secret-or-token"
    if (re.search(r"^" + compact_service + r"_.*(?:user|username|login)$", normalized)
            or re.fullmatch(compact_service + r"(?:user|username|login)", normalized)):
        return "literal-service-credential"
    return None


def placeholder_or_dynamic(value):
    value = value.strip().strip("'\"`").strip()
    if not value or value.lower() in {"null", "none", "undefined", "false", "true", "bearer", "basic"}:
        return True
    normalized = re.sub(r"[\s-]+", "_", value).lower()
    if normalized in {"changeme", "change_me", "replace_me", "redacted", "placeholder",
                      "todo", "tbd", "example", "sample", "dummy"}:
        return True
    if re.fullmatch(r"(?:your|insert|replace|example|sample)_[a-z0-9_]+", normalized):
        return True
    if re.fullmatch(r"[xX*\u2022\u25cf_]{3,}", value):
        return True
    if re.fullmatch(r"(?:<[^<>]+>|\$\{[^{}]+\}|\{\{[^{}]+\}\}|\{\$[^{}]+\}|%[A-Z0-9_]+%)", value):
        return True
    # Dynamic lookups are not literals, including config-text examples of them.
    return bool(re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*(?:\[.*\])?", value)
                or re.match(r"(?:getenv|env|os\.getenv)\s*\(|process\.env\.|os\.environ\[", value))


def reviewed_browser_key(name, value, relative):
    review = REVIEWED_BROWSER_KEYS.get(name)
    return bool(review and relative in review["paths"]
                and hashlib.sha256(value.encode()).hexdigest() == review["sha256"])


def credential_categories(data, *, relative=None):
    """Return categories only; matching values never enter diagnostic output."""
    categories = set()
    if SECRET_PATTERN.search(data):
        categories.add("provider-key-or-private-key")
    text = data.decode("utf-8-sig", errors="replace")
    for pattern in (LITERAL_ASSIGNMENT, DEFINED_LITERAL, CONFIG_ASSIGNMENT, XML_LITERAL):
        for match in pattern.finditer(text):
            name = match.groupdict().get("key") or match.groupdict().get("bare")
            category = credential_category(name)
            if (category and not placeholder_or_dynamic(match.group("value"))
                    and not reviewed_browser_key(name, match.group("value"), relative)):
                categories.add(category)
    for match in URL_LITERAL.finditer(html.unescape(text.replace(r"\/", "/"))):
        try:
            url = urlsplit(match.group().rstrip(").,;"))
            if url.password is not None and not placeholder_or_dynamic(unquote(url.password)):
                categories.add("credential-bearing-url")
            for name, value in parse_qsl(url.query):
                if credential_category(name) and not placeholder_or_dynamic(value):
                    categories.add("credential-bearing-url")
        except ValueError:
            # Malformed public URLs are checked by the relevant source checks.
            continue
    return sorted(categories)


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
                    and (file.suffix.lower() in TEXT_SUFFIXES or file.name.lower() == ".htaccess")):
                for category in credential_categories(file.read_bytes(), relative=relative):
                    self.errors.append(f"Possible credential in payload: {relative} [{category}] (value redacted)")

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
