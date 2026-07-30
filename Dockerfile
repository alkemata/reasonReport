# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY flask_extension /build/flask_extension
WORKDIR /build/flask_extension
RUN npm ci --no-audit --no-fund
RUN npm run build:prod
RUN extension_dir="$(python -c 'import sysconfig; print(sysconfig.get_path("data"))')/share/jupyter/labextensions/jupyter_flask_extension" \
    && mkdir -p "$extension_dir" \
    && cp -a jupyter_flask_extension_py/labextension/. "$extension_dir/"
COPY jupyterlite-content /build/jupyterlite-content
RUN mkdir -p /build/piplite-wheels \
    && pip download --no-deps --only-binary=:all: \
        --dest=/build/piplite-wheels comm==0.2.2
# Download the large runtime independently so transient CDN failures are retried
# and are not hidden inside the JupyterLite build step's combined exit status.
ARG PYODIDE_VERSION=0.27.6
RUN curl --fail --location --show-error --silent \
    --retry 5 --retry-delay 5 --retry-all-errors \
    --output /build/pyodide.tar.bz2 \
    "https://github.com/pyodide/pyodide/releases/download/${PYODIDE_VERSION}/pyodide-${PYODIDE_VERSION}.tar.bz2" \
    && test -s /build/pyodide.tar.bz2
RUN jupyter lite build --log-level=INFO \
    --contents=/build/jupyterlite-content \
    --pyodide=/build/pyodide.tar.bz2 \
    --piplite-wheels=/build/piplite-wheels \
    --output-dir=/opt/jupyterlite
RUN python /build/jupyterlite-content/validate_build.py /opt/jupyterlite
COPY scripts/externalize_inline_scripts.py /usr/local/bin/externalize-inline-scripts
COPY scripts/migrate_mongodb_schema.py /usr/local/bin/migrate-reasonreport-schema
COPY scripts/manage_mcp_token.py /usr/local/bin/manage-reasonreport-mcp-token
RUN chmod 0755 /usr/local/bin/manage-reasonreport-mcp-token
RUN externalize-inline-scripts /opt/jupyterlite

COPY app /app
WORKDIR /app/reasonreport
ENV JUPYTERLITE_PATH=/opt/jupyterlite
CMD python /usr/local/bin/migrate-reasonreport-schema && python -c "from models import mongo; from app import app; from database_init import initialize_database; app.app_context().push(); initialize_database(mongo.db)" && flask run -h 0.0.0.0 -p 5000
