# ReasonReport installation guide

ReasonReport runs Flask and MongoDB with Docker Compose. The Flask image also
builds the bundled JupyterLab extension and a static JupyterLite site containing
the Pyodide kernel.

The checked-in Compose configuration targets an HTTPS deployment behind an
existing Traefik instance at `rr.alkemata.com`. See [Local development](#local-development)
if you do not use Traefik.

## 1. Prerequisites

Install:

- Git;
- Docker Engine;
- Docker Compose v2 (`docker compose`);
- an HTTPS-capable Traefik instance for the production configuration;
- DNS access for the chosen public hostname.

Verify the tools:

```bash
git --version
docker --version
docker compose version
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

## 3. Configure the hostname and HTTPS proxy

The default Traefik router matches `rr.alkemata.com` and uses the `websecure`
entrypoint. If you use another hostname, change the
`traefik.http.routers.flaskapprr.rule` label in `docker-compose.yml` and point
that hostname's DNS record at the Docker host.

The Compose file does not start Traefik. Traefik must already:

1. expose ports 80 and 443;
2. define the `websecure` entrypoint;
3. provide a TLS certificate;
4. be connected to the external `traefik_web` Docker network.

Create the network if it does not exist:

```bash
docker network inspect traefik_web >/dev/null 2>&1 \
  || docker network create traefik_web
```

If Traefik is already running but is not attached to it:

```bash
docker network connect traefik_web <traefik-container-name>
```

Do not run that command when Traefik's own Compose file already attaches the
container to the network.

## 4. Configure production secrets

Before exposing the application publicly, generate strong Flask and JWT secrets:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Put them in a local, uncommitted `.env` file. The Compose service passes these
environment-backed settings to Flask:

```dotenv
SECRET_KEY=<first-generated-value>
JWT_SECRET_KEY=<second-generated-value>
MONGO_URI=mongodb://mongo:27017/flaskdb
JUPYTERLITE_PATH=/opt/jupyterlite
JWT_COOKIE_SECURE=true
```

Never commit real production secrets.

## 5. Prepare MongoDB storage

The Compose stack bind-mounts `mongo-data` and `mongo-logs` from the checkout.
Create them before the first start:

```bash
mkdir -p mongo-data mongo-logs
```

If MongoDB reports permission errors on Linux, assign the directories to the
MongoDB container user:

```bash
sudo chown -R 999:999 mongo-data mongo-logs
```

## 6. Build the application and JupyterLite

```bash
docker compose build flaskapprr
```

For a clean build with complete diagnostic output:

```bash
docker compose build --no-cache --progress=plain flaskapprr
```

The Dockerfile keeps dependency installation, TypeScript/extension compilation,
extension registration, and the JupyterLite site build in separate layers. The
last successful `RUN` line therefore identifies which stage failed. If Docker
only prints a combined shell-command error, pull the latest revision before
retrying: older revisions used a single `jlpm` build step with a lockfile that
did not describe this standalone extension package.

The build downloads Python and JavaScript packages, compiles
`flask_extension/src/index.ts`, installs the resulting federated extension, and
runs `jupyter lite build`. Internet access to PyPI and the Yarn/npm registries is
therefore required during this step.

The build also seeds the JupyterLite contents service from
`jupyterlite-content/` and verifies that `api/contents/all.json` exists. It
downloads Pyodide 0.27.6 while building the image and serves the runtime from
`/jupyterlite/static/pyodide/`. Browsers therefore do not need to connect to an
external CDN for the Python runtime.
The pure-Python `comm` dependency is also downloaded at image-build time and
added to JupyterLite's local piplite index. The piplite/micropip resolver can
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
docker compose up -d mongo
docker compose logs -f mongo
```

Once MongoDB is ready, stop following the log with `Ctrl+C` and run:

```bash
docker compose exec mongo mongosh --eval 'db.runCommand({ ping: 1 })'
```

The result should contain `ok: 1`.

## 8. Start the website

```bash
docker compose up -d flaskapprr
docker compose ps
```

Follow the application log if startup fails:

```bash
docker compose logs -f flaskapprr
```

The Flask service listens on port 5000 inside the Docker networks. Traefik
forwards the public HTTPS hostname to that internal port.

### Development hot reload

For local development, start Compose with the development override:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up flaskapprr
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
docker compose -f docker-compose.yml -f docker-compose.dev.yml up \
  --build flaskapprr
```

Do not use the development override in production: Flask debug mode permits
interactive debugging, and the source watcher consumes extra resources.

## 9. Verify the HTTP endpoints

Using the default hostname:

```bash
curl -I https://rr.alkemata.com/register
curl -I https://rr.alkemata.com/login
curl -I https://rr.alkemata.com/jupyterlite/
```

Confirm that the generated JupyterLite site exists in the application image:

```bash
docker compose exec flaskapprr \
  test -f /opt/jupyterlite/index.html
```

Check the effective Content Security Policy:

```bash
curl -sSI https://rr.alkemata.com/jupyterlite/ \
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
curl -s https://rr.alkemata.com/jupyterlite/ \
  | grep -i 'content-security-policy'
```

It must include explicit `script-src` and `style-src` directives. A response
containing only `default-src 'self' data:` is an older JupyterLite build: rebuild
the image without cache so the CSP postprocessor rewrites JupyterLite's embedded
meta policy as well as externalizing its bootstrap scripts.

If `/jupyterlite/` fails, inspect both the image contents and Flask log:

```bash
docker compose exec flaskapprr \
  find /opt/jupyterlite -maxdepth 2 -type f | head -30
docker compose logs --tail=200 flaskapprr
```

## 10. Exercise the notebook workflow

1. Open `https://rr.alkemata.com/register` and create an account.
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
docker compose exec mongo mongosh flaskdb --eval \
  'db.notebooks.find({}, {title: 1, slug: 1, author: 1, is_public: 1}).pretty()'
```

Inspect users with:

```bash
docker compose exec mongo mongosh flaskdb --eval \
  'db.users.find({}, {username: 1}).pretty()'
```

Verify login, the current-user endpoint, and logout with a cookie jar:

```bash
curl -k -c /tmp/reasonreport-cookies.txt -X POST \
  -d 'username=<username>&password=<password>' \
  'https://rr.alkemata.com/login?next=/'
curl -k -b /tmp/reasonreport-cookies.txt \
  'https://rr.alkemata.com/api/me'
curl -k -b /tmp/reasonreport-cookies.txt -c /tmp/reasonreport-cookies.txt \
  -X POST 'https://rr.alkemata.com/api/logout'
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
docker compose up --build
```

The pages are then available at `http://localhost:5000`. For plain HTTP local
development, set `JWT_COOKIE_SECURE=false` in the local `.env` file. Keep it
`true` for the HTTPS production deployment.

## Updating a deployment

```bash
git pull --ff-only
docker compose build flaskapprr
docker compose up -d --force-recreate flaskapprr
docker compose ps
```

Always rebuild the image after changing the extension, Python requirements, or
JupyterLite configuration. A container restart alone does not rebuild the
JupyterLite static site.

## Common operations

Show status:

```bash
docker compose ps
```

Follow all logs:

```bash
docker compose logs -f
```

Restart Flask:

```bash
docker compose restart flaskapprr
```

Stop the stack without deleting MongoDB data:

```bash
docker compose down
```

Back up MongoDB:

```bash
mkdir -p backups
docker compose exec -T mongo mongodump --archive --db flaskdb \
  > "backups/flaskdb-$(date +%Y%m%d-%H%M%S).archive"
```

## Current production caveats

Before treating the deployment as production-ready, address these existing
application issues:

- protect or remove the `/database` debugging endpoint;
- add health checks and automated API/browser tests;
- ensure converted notebook HTML is sanitized or isolated appropriately.
