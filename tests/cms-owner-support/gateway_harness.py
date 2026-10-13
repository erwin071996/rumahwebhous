#!/usr/bin/env python3
"""Focused local HTTP checks. This module contains no gateway implementation."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import http.client
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlsplit


# Preserve dataclass identity when a CLI-loaded adapter imports this module.
if __name__ == "__main__":
    sys.modules.setdefault("gateway_harness", sys.modules[__name__])


VECTORS = {
    "anonymous-load": "deny",
    "anonymous-save": "deny",
    "anonymous-review": "deny",
    "anonymous-request-publish": "deny",
    "forged-payload-identity": "deny",
    "non-owner-session": "deny",
    "csrf-missing-save": "deny",
    "csrf-wrong-save": "deny",
    "csrf-cross-session-save": "deny",
    "csrf-missing-request-publish": "deny",
    "csrf-client-flag": "deny",
    "expired-session": "deny",
    "expiry-at-boundary": "deny",
    "active-before-expiry": "allow",
    "unknown-session-id": "deny",
    "payload-expiry-extension": "deny",
    "logout-session-reuse": "deny",
}


class ContractError(Exception):
    """A required fixture contract is absent or unsafe."""


class CheckFailed(Exception):
    """A fixed category only; response data and fixture values stay private."""


_CATEGORIES = frozenset({
    "invalid-json-path", "loopback-target-required", "invalid-port",
    "explicit-port-required", "relative-path-required", "unsupported-fixture-method",
    "unsafe-fixture-header", "ambiguous-body", "response-too-large", "transport-failed",
    "backend-status-map-required", "synthetic-private-sentinels-required",
    "explicit-denial-discriminator-required", "status-mismatch", "private-response-leak",
    "body-contract-mismatch", "json-contract-mismatch", "unexpected-json-field",
    "unknown-vector", "check-contract-required", "denial-state-invariant-required",
    "synthetic-state-probe-required", "state-changed",
    "gateway-sha-and-synthetic-clock-required", "backend-action-map-required",
    "fixture-adapter-required", "backend-fixture-mapping-required",
    "backend-synthetic-state-probe-required",
})


def public_category(error: Exception) -> str:
    # Even a trusted fixture adapter may accidentally put payloads in an error.
    category = str(error)
    return category if category in _CATEGORIES else "fixture-contract-invalid"


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    json_body: Any = None
    raw_body: bytes | None = None


@dataclass(frozen=True)
class Expectation:
    # Populate from the REAL Backend contract, never inferred HTTP statuses.
    statuses: tuple[int, ...]
    json_equals: dict[str, Any] = field(default_factory=dict)
    absent_json_paths: tuple[str, ...] = ()
    required_body_fragments: tuple[bytes, ...] = ()
    forbidden_body_values: tuple[bytes, ...] = ()


@dataclass(frozen=True)
class Check:
    request: Request
    expect: Expectation
    state_unchanged: bool = True


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


_MISSING = object()


def _json_path(value: Any, path: str) -> Any:
    if not path or path.startswith(".") or path.endswith("."):
        raise ContractError("invalid-json-path")
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part, _MISSING)
        elif isinstance(value, list) and part.isdigit():
            index = int(part)
            value = value[index] if index < len(value) else _MISSING
        else:
            return _MISSING
    return value


def _target(base_url: str):
    parsed = urlsplit(base_url)
    # Literal loopback only. No DNS, public target, userinfo or hidden proxy.
    if (parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ContractError("loopback-target-required")
    try:
        port = parsed.port
    except ValueError:
        raise ContractError("invalid-port") from None
    if port is None or not 1 <= port <= 65535:
        raise ContractError("explicit-port-required")
    return parsed.scheme, parsed.hostname, port


def exchange(base_url: str, request: Request) -> Response:
    scheme, host, port = _target(base_url)
    parsed_path = urlsplit(request.path)
    if (not request.path.startswith("/") or request.path.startswith("//")
            or parsed_path.netloc or parsed_path.scheme or parsed_path.fragment
            or any(c in request.path for c in "\r\n\\")):
        raise ContractError("relative-path-required")
    if request.method not in {"GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"}:
        raise ContractError("unsupported-fixture-method")
    headers = dict(request.headers)
    for key, value in headers.items():
        if (key.lower() in {"authorization", "proxy-authorization", "host"}
                or not isinstance(value, str)
                or any(c in key + value for c in "\r\n")):
            raise ContractError("unsafe-fixture-header")
    if request.json_body is not None and request.raw_body is not None:
        raise ContractError("ambiguous-body")
    body = request.raw_body
    if request.json_body is not None:
        body = json.dumps(request.json_body, separators=(",", ":")).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    connection_type = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
    connection = connection_type(host, port, timeout=5)
    try:
        connection.request(request.method, request.path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read(131073)
        if len(payload) > 131072:
            raise CheckFailed("response-too-large")
        return Response(response.status, dict(response.getheaders()), payload)
    except (OSError, http.client.HTTPException):
        raise CheckFailed("transport-failed") from None
    finally:
        connection.close()


def verify(response: Response, expected: Expectation, outcome: str):
    if (not expected.statuses or any(type(s) is not int or s < 100 or s > 599
                                     for s in expected.statuses)):
        raise ContractError("backend-status-map-required")
    if outcome == "deny":
        if not expected.forbidden_body_values or any(not s for s in expected.forbidden_body_values):
            raise ContractError("synthetic-private-sentinels-required")
        if (any(200 <= s <= 299 for s in expected.statuses)
                and not expected.json_equals and not expected.required_body_fragments):
            raise ContractError("explicit-denial-discriminator-required")
    if response.status not in expected.statuses:
        raise CheckFailed("status-mismatch")
    for marker in expected.forbidden_body_values:
        if marker in response.body:
            raise CheckFailed("private-response-leak")
    for fragment in expected.required_body_fragments:
        if fragment not in response.body:
            raise CheckFailed("body-contract-mismatch")
    if expected.json_equals or expected.absent_json_paths:
        try:
            value = json.loads(response.body)
        except (ValueError, UnicodeError):
            raise CheckFailed("json-contract-mismatch") from None
        for path, wanted in expected.json_equals.items():
            found = _json_path(value, path)
            if found is _MISSING or type(found) is not type(wanted) or found != wanted:
                raise CheckFailed("json-contract-mismatch")
        for path in expected.absent_json_paths:
            if _json_path(value, path) is not _MISSING:
                raise CheckFailed("unexpected-json-field")


def run_case(adapter, vector_id: str):
    if vector_id not in VECTORS:
        raise ContractError("unknown-vector")
    check = adapter.prepare(vector_id)
    if not isinstance(check, Check):
        raise ContractError("check-contract-required")
    if VECTORS[vector_id] == "deny" and not check.state_unchanged:
        raise ContractError("denial-state-invariant-required")
    before = adapter.state_fingerprint()
    if before is None:
        raise ContractError("synthetic-state-probe-required")
    response = exchange(adapter.base_url, check.request)
    after = adapter.state_fingerprint()
    if check.state_unchanged and before != after:
        raise CheckFailed("state-changed")
    verify(response, check.expect, VECTORS[vector_id])


def run_suite(adapter) -> dict[str, Any]:
    meta = adapter.describe()
    # A complete suite cannot silently replace missing gateway checks with mocks.
    if (meta.get("fixture_kind") != "local-synthetic"
            or meta.get("gateway_available") is not True
            or not re.fullmatch(r"[a-f0-9]{40}", meta.get("candidate_sha", ""))
            or meta.get("clock_fixture") is not True):
        raise ContractError("gateway-sha-and-synthetic-clock-required")
    mapping = meta.get("action_map", {})
    if any(not mapping.get(action) for action in ("load", "save", "review", "request_publish")):
        raise ContractError("backend-action-map-required")
    _target(adapter.base_url)
    results = []
    for vector_id in VECTORS:
        try:
            run_case(adapter, vector_id)
            results.append({"id": vector_id, "outcome": "pass"})
        except (ContractError, CheckFailed) as error:
            results.append({"id": vector_id, "outcome": "fail", "category": public_category(error)})
        except Exception:
            # Never print adapter exceptions: they may contain response/session data.
            results.append({"id": vector_id, "outcome": "blocked", "category": "fixture-adapter-failed"})
    return {"evidence_kind": "local-synthetic-gateway-only",
            "candidate_sha": meta["candidate_sha"], "cases": results,
            "passed": sum(r["outcome"] == "pass" for r in results),
            "failed": sum(r["outcome"] != "pass" for r in results)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter", type=Path, help="Backend's local synthetic fixture adapter")
    arguments = parser.parse_args()
    try:
        spec = importlib.util.spec_from_file_location("backend_local_fixture", arguments.adapter)
        if spec is None or spec.loader is None:
            raise ContractError("fixture-adapter-required")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = run_suite(module.create_adapter())
        print(json.dumps(report, indent=2))
        return 0 if report["failed"] == 0 else 1
    except ContractError as error:
        print(json.dumps({"outcome": "blocked", "category": public_category(error)}))
        return 2
    except Exception:
        print(json.dumps({"outcome": "blocked", "category": "fixture-adapter-failed"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
