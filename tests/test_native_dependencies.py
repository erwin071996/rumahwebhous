"""Synthetic checks for the network-free integrity and path boundary helpers."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

FILE = Path(__file__).resolve().parents[1] / "scripts/prepare_native_qa.py"
SPEC = importlib.util.spec_from_file_location("native_fixture_under_test", FILE)
QA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QA)


class NativeFixtureTests(unittest.TestCase):
    def entry(self):
        data = b"body { color: black; }"
        return {"path": "/assets/qa.css", "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(), "mime": "text/css"}, data

    def test_paths_refuse_traversal_query_redirect_forms_and_bad_digest(self):
        entry, _ = self.entry()
        for path in ("/../secret", "//elsewhere.invalid/a", "/a\\b", "/a?query",
                     "/a#fragment", "/a%2f..", "/a//b", "relative"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    QA.validate_entry({**entry, "path": path})
        with self.assertRaises(ValueError):
            QA.validate_entry({**entry, "sha256": "bad"})
        with self.assertRaises(ValueError):
            QA.validate_entry({**entry, "checkoutSource": "../file"})

    def test_wrong_size_hash_and_mime_fail_closed(self):
        entry, data = self.entry()
        QA.verify_data(entry, data, "text/css; charset=utf-8")
        for payload in (data + b"x", b"x" * len(data)):
            with self.assertRaises(RuntimeError):
                QA.verify_data(entry, payload, "text/css")
        with self.assertRaises(RuntimeError):
            QA.verify_data(entry, data, "text/html")

    def test_redirects_are_refused(self):
        with self.assertRaises(RuntimeError):
            QA.NoRedirect().redirect_request(None, None, 302, None, None, "https://elsewhere.invalid")

    def test_https_reader_checks_final_url_and_bounds_read(self):
        entry, data = self.entry()
        class Response:
            status = 200
            headers = {"Content-Type": "text/css"}
            url = QA.ORIGIN + entry["path"]
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return self.url
            def read(self, limit):
                self.limit = limit
                return data
        response = Response()
        class Opener:
            def open(self, request, timeout):
                self.request, self.timeout = request, timeout
                return response
        opener = Opener()
        self.assertEqual(QA.read_public(entry, opener), (data, "text/css"))
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertEqual(opener.request.full_url, QA.ORIGIN + entry["path"])
        self.assertEqual(response.limit, entry["bytes"] + 1)
        response.url = "https://elsewhere.invalid/qa.css"
        with self.assertRaises(RuntimeError):
            QA.read_public(entry, opener)


if __name__ == "__main__":
    unittest.main()
