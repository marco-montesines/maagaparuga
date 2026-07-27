"""OpenFGA access checks (relationship-based authorization).

Calls OpenFGA's HTTP check API. Fail-CLOSED: any error (OpenFGA unreachable,
missing store/model, malformed response) denies — an authorization system that
fails open is worse than none, and the platform's Go/PHP checkers fail closed too.
Reads map to the `viewer` relation, writes to `editor` (both already defined in
the shared FGA model), so no model change is needed.
"""

from __future__ import annotations

import logging

import httpx

from .config import Settings

log = logging.getLogger("media.authz")

RELATION_READ = "viewer"
RELATION_WRITE = "editor"


class OpenFgaChecker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or Settings()

    def allowed(self, user_sub: str, relation: str, recipient_id: int) -> bool:
        store = self._s.openfga_store_id
        if not store:
            log.error("OPENFGA_STORE_ID unset — denying (fail-closed)")
            return False
        body: dict[str, object] = {
            "tuple_key": {
                "user": f"user:{user_sub}",
                "relation": relation,
                "object": f"care_recipient:{recipient_id}",
            }
        }
        if self._s.openfga_model_id:
            body["authorization_model_id"] = self._s.openfga_model_id
        try:
            resp = httpx.post(
                f"{self._s.openfga_api_url}/stores/{store}/check", json=body, timeout=5.0
            )
            resp.raise_for_status()
            return bool(resp.json().get("allowed", False))
        except Exception as exc:  # network / HTTP / decode — all deny
            log.warning("OpenFGA check failed (%s); denying", exc)
            return False
