"""Bearer-token verification — the caller's ZITADEL access token (a JWT).

Verified locally against the issuer's JWKS (signature -> issuer -> expiry, and
audience when configured), exactly like the telemetry service: no introspection
round trip per request. Defense in depth — the gateway already validates at the
edge, but the web app reaches media in-cluster directly, so the service re-checks.
PyJWT (+ its JWKS client) is imported lazily and the key set is fetched/cached once.
"""

from __future__ import annotations

from typing import Any

from .config import Settings


class InvalidToken(Exception):
    """The bearer token is missing, malformed, or fails verification."""


class _Verifier:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._jwks: Any | None = None

    def _client(self) -> Any:
        if self._jwks is None:
            from jwt import PyJWKClient

            self._jwks = PyJWKClient(self._s.jwks_uri())
        return self._jwks

    def subject(self, token: str) -> str:
        """Verify the JWT and return its subject (the caller's ZITADEL user id)."""
        import jwt

        try:
            signing_key = self._client().get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._s.oidc_issuer,
                audience=self._s.oidc_audience or None,
                options={"verify_aud": bool(self._s.oidc_audience)},
            )
        except Exception as exc:  # PyJWT raises many subclasses; all mean "reject"
            raise InvalidToken(str(exc)) from exc

        sub = claims.get("sub")
        if not sub:
            raise InvalidToken("token has no subject")
        return str(sub)


_verifier: _Verifier | None = None


def verify_subject(token: str, settings: Settings) -> str:
    """Module-level entry point with a process-wide cached verifier."""
    global _verifier
    if _verifier is None:
        _verifier = _Verifier(settings)
    return _verifier.subject(token)
