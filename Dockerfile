# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN apt-get update \
    && apt-get install --no-install-recommends -y nodejs npm \
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
RUN jupyter lite build \
    --contents=/build/jupyterlite-content \
    --pyodide=https://github.com/pyodide/pyodide/releases/download/0.27.6/pyodide-0.27.6.tar.bz2 \
    --piplite-wheels=/build/piplite-wheels \
    --output-dir=/opt/jupyterlite \
    && test -f /opt/jupyterlite/api/contents/all.json \
    && test -f /opt/jupyterlite/static/pyodide/pyodide.js \
    && test -f /opt/jupyterlite/api/pypi/all.json \
    && grep -q 'comm-0.2.2-py3-none-any.whl' /opt/jupyterlite/api/pypi/all.json \
    && grep -q '"pyodideUrl": "./static/pyodide/pyodide.js"' /opt/jupyterlite/jupyter-lite.json
COPY scripts/externalize_inline_scripts.py /usr/local/bin/externalize-inline-scripts
RUN externalize-inline-scripts /opt/jupyterlite

WORKDIR /app/reasonreport
ENV JUPYTERLITE_PATH=/opt/jupyterlite
CMD flask run -h 0.0.0.0 -p 5000
