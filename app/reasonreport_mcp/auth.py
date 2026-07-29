"""Hashed bearer-token authentication for the MCP resource server."""

from datetime import datetime, timezone

from mcp.server.auth.provider import AccessToken, TokenVerifier


from .tokens import TOKEN_PREFIX, token_digest


class MongoTokenVerifier(TokenVerifier):
    def __init__(self, database, pepper: str):
        self.database = database
        self.pepper = pepper

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token.startswith(TOKEN_PREFIX) or len(token) > 256:
            return None
        record = self.database.mcp_tokens.find_one(
            {"token_hash": token_digest(token, self.pepper), "revoked_at": None}
        )
        if not record:
            return None
        now = datetime.now(timezone.utc)
        expires_at = record.get("expires_at")
        if expires_at and expires_at.replace(tzinfo=expires_at.tzinfo or timezone.utc) <= now:
            return None
        user = self.database.users.find_one({"_id": record["user_id"], "status": "active"})
        if not user:
            return None
        self.database.mcp_tokens.update_one(
            {"_id": record["_id"]}, {"$set": {"last_used_at": now}}
        )
        return AccessToken(
            token=token,
            client_id=str(record["user_id"]),
            scopes=record.get("scopes", []),
            expires_at=int(expires_at.timestamp()) if expires_at else None,
        )
