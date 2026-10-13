import contextlib
from email.message import Message
import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError

from scripts import check_worker_privacy as privacy


class PrivacyTests(unittest.TestCase):
    def safe_fetch(self, url):
        if url.startswith("http:"):
            return privacy.Headers(301, url.replace("http:", "https:", 1))
        if url.endswith(".store/"):
            return privacy.Headers(200)
        return privacy.Headers(401, challenges=('Basic realm="3DKanOwner"',))

    def test_all_paths_hosts_protocols_and_public_homepage(self):
        fetch = Mock(side_effect=self.safe_fetch)
        report = privacy.check_privacy(fetch)
        self.assertTrue(report["checks"]["anonymous_gate_verified"])
        self.assertFalse(report["checks"]["owner_login_verified"])
        self.assertTrue(report["checks"]["manual_owner_login_required"])
        self.assertEqual(len(report["results"]), 22)
        urls = {call.args[0] for call in fetch.call_args_list}
        for host in privacy.HOSTS:
            for path in privacy.PATHS:
                for scheme in ("http", "https"):
                    self.assertIn(f"{scheme}://{host}{path}", urls)

    def test_canonical_https_redirect_keeps_each_path(self):
        def fetch(url):
            if url.startswith("http:") or url.startswith("https://3dkan"):
                target = url.replace("http:", "https:", 1).replace("//3dkan", "//www.3dkan", 1)
                return privacy.Headers(308, target)
            return self.safe_fetch(url)

        self.assertTrue(privacy.check_privacy(fetch)["checks"]["anonymous_gate_verified"])

    def test_http_must_redirect_before_challenge_or_content(self):
        for response in [privacy.Headers(401, challenges=("Basic",)), privacy.Headers(200)]:
            with self.subTest(status=response.status):
                result = privacy._probe(privacy.HOSTS[0], privacy.PATHS[0], "http", True, Mock(return_value=response))
                self.assertFalse(result["checks"]["passed"])
                self.assertEqual(result["checks"]["result"], "http_first_response_not_https_redirect")

    def test_unsafe_redirects_never_followed_and_never_echoed(self):
        bad = [
            "https://foreign.invalid/pekerja-web/",
            "http://www.3dkanadvertising.store/pekerja-web/",
            "https://user:secret@3dkanadvertising.store/pekerja-web/",
            "https://3dkanadvertising.store:444/pekerja-web/",
            "https://3dkanadvertising.store/public/",
            "/pekerja-web/?secret=private",
            "/pekerja-web/#private",
            "https://[invalid/pekerja-web/",
            "https://3dkanadvertising.store/pekerja-web/\n",
            None,
        ]
        for location in bad:
            with self.subTest(location=location):
                fetch = Mock(return_value=privacy.Headers(302, location))
                result = privacy._probe(privacy.HOSTS[0], privacy.PATHS[0], "https", True, fetch)
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(result["checks"]["result"], "unsafe_redirect")
                self.assertFalse(result["checks"]["passed"])
                self.assertNotIn("secret", json.dumps(result))
                self.assertNotIn("foreign.invalid", json.dumps(result))

    def test_http_redirect_to_http_canonical_host_is_rejected(self):
        fetch = Mock(return_value=privacy.Headers(301, f"http://{privacy.HOSTS[1]}{privacy.PATHS[0]}"))
        result = privacy._probe(privacy.HOSTS[0], privacy.PATHS[0], "http", True, fetch)
        self.assertFalse(result["checks"]["passed"])
        self.assertEqual(fetch.call_count, 1)

    def test_direct_public_feed_or_missing_path_blocks_whole_gate(self):
        for code in (200, 403, 404, 500):
            with self.subTest(status=code):
                def fetch(url):
                    if url == f"https://{privacy.HOSTS[0]}/pekerja-web/status.json":
                        return privacy.Headers(code)
                    return self.safe_fetch(url)

                report = privacy.check_privacy(fetch)
                self.assertEqual(report["status"], "blocked")

    def test_challenge_scheme_cannot_be_faked_inside_quoted_realm(self):
        for challenge in ("Bearer", 'Bearer realm="thing, Basic realm=hidden"', "BasicFake realm=hidden"):
            with self.subTest(challenge=challenge):
                response = privacy.Headers(401, challenges=(challenge,))
                result = privacy._probe(privacy.HOSTS[0], privacy.PATHS[0], "https", True, Mock(return_value=response))
                self.assertFalse(result["checks"]["passed"])
        self.assertTrue(privacy._has_basic(('Bearer realm="example", bAsIc realm="Owner"',)))

    def test_network_failure_is_unknown_and_does_not_log_exception(self):
        report = privacy.check_privacy(Mock(side_effect=URLError("credential/private/path")))
        self.assertFalse(report["checks"]["anonymous_gate_verified"])
        self.assertTrue(all(result["status"] is None for result in report["results"]))
        self.assertNotIn("credential", json.dumps(report))
        self.assertNotIn("private", json.dumps(report))

    def test_redirect_loop_is_bounded(self):
        def fetch(url):
            target = url.replace("//3dkan", "//www.3dkan") if "//3dkan" in url else url.replace("//www.3dkan", "//3dkan")
            return privacy.Headers(302, target)

        mocked = Mock(side_effect=fetch)
        result = privacy._probe(privacy.HOSTS[0], privacy.PATHS[0], "https", True, mocked)
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(result["checks"]["result"], "redirect_loop")

    def test_homepage_authentication_blocks_gate(self):
        def fetch(url):
            if url.endswith(".store/"):
                return privacy.Headers(401, challenges=("Basic",))
            return self.safe_fetch(url)

        self.assertFalse(privacy.check_privacy(fetch)["checks"]["anonymous_gate_verified"])

    def test_transport_only_gets_headers_and_closes_without_body(self):
        headers = Message()
        headers["WWW-Authenticate"] = 'Basic realm="3DKanOwner"'
        response = Mock(status=401, headers=headers)
        response.read.side_effect = AssertionError("Body must never be read")
        opener = Mock()
        opener.open.return_value = response
        with patch.object(privacy, "_opener", return_value=opener):
            result = privacy.fetch_headers(f"https://{privacy.HOSTS[0]}{privacy.PATHS[0]}")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertFalse(request.has_header("Authorization"))
        self.assertFalse(request.has_header("Cookie"))
        self.assertEqual(result.status, 401)
        response.read.assert_not_called()
        response.close.assert_called_once()

    def test_transport_has_no_redirect_proxy_cookie_or_auth_handlers(self):
        self.assertEqual({type(handler).__name__ for handler in privacy._opener().handlers}, {"HTTPHandler", "HTTPSHandler"})

    def test_cli_rejects_custom_destinations_without_network(self):
        with patch.object(privacy, "check_privacy") as check, contextlib.redirect_stdout(io.StringIO()) as output:
            code = privacy.main(["--url", "https://foreign.invalid"])
        self.assertEqual(code, 2)
        check.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
