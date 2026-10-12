"""Synthetic publication fixtures; never use or print real credential values."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_site.py"
SPEC = importlib.util.spec_from_file_location("credential_literals_under_test", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class LiteralCredentialTests(unittest.TestCase):
    def test_ordinary_literals_and_fallbacks_are_rejected(self):
        values = [
            b'$password = "Synthetic9!";',
            b"$cfg['smtp_password'] = 'Synthetic9!';",
            b'{"ftp_password": "Synthetic9!"}',
            b'const clientSecret = "Synthetic9!";',
            b"define('DB_PASSWORD', 'Synthetic9!');",
            b'SetEnv SMTP_PASSWORD Synthetic9!\n',
            b'https://user:Synthetic9!@example.invalid/',
            b'$password = getenv("DB_PASSWORD") ?: "Synthetic9!";',
            b'password = env("DB_PASSWORD", "Synthetic9!");',
            b'const password = process.env.DB_PASSWORD || "Synthetic9!";',
            b'getenv("FTP_PASS") ?: "Synthetic9!";',
            b'env("SMTP_PWD", "Synthetic9!");',
            b'const password = process.env.FTP_PASS || "Synthetic9!";',
            b"$password = $_ENV['DB_PASSWORD'] ?? 'Synthetic9!';",
            b"$password = $_SERVER['FTP_PASS'] ?: 'Synthetic9!';",
            b"const password = process.env['DB_PASSWORD'] || 'Synthetic9!';",
            b"const password = process.env['SMTP_PWD'] ?? 'Synthetic9!';",
            b'password = "DemoSecret123";',
            b'api_key = "sk-' + b'A' * 40 + b'";',
        ]
        for index, value in enumerate(values):
            with self.subTest(case=index):
                self.assertTrue(CHECK.credential_categories(value))

    def test_env_reads_and_exact_placeholders_are_accepted(self):
        values = [
            b'$password = getenv("DB_PASSWORD");',
            b'const apiKey = process.env.API_KEY;',
            b'const password = process.env.FTP_PASS;',
            b"$password = $_ENV['DB_PASSWORD'];",
            b"$password = $_SERVER['FTP_PASS'];",
            b"const password = process.env['DB_PASSWORD'];",
            b'password = os.environ["PASSWORD"]',
            b'{"password": ""}',
            b'apiKey = "YOUR_API_KEY";',
            b'password = "CHANGE_ME";',
            b'client_secret = "REPLACE_ME";',
            b'password = "' + b"$" + b'{DB_PASSWORD}";',
            b'password = "{{ secrets.DB_PASSWORD }}";',
            b'password = "<DB_PASSWORD>";',
            b'<input type="password" name="password" value="">',
        ]
        for index, value in enumerate(values):
            with self.subTest(case=index):
                self.assertFalse(CHECK.credential_categories(value))

    def test_public_text_and_runtime_dependencies_fail_with_redacted_errors(self):
        synthetic = b"Synthetic9!"
        payloads = {
            "assets/example.css": b'/* api_key="' + synthetic + b'" */',
            "assets/example.svg": b'<svg><!-- password="' + synthetic + b'" --></svg>',
            ".htaccess": b"AuthUserFile /synthetic/auth-file\n",
        }
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            for name, data in payloads.items():
                file = repo / "public_html" / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(data)
            check = CHECK.SiteCheck(repo)
            check.check_payload()
            self.assertEqual(len(check.errors), len(payloads))
            self.assertNotIn(synthetic.decode(), "\n".join(check.errors))
            self.assertTrue(all("(value redacted)" in error for error in check.errors))

    def test_invalid_text_encoding_fails_closed_and_binary_scope_is_preserved(self):
        self.assertTrue(CHECK.credential_categories(b"\xffinvalid text"))
        self.assertTrue(CHECK.credential_categories(b"\x00invalid text"))
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            site = repo / "public_html"
            site.mkdir()
            (site / "example.png").write_bytes(b"\x89PNG\r\n" + b"sk-" + b"A" * 40)
            check = CHECK.SiteCheck(repo)
            check.check_payload()
            self.assertEqual(check.errors, [])


    def test_password_database_files_are_forbidden_at_any_depth(self):
        synthetic = "Synthetic9!"
        for name in (".htpasswd", "nested/.htpasswd", ".htdigest", "nested/.htdigest"):
            with self.subTest(path=name), tempfile.TemporaryDirectory() as folder:
                repo = Path(folder)
                file = repo / "public_html" / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("synthetic-user:" + synthetic, encoding="utf-8")
                check = CHECK.SiteCheck(repo)
                check.check_payload()
                self.assertEqual(len(check.errors), 1)
                self.assertIn("Credential/runtime file in payload:", check.errors[0])
                self.assertIn(name, check.errors[0])
                self.assertNotIn(synthetic, check.errors[0])

if __name__ == "__main__":
    unittest.main()
