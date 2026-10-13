"""Focused cloud-only SEO regression tests. No hosting or network requests.
Run: SEO_BASELINE_DIR=<a73 public_html archive> python tests/seo_content_test.py
The baseline must be the pinned a73 bytes; fixtures only change temporary copies.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public_html"
PINNED = {
    "seo.php": "94ca462126c062ed4156afdce01be6db265b2f3e7a647dca92723ac2b1409206",
    "includes/refresh-data.json": "c3d0af199f34ea902afa5044d3f8bf75bf41468bd46df4a9ff92b36b7c6da50c",
    "projects.html": "ebfc8e66ae7f94912988eeca684519e6282400eec7066a65ee7a85c59711b725",
}
FILES = ("seo.php", "includes/refresh-data.json", "includes/tracking-query.php",
         "includes/refresh-header.html", "includes/refresh-footer.html", "404.html")
LEGACY = ("name", "symbol", "intro", "body", "options", "guide", "image")
OPTIONAL = ("seo_title", "seo_description", "detail_heading", "detail_sections")

class Page(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.nodes, self.stack = [], []
        self.feed(body)
    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "text": "",
                "ancestors": [n["attrs"].get("id") for n in self.stack]}
        self.nodes.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)
    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return
    def handle_data(self, data):
        for node in self.stack:
            node["text"] += data
    def find(self, tag, **attrs):
        return [n for n in self.nodes if n["tag"] == tag
                and all(n["attrs"].get(k) == v for k, v in attrs.items())]
    def one(self, tag, **attrs):
        found = self.find(tag, **attrs)
        if len(found) != 1:
            raise AssertionError("Expected exactly one " + tag + " " + str(attrs))
        return found[0]

PHP_RUNNER = r"""
$site=$argv[1]; $_SERVER['REQUEST_URI']=$argv[2];
$_SERVER['REQUEST_METHOD']='GET'; $_SERVER['HTTP_HOST']='www.3dkanadvertising.store';
$_SERVER['HTTPS']='on'; $_GET=json_decode($argv[3],true); $_POST=[];
http_response_code(200); ob_start();
register_shutdown_function(function(){
 $body=ob_get_clean();
 echo json_encode(['status'=>http_response_code(),'body'=>$body],
                  JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
});
include $site.'/seo.php';
"""

class SeoContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = os.environ.get("SEO_BASELINE_DIR")
        if not raw:
            raise RuntimeError("SEO_BASELINE_DIR must point to the pinned a73 public_html archive")
        cls.baseline = Path(raw).resolve(strict=True)
        for name, expected in PINNED.items():
            file = cls.baseline / name
            if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                raise RuntimeError("Pinned a73 baseline mismatch: " + name)
        cls.php = shutil.which(os.environ.get("PHP_BIN", "php"))
        if not cls.php:
            raise RuntimeError("PHP CLI is required; these render checks cannot be skipped")
        cls.temp = tempfile.TemporaryDirectory(prefix="seo-focused-")
        cls.old = cls.prepare(cls.baseline, "baseline")
        cls.new = cls.prepare(PUBLIC, "candidate")
        cls.old_data = json.loads((cls.old / "includes/refresh-data.json").read_text(encoding="utf-8"))
        cls.new_data = json.loads((cls.new / "includes/refresh-data.json").read_text(encoding="utf-8"))
        cls.neon = cls.new_data["services"]["neon-box"]
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
    @classmethod
    def prepare(cls, source, name):
        target = Path(cls.temp.name) / name
        for relative in FILES:
            original = source / relative
            if original.is_symlink() or not original.is_file():
                raise RuntimeError("Missing/unsafe renderer dependency: " + relative)
            file = target / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, file)
        return target
    def render(self, site=None, uri="/layanan/neon-box", params=None):
        command = [self.php, "-d", "allow_url_fopen=0", "-d", "allow_url_include=0",
                   "-d", "display_errors=stderr", "-d", "log_errors=0",
                   "-d", "disable_functions=curl_exec,curl_multi_exec,fsockopen,pfsockopen,"
                         "stream_socket_client,stream_socket_server,mail,exec,shell_exec,"
                         "system,passthru,popen,proc_open", "-r", PHP_RUNNER,
                   str(site or self.new), uri, json.dumps(params or {})]
        result = subprocess.run(command, capture_output=True, timeout=10, check=True)
        self.assertEqual(result.stderr, b"", "PHP emitted a warning/error")
        return json.loads(result.stdout.decode("utf-8"))
    def fixture(self, name, change):
        target = self.prepare(self.new, name)
        data = copy.deepcopy(self.new_data)
        change(data["services"]["neon-box"])
        (target / "includes/refresh-data.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return target
    def reject(self, name, change):
        response = self.render(self.fixture(name, change))
        self.assertEqual(response["status"], 503)
        self.assertEqual(response["body"], "Halaman sementara tidak tersedia.")
        self.assertNotIn("<head", response["body"])

    def test_01_legacy_values_and_other_registry_data(self):
        self.assertEqual(set(self.old_data), set(self.new_data))
        self.assertEqual(set(self.old_data["services"]), set(self.new_data["services"]))
        for key in self.old_data:
            if key != "services":
                self.assertEqual(self.old_data[key], self.new_data[key], key)
        for slug, old in self.old_data["services"].items():
            new = self.new_data["services"][slug]
            if slug == "neon-box":
                self.assertEqual({k: old[k] for k in LEGACY}, {k: new[k] for k in LEGACY})
                self.assertEqual(set(new), set(old) | set(OPTIONAL))
            else:
                self.assertEqual(old, new, slug)

    def test_02_six_other_services_render_byte_identically(self):
        slugs = sorted(set(self.old_data["services"]) - {"neon-box"})
        self.assertEqual(len(slugs), 6)
        for slug in slugs:
            with self.subTest(slug=slug):
                old = self.render(self.old, "/layanan/" + slug)
                new = self.render(self.new, "/layanan/" + slug)
                self.assertEqual(old["status"], 200)
                self.assertEqual(new, old)

    def test_03_metadata_canonical_robots_and_schema(self):
        response = self.render()
        self.assertEqual(response["status"], 200)
        page = Page(response["body"])
        self.assertEqual(page.one("title")["text"], self.neon["seo_title"])
        self.assertEqual(page.one("meta", name="description")["attrs"]["content"], self.neon["seo_description"])
        self.assertEqual(page.one("meta", property="og:title")["attrs"]["content"], self.neon["seo_title"])
        self.assertEqual(page.one("meta", property="og:description")["attrs"]["content"], self.neon["seo_description"])
        canonical = "https://www.3dkanadvertising.store/layanan/neon-box"
        self.assertEqual(page.one("link", rel="canonical")["attrs"]["href"], canonical)
        self.assertEqual(page.one("meta", property="og:url")["attrs"]["content"], canonical)
        old_page = Page(self.render(self.old)["body"])
        self.assertEqual(page.one("meta", name="robots")["attrs"], old_page.one("meta", name="robots")["attrs"])
        graph = json.loads(page.one("script", type="application/ld+json")["text"])
        service = [record for record in graph if record.get("@type") == "Service"]
        self.assertEqual(len(service), 1)
        self.assertEqual(service[0]["description"], self.neon["seo_description"])
        self.assertEqual(service[0]["url"], canonical)
        self.assertFalse(any(record.get("@type") in {"Offer", "AggregateRating", "VideoObject"} for record in graph))

    def test_04_one_h1_three_new_sections_and_exact_links(self):
        page = Page(self.render()["body"])
        self.assertEqual(page.one("h1")["text"], self.neon["detail_heading"])
        sections = self.neon["detail_sections"]
        self.assertEqual(len(sections), 3)
        old = Page(self.render(self.old)["body"])
        self.assertEqual(len(page.find("h2")), len(old.find("h2")) + 3)
        ids = [n["attrs"]["id"] for n in page.nodes if "id" in n["attrs"]]
        self.assertEqual(len(ids), len(set(ids)))
        for section in sections:
            element = page.one("section", id="service-detail-" + section["id"])
            self.assertEqual(element["attrs"]["aria-labelledby"], "service-heading-" + section["id"])
            self.assertEqual(page.one("h2", id="service-heading-" + section["id"])["text"], section["heading"])
            for paragraph in section["paragraphs"]:
                self.assertEqual(sum(n["text"] == paragraph for n in page.find("p")), 1)
            for link in section["links"]:
                matches = [n for n in page.find("a", href=link["href"])
                           if "service-detail-" + section["id"] in n["ancestors"]]
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0]["text"], link["label"])

    def test_05_city_redirect_preserved(self):
        old = self.render(self.old, "/layanan/neon-box/makassar")
        new = self.render(self.new, "/layanan/neon-box/makassar")
        self.assertEqual(old, {"status": 301, "body": ""})
        self.assertEqual(new, old)

    def test_06_two_contextual_project_backlinks_only(self):
        old_html = (self.baseline / "projects.html").read_text(encoding="utf-8")
        new_html = (PUBLIC / "projects.html").read_text(encoding="utf-8")
        additions = [
            '<a class="case-cta" href="/layanan/neon-box">Pilihan dan spesifikasi neon box ↗</a>',
            '<a class="case-cta" href="/layanan/neon-box">Bahas pilihan neon box ↗</a>',
        ]
        restored = new_html
        page = Page(new_html)
        for case_id, addition in zip(("gadget-solution", "shop-sign-retail"), additions):
            self.assertEqual(restored.count(addition), 1)
            links = [n for n in page.find("a", href="/layanan/neon-box")
                     if case_id in n["ancestors"] and n["attrs"].get("class") == "case-cta"]
            self.assertEqual(len(links), 1, case_id)
            restored = restored.replace(addition, "", 1)
        self.assertEqual(restored, old_html)

    def test_07_optional_absence_retains_legacy_render(self):
        target = self.fixture("no-editorial", lambda record: [record.pop(k) for k in OPTIONAL])
        self.assertEqual(self.render(target), self.render(self.old))

    def test_08_text_is_escaped_once(self):
        value = '<img src=x onerror="synthetic()"> & "quoted" \'single\''
        def change(record):
            record["seo_title"] = value
            record["seo_description"] = value
            record["detail_heading"] = value
            record["detail_sections"][0]["heading"] = value
            record["detail_sections"][0]["paragraphs"] = [value]
            record["detail_sections"][0]["links"][0]["label"] = value
        response = self.render(self.fixture("escaped", change))
        self.assertEqual(response["status"], 200)
        page = Page(response["body"])
        self.assertEqual(page.one("title")["text"], value)
        self.assertEqual(page.one("h1")["text"], value)
        self.assertEqual(page.one("meta", name="description")["attrs"]["content"], value)
        self.assertFalse(page.find("img", src="x"))
        self.assertNotIn("<img src=x", response["body"])
        self.assertIn("&lt;img", response["body"])
        self.assertNotIn("&amp;lt;img", response["body"])
        graph = json.loads(page.one("script", type="application/ld+json")["text"])
        self.assertEqual(next(n for n in graph if n.get("@type") == "Service")["description"], value)

    def test_09_invalid_metadata_type(self):
        for key in ("seo_title", "seo_description", "detail_heading"):
            with self.subTest(key=key):
                self.reject("type-" + key, lambda r, key=key: r.__setitem__(key, ["synthetic"]))

    def test_10_invalid_metadata_bounds(self):
        for key, limit in (("seo_title", 160), ("seo_description", 320), ("detail_heading", 200)):
            with self.subTest(key=key):
                self.reject("long-" + key, lambda r, key=key, limit=limit: r.__setitem__(key, "x" * (limit + 1)))

    def test_11_invalid_sections_type(self):
        self.reject("section-type", lambda r: r.__setitem__("detail_sections", "synthetic"))

    def test_12_duplicate_section_id(self):
        self.reject("duplicate", lambda r: r["detail_sections"][1].__setitem__("id", r["detail_sections"][0]["id"]))

    def test_13_unsafe_link(self):
        for index, href in enumerate(("javascript:synthetic()", "https://example.invalid/",
                                      "//example.invalid/", "/projects.html#unknown")):
            with self.subTest(href=href):
                self.reject("href-" + str(index), lambda r, href=href: r["detail_sections"][0]["links"][0].__setitem__("href", href))

    def test_14_invalid_paragraph_type(self):
        self.reject("paragraph-type", lambda r: r["detail_sections"][0].__setitem__("paragraphs", [123]))

    def test_15_unknown_section_field(self):
        self.reject("unknown-field", lambda r: r["detail_sections"][0].__setitem__("private_note", "synthetic"))

    def test_16_invalid_link_shape(self):
        self.reject("link-shape", lambda r: r["detail_sections"][0]["links"][0].__setitem__("extra", "synthetic"))

    def test_17_control_character(self):
        self.reject("control-char", lambda r: r.__setitem__("seo_title", "synthetic\u0000value"))

    def test_18_preserved_canonical_redirect_and_unknown_route(self):
        self.assertEqual(self.render(uri="/seo.php", params={"produk": "neon-box"}),
                         self.render(self.old, "/seo.php", {"produk": "neon-box"}))
        self.assertEqual(self.render(uri="/seo.php", params={"produk": "neon-box"})["status"], 301)
        self.assertEqual(self.render(uri="/layanan/unknown"), self.render(self.old, "/layanan/unknown"))
        self.assertEqual(self.render(uri="/layanan/unknown")["status"], 404)

if __name__ == "__main__":
    unittest.main(verbosity=2)
