# ReasonReport installation guide

ReasonReport runs Flask and MongoDB with Docker Compose. The Flask image also
builds the bundled JupyterLab extension and a static JupyterLite site containing
the Pyodide kernel.

The checked-in Compose configuration targets an HTTPS deployment behind an
existing Traefik instance. The public hostname and every credential are set in
a local `.env` file. See [Local development](#local-development) if you do not
use Traefik.

## 1. Prerequisites

Install:

- Git;
- Docker Engine;
- Docker Compose CLI (`docker-compose`);
- an HTTPS-capable Traefik instance for the production configuration;
- DNS access for the chosen public hostname.

Verify the tools:

```bash
git --version
docker --version
docker-compose version
```

## 2. Check out the repository

```bash
git clone https://github.com/alkemata/reasonReport.git
cd reasonReport
```

To deploy a particular branch or release:

```bash
git fetch --all --tags
git checkout <branch-or-tag>
```

## 3. Create the installation configuration

All installation-specific values live in the repository root's `.env` file.
Docker Compose reads this file automatically; it is ignored by Git so that
credentials are not committed. Create it from the documented template:

```bash
cp .env.example .env
```

Open `.env` and replace **every** `CHANGE_ME` value. At minimum, configure:

| Variable | Purpose |
| --- | --- |
| `APP_HOSTNAME` | Public hostname routed by Traefik, without `https://` or a path. |
| `MONGO_ROOT_USERNAME` | MongoDB administrator used by MongoDB, Flask, MCP, health checks, and maintenance scripts. |
| `MONGO_ROOT_PASSWORD` | URL-safe MongoDB password; generate with `openssl rand -hex 32`. |
| `MONGO_DATABASE` | Application database name; normally `flaskdb`. |
| `SECRET_KEY` | Flask session secret; generate independently with `openssl rand -hex 32`. |
| `JWT_SECRET_KEY` | Authentication-token secret; generate independently. |
| `MCP_PUBLIC_URL` | Full external MCP URL, normally `https://<APP_HOSTNAME>/mcp`. |
| `MCP_TOKEN_PEPPER` | Secret used to hash MCP tokens; generate independently. |

`JWT_COOKIE_SECURE=true` is required behind production HTTPS. `ADMIN_USERNAME`,
`INDEX_PAGE_NAME`, and the optional `MCP_ISSUER_URL` are also explained in the
template. Do not define `MONGO_URI` yourself: Compose constructs exactly the
same authenticated URI for both `flaskapprr` and `mcp` from the Mongo settings.

Check interpolation and the resulting service model before starting anything:

```bash
docker-compose config --quiet
```

The rendered output of `docker-compose config` contains secrets; do not paste
it into tickets or commit it. The checked-in file deliberately has no fallback
production secrets and reports a missing required setting immediately.

## 4. Connect to the existing Traefik deployment

ReasonReport does not start Traefik. It joins the external Docker network named
`traefik_web`, which is the network created by the Traefik Compose configuration
in the deployment (`web: {name: traefik_web}`). The application labels select
the `websecure` entrypoint, enable TLS, route `APP_HOSTNAME` to Flask port 5000,
and give `/mcp` a higher-priority route to the MCP service on port 8000.
MongoDB joins only the internal `backend` network and is never exposed through
Traefik or published on the host.

Start the supplied Traefik stack first. Confirm that its network exists:

```bash
docker network inspect traefik_web
```

If the Traefik stack has not created it yet, create it once, then start/recreate
Traefik so its `reverse_proxy` service joins that network:

```bash
docker network create traefik_web
docker-compose -f /path/to/traefik/docker-compose.yml up -d
```

The Traefik static configuration must define an entrypoint named `websecure` on
port 443 and arrange certificate issuance/loading. Point the DNS record for
`APP_HOSTNAME` to this host. No `ports:` entry should be added to ReasonReport
for production: Traefik reaches the containers over `traefik_web`.

### Existing MongoDB volumes

The official Mongo image creates `MONGO_INITDB_ROOT_USERNAME` and
`MONGO_INITDB_ROOT_PASSWORD` only when `/data/db` is empty. If this deployment
already has a credential-free `mongo-data` volume, back it up before upgrading.
Either create the configured administrator in that database before enabling
authentication, or restore the backup into a newly initialized volume. Merely
adding credentials to `.env` cannot create a user in an existing non-empty
volume.

## 5. Prepare MongoDB storage

The Compose stack stores `/data/db` in its managed `mongo-data` Docker volume.
Normal rebuilds, container recreation, and `docker-compose down` followed by
`up` reuse the same database. Keep the same Compose project name (which defaults
to the checkout directory name), and do not run `docker-compose down -v` or
manually remove the project volume unless you intend to delete the database.

MongoDB logs remain bind-mounted from the checkout. Create that directory
before the first start:

```bash
mkdir -p mongo-logs
```

If MongoDB reports permission errors on Linux, assign the directories to the
MongoDB container user:

```bash
sudo chown -R 999:999 mongo-logs
```

If upgrading from a version that used the checkout's `mongo-data/` directory,
create a backup before changing Compose configuration, start the new stack,
and restore it into the named volume:

```bash
docker-compose exec -T mongo sh -c 'exec mongodump \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin --db "$MONGO_DATABASE" --archive' \
  > flaskdb.archive
docker-compose up -d mongo
docker-compose exec -T mongo sh -c 'exec mongorestore \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin --archive --drop' < flaskdb.archive
```

## 6. Build the application and JupyterLite

```bash
docker-compose build flaskapprr
```

For a clean build with complete diagnostic output:

```bash
docker-compose build --no-cache --progress=plain flaskapprr
```

The Dockerfile keeps dependency installation, TypeScript/extension compilation,
extension registration, and the JupyterLite site build in separate layers. The
last successful `RUN` line therefore identifies which stage failed. If Docker
only prints a combined shell-command error, pull the latest revision before
retrying: older revisions used a single `jlpm` build step with a lockfile that
did not describe this standalone extension package.

The build downloads Python and JavaScript packages, compiles
`flask_extension/src/index.ts`, installs the resulting federated extension, and
runs `jupyter lite build`. Internet access to PyPI, GitHub Releases, and the
Yarn/npm registries is therefore required during this step. The Pyodide download
is a separate, retried image layer, so a CDN failure is reported directly and a
successful download is reused by subsequent builds.

The build also seeds the JupyterLite contents service from
`jupyterlite-content/` and verifies that `api/contents/all.json` exists. It
downloads Pyodide 0.27.6 while building the image and serves the runtime from
`/jupyterlite/static/pyodide/`. Browsers therefore do not need to connect to an
external CDN for the Python runtime.
The pure-Python `comm` dependency is also downloaded at image-build time and
added to JupyterLite's local `/pypi/all.json` index. The piplite/micropip resolver can
still consult PyPI while resolving dependencies, so `connect-src` permits
`https://pypi.org` and wheel downloads from `https://files.pythonhosted.org`.
These are connection sources rather than script sources: wheels are package
data interpreted inside Pyodide, not JavaScript executed by the browser.

### Why CSP errors appear one resource at a time

Content Security Policy is an allowlist enforced by the browser. `script-src`
controls executable scripts, while `connect-src` controls `fetch`, XHR, and
similar network requests. When a directive is absent, the browser falls back
to `default-src`. A policy such as `default-src 'self' data:` therefore denies
every HTTPS origin other than the site that served the page.

JupyterLite runs Python in the browser. Its Pyodide kernel may fetch both the
Python runtime and missing Python wheels, so fixing one external request can
reveal the next one. ReasonReport reduces that sequence by bundling both the
Pyodide runtime and required startup wheels into the image. The PyPI origins
remain explicitly allowed for dependency resolution and packages installed
interactively by notebook code.

CSP can be supplied by an HTTP response header, an HTML meta element, and a
reverse proxy. Browsers enforce all policies at once; a permissive Flask header
cannot weaken a stricter Traefik header or meta policy. JupyterLite also uses a
service worker, so old application configuration can remain cached after a
deployment. Inspect every `Content-Security-Policy` response header and the
page's meta policy, then unregister the old service worker or clear site data
after replacing the container.

## 7. Start and verify MongoDB

```bash
docker-compose up -d mongo
docker-compose logs -f mongo
```

Once MongoDB is ready, stop following the log with `Ctrl+C` and run:

```bash
docker-compose exec mongo sh -c 'mongosh --quiet \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --eval '"'"'db.runCommand({ ping: 1 })'"'"''
```

The result should contain `ok: 1`.

## 8. Start the website

```bash
docker-compose up -d flaskapprr
docker-compose ps
```

Follow the application log if startup fails:

```bash
docker-compose logs -f flaskapprr
```

The Flask service listens on port 5000 inside the Docker networks. Traefik
forwards the public HTTPS hostname to that internal port.

### Development hot reload

For local development, start Compose with the development override:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up flaskapprr
```

Both Compose files declare the same Compose format version, so this command is
also compatible with legacy `docker-compose` installations that otherwise
interpret a versionless override as the old version 1 format.
The application bind mount is declared only by `docker-compose.yml`; the
development override inherits it rather than declaring `/app` a second time.
This avoids the duplicate-mount error raised by some Compose releases.

The override enables Flask's debugger/reloader, so changes under `app/` are
picked up without restarting the container. It also watches
`flask_extension/src/`; after a TypeScript change it rebuilds the federated
extension and JupyterLite site automatically. Wait for the
`JupyterLite extension rebuild complete` log message, then reload the editor
page. A JupyterLite service worker may retain the prior build, so use a hard
reload or clear the site's service worker/cache if the new extension does not
appear.

If `git pull` only changes Flask application files, templates, static files, or
extension source, the running development stack reloads them. Rebuild the image
when the pull changes dependencies, the Dockerfile, build configuration, or
system packages:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up \
  --build flaskapprr
```

Do not use the development override in production: Flask debug mode permits
interactive debugging, and the source watcher consumes extra resources.

## 9. Verify the HTTP endpoints

Using the `APP_HOSTNAME` configured in `.env` (the examples below use `rr.example.com`):

```bash
curl -I https://rr.example.com/register
curl -I https://rr.example.com/login
curl -I https://rr.example.com/jupyterlite/
```

Confirm that the generated JupyterLite site exists in the application image:

```bash
docker-compose exec flaskapprr \
  test -f /opt/jupyterlite/index.html
```

Check the effective Content Security Policy:

```bash
curl -sSI https://rr.example.com/jupyterlite/ \
  | grep -i '^content-security-policy:'
```

There must be only one effective policy. JupyterLite requires same-origin
scripts, WebAssembly/eval support, blob workers, and inline styles used by
JupyterLab's widget layout. If Traefik or another proxy adds a second stricter
`Content-Security-Policy` header, remove that middleware for ReasonReport or
make its policy match the application policy. Multiple CSP headers are enforced
together, so Flask cannot loosen a stricter policy added by the proxy.

Also inspect the policy embedded in the generated JupyterLite HTML:

```bash
curl -s https://rr.example.com/jupyterlite/ \
  | grep -i 'content-security-policy'
```

It must include explicit `script-src` and `style-src` directives. A response
containing only `default-src 'self' data:` is an older JupyterLite build: rebuild
the image without cache so the CSP postprocessor rewrites JupyterLite's embedded
meta policy as well as externalizing its bootstrap scripts.

If `/jupyterlite/` fails, inspect both the image contents and Flask log:

```bash
docker-compose exec flaskapprr \
  find /opt/jupyterlite -maxdepth 2 -type f | head -30
docker-compose logs --tail=200 flaskapprr
```

## 10. Exercise the notebook workflow

1. Open `https://rr.example.com/register` and create an account.
2. Registration authenticates the new account and redirects directly to its
   initial notebook editor.
3. To create another notebook, choose **Create Notebook → Blank**.
4. Wait for JupyterLite to load inside the page and open the notebook.
5. Keep the cells carrying `type: title` and `type: date` metadata non-empty.
6. Edit the title and notebook content.
7. Click **Publish**.
8. Confirm that the browser redirects to `/id/<notebook-id>`.
9. Refresh that page and confirm the rendered content persists.
10. As the author, click **Edit Notebook**, make another change, publish, and
    confirm the same notebook is updated.

Inspect stored notebook records when troubleshooting:

```bash
docker-compose exec mongo sh -c 'exec mongosh "$MONGO_DATABASE" \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin --eval "$1"' sh \
  'db.notebooks.find({}, {title: 1, slug: 1, author: 1, is_public: 1}).pretty()'
```

Inspect users with:

```bash
docker-compose exec mongo sh -c 'exec mongosh "$MONGO_DATABASE" \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin --eval "$1"' sh \
  'db.users.find({}, {username: 1, role: 1}).pretty()'
```

The repository also provides maintenance wrappers which run `mongosh` inside
the Compose MongoDB container:

```bash
./scripts/list_users.sh
./scripts/list_documents.sh
./scripts/delete_user.sh USERNAME
./scripts/delete_document.sh DOCUMENT_ID
./scripts/delete_all_users.sh --yes
```

`delete_user.sh` removes the selected user and all of their documents;
`delete_all_users.sh` permanently removes every user and notebook and requires
the explicit `--yes` argument;
`delete_document.sh` accepts the `_id` printed by `list_documents.sh`. Back up
MongoDB before using any deletion command.

Verify login, the current-user endpoint, and logout with a cookie jar:

```bash
curl -k -c /tmp/reasonreport-cookies.txt -X POST \
  -d 'username=<username>&password=<password>' \
  'https://rr.example.com/login?next=/'
curl -k -b /tmp/reasonreport-cookies.txt \
  'https://rr.example.com/api/me'
curl -k -b /tmp/reasonreport-cookies.txt -c /tmp/reasonreport-cookies.txt \
  -X POST 'https://rr.example.com/api/logout'
```

If the browser returns to `/login`, inspect the form POST in developer tools.
The request URL must preserve the destination, such as
`/login?next=/edit/<notebook-id>`, and its response must set `jwt_token1`.

## Local development

The checked-in Compose file does not publish Flask port 5000 to the host and
requires the external `traefik_web` network. To expose Flask directly, create an
uncommitted `docker-compose.override.yml`:

```yaml
services:
  flaskapprr:
    ports:
      - "5000:5000"
```

Then run:

```bash
docker network inspect traefik_web >/dev/null 2>&1 \
  || docker network create traefik_web
docker-compose up --build
```

The pages are then available at `http://localhost:5000`. For plain HTTP local
development, set `JWT_COOKIE_SECURE=false` in the local `.env` file. Keep it
`true` for the HTTPS production deployment.

## Updating a deployment

```bash
git pull --ff-only
docker-compose build flaskapprr
docker-compose up -d --force-recreate flaskapprr
docker-compose ps
```

Always rebuild the image after changing the extension, Python requirements, or
JupyterLite configuration. A container restart alone does not rebuild the
JupyterLite static site.

## Common operations

Show status:

```bash
docker-compose ps
```

Follow all logs:

```bash
docker-compose logs -f
```

### Diagnose repeated login or registration requests

A page that stays pending is not, by itself, evidence of a full database. First
check container health and resource usage, then inspect recent application and
proxy access logs (replace `reverse_proxy` with the Traefik service name):

```bash
docker-compose ps
docker stats --no-stream
docker-compose logs --since=30m flaskapprr mongo
docker-compose -f /path/to/traefik/docker-compose.yml logs --since=30m reverse_proxy \
  | grep -E '(/login|/register|/api/login|/api/register)'
```

Count source addresses and response codes in the access log. A high request
rate, many source addresses, repeated usernames, or many `401`/`429` responses
can indicate credential stuffing or automated registration. Do not infer an
attack only from browser requests: the browser developer tools **Network** tab
shows whether a request is pending, rejected with `429`, or failing with `5xx`.

MongoDB status, logical database size, collection counts, and host disk usage
can be checked without publishing MongoDB's port:

```bash
docker-compose exec -T mongo sh -c 'exec mongosh --quiet \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin "$MONGO_DATABASE" \
  --eval '\''printjson(db.stats({scale: 1024*1024})); db.getCollectionNames().forEach(n => print(n, db[n].countDocuments({})))'\'''
du -sh mongo-data mongo-logs
df -h .
```

For immediate containment, preserve logs and take the backup below, then stop
new account creation by setting `REGISTRATION_ENABLED=false` in `.env` and
recreating the web container:

```bash
docker-compose up -d --force-recreate flaskapprr
```

Both HTML and API login/registration POSTs are rate limited. Tune
`LOGIN_RATE_LIMIT` and `REGISTRATION_RATE_LIMIT` in `.env` (for example,
`5 per minute`). Rate limiting uses the client address forwarded by the single
trusted Traefik proxy hop. Do not expose the Flask container directly while
trusting forwarded headers. The default limiter storage is in-memory and is
appropriate only for this single-process deployment; configure shared limiter
storage before adding multiple application workers.

Also block confirmed abusive addresses or countries at Traefik, the host
firewall, or the upstream CDN/WAF; rotate credentials that may have been
exposed; invalidate sessions by rotating `JWT_SECRET_KEY` if account takeover
is suspected; and review/delete unexpected users only after retaining evidence.
Never publish MongoDB port 27017 as a response to an incident.

Restart Flask:

```bash
docker-compose restart flaskapprr
```

Stop the stack without deleting MongoDB data:

```bash
docker-compose down
```

Back up MongoDB:

```bash
mkdir -p backups
docker-compose exec -T mongo sh -c 'exec mongodump \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin --db "$MONGO_DATABASE" --archive' \
  > "backups/flaskdb-$(date +%Y%m%d-%H%M%S).archive"
```

## Current production caveats

Before treating the deployment as production-ready, address these existing
application issues:

- protect or remove the `/database` debugging endpoint;
- add health checks and automated API/browser tests;
- ensure converted notebook HTML is sanitized or isolated appropriately.
