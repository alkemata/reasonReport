# ReasonReport MCP knowledge server

ReasonReport includes a remote, Streamable HTTP MCP server at `/mcp`. Its tools
create, find, read, edit, and delete MongoDB-backed Jupyter notebooks. The
authenticated user is always the author; an LLM cannot set or replace the
server-owned `author_id`, timestamps, or revision.

## Security model

- TLS terminates at Traefik. Do not publish port 8000 directly.
- Every MCP request requires an `Authorization: Bearer rrmcp_...` header.
- Only a SHA-256 HMAC of each token is stored. `MCP_TOKEN_PEPPER` stays outside
  MongoDB and tokens expire automatically.
- Tokens have separate `documents:read`, `documents:write`, and
  `documents:delete` scopes and can be revoked immediately.
- Reads enforce private/public sharing rules. Writes and deletes require
  ownership and an expected revision, preventing lost updates.
- Mutations create audit events. MongoDB is not exposed on a host port and
  requires credentials.

Treat bearer tokens like passwords. Give each connector its own short-lived,
least-privilege token, rotate the pepper only as an emergency global revocation,
and keep Traefik access logs free of authorization headers.

## Deploy

Create `.env` with strong, distinct values (alongside the existing Flask
secrets):

```dotenv
MONGO_ROOT_USERNAME=reasonreport
MONGO_ROOT_PASSWORD=<openssl-rand-hex-32>
MCP_TOKEN_PEPPER=<openssl-rand-hex-32>
MCP_PUBLIC_URL=https://rr.example.com/mcp
MCP_ISSUER_URL=https://rr.example.com/mcp
```

Update both Traefik host rules in `docker-compose.yml`, then initialize and
start the services:

```bash
docker-compose build flaskapprr mcp
docker-compose run --rm flaskapprr python -c \
  "from models import mongo; from app import app; from database_init import initialize_database; app.app_context().push(); initialize_database(mongo.db)"
docker-compose up -d
```

Mongo authentication is initialized only for a fresh data volume. For an
existing unauthenticated volume, follow MongoDB's documented access-control
migration procedure before deploying this Compose change; do not delete the
volume.

## Issue and revoke connector credentials

Issue a full-access token for an existing active ReasonReport user:

```bash
docker-compose run --rm mcp manage-reasonreport-mcp-token issue alice \
  --name chatgpt --days 30 \
  --scopes documents:read documents:write documents:delete
```

The raw value is displayed once. Configure the ChatGPT/custom MCP connector URL
as `https://rr.example.com/mcp` and its bearer token as that value. Prefer a
read-only token (`--scopes documents:read`) whenever the connector only needs
knowledge retrieval.

List token metadata or revoke by its displayed ID:

```bash
docker-compose run --rm mcp manage-reasonreport-mcp-token list
docker-compose run --rm mcp manage-reasonreport-mcp-token revoke TOKEN_ID
```

## Available tools

| Tool | Scope | Behavior |
| --- | --- | --- |
| `add_document` | `documents:write` | Creates a Jupyter notebook and metadata. |
| `get_document` | `documents:read` | Returns metadata and optionally notebook JSON. |
| `find_documents` | `documents:read` | Searches accessible title, summary, and tags. |
| `edit_document` | `documents:write` | Updates owned fields with revision checking. |
| `delete_document` | `documents:delete` | Deletes an owned document with revision checking. |

For a smoke test, send an MCP `initialize` JSON-RPC request with `curl`; a
missing or invalid bearer token must return HTTP 401 before JSON-RPC handling.
