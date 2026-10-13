"""Fill ONLY with a local synthetic fixture for the real Backend gateway.

This intentionally stops the runner: no HTTP route/status/login contract is known.
Do not put production passwords, sessions, API keys, or hosting paths here.
"""
from gateway_harness import ContractError


class BackendAdapter:
    base_url = None  # A literal loopback URL with an explicit ephemeral port.

    def describe(self):
        return {
            "fixture_kind": "local-synthetic",
            "gateway_available": False,
            "candidate_sha": None,  # Actual gateway commit, not the foundation SHA.
            "clock_fixture": False,
            "action_map": {
                "load": None,
                "save": None,
                "review": None,
                "request_publish": None,
            },
        }

    def prepare(self, vector_id):
        # Reset the synthetic draft/outbox and seed the server-side fixture session
        # and clock for this vector, then return gateway_harness.Check.
        raise ContractError("backend-fixture-mapping-required")

    def state_fingerprint(self):
        # Probe only fixture-owned draft/outbox + an instrumented private-read
        # counter. Exclude session files if rejection legitimately expires them.
        raise ContractError("backend-synthetic-state-probe-required")


def create_adapter():
    return BackendAdapter()
