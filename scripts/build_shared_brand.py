#!/usr/bin/env python3
"""Deterministic public SharedBrand build. No network, runtime secrets or publisher."""
from __future__ import annotations
import argparse
import base64
import importlib.util
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import zlib
from urllib.parse import quote, urlsplit

CONFIG = "config/site-brand.json"
INPUTS = "config/shared-brand-inputs.json"
MANIFEST = "docs/shared-brand-build.json"
REGISTRY = "public_html/includes/content-index.json"
HEADER = "public_html/includes/refresh-header.html"
FOOTER = "public_html/includes/refresh-footer.html"
HEAD = "public_html/includes/refresh-brand-head.html"
ADAPTER = "public_html/includes/shared-brand.php"
PUBLIC_CONFIG = "public_html/includes/site-brand.json"
TOKENS = "public_html/assets/ui/brand-tokens.css"
DESIGN = "public_html/assets/ui/design-system.css"
CONTROLLER = "public_html/assets/ui/frontend.js"
TEMPLATES = {
    "header": ("templates/presentation/shared-header.html", "7a1a98936698f57cfec2cee7e54f0e64c7176dba16c7acfb916125e9b51bc652"),
    "footer": ("templates/presentation/shared-footer.html", "1dcb943ed1bf607aab248361ebf075d498f083fc01a8a4984687ebf72f12e64a"),
    "cta": ("templates/presentation/shared-cta.html", "d1597bb8b7f315eff0fa600d30b2f6a5dccdcfa4340e544841d5554b71f3761e"),
}
DESIGN_SHA = "66a28499c514cb36c4e43ef1bad89782f963a5bf93146fa81f7370f7e85fef74"
CONTROLLER_SHA = "0f2137981e0b5e6eea0e3ac5899266a0f59ced724090d5ad4b0b504dbddef828"
LEGACY_SCRIPTS = {
    "/assets/marketing-20261006/site.js": "baf0918036519d5d847d41ee812c5f7823823a41158973d999e9ce317cfa0c5d",
    "/assets/refresh-20261006/site-v2.js": "16cf9ec47fb3d251b3439eaf717f9c9e67abe58a5eb21f8d0027bc82f27b27b4",
    "/assets/refresh-20261006/site.js": "75c087398bf581cba22e65d75a86c76e612459e9be394a613d408f5f73c910b1",
}
COUNTS = {"utama": 8, "layanan": 7, "wilayah": 24, "produk": 9, "panduan": 12, "tutorial": 400, "topik": 20, "alat": 14, "toko": 3, "informasi": 3}
BASE_COMMIT = "dd31d7305d1571b4fde960ed0b942135a88388a1"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("ascii")

def read(root, relative):
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or unsafe source: " + relative)
    real = path.resolve()
    if not real.is_relative_to(root.resolve()):
        raise ValueError("Source leaves checkout: " + relative)
    return path.read_bytes()

def exact(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Unexpected source multiplicity")
    return source.replace(old, new, 1)

def text(value, limit=500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or re.search(r"[\x00-\x1f\x7f]", value):
        raise ValueError("Invalid public text")
    return value

def esc(value):
    return html.escape(str(value), quote=True)

def internal(value):
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//") or re.search(r"[\s\\<>\"'\x00-\x1f]", value):
        raise ValueError("Invalid internal URL")
    u = urlsplit(value)
    if u.scheme or u.netloc or any(part in (".", "..") for part in u.path.split("/")):
        raise ValueError("Invalid internal URL")
    return value

def href(value):
    if isinstance(value, str) and value.startswith("/"):
        return internal(value)
    if not isinstance(value, str) or re.search(r"[\s\\<>\"'\x00-\x1f]", value):
        raise ValueError("Invalid link")
    u = urlsplit(value)
    if u.scheme == "https" and u.hostname and not u.username and not u.password and not u.port:
        return value
    if re.fullmatch(r"tel:\+[1-9][0-9]{6,14}", value):
        return value
    if re.fullmatch(r"mailto:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value):
        return value
    raise ValueError("Invalid link scheme")

def keys(record, required, optional=()):
    if not isinstance(record, dict) or set(record) - set(required) - set(optional) or set(required) - set(record):
        raise ValueError("Unexpected public configuration fields")

def public_shape(cfg):
    keys(cfg, ("schema_version", "theme_version", "brand", "colors", "typography", "navigation", "footer", "contact", "cta", "layout", "shell"))
    keys(cfg["brand"], ("display_name", "home_href", "logo_primary", "favicon_path"))
    keys(cfg["brand"]["logo_primary"], ("path", "width", "height", "alt", "revision", "sha256"), ("screen_derivative",))
    if cfg["brand"]["logo_primary"].get("screen_derivative"):
        keys(cfg["brand"]["logo_primary"]["screen_derivative"], ("path", "width", "height", "master_sha256", "git_blob"))
    keys(cfg["typography"], ("font_family_headings", "font_family_body", "font_weights", "line_height_body"))
    keys(cfg["navigation"], ("items", "active_path_rules"))
    keys(cfg["footer"], ("intro_lines", "columns", "copyright_template", "copyright_year", "region_label"))
    keys(cfg["contact"], ("phone_display", "phone_e164", "email", "social_links"))
    keys(cfg["cta"], ("primary",))
    keys(cfg["cta"]["primary"], ("label", "kind", "href_or_message_template"))
    keys(cfg["layout"], ("container_max_width", "spacing_scale", "border_radius"))
    keys(cfg["shell"], ("business_bar", "services_label", "services_eyebrow", "feature", "skip_label", "menu_label", "nav_label", "social_label", "email_label"))
    keys(cfg["shell"]["business_bar"], ("tagline", "locations_label", "locations_href"))
    keys(cfg["shell"]["feature"], ("eyebrow", "heading", "text", "links"))
    for column in cfg["footer"]["columns"]:
        keys(column, ("title", "items"))
    collections = [cfg["navigation"]["items"], cfg["contact"]["social_links"], cfg["shell"]["feature"]["links"]]
    collections += [column["items"] for column in cfg["footer"]["columns"]]
    for collection in collections:
        for item in collection:
            keys(item, ("label", "href"))

def validate(cfg):
    public_shape(cfg)
    if cfg.get("schema_version") != 1:
        raise ValueError("Unsupported SharedBrand schema")
    text(cfg["theme_version"], 80)
    brand = cfg["brand"]
    text(brand["display_name"], 120)
    internal(brand["home_href"])
    internal(brand["favicon_path"])
    logo = brand["logo_primary"]
    internal(logo["path"]); text(logo["alt"], 180); text(logo["revision"], 80)
    if not all(isinstance(logo[k], int) and not isinstance(logo[k], bool) and 0 < logo[k] < 10000 for k in ("width", "height")):
        raise ValueError("Invalid logo dimensions")
    if not re.fullmatch(r"[a-f0-9]{64}", logo["sha256"]):
        raise ValueError("Invalid master digest")
    derivative = logo.get("screen_derivative")
    if derivative:
        internal(derivative["path"])
        if not re.fullmatch(r"[a-f0-9]{40}", derivative["git_blob"]):
            raise ValueError("Invalid derivative blob identity")
        if derivative["master_sha256"] != logo["sha256"]:
            raise ValueError("Derivative belongs to another master")
        if not all(isinstance(derivative[k], int) and 0 < derivative[k] < 10000 for k in ("width", "height")):
            raise ValueError("Invalid derivative dimensions")
        if abs(derivative["width"] / derivative["height"] - logo["width"] / logo["height"]) > .01:
            raise ValueError("Derivative aspect mismatch")
    color_keys = {"primary", "secondary", "accent", "text", "text_muted", "background", "surface", "border"}
    if set(cfg["colors"]) != color_keys or any(not re.fullmatch(r"#[0-9a-fA-F]{6}", v) for v in cfg["colors"].values()):
        raise ValueError("Invalid color tokens")
    tp = cfg["typography"]
    for key in ("font_family_body", "font_family_headings"):
        if not re.fullmatch(r"[A-Za-z0-9 ,\"'-]{1,160}", tp[key]):
            raise ValueError("Invalid font token")
    if set(tp["font_weights"]) != {"body", "headings"} or any(not isinstance(v, int) or v < 100 or v > 900 for v in tp["font_weights"].values()):
        raise ValueError("Invalid font weight")
    if not isinstance(tp["line_height_body"], (int, float)) or not 1.2 <= tp["line_height_body"] <= 2.2:
        raise ValueError("Invalid line height")
    layout = cfg["layout"]
    lengths = [layout["container_max_width"], *layout["spacing_scale"].values(), *layout["border_radius"].values()]
    if set(layout["spacing_scale"]) != {"xs", "sm", "md", "lg", "xl", "section"} or set(layout["border_radius"]) != {"control", "card"}:
        raise ValueError("Invalid layout fields")
    for value in lengths:
        if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9.]+(?:px|rem)|clamp\([0-9.]+rem,[0-9.]+vw,[0-9.]+rem\))", value):
            raise ValueError("Invalid layout token")
    contact = cfg["contact"]
    text(contact["phone_display"], 40)
    if not re.fullmatch(r"\+[1-9][0-9]{6,14}", contact["phone_e164"]):
        raise ValueError("Invalid contact phone")
    href("mailto:" + contact["email"])
    collections = [cfg["navigation"]["items"], contact["social_links"], cfg["shell"]["feature"]["links"]]
    collections += [column["items"] for column in cfg["footer"]["columns"]]
    for items in collections:
        if not isinstance(items, list) or len(items) > 30:
            raise ValueError("Invalid public links")
        for item in items:
            text(item["label"], 180); href(item["href"])
    if len({i["href"] for i in cfg["navigation"]["items"]}) != len(cfg["navigation"]["items"]):
        raise ValueError("Duplicate navigation")
    for target, rules in cfg["navigation"]["active_path_rules"].items():
        if target not in [item["href"] for item in cfg["navigation"]["items"]]:
            raise ValueError("Unknown navigation rule")
        for rule in rules:
            internal(rule)
    footer = cfg["footer"]
    if not isinstance(footer["copyright_year"], int) or not 2000 <= footer["copyright_year"] <= 2100:
        raise ValueError("Invalid fixed copyright year")
    text(footer["copyright_template"], 200); text(footer["region_label"], 180)
    for line in footer["intro_lines"]:
        text(line, 180)
    for column in footer["columns"]:
        text(column["title"], 120)
    shell = cfg["shell"]
    for key in ("services_label", "services_eyebrow", "skip_label", "menu_label", "nav_label", "social_label", "email_label"):
        text(shell[key], 180)
    for key in ("tagline", "locations_label"):
        text(shell["business_bar"][key], 180)
    internal(shell["business_bar"]["locations_href"])
    for key in ("eyebrow", "heading", "text"):
        text(shell["feature"][key])
    primary = cfg["cta"]["primary"]
    text(primary["label"], 120)
    if primary["kind"] not in ("whatsapp", "link"):
        raise ValueError("Invalid CTA kind")
    (text if primary["kind"] == "whatsapp" else href)(primary["href_or_message_template"])
    return cfg

def wa(cfg, message):
    return "https://wa.me/" + cfg["contact"]["phone_e164"][1:] + "?text=" + quote(message, safe="")

def default_cta(cfg):
    cta = cfg["cta"]["primary"]
    return wa(cfg, cta["href_or_message_template"]) if cta["kind"] == "whatsapp" else href(cta["href_or_message_template"])

def link(item, *, css="", arrow=False, active=False):
    dest = href(item["href"])
    attributes = ' target="_blank" rel="noopener noreferrer"' if dest.startswith("https://") else ""
    if css:
        attributes = ' class="' + esc(css) + '"' + attributes
    if active:
        attributes += ' aria-current="page"'
    label = esc(item["label"])
    if arrow:
        label += ' <span aria-hidden="true">\u2197</span>'
    return '<a href="' + esc(dest) + '"' + attributes + ">" + label + "</a>"

def active_href(cfg, route):
    if route == "/":
        return "/"
    for item in cfg["navigation"]["items"]:
        if urlsplit(item["href"]).path == route:
            return item["href"]
    for target, rules in cfg["navigation"]["active_path_rules"].items():
        if any((route.startswith(rule) if rule.endswith("/") else route == rule) for rule in rules):
            return target
    return None

def logo_markup(cfg, footer=False):
    logo = cfg["brand"]["logo_primary"]
    img = '<img src="' + esc(logo["path"]) + '" width="' + str(logo["width"]) + '" height="' + str(logo["height"]) + '"'
    if footer:
        img += ' loading="lazy"'
    img += ' decoding="async" alt="' + esc(logo["alt"]) + '">'
    derivative = logo.get("screen_derivative")
    if derivative:
        return '<picture class="responsive-documentation"><source media="screen" type="image/webp" srcset="' + esc(derivative["path"]) + '">' + img + "</picture>"
    return img

def substitute(template, fields):
    for key, value in fields.items():
        marker = "{{" + key + "}}"
        if marker not in template:
            raise ValueError("Missing template slot: " + key)
        template = template.replace(marker, value)
    if re.search(r"{{[^}]+}}", template):
        raise ValueError("Unfilled presentation slot")
    return template

def render_shell(cfg, templates, route=None, cta_href=None):
    shell = cfg["shell"]; brand = cfg["brand"]; footer = cfg["footer"]
    current = active_href(cfg, route) if route else None
    socials = '<div class="social-links" aria-label="' + esc(shell["social_label"]) + '">'
    socials += "".join(link(item) for item in cfg["contact"]["social_links"])
    socials += link({"href": "mailto:" + cfg["contact"]["email"], "label": shell["email_label"]}) + "</div>"
    services = [item for item in cfg["navigation"]["items"] if item["href"].startswith("/layanan/")]
    primary = [item for item in cfg["navigation"]["items"] if not item["href"].startswith("/layanan/")]
    feature = shell["feature"]
    feature_markup = '<div class="mega-feature"><p class="eyebrow">' + esc(feature["eyebrow"]) + "</p><h2>" + esc(feature["heading"]) + "</h2><p>" + esc(feature["text"]) + "</p>"
    feature_markup += "".join(link(item, css="text-link") for item in feature["links"]) + "</div>"
    header = templates["header"]
    replacements = [
        ("Langsung ke isi", esc(shell["skip_label"])),
        ("Desain \u00b7 Produksi \u00b7 Pemasangan", esc(shell["business_bar"]["tagline"])),
        ('href="/contact.html#toko">3 lokasi toko', 'href="' + esc(shell["business_bar"]["locations_href"]) + '">' + esc(shell["business_bar"]["locations_label"])),
        ('>Menu <span', '>' + esc(shell["menu_label"]) + ' <span'),
        ('aria-label="Navigasi utama"', 'aria-label="' + esc(shell["nav_label"]) + '"'),
        ('<summary>Layanan</summary>', '<summary>' + esc(shell["services_label"]) + '</summary>'),
        ("IDENTITAS USAHA ANDA", esc(shell["services_eyebrow"])),
    ]
    for old, new in replacements:
        header = exact(header, old, new)
    feature_match = re.search(r'<div class="mega-feature">.*?</div>', header, re.S)
    if not feature_match:
        raise ValueError("Missing feature presentation")
    header = exact(header, feature_match.group(), feature_markup)
    target = cta_href or default_cta(cfg)
    if target.startswith("#"):
        if target not in ("#brief-cepat", "#brief-proyek"):
            raise ValueError("Unexpected local header CTA")
    else:
        href(target)
    cta = substitute(templates["cta"], {"cta_href": esc(target), "cta_external_attributes": ' target="_blank" rel="noopener noreferrer"' if target.startswith("https://") else "", "cta_label": esc(cfg["cta"]["primary"]["label"])})
    cta = exact(cta, 'class="btn btn-primary"', 'class="btn btn-small btn-primary"')
    header = substitute(header, {
        "social_links": socials, "brand_home_href": esc(brand["home_href"]),
        "brand_home_label": esc(brand["display_name"] + " \u2014 beranda"),
        "logo_header": logo_markup(cfg), "service_links": "".join(link(item, arrow=True, active=item["href"] == current) for item in services),
        "navigation_links": "".join(link(item, active=item["href"] == current) for item in primary), "header_cta": cta.rstrip("\n"),
    })
    if current == "/":
        header = exact(header, 'class="brand" href="' + esc(brand["home_href"]) + '"', 'class="brand" href="' + esc(brand["home_href"]) + '" aria-current="page"')
    columns = []
    for i, column in enumerate(footer["columns"]):
        markup = "<div><h2>" + esc(column["title"]) + "</h2>" + "".join(link(item) for item in column["items"])
        if i == len(footer["columns"]) - 1:
            markup += link({"href": "tel:" + cfg["contact"]["phone_e164"], "label": cfg["contact"]["phone_display"]})
            markup += link({"href": "mailto:" + cfg["contact"]["email"], "label": cfg["contact"]["email"]})
        columns.append(markup + "</div>")
    paper_footer = exact(templates["footer"], "Nama yang Anda bangun.<br>Identitas yang kami bantu wujudkan.", "<br>".join(esc(line) for line in footer["intro_lines"]))
    paper_footer = exact(paper_footer, "Sulawesi Selatan &amp; Sulawesi Tenggara", esc(footer["region_label"]))
    copyright_text = footer["copyright_template"].replace("{year}", str(footer["copyright_year"])).replace("{brand}", brand["display_name"])
    paper_footer = substitute(paper_footer, {"brand_home_href": esc(brand["home_href"]), "logo_footer": logo_markup(cfg, True), "social_links": socials, "footer_columns": "".join(columns), "copyright": esc(copyright_text)})
    return "<!-- SharedBrand:header -->\n" + header.rstrip("\n") + "\n<!-- /SharedBrand:header -->", "<!-- SharedBrand:footer -->\n" + paper_footer.rstrip("\n") + "\n<!-- /SharedBrand:footer -->"

def tokens(cfg):
    colors = cfg["colors"]; tp = cfg["typography"]; layout = cfg["layout"]
    values = {"--kan-color-" + ("muted" if key == "text_muted" else key): value for key, value in colors.items()}
    values.update({"--kan-font-body": tp["font_family_body"], "--kan-font-heading": tp["font_family_headings"],
                   "--kan-weight-body": str(tp["font_weights"]["body"]), "--kan-weight-heading": str(tp["font_weights"]["headings"]),
                   "--kan-line-height": str(tp["line_height_body"]), "--kan-content-width": layout["container_max_width"]})
    values.update({"--kan-space-" + key: value for key, value in layout["spacing_scale"].items()})
    values.update({"--kan-radius-" + key: value for key, value in layout["border_radius"].items()})
    return ("/* Generated from config/site-brand.json; edit the configuration. */\n:root {\n" + "".join("  " + key + ": " + value + ";\n" for key, value in sorted(values.items())) + "}\n").encode("utf-8")

class Tags(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.offsets = [0]
        for line in source.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.stack = []; self.records = []
        self.feed(source)
        if self.stack:
            raise ValueError("Unclosed document structure")
    def source_offset(self):
        line, col = self.getpos()
        return self.offsets[line - 1] + col
    def handle_starttag(self, tag, attrs):
        start = self.source_offset(); raw = self.get_starttag_text()
        record = {"tag": tag, "attrs": dict(attrs), "start": start, "open_end": start + len(raw), "end": None}
        self.records.append(record)
        if tag not in ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"):
            self.stack.append(record)
        else:
            record["end"] = record["open_end"]
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1]["tag"] == tag:
            self.stack.pop()["end"] = self.source_offset() + len(self.get_starttag_text())
    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1]["tag"] != tag:
            raise ValueError("Unexpected document nesting: " + tag)
        record = self.stack.pop()
        close = self.source.find(">", self.source_offset())
        record["close_start"] = self.source_offset(); record["end"] = close + 1
    def one(self, tag, css=None):
        matches = [r for r in self.records if r["tag"] == tag and (css is None or css in (r["attrs"].get("class") or "").split())]
        if len(matches) != 1:
            raise ValueError("Unexpected element multiplicity: " + tag)
        return matches[0]

def managed_head(source, head_markup):
    begin = "<!-- SharedBrand:head -->"
    end = "<!-- /SharedBrand:head -->"
    if begin in source or end in source:
        if source.count(begin) != 1 or source.count(end) != 1:
            raise ValueError("Invalid managed head")
        a = source.index(begin); b = source.index(end, a) + len(end)
        source = source[:a] + source[b:]
    source = re.sub(r'<script\b[^>]*\bsrc="/assets/ui/frontend\.js(?:\?v=[a-f0-9]+)?"[^>]*>\s*</script>', "", source)
    if source.count("</head>") != 1:
        raise ValueError("Unexpected head multiplicity")
    return exact(source, "</head>", begin + head_markup + end + "</head>")

def original_cta(source, cfg):
    tags = Tags(source)
    body = tags.one("body"); main = tags.one("main"); header = tags.one("header", "site-header")
    if not body["open_end"] <= header["start"] < header["end"] <= main["start"]:
        raise ValueError("Unexpected shell placement")
    matches = [r for r in tags.records if r["tag"] == "a" and r["start"] > header["start"] and r["end"] < header["end"] and "btn-primary" in (r["attrs"].get("class") or "").split()]
    if len(matches) != 1:
        raise ValueError("Unexpected header CTA multiplicity")
    value = matches[0]["attrs"].get("href", "")
    if value.startswith("#"):
        if value not in ("#brief-cepat", "#brief-proyek"):
            raise ValueError("Unapproved local CTA")
        return value
    href(value)
    u = urlsplit(value)
    if u.hostname == "wa.me" and re.fullmatch(r"/[0-9]+", u.path):
        return "https://wa.me/" + cfg["contact"]["phone_e164"][1:] + ("?" + u.query if u.query else "")
    if value == default_cta(cfg):
        return value
    raise ValueError("Unapproved header CTA")

def version_legacy_scripts(source, versions):
    # Change only known script src attributes in the head, never business main.
    match = re.search(r"<head\b[^>]*>.*?</head>", source, re.S)
    if not match or len(re.findall(r"<head\b", source)) != 1 or source.count("</head>") != 1:
        raise ValueError("Unexpected head for navigation script versioning")
    head = match.group()
    for path, sha in sorted(versions.items()):
        pattern = re.compile(r'(<script\b[^>]*\bsrc=")' + re.escape(path) + r'(?:\?v=[a-f0-9]{16,64})?(")', re.S)
        head = pattern.sub(lambda item, path=path, sha=sha: item.group(1) + path + "?v=" + sha[:16] + item.group(2), head)
    return source[:match.start()] + head + source[match.end():]

def pre_main_content(source):
    tags = Tags(source)
    header = tags.one("header", "site-header")
    main = tags.one("main")
    start = header["end"]
    begin, end = "<!-- SharedBrand:header -->", "<!-- /SharedBrand:header -->"
    if begin in source or end in source:
        if source.count(begin) != 1 or source.count(end) != 1:
            raise ValueError("Invalid managed header")
        marker_start = source.index(begin)
        marker_end = source.index(end, marker_start) + len(end)
        if not marker_start <= header["start"] < header["end"] <= marker_end <= main["start"]:
            raise ValueError("Managed header boundary mismatch")
        start = marker_end
    if start > main["start"]:
        raise ValueError("Unexpected pre-main module placement")
    return source[start:main["start"]]

def focusable_main(source):
    tags = Tags(source)
    main = tags.one("main")
    if "tabindex" in main["attrs"]:
        return source
    # This is the sole approved main delta: retain every existing byte/attribute.
    at = main["open_end"] - 1
    if source[at] != ">":
        raise ValueError("Unexpected main opening tag")
    return source[:at] + ' tabindex="-1"' + source[at:]

def static_document(source, cfg, templates, route, head_markup, script_versions):
    source = version_legacy_scripts(focusable_main(source), script_versions)
    old = Tags(source); body = old.one("body"); main = old.one("main"); footer = old.one("footer", "site-footer")
    main_bytes = source[main["start"]:main["end"]]
    before_main = pre_main_content(source)
    header_html, footer_html = render_shell(cfg, templates, route, original_cta(source, cfg))
    if not main["end"] <= footer["start"] < footer["end"] < body["end"]:
        raise ValueError("Unexpected footer placement")
    # Replace shell ranges only. Everything between main start/end remains exact.
    footer_start, footer_end = footer["start"], footer["end"]
    begin, end = "<!-- SharedBrand:footer -->", "<!-- /SharedBrand:footer -->"
    if begin in source or end in source:
        if source.count(begin) != 1 or source.count(end) != 1:
            raise ValueError("Invalid managed footer")
        footer_start = source.index(begin)
        footer_end = source.index(end, footer_start) + len(end)
        if not footer_start <= footer["start"] < footer["end"] <= footer_end:
            raise ValueError("Managed footer boundary mismatch")
    source = source[:footer_start] + footer_html + source[footer_end:]
    source = source[:body["open_end"]] + header_html + before_main + source[main["start"]:]
    # Keep optional legacy floating CTA markup intact; design-system hides it.
    body_text = source[body["start"]:body["open_end"]]
    if "class" in body["attrs"]:
        classes = (body["attrs"].get("class") or "").split()
        if "kan-site" not in classes:
            body_text = exact(body_text, 'class="' + body["attrs"]["class"] + '"', 'class="' + body["attrs"]["class"] + ' kan-site"')
    else:
        body_text = exact(body_text, "<body", '<body class="kan-site"')
    source = source[:body["start"]] + body_text + source[body["open_end"]:]
    source = managed_head(source, head_markup)
    new = Tags(source); new_main = new.one("main")
    if source[new_main["start"]:new_main["end"]] != main_bytes:
        raise ValueError("Main content changed")
    if pre_main_content(source) != before_main:
        raise ValueError("Pre-main module changed")
    return source

PHP_ADAPTER = r'''<?php
// Generated public presentation adapter. No authentication, storage writer or network.
function kan_shared_brand() {
    static $brand = null;
    if ($brand === null) {
        $raw = file_get_contents(__DIR__ . '/site-brand.json');
        $brand = json_decode($raw === false ? '' : $raw, true);
        if (!is_array($brand) || ($brand['schema_version'] ?? null) !== 1) {
            http_response_code(503); exit('Halaman sementara tidak tersedia.');
        }
    }
    return $brand;
}
function kan_shared_fragment($name) {
    $files = ['header' => 'refresh-header.html', 'footer' => 'refresh-footer.html', 'head' => 'refresh-brand-head.html'];
    if (!isset($files[$name])) throw new InvalidArgumentException('Unknown presentation fragment');
    $value = file_get_contents(__DIR__ . '/' . $files[$name]);
    if ($value === false) { http_response_code(503); exit('Halaman sementara tidak tersedia.'); }
    return $value;
}
function kan_shared_active_href($path) {
    $brand = kan_shared_brand();
    if ($path === '/') return '/';
    foreach ($brand['navigation']['items'] as $item) {
        if (parse_url($item['href'], PHP_URL_PATH) === $path) return $item['href'];
    }
    foreach ($brand['navigation']['active_path_rules'] as $target => $rules) {
        foreach ($rules as $rule) {
            if (str_ends_with($rule, '/') ? str_starts_with($path, $rule) : $path === $rule) return $target;
        }
    }
    return null;
}
function kan_shared_header($path) {
    $active = kan_shared_active_href($path);
    echo preg_replace_callback('/<a\b[^>]*href="([^"]*)"[^>]*>/', function ($match) use ($active) {
        $url = html_entity_decode($match[1], ENT_QUOTES | ENT_HTML5, 'UTF-8');
        if ($active !== null && $url === $active && strpos($match[0], 'aria-current=') === false) {
            return substr($match[0], 0, -1) . ' aria-current="page">';
        }
        return $match[0];
    }, kan_shared_fragment('header'));
}
function kan_shared_footer() { echo kan_shared_fragment('footer'); }
function kan_shared_head() { echo kan_shared_fragment('head'); }
function kan_shared_whatsapp($message) {
    $brand = kan_shared_brand();
    return 'https://wa.me/' . ltrim($brand['contact']['phone_e164'], '+') . '?text=' . rawurlencode($message);
}
'''
def php_document(source, script_versions):
    if "require_once __DIR__ . '/includes/shared-brand.php';" not in source:
        source = exact(source, "require_once __DIR__ . '/includes/tracking-query.php';", "require_once __DIR__ . '/includes/tracking-query.php';\nrequire_once __DIR__ . '/includes/shared-brand.php';")
        source = exact(source, "function wa_link($message) { return 'https://wa.me/6285340382029?text=' . rawurlencode($message); }", "function wa_link($message) { return kan_shared_whatsapp($message); }")
        source = exact(source, "</head><body><?php readfile(__DIR__.'/includes/refresh-header.html'); ?>", '<?php kan_shared_head(); ?>\n</head><body class="kan-site"><?php kan_shared_header(parse_url($canonical, PHP_URL_PATH)); ?>')
        source = exact(source, "<?php readfile(__DIR__.'/includes/refresh-footer.html'); ?>", "<?php kan_shared_footer(); ?>")
        source = exact(source, '<main id="main">', '<main id="main" tabindex="-1">')
    if source.count("kan_shared_head();") != 1 or source.count("kan_shared_header(") != 1 or source.count("kan_shared_footer();") != 1:
        raise ValueError("Unexpected PHP presentation binding")
    return version_legacy_scripts(source, script_versions)

def build(repo, baseline_repo=None):
    repo = Path(repo).resolve(); source_root = Path(baseline_repo).resolve() if baseline_repo else repo
    cfg = validate(json.loads(read(repo, CONFIG)))
    inputs = json.loads(read(repo, INPUTS))
    if inputs.get("schema_version") != 1 or inputs.get("base_commit") != BASE_COMMIT or inputs.get("groups") != COUNTS:
        raise ValueError("Unexpected input pin")
    old_manifest = json.loads(read(repo, MANIFEST)) if (repo / MANIFEST).is_file() and not baseline_repo else {}
    prior = {entry["path"]: entry["sha256"] for entry in old_manifest.get("outputs", [])}
    prior_modules = {entry["path"]: entry.get("pre_main_sha256") for entry in old_manifest.get("managed_sources", [])}
    pinned_inputs = {entry["path"]: entry["git_blob"] for entry in inputs["files"]}
    sources = {}
    for entry in inputs["files"]:
        raw = read(source_root, entry["path"])
        pinned = git_blob(raw) == entry["git_blob"] and len(raw) == entry["bytes"]
        managed = entry["path"] != REGISTRY and digest(raw) == prior.get(entry["path"])
        if not pinned and not managed:
            raise ValueError("Unreviewed source changed: " + entry["path"])
        sources[entry["path"]] = raw
    if len(sources) != 498 or REGISTRY not in sources:
        raise ValueError("Incomplete input coverage")
    registry = json.loads(sources[REGISTRY])
    if registry.get("version") != 3 or registry.get("domain") != "https://www.3dkanadvertising.store":
        raise ValueError("Unexpected registry")
    if {g: len(es) for g, es in registry["groups"].items()} != COUNTS:
        raise ValueError("Registry family coverage changed")
    routes = [entry["path"] for es in registry["groups"].values() for entry in es]
    if len(routes) != 500 or len(set(routes)) != 500:
        raise ValueError("Registry URL set changed")
    docs = { "public_html/" + entry["file"]: entry["path"] for group, entries in registry["groups"].items() if group != "layanan" for entry in entries }
    docs["public_html/404.html"] = "/404.html"
    if len(docs) != 494 or any(path not in sources for path in docs):
        raise ValueError("Document coverage changed")
    templates = {}
    for key, (path, expected) in TEMPLATES.items():
        raw = read(repo, path)
        if digest(raw) != expected:
            raise ValueError("Presentation template changed: " + path)
        templates[key] = raw.decode("utf-8")
    design = read(repo, DESIGN)
    if digest(design) != DESIGN_SHA or re.search(rb"&(gt|lt|amp);", design):
        raise ValueError("Design-system source/hash/entity guard failed")
    if digest(read(repo, CONTROLLER)) != CONTROLLER_SHA:
        raise ValueError("Frozen R6 controller changed")
    script_versions = {}
    for path, expected in sorted(LEGACY_SCRIPTS.items()):
        actual = digest(read(repo, "public_html" + path))
        if actual != expected:
            raise ValueError("Changed navigation handler source: " + path)
        script_versions[path] = actual
    logo = cfg["brand"]["logo_primary"]
    if digest(read(repo, "public_html" + logo["path"])) != logo["sha256"]:
        raise ValueError("Logo master bytes do not match declared revision")
    if logo.get("screen_derivative"):
        if git_blob(read(repo, "public_html" + logo["screen_derivative"]["path"])) != logo["screen_derivative"]["git_blob"]:
            raise ValueError("Declared screen derivative bytes changed")
    out = {}
    out[TOKENS] = tokens(cfg)
    head_markup = '<link rel="stylesheet" href="/assets/ui/brand-tokens.css?v=' + digest(out[TOKENS])[:16] + '"><link rel="stylesheet" href="/assets/ui/design-system.css?v=' + digest(design)[:16] + '"><script src="/assets/ui/frontend.js?v=' + CONTROLLER_SHA[:16] + '" defer></script>'
    out[HEAD] = (head_markup + "\n").encode("utf-8")
    generic_header, generic_footer = render_shell(cfg, templates)
    out[HEADER] = (generic_header + "\n").encode("utf-8")
    out[FOOTER] = (generic_footer + "\n").encode("utf-8")
    out[PUBLIC_CONFIG] = json_bytes(cfg)
    out[ADAPTER] = PHP_ADAPTER.encode("ascii")
    managed_sources = []
    for path, route in sorted(docs.items()):
        original = sources[path].decode("utf-8")
        if not baseline_repo and git_blob(sources[path]) != pinned_inputs[path]:
            expected_module = prior_modules.get(path)
            if not expected_module or digest(pre_main_content(original).encode("utf-8")) != expected_module:
                raise ValueError("Pinned baseline rebuild required for pre-main module: " + path)
        rendered = static_document(original, cfg, templates, route, head_markup, script_versions)
        out[path] = rendered.encode("utf-8")
        parsed = Tags(rendered); main = parsed.one("main")
        managed_sources.append({"path": path, "main_sha256": digest(rendered[main["start"]:main["end"]].encode("utf-8")),
                                "pre_main_sha256": digest(pre_main_content(rendered).encode("utf-8"))})
    php_source = sources["public_html/seo.php"].decode("utf-8")
    out["public_html/seo.php"] = php_document(php_source, script_versions).encode("utf-8")
    manifest = {"schema_version": 1, "base_commit": BASE_COMMIT, "config_sha256": digest(json_bytes(cfg)),
                "registry_sha256": digest(sources[REGISTRY]), "route_count": 500, "groups": COUNTS,
                "managed_sources": managed_sources, "outputs": [
                    {"path": path, "bytes": len(raw), "sha256": digest(raw), "git_blob": git_blob(raw)}
                    for path, raw in sorted(out.items())]}
    out[MANIFEST] = json_bytes(manifest)
    return out

def emit_transfer(repo, outputs):
    # Use the same minimum scanner as deployment. Never print matched values.
    scanner_path = repo / "scripts/check_site.py"
    if scanner_path.is_symlink() or not scanner_path.is_file():
        raise ValueError("Deployment scanner is missing")
    spec = importlib.util.spec_from_file_location("kan_shared_scan", scanner_path)
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    for path, raw in sorted(outputs.items()):
        relative = path.removeprefix("public_html/")
        categories = scanner.credential_categories(raw, relative=relative)
        if categories:
            raise ValueError("Public transfer rejected: " + path + " [" + ",".join(categories) + "]")
    payload = json.dumps({path: raw.decode("utf-8") for path, raw in sorted(outputs.items())},
                         ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(payload) > 20_000_000:
        raise ValueError("Public transfer exceeds bounded payload")
    print("SHARED_BRAND_TREE_IDENTITY=" + json.dumps({"sha256": digest(payload), "bytes": len(payload), "files": len(outputs)}, sort_keys=True))
    print("SHARED_BRAND_TREE_DATA_B64=" + base64.b64encode(zlib.compress(payload, level=9)).decode("ascii"))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--baseline")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--emit-transfer", action="store_true", help="Emit only scanned, bounded public build output")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    outputs = build(repo, args.baseline)
    changed = []
    for path, raw in sorted(outputs.items()):
        target = repo / path
        if not target.is_file() or target.read_bytes() != raw:
            changed.append(path)
            if not args.check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
    print(json.dumps({"routes": 500, "managed_html_documents": 494, "outputs": len(outputs), "changed": changed}, sort_keys=True))
    if args.check and changed:
        raise SystemExit(1)
    if args.emit_transfer:
        emit_transfer(repo, outputs)

if __name__ == "__main__":
    main()
