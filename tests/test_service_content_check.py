"""Synthetic service HTTP verifier regressions; no hosting, credentials, or CMS."""
import copy
import html
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

import importlib.util

def load_script(name, filename):
    source = Path(__file__).resolve().parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

deploy = load_script("service_deploy_under_test", "deploy_ftps.py")
import sys
checker = load_script("service_content_check", "service_content_check.py")
# Bind both import contexts to this trusted repository module for rollback mocks.
sys.modules["service_content_check"] = checker
sys.modules["scripts.service_content_check"] = checker
verify_service_content = checker.verify_service_content

DOMAIN = "https://www.3dkanadvertising.store"
SLUG = "neon-box"


def record():
    return {
        "name": "Synthetic Neon",
        "seo_title": "Synthetic Neon & Examples | Fixture",
        "seo_description": "Synthetic description; no customer or production data.",
        "detail_heading": "Synthetic Neon Detail",
        "detail_sections": [
            {"id": "example", "heading": "Synthetic Example",
             "paragraphs": ["Synthetic alpha & beta.", "Synthetic reference only."],
             "links": [{"href": "/projects.html#synthetic-project",
                        "label": "Synthetic project"}]},
            {"id": "choices", "heading": "Synthetic Choices",
             "paragraphs": ["Synthetic selection; confirm independently."],
             "links": []},
            {"id": "order", "heading": "Synthetic Order",
             "paragraphs": ["Synthetic planning.", "Synthetic review."],
             "links": [{"href": "/cara-pemesanan.html",
                        "label": "Synthetic ordering guide"}]},
        ],
    }


def section(detail):
    sid = "service-detail-" + detail["id"]
    hid = "service-heading-" + detail["id"]
    paragraphs = "".join("<p>" + html.escape(p) + "</p>" for p in detail["paragraphs"])
    links = "".join('<a href="' + html.escape(a["href"], quote=True) + '">' +
                    html.escape(a["label"]) + "</a>" for a in detail["links"])
    return ('<section id="' + sid + '" aria-labelledby="' + hid + '"><div>' +
            '<h2 id="' + hid + '">' + html.escape(detail["heading"]) + "</h2>" +
            paragraphs + links + "</div></section>")


def render(expected):
    canonical = DOMAIN + "/layanan/" + SLUG
    graph = [
        {"@type": "Organization", "@id": DOMAIN + "/#organization",
         "name": "Synthetic Organization"},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Beranda",
             "item": DOMAIN + "/"},
            {"@type": "ListItem", "position": 2, "name": expected["name"],
             "item": canonical}]},
        {"@type": "Service", "name": expected["name"],
         "serviceType": expected["name"], "description": expected["seo_description"],
         "url": canonical, "provider": {"@id": DOMAIN + "/#organization"},
         "areaServed": {"@type": "AdministrativeArea", "name": "Sulawesi Selatan"}},
    ]
    metas = [
        ("name", "description", expected["seo_description"]),
        ("name", "robots", "index,follow,max-image-preview:large"),
        ("property", "og:title", expected["seo_title"]),
        ("property", "og:description", expected["seo_description"]),
        ("property", "og:url", canonical),
    ]
    head = ('<meta charset="utf-8"><meta name="viewport" content="width=device-width">' +
            "<title>" + html.escape(expected["seo_title"]) + "</title>" +
            '<link rel="canonical" href="' + canonical + '">' +
            "".join('<meta ' + attr + '="' + name + '" content="' +
                    html.escape(value, quote=True) + '">' for attr, name, value in metas) +
            '<script type="application/ld+json">' +
            json.dumps(graph, ensure_ascii=False, separators=(",", ":")) + "</script>")
    return ('<!doctype html><html lang="id"><head>' + head + '</head><body>' +
            '<header><a href="/">Synthetic header</a></header><main>' +
            "<h1>" + html.escape(expected["detail_heading"]) + "</h1>" +
            '<aside><p>Unrelated legacy copy.</p><img src="/synthetic.webp"><br><hr></aside>' +
            "".join(section(d) for d in expected["detail_sections"]) +
            '</main><footer>Synthetic footer only.</footer></body></html>')


class ServiceContentCheckTests(unittest.TestCase):
    def setUp(self):
        self.expected = record()
        self.document = render(self.expected)

    def verify(self, document=None, expected=None):
        return verify_service_content(
            (self.document if document is None else document).encode("utf-8"),
            self.expected if expected is None else expected, domain=DOMAIN, slug=SLUG)

    def changed(self, old, new):
        self.assertEqual(self.document.count(old), 1, "Fixture mutation must be exact once")
        return self.document.replace(old, new, 1)

    def rejected(self, document, category):
        with self.assertRaisesRegex(RuntimeError, category):
            self.verify(document)

    def test_valid_void_tags_entities_and_legacy_copy(self):
        self.assertEqual(self.verify(), {
            "path": "/layanan/neon-box", "sections": 3,
            "rendered_content": "verified"})

    def test_valid_nested_inline_text(self):
        candidate = self.changed("<p>Synthetic alpha &amp; beta.</p>",
                                 "<p>Synthetic <strong>alpha</strong> &amp; beta.</p>")
        candidate = candidate.replace(">Synthetic project</a>",
                                      "><span>Synthetic project</span></a>")
        self.assertEqual(self.verify(candidate)["sections"], 3)

    def test_valid_self_closing_void_tags(self):
        candidate = self.document.replace('<meta charset="utf-8">',
                                          '<meta charset="utf-8"/>')
        candidate = candidate.replace('<img src="/synthetic.webp"><br><hr>',
                                      '<img src="/synthetic.webp"/><br/><hr/>')
        self.assertEqual(self.verify(candidate)["sections"], 3)

    def test_reject_non_bytes_input(self):
        with self.assertRaisesRegex(RuntimeError, "input type"):
            verify_service_content(self.document, self.expected, domain=DOMAIN, slug=SLUG)

    def test_reject_invalid_utf8(self):
        with self.assertRaisesRegex(RuntimeError, "response decoding"):
            verify_service_content(b"\xff", self.expected, domain=DOMAIN, slug=SLUG)

    def test_reject_missing_expected_fields(self):
        expected = copy.deepcopy(self.expected)
        expected.pop("seo_title")
        with self.assertRaisesRegex(RuntimeError, "expected fields"):
            self.verify(expected=expected)

    def test_reject_missing_section_links_contract(self):
        expected = copy.deepcopy(self.expected)
        expected["detail_sections"][1].pop("links")
        with self.assertRaisesRegex(RuntimeError, "expected section"):
            self.verify(expected=expected)

    def test_reject_stale_title(self):
        self.rejected(self.changed("<title>Synthetic Neon &amp; Examples | Fixture</title>",
                                   "<title>Stale fixture</title>"), "title")

    def test_reject_duplicate_title(self):
        self.rejected(self.changed("</title>", "</title><title>Duplicate</title>"), "title")

    def test_reject_stale_description(self):
        self.rejected(self.changed('name="description" content="' + self.expected["seo_description"] + '"',
                                   'name="description" content="Stale description"'), "metadata")

    def test_reject_duplicate_description_meta(self):
        self.rejected(self.changed("</head>", '<meta name="description" content="duplicate"></head>'),
                      "metadata")

    def test_reject_stale_og_title(self):
        self.rejected(self.changed('property="og:title" content="Synthetic Neon &amp; Examples | Fixture"',
                                   'property="og:title" content="Stale title"'), "metadata")

    def test_reject_stale_og_description(self):
        self.rejected(self.changed('property="og:description" content="' + self.expected["seo_description"] + '"',
                                   'property="og:description" content="Stale description"'), "metadata")

    def test_reject_wrong_og_url(self):
        self.rejected(self.changed('property="og:url" content="' + DOMAIN + '/layanan/neon-box"',
                                   'property="og:url" content="' + DOMAIN + '/layanan/wrong"'), "metadata")

    def test_reject_wrong_canonical(self):
        self.rejected(self.changed('rel="canonical" href="' + DOMAIN + '/layanan/neon-box"',
                                   'rel="canonical" href="' + DOMAIN + '/layanan/wrong"'), "canonical")

    def test_reject_duplicate_canonical(self):
        self.rejected(self.changed("</head>", '<link rel="canonical" href="' +
                                   DOMAIN + '/layanan/neon-box"></head>'), "canonical")

    def test_reject_noindex(self):
        self.rejected(self.changed('content="index,follow,max-image-preview:large"',
                                   'content="noindex,follow"'), "metadata")

    def test_reject_duplicate_h1(self):
        self.rejected(self.changed("</main>", "<h1>Duplicate</h1></main>"), "H1")

    def test_reject_stale_h1(self):
        self.rejected(self.changed("<h1>Synthetic Neon Detail</h1>",
                                   "<h1>Stale detail</h1>"), "H1")

    def test_reject_duplicate_section_id(self):
        self.rejected(self.changed("</main>", '<div id="service-detail-example"></div></main>'),
                      "duplicate IDs")

    def test_reject_wrong_heading_association(self):
        self.rejected(self.changed('aria-labelledby="service-heading-example"',
                                   'aria-labelledby="wrong-heading"'), "section identity")

    def test_reject_section_outside_main_even_with_text(self):
        original = section(self.expected["detail_sections"][0])
        candidate = self.changed(original, "")
        candidate = candidate.replace("</main>", "</main>" + original)
        self.rejected(candidate, "section identity")

    def test_reject_wrong_scoped_heading(self):
        self.rejected(self.changed('<h2 id="service-heading-example">Synthetic Example</h2>',
                                   '<h2 id="service-heading-example">Wrong heading</h2>'),
                      "section heading")

    def test_reject_expected_paragraph_only_outside_section(self):
        candidate = self.changed("<p>Synthetic reference only.</p>", "")
        candidate = candidate.replace("</main>", "<p>Synthetic reference only.</p></main>")
        self.rejected(candidate, "section paragraphs")

    def test_reject_unexpected_paragraph_inside_section(self):
        self.rejected(self.changed("<p>Synthetic reference only.</p>",
                                   "<p>Synthetic reference only.</p><p>Unexpected.</p>"),
                      "section paragraphs")

    def test_reject_expected_link_only_outside_section(self):
        anchor = '<a href="/projects.html#synthetic-project">Synthetic project</a>'
        candidate = self.changed(anchor, "")
        candidate = candidate.replace("</main>", anchor + "</main>")
        self.rejected(candidate, "section links")

    def test_reject_wrong_scoped_link(self):
        self.rejected(self.changed('href="/projects.html#synthetic-project"',
                                   'href="/projects.html#wrong-project"'), "section links")

    def test_reject_schema_json_failure(self):
        self.rejected(self.changed('<script type="application/ld+json">',
                                   '<script type="application/ld+json">invalid-json'), "schema JSON")

    def test_reject_duplicate_schema_script(self):
        self.rejected(self.changed("</head>", '<script type="application/ld+json">[]</script></head>'),
                      "schema envelope")

    def test_reject_duplicate_service_schema(self):
        start = self.document.index('<script type="application/ld+json">') + len('<script type="application/ld+json">')
        end = self.document.index("</script>", start)
        graph = json.loads(self.document[start:end])
        graph.append(copy.deepcopy(graph[-1]))
        candidate = self.document[:start] + json.dumps(graph, separators=(",", ":")) + self.document[end:]
        self.rejected(candidate, "schema duplicates")

    def mutate_schema(self, change):
        start = self.document.index('<script type="application/ld+json">') + len('<script type="application/ld+json">')
        end = self.document.index("</script>", start)
        graph = json.loads(self.document[start:end])
        change(graph)
        return self.document[:start] + json.dumps(graph, separators=(",", ":")) + self.document[end:]

    def test_reject_stale_service_description(self):
        self.rejected(self.mutate_schema(lambda graph: graph[-1].update(description="Stale description")),
                      "Service schema")

    def test_reject_wrong_provider(self):
        self.rejected(self.mutate_schema(lambda graph: graph[-1].update(provider={"@id": DOMAIN + "/wrong"})),
                      "Service schema")

    def test_reject_wrong_area(self):
        self.rejected(self.mutate_schema(lambda graph: graph[-1].update(areaServed={"@type": "AdministrativeArea", "name": "Wrong"})),
                      "Service schema")

    def test_reject_wrong_breadcrumb_target(self):
        def change(graph):
            graph[1]["itemListElement"][1]["item"] = DOMAIN + "/wrong"
        self.rejected(self.mutate_schema(change), "Breadcrumb schema")

    def test_reject_duplicate_main(self):
        self.rejected(self.changed("</body>", "<main></main></body>"), "head/main")



class DeploymentServiceGateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.site = Path(self.folder.name) / "public_html"
        (self.site / "includes").mkdir(parents=True)
        self.responses = {}
        rows = [{"path": "/synthetic/" + str(i)} for i in range(500)]
        (self.site / "includes/content-index.json").write_text(
            json.dumps({"groups": {"synthetic": rows}}), encoding="utf-8")
        current = {
            "/": b"<html>Synthetic current home</html>",
            "/projects.html": b"<html>Synthetic current portfolio</html>",
        }
        (self.site / "index.html").write_bytes(current["/"])
        (self.site / "projects.html").write_bytes(current["/projects.html"])
        self.responses.update(current)
        ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
        index = ET.Element("{" + ns + "}sitemapindex")
        for group in range(10):
            url = DOMAIN + "/sitemap-qa" + str(group) + ".xml"
            item = ET.SubElement(index, "{" + ns + "}sitemap")
            ET.SubElement(item, "{" + ns + "}loc").text = url
            child = ET.Element("{" + ns + "}urlset")
            for row in rows[group * 50:(group + 1) * 50]:
                entry = ET.SubElement(child, "{" + ns + "}url")
                ET.SubElement(entry, "{" + ns + "}loc").text = DOMAIN + row["path"]
            self.responses[url.removeprefix(DOMAIN)] = ET.tostring(child)
        self.responses["/sitemap.xml"] = ET.tostring(index)
        self.calls = []

    def configure(self, expected):
        (self.site / "includes/refresh-data.json").write_text(
            json.dumps({"services": {"neon-box": expected}}), encoding="utf-8")
        self.responses["/layanan/neon-box"] = render(record()).encode("utf-8")

    def respond(self, route):
        self.calls.append(route)
        return self.responses.get(route, b"<html>Synthetic sample</html>")

    def run_gate(self):
        with patch.object(deploy, "SITE", self.site), patch.object(
                deploy, "https", side_effect=self.respond):
            return deploy.verify_live()

    def test_legacy_without_optional_fields_remains_nine_samples(self):
        self.configure({"name": "Synthetic Neon"})
        self.assertEqual(self.run_gate(), {
            "sitemaps": 11, "unique_urls": 500, "http_samples": 9})
        self.assertNotIn("/layanan/neon-box", self.calls)

    def test_reviewed_service_adds_tenth_verified_sample(self):
        self.configure(record())
        result = self.run_gate()
        self.assertEqual(result["http_samples"], 10)
        self.assertEqual(result["service_content"], {
            "path": "/layanan/neon-box", "sections": 3,
            "rendered_content": "verified"})
        self.assertEqual(self.calls.count("/layanan/neon-box"), 1)

    def test_any_present_optional_field_cannot_skip_malformed_record(self):
        for key in ("seo_title", "seo_description", "detail_heading", "detail_sections"):
            with self.subTest(key=key):
                self.calls.clear()
                self.configure({"name": "Synthetic Neon", key: None})
                with self.assertRaisesRegex(RuntimeError, "expected fields"):
                    self.run_gate()
                self.assertEqual(self.calls.count("/layanan/neon-box"), 1)

    def test_stale_render_rejects_gate_despite_valid_static_samples(self):
        self.configure(record())
        self.responses["/layanan/neon-box"] = self.responses["/layanan/neon-box"].replace(
            b"<title>Synthetic Neon &amp; Examples | Fixture</title>",
            b"<title>Stale synthetic page</title>")
        with self.assertRaisesRegex(RuntimeError, "title"):
            self.run_gate()

    def test_service_failure_rolls_back_before_success_state_write(self):
        self.configure(record())
        old = b"Synthetic previous PHP source"
        desired = b"Synthetic reviewed PHP source"
        (self.site / "seo.php").write_bytes(desired)
        old_state = deploy.encode_successful_state("1" * 40)
        desired_state = deploy.encode_successful_state("2" * 40)
        files = {"seo.php": old, deploy.STATE_PATH: old_state}
        writes = []

        class MemoryTransport:
            def read(self, route):
                return files.get(route)
            def write(self, route, data, **kwargs):
                writes.append((route, data))
                files[route] = data
            def close(self):
                pass

        report = {"uploaded": [], "already_current": [], "rollback": "not needed"}
        transport, restore = MemoryTransport(), MemoryTransport()
        with patch.object(deploy, "SITE", self.site), patch.object(
                deploy, "REPORT", Path(self.folder.name) / "report"), patch.object(
                deploy, "previous", return_value=old), patch.object(
                deploy, "Server", return_value=restore), patch.object(
                deploy, "https", side_effect=self.respond), patch.object(
                checker, "verify_service_content",
                side_effect=RuntimeError("Reviewed service HTTP check failed: synthetic")) as check:
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                deploy.deploy_changes(transport, ["seo.php"], "1" * 40, report,
                                      state_update=(old_state, desired_state))
        check.assert_called_once()
        self.assertEqual(files["seo.php"], old)
        self.assertEqual(files[deploy.STATE_PATH], old_state)
        self.assertEqual(writes, [("seo.php", desired), ("seo.php", old)])
        self.assertEqual(report["rollback"], "verified")
        self.assertNotIn("successful_release_commit", report)
        self.assertNotIn("live", report)


if __name__ == "__main__":
    unittest.main()
