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

Before exposing the application publicly, replace the development Flask and JWT
secrets in `app/reasonreport/config.py` with environment-backed values. Generate
strong values with:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

The current application code must be adjusted to read these variables before
putting them in a local, uncommitted `.env` file:

```dotenv
SECRET_KEY=<first-generated-value>
JWT_SECRET_KEY=<second-generated-value>
MONGO_URI=mongodb://mongo:27017/flaskdb
JUPYTERLITE_PATH=/opt/jupyterlite
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

If `/jupyterlite/` fails, inspect both the image contents and Flask log:

```bash
docker compose exec flaskapprr \
  find /opt/jupyterlite -maxdepth 2 -type f | head -30
docker compose logs --tail=200 flaskapprr
```

## 10. Exercise the notebook workflow

1. Open `https://rr.alkemata.com/register` and create an account.
2. Registration currently does not establish the JWT cookie, so next open
   `https://rr.alkemata.com/login?next=/` and log in.
3. Choose **Create Notebook → Blank**.
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

The pages are then available at `http://localhost:5000`. Be aware that the
current login route always marks its JWT cookie `Secure`; authentication over
plain HTTP may therefore be rejected by the browser. Use local HTTPS, or make
the cookie's secure setting environment-dependent for development.

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

- move the hard-coded Flask/JWT secrets to environment variables;
- disable Flask debug mode and the debug toolbar;
- protect or remove the `/database` debugging endpoint;
- make registration establish an authenticated session;
- make the `Secure` cookie setting configurable for local development;
- add health checks and automated API/browser tests;
- ensure converted notebook HTML is sanitized or isolated appropriately.
