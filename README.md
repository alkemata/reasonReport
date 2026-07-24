# reasonReport
social network, the jupyter way

See [INSTALL.md](INSTALL.md) for checkout, deployment, verification, and
first-notebook instructions.

See [JUPYTERLITE_API.md](JUPYTERLITE_API.md) for the Python client available inside notebooks.

## User roles and home page

Every newly registered user is stored with one of three roles: `admin`,
`editor`, or `user`. Set `ADMIN_USERNAME` to the username that should receive
the `admin` role when it registers. Set `INDEX_PAGE_NAME` to the slug of that
administrator's document that should be served from `/`. The defaults are
`admin` and `mainpage` respectively. Both values can be placed in the Compose
environment or in the shell's `.env` file before starting the stack.

For an existing database, assign roles once after upgrading (adjust usernames
as appropriate):

```bash
docker compose exec mongo mongosh flaskdb --eval \
  'db.users.updateMany({role: {$exists: false}}, {$set: {role: "user"}}); db.users.updateOne({username: "admin"}, {$set: {role: "admin"}})'
```

## Database maintenance scripts

The scripts operate on the MongoDB service in the current Docker Compose
project. User output excludes password hashes. Deleting a user also deletes all
documents authored by that user.

```bash
./scripts/list_users.sh
./scripts/list_documents.sh
./scripts/delete_user.sh USERNAME
./scripts/delete_document.sh DOCUMENT_ID
```

Use `list_documents.sh` to obtain a document's MongoDB `_id` before deleting
it. These destructive commands cannot be undone, so back up the database first.
