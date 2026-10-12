"""Keep credential checks strict without confusing public asset names for keys."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_site.py"
SPEC = importlib.util.spec_from_file_location("check_site_under_test", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class CredentialBoundaryTests(unittest.TestCase):
    def test_public_desk_image_slugs_are_not_credentials(self):
        names = [
            b"digital-and-handwritten-brainstorming-tools-on-a-wooden-desk-"
            b"with-notes-and-computer-in-the-workspace-generatedidentifier",
            b"overhead-view-of-a-business-desk-with-documents-and-calculations-"
            b"for-the-annual-financial-budget-generatedidentifier",
        ]
        for name in names:
            with self.subTest(name=name):
                html = b'<meta property="og:image" content="/images/0/123/' + name + b'.jpeg">'
                self.assertIsNone(CHECK.SECRET_PATTERN.search(html))

    def test_standalone_synthetic_provider_keys_still_match(self):
        # Generated placeholders only; no real credentials are used by tests.
        tokens = [
            b"sk-" + b"A" * 40,
            b"sk-proj-" + b"A" * 40,
            b"ghp_" + b"A" * 36,
            b"github_pat_" + b"A" * 50,
            b"AKIA" + b"A" * 16,
        ]
        for token in tokens:
            for surrounding in [b'"%s"', b'Bearer %s\n', b"token=%s;"]:
                with self.subTest(prefix=token[:8], surrounding=surrounding):
                    self.assertIsNotNone(CHECK.SECRET_PATTERN.search(surrounding % token))

    def test_private_key_header_still_matches(self):
        self.assertIsNotNone(CHECK.SECRET_PATTERN.search(
            b"-----BEGIN OPENSSH PRIVATE KEY-----\nplaceholder\n"
        ))


class LiteralCredentialTests(unittest.TestCase):
    def test_ordinary_php_json_js_and_config_credentials_are_detected(self):
        examples = [
            (b"$ftpPassword = 'synthetic-ftps-password-123';", "literal-password"),
            (b"$dbpass = 'synthetic-db-password-123';", "literal-password"),
            (b"$smtppass = 'synthetic-mail-password-123';", "literal-password"),
            (b"define('SMTP_PASSWORD', 'synthetic-mail-password-123');", "literal-password"),
            (b'{"database_password": "synthetic-db-password-123"}', "literal-password"),
            (b"$settings['password'] = 'synthetic-password-123';", "literal-password"),
            (b"const clientSecret = 'synthetic-secret-123';", "literal-secret-or-token"),
            (b"const secret_key = 'synthetic-secret-key-123';", "literal-secret-or-token"),
            (b'Authorization: "Bearer synthetic-token-123"', "literal-secret-or-token"),
            (b'config.access_token = "synthetic-access-token-123";', "literal-secret-or-token"),
            (b"FTP_PASSWORD=synthetic-unquoted-password-123\n", "literal-password"),
            (b"SetEnv SMTP_PASSWORD synthetic-apache-password-123\n", "literal-password"),
            (b'<password>synthetic-xml-password-123</password>', "literal-password"),
            (b'{"ftp_username": "synthetic-service-user"}', "literal-service-credential"),
        ]
        for data, category in examples:
            with self.subTest(category=category, syntax=data[:20]):
                self.assertIn(category, CHECK.credential_categories(data))

    def test_credential_bearing_urls_and_encoded_url_text_are_detected(self):
        examples = [
            b'ftp://synthetic-user:synthetic-pass@example.invalid/private',
            b'https://synthetic-user:synthetic-pass@example.invalid/api',
            b'mysql://synthetic-user:synthetic-pass@example.invalid/database',
            b'https://example.invalid/api?access_token=synthetic-token-123',
            b'https://example.invalid/api?other=public&amp;password=synthetic-password-123',
            br'ftp:\/\/synthetic-user:synthetic-pass@example.invalid/private',
        ]
        for data in examples:
            with self.subTest(scheme=data.split(b":", 1)[0]):
                self.assertIn("credential-bearing-url", CHECK.credential_categories(data))

    def test_dynamic_lookups_empty_values_and_clear_placeholders_are_accepted(self):
        examples = [
            b"$password = getenv('FTP_PASSWORD');",
            b"$secret = $_POST['secret'];",
            b"$turnstileCaptchaSecret = $attribute['value'];",
            b"'password' => $_ENV['DB_PASSWORD'],",
            b"const token = process.env.ACCESS_TOKEN;",
            b"password = os.getenv('DB_PASSWORD')\n",
            b'{"password": "", "secret": null, "token": "  "}',
            b"define('DB_PASSWORD', 'CHANGE_ME');",
            b'{"password": "YOUR_PASSWORD_HERE", "secret": "<INSERT_SECRET>", "token": "${TOKEN}"}',
            b'{"password": "REDACTED", "secret": "********", "token": "{{API_TOKEN}}"}',
            b'ftp://placeholder-user:${FTP_PASSWORD}@example.invalid/private',
            b'https://example.invalid/api?access_token=%24%7BTOKEN%7D',
        ]
        for data in examples:
            with self.subTest(syntax=data[:25]):
                self.assertEqual(CHECK.credential_categories(data), [])

    def test_public_business_text_and_policy_fields_are_accepted(self):
        data = b"""{
          "email": "public@example.invalid", "phone": "+62000000000",
          "site_url": "https://example.invalid/contact?utm_source=public",
          "password_policy": "Use at least eight characters",
          "token_label": "Security code", "secret_description": "Form configuration"
        }"""
        self.assertEqual(CHECK.credential_categories(data), [])

    def test_public_browser_exception_requires_exact_field_fingerprint_and_path(self):
        value = "synthetic-public-browser-value-123"
        path = "reviewed/index.html"
        reviewed = {"googleMapsEmbedApiKey": {
            "sha256": CHECK.hashlib.sha256(value.encode()).hexdigest(),
            "paths": frozenset({path}),
        }}
        field = f"webcard.googleMapsEmbedApiKey='{value}';".encode()
        with patch.dict(CHECK.REVIEWED_BROWSER_KEYS, reviewed, clear=True):
            self.assertEqual(CHECK.credential_categories(field, relative=path), [])
            for unreviewed_path in [None, "unreviewed/index.html"]:
                self.assertEqual(CHECK.credential_categories(field, relative=unreviewed_path),
                                 ["literal-secret-or-token"])
            changed = field.replace(value.encode(), b"different-synthetic-browser-value")
            self.assertEqual(CHECK.credential_categories(changed, relative=path),
                             ["literal-secret-or-token"])
            other_field = f"server.api_key='{value}';".encode()
            self.assertEqual(CHECK.credential_categories(other_field, relative=path),
                             ["literal-secret-or-token"])
            password = f"FTP_PASSWORD='{value}'".encode()
            self.assertEqual(CHECK.credential_categories(password, relative=path),
                             ["literal-password"])

    def test_css_svg_htaccess_and_xml_payload_findings_do_not_print_values(self):
        workspace = SCRIPT.parents[1]
        with tempfile.TemporaryDirectory(prefix=".credential-test-", dir=workspace) as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(workspace))
            site = Path(folder) / "public_html"
            site.mkdir()
            value = "synthetic-value-never-in-diagnostics"
            fixtures = {
                "styles.css": f"/* ftp_password = '{value}' */",
                "diagram.svg": f"<svg><!-- smtp_password = '{value}' --></svg>",
                ".htaccess": f"SetEnv DB_PASSWORD {value}\n",
                "config.xml": f"<settings><password>{value}</password></settings>",
            }
            for name, data in fixtures.items():
                (site / name).write_text(data, encoding="utf-8")
            check = CHECK.SiteCheck(Path(folder))
            check.check_payload()
            self.assertEqual(len(check.errors), len(fixtures))
            for name in fixtures:
                self.assertTrue(any(name in error and "[literal-password]" in error
                                    for error in check.errors))
            self.assertNotIn(value, "\n".join(check.errors))


if __name__ == "__main__":
    unittest.main()
