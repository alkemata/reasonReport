# ReasonReport Python API in JupyterLite

Notebooks opened from ReasonReport can import the bundled asynchronous Python
client:

```python
import reasonreport
```

The JupyterLite extension provisions the module and a short-lived editor session
when the authenticated editor starts. The browser's HTTP-only JWT cookie remains
unavailable to notebook code; the module receives only a 15-minute, user-bound,
editor-scoped capability and renews it through the authenticated same-origin
session when necessary.

## List readable notebooks

```python
documents = await reasonreport.list_documents(limit=50)
documents
```

The result includes the user's notebooks and public notebooks. The maximum limit
is 100.

## Read a notebook

```python
document = await reasonreport.get_document("<notebook-id>")
document["notebook"]["cells"]
```

Private notebooks owned by another user are returned as not found.

## Query notebook metadata

```python
documents = await reasonreport.query_documents(
    {"title": "My report", "is_public": True},
    limit=20,
)
```

Only exact-value filters on `_id`, `title`, `slug`, `author`, and `is_public` are
accepted. MongoDB operators, nested dictionaries, collection selection,
aggregation pipelines, JavaScript expressions, writes, and raw database access
are deliberately unavailable.

## Renew credentials explicitly

Normally a 401 response triggers one automatic renewal. It can also be renewed:

```python
expires_at = await reasonreport.refresh_session()
```

If renewal fails, reopen the notebook through the authenticated ReasonReport
editor. Do not copy `.reasonreport-session.json` or its token elsewhere.

## Administrator overview

The user named `admin` can display the user count and the ten most recently
created documents, including their title, slug, and author name:

```python
overview = await reasonreport.admin_overview()
overview
```

Other users receive an administrator-access error. This command exposes only
the listed summary fields and never returns password hashes.

## Security model

Every editor API request must satisfy all of the following:

1. contain a valid logged-in ReasonReport JWT cookie or Bearer token;
2. carry the JupyterLite marker header;
3. come from the same host/origin context;
4. carry a random editor token stored only as a SHA-256 digest in MongoDB;
5. use a non-expired editor session bound to the JWT user;
6. pass document-level authorization (owner or public notebook).

The capability is intentionally narrow and short-lived. It does not grant direct
MongoDB access and cannot bypass the server's allowlisted query language or
notebook visibility checks.
