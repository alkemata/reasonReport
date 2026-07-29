"""Dependency-free token primitives shared by the server and admin CLI."""

import hashlib
import hmac


TOKEN_PREFIX = "rrmcp_"


def token_digest(token: str, pepper: str) -> str:
    """Return the server-peppered digest persisted instead of a bearer token."""
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()
