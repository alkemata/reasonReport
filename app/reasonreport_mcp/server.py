"""Streamable-HTTP MCP entry point."""

import os

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient

from .auth import MongoTokenVerifier
from .service import KnowledgeService


mongo = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=5000)
database = mongo.get_default_database()
resource_url = os.environ["MCP_PUBLIC_URL"].rstrip("/")
pepper = os.environ["MCP_TOKEN_PEPPER"]
service = KnowledgeService(database)
verifier = MongoTokenVerifier(database, pepper)
mcp = FastMCP(
    "ReasonReport Knowledge Database",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8000")),
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    token_verifier=verifier,
    auth=AuthSettings(
        issuer_url=os.environ.get("MCP_ISSUER_URL", resource_url),
        resource_server_url=resource_url,
        required_scopes=[],
    ),
)


def identity(required_scope):
    token = get_access_token()
    if token is None or required_scope not in token.scopes:
        raise PermissionError(f"Bearer token requires the {required_scope!r} scope")
    return token.client_id


@mcp.tool()
def add_document(title: str, content: str, summary: str = "", tags: list[str] | None = None,
                 visibility: str = "private") -> dict:
    """Create a notebook document owned by the authenticated user."""
    return service.create(identity("documents:write"), title, content, summary, tags, visibility)


@mcp.tool()
def get_document(document_id: str, include_content: bool = True) -> dict:
    """Read accessible notebook content and server-owned metadata, including author ID."""
    return service.read(identity("documents:read"), document_id, include_content)


@mcp.tool()
def find_documents(query: str = "", limit: int = 20) -> list[dict]:
    """Find accessible documents by title, summary, or exact tag."""
    return service.list(identity("documents:read"), query, limit)


@mcp.tool()
def edit_document(document_id: str, expected_revision: int, title: str | None = None,
                  content: str | None = None, summary: str | None = None,
                  tags: list[str] | None = None, visibility: str | None = None) -> dict:
    """Edit an owned document using optimistic concurrency; author cannot be changed."""
    return service.update(identity("documents:write"), document_id, expected_revision,
                          title, content, summary, tags, visibility)


@mcp.tool()
def delete_document(document_id: str, expected_revision: int) -> dict:
    """Permanently delete an owned document at the expected revision."""
    return service.delete(identity("documents:delete"), document_id, expected_revision)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
