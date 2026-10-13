#!/usr/bin/env python3
"""Harness self-tests only. The HTTP double must never be deployed."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from gateway_harness import (Check, CheckFailed, ContractError, Expectation,
                             Request, VECTORS, exchange, public_category, run_case, verify)

PRIVATE_MARKER = b"SYNTHETIC_PRIVATE_DRAFT_SENTINEL"


@contextmanager
def double(mode="reference"):
    # Test-double sessions are constants, never real sessions or login passwords.
    state = {"reads": 0, "writes": 0, "now": 1000, "mode": mode, "hits": 0}
    sessions = {
        "synthetic-active": ("owner", 1001, "synthetic-csrf-a"),
        "synthetic-non-owner": ("other", 1001, "synthetic-csrf-b"),
        "synthetic-at-boundary": ("owner", 1000, "synthetic-csrf-a"),
        "synthetic-expired": ("owner", 999, "synthetic-csrf-a"),
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.process()

        def do_POST(self):
            self.process()

        def process(self):
            state["hits"] += 1
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "https://example.invalid/cms-owner/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length)) if length else {}
            action = payload.get("action", "load")
            session = sessions.get(self.headers.get("Cookie", "").removeprefix("fixture_sid="))
            if mode == "trust-payload" and payload.get("serverIdentity") == "owner":
                session = ("owner", payload.get("expiresAt", 1001), "synthetic-csrf-a")
            if mode == "read-before-auth":
                state["reads"] += 1
            boundary_valid = (session is not None and session[1] >= state["now"]
                              if mode == "expiry-off-by-one" else
                              session is not None and session[1] > state["now"])
            authenticated = bool(session and session[0] == "owner" and boundary_valid)
            csrf_ok = bool(session and self.headers.get("X-Fixture-CSRF") == session[2])
            accepted = authenticated and (action == "load" or csrf_ok or mode == "skip-csrf")
            if accepted:
                state["reads"] += 1
                if action != "load":
                    state["writes"] += 1
                response = {"category": "ok"}
                status = 200
            else:
                if mode == "deny-but-write":
                    state["writes"] += 1
                response = {"category": "denied"}
                status = 403
                if mode == "leak-on-deny":
                    response["private"] = PRIVATE_MARKER.decode()
            data = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()

    class Fixture:
        base_url = f"http://127.0.0.1:{server.server_port}"

        def prepare(self, vector_id):
            state["reads"] = state["writes"] = 0
            session_id = "synthetic-active"
            csrf = "synthetic-csrf-a"
            action = "save"
            payload = {}
            if vector_id.startswith("anonymous-"):
                session_id = None
                action = vector_id.removeprefix("anonymous-")
            if vector_id == "forged-payload-identity":
                session_id = None
                payload = {"serverIdentity": "owner", "expiresAt": 999999,
                           "csrfVerified": True, "owner": True}
            if vector_id == "non-owner-session":
                session_id, csrf = "synthetic-non-owner", "synthetic-csrf-b"
            if vector_id == "csrf-missing-save":
                csrf = None
            if vector_id == "csrf-wrong-save":
                csrf = "synthetic-invalid-csrf"
            if vector_id == "csrf-cross-session-save":
                csrf = "synthetic-csrf-b"
            if vector_id == "csrf-missing-request-publish":
                csrf, action = None, "request-publish"
            if vector_id == "csrf-client-flag":
                csrf, payload = None, {"csrfVerified": True}
            if vector_id == "expired-session":
                session_id = "synthetic-expired"
            if vector_id == "expiry-at-boundary":
                session_id = "synthetic-at-boundary"
            if vector_id == "active-before-expiry":
                action = "load"
            if vector_id == "unknown-session-id":
                session_id = "synthetic-unknown"
            if vector_id == "payload-expiry-extension":
                session_id = "synthetic-expired"
                payload = {"expiresAt": 999999, "serverIdentity": "owner"}
            if vector_id == "logout-session-reuse":
                # A revoked synthetic SID, not proof of a real logout handler.
                session_id = "synthetic-revoked"
            headers = {}
            if session_id:
                headers["Cookie"] = "fixture_sid=" + session_id
            if csrf:
                headers["X-Fixture-CSRF"] = csrf
            denied = VECTORS[vector_id] == "deny"
            return Check(
                Request("POST", "/fixture", headers, {"action": action, **payload}),
                Expectation((403,) if denied else (200,),
                            {"category": "denied" if denied else "ok"},
                            forbidden_body_values=(PRIVATE_MARKER,)),
                state_unchanged=denied,
            )

        def state_fingerprint(self):
            return state["reads"], state["writes"]

    try:
        yield Fixture(), state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class HarnessTests(unittest.TestCase):
    def test_reference_double_accepts_all_17_vectors(self):
        with double() as (adapter, _):
            for name in VECTORS:
                with self.subTest(name=name):
                    run_case(adapter, name)

    def test_detects_trusted_payload_identity(self):
        with double("trust-payload") as (adapter, _):
            with self.assertRaises(CheckFailed):
                run_case(adapter, "forged-payload-identity")

    def test_detects_missing_wrong_cross_session_and_client_flag_csrf(self):
        with double("skip-csrf") as (adapter, _):
            for name in ("csrf-missing-save", "csrf-wrong-save", "csrf-cross-session-save",
                         "csrf-missing-request-publish", "csrf-client-flag"):
                with self.subTest(name=name), self.assertRaises(CheckFailed):
                    run_case(adapter, name)

    def test_detects_expiry_off_by_one(self):
        with double("expiry-off-by-one") as (adapter, _):
            with self.assertRaises(CheckFailed):
                run_case(adapter, "expiry-at-boundary")

    def test_detects_mutation_even_when_response_denies(self):
        with double("deny-but-write") as (adapter, _):
            with self.assertRaisesRegex(CheckFailed, "^state-changed$"):
                run_case(adapter, "anonymous-save")

    def test_detects_private_read_before_authorization(self):
        with double("read-before-auth") as (adapter, _):
            with self.assertRaisesRegex(CheckFailed, "^state-changed$"):
                run_case(adapter, "anonymous-load")

    def test_detects_private_response_leak(self):
        with double("leak-on-deny") as (adapter, _):
            with self.assertRaisesRegex(CheckFailed, "^private-response-leak$"):
                run_case(adapter, "anonymous-load")

    def test_blocks_public_targets_before_connection(self):
        with patch("gateway_harness.http.client.HTTPConnection") as connection:
            with self.assertRaises(ContractError):
                exchange("https://example.invalid:443", Request("POST", "/cms-owner/"))
            with self.assertRaises(ContractError):
                exchange("http://localhost:1234", Request("POST", "/"))
            with self.assertRaises(ContractError):
                exchange("http://127.0.0.1:1234", Request("POST", "//example.com/"))
            connection.assert_not_called()

    def test_does_not_follow_redirect(self):
        with double() as (adapter, state):
            result = exchange(adapter.base_url, Request("GET", "/redirect"))
            self.assertEqual(result.status, 302)
            self.assertEqual(state["hits"], 1)

    def test_requires_backend_status_and_denial_discriminator(self):
        with self.assertRaises(ContractError):
            verify(None, Expectation(()), "deny")
        with self.assertRaises(ContractError):
            verify(None, Expectation((200,), forbidden_body_values=(PRIVATE_MARKER,)), "deny")

    def test_redacts_unregistered_adapter_error(self):
        self.assertEqual(public_category(ContractError(PRIVATE_MARKER.decode())),
                         "fixture-contract-invalid")

    def test_portable_cli_preserves_adapter_contract_types(self):
        # A synthetic double checks CLI/import wiring; no actual gateway is used.
        root = Path(__file__).resolve().parent
        source = '''import atexit
from test_harness import double
context = double()
adapter, state = context.__enter__()
atexit.register(lambda: context.__exit__(None, None, None))
adapter.describe = lambda: {
    "fixture_kind": "local-synthetic",
    "gateway_available": True,
    "candidate_sha": "1" * 40,
    "clock_fixture": True,
    "action_map": {action: "synthetic-fixture-only" for action in
                   ("load", "save", "review", "request_publish")},
}
def create_adapter():
    return adapter
'''
        with tempfile.TemporaryDirectory(prefix="synthetic-cli-", dir=root) as temporary:
            path = Path(temporary) / "synthetic_adapter.py"
            path.write_text(source)
            result = subprocess.run([sys.executable, str(root / "gateway_harness.py"), str(path)],
                                    cwd=root, capture_output=True, text=True, timeout=10,
                                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, "portable CLI synthetic adapter failed")
        report = json.loads(result.stdout)
        self.assertEqual(report["passed"], len(VECTORS))
        self.assertEqual(report["failed"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
